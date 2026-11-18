"""Executable integration boundary: python -m toolkit.product_commands --help.

Input is a trusted-host HMAC-attested envelope, never a raw model/chat message.
No signing command or HTTP listener is exposed here.
"""
import argparse
import json
import os
from pathlib import Path
import sys
from .trusted_bridge import Bridge
from .product_api import Woo
from .product_workflow import Products


def dispatch(engine, envelope):
    if not isinstance(envelope,dict) or set(envelope)-{'event','signature','review_receipt'} or not {'event','signature'} <= set(envelope):
        raise PermissionError('Attested transport envelope required')
    event, signature = envelope['event'], envelope['signature']
    text = event.get('text','')
    if text.startswith('PRODUCT PLAN '):
        if 'review_receipt' in envelope: raise ValueError('Unexpected review receipt')
        return engine.plan(event,signature)
    words = text.split(' ')
    if len(words)==3 and words[0]=='PRODUCT' and words[1] in ('REVIEW','EXECUTE','REVOKE','RECONCILE','STATUS'):
        command,jid = words[1],words[2]
        if command=='REVIEW':
            return engine.challenge(jid,event,signature,review_receipt=envelope.get('review_receipt',{}))
        if 'review_receipt' in envelope: raise ValueError('Unexpected review receipt')
        return getattr(engine,command.lower())(jid,event,signature)
    if len(words)==2 and words[0]=='CONFIRM':
        # Resolve only the stored challenge; external job IDs cannot rebind it.
        with engine.db() as db:
            rows=db.execute('SELECT id FROM product_jobs WHERE challenge=?',(words[1],)).fetchall()
        if len(rows)!=1: raise PermissionError('Unknown product challenge')
        return engine.confirm(rows[0]['id'],event,signature)
    raise ValueError('One exact product command required; quoted commands do not authorize')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--state',required=True)
    parser.add_argument('--network',action='store_true')
    parser.add_argument('--writes',action='store_true')
    args=parser.parse_args(argv)
    os.umask(0o077)
    try:
        path=Path(args.config)
        if path.is_symlink() or path.stat().st_uid!=os.getuid() or path.stat().st_mode & 0o022:
            raise PermissionError('Operator-owned non-writable config required')
        config=json.loads(path.read_text())
        sites={s['id']:s for s in config['sites']}
        if len(sites)!=len(config['sites']): raise ValueError('Duplicate site')
        home=Path(args.state)
        home.mkdir(parents=True,exist_ok=True,mode=0o700)
        Products._private(home,directory=True)
        key=os.environ[config['bridge_key_env']].encode()
        bridge_path=home/'bridge.sqlite3'
        if bridge_path.exists(): Products._private(bridge_path)
        bridge=Bridge(bridge_path,key,config['routes'])
        def factory(site):
            return Woo(site,os.environ[site['username_env']],os.environ[site['password_env']],
                       allow_network=args.network,allow_write=args.writes)
        engine=Products(home,bridge,sites,factory,enabled=args.writes)
        raw=sys.stdin.read(131073)
        if len(raw)>131072: raise ValueError('Envelope too large')
        print(json.dumps(dispatch(engine,json.loads(raw)),ensure_ascii=False))
        return 0
    except Exception as error:
        # Provider exceptions and credentials are never included in outbound errors.
        print(json.dumps({'state':'BLOCKED','error_type':type(error).__name__}))
        return 2


if __name__=='__main__':
    raise SystemExit(main())
