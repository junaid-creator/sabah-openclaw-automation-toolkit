from pathlib import Path
import json,sys,hashlib,importlib.metadata
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from toolkit.poster_render import render
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--font',required=True);parser.add_argument('--arabic-font');parser.add_argument('--chromium');args=parser.parse_args()
E=Path(args.output).absolute()
if E.is_relative_to(R):raise ValueError('Keep synthetic render outputs outside the source checkout')
E.mkdir(mode=0o700,parents=True,exist_ok=True);out=E/'renders';out.mkdir(mode=0o700,exist_ok=True)
atlas=E/'synthetic-atlas.png';im=Image.new('RGB',(1600,1600),'#c3dce4');d=ImageDraw.Draw(im)
for i,color in enumerate(['#cd7f62','#729ab2','#86a98b','#b49abb']):
 d.rectangle((i*400,0,(i+1)*400-1,799),fill=color);d.rectangle((i*400+70,220,i*400+320,500),fill='#f2f2ed');d.text((i*400+120,560),'SYNTHETIC PANEL '+str(i+1),fill='black')
d.rectangle((0,800,1599,1599),fill='#d9e3d8');d.rectangle((250,1020,1350,1380),fill='#386980');d.text((650,1450),'SYNTHETIC HERO',fill='black');im.save(atlas);atlas.chmod(0o600)
from poster_fixture_helpers import private_demo_assets
a=private_demo_assets(R/'poster_templates/assets',E)
primary={'short_name':'EXAMPLE','display_name':'EXAMPLE COMPANY','descriptor':'EQUIPMENT SERVICES','tagline':'READY FOR YOUR PROJECT','display_name_ar':'شركة مثال','descriptor_ar':'خدمات المعدات','tagline_ar':'جاهزون لمشروعك','phones':['000 000 0000'],'website':'example.com','email':'hello@example.com','location':'Example City','social':'@example','logo':str(a/'primary-logo.svg')}
secondary=dict(primary,short_name='DEMO TWO',display_name='EXAMPLE TWO',descriptor='SURVEY SERVICES',logo=str(a/'secondary-logo.svg'))
brand={'primary':primary,'secondary':secondary,'qr':str(a/'qr-placeholder.svg'),'backdrop':str(a/'backdrop.svg'),'qr_label':'DEMO — NOT A QR'}
font=args.font;fonts={'english':font,'arabic':args.arabic_font or font}
content={'headline':'READY FOR WORK','headline_ar':'جاهزون للعمل','subheadline':'Equipment Solutions','subheadline_ar':'حلول المعدات','cta':'CONTACT US','cta_ar':'اتصل بنا','benefit':'Reliable Tools','benefit_ar':'معدات عملية','benefit_accent':'For Your Project','benefit_accent_ar':'لمشروعك','tagline':'Plan Your Project','tagline_ar':'خطط لمشروعك','description':'Illustrative equipment layout','description_ar':'تصميم توضيحي للمعدات','primary_services':'Equipment Services','primary_services_ar':'خدمات المعدات','secondary_services':'Survey Services','secondary_services_ar':'خدمات المساحة','services':[{'en':'Tool '+str(i+1),'ar':'معدات '+str(i+1),'icon':'equipment'} for i in range(4)]}
results=[]
for mode in ['ENGLISH','ARABIC','BILINGUAL']:
 for n in range(1,7):
  c=dict(content,language=mode);request='t'+str(n)+'-'+mode.lower()
  try:
   report=render(n,c,brand,fonts,atlas,out,request,chromium=args.chromium)
   results.append({'template':n,'language':mode,'geometry_pass':report['geometry_pass'],'outputs':report['outputs']})
  except Exception as ex:results.append({'template':n,'language':mode,'error':type(ex).__name__+': '+str(ex)})
  (E/'render-results.json').write_text(json.dumps(results,indent=2))
  print(json.dumps(results[-1]),flush=True)
(E/'runtime.json').write_text(json.dumps({p:importlib.metadata.version(p) for p in ['playwright','pyee','greenlet']},indent=2))
example={'template':1,'content':dict(content,language='ENGLISH'),'brand':brand,'fonts':fonts,'atlas':str(atlas)}
(E/'example-private.json').write_text(json.dumps(example,indent=2))
print('PASS',sum(x.get('geometry_pass') is True for x in results),'OF',len(results))

raise SystemExit(0 if len(results)==18 and all(x.get('geometry_pass') for x in results) else 1)
