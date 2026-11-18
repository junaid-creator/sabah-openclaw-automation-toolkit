"""Actual browser checks; outputs outside checkout, no network or account."""
from pathlib import Path
import argparse,json,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from toolkit.browser_verification import verify_fixture
p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args()
a=Path(args.output).absolute();a.mkdir(mode=0o700,parents=True,exist_ok=False)
f=a/'product.html'
f.write_text('<!doctype html><meta name="viewport" content="width=device-width"><style>.badge{display:block;color:white;background:black} @media(max-width:500px){.price{font-size:20px}}</style><h1>Example tool</h1><span class="badge">Save 20%</span><span class="price">80.00</span><a href="/cart/">Cart</a>')
f.chmod(0o600)
checks=[{'selector':'.badge','text':'Save 20%','count':1},{'selector':'.price','text':'80.00','count':1}]
r=verify_fixture(f,checks,a/'good');assert r['passed']
f.write_text(f.read_text()+'<style>.badge{display:none}</style>')
n=verify_fixture(f,checks,a/'negative');assert not n['passed']
(a/'acceptance.json').write_text(json.dumps({'desktop_mobile_positive':r,'hidden_badge_negative':n},indent=2))
print('Two viewport positive cases and two hidden-badge negative cases passed; network denied')
