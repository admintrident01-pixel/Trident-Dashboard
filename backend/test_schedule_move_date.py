import copy,unittest
from unittest.mock import patch
import schedule,schedule_routes,schedule_history,test_accounts
from core import Problem
class MoveDateTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  self.routes=patch.object(schedule_routes,'estimate',return_value={'duration':15,'seconds':501,'distanceMeters':1000});self.routes.start();self.addCleanup(self.routes.stop)
  self.user={'email':'admin@example.nz'};self.date='2027-02-01';self.target='2027-02-02'
  base={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]}}
  self.booking={'date':self.date,'technician':'Scott','start':'09:00','duration':30,'client':'First','address':'A Road','type':'Repair','timing':'flexible','notes':''}
  state,self.a=schedule.save(base,self.booking,self.user);self.state,self.b=schedule.save(state,{**self.booking,'start':'11:00','client':'Second','address':'B Road'},self.user)
 def move(self,state,ids):return schedule.save_travel(state,{'date':self.date,'targetDate':self.target,'action':'move_to_date','ids':ids},self.user)
 def test_multiple_moves_and_undo_preserve_both_days(self):
  self.state['quotes']={'keep':123};before=copy.deepcopy(self.state);result=self.move(self.state,[self.a['id'],self.b['id']])
  self.assertEqual(schedule.read(result,self.date)['appointments'],[]);self.assertEqual([a['start'] for a in schedule.read(result,self.target)['appointments']],['09:00','11:00']);self.assertEqual(result['quotes'],before['quotes']);self.assertEqual(self.state,before)
  result=schedule_history.record(self.state,result,self.user['email'],self.date,'Move date');restored=schedule_history.apply(result,self.user['email'],self.date,'undo');self.assertEqual(schedule_history.signature(restored),schedule_history.signature(self.state))
 def test_linked_form_date_change_moves_linked_bookings_but_selected_move_does_not(self):
  self.state['appointments'][self.b['id']]['start']='09:45'
  result,edited=schedule.save(self.state,{**self.a,'date':self.target,'notes':'Moved'},self.user)
  self.assertEqual(result['appointments'][self.b['id']]['date'],self.target);self.assertEqual(edited['notes'],'Moved')
  result=self.move(self.state,[self.b['id']]);self.assertEqual(result['appointments'][self.a['id']],self.state['appointments'][self.a['id']])
 def test_fixed_and_booked_are_named_and_must_be_changed_first(self):
  for field,value,word in [('timing','fixed','booked'),('bookingStatus','confirmed','Unbook')]:
   state=copy.deepcopy(self.state);state['appointments'][self.b['id']][field]=value;state['appointments'][self.b['id']].pop('bookingControlsVersion',None);before=copy.deepcopy(state)
   with self.assertRaisesRegex(Problem,word):self.move(state,[self.a['id'],self.b['id']])
   self.assertEqual(state,before)
  state,a=schedule.save(self.state,{**self.a,'bookingStatus':'confirmed'},self.user)
  with self.assertRaisesRegex(Problem,'Unbook'):schedule.save(state,{**a,'date':self.target,'bookingStatus':'action-needed'},self.user)
  state,a=schedule.save(state,{**a,'bookingStatus':'action-needed'},self.user);result,updated=schedule.save(state,{**a,'date':self.target},self.user);self.assertEqual(updated['date'],self.target)
 def test_destination_collision_is_atomic(self):
  state,_=schedule.save(self.state,{**self.booking,'date':self.target,'client':'Occupied'},self.user);before=copy.deepcopy(state)
  with self.assertRaisesRegex(Problem,'overlaps'):self.move(state,[self.a['id'],self.b['id']])
  self.assertEqual(state,before)
 def test_default_lunch_and_travel_selection(self):
  lunch=next(a for a in schedule.lunch_blocks(self.state,self.date) if a['technician']=='Scott');result=self.move(self.state,[lunch['id']])
  self.assertFalse(any(a['technician']=='Scott' for a in schedule.lunch_blocks(result,self.date)));self.assertEqual(len([a for a in result['appointments'].values() if a.get('source')=='lunch' and a['date']==self.target and not a.get('cancelled')]),1)
  with self.assertRaisesRegex(Problem,'associated appointment'):self.move(self.state,[schedule.travel_blocks(self.state,self.date)[0]['id']])
 def test_endpoint_permission_revision_and_history(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state);body={'date':self.date,'targetDate':self.target,'action':'move_to_date','ids':[self.a['id']]}
  self.assertEqual(api.call('/api/schedule/travel','POST',body,token='tech')[0],403);self.assertEqual(api.call('/api/schedule/travel','POST',body,match=False)[0],409)
  status,payload,_=api.call('/api/schedule/travel','POST',body);self.assertEqual(status,200);self.assertTrue(payload['history']['undo']['available'])
