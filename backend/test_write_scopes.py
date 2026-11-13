import copy,io,json,threading,unittest
from unittest.mock import patch
import recycle,schedule_routes,test_accounts

class RacingStore(test_accounts.MemoryStore):
 """Commits an unrelated change once, just before the first save lands."""
 def __init__(self,state):
  super().__init__(state);self.race=True;self.lock=threading.RLock()
 def commit(self,revision,state):
  with self.lock:
   if self.race:
    self.race=False
    self.state=copy.deepcopy(self.state);self.state['mailOutbox']={'race':{'id':'race'}}
    self.revision+=1
   if revision!=self.revision:return False
   self.state=copy.deepcopy(state);self.revision=revision+1
   return True

class CountingStore(test_accounts.MemoryStore):
 def __init__(self,state):
  super().__init__(state);self.reads=0
 def read(self):
  self.reads+=1;return super().read()

class ScopedWriteTests(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp()
  self.api.store=RacingStore(self.api.store.state);self.api.app.store=self.api.store
  self.date='2027-02-01'
  self.booking={'date':self.date,'technician':'Scott Yearbury','client':'Sample','address':'1 Sample Road','start':'09:00','duration':30,'type':'Repair','timing':'flexible','notes':''}
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
 def call(self,method='GET',path='/api/stock',body=None,tag=''):
  raw=json.dumps(body).encode() if body is not None else b''
  env={'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'date='+self.date,'HTTP_ORIGIN':'http://127.0.0.1:18780','HTTP_AUTHORIZATION':'Bearer admin','HTTP_IF_MATCH':tag,'CONTENT_LENGTH':str(len(raw)),'REMOTE_ADDR':'127.0.0.1','wsgi.input':io.BytesIO(raw)}
  meta=[];raw=b''.join(self.api.app(env,lambda s,h:meta.append((int(s[:3]),dict(h)))))
  return meta[0][0],json.loads(raw),meta[0][1]
 def unrelated_save(self,key='timesheets'):
  revision,state=self.api.store.read();state[key]={'preserve':'new'};self.assertTrue(self.api.store.commit(revision,state))
 def test_stock_uses_its_own_token(self):
  _,_,headers=self.call();tag=headers['ETag'];self.assertTrue(tag.startswith('"stock-'),tag)
  self.api.store.race=False;self.unrelated_save()
  status,data,h=self.call('POST',body={'action':'product','code':'BED','description':'Bed'},tag=tag)
  self.assertEqual(status,200,data);self.assertIn('stock',data);self.assertTrue(h['ETag'].startswith('"stock-'))
  state=self.api.store.state;self.assertEqual(state['timesheets'],{'preserve':'new'});self.assertTrue(state['stock']['products'])
 def test_stock_change_still_blocks_a_stale_edit(self):
  _,_,headers=self.call();tag=headers['ETag'];self.api.store.race=False
  self.assertEqual(self.call('POST',body={'action':'product','code':'BED','description':'Bed'},tag=tag)[0],200)
  saved=copy.deepcopy(self.api.store.state)
  self.assertEqual(self.call('POST',body={'action':'product','code':'CHAIR','description':'Chair'},tag=tag)[0],409)
  self.assertEqual(self.api.store.state,saved)
 def test_unrelated_save_mid_request_is_rebased(self):
  _,_,headers=self.call(path='/api/schedule');tag=headers['ETag'];self.assertTrue(tag.startswith('"schedule-'),tag)
  status,data,_=self.call('POST','/api/schedule',self.booking,tag)
  self.assertEqual(status,200,data);self.assertEqual(self.api.store.state['mailOutbox'],{'race':{'id':'race'}})
  self.assertEqual([a['client'] for a in self.api.store.state['appointments'].values()],['Sample'])
 def test_stock_capture_does_not_touch_the_new_state(self):
  before={'appointments':{'a':{'id':'a','client':'Sample','date':self.date,'cancelled':False}},'pdfs':{}}
  after={'appointments':{},'pdfs':{}}
  result=recycle.capture(before,after,'admin')
  self.assertEqual(after['appointments'],{});self.assertIn('appointment:a',result['recycleBin'])
  unchanged={'appointments':{'a':{'id':'a','cancelled':False}}}
  self.assertIs(recycle.capture(unchanged,unchanged,'admin'),unchanged)
 def test_direct_commit_reuses_request_snapshot(self):
  api=test_accounts.AccountsAPI();api.setUp()
  store=CountingStore(api.store.state);api.store=store;api.app.store=store
  store.state['mailOutbox']={'mail':{'id':'mail','archived':False}}
  before=store.reads
  status,data,_=api.call('/api/mail-archive','POST',{'id':'mail','archived':True})
  self.assertEqual(status,200,data)
  self.assertEqual(store.reads-before,1)
  self.assertTrue(store.state['mailOutbox']['mail']['archived'])

if __name__=='__main__':unittest.main()
