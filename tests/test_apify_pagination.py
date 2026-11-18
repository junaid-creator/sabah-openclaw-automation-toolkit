import unittest
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs
from toolkit.apify_client import ApifyClient
from toolkit.apify_budget import RunBudgetUnsafe


class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.rows=[{'id':'run-'+str(i),'status':'SUCCEEDED'} for i in range(235)]
        self.mutate=lambda page,index:page
        self.client=ApifyClient('fixture~actor','fixture-actor',lambda:'unused',transport=self.transport)
        p=patch('socket.socket',side_effect=AssertionError('No network'));p.start();self.addCleanup(p.stop)

    def transport(self,method,path,payload):
        self.assertEqual(method,'GET');self.assertIsNone(payload)
        q=parse_qs(urlsplit(path).query);offset=int(q['offset'][0]);limit=int(q['limit'][0]);self.assertEqual(q['desc'],['0'])
        rows=self.rows[offset:offset+limit]
        page=dict(total=len(self.rows),offset=offset,limit=limit,count=len(rows),desc=False,items=rows)
        self.calls.append(path)
        return self.mutate(page,len(self.calls))

    def test_complete_history_over_30(self):
        self.assertEqual(len(self.client.account_runs()),235);self.assertEqual(len(self.calls),4)

    def test_empty_history_rechecked(self):
        self.rows=[];self.assertEqual(self.client.account_runs(),[]);self.assertEqual(len(self.calls),2)

    def test_nonterminal_and_unknown_states(self):
        for status in ('READY','RUNNING','TIMING-OUT','ABORTING','UNKNOWN',None):
            self.rows[200]['status']=status
            with self.assertRaises(RunBudgetUnsafe):self.client.account_runs()

    def test_bound_exceeded(self):
        with self.assertRaises(RunBudgetUnsafe):self.client.account_runs(page_size=10,max_pages=2)
        self.assertEqual(len(self.calls),1)

    def test_changed_total(self):
        self.mutate=lambda p,n:dict(p,total=p['total']+1) if n==2 else p
        with self.assertRaises(RunBudgetUnsafe):self.client.account_runs()

    def test_duplicate_run(self):
        self.rows[120]['id']=self.rows[0]['id']
        with self.assertRaises(RunBudgetUnsafe):self.client.account_runs()

    def test_bad_metadata(self):
        for extra in ({'offset':3},{'count':0},{'total':True},{'desc':True},{'limit':99}):
            self.mutate=lambda p,n:dict(p,**extra)
            with self.assertRaises(RunBudgetUnsafe):self.client.account_runs()

    def test_empty_intermediate_page(self):
        self.mutate=lambda p,n:dict(p,count=0,items=[]) if n==2 else p
        with self.assertRaises(RunBudgetUnsafe):self.client.account_runs()

    def test_head_recheck_changed(self):
        def mutate(p,n):
            if n==4:p['items']=[dict(r,id='changed-'+r['id']) for r in p['items']]
            return p
        self.mutate=mutate
        with self.assertRaises(RunBudgetUnsafe):self.client.account_runs()

    def test_invalid_bounds(self):
        for kw in ({'page_size':True},{'page_size':0},{'max_pages':21}):
            with self.assertRaises(ValueError):self.client.account_runs(**kw)

    def test_start_blocks_before_paid_post(self):
        # Reuse the full authorization/billing fixture, but inject a nonterminal
        # account run. Both fixtures deny network. No POST may be attempted.
        from test_acquisition import AcquisitionTests
        fixture=AcquisitionTests('test_explicit_paid_approval');fixture.setUp()
        try:
            client,calls=fixture.client();original=client.transport
            def transport(method,path,payload):
                if path.startswith('actor-runs?'):
                    return dict(items=[{'id':'active','status':'ABORTING'}],total=1,count=1,offset=0,limit=100,desc=False)
                return original(method,path,payload)
            client.transport=transport
            with self.assertRaises(RunBudgetUnsafe):fixture.start(client)
            self.assertFalse(any(m=='POST' for m,p in calls));self.assertFalse(fixture.state.exists())
        finally:fixture.doCleanups()
