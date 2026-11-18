"""Fail-closed reviewed-response policy, not arbitrary prose semantic certification.

An operator-approved phrasebook binds exact replies to locale and inquiry class.
Free-form model output requires a separately qualified independent reviewer.
"""
from .trusted_bridge import fingerprint

class ReviewedPolicy:
    def __init__(self, phrasebook, classifier, *, clock, max_age=86400):
        if not callable(classifier) or not callable(clock) or not 0<max_age<=86400:
            raise ValueError('Trusted classifier, clock and bounded age required')
        if not isinstance(phrasebook,list) or not phrasebook:
            raise ValueError('Operator-reviewed phrases required')
        self.rows=[];self.classifier=classifier;self.clock=clock;self.max_age=max_age
        for row in phrasebook:
            if set(row)!={'locale','intent','text','reviewed_at','reviewer','sha256'}:
                raise ValueError('Exact review fields required')
            if not all(isinstance(row[k],str) and row[k] for k in ('locale','intent','text','reviewer')):
                raise ValueError('Reviewed phrase metadata required')
            if fingerprint({k:row[k] for k in ('locale','intent','text')})!=row['sha256']:
                raise ValueError('Phrase review binding mismatch')
            self.rows.append(dict(row))

    def __call__(self,event,proposal):
        if set(proposal)!={'action','text'} or proposal['action']!='reply':return False
        try:context=self.classifier(dict(event))
        except Exception:return False
        if not isinstance(context,dict) or set(context)!={'locale','intent','confident'} or context['confident'] is not True:
            return False
        for row in self.rows:
            if (row['locale']==context['locale'] and row['intent']==context['intent']
                and row['text']==proposal['text'] and type(row['reviewed_at']) in (int,float)
                and 0<=self.clock()-row['reviewed_at']<=self.max_age):return True
        return False
