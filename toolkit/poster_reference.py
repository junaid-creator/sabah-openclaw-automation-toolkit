"""Owner-authorized original reference structure; data-only brand adaptation."""
import base64,html,mimetypes,random
from pathlib import Path
from PIL import Image
PAIRS={'headline':'headline_ar','subheadline':'subheadline_ar','third':'third_ar','benefit':'benefit_ar','benefit_accent':'benefit_accent_ar','strapline':'strapline_ar','cta':'cta_ar','claim_right_en':'claim_right','claim_left_en':'claim_left','slogan':'slogan_ar'}

def localized(en,ar,language):
 if language=='ENGLISH':return esc(en)
 if language=='ARABIC':return esc(ar)
 return '<span class="copy-en" lang="en" dir="ltr">'+esc(en)+'</span><span class="copy-ar" lang="ar" dir="rtl">'+esc(ar)+'</span>'

def campaign_text(cfg,key):
 return localized(cfg.get(key,''),cfg.get(PAIRS.get(key,key+'_ar'),''),cfg['language'])

def campaign_band(cfg,key,color,ident,cls,minimum=22):
 text=campaign_text(cfg,key)
 if cfg['language']=='ENGLISH' and key=='subheadline' and cfg.get('accent'):text=text.replace(esc(cfg['accent']),'<span class="accent">'+esc(cfg['accent'])+'</span>',1)
 return '<div class="brush '+cls+'">'+brush(color,ident)+fit(text,extra='campaign-copy',minimum=minimum)+'</div>'

def photo_mask():
 # Small, deterministic variations in the alpha boundary; photo pixels stay sharp.
 # Blur applies only to alpha at the edge, never to the equipment photograph.
 import math
 def boundary(base,amplitude,reverse=False):
  points=[(x,base+amplitude*(.5*math.sin(x/73)+.3*math.sin(x/29+1)+.2*math.sin(x/11))) for x in range(0,1081,12)]
  return list(reversed(points)) if reverse else points
 top=boundary(32,28);bottom=boundary(978,12,True)
 d='M'+' L'.join(f'{x},{y:.2f}' for x,y in top+bottom)+'Z'
 svg='<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1000" viewBox="0 0 1080 1000" preserveAspectRatio="none"><defs><filter id="soft" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".035 .09" numOctaves="2" seed="7" result="texture"/><feDisplacementMap in="SourceGraphic" in2="texture" scale="12" xChannelSelector="R" yChannelSelector="G"/><feGaussianBlur stdDeviation="1.4 14"/></filter></defs><path d="'+d+'" fill="white" filter="url(#soft)"/></svg>'
 return 'data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode()

def uri(path):
 p=Path(path);mime=mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
 return 'data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()

def esc(value):return html.escape(str(value),quote=True)

def icon(name):
    paths = {
        'power': '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M5 7V4h10v3M5 11h3M5 15h3m7-5-4 6h4l-2 4M4 23h3M17 23h3"/>',
        'panel': '<rect x="4" y="2" width="16" height="20" rx="2"/><circle cx="9" cy="7" r="1.5"/><circle cx="15" cy="7" r="1.5"/><path d="M7 12h10M8 16v3M12 16v3M16 16v3"/>',
        'cable': '<path d="M5 2v4M10 2v4M3 6h9v4l-3 3v3c0 7 12 7 12 0v-3M18 9v4h5M5 19h4"/>',
        'breaker': '<path d="M4 4h16M7 4v4M17 4v4M9 7h6v10H9zM11 17v5M13 17v5M8 10H5V7M16 10h3V7"/>',
        'equipment': '<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M3 12h18M10 10v5h4v-5"/>',
        'phone': '<path d="M7 3 4 5c-3 6 9 18 15 15l2-3-5-3-2 2c-3-1-5-3-6-6l2-2z"/>',
        'web': '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18M5 7h14M5 17h14"/>',
        'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 6 9 7 9-7"/>',
        'pin': '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2"/>',
        'weld': '<path d="M6 3h12v12l-6 6-6-6Z"/><path d="M8 7h8v5H8zM2 16l3-1M3 20l3-3M21 16l-3-1"/>',
        'cut': '<path d="M6 3h10v6H6zM11 9v11M7 20h10M18 3v17"/><path d="M7 11h8v7H7z"/>',
        'grind': '<circle cx="10" cy="15" r="6"/><circle cx="10" cy="15" r="2"/><path d="m13 10 5-6 3 3-5 6M3 21h17"/>',
        'clean': '<path d="M8 4h8v4H8zM6 8h12v12H6zM9 20v2M15 20v2M18 10c6 0 1 8 4 9M3 21h4"/>',
        'instagram': '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r=".6"/>',
        'youtube': '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="m10 9 6 3-6 3z"/>',
        'whatsapp': '<path d="M4 18a9 9 0 1 1 4 3l-5 1z"/><path d="m8 7-1 2c1 4 3 6 7 7l2-2-3-2-1 1-3-3 1-1z"/>',
        'facebook': '<path d="M15 22V13h3l1-4h-4V7c0-1 1-2 2-2h2V1h-3c-4 0-6 2-6 6v2H7v4h3v9z" fill="currentColor" stroke="none"/>',
        'tiktok': '<path d="M14 2v13a5 5 0 1 1-4-5v4a2 2 0 1 0 1 2V2h3c0 4 3 6 7 6v4c-3 0-5-1-7-3"/>',
    }
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths[name] + '</svg>'

