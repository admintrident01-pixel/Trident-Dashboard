import copy, unittest
import schedule, schedule_history, staff_setup, recycle, accounts, leave, timesheets, test_accounts
from core import Problem

class TravelStaffTests(unittest.TestCase):
    def setUp(self):
        self.actor={'email':accounts.FIRST_ADMIN,'role':'admin'}
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]},'users':copy.deepcopy(accounts.users({})),'quotes':{'old':{'historic':True}},'timesheets':{'old':{'technician':'Scott','history':True}}}
        self.booking={'date':'2027-02-01','technician':'Scott','start':'09:00','duration':60,'client':'First','address':'1 Road','type':'Repair','timing':'flexible','notes':''}
        self.state,self.first=schedule.save(self.state,self.booking,self.actor)
        self.state,self.second=schedule.save(self.state,{**self.booking,'start':'11:00','client':'Second'},self.actor)
    def test_travel_fills_gap_resizes_and_snaps_after_move(self):
        block=schedule.read(self.state,self.booking['date'])['travelBlocks'][0]
        self.assertEqual((block['start'],block['duration']),('10:00',60))
        state=schedule.save_travel(self.state,{**block,'action':'resize','delta':-15},self.actor)
        block=schedule.travel_blocks(state,self.booking['date'])[0]
        self.assertEqual((block['start'],block['duration']),('10:15',45))
        state,moved=schedule.save(state,{**self.second,'start':'11:30'},self.actor)
        block=schedule.travel_blocks(state,self.booking['date'])[0]
        self.assertEqual((block['start'],block['duration']),('10:45',45))
        state=schedule.save_travel(state,{**block,'action':'resize','delta':15},self.actor)
        self.assertEqual(schedule.travel_blocks(state,self.booking['date'])[0]['duration'],60)
        with self.assertRaises(Problem):schedule.save_travel(state,{**block,'action':'resize','delta':15},self.actor)
        lunch_state,lunch_visit=schedule.save(state,{**moved,'date':'2027-02-02'},self.actor)
        self.assertEqual(lunch_visit['start'],'11:30')
        self.assertEqual(schedule.read(lunch_state,'2027-02-02')['lunchBlocks'],[])
        state,_=schedule.save(state,{**moved,'date':'2027-02-02','start':'10:30'},self.actor)
        self.assertEqual(schedule.travel_blocks(state,'2027-02-02')[0]['duration'],60)
    def test_travel_can_cover_lunch_and_keeps_insert_constraints(self):
        state,a=schedule.save(self.state,{**self.second,'start':'13:00'},self.actor)
        block=schedule.travel_blocks(state,self.booking['date'])[0]
        self.assertEqual((block['start'],block['duration']),('10:00',180))
        resized=schedule.save_travel(state,{**block,'action':'resize','delta':-15},self.actor)
        self.assertEqual(schedule.travel_blocks(resized,self.booking['date'])[0]['duration'],165)
        for delta in (15,-180,0):
            with self.assertRaises(Problem):schedule.save_travel(state,{**block,'action':'resize','delta':delta},self.actor)
        state=schedule.save_travel(state,{'date':self.booking['date'],'technician':'Scott','anchorId':self.first['id'],'side':'before','duration':15,'action':'insert'},self.actor)
        self.assertTrue(any(b['start']=='08:45' and b['duration']==15 for b in schedule.travel_blocks(state,self.booking['date'])))
        for duration in (0,20,600):
            with self.assertRaises(Problem):schedule.save_travel(state,{'date':self.booking['date'],'technician':'Scott','anchorId':a['id'],'side':'before','duration':duration,'action':'insert'},self.actor)
    def test_manual_travel_after_snaps_to_previous_booking_without_duplicate(self):
        state=schedule.save_travel(self.state,{'date':self.booking['date'],'technician':'Scott','anchorId':self.first['id'],'side':'after','duration':15,'action':'insert'},self.actor)
        blocks=schedule.travel_blocks(state,self.booking['date'])
        self.assertEqual(len(blocks),1);self.assertEqual((blocks[0]['start'],blocks[0]['duration']),('10:00',15))
        state,moved=schedule.save(state,{**self.first,'start':'08:30'},self.actor)
        self.assertEqual(schedule.travel_blocks(state,self.booking['date'])[0]['start'],'09:30')
    def test_approved_leave_blocks_travel(self):
        state=copy.deepcopy(self.state);state['timeSettings']={'start':'10:00','finish':'16:00'}
        state['leaveRequests']={'leave':{'id':'leave','technician':'Scott','dates':[self.booking['date']],'status':'Approved','hoursPerDay':1,'leaveType':'Sick leave','other':''}}
        self.assertEqual(schedule.travel_blocks(state,self.booking['date']),[])
    def test_deleted_staff_accounts_are_recoverable_without_old_credentials(self):
        self.state['users']['scott@example.nz']={'email':'scott@example.nz','name':'Scott','technician':'Scott','role':'tech','active':True,'verified':True}
        self.state['sessions']={'old':{'email':'scott@example.nz'}};self.state['loginLinks']={'old':{'email':'scott@example.nz'}};self.state['passwords']={'scott@example.nz':{'hash':'old'}}
        result=staff_setup.delete(self.state,{'originalName':'Scott','originalEmail':'scott@example.nz','confirmed':True},self.actor)
        result=recycle.capture(self.state,result,self.actor['email'])
        self.assertNotIn('scott@example.nz',result['users']);self.assertEqual(result['sessions'],{});self.assertEqual(result['loginLinks'],{});self.assertEqual(result['passwords'],{})
        self.assertEqual(result['quotes'],self.state['quotes']);self.assertEqual(result['timesheets'],self.state['timesheets']);self.assertEqual(result['appointments'],self.state['appointments'])
        self.assertIn('staff:Scott',result['recycleBin']);self.assertIn('account:scott@example.nz',result['recycleBin'])
        result,_=recycle.action(result,{'action':'restore','ids':['account:scott@example.nz','staff:Scott']},self.actor)
        self.assertFalse(result['users']['scott@example.nz']['active']);self.assertFalse(result['users']['scott@example.nz']['verified'])
        self.assertNotIn('scott@example.nz',result['passwords'])
    def test_delete_confirmation_self_and_stale_snapshot(self):
        with self.assertRaises(Problem):staff_setup.delete(self.state,{'originalName':'Scott'},self.actor)
        with self.assertRaises(Problem):staff_setup.delete(self.state,{'originalEmail':accounts.FIRST_ADMIN,'confirmed':True},self.actor)
        api=test_accounts.AccountsAPI();api.setUp()
        data={'action':'delete','originalEmail':accounts.LEGACY_OWNER,'confirmed':True}
        self.assertEqual(api.call('/api/staff-setup','POST',data,token='tech')[0],403)
        self.assertEqual(api.call('/api/staff-setup','POST',data,match=False)[0],409)
        self.assertEqual(api.call('/api/staff-setup','POST',{**data,'confirmed':False})[0],400)
        self.assertEqual(api.call('/api/staff-setup','POST',data)[0],200)
        self.assertIn('account:'+accounts.LEGACY_OWNER,api.store.state['recycleBin'])
    def test_travel_api_is_admin_only_and_checks_revision(self):
        api=test_accounts.AccountsAPI();api.setUp();api.store.state['staffSettings']=self.state['staffSettings'];api.store.state['appointments']=self.state['appointments']
        payload={'action':'insert','date':self.booking['date'],'technician':'Scott','anchorId':self.second['id'],'side':'before','duration':15}
        self.assertEqual(api.call('/api/schedule/travel','POST',payload,token='tech')[0],403)
        self.assertEqual(api.call('/api/schedule/travel','POST',payload,match=False)[0],409)
        status,data,headers=api.call('/api/schedule/travel','POST',payload)
        self.assertEqual(status,200);self.assertEqual(data['travelBlocks'][0]['duration'],15);self.assertEqual(headers['ETag'],schedule_history.etag(api.store.state))
