import unittest
from toolkit.support_policy import ReviewedPolicy
from toolkit.trusted_bridge import fingerprint
class ReviewedTests(unittest.TestCase):
    def policy(self,**changes):
        row={'locale':'en','intent':'rental','text':'Please confirm quantity and rental dates.'}
        row.update(sha256=fingerprint(row),reviewed_at=100,reviewer='operator-fixture')
        row.update(changes)
        return ReviewedPolicy([row],lambda e:{'locale':'en','intent':e['text'],'confident':True},clock=lambda:120)
    def test_exact(self):
        p=self.policy();self.assertTrue(p({'text':'rental'},{'action':'reply','text':'Please confirm quantity and rental dates.'}))
    def test_invented_terms_wrong_context(self):
        p=self.policy()
        self.assertFalse(p({'text':'rental'},{'action':'reply','text':'Guaranteed available at 10.'}))
        self.assertFalse(p({'text':'complaint'},{'action':'reply','text':'Please confirm quantity and rental dates.'}))
    def test_stale(self):
        self.assertFalse(self.policy(reviewed_at=-100000)({'text':'rental'},{'action':'reply','text':'Please confirm quantity and rental dates.'}))
    def test_changed_review(self):
        with self.assertRaises(ValueError):self.policy(text='Changed')
