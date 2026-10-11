import copy, unittest
import schedule, test_accounts
from core import Problem

class BookingActionsTests(unittest.TestCase):
    def setUp(self):
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]},'users':{}}
        for name in ('Scott','Bala'):
            address=name.lower()+'@example.nz'
            self.state['users'][address]={'email':address,'name':name,'technician':name,'role':'tech','active':True,'verified':True}
        self.booking={'date':'2027-02-01','technicians':['Scott','Bala'],'start':'09:00','duration':30,'client':'Client','address':'1 Road','type':'Repair','timing':'flexible','notes':'Bring equipment'}
        self.user={'email':'admin@example.nz'}
    def test_status_is_independent_of_timing_and_survives_move(self):
        state,a=schedule.save(self.state,{**self.booking,'bookingStatus':'confirmed'},self.user)
        self.assertEqual(a['bookingStatus'],'confirmed')
        update={**a,'start':'10:00'};update.pop('bookingStatus')
        state,a=schedule.save(state,update,self.user)
        self.assertEqual(a['bookingStatus'],'confirmed')
        self.assertEqual(a['timing'],'flexible')
        for status in ('option','action-needed'):
            state,a=schedule.save(state,{**a,'bookingStatus':status},self.user)
            self.assertEqual(a['bookingStatus'],status)
        with self.assertRaises(Problem):schedule.save(state,{**a,'bookingStatus':'invalid'},self.user)
    def test_quick_notes_settings_validation_and_preservation(self):
        state=schedule.save_settings(self.state,{'appointmentTypes':['Repair'],'quickNotes':['Contacted','Waiting']})
        self.assertEqual(schedule.read(state,self.booking['date'])['quickNotes'],['Contacted','Waiting'])
        state=schedule.save_settings(state,{'appointmentTypes':['Visit']})
        self.assertEqual(schedule.settings(state)['quickNotes'],['Contacted','Waiting'])
        for notes in (['One','one'],[''],['x'*121],'invalid'):
            with self.assertRaises(Problem):schedule.save_settings(state,{'appointmentTypes':['Visit'],'quickNotes':notes})
    def test_notifications_cover_every_technician_atomically(self):
        state,a=schedule.save(self.state,self.booking,self.user)
        result,ids=schedule.queue_appointment_email(state,a)
        self.assertEqual(len(ids),2)
        self.assertEqual({m['to'] for m in result['mailOutbox'].values()},{'scott@example.nz','bala@example.nz'})
        for m in result['mailOutbox'].values():
            for detail in ['Bring equipment','Client','1 Road','Scott, Bala','09:00']:self.assertIn(detail,m['body'])
        for field in ('active','verified'):
            broken=copy.deepcopy(state);broken['users']['bala@example.nz'][field]=False
            with self.assertRaises(Problem):schedule.queue_appointment_email(broken,a)
            self.assertNotIn('mailOutbox',broken)
    def test_send_endpoint_permissions_preview_and_current_etag(self):
        api=test_accounts.AccountsAPI();api.setUp();existing=api.store.state['users'].copy();api.store.state.update(copy.deepcopy(self.state));api.store.state['users']={**existing,**api.store.state['users']}
        payload={**self.booking,'sendEmail':True}
        self.assertEqual(api.call('/api/schedule','POST',payload,token='tech')[0],403)
        api.store.state['users']['bala@example.nz']['verified']=False
        self.assertEqual(api.call('/api/schedule','POST',payload)[0],400)
        self.assertNotIn('appointments',api.store.state)
        api.store.state['users']['bala@example.nz']['verified']=True
        status,data,headers=api.call('/api/schedule','POST',payload)
        self.assertEqual(status,200);self.assertIn('previews',data['message'])
        self.assertEqual(headers['ETag'],f'"{api.store.revision}"')
        self.assertTrue(all(m['status']=='preview' for m in api.store.state['mailOutbox'].values()))
