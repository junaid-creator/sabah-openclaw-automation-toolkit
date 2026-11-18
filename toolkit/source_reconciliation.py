"""Strict source/Sheet row binding for product plans; no inferred destructive edits."""
from .trusted_bridge import fingerprint


def snapshot(rows, *, identity='source_id', formulas=None):
    if not isinstance(rows,list) or not rows:
        raise ValueError('Nonempty source rows required')
    ids=[]
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get(identity),str) or not row[identity]:
            raise ValueError('Stable source identity required')
        ids.append(row[identity])
    if len(set(ids)) != len(ids): raise ValueError('Duplicate source identity')
    if formulas is not None and (not isinstance(formulas,list) or len(formulas)!=len(rows)):
        raise ValueError('Formula view must match source rows')
    value={'rows':rows,'identity':identity,'formulas':formulas}
    return {'value':value,'sha256':fingerprint(value)}


def row_request(bound, source_id, fields, *, site, product_id=None):
    if fingerprint(bound['value']) != bound['sha256']: raise ValueError('Source snapshot altered')
    rows=[r for r in bound['value']['rows'] if r[bound['value']['identity']]==source_id]
    if len(rows)!=1: raise ValueError('Source row missing')
    if not isinstance(fields,dict) or not fields: raise ValueError('Explicit source column mapping required')
    row=rows[0]
    if any(column not in row for column in fields.values()): raise ValueError('Source column missing')
    request={'site':site,'operation':'edit' if product_id else 'create','fields':{k:row[v] for k,v in fields.items()}}
    if product_id is not None: request['product_id']=product_id
    return {'request':request,'source_id':source_id,'source_sha256':bound['sha256']}


def revalidate(bound, reader):
    """reader returns fresh VALUE and FORMULA snapshots; no write occurs here."""
    current=reader()
    if current != bound or fingerprint(current['value']) != bound['sha256']:
        raise RuntimeError('Source/formulas changed; discard plan and obtain new approval')
    return True


def mirror_once(path, binding, *, reader, writer, exclusive_writer=False):
    """Exact before/after Sheet write with durable uncertain-write fencing.

    Provider APIs lack atomic compare-and-swap. Exclusive writer is a mandatory
    deployment prerequisite, not a guarantee supplied by this helper.
    """
    from pathlib import Path
    import json
    from .reliability import lock,atomic_json
    if not exclusive_writer: raise PermissionError('Exclusive Sheet writer required')
    if set(binding) != {'before','after','range','source_id'}: raise ValueError('Exact mirror binding required')
    p=Path(path)
    with lock(p.with_suffix('.lock')):
        old=json.loads(p.read_text()) if p.exists() else None
        if old and old['digest'] != fingerprint(binding): raise ValueError('Operation identity changed')
        current=reader(binding['range'])
        if old:
            if current==binding['after']:
                atomic_json(p,{'digest':fingerprint(binding),'state':'VERIFIED'})
                return 'VERIFIED'
            raise RuntimeError('Uncertain Sheet outcome; no automatic retry')
        if current!=binding['before']: raise RuntimeError('Sheet changed before write')
        atomic_json(p,{'digest':fingerprint(binding),'state':'SENDING'})
        try: writer(binding['range'],binding['after'])
        except Exception: pass
        if reader(binding['range'])!=binding['after']:
            raise RuntimeError('Sheet readback not exact; reconcile without replay')
        atomic_json(p,{'digest':fingerprint(binding),'state':'VERIFIED'})
        return 'VERIFIED'
