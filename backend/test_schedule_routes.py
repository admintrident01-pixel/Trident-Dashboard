import copy, unittest
from unittest.mock import patch
import schedule, schedule_routes, schedule_links
from core import Problem

class RoutingTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  self.original_estimate=schedule_routes.estimate
  self.route=patch.object(schedule_routes,'estimate',return_value={'duration':30,'seconds':901});self.route.start();self.addCleanup(self.route.stop)
  self.actor={'email':'admin@example.nz'}
  self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''}]}}
  self.booking={'date':'2027-02-01','technician':'Scott','start':'09:00','duration':60,'client':'First','address':'1 Road','type':'Repair','timing':'flexible','notes':''}
  self.state,self.first=schedule.save(self.state,self.booking,self.actor)
 def test_rounds_up_to_quarter_hours(self):
  for seconds,minutes in [(0,0),(1,15),(900,15),(901,30),(1800,30),(1801,45)]:self.assertEqual(schedule_routes.rounded_minutes(seconds),minutes)
 def test_depot_trips_and_between_bookings(self):
  state,second=schedule.save(self.state,{**self.booking,'start':'11:00','client':'Second','address':'2 Road'},self.actor)
  blocks=schedule.travel_blocks(state,self.booking['date'])
  self.assertEqual(len(blocks),3)
  self.assertEqual([(b['origin'],b['destination']) for b in blocks],[('Depot','1 Road'),('1 Road','2 Road'),('2 Road','Depot')])
  self.assertTrue(all(b['duration']==30 and b['locked'] for b in blocks))
 def test_lock_manual_adjustment_and_relock(self):
  b=schedule.travel_blocks(self.state,self.booking['date'])[0]
  with self.assertRaisesRegex(Problem,'Unlock'):schedule.save_travel(self.state,{**b,'action':'resize','delta':15},self.actor)
  state=schedule.save_travel(self.state,{**b,'action':'lock','locked':False},self.actor)
  b=schedule.travel_blocks(state,self.booking['date'])[0]
  state=schedule.save_travel(state,{**b,'action':'resize','delta':15},self.actor)
  b=schedule.travel_blocks(state,self.booking['date'])[0];self.assertEqual(b['duration'],45)
  state=schedule.save_travel(state,{**b,'action':'lock','locked':True},self.actor)
  self.assertEqual(schedule.travel_blocks(state,self.booking['date'])[0]['duration'],30)
 def test_unlink_travel_keeps_position_when_booking_moves(self):
  before=schedule.travel_blocks(self.state,self.booking['date'])[0]
  edge=next(e for e in schedule_links.connections(self.state,self.booking['date']) if e['leftId']==before['id'])
  state=schedule.save_travel(self.state,{'date':self.booking['date'],'action':'link','edgeId':edge['id'],'linked':False},self.actor)
  state,moved=schedule.save(state,{**self.first,'start':'09:30'},self.actor)
  detached=next(b for b in schedule.travel_blocks(state,self.booking['date']) if b['id']==before['id'])
  self.assertFalse(detached['linked']);self.assertEqual(detached['start'],before['start'])
 def test_touching_bookings_move_together_then_unlink(self):
  state,second=schedule.save(self.state,{**self.booking,'start':'10:30','client':'Second'},self.actor)
  state,moved=schedule.save(state,{**self.first,'start':'08:30'},self.actor)
  self.assertEqual(state['appointments'][second['id']]['start'],'10:00')
  edge=next(e for e in schedule_links.connections(state,self.booking['date']) if e['leftId']==self.first['id'])
  state=schedule.save_travel(state,{'date':self.booking['date'],'action':'link','edgeId':edge['id'],'linked':False},self.actor)
  state,_=schedule.save(state,{**moved,'start':'08:00'},self.actor)
  self.assertEqual(state['appointments'][second['id']]['start'],'10:00')
 def test_fixed_linked_booking_cannot_be_shifted(self):
  state,second=schedule.save(self.state,{**self.booking,'start':'10:30','client':'Second','timing':'fixed'},self.actor)
  with self.assertRaisesRegex(Problem,'fixed'):schedule.save(state,{**self.first,'start':'08:30'},self.actor)
 def test_insufficient_gap_preserves_full_estimate_and_flags_conflict(self):
  state,_=schedule.save(self.state,{**self.booking,'start':'10:15','client':'Second'},self.actor)
  b=next(b for b in schedule.travel_blocks(state,self.booking['date']) if b['origin']=='1 Road' and b['side']=='before' and b['anchorId']!=self.first['id'])
  self.assertEqual(b['duration'],30);self.assertTrue(b['routeConflict'])
 def test_routing_failure_is_explicit_not_confirmed_estimate(self):
  with patch.object(schedule_routes,'estimate',return_value={'error':'Google Routes access denied'}):
   b=schedule.travel_blocks(self.state,self.booking['date'])[0]
   self.assertIn('denied',b['routeError']);self.assertIsNone(b['estimatedSeconds'])
 def test_stale_lock_and_missing_edge_rejected(self):
  b=schedule.travel_blocks(self.state,self.booking['date'])[0]
  with self.assertRaises(Problem):schedule.save_travel(self.state,{**b,'action':'lock','locked':False,'version':99},self.actor)
  with self.assertRaises(Problem):schedule.save_travel(self.state,{'date':self.booking['date'],'action':'link','edgeId':'wrong','linked':False},self.actor)

 def test_unlocked_unlinked_travel_can_move_independently(self):
  b=schedule.travel_blocks(self.state,self.booking['date'])[0]
  state=schedule.save_travel(self.state,{**b,'action':'lock','locked':False},self.actor)
  edge=next(e for e in schedule_links.connections(state,self.booking['date']) if e['leftId']==b['id'])
  state=schedule.save_travel(state,{'date':self.booking['date'],'action':'link','edgeId':edge['id'],'linked':False},self.actor)
  b=next(row for row in schedule.travel_blocks(state,self.booking['date']) if row['id']==b['id'])
  state=schedule.save_travel(state,{**b,'action':'move','start':'08:00'},self.actor)
  moved=next(row for row in schedule.travel_blocks(state,self.booking['date']) if row['id']==b['id'])
  self.assertEqual(moved['start'],'08:00')
  with self.assertRaises(Problem):schedule.save_travel(state,{**moved,'action':'move','start':'09:00'},self.actor)
 def test_touching_lunch_is_linked_and_moves_with_group(self):
  state,second=schedule.save(self.state,{**self.booking,'start':'10:30','client':'Second'},self.actor)
  state,_=schedule.save(state,{**self.first,'start':'10:00'},self.actor)
  lunch=next(a for a in state['appointments'].values() if a.get('source')=='lunch')
  self.assertEqual(lunch['start'],'13:00')
 def test_own_depot_travel_follows_booking_to_another_date(self):
  state,a=schedule.save(self.state,{**self.first,'date':'2027-02-02'},self.actor)
  self.assertEqual(len(schedule.travel_blocks(state,'2027-02-02')),2)
  self.assertEqual(schedule.travel_blocks(state,'2027-02-01'),[])
 def test_locked_travel_cannot_be_replaced_using_insert(self):
  b=schedule.travel_blocks(self.state,self.booking['date'])[0]
  with self.assertRaisesRegex(Problem,'Unlock'):schedule.save_travel(self.state,{**b,'action':'insert','duration':45},self.actor)

 def test_provider_failure_is_sanitized(self):
  import io,urllib.error,json
  error=urllib.error.HTTPError('https://routes.googleapis.com',403,'Forbidden',{},io.BytesIO(json.dumps({'error':{'message':'do not expose credentials','details':[{'reason':'SERVICE_DISABLED'}]}}).encode()))
  with patch.object(schedule_routes,'estimate',new=self.original_estimate),patch.object(schedule_routes.urllib.request,'urlopen',side_effect=error):
   result=schedule_routes.estimate('Unique route for failure test','Destination')
  self.assertIn('disabled',result['error']);self.assertNotIn('credentials',result['error'])
 def test_public_schedule_does_not_include_routing_key(self):
  import json
  self.assertNotIn('"key"',json.dumps(schedule.read(self.state,self.booking['date'])))

 def test_recalculate_uses_fresh_route_and_restores_automatic_time(self):
  b=schedule.travel_blocks(self.state,self.booking['date'])[0]
  state=schedule.save_travel(self.state,{**b,'action':'lock','locked':False},self.actor)
  b=schedule.travel_blocks(state,self.booking['date'])[0]
  with patch.object(schedule_routes,'estimate',return_value={'duration':45,'seconds':1801}) as estimate:
   result=schedule.save_travel(state,{**b,'action':'recalculate'},self.actor)
   estimate.assert_any_call('Depot','1 Road',force=True)
  saved=result['travelBlocks'][b['id']]
  self.assertTrue(saved['locked']);self.assertEqual(saved['duration'],45)
 def test_failed_recalculation_leaves_records_unchanged(self):
  b=schedule.travel_blocks(self.state,self.booking['date'])[0];snapshot=copy.deepcopy(self.state)
  with patch.object(schedule_routes,'estimate',return_value={'error':'Check route addresses'}):
   with self.assertRaisesRegex(Problem,'Check route addresses'):schedule.save_travel(self.state,{**b,'action':'recalculate'},self.actor)
  self.assertEqual(self.state,snapshot)
 def test_force_recalculation_bypasses_cached_route(self):
  import io,json
  def response(*args,**kwargs):return io.BytesIO(json.dumps({'routes':[{'duration':'901s','distanceMeters':5000}]}).encode())
  with patch.object(schedule_routes,'estimate',new=self.original_estimate),patch.object(schedule_routes.urllib.request,'urlopen',side_effect=response) as request:
   for force in (False,False,True):self.assertEqual(schedule_routes.estimate('Fresh route cache test','Destination',force=force)['duration'],30)
   self.assertEqual(request.call_count,2)
