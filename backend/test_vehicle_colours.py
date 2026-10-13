import copy,unittest
import vehicles,test_accounts
from core import Problem
class VehicleColoursTests(unittest.TestCase):
 def check(self):return {'vehicleId':'VEH-06','registration':'RWB869','driver':'Andrew','checkDate':'2026-10-09','overall':'Issues found','checklist':['Pass']*9+['Fail']+['Pass']*12,'comments':'Stone chip; glass repair booked','serviceDue':'2027-06-09','serviceDueKm':15000,'wofExpiry':'2029-06-09','alignmentDue':'','alignmentDueKm':'','regoExpiry':'2027-06-09','odometer':6223,'rucCurrent':21007,'signature':'Andrew Thomas'}
 def test_alignment_is_optional_and_followup_notes_required(self):
  check=self.check();check.update(followUpNeeded=True,followUpNotes='Contact glass repairer')
  state,saved=vehicles.save_check({},check)
  self.assertEqual(saved['alignmentDue'],'');self.assertIsNone(saved['alignmentDueKm']);self.assertTrue(saved['followUpNeeded']);self.assertEqual(saved['followUpNotes'],'Contact glass repairer')
  for value in ['', '   ']:
   with self.assertRaises(Problem):vehicles.save_check({}, {**check,'followUpNotes':value})
  for value in ['yes',1,'']:
   with self.assertRaises(Problem):vehicles.save_check({}, {**check,'followUpNeeded':value})
  saved.update(followUpNeeded=False,followUpNotes='Old note')
  _,edited=vehicles.save_check(state,saved)
  self.assertFalse(edited['followUpNeeded']);self.assertEqual(edited['followUpNotes'],'')
 def test_legacy_record_does_not_claim_no_followup(self):
  _,saved=vehicles.save_check({},self.check());self.assertIsNone(saved['followUpNeeded']);self.assertEqual(saved['followUpNotes'],'')
 def test_settings_validate_and_preserve_checks_and_order(self):
  before={'vehicleChecks':{'old':{'notes':'Keep me'}}};order=[v['id'] for v in vehicles.fleet(before)];config=vehicles.colour_settings(before)
  config['checkDays']['red']=3;config['colours']['orange']='#eaa366';config['rucKm']['green']=5000
  state=vehicles.save_order(before,{'order':order,'colourSettings':config})
  self.assertEqual(state['vehicleChecks'],before['vehicleChecks']);self.assertEqual(vehicles.colour_settings(state),config);self.assertNotIn('vehicleColourSettings',before)
  bad=copy.deepcopy(config);bad['km']['red']=4000
  with self.assertRaises(Problem):vehicles.save_order(before,{'order':order,'colourSettings':bad})
  for group,key,value in [('colours','red','red'),('followUp','yes','blue'),('checkDays','red',True),('km','green',-1)]:
   bad=copy.deepcopy(config);bad[group][key]=value
   with self.assertRaises(Problem):vehicles.clean_colours(bad)
 def test_settings_and_followup_api_persistence(self):
  api=test_accounts.AccountsAPI();api.setUp();config=vehicles.colour_settings({});config['followUp']['yes']='red';order=[v['id'] for v in vehicles.fleet(api.store.state)]
  self.assertEqual(api.call('/api/vehicle-order','POST',{'order':order,'colourSettings':config})[0],200)
  self.assertEqual(api.call('/api/vehicles')[1]['colourSettings'],config)
  check={**self.check(),'followUpNeeded':True,'followUpNotes':'Book windscreen repair'}
  self.assertEqual(api.call('/api/vehicle-checks','POST',check)[0],200)
  saved=api.call('/api/vehicles')[1]['checks'][0];self.assertEqual(saved['followUpNotes'],'Book windscreen repair');self.assertIsNone(saved['alignmentDueKm'])
