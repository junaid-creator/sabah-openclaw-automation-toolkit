"""Portable guarded GOG adapter; no credential-file discovery or implicit writes."""
import hashlib,json,os,subprocess
from .lead_sheet_merge import merged
TABS=('All Leads','Qualified Leads','Reviewed / Contacted')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def normalized(rows):
    if not isinstance(rows,list) or any(not isinstance(r,list) or len(r)>19 for r in rows):raise ValueError('Invalid 19-column Sheet response')
    return [list(r)+['']*(19-len(r)) for r in rows]
class GogSheets:
    def __init__(self,account,client,*,executable='gog',runner=subprocess.run,env=None,allow_reads=False,allow_writes=False):
        if not account or not client or account.startswith('-') or client.startswith('-'):raise ValueError('Explicit account/client required')
        self.account,self.client,self.executable=account,client,executable
        self.runner=runner;self.allow_reads,self.allow_writes=allow_reads,allow_writes
        source=os.environ if env is None else env
        self.env={k:v for k,v in source.items() if k in {'PATH','HOME','USER','LANG','LC_ALL','GOG_KEYRING_BACKEND','GOG_KEYRING_PASSWORD','GOG_ACCOUNT'}}
    def _request(self,*args):
        write=args[0]!='get'
        if not self.allow_reads or (write and not self.allow_writes):raise RuntimeError('GOG operation disabled')
        cmd=[self.executable,'sheets',*args,'--account',self.account,'--client',self.client,'--json','--no-input']
        try:r=self.runner(cmd,text=True,capture_output=True,env=self.env,timeout=45,check=False)
        except (OSError,subprocess.TimeoutExpired):raise RuntimeError('GOG request outcome uncertain; reconcile before retry') from None
        if r.returncode:raise RuntimeError('GOG request failed; inspect privately without exposing credentials')
        return json.loads(r.stdout)
    def values(self,sheet_id,tab):
        if tab not in TABS:raise ValueError('Unsupported lead worksheet')
        return normalized(self._request('get',sheet_id,"'"+tab+"'!A:S").get('values') or [])
    def plan(self,sheet_id,tab,headers,incoming):
        old=self.values(sheet_id,tab);target=merged(headers,old,incoming)
        body={'sheet_id':sheet_id,'tab':tab,'before':old,'target':target}
        return {**body,'digest':digest(body)}
    def apply(self,plan,*,approved_digest):
        body={k:plan[k] for k in ('sheet_id','tab','before','target')}
        if approved_digest!=digest(body) or plan.get('digest')!=approved_digest:raise ValueError('Exact reviewed plan approval required')
        current=self.values(plan['sheet_id'],plan['tab'])
        if current==plan['target']:return {'status':'VERIFIED','writes':0}
        if current!=plan['before']:raise RuntimeError('Sheet changed since review')
        if not self.allow_writes:raise RuntimeError('GOG writes disabled')
        address="'"+plan['tab']+"'!A1:S"+str(len(plan['target']))
        try:self._request('update',plan['sheet_id'],address,'--values-json='+json.dumps(plan['target']),'--input=RAW')
        except Exception:
            if self.values(plan['sheet_id'],plan['tab'])!=plan['target']:raise RuntimeError('Sheet write uncertain; no automatic replay') from None
        if self.values(plan['sheet_id'],plan['tab'])!=plan['target']:raise RuntimeError('Exact Sheet readback failed; no replay')
        return {'status':'VERIFIED','writes':1}
