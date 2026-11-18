import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from toolkit.google_sheets import GogSheets
from toolkit.workflow_tracker import Tracker

class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.tabs={'Drafts':{'headers':['run_id','post_id','url','status'],'key':'run_id'},'Topics':{'headers':['run_id','topic','keyword'],'key':'run_id'},'Runs':{'headers':['run_id','plan_sha256','status'],'key':'run_id'}}
        self.rows={k:[v['headers']] for k,v in self.tabs.items()};self.calls=[];self.fail_before=False;self.lose=False;self.formula=False
        def run(cmd,**kwargs):
            action=cmd[2];tab=cmd[4].split("'")[1]
            if action=='get':
                rows=copy.deepcopy(self.rows[tab])
                if self.formula and '--render' in cmd:rows.append(['=UNTRUSTED()'])
                return SimpleNamespace(returncode=0,stdout=json.dumps({'values':rows}))
            self.calls.append(cmd)
            if self.fail_before:raise OSError('before write')
            value=next(x.split('=',1)[1] for x in cmd if x.startswith('--values-json='));self.rows[tab]=json.loads(value)
            if self.lose:raise OSError('lost response')
            return SimpleNamespace(returncode=0,stdout='{}')
        self.gog=GogSheets('fixture-account','fixture-client',runner=run,env={},allow_reads=True,allow_writes=True)
        self.t=Tracker(Path(self.tmp.name)/'tracker',self.gog,sheet_id='fixture-sheet',tabs=self.tabs,exclusive_writer=True)
    def plan(self):
        return self.t.seo_draft_plan({'status':'draft','post_id':10,'url':'https://cms.example/draft','plan_sha256':'a'*64},{'title':'Topic','keyword':'Keyword'},draft_tab='Drafts',topic_tab='Topics',run_tab='Runs',run_id='run-1')
    def test_three_tabs_exact_replay(self):
        p=self.plan()
        for _ in range(2):self.assertEqual(set(self.t.apply('operation',p,approved_digest=p['digest']).values()),{'VERIFIED'})
        self.assertEqual(len(self.calls),3);self.assertTrue(all('--input=RAW' in x for x in self.calls))
    def test_response_loss_reconciles_each_tab(self):
        p=self.plan();self.lose=True;self.t.apply('operation',p,approved_digest=p['digest']);self.t.apply('operation',p,approved_digest=p['digest']);self.assertEqual(len(self.calls),3)
    def test_unknown_first_write_not_retried(self):
        p=self.plan();self.fail_before=True
        for _ in range(2):
            with self.assertRaises(RuntimeError):self.t.apply('operation',p,approved_digest=p['digest'])
        self.assertEqual(len(self.calls),1)
    def test_all_tabs_preflight_before_write(self):
        p=self.plan();self.rows['Runs'].append(['other','b','Draft'])
        with self.assertRaises(RuntimeError):self.t.apply('operation',p,approved_digest=p['digest'])
        self.assertFalse(self.calls)
    def test_formulas_and_unapproved_plan_rejected(self):
        self.formula=True
        with self.assertRaises(ValueError):self.plan()
        self.formula=False;p=self.plan()
        with self.assertRaises(PermissionError):self.t.apply('operation',p,approved_digest='wrong')
        self.assertFalse(self.calls)
    def test_no_rebinding_and_duplicate_keys(self):
        p=self.plan();self.t.apply('operation',p,approved_digest=p['digest'])
        self.rows['Topics'].append(['run-1','Another','K'])
        with self.assertRaises(ValueError):self.plan()
    def test_out_of_schema_address_rejected(self):
        from toolkit.trusted_bridge import fingerprint
        p=self.plan();p['binding']['tabs']['Drafts']['range']="'Other'!A1:D2";p['digest']=fingerprint(p['binding'])
        with self.assertRaises(ValueError):self.t.apply('operation',p,approved_digest=p['digest'])
        self.assertFalse(self.calls)

    def test_frozen_workflow_plan_reused(self):
        result={'status':'draft','post_id':10,'url':'https://cms.example/draft','plan_sha256':'a'*64}
        article={'title':'Topic','keyword':'Keyword'}
        for _ in range(2):self.t.sync_seo_draft(result,article,draft_tab='Drafts',topic_tab='Topics',run_tab='Runs',run_id='run-1',enabled=True)
        self.assertEqual(len(self.calls),3)
        with self.assertRaises(ValueError):self.t.sync_seo_draft(dict(result,post_id=11),article,draft_tab='Drafts',topic_tab='Topics',run_tab='Runs',run_id='run-1',enabled=True)

    def test_social_draft_never_approval(self):
        tabs={'Queue':{'headers':['job_id','status','approval_mode','schedule'],'key':'job_id'},'Content':{'headers':['job_id','revision','template','media_url','content_sha256','captions_json'],'key':'job_id'}}
        self.rows.update({k:[v['headers']] for k,v in tabs.items()})
        t=Tracker(Path(self.tmp.name)/'social',self.gog,sheet_id='fixture-sheet',tabs=tabs,exclusive_writer=True)
        s={'phase':'DRAFT','approval_mode':'MANUAL','schedule':None,'job_id':'job-1','revision':1,'artifact':{'url':'https://media.example/photo'},'campaign':{'template':1,'captions':{'facebook':'Exact'}}}
        p=t.social_draft_plan(s,queue_tab='Queue',content_tab='Content');t.apply('draft-1',p,approved_digest=p['digest'])
        self.assertEqual(self.rows['Queue'][1],['job-1','WAITING_APPROVAL','MANUAL',''])
        s['phase']='APPROVED'
        with self.assertRaises(PermissionError):t.social_draft_plan(s,queue_tab='Queue',content_tab='Content')
