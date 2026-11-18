"""Official TikTok Login Kit WEB OAuth v2; not the Business API token family.
No environment/private account discovery, callback server or implicit network.
"""
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from .isolated_store import Store
from .approval_ledger import digest

AUTHORIZE='https://www.tiktok.com/v2/auth/authorize/'
TOKEN='https://open.tiktokapis.com/v2/oauth/token/'

class OAuthError(RuntimeError): pass
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*a,**kw): raise OAuthError('REDIRECT_REFUSED')

class OfficialTransport:
    def __init__(self, *, enabled=False): self.enabled=enabled
    def __call__(self,url,form):
        if not self.enabled or url!=TOKEN: raise OAuthError('LIVE_OAUTH_DISABLED')
        request=Request(url,data=urlencode(form).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','Cache-Control':'no-cache'},method='POST')
        try:
            with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=20) as r:
                raw=r.read(65537)
                if len(raw)>65536 or r.status!=200: raise OAuthError('INVALID_RESPONSE')
                return json.loads(raw)
        except Exception: raise OAuthError('TOKEN_OUTCOME_UNKNOWN') from None

def hashed(value): return hashlib.sha256(value.encode()).hexdigest()

class OAuth:
    def __init__(self,root,*,client_key,client_secret,redirect_uri,scopes,transport=None,clock=time.time):
        p=urlsplit(redirect_uri)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.query or p.fragment or len(redirect_uri)>=512:
            raise ValueError('Exact registered static HTTPS web redirect required')
        if not client_key or not client_secret or not scopes or any(not isinstance(s,str) or not s or ',' in s for s in scopes):
            raise ValueError('Explicit application and scope configuration required')
        self.store=Store(root,'oauth');self.key=client_key;self.secret=client_secret
        self.redirect,self.scopes,self.transport,self.clock=redirect_uri,sorted(set(scopes)),transport or OfficialTransport(),clock
        self.binding=digest({'client_key':client_key,'redirect':redirect_uri,'scopes':self.scopes,'family':'login-kit-web-v2'})
    def _read(self):
        state=self.store.read()
        if state and state.get('binding')!=self.binding: raise OAuthError('STORE_APPLICATION_MISMATCH')
        return state or {'binding':self.binding,'phase':'EMPTY'}
    def start(self,session,*,ttl=300):
        """session is an opaque authenticated browser-session ID, never callback input."""
        if not isinstance(session,str) or len(session)<16 or not 0<ttl<=600: raise ValueError('Bounded authenticated session required')
        with self.store.guard():
            state=self._read()
            if state['phase'] in {'EXCHANGING','REFRESHING','UNKNOWN'}: raise OAuthError('RECONCILIATION_REQUIRED')
            nonce=secrets.token_urlsafe(32)
            state.update(phase='WAITING',state_hash=hashed(nonce),session_hash=hashed(session),expires=self.clock()+ttl)
            self.store.save(state)
            return AUTHORIZE+'?'+urlencode({'client_key':self.key,'redirect_uri':self.redirect,'scope':','.join(self.scopes),'state':nonce,'response_type':'code'})
    def _candidate(self,response,pin=None):
        if not isinstance(response,dict) or response.get('error'): raise OAuthError('TOKEN_RESPONSE_REJECTED')
        keys=('access_token','refresh_token','open_id','scope','token_type')
        if any(not isinstance(response.get(k),str) or not response[k] or len(response[k])>16384 for k in keys): raise OAuthError('TOKEN_SCHEMA_INVALID')
        if response['token_type'].lower()!='bearer' or not set(self.scopes)<=set(response['scope'].split(',')): raise OAuthError('TOKEN_SCOPE_OR_TYPE_INVALID')
        if pin and response['open_id']!=pin: raise OAuthError('ACCOUNT_CHANGED')
        for k in ('expires_in','refresh_expires_in'):
            if type(response.get(k)) is not int or not 0<response[k]<=366*24*3600: raise OAuthError('TOKEN_EXPIRY_INVALID')
        return {**{k:response[k] for k in keys},'expires_at':self.clock()+response['expires_in'],
                'refresh_expires_at':self.clock()+response['refresh_expires_in']}
    def _exchange(self,state,form,pin=None):
        try:
            response=self.transport(TOKEN,{'client_key':self.key,'client_secret':self.secret,**form})
            candidate=self._candidate(response,pin)
            state.update(tokens=candidate,phase='READY')
            for k in ('state_hash','session_hash','expires'): state.pop(k,None)
            self.store.save(state)
        except Exception:
            # Consumed code/rotated refresh may have succeeded remotely. Never replay.
            state['phase']='UNKNOWN'; self.store.save(state)
            raise OAuthError('TOKEN_OUTCOME_REQUIRES_RECONCILIATION') from None
        return self._status(state)
    def finish(self,callback,session):
        if not isinstance(callback,str) or len(callback)>8192: raise OAuthError('CALLBACK_INVALID')
        p=urlsplit(callback);base=urlsplit(self.redirect)
        if (p.scheme,p.netloc,p.path)!=(base.scheme,base.netloc,base.path) or p.fragment: raise OAuthError('CALLBACK_URI_MISMATCH')
        query=parse_qs(p.query,keep_blank_values=True,max_num_fields=12)
        if any(len(v)!=1 for v in query.values()) or not query.get('state'): raise OAuthError('CALLBACK_PARAMETERS_INVALID')
        with self.store.guard():
            state=self._read()
            if state['phase']!='WAITING' or self.clock()>=state['expires']: raise OAuthError('STATE_EXPIRED_OR_CONSUMED')
            if not hmac.compare_digest(hashed(query['state'][0]),state['state_hash']) or not hmac.compare_digest(hashed(session),state['session_hash']): raise OAuthError('STATE_SESSION_MISMATCH')
            if query.get('error'):
                state['phase']='DENIED';self.store.save(state);raise OAuthError('CONSENT_DENIED')
            if not query.get('code') or not query['code'][0]: raise OAuthError('CODE_REQUIRED')
            state['phase']='EXCHANGING';self.store.save(state)
            return self._exchange(state,{'grant_type':'authorization_code','code':query['code'][0],'redirect_uri':self.redirect},state.get('tokens',{}).get('open_id'))
    def refresh(self,*,force=False):
        with self.store.guard():
            state=self._read()
            if state['phase']!='READY': raise OAuthError('READY_TOKEN_REQUIRED')
            token=state['tokens']
            if token['refresh_expires_at']<=self.clock(): raise OAuthError('REAUTHORIZATION_REQUIRED')
            if not force and token['expires_at']>self.clock()+120: return self._status(state)
            state['phase']='REFRESHING';self.store.save(state)
            return self._exchange(state,{'grant_type':'refresh_token','refresh_token':token['refresh_token']},token['open_id'])
    @staticmethod
    def _status(state):
        token=state.get('tokens',{})
        return {'phase':state['phase'],'family':'login-kit-web-v2','expires_at':token.get('expires_at'),'refresh_expires_at':token.get('refresh_expires_at'),'scope':token.get('scope')}
    def status(self):
        with self.store.guard(): return self._status(self._read())
    def access_token(self):
        """Explicit secret accessor for compatible Login Kit consumers only."""
        with self.store.guard():
            state=self._read()
            if state['phase']!='READY' or state['tokens']['expires_at']<=self.clock(): raise OAuthError('VALID_TOKEN_REQUIRED')
            return state['tokens']['access_token']
