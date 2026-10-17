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
        with self.assertRaisesRegex(Problem,'Unbook'):schedule.save(state,update,self.user)
        state,a=schedule.save(state,{**a,'bookingStatus':'action-needed'},self.user)
        state,a=schedule.save(state,{**a,'start':'10:00'},self.user)
        self.assertEqual(a['bookingStatus'],'action-needed')
        self.assertEqual(a['timing'],'flexible')
        for status in ('option','action-needed','high-priority'):
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

    def test_save_uses_one_read_returns_schedule_and_keeps_cas(self):
        from unittest.mock import patch
        api=test_accounts.AccountsAPI();api.setUp()
        with patch.object(api.store,'read',wraps=api.store.read) as read:
            status,data,headers=api.call('/api/schedule','POST',{**self.booking,'technicians':['Scott Yearbury']})
            self.assertEqual(status,200)
            self.assertEqual(read.call_count,1)
            self.assertIn(data['appointment'],data['schedule']['appointments'])
            self.assertEqual(headers['ETag'],f'"{api.store.revision}"')
        appointment=data['appointment']
        with patch.object(api.store,'commit',return_value=False):
            status,_,_=api.call('/api/schedule','POST',{**appointment,'start':'10:00'})
            self.assertEqual(status,409)
        self.assertEqual(api.store.state['appointments'][appointment['id']]['start'],appointment['start'])

    def test_conditional_schedule_response_is_small_and_authenticated(self):
        import io,json
        api=test_accounts.AccountsAPI();api.setUp()
        env={'REQUEST_METHOD':'GET','PATH_INFO':'/api/schedule','QUERY_STRING':'date=2027-02-01','HTTP_AUTHORIZATION':'Bearer admin','HTTP_IF_NONE_MATCH':f'"{api.store.revision}"','CONTENT_LENGTH':'0','wsgi.input':io.BytesIO(b'')}
        meta=[];body=b''.join(api.app(env,lambda status,headers:meta.append(status)))
        self.assertEqual(meta[0],'200 OK');self.assertEqual(json.loads(body),{'unchanged':True})
        preflight=api.call('/api/schedule','OPTIONS')[2]
        self.assertIn('If-None-Match',preflight['Access-Control-Allow-Headers'])
        env.pop('HTTP_AUTHORIZATION');meta=[];body=b''.join(api.app(env,lambda status,headers:meta.append(status)))
        self.assertTrue(meta[0].startswith('401'))

    def test_high_priority_survives_move_and_undo(self):
        import schedule_history
        state,a=schedule.save(self.state,{**self.booking,'bookingStatus':'high-priority'},self.user)
        after,b=schedule.save(state,{**a,'start':'10:00'},self.user)
        self.assertEqual(b['bookingStatus'],'high-priority')
        after=schedule_history.record(state,after,self.user['email'],a['date'],'Move priority booking')
        restored=schedule_history.apply(after,self.user['email'],a['date'],'undo')
        self.assertEqual(restored['appointments'][a['id']]['bookingStatus'],'high-priority')
        self.assertEqual(restored['appointments'][a['id']]['start'],'09:00')
        self.assertEqual(schedule.BOOKING_STATUS_LABELS['option'],'Optional')
