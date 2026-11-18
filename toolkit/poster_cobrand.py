"""Original one-hero dual-company layout with separate identities."""
import base64,html,io
from pathlib import Path
from PIL import Image,ImageOps
from .poster_reference import uri as data_uri
def esc(s: object) -> str:
    return html.escape(str(s), quote=True)

def safe_photo(source: Path, mode: str) -> bytes:
    """Never mutate caller's source; extract the one hero if atlas is specified."""
    with Image.open(source) as src:
        im = ImageOps.exif_transpose(src).convert('RGB')
        if mode == 'atlas':
            # Existing Poster atlas convention: four top panels, one bottom hero.
            im = im.crop((0, im.height // 2, im.width, im.height))
        b = io.BytesIO()
        # Resize for deterministic rendering and reasonable standalone HTML size.
        im.thumbnail((1600, 1200), Image.Resampling.LANCZOS)
        im.save(b, 'JPEG', quality=94, subsampling=0)
        return b.getvalue()

def photo_uri(source: Path, mode: str) -> str:
    return 'data:image/jpeg;base64,' + base64.b64encode(safe_photo(source,mode)).decode('ascii')

def icon_svg(kind: str) -> str:
    if kind == 'worker':
        d = '<path d="M8 18v-2l3-1 1-3h8l1 3 3 1v2M13 8V5a5 5 0 0 1 10 0v3M11 9h14M10 23c0-3 4-5 8-5s8 2 8 5"/>'
    else:
        d = '<path d="M18 18V6m-7 17h14M8 24h20M11 9h14l2 5H9zM9 6l18-2M18 6l-4 3M18 6l4 3"/>'
    return '<svg viewBox="0 0 36 36" aria-hidden="true">' + d + '</svg>'

def contact_line(symbol: str, text: str) -> str:
    return '<div class="contact-line"><span class="contact-icon">'+esc(symbol)+'</span><span class="fit" data-min="13">'+esc(text)+'</span></div>'

def render_copy(cfg,key):
    if cfg['language']=='ENGLISH':return esc(cfg.get(key,''))
    if cfg['language']=='ARABIC':return esc(cfg.get(key+'_ar',''))
    return ('<span class="bilingual-lines"><span class="bilingual-en" lang="en" dir="ltr">'
            +esc(cfg.get(key,''))+'</span><span class="bilingual-ar" lang="ar" dir="rtl">'
            +esc(cfg.get(key+'_ar',''))+'</span></span>')

def make_html(cfg, brand, hero, css_file, fonts):
    primary, survey = brand['primary'], brand['secondary']
    paths = {'logo1':Path(primary['logo']), 'logo2':Path(survey['logo']), 'qr':Path(brand['qr'])}
    css = css_file.read_text(encoding='utf-8')
    for family,key in [('PosterRoboto','english'),('PosterCairo','arabic')]:
        css += "@font-face{font-family:"+family+";src:url('"+data_uri(fonts[key])+"');font-weight:900}"
    primary_phones = ''.join(contact_line('☎',n) for n in primary['phones'])
    survey_phones = ''.join(contact_line('☎',n) for n in survey['phones'])
    background = ("style=\"--bg-photo:url('" + hero + "');--hero-photo:url('" + hero + "')\"")
    # All campaign text is escaped; no JavaScript or CSS injected from user copy.
    return f'''<!doctype html><html lang="{ 'ar' if cfg['language']=='ARABIC' else 'en' }"><head>
<meta charset="utf-8"><meta name="viewport" content="width=1080,initial-scale=1"><title>Template 6 — Dual Company</title>
<style>{css}</style></head><body><main id="poster" class="language-{cfg['language'].lower()}" {background}>
<div class="backdrop"></div><div class="edge left"></div><div class="edge right"></div>
<header class="header">
  <div class="company"><div class="logo-box"><img src="{data_uri(paths['logo1'])}" alt="Configured primary logo"></div>
    <div class="brand-copy"><div class="brand-title fit" data-min="34">{esc(primary['short_name'])}</div>
    <div class="brand-sub fit" data-min="16">{esc(primary['display_name'])}</div>
    <div class="brand-trade fit" data-min="13">{esc(primary['descriptor'])}</div></div></div>
  <div class="brand-divider"></div>
  <div class="company"><div class="logo-box survey"><img src="{data_uri(paths['logo2'])}" alt="Configured secondary logo"></div>
    <div class="brand-copy"><div class="brand-title survey-title fit" data-min="25">{esc(survey['display_name'])}</div>
    <div class="brand-sub fit" data-min="15">{esc(survey['descriptor'])}</div></div></div>
</header>
<section class="title-stack">
 <div class="paint-band green"><span class="band-text fit" data-min="44">{render_copy(cfg,'headline')}</span></div>
 <div class="paint-band navy"><span class="band-text fit" data-min="43">{render_copy(cfg,'subheadline')}</span></div>
 <div class="pink-rays l">≻</div><div class="pink-rays r">≺</div>
</section>
<div class="tagline"><span class="fit" data-min="20">{render_copy(cfg,'tagline')}</span></div>
<div class="description fit" data-min="17">{render_copy(cfg,'description')}</div>
<section class="stage"><div class="stage-photo"></div><div class="frame"></div>
 <div class="service-cards">
  <div class="service-card"><div class="service-icon">{icon_svg('worker')}</div><div class="service-divider"></div>
   <div class="service-copy"><strong>{esc(primary['short_name'])}</strong><small class="fit" data-min="15">{render_copy(cfg,'primary_services')}</small></div></div>
  <div class="service-card survey"><div class="service-icon">{icon_svg('survey')}</div><div class="service-divider"></div>
   <div class="service-copy"><strong class="fit" data-min="20">{esc(survey['short_name'])}</strong><small class="fit" data-min="15">{render_copy(cfg,'secondary_services')}</small></div></div>
 </div>
</section>
<div class="benefit"><span class="fit" data-min="25">{render_copy(cfg,'benefit')}</span></div>
<div class="cta"><span class="cta-icon">☎</span><span class="fit" data-min="22">{render_copy(cfg,'cta')}</span></div>
<footer class="contact-footer">
  <div class="contact-col left"><div class="footer-name">{esc(primary['short_name'])}</div>
   {contact_line('◎',primary['website'])}{contact_line('✉',primary['email'])}
   {primary_phones}
   <div class="socialbar"><span class="social-icon">f</span><span class="social-icon ig">◎</span><span class="social-icon yt">▶</span><span class="social-icon tt">♪</span>
    <span class="social-handle">{esc(primary.get('social',''))}</span></div>
  </div>
  <div class="qr-column"><div class="qr-title">{esc(brand['qr_label'])}</div>
   <div class="qr-frame"><img class="qr-image" src="{data_uri(paths['qr'])}" alt="Configured primary QR"></div></div>
  <div class="contact-col right"><div class="footer-name long fit" data-min="20">{esc(survey['short_name'])}</div>
   {contact_line('◎',survey['website'])}{contact_line('✉',survey['email'])}
   {survey_phones}
   {contact_line('⌖',survey.get('location',''))}
  </div>
  <div class="bottom-stroke"></div>
</footer>
</main></body></html>'''

