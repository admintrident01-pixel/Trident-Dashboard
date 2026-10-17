import copy,unittest
import schedule
from core import Problem
class DurationTests(unittest.TestCase):
 def setUp(self):
  self.user={'email':'admin@example.nz'};self.base={'staffSettings':{'technicians':[{'name':'Rick','rego':''}]},'quotes':{'kept':{'notes':'Existing online record'}},'stock':{'products':{'kept':{'code':'Preserved stock'}}},'officeFiles':{'kept':{'name':'Preserved SOP'}}}
  self.booking={'date':'2027-02-01','technician':'Rick','start':'09:00','duration':60,'client':'Duration test','address':'1 Test Road','type':'Repair','timing':'fixed','bookingStatus':'confirmed','notes':''}
 def test_fixed_and_booked_duration_changes_preserve_start_and_other_records(self):
  state,appointment=schedule.save(self.base,self.booking,self.user)
  for duration in [90,30]:
   result,resized=schedule.save(state,{**appointment,'duration':duration},self.user)
   self.assertEqual(resized['start'],'09:00');self.assertEqual(resized['duration'],duration);self.assertEqual(result['quotes'],state['quotes'])
   self.assertEqual(result['stock'],state['stock']);self.assertEqual(result['officeFiles'],state['officeFiles'])
   self.assertEqual(resized['timing'],'fixed');self.assertEqual(resized['bookingStatus'],'confirmed')
 def test_fixed_or_booked_start_still_cannot_be_moved(self):
  state,a=schedule.save(self.base,self.booking,self.user)
  with self.assertRaises(Problem):schedule.save(state,{**a,'start':'10:00'},self.user)
 def test_end_time_preference_is_saved_and_retained_on_later_edits(self):
  state,a=schedule.save(self.base,{**self.booking,'timeBasis':'end'},self.user)
  self.assertEqual(a['timeBasis'],'end')
  result,b=schedule.save(state,{**a,'notes':'Updated notes'},self.user)
  self.assertEqual(b['timeBasis'],'end');self.assertEqual(result['stock'],self.base['stock'])
  with self.assertRaises(Problem):schedule.save(state,{**a,'timeBasis':'invalid'},self.user)
 def test_resizing_still_checks_overlaps_and_retains_original_on_failure(self):
  state,a=schedule.save(self.base,self.booking,self.user)
  state,_=schedule.save(state,{**self.booking,'start':'10:00','client':'Next booking'},self.user);before=copy.deepcopy(state)
  with self.assertRaises(Problem):schedule.save(state,{**a,'duration':90},self.user)
  self.assertEqual(state,before)
