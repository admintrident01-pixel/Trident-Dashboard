import copy,unittest
from unittest.mock import patch
import schedule,schedule_notes,test_accounts
from core import Problem

class RecurringNotes(unittest.TestCase):
 def setUp(self):
  self.state={'staffSettings':{'technicians':[{'name':'Sample technician','rego':''}]},'quotes':{'keep':1},'stock':{'keep':2},'officeFiles':{'keep':3}}
  self.user={'email':'admin@example.nz'}
  self.data={'action':'create','title':'Paperwork','notes':'Complete notes','technicians':['Sample technician'],'weekday':0,'intervalWeeks':2,'start':'15:30','finish':'16:00','fromDate':'2026-10-21','toDate':''}
 def create(self,**changes):return schedule_notes.save(self.state,{**self.data,**changes},self.user)
 def test_interval_range_and_stable_per_staff_blocks(self):
  state=self.create();rule=next(iter(state['scheduleNoteSeries'].values()))
  self.assertFalse(schedule_notes.blocks(state,'2026-10-21'))
  self.assertTrue(schedule_notes.blocks(state,'2026-10-26'))
  self.assertFalse(schedule_notes.blocks(state,'2026-11-02'))
  a=schedule_notes.blocks(state,'2026-11-09')[0]
  self.assertEqual(a,schedule_notes.blocks(state,'2026-11-09')[0]);self.assertEqual(a['duration'],30)
  self.assertEqual(rule['history'][0]['by'],self.user['email'])
  bounded=self.create(toDate='2026-10-30');self.assertFalse(schedule_notes.blocks(bounded,'2026-11-09'))
 def test_validation_and_atomicity(self):
  before=copy.deepcopy(self.state)
  for changes in ({'intervalWeeks':0},{'intervalWeeks':True},{'weekday':7},{'technicians':[]},{'technicians':['Unknown']},{'start':'15:31'},{'finish':'15:00'},{'toDate':'2026-10-20'},{'title':''}):
   with self.subTest(changes=changes),self.assertRaises(Problem):self.create(**changes)
  self.assertEqual(self.state,before)
 def test_delete_restore_and_preserve_register(self):
  state=self.create();rule=next(iter(state['scheduleNoteSeries'].values()))
  deleted=schedule_notes.save(state,{'action':'delete','id':rule['id'],'version':1},self.user)
  self.assertFalse(schedule_notes.blocks(deleted,'2026-10-26'))
  restored=schedule_notes.save(deleted,{'action':'restore','id':rule['id'],'version':2},self.user)
  self.assertTrue(schedule_notes.blocks(restored,'2026-10-26'))
  self.assertEqual(len(restored['scheduleNoteSeries'][rule['id']]['history']),3)
  for key in ('quotes','stock','officeFiles'):self.assertEqual(restored[key],self.state[key])
  with self.assertRaises(Problem):schedule_notes.save(restored,{'action':'delete','id':rule['id'],'version':1},self.user)
 def test_series_phases_and_existing_booking_conflicts(self):
  self.state=self.create()
  with self.assertRaises(Problem):self.create(intervalWeeks=3)
  self.create(fromDate='2026-11-02') # alternating weeks do not conflict
  self.state['appointments']={'a':{'id':'a','date':'2026-11-02','start':'15:30','duration':30,'technician':'Sample technician','client':'Existing client'}}
  with self.assertRaises(Problem):self.create(fromDate='2026-11-02')
 def test_reserved_time_blocks_booking_resize_and_selection_delete(self):
  state=self.create();base={'date':'2026-10-26','technician':'Sample technician','start':'15:30','duration':30,'client':'Visit','address':'1 Sample Road','type':'Other','timing':'flexible'}
  with self.assertRaises(Problem):schedule.save(state,base,self.user)
  state,booking=schedule.save(state,{**base,'start':'15:00'},self.user)
  with patch.object(schedule,'travel_blocks',return_value=[]):
   with self.assertRaises(Problem):schedule.save(state,{**booking,'action':'resize','edge':'end','duration':60},self.user)
   note=schedule_notes.blocks(state,base['date'])[0]
   with self.assertRaises(Problem):schedule.save_travel(state,{'date':base['date'],'action':'delete_selection','ids':[note['id']]},self.user)
 def test_admin_api_permissions_and_revision(self):
  api=test_accounts.AccountsAPI();api.setUp();data={**self.data,'technicians':['Scott Yearbury']}
  self.assertEqual(api.call('/api/schedule-notes',token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule-notes','POST',data,token='tech')[0],403)
  self.assertEqual(api.call('/api/schedule-notes','POST',data,match=False)[0],409)
  status,result,_=api.call('/api/schedule-notes','POST',data);self.assertEqual(status,200);self.assertEqual(len(result['series']),1)
  self.assertEqual(schedule.read(api.store.state,'2026-10-26')['noteBlocks'][0]['client'],'Paperwork')
 def test_type_defaults_validation_and_old_client_preservation(self):
  defaults={'Other':{'colour':'#ab12cd','duration':45,'timing':'fixed','bookingStatus':'confirmed'}}
  state=schedule.save_settings(self.state,{'appointmentTypes':['Other'],'typeDefaults':defaults})
  self.assertEqual(schedule.settings(state)['typeDefaults'],defaults)
  self.assertEqual(schedule.save_settings(state,{'appointmentTypes':['Other']})['scheduleSettings']['typeDefaults'],defaults)
  for invalid in ({'colour':'red'},{'duration':31},{'timing':'wrong'},{'bookingStatus':'wrong'}):
   with self.assertRaises(Problem):schedule.save_settings(state,{'appointmentTypes':['Other'],'typeDefaults':{'Other':{**defaults['Other'],**invalid}}})
