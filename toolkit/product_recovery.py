"""Build a NEW reviewed restoration plan; never automatic rollback or deletion."""
import copy
from .trusted_bridge import fingerprint
from .product_plan import build, group_stable, merged


def restore_plan(source, request, site, api, snapshot):
    if set(request) != {'site','operation','source_job'} or request['operation']!='restore' or request['source_job']!=source['id']:
        raise ValueError('Restore accepts only site and a recorded source job')
    p=source['plan']
    if source['state']!='VERIFIED' or p['operation']!='edit' or p['site']!=site or not p['before']:
        raise ValueError('Only a verified existing-product edit can be restored')
    if snapshot.get('plan')!=p or snapshot.get('binding',{}).get('plan_sha256')!=source['digest']:
        raise ValueError('Before snapshot identity mismatch')
    after=source['receipt'].get('after')
    current=group_stable(api.group(p['product_id']))
    if current!=after:
        raise ValueError('Current target differs from recorded after-state; no restoration plan')
    fields={};variations=[]
    for step in p['steps']:
        vid=step['variation_id']
        before=p['before']['parent'] if vid is None else next(v for v in p['before']['variations'] if v['id']==vid)
        patch={}
        for key,value in step['fields'].items():
            if key=='meta_data':
                old={m['key']:m['value'] for m in before.get(key,[])}
                if any(m['key'] not in old for m in value):
                    raise ValueError('Restoring newly added metadata needs deletion; not supported')
                patch[key]=[{'key':m['key'],'value':old[m['key']]} for m in value]
            else:
                if key not in before:
                    raise ValueError('Cannot restore a previously absent field')
                patch[key]=copy.deepcopy(before[key])
        if vid is None:fields=patch
        else:variations.append({'id':vid,'fields':patch})
    edit_request={'site':site['id'],'operation':'edit','product_id':p['product_id'],'fields':fields}
    if variations:edit_request['variations']=variations
    result=build(edit_request,site,api)
    if result['before']!=after:
        raise ValueError('Target changed while constructing restoration')
    # Preserve current unrelated fields: the restoration is a patch, not an object overwrite.
    result.update(operation='restore',request=copy.deepcopy(request),
                  recovery={'source_job':source['id'],'source_plan_sha256':source['digest'],
                            'after_sha256':fingerprint(after),'before_snapshot_sha256':source['receipt']['backup']['sha256']})
    return result
