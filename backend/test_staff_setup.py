import copy, unittest
import accounts, staff_setup, schedule, test_accounts
from core import Problem

class StaffSetupTests(unittest.TestCase):
    def setUp(self):
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':'ABC123'}]},'quotes':{'1753':{'kept':True}}}
        self.actor={'email':accounts.FIRST_ADMIN}
        self.staff={'name':'Office Test','staffType':'office','hasVehicle':False,'rego':'IGNORED'}
        self.account={'email':'office@example.nz','name':'Office Test','technician':'Office Test','role':'tech','active':True}
    def test_staff_and_sign_in_saved_together(self):
        result=staff_setup.save(self.state,{'staff':self.staff,'account':self.account},self.actor)
        self.assertEqual(result['staffSettings']['technicians'][-1]['rego'],'')
        self.assertEqual(result['users']['office@example.nz']['technician'],'Office Test')
        self.assertFalse(result['users']['office@example.nz']['verified'])
        self.assertEqual(schedule.read(result,'2027-02-01')['technicians'],['Scott','Office Test'])
        self.assertEqual(result['quotes'],self.state['quotes'])
        self.assertNotIn('users',self.state)
    def test_invalid_account_does_not_partially_change_staff(self):
        before=copy.deepcopy(self.state)
        with self.assertRaises(Problem):staff_setup.save(self.state,{'staff':self.staff,'account':{**self.account,'email':'bad'}},self.actor)
        self.assertEqual(self.state,before)
    def test_staff_only_and_unchanged_account_keep_session(self):
        result=staff_setup.save(self.state,{'staff':self.staff,'account':None},self.actor)
        self.assertNotIn('office@example.nz',accounts.users(result))
        result=staff_setup.save(self.state,{'staff':self.staff,'account':self.account},self.actor)
        result['sessions']={'keep':{'email':self.account['email'],'expires':9999999999}}
        updated=staff_setup.save(result,{'originalName':self.staff['name'],'originalEmail':self.account['email'],'staff':{**self.staff,'hasVehicle':True,'rego':'XYZ789'},'account':self.account},self.actor)
        self.assertIn('keep',updated['sessions'])
        self.assertEqual(updated['staffSettings']['technicians'][-1]['rego'],'XYZ789')
    def test_existing_email_cannot_be_overwritten_and_last_admin_protected(self):
        with self.assertRaises(Problem):staff_setup.save(self.state,{'staff':self.staff,'account':{**self.account,'email':accounts.FIRST_ADMIN}},self.actor)
        with self.assertRaises(Problem):staff_setup.save(self.state,{'originalEmail':accounts.FIRST_ADMIN,'account':{**accounts.users(self.state)[accounts.FIRST_ADMIN],'active':False}},self.actor)
    def test_api_admin_only_and_revision_conflict(self):
        api=test_accounts.AccountsAPI();api.setUp()
        self.assertEqual(api.call('/api/staff-setup',token='tech')[0],403)
        self.assertEqual(api.call('/api/staff-setup','POST',{'staff':self.staff},token='tech')[0],403)
        self.assertEqual(api.call('/api/staff-setup','POST',{'staff':self.staff},match=False)[0],409)
        self.assertEqual(api.call('/api/staff-setup','POST',{'staff':self.staff,'account':self.account})[0],200)
        self.assertEqual(api.call('/api/staff-setup')[0],200)

class VehicleAllocationTests(unittest.TestCase):
    def setUp(self):
        self.actor={'email':accounts.FIRST_ADMIN}
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':'AAA111','hasVehicle':True},{'name':'Andrew','rego':'BBB222','hasVehicle':True}]},'vehicles':[{'id':'VEH-01','registration':'AAA111','makeModel':'Toyota','driver':'Scott','active':True},{'id':'VEH-02','registration':'BBB222','makeModel':'Toyota','driver':'Andrew','active':True}],'vehicleChecks':{'old':{'vehicleId':'VEH-02','driver':'Andrew'}}}
    def test_allocate_and_release_vehicle_without_changing_history(self):
        before=copy.deepcopy(self.state)
        result=staff_setup.save(self.state,{'originalName':'Scott','staff':{'name':'Scott','hasVehicle':True,'rego':'BBB222','vehicleId':'VEH-02'}},self.actor)
        self.assertEqual(result['vehicles'][0]['driver'],'');self.assertEqual(result['vehicles'][1]['driver'],'Scott')
        self.assertEqual(result['staffSettings']['technicians'][0]['rego'],'BBB222');self.assertFalse(result['staffSettings']['technicians'][1]['hasVehicle'])
        self.assertEqual(result['vehicleChecks'],self.state['vehicleChecks']);self.assertEqual(self.state,before)
        result=staff_setup.save(result,{'originalName':'Scott','staff':{'name':'Scott','hasVehicle':False,'rego':'','vehicleId':''}},self.actor)
        self.assertEqual(result['vehicles'][1]['driver'],'');self.assertFalse(result['staffSettings']['technicians'][0]['hasVehicle'])
    def test_invalid_vehicle_is_atomic(self):
        for target in ['', 'missing']:
            before=copy.deepcopy(self.state)
            with self.assertRaises(Problem):staff_setup.save(self.state,{'originalName':'Scott','staff':{'name':'Scott','hasVehicle':True,'vehicleId':target}},self.actor)
            self.assertEqual(self.state,before)
    def test_fleet_registration_and_removal_sync_staff(self):
        import vehicles
        rows=copy.deepcopy(self.state['vehicles']);rows[0]['registration']='NEW123'
        result=vehicles.save_fleet(self.state,{'vehicles':rows})
        self.assertEqual(result['staffSettings']['technicians'][0]['rego'],'NEW123')
        result=vehicles.save_fleet(result,{'vehicles':rows[1:]})
        self.assertFalse(result['staffSettings']['technicians'][0]['hasVehicle']);self.assertEqual(result['staffSettings']['technicians'][0]['rego'],'')
        self.assertEqual(result['vehicleChecks'],self.state['vehicleChecks'])

if __name__=='__main__': unittest.main()
