"""Reviewed binary media intake; independent of product mutation approval.

Only operator-owned source assets with explicit rights attestations are accepted.
An unknown POST outcome is permanently fenced until exact read-only reconciliation.
"""
import hashlib
import io
import json
from pathlib import Path
from PIL import Image
from .product_workflow import Products
from .reliability import atomic_json
from .trusted_bridge import canonical, fingerprint


class Media:
    def __init__(self, products, asset_root):
        self.products = products
        self.assets = Path(asset_root)
        Products._private(self.assets, directory=True)

    def asset(self, request):
        name = request['file']
        if not isinstance(name, str) or Path(name).name != name or not name.endswith('.webp'):
            raise ValueError('One local WebP basename required')
        p = self.assets / name
        Products._private(p)
        if p.stat().st_size > 8_000_000:
            raise ValueError('Asset size limit')
        raw = p.read_bytes()
        if hashlib.sha256(raw).hexdigest() != request['sha256']:
            raise ValueError('Asset hash changed')
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'WEBP' or not 1 <= image.width * image.height <= 24_000_000:
                raise ValueError('Bounded WebP image required')
            image.verify()
        if request.get('rights') not in ('owned', 'licensed-for-this-use'):
            raise PermissionError('Explicit image rights required')
        if not isinstance(request.get('rights_reference'), str) or not request['rights_reference'].strip():
            raise PermissionError('Rights evidence reference required')
        return raw

    def path(self, jid):
        import re
        if not re.fullmatch(r'media-[a-f0-9]{24}', jid):
            raise ValueError('Invalid media job')
        return self.products.home / (jid + '.json')

    def load(self, jid):
        p = self.path(jid)
        Products._private(p)
        j = json.loads(p.read_text())
        if fingerprint(j['binding']) != j['digest']:
            raise PermissionError('Media binding changed')
        if self.products.sites.get(j['binding']['site']['id']) != j['binding']['site']:
            raise PermissionError('Site configuration changed')
        return j

    def plan(self, event, signature):
        if not event['text'].startswith('MEDIA PLAN '):
            raise ValueError('Exact media plan command required')
        request = json.loads(event['text'][11:])
        if set(request) != {'site','file','sha256','rights','rights_reference'}:
            raise ValueError('Exact media request fields required')
        site = self.products.sites[request['site']]
        owner = self.products.owner(event, signature, site)
        raw = self.asset(request)
        binding = {'kind':'media-upload', 'site':site, 'request':request,
                   'bytes':len(raw), 'owner':owner}
        jid = 'media-' + fingerprint({'event':event['id'],'binding':binding})[:24]
        with self.products.lock():
            if self.path(jid).exists():
                j = self.load(jid)
                if j['binding'] != binding:
                    raise PermissionError('Media job collision')
            else:
                j = {'id':jid,'binding':binding,'digest':fingerprint(binding),'state':'DRAFT'}
                atomic_json(self.path(jid), j)
        return {'job_id':jid,'binding':binding,'state':j['state']}

    def challenge(self, jid, event, signature, review_receipt):
        with self.products.lock():
            j = self.load(jid)
            owner = self.products.owner(event,signature,j['binding']['site'])
            if owner != j['binding']['owner'] or event['text'] != 'MEDIA REVIEW '+jid or j['state'] != 'DRAFT':
                raise PermissionError('Exact owner draft review required')
            c = self.products.bridge.challenge(event,signature,j['binding'],review_receipt=review_receipt)
            j['challenge'] = c['challenge_id']
            atomic_json(self.path(jid),j)
            return c

    def revoke(self, jid, event, signature):
        j = self.load(jid)
        owner = self.products.owner(event, signature, j['binding']['site'])
        if owner != j['binding']['owner'] or event['text'] != 'MEDIA REVOKE '+jid:
            raise PermissionError('Exact owner media revocation required')
        with self.products.bridge.db() as db:
            db.execute('BEGIN IMMEDIATE')
            self.products.bridge.remember(db,event)
            db.execute("UPDATE challenges SET state='REVOKED' WHERE id=? AND binding=?",
                       (j.get('challenge'),canonical(j['binding'])))
        return {'job_id':jid,'revoked':True,'remote_undo':False}

    def execute(self, jid, event, signature):
        with self.products.lock():
            j = self.load(jid)
            owner = self.products.owner(event,signature,j['binding']['site'])
            if owner != j['binding']['owner'] or event['text'] != 'MEDIA EXECUTE '+jid:
                raise PermissionError('Exact owner execution required')
            if j['state'] == 'VERIFIED':
                return j['receipt']
            if j['state'] != 'DRAFT':
                raise RuntimeError('Unknown upload outcome: reconcile, never replay')
            if not self.products.enabled or not self.products.bridge.authorized(j.get('challenge'),j['binding']):
                raise PermissionError('Bound media approval required')
            raw = self.asset(j['binding']['request'])
            api = self.products.api(j['binding']['site'])
            api.identity()
            filename = jid+'.webp'
            if not self.products.bridge.authorized(j.get('challenge'),j['binding']):
                raise PermissionError('Approval revoked before upload admission')
            j['state'] = 'SENDING'
            atomic_json(self.path(jid),j)
            try:
                receipt = api.wp.request('/wp-json/wp/v2/media',binary=raw,filename=filename)
                self.validate(receipt,filename)
                saved = api.wp.request('/wp-json/wp/v2/media/'+str(receipt['id'])+'?context=edit')
                self.validate(saved,filename)
                if saved['id'] != receipt['id']:
                    raise ValueError('Wrong media readback')
            except Exception:
                j['state'] = 'UNKNOWN'
                atomic_json(self.path(jid),j)
                raise RuntimeError('Upload uncertain; no automatic resend') from None
            j.update(state='VERIFIED',receipt={k:saved[k] for k in ('id','slug','mime_type','source_url')})
            atomic_json(self.path(jid),j)
            return j['receipt']

    @staticmethod
    def validate(receipt, filename):
        from urllib.parse import urlsplit, unquote
        if (not isinstance(receipt,dict) or type(receipt.get('id')) is not int or receipt['id'] <= 0
            or receipt.get('mime_type') != 'image/webp' or receipt.get('media_type') != 'image'
            or receipt.get('slug') != filename[:-5]
            or Path(unquote(urlsplit(receipt.get('source_url','')).path)).name != filename):
            raise ValueError('Exact media identity not confirmed')

    def reconcile(self,jid,event,signature,*,lookup):
        """lookup is a trusted read-only verifier of remote bytes, NOT chat evidence."""
        with self.products.lock():
            j=self.load(jid)
            owner=self.products.owner(event,signature,j['binding']['site'])
            if owner != j['binding']['owner'] or event['text'] != 'MEDIA RECONCILE '+jid:
                raise PermissionError('Exact owner reconciliation required')
            if j['state']=='VERIFIED': return j['receipt']
            if j['state'] not in ('SENDING','UNKNOWN'): raise ValueError('No uncertain upload')
            result=lookup(jid,j['binding']['request']['sha256'])
            self.validate(result,jid+'.webp')
            if result.get('verified_sha256') != j['binding']['request']['sha256']:
                raise ValueError('Exact remote content verification required')
            j.update(state='VERIFIED',receipt={k:result[k] for k in ('id','slug','mime_type','source_url')})
            atomic_json(self.path(jid),j)
            return j['receipt']
