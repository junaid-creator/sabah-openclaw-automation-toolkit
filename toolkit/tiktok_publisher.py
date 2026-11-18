"""TikTok API for Business Accounts API. No credentials or response bodies logged.

Photo publishing only. Submission is deliberately separate from status polling;
the approval engine journals the in-flight transition before calling submit().
"""
from __future__ import annotations
import fcntl, hashlib, importlib.util, io, json, os, re, tempfile, time
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request
from .meta_publisher import urlopen

BASE='https://business-api.tiktok.com/open_api/v1.3/'


class Blocked(RuntimeError): pass
class Retry(RuntimeError):
    def __init__(self,code,delay=60):super().__init__(code);self.delay=delay
class Unknown(RuntimeError): pass



def request(method,endpoint,*,token=None,body=None,params=None,submission=False):
    # Endpoints are constants; never accept caller-supplied API hosts.
    if not re.fullmatch(r'[a-z0-9_/]+',endpoint):raise Blocked('TIKTOK_ENDPOINT_INVALID')
    headers={'Content-Type':'application/json'}
    if token:headers['Access-Token']=token
    req=Request(BASE+endpoint+('?' +urlencode(params) if params else ''),
        data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
    try:
        with urlopen(req,timeout=25) as response:
            status=response.status;raw=response.read(2*1024*1024);retry=response.headers.get('Retry-After','60')
    except HTTPError as exc:
        status=exc.code;raw=exc.read(2*1024*1024);retry=exc.headers.get('Retry-After','60')
    except Exception:
        if submission:raise Unknown('TIKTOK_SUBMISSION_OUTCOME_UNKNOWN') from None
        raise Retry('TIKTOK_READ_UNAVAILABLE') from None
    try:data=json.loads(raw)
    except (ValueError,UnicodeError):
        if submission:raise Unknown('TIKTOK_SUBMISSION_RESPONSE_INVALID') from None
        raise Retry('TIKTOK_RESPONSE_INVALID') from None
    if status>=500 or status in {408,425}:
        if submission:raise Unknown('TIKTOK_SUBMISSION_OUTCOME_UNKNOWN')
        raise Retry('TIKTOK_SERVICE_UNAVAILABLE')
    code=data.get('code')
    if status==429 or code==40100:
        try:delay=max(60,float(retry))
        except (ValueError,TypeError):delay=60
        raise Retry('TIKTOK_RATE_LIMIT',delay)
    if status>=400 or code!=0:
        safe=str(code) if isinstance(code,int) else str(status)
        raise Blocked('TIKTOK_API_REJECTED_'+safe)
    if not isinstance(data.get('data'),dict):
        if submission:raise Unknown('TIKTOK_SUBMISSION_DATA_MISSING')
        raise Retry('TIKTOK_DATA_MISSING')
    return data['data']

class Client:
    def __init__(self, config, token_provider, transport=request, clock=time.time, *, live_enabled=False, authorize=None):
        self._config=dict(config);self.token_provider=token_provider;self.transport=transport;self.clock=clock
        self.live_enabled=live_enabled;self.authorize=authorize or (lambda payload:False)
    def config(self):
        if not all(self._config.get(k) for k in ('client_id','client_secret','expected_open_id','approved_media_hosts')):
            raise Blocked('TIKTOK_EXPLICIT_CONFIGURATION_REQUIRED')
        return dict(self._config)
    def account_binding(self):
        cfg=self.config()
        if not cfg.get('expected_open_id'):raise Blocked('TIKTOK_ACCOUNT_NOT_VERIFIED')
        return {'client_id':cfg['client_id'],'open_id':cfg['expected_open_id'],
            'privacy_level':'PUBLIC_TO_EVERYONE','is_brand_organic':True,'is_branded_content':False}
    def tokens(self,force=False):
        token=self.token_provider(force=force)
        if not isinstance(token,dict) or not token.get('access_token') or token.get('open_id')!=self.config()['expected_open_id']:
            raise Blocked('TIKTOK_ACCOUNT_MISMATCH')
        return token
    def api(self,method,endpoint,**kw):
        token=self.tokens()
        return self.transport(method,endpoint,token=token['access_token'],**kw)
    def identity(self,require_bound=True,require_verification=False):
        cfg=self.config();token=self.tokens()
        value=self.transport('POST','tt_user/token_info/get/',body={'app_id':cfg['client_id'],'access_token':token['access_token']})
        if str(value.get('app_id'))!=str(cfg['client_id']) or value.get('creator_id')!=token['open_id']:
            raise Blocked('TIKTOK_TOKEN_IDENTITY_MISMATCH')
        if require_bound and self.account_binding()['open_id']!=value['creator_id']:raise Blocked('TIKTOK_ACCOUNT_MISMATCH')
        scopes=set(str(value.get('scope','')).split(','))
        if 'video.publish' not in scopes:raise Blocked('TIKTOK_VIDEO_PUBLISH_PERMISSION_REQUIRED')
        if require_verification and 'video.list' not in scopes:raise Blocked('TIKTOK_VIDEO_LIST_PERMISSION_REQUIRED')
        return {'open_id':value['creator_id'],'app_id':value['app_id'],'scopes':sorted(scopes)}
    def properties(self):
        cfg=self.config()
        return self.transport('GET','business/property/list/',params={'app_id':cfg['client_id'],'secret':cfg['client_secret']}).get('url_property_info_list',[])
    def verified_url(self,url):
        parsed=urlsplit(url);host=(parsed.hostname or '').lower()
        if parsed.scheme!='https' or host not in self.config()['approved_media_hosts'] or parsed.username or parsed.password or parsed.port or parsed.fragment:
            raise Blocked('TIKTOK_MEDIA_URL_NOT_APPROVED')
        for item in self.properties():
            if item.get('property_status')!=1:continue
            prop=str(item.get('url',''));kind=item.get('property_type')
            if kind==1:
                domain=(urlsplit(prop if '://' in prop else 'https://'+prop).hostname or '').lower()
                if domain and (host==domain or host.endswith('.'+domain)):return
            if kind==2:
                base=urlsplit(prop)
                if base.scheme==parsed.scheme and base.netloc==parsed.netloc and (parsed.path==base.path or parsed.path.startswith(base.path.rstrip('/')+'/')):return
        raise Blocked('TIKTOK_MEDIA_DOMAIN_OWNERSHIP_NOT_VERIFIED')
    def prepare(self,url,caption):
        self.identity(require_verification=True);self.verified_url(url)
        if len(caption.encode('utf-16-le'))//2>4000:raise Blocked('TIKTOK_CAPTION_EXCEEDS_4000_UTF16')
        if len(re.findall(r'(?<!\w)@\w+',caption))>30:raise Blocked('TIKTOK_TOO_MANY_MENTIONS')
        settings=self.api('GET','business/video/settings/',params={'business_id':self.account_binding()['open_id']})
        if 'PUBLIC_TO_EVERYONE' not in settings.get('privacy_level_options',[]):raise Blocked('TIKTOK_PUBLIC_POSTING_NOT_ALLOWED')
        return {'business_id':self.account_binding()['open_id'],'photo_images':[url],'photo_cover_index':0,
            'post_info':{'caption':caption,'privacy_level':'PUBLIC_TO_EVERYONE','is_brand_organic':True,
              'is_branded_content':False,'disable_comment':bool(settings.get('comment_disabled',True)),'auto_add_music':False,'is_draft':False}}
    def submit(self,payload):
        if not self.live_enabled or self.authorize(payload) is not True: raise Blocked("TIKTOK_EXPLICIT_APPROVAL_REQUIRED")
        if payload.get("business_id")!=self.account_binding()["open_id"]: raise Blocked("TIKTOK_ACCOUNT_MISMATCH")
        result=self.api('POST','business/photo/publish/',body=payload,submission=True)
        task=result.get('share_id')
        if not isinstance(task,str) or not task:raise Unknown('TIKTOK_TASK_ID_MISSING')
        return task
    def status(self,task):return self.api('GET','business/publish/status/',params={'business_id':self.account_binding()['open_id'],'publish_id':task})
    def public_post(self,post_id):
        """Return an owned public post with its official share URL, if indexed.

        PUBLISH_COMPLETE plus a post ID proves processing completed, but it is
        not used as a public-link receipt. The Accounts API read is the second,
        independent check. It requires the video.list permission.
        """
        post_id=str(post_id)
        try:
            result=self.api('GET','business/video/list/',params={
                'business_id':self.account_binding()['open_id'],
                'fields':json.dumps(['item_id','media_type','create_time','caption','share_url','embed_url']),
                'filters':json.dumps({'video_ids':[post_id]}),'max_count':20})
        except Blocked as exc:
            if str(exc)=='TIKTOK_API_REJECTED_40130':
                raise Blocked('TIKTOK_VIDEO_LIST_PERMISSION_REQUIRED') from None
            raise
        rows=result.get('videos') or result.get('list') or []
        matches=[row for row in rows if str(row.get('item_id') or row.get('video_id') or '')==post_id]
        if not matches:return None
        if len(matches)!=1:raise Blocked('TIKTOK_PUBLIC_POST_LOOKUP_AMBIGUOUS')
        row=matches[0];share=str(row.get('share_url') or '')
        parsed=urlsplit(share);host=(parsed.hostname or '').lower()
        if parsed.scheme!='https' or not (host=='tiktok.com' or host.endswith('.tiktok.com')) or post_id not in parsed.path:
            raise Blocked('TIKTOK_PUBLIC_SHARE_URL_INVALID')
        return {**row,'item_id':post_id,'share_url':share}

def verify_public_post(client,post_id):
    row=client.public_post(post_id)
    if not row:raise Retry('TIKTOK_PUBLIC_POST_NOT_INDEXED',300)
    return row['share_url']

def reconcile_existing(ledger,job,client):
    """Read ONLY the already accepted task; never invokes prepare or submit."""
    op=ledger.op(job,'tiktok');known=ledger.get(job,'tiktok')
    if not op or not op.get('container_id') or not known:raise Blocked('TIKTOK_EXISTING_TASK_REQUIRED')
    result=client.status(op['container_id'])
    state=result.get('status');ids=result.get('post_ids') or []
    ledger.event(job,'TIKTOK_READ_ONLY_STATUS',json.dumps({'status':state,'post_ids':ids}))
    outcome='PROCESSING'
    if state=='PUBLISH_COMPLETE' and len(ids)==1 and re.fullmatch(r'\d+',str(ids[0])):
        post_id=str(ids[0])
        try:
            permalink=verify_public_post(client,post_id)
        except Retry as exc:
            ledger.update(job,'tiktok','CONTAINER_CREATED',remote_id=post_id,error_code=str(exc))
            ledger.setop(job,'tiktok',phase='VERIFYING',next_at=time.time()+exc.delay)
        except Blocked as exc:
            ledger.update(job,'tiktok','UNCERTAIN',remote_id=post_id,error_code=str(exc))
            ledger.setop(job,'tiktok',phase='NEEDS_ACTION',next_at=0)
            outcome='NEEDS_ACTION'
        else:
            ledger.update(job,'tiktok','PUBLISHED',remote_id=post_id,permalink=permalink)
            ledger.setop(job,'tiktok',phase='PUBLISHED',next_at=0)
            outcome='VERIFIED'
        ledger.setjob(job,sheet_pending=1)
    elif state=='PUBLISH_COMPLETE' and not ids:
        ledger.update(job,'tiktok','UNCERTAIN',error_code='TIKTOK_PUBLISH_COMPLETE_MISSING_POST_IDS')
        ledger.setop(job,'tiktok',phase='NEEDS_ACTION',next_at=0)
        ledger.setjob(job,sheet_pending=1)
        outcome='NEEDS_ACTION'
    elif state=='FAILED':
        ledger.update(job,'tiktok','FAILED_FINAL',error_code='TIKTOK_PUBLISH_FAILED_'+re.sub(r'[^A-Za-z0-9_]','_',str(result.get('reason','unknown')))[:70])
        ledger.setop(job,'tiktok',phase='FAILED',next_at=0);ledger.setjob(job,sheet_pending=1)
        outcome='FAILED'
    elif state=='SEND_TO_USER_INBOX':
        ledger.update(job,'tiktok','UNCERTAIN',error_code='TIKTOK_CREATOR_IN_APP_ACTION_REQUIRED')
        ledger.setop(job,'tiktok',phase='NEEDS_ACTION',next_at=0);ledger.setjob(job,sheet_pending=1)
        outcome='NEEDS_ACTION'
    return {'job_id':job,'task_id':op['container_id'],'remote_status':state,'post_ids':ids,
        'outcome':outcome,'link_status':'VERIFIED' if outcome=='VERIFIED' else 'LINK_PENDING_VERIFICATION',
        'publishing_performed':False,'new_submissions':0}

def validate_photo(raw):
    from PIL import Image
    if len(raw)>20*1024*1024:raise Blocked('TIKTOK_PHOTO_EXCEEDS_20MB')
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {'JPEG','WEBP'}:raise Blocked('TIKTOK_PHOTO_FORMAT_UNSUPPORTED')
            w,h=image.size
            if not ((w<=1080 and h<=1920) or (w<=1920 and h<=1080)):raise Blocked('TIKTOK_PHOTO_DIMENSIONS_UNSUPPORTED')
            image.verify()
    except Blocked:raise
    except Exception:raise Blocked('TIKTOK_PHOTO_INVALID') from None
    return hashlib.sha256(raw).hexdigest()

def advance(engine,job,content):
    """One durable submission; every subsequent run polls that same task."""
    p='tiktok';ledger=engine.ledger;op=ledger.op(job,p);known=ledger.get(job,p)
    if known and known['state'] in {'PUBLISHED','FAILED_FINAL','UNCERTAIN'}:return
    client=engine.tiktok
    try:
        if op.get('container_id') and (op['checks']>=480 or engine.clock()-(op['started_at'] or engine.clock())>86400):
            ledger.update(job,p,'UNCERTAIN',error_code='TIKTOK_STATUS_REVIEW_REQUIRED');return
        if not op.get('container_id'):
            if op['phase']=='PUBLISH_IN_FLIGHT':
                if not known:ledger.reserve(job,p,4)
                ledger.update(job,p,'UNCERTAIN',error_code='TIKTOK_TASK_UNKNOWN_NO_BLIND_RETRY');return
            if op['tries']>=4:
                if not known:ledger.reserve(job,p,4)
                ledger.update(job,p,'FAILED_FINAL',error_code='TIKTOK_RETRY_LIMIT');return
            payload=client.prepare(content.get('tiktok_asset_url') or content['final_master_asset_url'],engine.caption(content,p))
            engine.checked(job)
            if not known or known['state']=='FAILED_RETRYABLE':ledger.reserve(job,p,4)
            ledger.setop(job,p,phase='PUBLISH_IN_FLIGHT',started_at=engine.clock(),tries=op['tries']+1)
            task=client.submit(payload)
            ledger.setop(job,p,phase='TASK_ACCEPTED',container_id=task,next_at=engine.clock()+60)
            ledger.update(job,p,'CONTAINER_CREATED',remote_id=task)
            ledger.event(job,'TIKTOK_TASK_ACCEPTED',task);ledger.setjob(job,sheet_pending=1)
            return
        result=client.status(op['container_id']);state=result.get('status');checks=op['checks']+1
        ledger.event(job,'TIKTOK_STATUS',str(state)[:60])
        if state=='PUBLISH_COMPLETE' and result.get('post_ids'):
            ids=result['post_ids']
            if len(ids)!=1 or not re.fullmatch(r'\d+',str(ids[0])):raise Blocked('TIKTOK_UNEXPECTED_POST_IDENTIFIERS')
            post_id=str(ids[0])
            try:permalink=verify_public_post(client,post_id)
            except Retry as exc:
                ledger.update(job,p,'CONTAINER_CREATED',remote_id=post_id,error_code=str(exc));ledger.setop(job,p,phase='VERIFYING',checks=checks,next_at=engine.clock()+exc.delay)
            except Blocked as exc:
                ledger.update(job,p,'UNCERTAIN',remote_id=post_id,error_code=str(exc));ledger.setop(job,p,phase='NEEDS_ACTION',checks=checks,next_at=0)
            else:
                ledger.update(job,p,'PUBLISHED',remote_id=post_id,permalink=permalink);ledger.setop(job,p,phase='PUBLISHED',checks=checks,next_at=0)
            ledger.setjob(job,sheet_pending=1);return
        if state=='PUBLISH_COMPLETE' and not result.get('post_ids'):
            # The accepted task may precede post indexing. Poll only this task;
            # never submit again. Exhaustion still fails closed for review.
            if checks>=480 or engine.clock()-(op['started_at'] or engine.clock())>86400:
                ledger.update(job,p,'UNCERTAIN',error_code='TIKTOK_POST_ID_TIMEOUT');ledger.setjob(job,sheet_pending=1);return
            ledger.setop(job,p,phase='AWAITING_POST_ID',checks=checks,next_at=engine.clock()+180)
            ledger.setjob(job,sheet_pending=1);return
        if state=='FAILED':
            reason=re.sub(r'[^A-Za-z0-9_]','_',str(result.get('reason','unknown')))[:70]
            raise Blocked('TIKTOK_PUBLISH_FAILED_'+reason)
        if state=='SEND_TO_USER_INBOX':raise Blocked('TIKTOK_CREATOR_IN_APP_ACTION_REQUIRED')
        if checks>=480 or engine.clock()-(op['started_at'] or engine.clock())>86400:
            ledger.update(job,p,'UNCERTAIN',error_code='TIKTOK_STATUS_REVIEW_REQUIRED');return
        ledger.setop(job,p,checks=checks,next_at=engine.clock()+180)
    except Retry as exc:
        if not ledger.get(job,p):ledger.reserve(job,p,4)
        current=ledger.op(job,p)
        if current.get('container_id'):
            ledger.setop(job,p,next_at=engine.clock()+max(180,exc.delay),checks=current['checks']+1)
        else:
            ledger.update(job,p,'FAILED_RETRYABLE',error_code=str(exc));ledger.setop(job,p,phase='PENDING',tries=max(current['tries'],op['tries']+1),next_at=engine.clock()+max(exc.delay,60*2**min(op['tries'],5)))
    except Unknown:
        ledger.update(job,p,'UNCERTAIN',error_code='TIKTOK_SUBMISSION_UNKNOWN_NO_BLIND_RETRY')
    except Blocked as exc:
        if not ledger.get(job,p):ledger.reserve(job,p,4)
        ledger.update(job,p,'FAILED_FINAL',error_code=str(exc))
