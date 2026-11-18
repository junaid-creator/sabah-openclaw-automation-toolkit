"""Conservative product schemas and exact before/after projections."""
import copy
import re
from decimal import Decimal
from .product_api import positive, normalized, stable, MARKER
from .trusted_bridge import fingerprint

PARENT = {'name','description','short_description','regular_price','categories','images','meta_data'}
CHILD = {'regular_price','image','meta_data'}


def price(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:0|[1-9][0-9]*)(?:[.][0-9]{1,2})?', value):
        raise ValueError('Literal nonnegative decimal price required')
    return value


def fields(value, site, *, child=False, create=False):
    allowed = CHILD if child else PARENT
    if create:
        allowed = allowed | ({'sku','attributes'} if child else {'sku','type','attributes'})
    if not isinstance(value, dict) or set(value) - allowed or not value:
        raise ValueError('Unsupported/empty product fields; status, stock and discounts are protected')
    out = copy.deepcopy(value)
    for key in ('name','description','short_description'):
        if key in out and (not isinstance(out[key], str) or not out[key].strip() or len(out[key]) > 20000):
            raise ValueError('Nonempty bounded text required')
    if 'name' in out and (len(out['name']) > 180 or '<' in out['name'] or '>' in out['name']):
        raise ValueError('Plain product name required')
    if 'sku' in out and (not isinstance(out['sku'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', out['sku'])):
        raise ValueError('Explicit safe SKU required')
    if 'regular_price' in out:
        price(out['regular_price'])
    for key in ('categories','images'):
        if key in out:
            if not isinstance(out[key], list) or len(out[key]) > 30:
                raise ValueError('Bounded ID collection required')
            ids = []
            for item in out[key]:
                if not isinstance(item, dict) or set(item) != {'id'}:
                    raise ValueError('Only existing IDs accepted; remote URLs are forbidden')
                ids.append(positive(item['id']))
            if len(set(ids)) != len(ids):
                raise ValueError('Duplicate ID')
    if 'image' in out:
        if not isinstance(out['image'], dict) or set(out['image']) != {'id'}:
            raise ValueError('Only existing media ID accepted')
        positive(out['image']['id'])
    if 'meta_data' in out:
        if not isinstance(out['meta_data'], list) or len(out['meta_data']) > 30:
            raise ValueError('Bounded metadata required')
        keys = []
        for m in out['meta_data']:
            if not isinstance(m, dict) or set(m) != {'key','value'} or m['key'] not in site.get('metadata_keys', []) or m['key'] == MARKER:
                raise ValueError('Metadata key not operator-allowlisted')
            if not isinstance(m['value'], str) or len(m['value']) > 4000:
                raise ValueError('Metadata string required')
            keys.append(m['key'])
        if len(keys) != len(set(keys)):
            raise ValueError('Duplicate metadata key')
    if create:
        if not out.get('sku'):
            raise ValueError('Explicit SKU required for each created object')
        if not child and (not out.get('name') or out.get('type') not in ('simple','variable')):
            raise ValueError('Explicit name and simple/variable type required')
    if 'attributes' in out:
        attrs = out['attributes']
        if not isinstance(attrs, list) or not 1 <= len(attrs) <= 4:
            raise ValueError('One to four local attributes supported')
        names = []
        for attr in attrs:
            expected = {'name','option'} if child else {'name','options','visible','variation'}
            if not isinstance(attr, dict) or set(attr) != expected or not isinstance(attr['name'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9 -]{0,39}', attr['name']):
                raise ValueError('Explicit local attribute schema required')
            names.append(normalized(attr['name']))
            options = [attr['option']] if child else attr['options']
            if not isinstance(options, list) or not options or any(not isinstance(o, str) or not o.strip() or len(o)>80 for o in options) or len(set(map(normalized, options))) != len(options):
                raise ValueError('Distinct literal attribute options required')
            if not child and (attr['visible'] is not True or attr['variation'] is not True):
                raise ValueError('Visible variation attributes required')
        if len(set(names)) != len(names):
            raise ValueError('Duplicate attributes')
    return out


def merged(old, patch):
    value = copy.deepcopy(old)
    for key, item in patch.items():
        if key == 'meta_data':
            meta = {m['key']:m['value'] for m in old.get('meta_data', [])}
            meta.update({m['key']:m['value'] for m in item})
            value[key] = [{'key':k,'value':v} for k,v in meta.items()]
        else:
            value[key] = copy.deepcopy(item)
    if 'regular_price' in patch:
        if old.get('sale_price') or any(old.get(k) for k in ('date_on_sale_from','date_on_sale_to','date_on_sale_from_gmt','date_on_sale_to_gmt')):
            raise ValueError('Promotion-aware price changes require a separate adapter')
        if old.get('price') not in (None, '', old.get('regular_price')):
            raise ValueError('Unexplained effective price')
        value['price'] = patch['regular_price']
    return stable(value)


def group_stable(group):
    return {'parent':stable(group['parent']), 'variations':[stable(v) for v in sorted(group['variations'], key=lambda v:v['id'])]}


def duplicates(catalog, name, skus, *, except_id=None):
    if len(set(map(normalized, skus))) != len(skus):
        raise ValueError('Duplicate planned SKUs')
    models = re.findall(r'[a-z]+[- ]?[0-9]{2,}[a-z0-9-]*', normalized(name))
    for group in catalog:
        parent = group['parent']
        if parent['id'] == except_id:
            continue
        if normalized(parent['name']) == normalized(name):
            raise ValueError('All-status name duplicate')
        compact = re.sub(r'[- ]', '', normalized(parent['name']))
        if any(re.sub(r'[- ]', '', m) in compact for m in models):
            raise ValueError('Possible model-family duplicate; independent identity review needed')
        for item in [parent] + group['variations']:
            if item.get('sku') and normalized(item['sku']) in set(map(normalized, skus)):
                raise ValueError('All-status parent/variation SKU duplicate')


def build(request, site, api):
    if not isinstance(request, dict) or set(request) - {'site','operation','product_id','fields','variations'} or request.get('site') != site['id']:
        raise ValueError('Exact site-scoped request required')
    op = request.get('operation')
    if op not in ('create','edit','publish'):
        raise ValueError('Unsupported product operation')
    api.identity()
    catalog = api.catalog()
    before = None
    pid = request.get('product_id')
    if op == 'create':
        if pid is not None:
            raise ValueError('Creation cannot target an existing ID')
    else:
        positive(pid)
        hits = [g for g in catalog if g['parent']['id'] == pid]
        if len(hits) != 1 or hits[0]['parent']['status'] == 'trash':
            raise ValueError('Existing nontrashed parent required')
        before = group_stable(hits[0])
        if before['parent']['type'] not in ('simple','variable'):
            raise ValueError('Unsupported product type')
    if op == 'publish':
        if request.get('fields') or request.get('variations') or before['parent']['status'] != 'draft':
            raise ValueError('Separate publish accepts only an existing unchanged draft')
        patch = {'status':'publish'}
        variations = []
    else:
        patch = fields(request.get('fields'), site, create=op=='create')
        variations = request.get('variations', [])
        if not isinstance(variations, list) or len(variations) > 50:
            raise ValueError('At most fifty exact variation changes')
    steps = []
    expected = copy.deepcopy(before)
    if op == 'create':
        patch.update(status='draft', catalog_visibility='hidden', manage_stock=False,
                     stock_status='outofstock', stock_quantity=None, sale_price='',
                     date_on_sale_from=None, date_on_sale_to=None)
        patch.setdefault('images', [])
        patch.setdefault('categories', [])
        if patch['type'] == 'simple' and (variations or 'attributes' in patch or 'regular_price' not in patch):
            raise ValueError('Simple create requires price and no variants')
        if patch['type'] == 'variable' and ('regular_price' in patch or not variations or 'attributes' not in patch):
            raise ValueError('Variable create requires attributes and variants, not parent price')
    elif before['parent']['type'] == 'variable' and 'regular_price' in patch:
        raise ValueError('Variable prices belong to existing variation IDs')
    steps.append({'variation_id':None, 'fields':patch})
    if expected:
        expected['parent'] = merged(expected['parent'], patch)
    seen = set()
    for item in variations:
        if not isinstance(item, dict) or set(item) != ({'fields'} if op=='create' else {'id','fields'}):
            raise ValueError('Explicit variation schema required')
        child = fields(item['fields'], site, child=True, create=op=='create')
        vid = 0 if op=='create' else positive(item['id'])
        if op=='create':
            if not child.get('attributes') or 'regular_price' not in child:
                raise ValueError('Created variation needs attributes and price')
            schema = {a['name']:a['options'] for a in patch['attributes']}
            actual = {a['name']:a['option'] for a in child['attributes']}
            if set(actual) != set(schema) or any(v not in schema[k] for k,v in actual.items()):
                raise ValueError('Variant does not match parent options')
            identity = fingerprint(actual)
            child.update(status='publish', manage_stock=False, stock_status='outofstock',
                         stock_quantity=None, sale_price='', date_on_sale_from=None, date_on_sale_to=None)
        else:
            identity = vid
            found = [v for v in expected['variations'] if v['id']==vid and v['status']!='trash']
            if len(found)!=1:
                raise ValueError('Variation outside selected parent')
            expected['variations'][expected['variations'].index(found[0])] = merged(found[0], child)
        if identity in seen:
            raise ValueError('Duplicate variation change/combination')
        seen.add(identity)
        steps.append({'variation_id':vid,'fields':child})
    name = patch.get('name', before['parent']['name'] if before else '')
    skus = [s['fields']['sku'] for s in steps if 'sku' in s['fields']]
    if before:
        skus = [v['sku'] for v in [before['parent']]+before['variations'] if v.get('sku')]
    duplicates(catalog, name, skus, except_id=pid)
    dependencies = []
    dependency_steps = list(steps)
    if before:
        dependency_steps += [{'fields':v} for v in [before['parent']]+before['variations']]
    for step in dependency_steps:
        p = step['fields']
        for kind, ids in (('category', [x['id'] for x in p.get('categories', [])]),
                          ('media', [x['id'] for x in p.get('images', [])] + ([p['image']['id']] if p.get('image') else []))):
            for identity in ids:
                dep = {'kind':kind,'id':identity,'before':api.dependency(kind,identity)}
                if dep not in dependencies:
                    dependencies.append(dep)
    return {'request':copy.deepcopy(request), 'site':copy.deepcopy(site), 'operation':op,
            'product_id':pid, 'before':before, 'expected':expected, 'steps':steps,
            'dependencies':dependencies, 'identity':{'name':name,'skus':skus}}