def symbol(name):
 if name=='mobile':
  return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><rect x="6" y="2" width="12" height="20" rx="2"/><path d="M10 5h4M11 19h2"/></svg>'
 if name=='partner':
  return '<svg viewBox="0 0 40 40" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linejoin="round"><path d="m3 18 6-9 11 5 11-5 6 10-8 14-9-4-8 4z"/><path d="m10 15 8 6 7-5 8 6M11 24l8 7M15 21l10 9M21 20l9 7M16 16l-4 5"/></svg>'
 try:return icon(name)
 except KeyError:return icon('grind')

def brush(color,key):
 colors={'green':('#1f8a32','#005512'),'navy':('#095b92','#032c53'),'pink':('#f60081','#cb0059'),'blue':('#087fc2','#00538f')}
 c1,c2=colors.get(color,(color,color));rng=random.Random('smgc-reference-'+str(key))
 top=[(20,17),(59,11),(100,15),(155,8),(225,11),(330,5),(425,8),(510,4),(620,8),(728,3),(830,7),(913,2),(965,10),(984,7),(975,21)]
 bot=[(983,78),(970,89),(908,88),(832,95),(745,91),(649,97),(545,93),(443,98),(340,93),(231,99),(151,94),(79,99),(25,91),(9,88),(17,73),(7,65),(13,47),(5,34),(19,28)]
 d='M'+' L'.join(f'{x},{y}' for x,y in top+bot)+'Z'
 cuts=[]
 for i in range(95):
  x=rng.randint(0,998);y=rng.choice([rng.uniform(0,15),rng.uniform(86,100)]);length=rng.uniform(4,65);thick=rng.uniform(.5,2.8)
  cuts.append(f'<path d="M{x:.1f},{y:.1f}l{length:.1f},-1.2" stroke="black" stroke-width="{thick:.1f}"/>')
 for i in range(16):
  x=rng.randint(12,975);y=rng.randint(13,89)
  cuts.append(f'<path d="M{x},{y}l{rng.randint(2,13)},-1" stroke="black" stroke-width=".6" opacity=".45"/>')
 return f'<svg class="stroke" viewBox="0 0 1000 100" preserveAspectRatio="none" aria-hidden="true"><defs><linearGradient id="g{key}" x1="0" y1="0" x2="0" y2="1"><stop stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/></linearGradient><mask id="m{key}"><path d="{d}" fill="white"/>{"".join(cuts)}</mask></defs><rect width="1000" height="100" fill="url(#g{key})" mask="url(#m{key})"/></svg>'

def fit(text,lang=None,extra='',minimum=22):
 return f'<span class="ink {extra}" data-fit data-min="{minimum}"'+(' lang="ar" dir="rtl"' if lang=='ar' else '')+'>'+text+'</span>'

def band(text,color,key,cls,lang=None,accent=None,minimum=24):
 content=esc(text)
 if accent:content=content.replace(esc(accent),'<span class="accent">'+esc(accent)+'</span>',1)
 if lang=='ar' and '4' in content:content=content.replace('4','<span class="accent yellow">4</span>',1)
 return f'<div class="brush {cls}">'+brush(color,key)+fit(content,lang,minimum=minimum)+'</div>'

