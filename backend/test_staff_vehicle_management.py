import copy, unittest
import accounts, staff_setup, vehicles, test_accounts
from core import Problem
class StaffVehicleManagementTests(unittest.TestCase):
 def setUp(self):
  self.api=test_accounts.AccountsAPI();self.api.setUp()
  self.state={'staffSettings':{'technicians':[{'name':'Andrew','rego':'AAA111','hasVehicle':True},{'name':'Scott','rego':'BBB222','hasVehicle':True}]},'vehicles':[{'id':'VEH-01','registration':'AAA111','driver':'Andrew','active':True},{'id':'VEH-02','registration':'BBB222','driver':'Scott','active':True}],'vehicleChecks':{}}
  self.api.store.state.update(copy.deepcopy(self.state))
  for email,name in [('andrew@example.nz','Andrew'),('andrew.alt@example.nz','Andrew'),('scott@example.nz','Scott')]:self.api.store.state['users'][email]={'email':email,'name':name,'technician':name,'role':'tech','active':True,'verified':True}
 def test_inactive_vehicle_hidden_from_dashboard_and_reminders(self):
  body={'originalName':'Andrew','staff':{'name':'Andrew','hasVehicle':True,'vehicleId':'VEH-01','rego':'AAA111','vehicleActive':False}}
  self.assertEqual(self.api.call('/api/staff-setup','POST',body)[0],200)
  data=self.api.call('/api/vehicles')[1];self.assertEqual([v['id'] for v in data['activeVehicles']],['VEH-02']);self.assertEqual(len(data['vehicles']),2)
  reminders=self.api.call('/api/reminder-dashboard')[1]['items'];self.assertNotIn('VEH-01',[r.get('vehicleId') for r in reminders])
  body['staff']['vehicleActive']=True;self.assertEqual(self.api.call('/api/staff-setup','POST',body)[0],200)
  self.assertIn('VEH-01',[v['id'] for v in self.api.call('/api/vehicles')[1]['activeVehicles']])
 def test_create_vehicle_in_staff_setup_and_keep_signin_access(self):
  body={'originalName':'Andrew','originalEmail':'andrew@example.nz','staff':{'name':'Andrew','hasVehicle':True,'vehicleId':'new','rego':'NEW123','vehicleActive':True},'account':{'email':'andrew@example.nz','name':'Andrew','technician':'Andrew','role':'tech','active':True}}
  self.assertEqual(self.api.call('/api/staff-setup','POST',body)[0],200)
  allocated=next(v for v in vehicles.active_fleet(self.api.store.state) if v['driver']=='Andrew');self.assertEqual(allocated['registration'],'NEW123')
  self.assertEqual(self.api.store.state['users']['andrew@example.nz']['technician'],'Andrew')
 def test_unallocated_vehicle_stays_in_settings_only(self):
  self.assertEqual(self.api.call('/api/staff-setup','POST',{'action':'vehicle','vehicle':{'id':'new','registration':'SPARE1','staff':'','active':False}})[0],200)
  self.assertIn('SPARE1',[v['registration'] for v in staff_setup.read(self.api.store.state)['vehicles']]);self.assertNotIn('SPARE1',[v['registration'] for v in vehicles.active_fleet(self.api.store.state)])
  self.assertEqual(self.api.call('/api/staff-setup','POST',{'action':'vehicle','vehicle':{'id':'new','registration':'BAD123','staff':'','active':True}})[0],400)
 def test_reminder_uses_requested_email_linked_to_vehicle_staff(self):
  self.assertEqual(self.api.call('/api/send-reminder','POST',{'id':'vehicle:VEH-01','recipient':'andrew.alt@example.nz'})[0],200)
  mail=list(self.api.store.state['mailOutbox'].values())[-1];self.assertEqual(mail['to'],'andrew.alt@example.nz');self.assertEqual(mail['status'],'preview')
  before=copy.deepcopy(self.api.store.state['mailOutbox'])
  self.assertEqual(self.api.call('/api/send-reminder','POST',{'id':'vehicle:VEH-01','recipient':'scott@example.nz'})[0],400)
  self.assertEqual(self.api.store.state['mailOutbox'],before)
 def test_registration_edits_preserve_check_history(self):
  state=copy.deepcopy(self.state);state['vehicleChecks']={'old':{'vehicleId':'VEH-01','registration':'AAA111','driver':'Andrew'}}
  saved=staff_setup.save_vehicle(state,{'vehicle':{'id':'VEH-01','registration':'EDIT01','staff':'Andrew','active':False}})
  self.assertEqual(saved['vehicleChecks'],state['vehicleChecks']);self.assertEqual(saved['staffSettings']['technicians'][0]['rego'],'EDIT01');self.assertFalse(saved['vehicles'][0]['active'])
