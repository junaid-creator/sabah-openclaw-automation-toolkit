"""Explicit opt-in WordPress REST client; writes disabled by default."""
import base64,json,re,urllib.request,urllib.error
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

class WP:
    def __init__(self, base_url, username, password, *, allow_network=False, allow_write=False, opener=None):
        from urllib.parse import urlsplit
        u=urlsplit(base_url)
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
            raise ValueError('Explicit trusted HTTPS origin required')
        if not username or not password: raise ValueError('Credentials required')
        self.base=base_url.rstrip('/')
        self.auth='Basic '+base64.b64encode((username+':'+password).encode()).decode()
        self.allow_network,self.allow_write=allow_network,allow_write
        self.opener=opener or urllib.request.build_opener(_NoRedirect())

    def request(self, path, data=None, binary=None, filename=None):
        if not self.allow_network: raise RuntimeError('WordPress network disabled')
        if not path.startswith('/wp-json/') or any(x in path for x in (chr(10),chr(13),'#')): raise ValueError('REST path required')
        if (data is not None or binary is not None) and not self.allow_write: raise RuntimeError('WordPress writes disabled')
        if binary is not None and (not filename or not re.fullmatch(r'[A-Za-z0-9_.-]+[.]webp',filename)): raise ValueError('Safe WebP filename required')
        headers = {'Authorization': self.auth, 'Cache-Control': 'no-cache', 'User-Agent': 'AutomationToolkit/0.2'}
        body = None
        if binary is not None:
            body = binary
            headers.update({'Content-Type': 'image/webp',
                            'Content-Disposition': 'attachment; filename="' + filename + '"'})
        elif data is not None:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.base + path, data=body, headers=headers,
                                     method='GET' if body is None else 'POST')
        try:
            with self.opener.open(req, timeout=45) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000: raise ValueError("Response too large")
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            raise RuntimeError('WordPress HTTP ' + str(error.code)) from None
        except (OSError, ValueError):
            raise RuntimeError('WordPress request uncertain or unreadable') from None

    def posts(self):
        rows = []
        for page in range(1, 101):
            batch = self.request('/wp-json/wp/v2/posts?context=edit&status=publish,draft,'
                                 'pending,future,private,trash&per_page=100&page=' + str(page))
            rows.extend(batch)
            if len(batch) < 100:
                return rows
        raise RuntimeError('Inventory pagination exceeds safety bound')