def atlas_image(source_uri,size,index=None,mode='slice',extra='',foreground=False):
 w,h=size;box=(f'0 {h*.66:g} {w} {h*.34:g}' if foreground else f'0 {h/2:g} {w} {h/2:g}') if index is None else f'{index*w/4:g} 0 {w/4:g} {h/2:g}'
 return f'<svg class="photo-svg {extra}" viewBox="{box}" preserveAspectRatio="xMidYMid {mode}"><image width="{w}" height="{h}" href="{source_uri}"/></svg>'

def build_html(source,assets,style,cfg,brand,fonts):
 if style!='equipment':raise ValueError('Use the public six-template controller; legacy style aliases are not exposed')
 with Image.open(source) as im:size=im.size
 source_uri=uri(source);language=cfg['language'];css=(assets/'reference.css').read_text()
 for prefix,key in [('R','english'),('C','arabic')]:
  for weight in [600,700,900]:
   css=css.replace(f'__FONT_{prefix}{weight}__',uri(fonts[key]))
 css=css.replace('__PHOTO_MASK__',photo_mask())
 palette=['pink','blue','green','pink'] if style!='stages-ar' else ['blue','blue','pink','green']
 hexes={'pink':'#eb0073','blue':'#0067a9','navy':'#063760','green':'#087a25'}
 pales={'pink':'#ffe1ed','blue':'#d8f3ff','green':'#e2ffd4','navy':'#deecfa'}
 cards=[]
 for i,s in enumerate(cfg['services']):
  col=palette[i];attrs=f'style="--accent:{hexes[col]};--pale:{pales[col]}"';round_icon='<div class="round">'+symbol(s['icon'])+'</div>'
  photo='<div class="action-photo">'+atlas_image(source_uri,size,i)+'</div>'
  if style=='equipment':
   inner=round_icon+'<div class="machine-label campaign-copy" data-fit data-min="16">'+localized(s['en'],s['ar'],language)+'</div>'
  elif style=='job-changes':
   inner=round_icon+'<div class="mini-label campaign-copy" data-fit data-min="16">'+localized(s['short'],s['ar'],language)+'</div>'+photo
  elif style=='challenges-ar':
   question_en=['Need welding?','Need core cutting?','Need grinding?','Need cleaning?'][i]
   question_text=localized(question_en,'هل تحتاج إلى '+s['question'],language)
   if language=='ARABIC':question_text='هل تحتاج إلى<br><strong>'+esc(s['question'])+'</strong>'
   question='<div class="challenge-question campaign-copy" data-fit data-min="17">'+question_text+'</div>'
   label='<div class="challenge-label">'+brush(col,'card'+str(i))+'<span class="campaign-copy" data-fit data-min="17">'+localized(s['short'],s['ar'],language)+'</span></div>'
   inner=round_icon+question+label+'<div class="challenge-en"></div>'+photo
  else:
   ar=['لحام','قطع','تجليخ','تنظيف'][i] if s['ar']==DEFAULT_SERVICES[i]['ar'] else s['ar']
   inner=photo+round_icon+'<div class="flow-label">'+brush(col,'flow'+str(i))+'<span class="campaign-copy" data-fit data-min="16">'+localized(s['short'],ar,language)+'</span></div>'
  cards.append(f'<article class="service" {attrs}>{inner}</article>')
 if style in ['equipment','job-changes','challenges-ar']:
  color='navy' if style=='challenges-ar' else 'green'
  headlines=campaign_band(cfg,'headline',color,'main','main-brush')+campaign_band(cfg,'subheadline','green' if style=='challenges-ar' else 'navy','sub','sub-brush')
  if style=='job-changes':headlines+=campaign_band(cfg,'third','pink','third','third-brush')
 else:
  headlines='<div class="flow-headline"><span class="campaign-copy" data-fit data-min="22">'+campaign_text(cfg,'headline')+'</span><span class="pink-line campaign-copy" data-fit data-min="22">'+campaign_text(cfg,'subheadline')+'</span></div><div class="flow-underline"></div>'
 hero_ratio=size[0]/(size[1]*(.34 if style=='challenges-ar' else .5))
 hero='<div class="hero" style="--hero-ratio:'+str(hero_ratio)+'"><div class="hero-main">'+atlas_image(source_uri,size,mode='slice' if style=='equipment' else 'meet',foreground=style=='challenges-ar')+'</div></div>'
 extras=''
 if style=='equipment':
  combined=localized(cfg['benefit']+' '+cfg['benefit_accent'],cfg['benefit_ar']+' '+cfg['benefit_accent_ar'],language)
  if language=='ENGLISH':combined=esc(cfg['benefit'])+' <span class="accent">'+esc(cfg['benefit_accent'])+'</span>'
  extras='<div class="benefit"><span class="partner">'+symbol('partner')+'</span><span class="benefit-text campaign-copy" data-fit data-min="17">'+combined+'</span></div>'
 elif style=='job-changes':
  extras='<div class="stage-strap campaign-copy" data-fit data-min="20">'+campaign_text(cfg,'strapline')+'</div>'
 elif style=='challenges-ar':
  extras='<div class="arabic-cta-brush">'+brush('pink','arcta')+fit(campaign_text(cfg,'cta'),extra='campaign-copy',minimum=20)+'</div>'
 else:
  extras='<div class="flow-claims"><span class="pink campaign-copy" data-fit data-min="19">'+campaign_text(cfg,'claim_right_en')+'</span><i class="claim-separator"></i><span class="campaign-copy" data-fit data-min="19">'+campaign_text(cfg,'claim_left_en')+'</span></div><div class="flow-green-brush">'+brush('green','slogan')+fit(campaign_text(cfg,'slogan'),extra='campaign-copy',minimum=20)+'</div>'
 socials=''.join('<span class="social '+n+'">'+symbol(n)+'</span>' for n in ['facebook','instagram','youtube','tiktok','whatsapp'])
 phones=''.join('<div class="phone"><i class="phone-icon">'+symbol('phone' if i==0 else 'mobile')+'</i><span>'+esc(n)+'</span></div>' for i,n in enumerate(brand['primary']['phones']))
 edge='<svg viewBox="0 0 140 200" aria-hidden="true"><path d="M0 0 140 100 0 200" fill="#b1e5a0"/><path d="M0 28 110 100 0 172" fill="#176d40"/><path d="m0 58 66 42-66 43" fill="#074f7e"/><path d="m0 50 76 50-76 51" fill="none" stroke="white" stroke-width="7"/></svg>'
 footer_items=[('web',esc(brand['primary']['website'])),('mail',esc(brand['primary']['email'])),('pin',esc(brand['primary']['location']).replace('\n','<br>'))]
 footer=''.join('<div class="footer-item'+(' address' if i==2 else '')+'"><i class="footer-icon">'+symbol(n)+'</i><span class="footer-text">'+text+'</span></div>' for i,(n,text) in enumerate(footer_items))
 return '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Reusable Reference Template</title><style>'+css+'</style></head><body><main id="poster" class="style-'+style+' language-'+language.lower()+'">'+\
 '<img class="backdrop" alt="Synthetic or operator supplied background" src="'+uri(brand['backdrop'])+'"><div class="sky-wash"></div><div class="edge">'+edge+'</div>'+\
 '<header class="header"><img class="logo" alt="Configured primary logo" src="'+uri(brand['primary']['logo'])+'"><div class="brand"><div class="smgc">'+esc(brand['primary']['short_name'])+'</div><div class="brand-name">'+esc(brand['primary']['display_name'])+'</div><div class="brand-trade">'+esc(brand['primary']['descriptor'])+'</div><div class="brand-tag">'+esc(brand['primary']['tagline'])+'</div></div><div class="arabic-brand" lang="ar" dir="rtl"><div class="ar-name">'+esc(brand['primary']['display_name_ar'])+'</div><div class="ar-trade">'+esc(brand['primary']['descriptor_ar'])+'</div><div class="ar-tag">'+esc(brand['primary']['tagline_ar'])+'</div></div></header>'+\
 headlines+'<section class="service-row">'+''.join(cards)+'</section>'+hero+extras+\
 '<div class="contact-wash"></div><div class="qr-wrap"><div class="qr-inner"><img class="qr" alt="Configured QR asset" src="'+uri(brand['qr'])+'"></div></div><div class="follow"><div class="follow-title campaign-copy">'+localized('FOLLOW US','تابعونا',language)+'</div><div class="socials">'+socials+'</div><div class="handle">'+esc(brand['primary']['social'])+'</div></div><div class="contact-divider"></div><section class="contact"><div class="cta"><i class="call">'+symbol('phone')+'</i><span class="campaign-copy" data-fit data-min="18">'+campaign_text(cfg,'cta')+'</span></div><div class="phones">'+phones+'</div></section><footer class="footer">'+footer+'</footer></main></body></html>'

