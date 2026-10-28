import copy, unittest
from unittest.mock import patch
import schedule,schedule_links,schedule_routes,test_accounts
from core import Problem

class GapSnapTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  self.routes=patch.object(schedule_routes,'estimate',return_value={'duration':30,'seconds':901});self.routes.start();self.addCleanup(self.routes.stop)
  self.user={'email':'admin@example.nz'};self.date='2027-02-01'
  self.base={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]}}
  self.booking={'date':self.date,'technician':'Scott','start':'09:00','duration':60,'client':'Above','address':'1 Road','type':'Repair','timing':'flexible','notes':''}
 def setup_gap(self,above='flexible',below='flexible'):
  state,self.first=schedule.save(self.base,{**self.booking,'timing':above},self.user)
  state,self.second=schedule.save(state,{**self.booking,'start':'11:00','duration':30,'client':'Below','address':'2 Road','timing':below},self.user)
  gap=next(g for g in schedule_links.free_gaps(state,self.date,'Scott') if g['upperId']==self.first['id'])
  return state,{'date':self.date,'technician':'Scott','action':'snap_gap',**gap}
 def test_closes_gap_moves_lower_group_and_links_touching_edges(self):
  state,body=self.setup_gap();snapshot=copy.deepcopy(state)
  result=schedule.save_travel(state,body,self.user)
  self.assertEqual(state,snapshot)
  self.assertEqual(result['appointments'][self.first['id']]['start'],'09:00')
  self.assertEqual(result['appointments'][self.second['id']]['start'],'10:30')
  edge=next(e for e in schedule_links.connections(result,self.date) if e['leftId']==body['upperId'] and e['rightId']==body['lowerId'])
  self.assertTrue(edge['linked']);self.assertTrue(result['scheduleLinks'][edge['id']])
  self.assertEqual(result['appointments'][self.second['id']]['duration'],30)
  self.assertTrue(all(b['duration']==30 for b in schedule.travel_blocks(result,self.date)))
 def test_fixed_appointment_above_stays_unchanged_while_lower_group_snaps(self):
  state,body=self.setup_gap(above='fixed');before=copy.deepcopy(state)
  result=schedule.save_travel(state,body,self.user)
  self.assertEqual(result['appointments'][self.first['id']],before['appointments'][self.first['id']])
  self.assertEqual(result['appointments'][self.second['id']]['start'],'10:30')
  self.assertEqual(state,before)
  self.assertTrue(any(e['leftId']==body['upperId'] and e['rightId']==body['lowerId'] and e['linked'] for e in schedule_links.connections(result,self.date)))
 def test_fixed_appointment_below_is_detected_through_its_travel_block(self):
  state,body=self.setup_gap(below='fixed')
  with self.assertRaisesRegex(Problem,'appointment below is booked'):schedule.save_travel(state,body,self.user)
 def test_stale_gap_is_rejected(self):
  state,body=self.setup_gap()
  with self.assertRaisesRegex(Problem,'empty space changed'):schedule.save_travel(state,{**body,'lowerId':'missing'},self.user)
 def test_no_gaps_are_created_inside_overlapping_blocks(self):
  state,body=self.setup_gap()
  blocks=[{'id':'long','technician':'Scott','start':'08:00','duration':180},{'id':'short','technician':'Scott','start':'09:00','duration':15},{'id':'next','technician':'Scott','start':'12:00','duration':15}]
  self.assertEqual(schedule_links.free_gaps(state,self.date,'Scott',blocks),[{'upperId':'long','lowerId':'next','start':660,'end':720}])
 def test_shared_booking_collision_on_another_technician_is_rejected(self):
  state,body=self.setup_gap()
  second=state['appointments'][self.second['id']];state['appointments'][second['id']]={**second,'technicians':['Scott','Bala']}
  state,_=schedule.save(state,{**self.booking,'technician':'Bala','start':'10:30','duration':30,'client':'Other job'},self.user)
  with self.assertRaisesRegex(Problem,'overlap'):schedule.save_travel(state,body,self.user)
 def test_endpoint_enforces_admin_and_revision_before_snap(self):
  state,body=self.setup_gap();api=test_accounts.AccountsAPI();api.setUp()
  api.store.state.update(state)
  self.assertEqual(api.call('/api/schedule/travel','POST',body,token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule/travel','POST',body,match=False)[0],409)
  status,payload,_=api.call('/api/schedule/travel','POST',body)
  self.assertEqual(status,200);self.assertTrue(any(e['linked'] and e['leftId']==body['upperId'] for e in payload['connections']))

 def test_block_link_control_can_reach_edges_outside_visible_time_range(self):
  state,body=self.setup_gap(above='fixed')
  result=schedule.save_travel(state,{'date':self.date,'action':'link_block','blockId':self.first['id'],'linked':False},self.user)
  edges=[e for e in schedule_links.connections(result,self.date) if self.first['id'] in (e['leftId'],e['rightId'])]
  self.assertTrue(edges);self.assertTrue(all(not e['linked'] for e in edges))
  result=schedule.save_travel(result,{'date':self.date,'action':'link_block','blockId':self.first['id'],'linked':True},self.user)
  self.assertTrue(all(e['linked'] for e in schedule_links.connections(result,self.date) if self.first['id'] in (e['leftId'],e['rightId'])))
 def test_missing_block_link_control_is_rejected(self):
  state,body=self.setup_gap()
  with self.assertRaises(Problem):schedule.save_travel(state,{'date':self.date,'action':'link_block','blockId':'missing','linked':False},self.user)
