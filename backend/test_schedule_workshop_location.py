import copy,unittest
from unittest.mock import patch
import schedule,schedule_routes,schedule_history
from core import Problem

class WorkshopLocation(unittest.TestCase):
 def setUp(self):
  self.actor={'email':'admin@example.invalid'};self.date='2026-11-09'
  self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''},{'name':'Blair','rego':''}]},'scheduleSettings':{'workshopAddress':'255 Example Workshop Road'}}
  self.booking={'date':self.date,'technicians':['Alex','Blair'],'start':'10:00','duration':60,'client':'Example workshop job','address':'Old client address','type':'Repair','bookingStatus':'action-needed','bookingControlsVersion':1,'workshopLocation':True}
  self.config=patch.object(schedule_routes,'configuration',return_value={'key':'test-only','depot':'Depot'});self.config.start();self.addCleanup(self.config.stop)
 def save(self,**changes):return schedule.save(self.state,{**self.booking,**changes},self.actor)
 def test_workshop_uses_stored_settings_and_preserves_team_and_booking(self):
  before=copy.deepcopy(self.state);state,booking=self.save()
  self.assertEqual(booking['address'],'255 Example Workshop Road')
  self.assertTrue(booking['workshopLocation']);self.assertFalse(booking['includeWorkshopTravel'])
  self.assertEqual(booking['technicians'],['Alex','Blair']);self.assertEqual(booking['duration'],60)
  self.assertEqual(self.state,before)
  state,edited=schedule.save(state,{**booking,'notes':'Changed notes'},self.actor)
  self.assertEqual(edited['id'],booking['id']);self.assertTrue(edited['workshopLocation'])
  config=schedule.settings(state)
  changed=schedule.save_settings(state,{**config,'workshopAddress':'Updated workshop address'})
  self.assertEqual(schedule.settings(changed)['workshopAddress'],'Updated workshop address')
 def test_default_hides_saved_travel_without_deleting_it_and_never_calls_google(self):
  state,booking=self.save();key=schedule.travel_id(self.date,'Alex',booking['id'],'before')
  state['travelBlocks']={key:{'duration':45,'locked':True,'version':4}}
  before=copy.deepcopy(state)
  with patch.object(schedule_routes,'_provider',side_effect=AssertionError('No paid calls')):
   self.assertEqual(schedule.travel_blocks(state,self.date),[])
   self.assertEqual(schedule.read(state,self.date,fast=True)['travelBlocks'],[])
   self.assertEqual(schedule.read(state,self.date)['travelBlocks'],[])
  self.assertEqual(state,before)
 def test_neighbouring_blocks_do_not_recreate_travel_to_or_from_workshop(self):
  state,workshop=self.save(technicians=['Alex'])
  for start in ('08:00','12:00'):
   state,_=schedule.save(state,{**self.booking,'technicians':['Alex'],'workshopLocation':False,'start':start,'address':start+' client road'},self.actor)
  candidates=schedule.travel_candidates(state,self.date)
  permitted=[c for c in candidates if schedule.travel_allowed(state,c)]
  self.assertEqual(len(permitted),2)
  self.assertTrue(all(c['anchorId']!=workshop['id'] for c in permitted))
  self.assertEqual([c['side'] for c in permitted],['before','after'])
 def test_include_travel_and_manual_insertion_are_explicit_and_need_no_google(self):
  state,booking=self.save(technicians=['Alex'],includeWorkshopTravel=True)
  with patch.object(schedule_routes,'_provider',side_effect=AssertionError('Explicit calculation only')):
   blocks=schedule.travel_blocks(state,self.date)
  self.assertEqual(len(blocks),2);self.assertTrue(all(b['duration']==15 for b in blocks))
  state,booking=self.save(technicians=['Alex'])
  state=schedule.save_travel(state,{'date':self.date,'technician':'Alex','anchorId':booking['id'],'side':'before','action':'insert','duration':30},self.actor)
  blocks=schedule.travel_blocks(state,self.date)
  self.assertEqual(len(blocks),1);self.assertEqual(blocks[0]['duration'],30)
 def test_old_booking_updates_do_not_lose_workshop_flags_and_disable_uses_client_address(self):
  state,booking=self.save(includeWorkshopTravel=True)
  legacy={k:v for k,v in booking.items() if k not in ('workshopLocation','includeWorkshopTravel')}
  state,updated=schedule.save(state,{**legacy,'notes':'Preserved'},self.actor)
  self.assertTrue(updated['workshopLocation']);self.assertTrue(updated['includeWorkshopTravel'])
  state,updated=schedule.save(state,{**updated,'workshopLocation':False,'address':'12 Client Road'},self.actor)
  self.assertEqual(updated['address'],'12 Client Road');self.assertFalse(updated['includeWorkshopTravel'])
 def test_undo_restores_location_and_travel_policy(self):
  before,booking=self.save(workshopLocation=False)
  after,updated=schedule.save(before,{**booking,'workshopLocation':True},self.actor)
  recorded=schedule_history.record(before,after,self.actor['email'],self.date,'Workshop location')
  restored=schedule_history.apply(recorded,self.actor['email'],self.date,'undo')['appointments'][booking['id']]
  self.assertEqual(restored['address'],'Old client address');self.assertFalse(restored['workshopLocation'])
 def test_invalid_checkbox_values_are_rejected(self):
  for key in ('workshopLocation','includeWorkshopTravel'):
   for value in ('false',1,None):
    with self.assertRaises(Problem):self.save(**{key:value})
 def test_mobility_job_type_defaults_do_not_rewrite_saved_bookings_or_custom_settings(self):
  state,booking=self.save(workshopLocation=False,type='Existing saved type')
  before=copy.deepcopy(state)
  self.assertIn('RP - Repair',schedule.settings(state)['appointmentTypes'])
  self.assertIn('Notes',schedule.settings(state)['appointmentTypes'])
  self.assertEqual(state,before);self.assertEqual(state['appointments'][booking['id']]['type'],'Existing saved type')
  config=schedule.settings(state)
  saved=schedule.save_settings(state,{**config,'appointmentTypes':['Custom','Notes']})
  self.assertEqual(schedule.settings(saved)['appointmentTypes'],['Custom','Notes','Unspecified'])

if __name__=='__main__':unittest.main()
