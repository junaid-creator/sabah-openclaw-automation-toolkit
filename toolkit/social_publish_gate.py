"""Exact frozen-row approval gate for social_review -> MetaPublisher integration."""
from .approval_ledger import PLATFORMS, digest

def verify_rows(binding,queue,content):
    targets=binding['targets']
    selected={p for p in PLATFORMS if str(queue.get(p,'')).upper() in {'TRUE','YES','1'}}
    return (queue.get('job_id')==binding['job_id'] and content.get('job_id')==binding['job_id']
        and selected==set(targets) and queue.get('approval_mode')=='MANUAL'
        and not any(queue.get(k) for k in ('publish_date','publish_time'))
        and content.get('final_master_asset_url')==binding['url']
        and all(content.get(p+'_asset_url') in (None,'',binding['url'])
                and content.get(p+'_caption')==binding['captions'][p]
                and not content.get(p+'_hashtags') for p in targets))

class BoundApprovalGate:
    """Wrap existing operational gate, never replace it with a Sheet boolean.
    Rechecks trusted Bridge approval, ledger binding and frozen rows every time.
    """
    def __init__(self,controller,sheets,operational_gate):
        self.controller,self.sheets,self.operational=controller,sheets,operational_gate
    def authorize(self,job_id,platform):
        try:
            # Called under controller dispatch lock: do not recursively acquire it.
            state=self.controller._read(job_id);binding=self.controller._binding(state)
            ledger=self.controller.ledger;saved=ledger.job(job_id)
            return bool(state['phase'] in {'APPROVED','DISPATCHING'} and platform in binding['targets']
                and self.controller.bridge.authorized(state['challenge'],binding)
                and saved and saved['fingerprint']==digest(binding) and saved['state']!='REVOKED'
                and not ledger.submission_blocked(job_id)
                and verify_rows(binding,self.sheets.read_queue_job(job_id),self.sheets.read_content_job(job_id))
                and self.operational.authorize(job_id,platform))
        except (KeyError,ValueError,RuntimeError,OSError):return False
