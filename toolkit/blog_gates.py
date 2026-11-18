"""Pure indexing and template admission checks over operator-supplied snapshots."""
class Pending(RuntimeError): pass

class Blocked(RuntimeError): pass

def snapshot_robots(snapshot):
    if snapshot.get('post_type') != 'post' or snapshot.get('status') != 'draft':
        raise Blocked('WordPress inspection did not identify a post draft')
    if snapshot.get('blog_public') != '1' or snapshot.get('password_protected'):
        raise Blocked('Website indexing or post access would block indexing')
    if snapshot.get('rankmath_active') is not True: raise Pending('Rank Math activation not confirmed')
    values=snapshot.get('post_robots')
    source='post'
    if values in ('',None,[]):
        custom=snapshot.get('custom_post_robots')
        if custom in (True,1,'on','1'):
            values=snapshot.get('post_type_robots'); source='post-type'
        elif custom in (False,0,'off','0',None):
            values=snapshot.get('global_robots'); source='global'
            if values in (False, None, '', []):
                values=snapshot.get('rankmath_empty_default'); source='rankmath-default'
        else: raise Pending('Rank Math post-type inheritance is unclear')
    if not isinstance(values,list): raise Pending('Effective Rank Math robots defaults unavailable')
    directives={str(x).strip().lower() for x in values}
    if 'index' not in directives or 'noindex' in directives or 'nofollow' in directives:
        raise Blocked('Saved Rank Math settings do not permit indexing and following')
    return {'robots_source':source,'saved_robots':sorted(directives),'blog_public':True,
            'preview_robots':'not verified: authenticated preview unavailable',
            'public_robots':'must be checked after publication'}

def snapshot_template(snapshot, expected_template_id):
    if type(expected_template_id) is not int or expected_template_id <= 0: raise ValueError("Explicit template ID required")
    if snapshot.get('post_type') != 'post' or snapshot.get('status') != 'draft':
        raise Blocked('Intended draft is not a normal post')
    if not snapshot.get('elementor_active') or not snapshot.get('theme_builder_active'):
        raise Blocked('Elementor or its theme builder is inactive')
    templates=snapshot.get('templates')
    if not isinstance(templates,list) or len(templates)>=101:
        raise Pending('Complete published template inventory unavailable')
    matched=[t for t in templates if t.get('id')==expected_template_id]
    if len(matched)!=1 or matched[0].get('kind') not in ('single-post','single'):
        raise Blocked('Published single-post template expected_template_id unavailable')
    if matched[0].get('conditions') != ['include/singular/post']:
        raise Pending('Template expected_template_id conditions require independent evaluation')
    for t in templates:
        if t.get('id')==expected_template_id: continue
        if t.get('kind') in ('single','single-post'):
            conditions=t.get('conditions')
            if not isinstance(conditions,list) or any('singular' in str(x) for x in conditions):
                raise Pending('Another single template may override template expected_template_id')
        elif not t.get('kind'):
            raise Pending('Published template with unknown applicability')
    return {'template_id':expected_template_id,'status':'publish','conditions':['include/singular/post'],
            'other_templates_checked':len(templates)-1,'theme_builder':'active'}
