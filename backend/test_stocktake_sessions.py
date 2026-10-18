import copy,datetime as dt,unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
import stock,stocktake_sessions as takes,reminders,accounts
from core import Problem
from test_accounts import AccountsAPI

class StocktakeTests(unittest.TestCase):
 def setUp(self):
  self.state=stock.action({},dict(action='product',code='1234567',condition='NEW',description='Count test'),'admin')
  self.pid=next(iter(self.state['stock']['products']))
  self.state=stock.action(self.state,dict(action='receive_stock',date='2026-10-15',productId=self.pid,pool='Existing stock',quantity=3,numbers=['FOUND','MISSING','CLIENT']),'admin')
  self.ids=list(self.state['stock']['assets']);self.move('allocate',self.ids[1:],client='Test client',reference='SO1',jobId='JOB1');self.move('dispatch',self.ids[2:])
 def move(self,action,ids,**kw):
  self.state=stock.action(self.state,dict(action=action,date='2026-10-15',assetIds=ids,revisions={i:self.state['stock']['assets'][i]['revision'] for i in ids},**kw),'admin')
 def start(self):
  self.state=takes.action(self.state,{'action':'start'},'admin');return takes.read(self.state,'admin')['draft']
 def complete(self,entries):
  d=takes.read(self.state,'admin')['draft'];return takes.action(self.state,dict(action='complete',id=d['id'],version=d['version'],entries=entries,confirmed=True),'admin')
 def entry(self,count=2,**kw):return {self.pid:dict(count=count,decisions={self.ids[0]:'found',self.ids[1]:'found'},numbers=[],notes='',**kw)}
 def test_draft_resume_partial_and_owner_isolation(self):
  before=copy.deepcopy(self.state['stock']);d=self.start();self.state=takes.action(self.state,dict(action='save',id=d['id'],version=1,entries={self.pid:dict(count=None,decisions={},numbers=[],notes='Partway')}),'admin')
  self.assertEqual(self.state['stock'],before);self.assertIsNone(takes.read(self.state,'other')['draft']);self.assertEqual(self.start()['version'],2)
  with self.assertRaises(Problem):takes.action(self.state,dict(action='save',id=d['id'],version=1,entries={}), 'admin')
 def test_missing_retired_preserves_identity_allocation_history_and_client_stock(self):
  d=self.start();entry=self.entry(count=2);entry[self.pid].update(decisions={self.ids[0]:'found',self.ids[1]:'missing'},numbers=['ADDED'],notes='Missing in store')
  result=self.complete(entry);data=result['stock'];missing=data['assets'][self.ids[1]]
  self.assertEqual(missing['status'],'Retired');self.assertEqual(missing['number'],'MISSING');self.assertEqual(missing['numberHistory'],self.state['stock']['assets'][self.ids[1]]['numberHistory'])
  self.assertEqual(data['assets'][self.ids[2]]['status'],'With client');self.assertEqual(data['allocations'][missing['lastAllocationId']]['assetStates'][missing['id']]['status'],'Cancelled')
  self.assertEqual(len([a for a in data['assets'].values() if a['status'] in takes.ONSITE]),2)
  self.assertEqual(result['stockTakes'][d['id']]['status'],'completed');self.assertTrue(takes.status(result)['lastCompleted'])
  self.assertEqual(stock.read(result)['stockTakeStatus']['lastCompleted'],takes.status(result)['lastCompleted'])
  with self.assertRaises(Problem):takes.action(result,dict(action='complete',id=d['id'],version=1,entries=entry,confirmed=True),'admin')
 def test_conflict_and_duplicate_numbers_do_not_mutate_original(self):
  self.start();before=copy.deepcopy(self.state);self.state['stock']['assets'][self.ids[0]]['revision']+=1
  with self.assertRaises(Problem):self.complete(self.entry())
  self.state=before;entry=self.entry(3);entry[self.pid]['numbers']=['CLIENT'];before=copy.deepcopy(self.state)
  with self.assertRaises(Problem):self.complete(entry)
  self.assertEqual(self.state,before)
 def test_all_assets_must_be_decided_and_count_cannot_hide_a_numbered_asset(self):
  self.start();entry=self.entry(1)
  with self.assertRaises(Problem):self.complete(entry)
  entry=self.entry();entry[self.pid]['decisions'].pop(self.ids[1])
  with self.assertRaises(Problem):self.complete(entry)
 def test_unchanged_incoming_pending_keeps_receipt_and_pool(self):
  self.state=stock.action(self.state,dict(action='receive',productId=self.pid,pool='New stock',quantity=4,date='2026-10-15'),'admin');rid=list(self.state['stock']['receipts'])[-1];receipt=copy.deepcopy(self.state['stock']['receipts'][rid]);self.start()
  result=self.complete(self.entry(6));self.assertEqual(result['stock']['receipts'][rid],receipt)
 def test_existing_unlabelled_stock_assigned_without_double_counting(self):
  self.state=stock.action(self.state,dict(action='receive',productId=self.pid,pool='Existing stock',quantity=4,date='2026-10-15'),'admin');rid=list(self.state['stock']['receipts'])[-1];self.state['stock']['receipts'][rid]['openingBalance']=True;self.start();e=self.entry(5);e[self.pid]['numbers']=['EXTRA1','EXTRA2'];result=self.complete(e)
  self.assertEqual(result['stock']['receipts'][rid]['quantity'],3);self.assertEqual(len(result['stock']['receipts'][rid]['assetIds']),2);self.assertEqual(stock.balances(result['stock'],self.pid)['onHandQuantity'],5)
 def test_unknown_count_zero_becomes_known(self):
  self.state=stock.action({},dict(action='product',code='ZERO',description='Unknown'),'admin');self.pid=next(iter(self.state['stock']['products']));p=self.state['stock']['products'][self.pid];p.update(sourceRow=1,sourceQuantity=None,quantityBasis='listed_assets');self.start();result=self.complete({self.pid:dict(count=0,decisions={},numbers=[],notes='Checked empty')})
  self.assertTrue(stock.quantity_known(result['stock'],result['stock']['products'][self.pid]));self.assertEqual(stock.balances(result['stock'],self.pid)['onHandQuantity'],0)
 def test_unlisted_product_stays_draft_until_finish(self):
  d=self.start();self.state=takes.action(self.state,dict(action='add_product',id=d['id'],version=1,code='NEW',description='Found unlisted',condition='REFURB'),'admin');self.assertEqual(len(self.state['stock']['products']),1)
  d=takes.read(self.state,'admin')['draft'];pid=d['rows'][-1]['id'];e=self.entry();e[pid]=dict(count=1,decisions={},numbers=['UNLISTED'],notes='');result=self.complete(e)
  self.assertEqual(len(result['stock']['products']),2);self.assertIn('UNLISTED',[a['number'] for a in result['stock']['assets'].values()])
 def test_remove_accidentally_added_product_preserves_register_and_existing_counts(self):
  d=self.start();before=copy.deepcopy(self.state['stock'])
  self.state=takes.action(self.state,dict(action='add_product',id=d['id'],version=d['version'],code='OOPS',description='Mistake',condition=''),'admin')
  d=takes.read(self.state,'admin')['draft'];added=d['rows'][-1]['id']
  result=takes.action(self.state,dict(action='remove_product',id=d['id'],version=d['version'],productId=added),'admin')
  self.assertEqual(result['stock'],before);self.assertEqual([r['id'] for r in takes.read(result,'admin')['draft']['rows']],[self.pid])
  with self.assertRaises(Problem):takes.action(result,dict(action='remove_product',id=d['id'],version=d['version']+1,productId=self.pid),'admin')
  with self.assertRaises(Problem):takes.action(result,dict(action='remove_product',id=d['id'],version=d['version'],productId=added),'admin')
 def test_admin_only_reminders_interval_and_daily_dedupe(self):
  self.start();result=self.complete(self.entry());result['users']={accounts.FIRST_ADMIN:accounts.users({})[accounts.FIRST_ADMIN]};result['users'][accounts.FIRST_ADMIN].update(verified=True,active=True)
  result['users']['staff@example.nz']=dict(email='staff@example.nz',name='Staff',role='tech',active=True,verified=True,technician='Rick')
  result['stockTakeSettings']={'intervalDays':30,'automatic':True};last=takes.status(result)['lastCompleted'];due=dt.date.fromisoformat(last)+dt.timedelta(days=30);now=dt.datetime.combine(due,dt.time(10),ZoneInfo('Pacific/Auckland'))
  rows=[r for r in reminders.dashboard(result,now) if r['kind']=='stocktake'];self.assertEqual(len(rows),1);self.assertEqual(rows[0]['due'],due.isoformat())
  once,count=reminders.due_reminders(result,now);self.assertEqual(count,1);self.assertEqual(reminders.due_reminders(once,now)[1],0)
  self.assertIn('Stocktake reminder',list(once['mailOutbox'].values())[-1]['subject']);result['stockTakeSettings']['automatic']=False;self.assertEqual(reminders.due_reminders(result,now)[1],0)
 def test_interval_and_reminder_preferences_round_trip_through_stock_settings(self):
  result=stock.action(self.state,dict(action='stock_settings',minimums={},stocktakeIntervalDays=45,automaticStocktakes=False),'admin')
  self.assertEqual(stock.read(result)['stockTakeStatus']['intervalDays'],45)
  self.assertFalse(stock.read(result)['stockTakeStatus']['automatic'])
  with self.assertRaises(Problem):stock.action(self.state,dict(action='stock_settings',minimums={},stocktakeIntervalDays=0,automaticStocktakes=True),'admin')

class StocktakeAPITests(AccountsAPI):
 def test_stocktake_api_admin_only_and_version_guard(self):
  self.assertEqual(self.call('/api/stocktake',token='tech')[0],403);self.assertEqual(self.call('/api/stocktake','POST',{'action':'start'},token='tech')[0],403)
  code,body,_=self.call('/api/stocktake','POST',{'action':'start'});self.assertEqual(code,200);draft=body['draft']
  self.assertEqual(self.call('/api/stocktake','POST',dict(action='save',id=draft['id'],version=0,entries={}))[0],409)

if __name__=='__main__':unittest.main()
