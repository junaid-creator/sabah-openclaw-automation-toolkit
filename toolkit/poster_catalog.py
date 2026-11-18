"""Original catalog 2–5 geometry; reusable configurable identity."""
import base64,io,re
from PIL import Image
from . import poster_reference as locked
def build_html(source,assets,n,cfg,brand,fonts,layout_variant=None):
 if n==1:return locked.build_html(source,assets,'equipment',cfg,brand,fonts)
 if layout_variant and (n,layout_variant)!=(3,'recruitment-clean'):
  raise ValueError('Layout variant requires Template 3')
 base=locked.build_html(source,assets,'equipment',cfg,brand,fonts)
 # Reuse the approved corporate header and complete footer verbatim. Only the
 # main campaign area and photograph treatment belong to these new templates.
 head_end=base.index('</header>')+len('</header>');foot=base.index('<div class="contact-wash">')
 prefix=base[:head_end];suffix=base[foot:]
 prefix=re.sub(r'<img class="backdrop".*?<header class="header">','<header class="header">',prefix,count=1,flags=re.S)
 prefix=prefix.replace('class="style-equipment language-','class="style-equipment catalog catalog-'+str(n)+(' recruitment-clean' if layout_variant else '')+' language-')
 css=(assets/'catalog.css').read_text().replace('__CATALOG_MASK__',locked.photo_mask())
 prefix=prefix.replace('</style>',css+'</style>',1)
 with Image.open(source) as im:size=im.size
 data=locked.uri(source);loc=lambda en,ar:locked.localized(en,ar,cfg['language'])
 title='<div class="brush main-brush catalog-title">'+locked.brush('navy' if n in (3,5) else 'green','catalog-title')+locked.fit(locked.campaign_text(cfg,'headline'),extra='campaign-copy',minimum=25)+'</div>'
 sub='<div class="catalog-sub campaign-copy" data-fit data-min="21">'+locked.campaign_text(cfg,'subheadline')+'</div>'
 scene='<div class="catalog-scene">'+locked.atlas_image(data,size,mode='meet' if n in (3,5) else 'slice')+'</div>'
 if n==4:
  # Contain the complete panorama. A hero template must not cut off a machine
  # merely because a wide atlas has a different ratio from the display frame.
  with Image.open(source) as im:
   photo=im.crop((0,im.height//2,im.width,im.height));memory=io.BytesIO();photo.save(memory,format='PNG')
  scene='<div class="catalog-scene"><img class="complete-hero-photo" alt="Campaign equipment photograph" src="data:image/png;base64,'+base64.b64encode(memory.getvalue()).decode()+'"></div>' 
 tiles=[];colors=['#ed0076','#0067a9','#087a25','#ed0076'];tints=['#ffe5ef','#ddf5ff','#e9ffdf','#ffe5ef']
 for i,s in enumerate(cfg['services']):
  x=58+i*246 if n==2 else 43+i*253 if n==3 else 45+i*251 if n==4 else 61+i*245
  photo='' if n==4 else '<div class="tile-photo">'+locked.atlas_image(data,size,i)+'</div>'
  tiles.append('<article class="catalog-tile" style="left:'+str(x)+'px;--card:'+colors[i]+';--tint:'+tints[i]+'">'+photo+'<div class="round">'+locked.symbol(s['icon'])+'</div><div class="tile-copy campaign-copy" data-fit data-min="16">'+loc(s['en'],s['ar'])+'</div></article>')
 note='<div class="catalog-note campaign-copy" data-fit data-min="20">'+loc('Equipment for Your Next Project','معدات لمشروعك القادم')+'</div>'
 extras=''
 if n==5:
  extras=''.join('<div class="connector" style="left:'+str(285+i*245)+'px">→</div>' for i in range(3))
  extras+='<div class="catalog-values"><span class="campaign-copy" data-fit data-min="18">'+loc('Four Practical Solutions','أربعة حلول عملية')+'</span><span class="campaign-copy" data-fit data-min="18">'+loc('One Equipment Partner','شريك واحد للمعدات')+'</span></div>'
  note='<div class="catalog-note">'+locked.brush('green','catalog-note')+'<span class="campaign-copy" data-fit data-min="20">'+loc('Ready for Your Next Project','جاهزون لمشروعك القادم')+'</span></div>'
 return prefix+'<section class="catalog-main">'+title+sub+scene+''.join(tiles)+extras+note+'</section>'+suffix

