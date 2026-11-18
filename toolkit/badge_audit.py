"""Read-only server-HTML badge audit; never cart/checkout mutations or JS execution."""
import argparse
import ipaddress
import json
import re
import socket
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

MAX_BYTES = 2 * 1024 * 1024

class Badges(HTMLParser):
    def __init__(self, attribute):
        super().__init__(convert_charrefs=True)
        self.attribute, self.stack, self.badges, self.generic = attribute, [], [], []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'span':
            self.stack.append({'id': attrs.get(self.attribute), 'sale': 'onsale' in attrs.get('class', '').split(), 'text': []})
    def handle_data(self, text):
        for item in self.stack:
            item['text'].append(text)
    def handle_endtag(self, tag):
        if tag == 'span' and self.stack:
            item = self.stack.pop(); text = ' '.join(''.join(item['text']).split())
            if item['id'] is not None: self.badges.append((item['id'], text))
            if item['sale']: self.generic.append(text)

def audit_html(html, product_id, expected, *, attribute='data-smgc-product', generic_labels=('Sale!',)):
    if not re.fullmatch(r'data-[a-z0-9-]+', attribute): raise ValueError('Data attribute required')
    if not isinstance(html, str) or len(html.encode()) > MAX_BYTES: raise ValueError('HTML exceeds bound')
    expected = {str(k): ' '.join(v.split()) for k,v in expected.items()}
    product_id = str(product_id)
    if product_id not in expected: raise ValueError('Expected own badge required')
    parser = Badges(attribute); parser.feed(html); parser.close()
    own = [text for key,text in parser.badges if key == product_id]
    generic = any(text in generic_labels for text in parser.generic)
    return {'id': product_id, 'own_badges': own, 'all_badges': parser.badges,
            'generic_sale': generic, 'pass': own == [expected[product_id]] and not generic
            and all(expected.get(key) == text for key,text in parser.badges),
            'scope': 'SERVER_HTML_ONLY', 'visual_visibility': 'NOT_TESTED'}

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('Redirect refused')

def fetch_html(url, allowed_hosts):
    """Explicit operator allowlist, public HTTPS, no redirects/credentials/proxy.
    DNS validation is defense-in-depth, not protection against DNS rebinding;
    use an egress firewall for hostile targets. Never take URLs from chat alone.
    """
    from urllib.request import ProxyHandler
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.hostname not in allowed_hosts or p.username or p.password or p.fragment or p.port not in (None,443):
        raise ValueError('Allowlisted public HTTPS URL required')
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Non-public destination refused')
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(Request(url, headers={'User-Agent':'AutomationToolkit-BadgeAudit/1.0','Accept':'text/html'}),timeout=20) as response:
        if response.status != 200 or response.headers.get_content_type() != 'text/html':
            raise ValueError('Successful HTML response required')
        raw = response.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('HTML exceeds bound')
        return raw.decode(response.headers.get_content_charset() or 'utf-8', errors='strict')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--fixture'); source.add_argument('--url')
    p.add_argument('--allow-host', action='append',default=[]);p.add_argument('--expected',required=True)
    p.add_argument('--product-id',required=True);p.add_argument('--attribute',default='data-smgc-product')
    a=p.parse_args()
    if a.fixture:
        with Path(a.fixture).open('rb') as handle: raw=handle.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES: raise ValueError('HTML exceeds bound')
        html=raw.decode('utf-8')
    else: html=fetch_html(a.url,a.allow_host)
    result=audit_html(html,a.product_id,json.loads(Path(a.expected).read_text()),attribute=a.attribute)
    print(json.dumps(result,indent=2));return 0 if result['pass'] else 1

if __name__=='__main__': raise SystemExit(main())
