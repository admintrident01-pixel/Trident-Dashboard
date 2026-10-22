import copy,unittest
import schedule
from core import Problem

class ScheduleClientSearchTests(unittest.TestCase):
 def setUp(self):
  self.state={'scheduleSettings':{'appointmentTypes':['Repair','Visit'],'typeDefaults':{'Repair':{'colour':'#123456','duration':30,'timing':'fixed','bookingStatus':'option'}},'customSetting':{'keep':True}},'staffSettings':{'technicians':[{'name':'Scott','rego':''}]}}
 def test_unspecified_is_additive_and_read_does_not_mutate_existing_settings(self):
  original=copy.deepcopy(self.state);settings=schedule.settings(self.state)
  self.assertEqual(settings['appointmentTypes'],['Repair','Visit','Unspecified']);self.assertEqual(self.state,original)
  self.assertEqual(settings['typeDefaults'],original['scheduleSettings']['typeDefaults'])
  updated=schedule.save_settings(self.state,{'appointmentTypes':settings['appointmentTypes']})
  self.assertEqual(updated['scheduleSettings']['customSetting'],{'keep':True})
  self.assertEqual(updated['scheduleSettings']['typeDefaults'],original['scheduleSettings']['typeDefaults'])
  self.assertEqual(schedule.settings({'scheduleSettings':{'appointmentTypes':['unspecified','Repair']}})['appointmentTypes'],['unspecified','Repair'])
 def test_new_booking_missing_type_defaults_to_unspecified_existing_type_survives(self):
  payload={'date':'2027-02-01','technician':'Scott','start':'09:00','duration':60,'client':'Client','address':'1 Road','timing':'flexible'}
  state,new=schedule.save(self.state,payload,{'email':'admin@example.nz'});self.assertEqual(new['type'],'Unspecified')
  state,old=schedule.save(state,{**new,'type':'Legacy type'},{'email':'admin@example.nz'})
  edit={**old,'notes':'Keep type'};del edit['type']
  _,saved=schedule.save(state,edit,{'email':'admin@example.nz'});self.assertEqual(saved['type'],'Legacy type')
 def test_template_save_preserve_disable_and_validate(self):
  valid='https://clients.example.nz/search?name={client}&sort=name'
  state=schedule.save_settings(self.state,{'appointmentTypes':['Repair','Visit'],'clientSearchUrlTemplate':valid})
  self.assertEqual(schedule.read(state,'2027-02-01')['clientSearchUrlTemplate'],valid)
  state=schedule.save_settings(state,{'appointmentTypes':['Repair','Visit']});self.assertEqual(schedule.settings(state)['clientSearchUrlTemplate'],valid)
  state=schedule.save_settings(state,{'appointmentTypes':['Repair','Visit'],'clientSearchUrlTemplate':''});self.assertEqual(schedule.settings(state)['clientSearchUrlTemplate'],'')
  for value in ('javascript:alert({client})','data:text/html,{client}','https://user:secret@example.nz/{client}','https://{client}.example.nz/','https://example.nz/{secret}','https://example.nz/?q={client}\n',None,'https://example.nz/'+('x'*2000)+'{client}'):
   with self.subTest(value=value):
    with self.assertRaises(Problem):schedule.save_settings(self.state,{'appointmentTypes':['Repair'],'clientSearchUrlTemplate':value})
