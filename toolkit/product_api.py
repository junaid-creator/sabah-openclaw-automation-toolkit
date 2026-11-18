"""Original scoped WooCommerce v3 adapter; official REST protocol, no write retries."""
import copy
import re
from urllib.parse import urlencode
from .wordpress import WP
from .trusted_bridge import fingerprint

STATUSES = ('publish', 'future', 'draft', 'pending', 'private', 'trash')
ROOT = '/wp-json/wc/v3/products'
MARKER = '_portable_product_operation'


def positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError('Positive integer identity required')
    return value


def normalized(value):
    import html
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC', html.unescape(str(value))).casefold().split())


# Only server-derived fields may change without explicit review. Unknown fields stay protected.
DERIVED = {'date_modified', 'date_modified_gmt', 'price_html', 'on_sale', '_links'}


def stable(record):
    result = copy.deepcopy(record)
    for key in DERIVED:
        result.pop(key, None)
    # Media/taxonomy descriptive attributes are separately bound as dependencies.
    for key in ('images', 'categories'):
        if key in result:
            result[key] = [{'id': positive(x['id'])} for x in result[key]]
    if 'image' in result and result['image']:
        result['image'] = {'id': positive(result['image']['id'])}
    if 'meta_data' in result:
        meta = result['meta_data']
        if len({m['key'] for m in meta}) != len(meta):
            raise ValueError('Duplicate metadata keys require manual review')
        result['meta_data'] = sorted([{'key':m['key'], 'value':m['value']} for m in meta], key=lambda m:m['key'])
    if 'attributes' in result:
        result['attributes'] = sorted(result['attributes'], key=lambda a: (a.get('id', 0), a.get('name', '')))
    return result


def matches(record, fields):
    actual = stable(record)
    wanted = stable(fields)
    return all(actual.get(k) == v for k, v in wanted.items())


class Woo:
    def __init__(self, site, username, password, *, allow_network=False, allow_write=False, opener=None):
        self.site = copy.deepcopy(site)
        self.wp = WP(site['origin'], username, password, allow_network=allow_network,
                     allow_write=allow_write, opener=opener)
        positive(site['wp_user_id'])

    def identity(self):
        user = self.wp.request('/wp-json/wp/v2/users/me?context=edit')
        if user.get('id') != self.site['wp_user_id']:
            raise PermissionError('Unexpected authenticated site user')

    def pages(self, path, **query):
        out = []
        for page in range(1, 101):
            batch = self.wp.request(path + '?' + urlencode(dict(query, per_page=100, page=page)))
            if not isinstance(batch, list) or any(not isinstance(r, dict) for r in batch):
                raise ValueError('Invalid collection response')
            out.extend(batch)
            if len(batch) < 100:
                return out
        raise ValueError('Complete inventory exceeds safety bound')

    def catalog(self):
        """Explicit statuses include trash; an unsupported status fails closed."""
        parents = []
        for status in STATUSES:
            batch = self.pages(ROOT, status=status, context='edit')
            if any(r.get('status') != status for r in batch):
                raise ValueError('Status filter not honored')
            parents.extend(batch)
        ids = [positive(p['id']) for p in parents]
        if len(ids) != len(set(ids)):
            raise ValueError('Ambiguous catalog pagination')
        out = []
        for parent in parents:
            out.append({'parent': parent, 'variations': self.variations(parent)})
        return out

    def variations(self, parent):
        if parent.get('type') != 'variable':
            if parent.get('variations'):
                raise ValueError('Unsupported child topology')
            return []
        rows = []
        for status in STATUSES:
            batch = self.pages(ROOT + '/' + str(positive(parent['id'])) + '/variations',
                               status=status, context='edit')
            if any(r.get('status') != status for r in batch):
                raise ValueError('Variation status filter not honored')
            rows.extend(batch)
        ids = [positive(r['id']) for r in rows]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate variation IDs')
        # Woo 11.2 read_children('all') includes publish/private only, not draft,
        # pending, future or trash. Retain every status for identity checks anyway.
        active = {r['id'] for r in rows if r['status'] in ('publish','private')}
        if set(parent.get('variations', [])) != active:
            raise ValueError('Incomplete variation inventory')
        return sorted(rows, key=lambda r:r['id'])

    def group(self, pid):
        parent = self.wp.request(ROOT + '/' + str(positive(pid)) + '?context=edit')
        if parent.get('id') != pid:
            raise ValueError('Wrong parent readback')
        return {'parent': parent, 'variations': self.variations(parent)}

    def dependency(self, kind, identity):
        if kind == 'media':
            value = self.wp.request('/wp-json/wp/v2/media/' + str(positive(identity)) + '?context=edit')
            if value.get('id') != identity or value.get('media_type') != 'image' or not value.get('mime_type', '').startswith('image/'):
                raise ValueError('Verified image attachment required')
            # Do not GET source_url: it may be an external CDN or hostile URL.
            return {k:value.get(k) for k in ('id','media_type','mime_type','source_url','slug','title','alt_text','media_details')}
        if kind == 'category':
            value = self.wp.request(ROOT + '/categories/' + str(positive(identity)))
            if value.get('id') != identity:
                raise ValueError('Category identity mismatch')
            return {k:value.get(k) for k in ('id','name','slug','parent')}
        raise ValueError('Unsupported dependency')

    def mutate(self, pid, fields, variation_id=None):
        path = ROOT + ('/' + str(positive(pid)) if pid is not None else '')
        if variation_id is not None:
            if pid is None:
                raise ValueError('Parent required')
            path += '/variations' + ('/' + str(positive(variation_id)) if variation_id else '')
        # WP issues one POST, refuses redirects and never retries.
        result = self.wp.request(path, fields)
        positive(result.get('id'))
        if variation_id and result['id'] != variation_id:
            raise ValueError('Wrong variation mutation receipt')
        if variation_id is None and pid and result['id'] != pid:
            raise ValueError('Wrong parent mutation receipt')
        return result
