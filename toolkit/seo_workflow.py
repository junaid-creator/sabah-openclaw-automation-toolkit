"""Durable SEO draft pipeline using existing controller, WP and outbox.

Explicit provider callbacks; no automatic publication or inferred external APIs.
"""
from .blog_controller import Controller
from .blog_assets import read_upload_image
from .draft_primitives import create_once
from .reliability import Run
from .report_outbox import Outbox
from .trusted_bridge import fingerprint

class SEO:
    def __init__(self,controller,wp,*,expected_wp_user,enabled=False):
        self.c,self.wp,self.user,self.enabled=controller,wp,expected_wp_user,enabled
        if type(expected_wp_user) is not int or expected_wp_user<=0:raise ValueError('Expected WP user required')

    def prepare(self,*,research,article,start_images,read_images):
        if not self.enabled:raise PermissionError('Draft workflow not activated')
        if self.wp.request('/wp-json/wp/v2/users/me?context=edit').get('id')!=self.user:
            raise PermissionError('Wrong WP identity')
        self.c.step('inventory',lambda state:{'posts':self.wp.posts()})
        self.c.step('research',research)
        self.c.step('article',article)
        state=self.c.load();stage=state['stages'].get('images')
        if not stage:
            self.c.begin('images')
            # Intent is durable before provider start. Failure never reissues start.
            task=start_images(state['stages']['article']['result'])
            self.c.record_image_task(task)
            stage=self.c.load()['stages']['images']
        if stage['state']!='verified':
            task=stage.get('image_task',{}).get('id')
            if not task:raise RuntimeError('Image task identity unknown; do not regenerate')
            receipt=read_images(task)
            if not receipt or receipt.get('status')!='completed':return {'state':'WAITING_IMAGES','task_id':task}
            self.c.recover_image_assets(receipt)
        return {'state':'READY','run_id':self.c.rid}

    def draft(self,*,validate):
        if not self.enabled:raise PermissionError('Draft writes disabled')
        state=self.c.load();article=state['stages']['article']['result']
        if set(article)!={'title','content','excerpt','slug','keyword'} or not all(isinstance(v,str) and v.strip() for v in article.values()):
            raise ValueError('Exact reviewed article fields required')
        if state['stages'].get('images',{}).get('state')!='verified':raise RuntimeError('Completed image receipt required')
        images=state['stages']['images']['result']['images']
        plan={'article':article,'images':images,'wp_user':self.user,'origin':self.wp.base}
        self.c.verify_plan_images(plan)
        self.c.step('plan',lambda state:plan)
        if self.c.load()['stages']['plan']['result']!=plan:raise ValueError('Frozen plan changed')
        def create(state):
            if self.wp.request('/wp-json/wp/v2/users/me?context=edit').get('id')!=self.user:raise PermissionError('WP identity changed')
            with Run(self.c.rid+'-cms',plan,root=self.c.root/'cms') as run:
                media=[]
                for i,image in enumerate(images):
                    raw=read_upload_image(image,asset_root=self.c.asset_root/self.c.rid)
                    m=create_once(run,'image-'+str(i),lambda raw=raw,i=i:self.wp.request('/wp-json/wp/v2/media',binary=raw,filename=self.c.rid+'-'+str(i)+'.webp'),lambda mid:self.wp.request('/wp-json/wp/v2/media/'+str(mid)+'?context=edit'))
                    if m.get('media_type')!='image' or m.get('mime_type')!='image/webp':raise ValueError('Invalid media readback')
                    # Metadata has a separate create-once-style intent; an unknown
                    # response is reconciled by exact readback, never blindly rewritten.
                    fields={k:image[k] for k in ('title','caption')};fields['alt_text']=image['alt']
                    op='metadata-'+str(i);prior=run.data['operations'].get(op)
                    current=self.wp.request('/wp-json/wp/v2/media/'+str(m['id'])+'?context=edit')
                    def exact(row):return all((row.get(k,{}).get('raw') if isinstance(row.get(k),dict) else row.get(k))==v for k,v in fields.items())
                    if not exact(current):
                        if prior:raise RuntimeError('Media metadata uncertain; reconcile without replay')
                        run.checkpoint(op,'sending',object_id=m['id'])
                        try:self.wp.request('/wp-json/wp/v2/media/'+str(m['id']),fields)
                        except Exception:pass
                        current=self.wp.request('/wp-json/wp/v2/media/'+str(m['id'])+'?context=edit')
                        if not exact(current):raise RuntimeError('Media metadata not verified')
                    run.checkpoint(op,'verified',object_id=m['id']);media.append(m['id'])
                payload={k:article[k] for k in ('title','content','excerpt','slug')};payload.update(status='draft',featured_media=media[0])
                post=create_once(run,'post',lambda:self.wp.request('/wp-json/wp/v2/posts',payload),lambda pid:self.wp.request('/wp-json/wp/v2/posts/'+str(pid)+'?context=edit'))
                for k,v in payload.items():
                    value=post.get(k)
                    if isinstance(value,dict):value=value.get('raw')
                    if value!=v:raise ValueError('Draft readback mismatch: '+k)
                return {'post_id':post['id'],'url':post['link'],'status':'draft','media_ids':media,'plan_sha256':fingerprint(plan)}
        result=self.c.step('draft',create)
        def verify(state):
            proof=validate(result,plan)
            if not isinstance(proof,dict) or proof.get('passed') is not True or proof.get('plan_sha256')!=fingerprint(plan):
                raise ValueError('Independent exact-plan validation required')
            return proof
        self.c.step('validation',verify)
        box=Outbox(self.c.root/'owner-outbox.json',account=self.c.account,recipient=self.c.recipient)
        box.prepare(self.c.rid,{'title':article['title'],'post_id':result['post_id'],'topic':article['title'],'keyword':article['keyword'],'status':'Draft','url':result['url'],'sheets':'Separate tracker adapter required','blocker':''})
        return result

    def deliver(self,*,sender,enabled=False):
        if not enabled:raise PermissionError('Owner notification disabled')
        box=Outbox(self.c.root/'owner-outbox.json',account=self.c.account,recipient=self.c.recipient)
        rows=__import__('json').loads((self.c.root/'owner-outbox.json').read_text())
        row=rows[self.c.rid]
        if row['state']=='sent':return self.c.finish_report()
        claim=box.claim(self.c.rid)
        try:receipt=sender(self.c.account,self.c.recipient,claim)
        except Exception:receipt=None
        if not isinstance(receipt,dict) or receipt.get('delivered') is not True or receipt.get('dryRun') or receipt.get('account')!=self.c.account or receipt.get('recipient')!=self.c.recipient or not receipt.get('message_id'):
            box.receipt(self.c.rid,account=self.c.account,recipient=self.c.recipient)
            raise RuntimeError('Owner notification unknown; no resend')
        box.receipt(self.c.rid,receipt['message_id'],account=self.c.account,recipient=self.c.recipient)
        return self.c.finish_report()
