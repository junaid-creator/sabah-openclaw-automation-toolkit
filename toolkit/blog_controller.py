"""Source-derived stage orchestration; all provider/CMS/message adapters are injected."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .reliability import STATE,lock,atomic_json,state_path
from .report_outbox import Outbox
from .blog_assets import read_upload_image
STAGES=("inventory","research","article","images","plan","draft","validation","report")

def day_id(now=None,timezone_name="UTC"):
    return 'blog-daily-'+(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(timezone_name)).date().isoformat()

class Controller:
    def __init__(self, rid=None, root=STATE, *, account, recipient, asset_root=None, timezone_name="UTC"):
        if not account or not recipient: raise ValueError("Explicit report destination required")
        self.account,self.recipient=account,recipient
        self.asset_root=Path(asset_root) if asset_root else Path(root)/"assets"
        self.rid=rid or day_id(timezone_name=timezone_name); self.root=Path(root)
        if not re.fullmatch(r'blog-daily-\d{4}-\d{2}-\d{2}',self.rid):
            raise ValueError('Daily controller requires stable configured-date run ID')
        self.path=self.root/(self.rid+'-controller.json')
    def load(self):
        return json.loads(self.path.read_text()) if self.path.exists() else dict(run_id=self.rid,stages={})
    def step(self, stage, callback):
        if stage not in STAGES: raise ValueError('Unknown stage')
        with lock(self.root/'controller.lock'):
            data=self.load(); prior=data['stages'].get(stage)
            if prior and prior['state']=='verified': return prior['result']
            if prior: raise RuntimeError('REVIEW_REQUIRED: interrupted '+stage+'; reconcile saved task/objects, never regenerate')
            for earlier in STAGES[:STAGES.index(stage)]:
                if data['stages'].get(earlier,{}).get('state')!='verified':
                    raise RuntimeError('Complete prerequisite '+earlier)
            data['stages'][stage]=dict(state='sending')
            atomic_json(self.path,data)
            try:
                result=callback(data)
                if not result: raise ValueError('Empty stage evidence')
                if stage=='images' and (not isinstance(result,dict) or result.get('status')!='completed'): raise ValueError('Queued image task is not complete')
            except Exception as error:
                data['stages'][stage]=dict(state='blocked',error_type=type(error).__name__)
                atomic_json(self.path,data)
                self.failure(stage, type(error).__name__)
                raise
            data['stages'][stage]=dict(state='verified',result=result)
            atomic_json(self.path,data)
            return result
    def begin(self, stage):
        if stage not in STAGES: raise ValueError('Unknown stage')
        with lock(self.root/'controller.lock'):
            data=self.load()
            if stage in data['stages']: return data['stages'][stage]
            for earlier in STAGES[:STAGES.index(stage)]:
                if data['stages'].get(earlier,{}).get('state')!='verified':
                    raise RuntimeError('Complete prerequisite '+earlier)
            data['stages'][stage]=dict(state='sending')
            atomic_json(self.path,data)
            return dict(state='sending',claimed=True)
    def finish(self, stage, artifact):
        with lock(self.root/'controller.lock'):
            data=self.load(); prior=data['stages'].get(stage,{})
            if prior.get('state')=='verified':
                if prior['result']!=artifact: raise RuntimeError('Completed stage differs')
                return prior['result']
            if prior.get('state')!='sending': raise RuntimeError('Stage must be reserved first')
            if not artifact: raise ValueError('Empty completion evidence')
            data['stages'][stage]=dict(state='verified',result=artifact)
            if stage == 'images' and prior.get('image_task'):
                data['stages'][stage]['image_task'] = prior['image_task']
            atomic_json(self.path,data)
            return artifact
    def record_image_task(self, task_id, now=None):
        """Bind a provider receipt to the reserved image stage; never submit a task."""
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_:.\-/]{1,250}', task_id):
            raise ValueError('Invalid image task ID')
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None: raise ValueError('Timezone-aware timestamp required')
        with lock(self.root/'controller.lock'):
            data = self.load(); stage = data['stages'].get('images')
            if not stage or stage.get('state') not in ('sending','verified'):
                raise RuntimeError('Image stage must be reserved first')
            existing = stage.get('image_task')
            if existing:
                if existing.get('id') != task_id: raise RuntimeError('Image task already bound; reconcile existing task')
                return existing
            if stage.get('state') != 'sending': raise RuntimeError('Cannot add receipt to completed image stage')
            receipt = dict(id=task_id, recorded_at=now.astimezone(timezone.utc).isoformat())
            stage['image_task'] = receipt
            atomic_json(self.path,data)
            return receipt
    def image_task_status(self, now=None, max_age_seconds=1800):
        """Inspect a saved receipt; missing or stale evidence always requires review."""
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or max_age_seconds <= 0: raise ValueError('Invalid time or timeout')
        with lock(self.root/'controller.lock'):
            stage = self.load()['stages'].get('images')
            if not stage: return dict(status='not_started', resubmit=False)
            if stage.get('state') == 'verified': return dict(status='verified', resubmit=False)
            receipt = stage.get('image_task')
            if not receipt: return dict(status='unknown', resubmit=False, reason='No saved provider receipt; reconcile manually')
            try:
                recorded = datetime.fromisoformat(receipt['recorded_at'])
                if recorded.tzinfo is None: raise ValueError('naive')
                elapsed = (now - recorded).total_seconds()
                if elapsed < 0: raise ValueError('future')
            except (ValueError, TypeError, KeyError):
                return dict(status='unknown', resubmit=False, reason='Invalid receipt timestamp')
            if stage.get('state') != 'sending': return dict(status='review_required', resubmit=False, task_id=receipt['id'])
            return dict(status='timed_out' if elapsed >= max_age_seconds else 'pending',
                        resubmit=False, task_id=receipt['id'], recorded_at=receipt['recorded_at'])
    def recover_image_assets(self, receipt):
        """Resume a saved task from its completed tool receipt and local WebPs.

        This never submits or polls a provider. The caller must obtain the
        completed receipt through the existing agent tool and keep it durable.
        """
        stage = self.load().get('stages', {}).get('images', {})
        saved = stage.get('image_task', {})
        if not saved.get('id') or receipt.get('task_id') != saved['id']:
            raise ValueError('Completed receipt does not match the saved image task')
        if receipt.get('status') != 'completed':
            raise ValueError('Image task has not completed')
        images = receipt.get('images')
        if not isinstance(images, list) or len(images) != 3:
            raise ValueError('Exactly three completed image assets required')
        asset_root = (self.asset_root/self.rid).resolve()
        hashes = set()
        for image in images:
            if not isinstance(image, dict) or not all(image.get(k) for k in ('path','sha256','alt','title','caption')):
                raise ValueError('Image metadata incomplete')
            if not Path(image['path']).resolve().is_relative_to(asset_root):
                raise ValueError('Image must belong to this daily run')
            read_upload_image(image,asset_root=self.asset_root/self.rid)
            hashes.add(image['sha256'])
        if len(hashes) != 3:
            raise ValueError('Image assets must be distinct')
        return self.finish('images', receipt)

    def verify_plan_images(self, plan):
        """Bind the draft plan to the completed, validated image-task receipt."""
        stage = self.load().get('stages', {}).get('images', {})
        receipt = stage.get('result', {})
        if stage.get('state') != 'verified' or receipt.get('status') != 'completed':
            raise RuntimeError('Completed image task receipt required before draft creation')
        if receipt.get('task_id') != stage.get('image_task', {}).get('id'):
            raise RuntimeError('Image task receipt does not match the saved task')
        images = receipt.get('images')
        if not isinstance(images, list) or len(images) != 3 or plan.get('images') != images:
            raise RuntimeError('Draft images differ from the validated image task result')
        for image in images:
            read_upload_image(image,asset_root=self.asset_root/self.rid)
        if len({image['sha256'] for image in images}) != 3:
            raise RuntimeError('Draft images must be distinct')

    def finish_report(self, published=False, publication_run_id=None):
        # Derive completion from durable tool receipt, not caller success booleans.
        path=self.root/'owner-outbox.json'
        rows=json.loads(path.read_text()) if path.exists() else {}
        key=self.rid+'-published' if published else self.rid
        row=rows.get(key,{})
        if published:
            if not publication_run_id: raise ValueError('Explicit publication run ID required')
            saved=json.loads(state_path(publication_run_id,self.root).read_text())
            operation=saved.get('operations',{}).get('publish',{})
            receipt=operation.get('evidence',{})
            payload=row.get('payload',{})
            if (operation.get('state')!='verified' or receipt.get('status')!='publish'
                or payload.get('status')!='Published' or payload.get('post_id')!=receipt.get('post_id')
                or payload.get('url')!=receipt.get('url')):
                raise RuntimeError('Published owner report does not match verified publication')
        if (row.get('state')!='sent' or not row.get('message_id')
            or row.get('account')!=self.account or row.get('recipient')!=self.recipient):
            raise RuntimeError('Confirmed owner message-tool receipt required')
        self.begin('report')
        return self.finish('report',dict(outbox_key=key,message_id=row['message_id']))

    def failure(self, stage, error):
        box=Outbox(self.root/'owner-outbox.json',account=self.account,recipient=self.recipient); stage_label=re.sub(r'[^A-Za-z0-9_-]+', '-', str(stage)).strip('-')[:32] or 'unknown'; digest=hashlib.sha256((str(stage)+'|'+str(error)).encode()).hexdigest()[:16]; key=self.rid+'-failure-'+stage_label+'-'+digest
        path=self.root/'owner-outbox.json'
        if path.exists() and key in json.loads(path.read_text()): return key
        box.prepare(key,dict(title='Daily SEO blog blocked',post_id='',topic='',keyword='',status='Failed',url='',
             sheets='Checkpoint preserved',blocker=stage+': '+error))
        return key
    def run(self, adapters):
        """Adapters must return durable JSON; images adapter waits/records task ID,
        never treats queued generation as verified. Subsequent invocations reuse outputs.
        Interrupted stages require operator reconciliation, not blind retries.
        """
        for stage in STAGES:
            if stage not in adapters: raise ValueError('Missing tool adapter: '+stage)
            self.step(stage,adapters[stage])
        return self.load()
