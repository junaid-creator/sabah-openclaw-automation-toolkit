import copy
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from toolkit.poster_render import build,normalized

class PosterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.photo=self.root/'atlas.png';Image.new('RGB',(800,800),'#335577').save(self.photo)
        self.font=self.root/'font.ttf';self.font.write_bytes(b'fixture-font-not-used-in-browser')
        self.fonts={'english':self.font,'arabic':self.font}
        logo=Path(__file__).resolve().parents[1]/'poster_templates/assets/primary-logo.svg'
        company={k:'DEMO' for k in ['short_name','display_name','descriptor','tagline','display_name_ar','descriptor_ar','tagline_ar','website','email','location','social']};company.update(logo=logo,phones=['000 000 0000'])
        self.brand={'primary':company,'secondary':dict(company,short_name='SECOND'),'qr':logo,'backdrop':logo,'qr_label':'PLACEHOLDER'}
        self.content={'headline':'READY','headline_ar':'جاهز','subheadline':'TOOLS','subheadline_ar':'معدات','cta':'CONTACT','cta_ar':'اتصل','services':[{'en':'Tool','ar':'معدات','icon':'equipment'} for _ in range(4)]}
    def test_all_six_original_structures_build(self):
        for n in range(1,7):
            text=build(n,self.content,self.brand,self.fonts,self.photo)
            self.assertIn('id="poster"',text);self.assertIn('DEMO',text)
            if n==6:self.assertIn('SECOND',text);self.assertIn('service-card survey',text)
            elif n>1:self.assertIn('catalog-'+str(n),text)
            else:self.assertIn('style-equipment',text)
    def test_all_language_modes(self):
        for n in range(1,7):
            for language in ['ENGLISH','ARABIC','BILINGUAL']:
                text=build(n,dict(self.content,language=language),self.brand,self.fonts,self.photo)
                self.assertIn('language-'+language.lower(),text)
                if language=='BILINGUAL':self.assertIn('bilingual-ar' if n==6 else 'copy-ar',text);self.assertIn('bilingual-en' if n==6 else 'copy-en',text)
    def test_default_is_english(self):self.assertEqual(normalized(self.content,1)['language'],'ENGLISH')
    def test_missing_translation_fails(self):
        content=dict(self.content,language='BILINGUAL');content.pop('headline_ar')
        with self.assertRaises(ValueError):normalized(content,1)
    def test_invalid_template_and_language_fail(self):
        for n in [0,7,'1',True]:
            with self.assertRaises(ValueError):normalized(self.content,n)
        with self.assertRaises(ValueError):normalized(dict(self.content,language='AUTO'),1)
    def test_four_services_required(self):
        for services in [[],self.content['services'][:3],self.content['services']*2]:
            with self.assertRaises(ValueError):normalized(dict(self.content,services=services),2)
    def test_copy_is_escaped(self):
        text=build(1,dict(self.content,headline='<script>alert(1)</script>'),self.brand,self.fonts,self.photo)
        self.assertNotIn('<script>',text);self.assertIn('&lt;script&gt;',text)
    def test_atlas_geometry_and_hero_mode(self):
        for n in [2,3,5]:
            text=build(n,self.content,self.brand,self.fonts,self.photo)
            self.assertIn('viewBox="0 0 200 400"',text)
        self.assertIn('complete-hero-photo',build(4,self.content,self.brand,self.fonts,self.photo))
    def test_input_not_mutated(self):
        before=copy.deepcopy(self.content);build(1,self.content,self.brand,self.fonts,self.photo);self.assertEqual(before,self.content)
        from poster_fixture_helpers import private_demo_assets,NAMES
        source=self.root/'source-assets';source.mkdir(mode=0o700)
        original=Path(__file__).resolve().parents[1]/'poster_templates/assets'
        for name in NAMES:
            p=source/name;p.write_bytes((original/name).read_bytes());p.chmod(0o664)
        target=private_demo_assets(source,self.root)
        for name in NAMES:
            self.assertEqual((source/name).stat().st_mode & 0o777,0o664)
            self.assertEqual((target/name).stat().st_mode & 0o777,0o600)
            self.assertEqual((target/name).read_bytes(),(source/name).read_bytes())
        self.assertEqual(private_demo_assets(source,self.root),target)
        (source/NAMES[0]).write_bytes(b'changed')
        with self.assertRaises(ValueError):private_demo_assets(source,self.root)

if __name__=='__main__':unittest.main()
