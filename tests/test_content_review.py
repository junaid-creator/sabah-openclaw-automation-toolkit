import unittest
from toolkit import content_review as c, google_readiness as g
class PreservationTests(unittest.TestCase):
 def test_additive_roundtrip(self):
  old='<h1>Title</h1><!--insert-->';new=c.additive_candidate(old,'<p>Added</p>','<!--insert-->');self.assertTrue(c.verify_addition(old,new,'<p>Added</p>'))
 def test_additive_drift_rejected(self):
  with self.assertRaises(ValueError):c.verify_addition('<p>Old</p>','<p>Changed</p><p>Added</p>','<p>Added</p>')
 def test_duplicate_marker_rejected(self):
  with self.assertRaises(ValueError):c.additive_candidate('xx','add','x')
 def test_style_only(self):
  self.assertTrue(c.verify_style_only('<style>.x{color:red}</style><p>A</p>','<style>.x{color:blue}</style><p>A</p>'))
 def test_style_noncss_rejected(self):
  with self.assertRaises(ValueError):c.verify_style_only('<style>a</style><p>A</p>','<style>b</style><p>B</p>')
 def test_style_attribute_change_rejected(self):
  with self.assertRaises(ValueError):c.verify_style_only('<style>a</style>','<style media="print">b</style>')
 def test_protected_union(self):
  with self.assertRaises(ValueError):c.verify_protected_fields({'price':10},{'price':10,'stock':4},['description'])
  c.verify_protected_fields({'price':10,'description':'a'},{'price':10,'description':'b'},['description'])
 def test_equivalence_narrow(self):
  self.assertTrue(c.narrow_markup_equivalent('<p>A</p>\n<p>B</p>','<p>A</p><p>B</p>'))
  for other in ['<p>Changed</p><p>B</p>','<p>A</p><p>100</p>','<p>A</p><a href="changed">B</a>']:
   self.assertFalse(c.narrow_markup_equivalent('<p>A</p><p>B</p>',other))
class ReadinessTests(unittest.TestCase):
 def metadata(self):return {'spreadsheetId':'fixture-id','properties':{'title':'Fixture'},'sheets':[{'properties':{'title':'Queue'}}]}
 def test_read_not_edit(self):
  r=g.assess(self.metadata(),'Fixture',scopes=['https://www.googleapis.com/auth/spreadsheets']);self.assertIsNone(r['edit_permission']);self.assertEqual(r['write_readback_test'],'NOT PERFORMED')
 def test_permission_evidence(self):
  r=g.assess(self.metadata(),'Fixture',drive_evidence={'id':'fixture-id','capabilities':{'canEdit':True}});self.assertTrue(r['edit_permission'])
 def test_wrong_file_rejected(self):
  with self.assertRaises(ValueError):g.assess(self.metadata(),'Fixture',drive_evidence={'id':'other','capabilities':{'canEdit':True}})
 def test_wrong_title_rejected(self):
  with self.assertRaises(ValueError):g.assess(self.metadata(),'Other')
