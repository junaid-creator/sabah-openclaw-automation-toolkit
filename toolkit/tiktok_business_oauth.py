"""TikTok Accounts Business API v1.3 OAuth, distinct from Login Kit token storage.
Token endpoint/body and token-info contract verified against official indexed
Business docs; authorize URL must be operator-reviewed (not inferred here).
"""
import copy
import json
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, build_opener, ProxyHandler
from .tiktok_oauth import OAuth, OAuthError, NoRedirect
from .approval_ledger import digest
from .isolated_store import Store

BASE='https://business-api.tiktok.com/open_api/v1.3/'
EXCHANGE=BASE+'tt_user/oauth2/token/'
REFRESH=BASE+'tt_user/oauth2/refresh_token/'
INFO=BASE+'tt_user/token_info/get/'

class BusinessTransport:
    def __init__(self,*,enabled=False):self.enabled=enabled
    def __call__(self,url,body):
        if not self.enabled or url not in {EXCHANGE,REFRESH,INFO}:raise OAuthError('BUSINESS_OAUTH_DISABLED_OR_ENDPOINT_INVALID')
        req=Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=20) as response:
                raw=response.read(65537)
                if response.status!=200 or len(raw)>65536:raise OAuthError('INVALID_RESPONSE')
                return json.loads(raw)
        except Exception:raise OAuthError('BUSINESS_TOKEN_OUTCOME_UNKNOWN') from None

def envelope(value):
    if not isinstance(value,dict) or type(value.get('code')) is not int or value['code']!=0 or not isinstance(value.get('data'),dict):
        raise OAuthError('BUSINESS_RESPONSE_REJECTED')
    return value['data']

class BusinessOAuth(OAuth):
    def __init__(self,root,*,client_id,client_secret,redirect_uri,scopes,expected_open_id,transport=None,clock=None):
        import time
        super().__init__(root,client_key=client_id,client_secret=client_secret,redirect_uri=redirect_uri,scopes=scopes,
                         transport=transport or BusinessTransport(),clock=clock or time.time)
        if not isinstance(expected_open_id,str) or not expected_open_id:raise ValueError('Pinned Business account required')
        self.store=Store(root,'business-oauth');self.pin=expected_open_id
        self.binding=digest({'client_id':client_id,'redirect':redirect_uri,'scopes':self.scopes,
                             'family':'business-accounts-v1.3','open_id':expected_open_id})
    def start(self,session,*,ttl=300):
        """Return state/redirect contract, NOT an unverified authorization URL.
        Trusted web adapter inserts state into its reviewed Business consent URL.
        """
        generated=super().start(session,ttl=ttl)
        state=parse_qs(urlsplit(generated).query)['state'][0]
        return {'state':state,'redirect_uri':self.redirect,'client_id':self.key,'scopes':self.scopes,
                'family':'business-accounts-v1.3','authorization_url':'OPERATOR_REVIEW_REQUIRED'}
    def finish(self,callback,session):
        if not isinstance(callback,str) or len(callback)>8192:raise OAuthError('CALLBACK_INVALID')
        p=urlsplit(callback);q=parse_qs(p.query,keep_blank_values=True,max_num_fields=12)
        if 'auth_code' in q:
            if 'code' in q or len(q['auth_code'])!=1:raise OAuthError('CALLBACK_CODE_AMBIGUOUS')
            q['code']=q.pop('auth_code')
            callback=p._replace(query=urlencode(q,doseq=True)).geturl()
        return super().finish(callback,session)
    def _exchange(self,state,form,pin=None):
        # Reuse durable claim/locking/state validation, never Login Kit transport.
        endpoint=EXCHANGE if form['grant_type']=='authorization_code' else REFRESH
        body={'client_id':self.key,'client_secret':self.secret,**form}
        if 'code' in body:body['auth_code']=body.pop('code')
        try:
            raw=envelope(self.transport(endpoint,body))
            required=('access_token','refresh_token','open_id')
            if any(not isinstance(raw.get(k),str) or not raw[k] or len(raw[k])>16384 for k in required):raise OAuthError('BUSINESS_TOKEN_PAIR_REQUIRED')
            if raw['open_id']!=self.pin or (pin and raw['open_id']!=pin):raise OAuthError('BUSINESS_ACCOUNT_CHANGED')
            if type(raw.get('expires_in')) is not int or not 120<raw['expires_in']<=366*86400:raise OAuthError('BUSINESS_EXPIRY_INVALID')
            info=envelope(self.transport(INFO,{'app_id':self.key,'access_token':raw['access_token']}))
            if str(info.get('app_id'))!=self.key or info.get('creator_id')!=self.pin or not isinstance(info.get('scope'),str) or not set(self.scopes)<=set(info['scope'].split(',')):
                raise OAuthError('BUSINESS_TOKEN_IDENTITY_OR_SCOPE_MISMATCH')
            # Original implementation does not require a refresh-expiry field.
            # Keep explicit response expiry when present; otherwise unknown,
            # not an invented lifetime. Provider rejection requires reauth.
            remaining=raw.get('refresh_token_expires_in')
            if remaining is not None and (type(remaining) is not int or not 0<remaining<=366*86400):raise OAuthError('BUSINESS_REFRESH_EXPIRY_INVALID')
            candidate={k:raw[k] for k in required}
            candidate.update(scope=info['scope'],expires_at=self.clock()+raw['expires_in'],
                             refresh_expires_at=self.clock()+remaining if remaining is not None else None,
                             token_type='Bearer',family='business-accounts-v1.3')
            state.update(tokens=candidate,phase='READY')
            for key in ('state_hash','session_hash','expires'):state.pop(key,None)
            self.store.save(state)
        except Exception:
            state['phase']='UNKNOWN';self.store.save(state)
            raise OAuthError('BUSINESS_TOKEN_RECONCILIATION_REQUIRED') from None
        return self._status(state)
    def refresh(self,*,force=False):
        with self.store.guard():
            state=self._read()
            if state['phase']!='READY':raise OAuthError('READY_BUSINESS_TOKEN_REQUIRED')
            token=state['tokens']
            if token['refresh_expires_at'] is not None and token['refresh_expires_at']<=self.clock():raise OAuthError('REAUTHORIZATION_REQUIRED')
            if not force and token['expires_at']>self.clock()+120:return self._status(state)
            state['phase']='REFRESHING';self.store.save(state)
            return self._exchange(state,{'grant_type':'refresh_token','refresh_token':token['refresh_token']},self.pin)
    @staticmethod
    def _status(state):
        result=OAuth._status(state);result['family']='business-accounts-v1.3';return result
    def token_provider(self,*,force=False):
        """Compatible with existing Business publisher Client token_provider.
        May refresh only through the explicitly supplied transport; never sends posts.
        """
        self.refresh(force=force)
        with self.store.guard():
            state=self._read()
            if state['phase']!='READY' or state['tokens']['expires_at']<=self.clock():raise OAuthError('VALID_BUSINESS_TOKEN_REQUIRED')
            return copy.deepcopy(state['tokens'])
