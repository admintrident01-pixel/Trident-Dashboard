import copy,unittest
from unittest.mock import patch
import schedule,schedule_links,schedule_routes
from core import Problem

class SelectionTests(unittest.TestCase):
 def setUp(self):
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
  self.routes=patch.object(schedule_routes,'estimate',return_value={'duration':15,'seconds':500});self.routes.start();self.addCleanup(self.routes.stop)
  self.user={'email':'admin@example.nz'};self.date='2027-02-01'
  state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]}}
  base={'date':self.date,'technician':'Scott','start':'09:00','duration':30,'client':'A','address':'1 Road','type':'Repair','timing':'flexible','notes':''}
  state,self.a=schedule.save(state,base,self.user)
  self.state,self.b=schedule.save(state,{**base,'start':'10:30','client':'B'},self.user)
 def move(self,state,ids,delta):return schedule.save_travel(state,{'date':self.date,'action':'move_selection','ids':ids,'delta':delta},self.user)
 def test_atomic_move_and_travel(self):
  before=copy.deepcopy(self.state);result=self.move(self.state,[self.a['id'],self.b['id']],30)
  self.assertEqual(result['appointments'][self.a['id']]['start'],'09:30');self.assertEqual(result['appointments'][self.b['id']]['start'],'11:00');self.assertEqual(self.state,before)
  old={t['id']:t for t in schedule.travel_blocks(self.state,self.date)}
  for t in schedule.travel_blocks(result,self.date):self.assertEqual(schedule.minutes(t['start'])-schedule.minutes(old[t['id']]['start']),30)
 def test_fixed_rejects_everything(self):
  self.state['appointments'][self.b['id']]['timing']='fixed';before=copy.deepcopy(self.state)
  with self.assertRaisesRegex(Problem,'fixed'):self.move(self.state,[self.a['id'],self.b['id']],15)
  self.assertEqual(self.state,before)
 def test_collision_and_day_boundary(self):
  with self.assertRaisesRegex(Problem,'overlap'):self.move(self.state,[self.a['id']],90)
  with self.assertRaisesRegex(Problem,'day'):self.move(self.state,[self.a['id']],-600)
 def test_invalid_or_stale_selection(self):
  for ids,delta in [([],15),(['missing'],15),([self.a['id']],1),([self.a['id']],True)]:
   with self.assertRaises(Problem):self.move(self.state,ids,delta)
 def test_unchecked_linked_fixed_neighbour_stays_put(self):
  self.state['appointments'][self.b['id']].update(start='09:30',timing='fixed');before=copy.deepcopy(self.state['appointments'][self.b['id']])
  result=self.move(self.state,[self.a['id']],-15)
  self.assertEqual(result['appointments'][self.b['id']],before)
  self.assertEqual(result['appointments'][self.a['id']]['start'],'08:45')
  self.assertFalse(result['scheduleLinks'][schedule_links.edge_id('Scott',self.a['id'],self.b['id'])])
 def test_lunch_selected_keeps_duration(self):
  lunch=next(b for b in schedule.lunch_blocks(self.state,self.date) if b['technician']=='Scott')
  result=self.move(self.state,[lunch['id']],30)
  self.assertEqual(result['appointments'][lunch['id']]['start'],'12:30');self.assertEqual(result['appointments'][lunch['id']]['duration'],30)

 def test_across_technicians_and_team_collision(self):
  self.state['appointments'][self.b['id']].update(technician='Bala',technicians=['Bala'])
  result=self.move(self.state,[self.a['id'],self.b['id']],15)
  self.assertEqual(result['appointments'][self.a['id']]['start'],'09:15')
  self.assertEqual(result['appointments'][self.b['id']]['start'],'10:45')
  self.assertEqual(result['appointments'][self.b['id']]['technicians'],['Bala'])
  self.state['appointments'][self.a['id']]['technicians']=['Scott','Bala']
  with self.assertRaisesRegex(Problem,'overlap'):self.move(self.state,[self.a['id']],90)
 def test_detached_travel_moves_by_explicit_start(self):
  travel=schedule.travel_blocks(self.state,self.date)[0]
  self.state.setdefault('travelBlocks',{})[travel['id']]={'date':self.date,'duration':15,'start':travel['start'],'locked':False,'linked':False,'version':1}
  result=self.move(self.state,[travel['id']],-15)
  self.assertEqual(schedule.minutes(result['travelBlocks'][travel['id']]['start']),schedule.minutes(travel['start'])-15)

 def test_checked_booking_transfers_without_moving_neighbour(self):
  self.state['appointments'][self.b['id']].update(start='09:30',timing='fixed');before=copy.deepcopy(self.state['appointments'][self.b['id']])
  result=schedule.save_travel(self.state,{'date':self.date,'action':'move_selection','ids':[self.a['id']],'delta':0,'fromTechnician':'Scott','toTechnician':'Bala'},self.user)
  self.assertEqual(result['appointments'][self.a['id']]['technicians'],['Bala'])
  self.assertEqual(result['appointments'][self.a['id']]['start'],'09:00');self.assertEqual(result['appointments'][self.b['id']],before)
  own=[b for b in schedule.travel_blocks(result,self.date) if b['anchorId']==self.a['id']]
  self.assertTrue(own);self.assertTrue(all(b['technician']=='Bala' for b in own))
 def test_transfer_collision_rejects_whole_move(self):
  self.state['appointments'][self.b['id']].update(start='09:00',technician='Bala',technicians=['Bala']);before=copy.deepcopy(self.state)
  with self.assertRaisesRegex(Problem,'overlap'):schedule.save_travel(self.state,{'date':self.date,'action':'move_selection','ids':[self.a['id']],'delta':0,'fromTechnician':'Scott','toTechnician':'Bala'},self.user)
  self.assertEqual(self.state,before)
 def test_selected_travel_can_transfer_without_moving_its_booking(self):
  travel=schedule.travel_blocks(self.state,self.date)[0]
  result=schedule.save_travel(self.state,{'date':self.date,'action':'move_selection','ids':[travel['id']],'delta':0,'fromTechnician':'Scott','toTechnician':'Bala'},self.user)
  moved=next(b for b in schedule.travel_blocks(result,self.date) if b['id']==travel['id'])
  self.assertEqual(moved['technician'],'Bala');self.assertFalse(moved['linked']);self.assertEqual(result['appointments'],self.state['appointments'])
 def test_invalid_transfer_technician(self):
  with self.assertRaisesRegex(Problem,'Settings'):schedule.save_travel(self.state,{'date':self.date,'action':'move_selection','ids':[self.a['id']],'delta':0,'fromTechnician':'Scott','toTechnician':'Missing'},self.user)

 def test_selected_detached_travel_follows_transferred_selected_anchor(self):
  travel=schedule.travel_blocks(self.state,self.date)[0]
  self.state.setdefault('travelBlocks',{})[travel['id']]={'date':self.date,'duration':15,'start':travel['start'],'locked':False,'linked':False,'version':1}
  result=schedule.save_travel(self.state,{'date':self.date,'action':'move_selection','ids':[self.a['id'],travel['id']],'delta':0,'fromTechnician':'Scott','toTechnician':'Bala'},self.user)
  moved=next(b for b in schedule.travel_blocks(result,self.date) if b['anchorId']==self.a['id'] and b['side']=='before')
  self.assertEqual(moved['technician'],'Bala');self.assertFalse(moved['locked']);self.assertFalse(moved['linked'])
