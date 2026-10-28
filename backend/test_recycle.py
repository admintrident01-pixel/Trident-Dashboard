import copy, unittest
from core import Problem
import recycle, schedule, vehicles, timesheets
import test_accounts

class RecycleTests(unittest.TestCase):
    def setUp(self):
        self.actor={'email':'admin@example.nz'}
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''}]},'appointments':{},'leaveRequests':{},'quotes':{},'pdfs':{}}
        self.booking={'date':'2027-02-01','technician':'Scott','start':'09:00','duration':60,'client':'Test Client','address':'1 Test Road','type':'Equipment repair','timing':'flexible','notes':''}
    def cancel(self):
        state,booking=schedule.save(self.state,self.booking,self.actor)
        cancelled,record=schedule.save(state,{**booking,'action':'cancel'},self.actor)
        return recycle.capture(state,cancelled,self.actor['email']),record
    def test_cancel_restore_and_purge_are_transactional(self):
        state,record=self.cancel();entry=recycle.read(state)['items'][0]
        self.assertEqual(entry['type'],'appointment');self.assertNotIn('value',entry)
        restored,_=recycle.action(state,{'ids':[entry['id']],'action':'restore'},self.actor)
        self.assertFalse(restored['appointments'][record['id']]['cancelled'])
        self.assertEqual(recycle.read(restored)['items'],[])
        self.assertTrue(state['appointments'][record['id']]['cancelled'])
        with self.assertRaises(Problem):recycle.action(state,{'ids':[entry['id']],'action':'purge'},self.actor)
        purged,_=recycle.action(state,{'ids':[entry['id']],'action':'purge','confirmed':True},self.actor)
        self.assertNotIn(record['id'],purged['appointments']);self.assertEqual(recycle.read(purged)['items'],[])
    def test_restore_rejects_new_booking_conflict_without_partial_changes(self):
        state,_=self.cancel();state,new=schedule.save(state,self.booking,self.actor)
        original=copy.deepcopy(state)
        with self.assertRaises(Problem):recycle.action(state,{'ids':[recycle.read(state)['items'][0]['id']],'action':'restore'},self.actor)
        self.assertEqual(state,original)
    def test_staff_vehicle_and_settings_removal_restore(self):
        state=copy.deepcopy(self.state);state['vehicles']=[{'id':'v1','registration':'TEST1','driver':'Scott','makeModel':'','active':True,'baseline':{}}]
        result=timesheets.save_settings(state,{'technicians':[]});result=vehicles.save_fleet(result,{'vehicles':[]})
        result=recycle.capture(state,result,self.actor['email'])
        ids=[r['id'] for r in recycle.read(result)['items']]
        restored,_=recycle.action(result,{'ids':ids,'action':'restore'},self.actor)
        self.assertEqual(timesheets.settings(restored)['technicians'][0]['name'],'Scott')
        self.assertEqual(vehicles.fleet(restored)[0]['registration'],'TEST1')
        self.assertEqual(recycle.read(restored)['items'],[])
        state['scheduleSettings']={'appointmentTypes':['Repair','Delivery']}
        new=schedule.save_settings(state,{'appointmentTypes':['Repair']})
        archived=recycle.capture(state,new,self.actor['email'])
        restored,_=recycle.action(archived,{'ids':['appointmentType:Delivery'],'action':'restore'},self.actor)
        self.assertEqual(schedule.settings(restored)['appointmentTypes'],['Repair','Unspecified','Delivery'])
    def test_legacy_lunch_purge_does_not_regenerate_blocks(self):
        state=copy.deepcopy(self.state)
        state['appointments']['old-lunch']={**self.booking,'id':'old-lunch','source':'lunch','type':'Lunch','client':'Lunch','start':'12:00','duration':30,'cancelled':True,'version':1,'createdAt':'original'}
        ids=[r['id'] for r in recycle.read(state)['items']]
        purged,_=recycle.action(state,{'ids':ids,'action':'purge','confirmed':True},self.actor)
        self.assertEqual(schedule.lunch_blocks(purged,self.booking['date']),[])
        self.assertEqual(schedule.lunch_blocks(purged,'2027-02-02'),[])
        self.assertEqual(recycle.read(purged)['items'],[])
    def test_legacy_lunch_restore_keeps_history_without_blocking_current_work(self):
        state,booking=schedule.save(self.state,{**self.booking,'start':'12:00'},self.actor)
        state['appointments']['old-lunch']={**booking,'id':'old-lunch','source':'lunch','type':'Lunch','client':'Lunch','duration':30,'cancelled':True,'notes':'Historical note'}
        before=copy.deepcopy(state)
        restored,_=recycle.action(state,{'ids':['lunch:old-lunch'],'action':'restore'},self.actor)
        self.assertFalse(restored['appointments']['old-lunch']['cancelled']);self.assertEqual(restored['appointments']['old-lunch']['notes'],'Historical note')
        self.assertEqual(restored['appointments'][booking['id']],booking)
        self.assertEqual([a['id'] for a in schedule.read(restored,self.booking['date'])['appointments']],[booking['id']])
        self.assertEqual(state,before)
    def test_legacy_cancelled_leave_returns_pending(self):
        self.state['leaveRequests']['old']={'id':'old','revision':2,'status':'Cancelled','technician':'Scott','startDate':'2027-02-01','dates':['2027-02-01'],'hoursPerDay':8,'leaveType':'Sick leave'}
        restored,_=recycle.action(self.state,{'ids':['leave:old'],'action':'restore'},self.actor)
        self.assertEqual(restored['leaveRequests']['old']['status'],'Pending')
    def test_api_requires_admin_matching_revision_and_explicit_purge(self):
        api=test_accounts.AccountsAPI();api.setUp()
        self.assertEqual(api.call('/api/recycle-bin',token='tech')[0],403)
        self.assertEqual(api.call('/api/recycle-bin','POST',{'action':'purge','ids':['x']},token='tech')[0],403)
        self.assertEqual(api.call('/api/recycle-bin','POST',{'action':'restore','ids':['x']},match=False)[0],409)
        self.assertEqual(api.call('/api/recycle-bin')[1]['items'],[])
        self.assertEqual(api.call('/api/recycle-bin','POST',{'action':'purge','ids':['x']})[0],400)
