import copy,unittest
from unittest.mock import patch
import schedule,schedule_routes,schedule_history,test_accounts
from core import Problem
class HistoryTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  self.route=patch.object(schedule_routes,'estimate',return_value={'duration':15,'seconds':500});self.route.start();self.addCleanup(self.route.stop)
  self.user={'email':'admin@example.nz'};self.date='2027-02-01';self.base={'staffSettings':{'technicians':[{'name':'Scott','rego':''}]}}
  self.booking={'date':self.date,'technician':'Scott','start':'09:00','duration':30,'client':'Example','address':'1 Road','type':'Repair','timing':'flexible','notes':''}
 def record(self,before,after,label='Edit'):return schedule_history.record(before,after,self.user['email'],self.date,label)
 def apply(self,state,action):return schedule_history.apply(state,self.user['email'],self.date,action)
 def create(self):
  state,a=schedule.save(self.base,self.booking,self.user)
  return self.record(self.base,state),a
 def test_create_undo_redo_survives_reload_and_preserves_other_business_data(self):
  state,a=self.create();state['stockRecords']={'keep':123};before=copy.deepcopy(state)
  undone=self.apply(state,'undo');self.assertNotIn(a['id'],undone['appointments']);self.assertEqual(state,before)
  redone=self.apply(copy.deepcopy(undone),'redo');self.assertEqual(redone['appointments'][a['id']]['client'],'Example');self.assertEqual(redone['stockRecords'],{'keep':123})
  self.assertGreater(redone['appointments'][a['id']]['version'],a['version'])
 def test_multiple_undo_redo_and_branch(self):
  state,a=self.create();changed,b=schedule.save(state,{**a,'notes':'Updated'},self.user);state=self.record(state,changed)
  state=self.apply(state,'undo');state=self.apply(state,'undo');state=self.apply(state,'redo');state=self.apply(state,'redo')
  self.assertEqual(state['appointments'][a['id']]['notes'],'Updated')
  state=self.apply(state,'undo');changed,_=schedule.save(state,{**state['appointments'][a['id']],'notes':'Branch'},self.user);state=self.record(state,changed)
  self.assertFalse(schedule_history.read(state,self.date,self.user)['history']['redo']['available'])
 def test_newer_changes_or_other_user_cannot_be_overwritten(self):
  state,a=self.create();state['appointments'][a['id']]['notes']='Another admin changed this'
  with self.assertRaisesRegex(Problem,'newer changes'):self.apply(state,'undo')
  self.assertFalse(schedule_history.read(state,self.date,self.user)['history']['undo']['available'])
  with self.assertRaises(Problem):schedule_history.apply(state,'someone@example.nz',self.date,'undo')
 def test_delete_appointment_travel_and_lunch_restore_together(self):
  state,a=self.create();travel=schedule.travel_blocks(state,self.date)[0];lunch=schedule.lunch_blocks(state,self.date)[0]
  after=schedule.save_travel(state,{'date':self.date,'action':'delete_selection','ids':[a['id'],travel['id'],lunch['id']]},self.user);after=self.record(state,after,'Delete selected')
  self.assertTrue(after['appointments'][a['id']]['cancelled']);self.assertFalse(schedule.travel_blocks(after,self.date));self.assertFalse(schedule.lunch_blocks(after,self.date))
  undone=self.apply(after,'undo');self.assertFalse(undone['appointments'][a['id']]['cancelled']);self.assertEqual(len(schedule.travel_blocks(undone,self.date)),2);self.assertEqual(len(schedule.lunch_blocks(undone,self.date)),1)
  self.assertTrue(self.apply(undone,'redo')['appointments'][a['id']]['cancelled'])
 def test_delete_travel_only_and_undo(self):
  state,a=self.create();travel=schedule.travel_blocks(state,self.date)[0]
  after=schedule.save_travel(state,{'date':self.date,'action':'delete_selection','ids':[travel['id']]},self.user);after=self.record(state,after)
  self.assertNotIn(travel['id'],[b['id'] for b in schedule.travel_blocks(after,self.date)])
  self.assertIn(travel['id'],[b['id'] for b in schedule.travel_blocks(self.apply(after,'undo'),self.date)])
 def test_group_move_and_link_undo(self):
  state,a=self.create();after=schedule.save_travel(state,{'date':self.date,'action':'move_selection','ids':[a['id']],'delta':30},self.user);after=self.record(state,after)
  self.assertEqual(self.apply(after,'undo')['appointments'][a['id']]['start'],'09:00')
  edge=schedule.schedule_links.connections(state,self.date)[0]
  after=schedule.save_travel(state,{'date':self.date,'action':'link','edgeId':edge['id'],'linked':False},self.user);after=self.record(state,after)
  self.assertFalse(after['scheduleLinks'][edge['id']]);self.assertNotIn(edge['id'],self.apply(after,'undo')['scheduleLinks'])
 def test_history_limit_and_invalid_action(self):
  state,a=self.create()
  for n in range(35):
   after,a=schedule.save(state,{**state['appointments'][a['id']],'notes':str(n)},self.user);state=self.record(state,after)
  self.assertEqual(len(schedule_history.stacks(state,self.user['email'],self.date)['undo']),30)
  with self.assertRaises(Problem):self.apply(state,'invalid')
 def test_endpoint_permissions_revision_and_history(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.base)
  status,body,_=api.call('/api/schedule','POST',self.booking);self.assertEqual(status,200);self.assertTrue(body['schedule']['history']['undo']['available'])
  action={'date':self.date,'action':'undo'}
  self.assertEqual(api.call('/api/schedule/travel','POST',action,token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule/travel','POST',action,match=False)[0],409)
  status,body,_=api.call('/api/schedule/travel','POST',action);self.assertEqual(status,200);self.assertTrue(body['history']['redo']['available']);self.assertFalse(body['appointments'])
  status,body,_=api.call('/api/schedule/travel','POST',{'date':self.date,'action':'redo'});self.assertEqual(status,200);self.assertEqual(body['appointments'][0]['client'],'Example')

 def test_legacy_travel_deletion_stays_hidden_without_google_configuration(self):
  with patch.object(schedule_routes,'configuration',return_value={'key':'','depot':'Depot'}):
   state,a=schedule.save(self.base,self.booking,self.user)
   state,b=schedule.save(state,{**self.booking,'client':'Next','start':'10:30'},self.user)
   travel=schedule.travel_blocks(state,self.date)[0]
   deleted=schedule.save_travel(state,{'date':self.date,'action':'delete_selection','ids':[travel['id']]},self.user)
   self.assertNotIn(travel['id'],[b['id'] for b in schedule.travel_blocks(deleted,self.date)])
