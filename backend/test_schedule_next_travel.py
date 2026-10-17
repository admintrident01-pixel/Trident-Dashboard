import copy,unittest
from unittest.mock import patch
import schedule,schedule_routes,schedule_history,test_accounts
from core import Problem
class NextTravelTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  self.route=patch.object(schedule_routes,'estimate',return_value={'duration':15,'seconds':501});self.route_mock=self.route.start();self.addCleanup(self.route.stop)
  self.user={'email':'admin@example.nz'};self.date='2027-02-01'
  base={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]}}
  self.booking={'date':self.date,'technician':'Scott','start':'09:00','duration':60,'client':'Top','address':'A Road','type':'Repair','timing':'fixed','notes':''}
  state,self.top=schedule.save(base,self.booking,self.user)
  self.state,self.bottom=schedule.save(state,{**self.booking,'start':'11:30','duration':30,'client':'Bottom','address':'B Road','timing':'flexible'},self.user)
  self.action={'date':self.date,'action':'travel_next','technician':'Scott','upperId':self.top['id'],'lowerId':self.bottom['id']}
 def test_flexible_lower_pulls_up_and_upper_is_unchanged(self):
  before=copy.deepcopy(self.state);result=schedule.save_travel(self.state,self.action,self.user)
  self.assertEqual(result['appointments'][self.top['id']],self.top);self.assertEqual(self.state,before)
  self.assertEqual(result['appointments'][self.bottom['id']]['start'],'10:15')
  rows=schedule.travel_blocks(result,self.date)
  travel=next(b for b in rows if b['anchorId']==self.top['id'] and b['side']=='after')
  self.assertEqual((travel['start'],travel['duration'],travel['origin'],travel['destination']),('10:00',15,'A Road','B Road'))
  self.assertFalse(any(b['anchorId']==self.bottom['id'] and b['side']=='before' for b in rows))
  self.route_mock.assert_any_call('A Road','B Road',force=True)
 def test_fixed_requires_choice_then_yes_unlocks_only_lower(self):
  self.state['appointments'][self.bottom['id']]['timing']='fixed'
  with self.assertRaisesRegex(Problem,'Choose whether'):schedule.save_travel(self.state,self.action,self.user)
  result=schedule.save_travel(self.state,{**self.action,'makeFlexible':True},self.user)
  self.assertEqual(result['appointments'][self.top['id']],self.top)
  self.assertEqual(result['appointments'][self.bottom['id']]['timing'],'flexible');self.assertEqual(result['appointments'][self.bottom['id']]['start'],'10:15')
 def test_no_keeps_both_bookings_unchanged_and_anchors_travel(self):
  self.state['appointments'][self.bottom['id']]['timing']='fixed';bottom=copy.deepcopy(self.state['appointments'][self.bottom['id']])
  result=schedule.save_travel(self.state,{**self.action,'makeFlexible':False},self.user)
  self.assertEqual(result['appointments'][self.top['id']],self.top);self.assertEqual(result['appointments'][self.bottom['id']],bottom)
  travel=next(b for b in schedule.travel_blocks(result,self.date) if b['anchorId']==self.top['id'] and b['side']=='after')
  self.assertEqual(travel['start'],'10:00');self.assertTrue(travel['linked'])
 def test_route_failure_and_stale_next_leave_state_unchanged(self):
  before=copy.deepcopy(self.state)
  with patch.object(schedule_routes,'estimate',return_value={'error':'Address not found'}):
   with self.assertRaisesRegex(Problem,'Address not found'):schedule.save_travel(self.state,self.action,self.user)
  with self.assertRaisesRegex(Problem,'changed'):schedule.save_travel(self.state,{**self.action,'lowerId':'missing'},self.user)
  self.assertEqual(self.state,before)
 def test_team_collision_rejects_atomically(self):
  self.state['appointments'][self.bottom['id']]['technicians']=['Scott','Bala']
  state,other=schedule.save(self.state,{**self.booking,'technician':'Bala','start':'10:15','duration':30},self.user);before=copy.deepcopy(state)
  with self.assertRaisesRegex(Problem,'overlap'):schedule.save_travel(state,self.action,self.user)
  self.assertEqual(state,before)
 def test_undo_restores_hidden_travel_links_and_timing(self):
  self.state['appointments'][self.bottom['id']]['timing']='fixed'
  after=schedule.save_travel(self.state,{**self.action,'makeFlexible':True},self.user)
  after=schedule_history.record(self.state,after,self.user['email'],self.date,'Travel to next')
  restored=schedule_history.apply(after,self.user['email'],self.date,'undo')
  self.assertEqual(restored['appointments'][self.bottom['id']]['timing'],'fixed');self.assertEqual(restored['appointments'][self.bottom['id']]['start'],'11:30')
  self.assertEqual(schedule_history.signature(restored),schedule_history.signature(self.state))
 def test_api_admin_and_revision_protection(self):
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
  self.assertEqual(api.call('/api/schedule/travel','POST',self.action,token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule/travel','POST',self.action,match=False)[0],409)
  status,body,_=api.call('/api/schedule/travel','POST',self.action);self.assertEqual(status,200);self.assertTrue(body['history']['undo']['available'])

 def test_no_with_insufficient_gap_retains_fixed_booking_and_flags_travel(self):
  self.state['appointments'][self.bottom['id']].update(start='10:00',timing='fixed');before=copy.deepcopy(self.state['appointments'][self.bottom['id']])
  result=schedule.save_travel(self.state,{**self.action,'makeFlexible':False},self.user)
  self.assertEqual(result['appointments'][self.bottom['id']],before)
  travel=next(b for b in schedule.travel_blocks(result,self.date) if b['anchorId']==self.top['id'] and b['side']=='after')
  self.assertEqual(travel['start'],'10:00');self.assertTrue(travel['routeConflict'])

 def test_hidden_old_incoming_travel_does_not_reduce_the_new_journey_gap(self):
  identifier=schedule.travel_id(self.date,'Scott',self.bottom['id'],'before')
  self.state.setdefault('travelBlocks',{})[identifier]={'date':self.date,'duration':15,'start':'11:15','locked':False,'linked':False,'version':1}
  result=schedule.save_travel(self.state,self.action,self.user)
  travel=next(b for b in schedule.travel_blocks(result,self.date) if b['anchorId']==self.top['id'] and b['side']=='after')
  self.assertFalse(travel['routeConflict']);self.assertEqual(travel['maxDuration'],15)

 def test_travel_only_option_keeps_flexible_lower_at_original_time(self):
  original=copy.deepcopy(self.state['appointments'][self.bottom['id']])
  result=schedule.save_travel(self.state,{**self.action,'pullBelow':False},self.user)
  self.assertEqual(result['appointments'][self.bottom['id']],original)
  travel=next(b for b in schedule.travel_blocks(result,self.date) if b['anchorId']==self.top['id'] and b['side']=='after')
  self.assertEqual(travel['start'],'10:00')
 def test_travel_only_does_not_require_unlock_choice(self):
  self.state['appointments'][self.bottom['id']]['timing']='fixed'
  result=schedule.save_travel(self.state,{**self.action,'pullBelow':False},self.user)
  self.assertEqual(result['appointments'][self.bottom['id']],self.state['appointments'][self.bottom['id']])
