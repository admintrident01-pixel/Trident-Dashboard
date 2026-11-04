import copy,unittest
from unittest.mock import patch
import schedule,schedule_history,schedule_routes,test_accounts
from core import Problem

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.user={'email':'admin@example.invalid'};self.date='2027-02-01'
        self.state={'staffSettings':{'technicians':[{'name':'Alex'},{'name':'Blair'}]},'quotes':{'keep':{'id':'keep'}}}
        base={'date':self.date,'technicians':['Alex','Blair'],'start':'09:00','duration':30,'client':'Team visit','address':'1 Road','type':'Repair','bookingStatus':'action-needed','bookingControlsVersion':1,'notes':'Left Vmail\nKeep all notes'}
        self.state,self.a=schedule.save(self.state,base,self.user)
        self.state,self.b=schedule.save(self.state,{**base,'start':'11:00','client':'Other'},self.user)
    def bulk(self,state,ids,status):return schedule.save_travel(state,{'date':self.date,'action':'booking_selection','ids':ids,'bookingStatus':status},self.user)
    def test_all_statuses_are_atomic_keep_teams_contacts_notes_and_unselected_records(self):
        state=self.state;state['appointments'][self.a['id']]['contactStatus']={'email':True}
        for status in ('confirmed','option','action-needed'):
            before=copy.deepcopy(state);result=self.bulk(state,[self.a['id']],status)
            a=result['appointments'][self.a['id']]
            for key in ('id','date','start','duration','technicians','client','address','notes','contactStatus'):
                self.assertEqual(a[key],before['appointments'][self.a['id']][key])
            self.assertEqual(a['bookingStatus'],status);self.assertEqual(a['timing'],'fixed' if status=='confirmed' else 'flexible')
            self.assertEqual(result['appointments'][self.b['id']],before['appointments'][self.b['id']]);self.assertEqual(state,before)
            self.assertEqual(result['quotes'],state['quotes']);state=result
    def test_stale_or_other_day_selection_writes_nothing(self):
        before=copy.deepcopy(self.state)
        with self.assertRaises(Problem):self.bulk(self.state,[self.a['id'],'missing'],'confirmed')
        self.assertEqual(self.state,before)
        with self.assertRaises(Problem):self.bulk(self.state,[self.a['id']],'invalid')
    def test_bulk_undo_redo_roundtrip_preserves_identities(self):
        result=self.bulk(self.state,[self.a['id'],self.b['id']],'confirmed')
        recorded=schedule_history.record(self.state,result,self.user['email'],self.date,'Book selected')
        undone=schedule_history.apply(recorded,self.user['email'],self.date,'undo')
        self.assertEqual(schedule_history.clean(undone['appointments']),schedule_history.clean(self.state['appointments']))
        redone=schedule_history.apply(undone,self.user['email'],self.date,'redo')
        self.assertTrue(all(a['bookingStatus']=='confirmed' for a in redone['appointments'].values()))
    def test_contact_status_is_saved_and_retained_on_unrelated_edit(self):
        result,row=schedule.save(self.state,{**self.a,'contactStatus':{'voicemail':True,'text':False,'email':True}},self.user)
        command={**row,'notes':'User changed notes'};command.pop('contactStatus')
        result,changed=schedule.save(result,command,self.user)
        self.assertEqual(changed['contactStatus'],row['contactStatus']);self.assertEqual(changed['notes'],'User changed notes')
    def test_invalid_contact_markers_rejected_without_writes(self):
        before=copy.deepcopy(self.state)
        for value in (None,[],{'email':'yes'},{'unknown':True}):
            with self.assertRaises(Problem):schedule.save(self.state,{**self.a,'contactStatus':value},self.user)
        self.assertEqual(self.state,before)
    def test_notes_need_no_address_and_never_get_travel_or_provider_calls(self):
        state,note=schedule.save(self.state,{**self.a,'id':None,'start':'14:00','type':'Notes','client':'Reminder note','address':''},self.user)
        with patch.object(schedule_routes,'_provider',side_effect=AssertionError('Paid provider must never run')):
            self.assertFalse(any(t['anchorId']==note['id'] for t in schedule.travel_blocks(state,self.date)))
            schedule.read(state,self.date)
        deleted=schedule.save_travel(state,{'date':self.date,'action':'delete_selection','ids':[note['id']]},self.user)
        self.assertTrue(deleted['appointments'][note['id']]['cancelled']);self.assertEqual(deleted['appointments'][self.a['id']],self.a)
    def test_normal_appointments_still_require_address(self):
        with self.assertRaises(Problem):schedule.save(self.state,{**self.a,'address':''},self.user)
    def test_bulk_api_enforces_permissions_and_schedule_revision(self):
        api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
        command={'date':self.date,'action':'booking_selection','ids':[self.a['id']],'bookingStatus':'confirmed'}
        before=copy.deepcopy(api.store.state)
        self.assertEqual(api.call('/api/schedule/travel','POST',command,token='tech')[0],403)
        self.assertEqual(api.call('/api/schedule/travel','POST',command,match=False)[0],409)
        self.assertEqual(api.store.state,before)
        self.assertEqual(api.call('/api/schedule/travel','POST',command)[0],200)

if __name__=='__main__':unittest.main()
