"""Six original layout structures with replaceable local identity/assets/fonts.

No network, uploads, image generation or semantic PASS. Optional Playwright
renders locally. Output identity includes all inputs, renderer/CSS/font bytes.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from PIL import Image
from . import poster_reference, poster_catalog, poster_cobrand
from .image_intake import read_attachment, _trusted, _exclusive, _lock

ROOT=Path(__file__).resolve().parents[1]/'poster_templates'
FIELDS=['headline','subheadline','third','benefit','benefit_accent','strapline','cta','claim_right_en','claim_left_en','slogan','tagline','description','primary_services','secondary_services']

def normalized(content, number):
    if type(number) is not int or number not in range(1,7):raise ValueError('Template 1 through 6 required')
    cfg=copy.deepcopy(content)
    mode=cfg.setdefault('language','ENGLISH')
    if mode not in ('ENGLISH','ARABIC','BILINGUAL'):raise ValueError('Explicit supported language required')
    for key in FIELDS:
        cfg.setdefault(key,'');cfg.setdefault(poster_reference.PAIRS.get(key,key+'_ar'),'')
    for key in ('headline','subheadline','cta'):
        required=[key] if mode=='ENGLISH' else [poster_reference.PAIRS.get(key,key+'_ar')] if mode=='ARABIC' else [key,poster_reference.PAIRS.get(key,key+'_ar')]
        if any(not isinstance(cfg[k],str) or not cfg[k].strip() for k in required):raise ValueError('Required exact campaign/language copy missing')
    for key,value in cfg.items():
        if key!='services' and (not isinstance(value,str) or len(value)>4000):raise ValueError('Bounded plain copy required')
    if number<6:
        services=cfg.get('services')
        if not isinstance(services,list) or len(services)!=4:raise ValueError('Exactly four services required')
        for item in services:
            if not isinstance(item,dict) or set(item)-{'en','ar','icon'} or not isinstance(item.get('icon'),str):raise ValueError('Service label/icon schema required')
            item.setdefault('en','');item.setdefault('ar','')
            needed=['en'] if mode=='ENGLISH' else ['ar'] if mode=='ARABIC' else ['en','ar']
            if any(not isinstance(item[k],str) or not item[k].strip() or len(item[k])>120 for k in needed):raise ValueError('Exact service-language labels required')
    return cfg


def build(number,content,brand,fonts,atlas):
    cfg=normalized(content,number)
    if number==6:
        return poster_cobrand.make_html(cfg,brand,poster_cobrand.photo_uri(Path(atlas),'atlas'),ROOT/'template6.css',fonts)
    return poster_catalog.build_html(Path(atlas),ROOT,number,cfg,brand,fonts)


def render(number,content,brand,fonts,atlas,output_root,request_id,*,chromium=None):
    from playwright.sync_api import sync_playwright
    if not isinstance(request_id,str) or not request_id.isascii() or not request_id.replace('-','').replace('_','').isalnum() or len(request_id)>64:raise ValueError('Safe request identity required')
    root=_trusted(output_root,directory=True)
    cfg=normalized(content,number)
    files=[Path(atlas),Path(brand['backdrop']),Path(brand['qr']),Path(brand['primary']['logo']),Path(fonts['english']),Path(fonts['arabic'])]
    if number==6:files.append(Path(brand['secondary']['logo']))
    hashes={}
    for file in files:
        # Operator-selected local inputs, not paths from untrusted campaign text.
        path=file.absolute()
        if path != path.resolve(strict=True) or not path.is_file() or path.stat().st_mode & 0o022 or path.stat().st_size>20*1024*1024:
            raise ValueError('Trusted bounded local asset/font required')
        hashes[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    for p in list(ROOT.glob('*.css'))+[Path(__file__),Path(poster_reference.__file__),Path(poster_catalog.__file__),Path(poster_cobrand.__file__)]:hashes[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    binding={'template':number,'content':cfg,'brand':brand,'fonts':fonts,'hashes':hashes}
    identity=hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    folder=root/request_id
    with _lock(root,request_id):
        if folder.exists() or folder.is_symlink():
            _trusted(folder,directory=True)
            report=json.loads(read_attachment(folder/'render.json',[folder],max_bytes=100000))
            if set(report.get('outputs',{}))!={'poster.png','poster.jpg'}:raise ValueError('Invalid saved output proof')
            if report['input_sha256']!=identity:raise ValueError('Changed input requires a new revision identity')
            for name,digest in report['outputs'].items():
                if hashlib.sha256(read_attachment(folder/name,[folder])).hexdigest()!=digest:raise ValueError('Saved output changed')
            if not report['geometry_pass']:raise ValueError('Existing failed geometry requires reviewed revision')
            return report
        html=build(number,cfg,brand,fonts,atlas)
        with tempfile.TemporaryDirectory(prefix='.render-',dir=root) as tmp:
            stage=Path(tmp)/'complete';stage.mkdir(mode=0o700)
            blocked=[]
            with sync_playwright() as pw:
                options={'headless':True}
                if chromium:options['executable_path']=str(chromium)
                browser=pw.chromium.launch(**options)
                try:
                    context=browser.new_context(viewport={'width':1080,'height':1350},device_scale_factor=1,service_workers='block')
                    def deny(route):blocked.append(route.request.url.split(':',1)[0]);route.abort()
                    context.route('**/*',deny)
                    page=context.new_page();page.set_content(html,wait_until='load',timeout=30000)
                    page.evaluate('() => document.fonts.ready')
                    fit=page.evaluate('''n => {
                      const failed=[];
                      for (const e of document.querySelectorAll('[data-fit],.fit')) {
                        const min=Number(e.dataset.min||12);let size=parseFloat(getComputedStyle(e).fontSize);
                        const tooBig=()=>{const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();return e.scrollWidth>e.clientWidth+2 && e.clientWidth>0 || e.scrollHeight>e.clientHeight+2 && e.clientHeight>0 || e.clientWidth===0 && (r.width>p.width+2 || r.height>p.height+2);};
                        while(size>min && tooBig()){size-=0.5;e.style.fontSize=size+'px';}
                        const originalTolerance=n===6 && e.clientWidth>0 && e.scrollWidth<=e.clientWidth+7 && e.scrollHeight<=e.clientHeight+5;
                        if(tooBig()&&!originalTolerance)failed.push(e.className);
                      }
                      const box=document.querySelector('#poster').getBoundingClientRect();
                      return {failed,width:box.width,height:box.height,images:Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)};
                    }''',number)
                    page.locator('#poster').screenshot(path=str(stage/'poster.png'))
                    page.locator('#poster').screenshot(path=str(stage/'poster.jpg'),type='jpeg',quality=94)
                finally:browser.close()
            for file in files:
                if hashlib.sha256(file.absolute().read_bytes()).hexdigest()!=hashes[str(file.absolute())]:raise ValueError('Asset changed during render')
            for p in stage.iterdir():p.chmod(0o600)
            with Image.open(stage/'poster.png') as im:
                if im.size!=(1080,1350):raise ValueError('Wrong rendered dimensions')
            report={'template':number,'language':cfg['language'],'input_sha256':identity,'geometry_pass':not fit['failed'] and fit['images'] and fit['width']==1080 and fit['height']==1350 and not blocked,'geometry':fit,'external_requests_blocked':blocked,'semantic_review':'NOT TESTED','qr_decode':'NOT TESTED','published':False,'outputs':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}}
            _exclusive(stage/'render.json',json.dumps(report,sort_keys=True,indent=2).encode());os.rename(stage,folder)
        if not report['geometry_pass']:raise ValueError('Local geometry/assets gate failed; diagnostic output retained')
        return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--output-root',required=True);p.add_argument('--request-id',required=True);p.add_argument('--chromium')
    a=p.parse_args();value=json.loads(Path(a.config).read_text())
    print(json.dumps(render(value['template'],value['content'],value['brand'],value['fonts'],value['atlas'],a.output_root,a.request_id,chromium=a.chromium),indent=2))

if __name__=='__main__':main()
