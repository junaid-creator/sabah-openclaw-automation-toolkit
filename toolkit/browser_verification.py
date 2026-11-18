"""Read-only local HTML browser acceptance; all browser network is denied.

Not a live WooCommerce/cart or authenticated website administration adapter.
"""
import hashlib,json
from pathlib import Path
from .product_workflow import Products


def verify_fixture(html_path, checks, output, *, chromium=None):
    from playwright.sync_api import sync_playwright
    source=Path(html_path);Products._private(source)
    if source.stat().st_size>2_000_000:raise ValueError('Fixture too large')
    raw=source.read_text()
    if not isinstance(checks,list) or not checks or len(checks)>50:raise ValueError('Bounded checks required')
    for c in checks:
        if set(c)!={'selector','text','count'} or not isinstance(c['selector'],str) or not c['selector'] or not isinstance(c['text'],str) or type(c['count']) is not int or not 1<=c['count']<=20:
            raise ValueError('Exact CSS/text/count checks required')
    root=Path(output);root.mkdir(mode=0o700,parents=True,exist_ok=False)
    Products._private(root,directory=True)
    result={'source_sha256':hashlib.sha256(raw.encode()).hexdigest(),'cases':[],'network':'DENIED'}
    with sync_playwright() as p:
        options={'headless':True}
        if chromium:options['executable_path']=chromium
        browser=p.chromium.launch(**options)
        try:
            for width,height in [(1440,1000),(390,844)]:
                context=browser.new_context(viewport={'width':width,'height':height},service_workers='block',java_script_enabled=False)
                context.route('**/*',lambda route:route.abort())
                page=context.new_page();page.set_content(raw,wait_until='domcontentloaded',timeout=10000)
                rows=[]
                for check in checks:
                    loc=page.locator(check['selector']);count=loc.count()
                    texts=loc.all_text_contents() if count<=20 else []
                    visible=count==check['count'] and all(loc.nth(i).is_visible() for i in range(count))
                    exact=len(texts)==check['count'] and all(' '.join(t.split())==check['text'] for t in texts)
                    rows.append({'selector':check['selector'],'count':count,'visible':visible,'exact_text':exact,'passed':visible and exact})
                shot=root/(str(width)+'.png');page.screenshot(path=str(shot),full_page=True);shot.chmod(0o600)
                result['cases'].append({'viewport':[width,height],'checks':rows,'screenshot_sha256':hashlib.sha256(shot.read_bytes()).hexdigest()})
                context.close()
        finally:browser.close()
    result['passed']=all(c['passed'] for case in result['cases'] for c in case['checks'])
    path=root/'result.json';path.write_text(json.dumps(result,indent=2));path.chmod(0o600)
    return result


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--html',required=True);p.add_argument('--checks',required=True);p.add_argument('--output',required=True);p.add_argument('--chromium');a=p.parse_args()
    result=verify_fixture(a.html,json.loads(Path(a.checks).read_text()),a.output,chromium=a.chromium)
    print(json.dumps(result));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
