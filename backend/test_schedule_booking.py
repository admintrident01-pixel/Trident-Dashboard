import copy,unittest
from unittest.mock import patch
import schedule,schedule_booking as controls,schedule_links,schedule_history,schedule_routes
from core import Problem

class BookingControls(unittest.TestCase):
 def setUp(self):
  self.user={'email':'admin@example.nz'}
  self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''},{'name':'Blair','rego':''}]},'quotes':{'keep':{'value':123}}}
  self.row={'id':'legacy','date':'2026-10-21','technician':'Alex','technicians':['Alex','Blair'],'start':'11:00','duration':45,'client':'Legacy client','address':'1 Road','type':'Repair','notes':'Retain notes','version':3,'createdAt':'original','timing':'flexible','bookingStatus':'high-priority'}
 def test_read_maps_without_migrating_records_or_history(self):
  self.state['appointments']={'legacy':self.row};before=copy.deepcopy(self.state)
  with patch.object(schedule_routes,'configuration',return_value={'key':'','depot':'Depot'}):
   result=schedule.read(self.state,self.row['date'])['appointments'][0]
  self.assertEqual((result['bookingStatus'],result['urgency'],result['timing']),('action-needed','high','flexible'))
  self.assertEqual(self.state,before)
  for key in ('id','technicians','start','duration','notes','version','createdAt'):self.assertEqual(result[key],self.row[key])
 def test_approved_mapping_and_specific_conflict_decision(self):
  for timing,status,expected in [('fixed','confirmed','confirmed'),('fixed','action-needed','confirmed'),('fixed','high-priority','confirmed'),('flexible','confirmed','confirmed'),('flexible','option','option'),('flexible','high-priority','action-needed')]:
   self.assertEqual(controls.status({**self.row,'timing':timing,'bookingStatus':status}),expected)
  row={**self.row,'id':next(iter(controls.LEGACY_NOT_BOOKED)),'timing':'fixed','bookingStatus':'option'}
  self.assertEqual(controls.controls(row)['bookingStatus'],'action-needed');schedule_links.require_movable(row)
  with self.assertRaisesRegex(Problem,'both Fixed and Optional'):controls.controls({**row,'id':'another-conflict'})
 def test_new_defaults_and_independent_status_urgency_survive_save(self):
  data={k:v for k,v in self.row.items() if k not in ('id','version','createdAt','bookingStatus','timing')}
  state,row=schedule.save(self.state,data,self.user)
  self.assertEqual((row['bookingStatus'],row['urgency']),('action-needed','low'))
  for status,urgency in [('option','high'),('confirmed','high'),('confirmed','low'),('action-needed','high')]:
   state,row=schedule.save(state,{**row,'bookingStatus':status,'urgency':urgency},self.user)
   self.assertEqual((row['bookingStatus'],row['urgency']),(status,urgency));self.assertEqual(row['technicians'],['Alex','Blair'])
   self.assertEqual(row['timing'],'fixed' if status=='confirmed' else 'flexible')
  for bad in ('urgent','',None):
   with self.assertRaises(Problem):schedule.save(state,{**row,'urgency':bad},self.user)
 def test_booked_cannot_relocate_but_can_resize_and_unbook_then_move(self):
  state,row=schedule.save(self.state,{k:v for k,v in self.row.items() if k not in ('id','version','createdAt')},self.user)
  state,row=schedule.save(state,{**row,'bookingStatus':'confirmed'},self.user)
  with self.assertRaisesRegex(Problem,'Unbook'):schedule.save(state,{**row,'start':'12:00'},self.user)
  state,row=schedule.save(state,{**row,'action':'resize','edge':'end','duration':60},self.user)
  self.assertEqual((row['bookingStatus'],row['urgency']),('confirmed','high'))
  state,row=schedule.save(state,{**row,'bookingStatus':'action-needed'},self.user)
  after,moved=schedule.save(state,{**row,'start':'12:00'},self.user)
  after=schedule_history.record(state,after,self.user['email'],row['date'],'Move')
  restored=schedule_history.apply(after,self.user['email'],row['date'],'undo')
  for key in ('id','date','technicians','start','duration','client','address','notes','bookingStatus','urgency','createdAt'):self.assertEqual(restored['appointments'][row['id']][key],row[key])
  self.assertGreater(restored['appointments'][row['id']]['version'],row['version']);self.assertEqual(moved['urgency'],'high')
