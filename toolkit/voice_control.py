"""Opt-in isolated voice policy/configuration, never a Gateway configuration writer.
One atomic document holds settings plus rollback history; no services or assets
are installed. Effective local_voice config is exported only as a Python value.
"""
import argparse
import copy
import json
from pathlib import Path
from .approval_ledger import digest
from .isolated_store import Store
from .local_voice import asset

ALLOWED={'mode','profile','local_voice','routes'}

def merge(base,patch):
    result=copy.deepcopy(base)
    for key,value in patch.items():
        if isinstance(value,dict) and isinstance(result.get(key),dict): result[key]=merge(result[key],value)
        else: result[key]=copy.deepcopy(value)
    return result

def validate(settings):
    if settings.get('mode','off') not in {'off','inbound'}: raise ValueError('Only off/inbound voice supported')
    if settings.get('profile','female') not in {'female','male'}: raise ValueError('Explicit female/male profile required')
    routes=settings.get('routes',[])
    if not isinstance(routes,list): raise ValueError('Explicit isolated routes required')
    for r in routes:
        if not isinstance(r,dict) or set(r)!={'channel','account','peer'} or not all(isinstance(v,str) and v for v in r.values()): raise ValueError('Exact direct route required')
    if len({json.dumps(r,sort_keys=True) for r in routes})!=len(routes): raise ValueError('Duplicate route')
    cfg=settings.get('local_voice',{})
    if not isinstance(cfg,dict): raise ValueError('Local voice object required')
    if settings.get('mode')=='inbound':
        if not routes or cfg.get('model_license_reviewed') is not True: raise ValueError('Reviewed model licenses and exact routes required')
        for key in ('ffmpeg','asr','encoder','decoder','tokens','piper'): asset(cfg[key])
        voices=cfg.get('voices',{}).get(settings.get('profile','female'),{})
        if not voices: raise ValueError('Reviewed profile voices required')
        for value in voices.values(): asset(value)

class VoiceControl:
    def __init__(self,root,*,enabled=False): self.store=Store(root,'voice');self.enabled=enabled
    def _read(self):
        value=self.store.read()
        return value or {'format':'toolkit-isolated-voice-v1','generation':0,'settings':{'mode':'off','profile':'female'},'history':[]}
    def _check(self,value,expected):
        if not self.enabled: raise PermissionError('Explicit isolated mutation opt-in required')
        if value.get('format')!='toolkit-isolated-voice-v1': raise ValueError('Not isolated toolkit voice state')
        if digest(value)!=expected: raise ValueError('STALE_CONFIG_CAS')
    def status(self):
        with self.store.guard():
            value=self._read()
            return {'etag':digest(value),'generation':value['generation'],'settings':copy.deepcopy(value['settings']),'activated':False}
    def apply(self,patch,*,expected):
        if not isinstance(patch,dict) or not patch or set(patch)-ALLOWED: raise ValueError('Only isolated voice keys accepted')
        with self.store.guard():
            value=self._read();self._check(value,expected)
            settings=merge(value['settings'],patch);validate(settings)
            previous=copy.deepcopy(value['settings'])
            value['history'].append({'generation':value['generation'],'settings':previous,'sha256':digest(previous)})
            value['generation']+=1;value['settings']=settings
            self.store.save(value)
            return {'etag':digest(value),'generation':value['generation'],'activated':False}
    def rollback(self,generation,*,expected):
        with self.store.guard():
            value=self._read();self._check(value,expected)
            selected=next((h for h in value['history'] if h['generation']==generation),None)
            if selected is None or digest(selected['settings'])!=selected['sha256']: raise ValueError('Verified prior generation required')
            validate(selected['settings'])
            value['history'].append({'generation':value['generation'],'settings':value['settings'],'sha256':digest(value['settings'])})
            value['settings']=copy.deepcopy(selected['settings']);value['generation']+=1
            self.store.save(value)
            return {'etag':digest(value),'generation':value['generation'],'activated':False}
    def local_config(self,route):
        settings=self.status()['settings'];validate(settings)
        if settings.get('mode')!='inbound' or route not in settings.get('routes',[]): raise PermissionError('Voice disabled for this route')
        return copy.deepcopy(settings['local_voice']),settings['profile']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True);p.add_argument('--enable-isolated-write',action='store_true')
    sub=p.add_subparsers(dest='command',required=True);sub.add_parser('status')
    a=sub.add_parser('apply');a.add_argument('--patch',required=True);a.add_argument('--expected',required=True)
    a=sub.add_parser('rollback');a.add_argument('--generation',type=int,required=True);a.add_argument('--expected',required=True)
    a=p.parse_args();control=VoiceControl(a.root,enabled=a.enable_isolated_write)
    result=control.status() if a.command=='status' else control.apply(json.loads(Path(a.patch).read_text()),expected=a.expected) if a.command=='apply' else control.rollback(a.generation,expected=a.expected)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
