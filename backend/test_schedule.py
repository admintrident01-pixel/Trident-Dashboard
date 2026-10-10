import copy, io, json, unittest
import schedule, test_accounts
from core import Problem

class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.user={'email':'bala@trice.nz'}
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]},'quotes':{'1753':{'existing':True}}}
        self.booking={'date':'2027-02-01','technician':'Scott','start':'09:00','duration':60,'client':'Test Client','address':'1 Test Road','type':'Equipment repair','timing':'flexible','notes':''}
    def test_saved_column_order_keeps_office_last_and_handles_staff_changes(self):
        self.state['staffSettings']['technicians'].append({'name':'Office','rego':'','staffType':'office'})
        result=schedule.save_settings(self.state,{'appointmentTypes':['Repair'],'technicianOrder':['Office','Bala','Scott']})
        self.assertEqual(schedule.read(result,'2027-02-01')['technicians'],['Bala','Scott','Office'])
        self.assertEqual(schedule.settings(result)['technicianOrder'],['Bala','Scott','Office'])
        result['staffSettings']['technicians'][0]['name']='New staff'
        self.assertEqual(schedule.settings(result)['technicianOrder'],['Bala','New staff','Office'])
        for order in [['Scott'],['Scott','Scott','Office'],['Scott','Bala','Unknown']]:
            with self.assertRaises(Problem):schedule.save_settings(self.state,{'appointmentTypes':['Repair'],'technicianOrder':order})

    def test_future_booking_and_day_filter_preserve_business_data(self):
        result,booking=schedule.save(self.state,self.booking,self.user)
        self.assertEqual(schedule.read(result,'2027-02-01')['appointments'],[booking])
        self.assertEqual(schedule.read(result,'2027-02-02')['appointments'],[])
        self.assertEqual(result['quotes'],self.state['quotes'])
        self.assertNotIn('appointments',self.state)
    def test_schedule_includes_normal_work_hours(self):
        self.assertEqual(schedule.read(self.state,'2027-02-01')['workHours'],{'start':'08:00','finish':'16:00'})
        self.state['timeSettings']={'start':'07:30','finish':'16:15'}
        result=schedule.read(self.state,'2027-02-01')
        self.assertEqual(result['workHours'],self.state['timeSettings'])
        result['workHours']['start']='09:00'
        self.assertEqual(self.state['timeSettings']['start'],'07:30')
    def test_shared_booking_validates_every_technician_and_stays_one_record(self):
        state,booking=schedule.save(self.state,{**self.booking,'technicians':['Scott','Bala']},self.user)
        self.assertEqual(booking['technicians'],['Scott','Bala'])
        self.assertEqual(len(state['appointments']),1)
        self.assertEqual(len(schedule.read(state,self.booking['date'])['appointments']),1)
        with self.assertRaises(Problem):schedule.save(state,{**self.booking,'technician':'Bala'},self.user)
        state,updated=schedule.save(state,{**booking,'start':'10:30'},self.user)
        self.assertEqual(updated['technicians'],['Scott','Bala'])
        state,cancelled=schedule.save(state,{**updated,'action':'cancel'},self.user)
        self.assertTrue(cancelled['cancelled'])
        state,restored=schedule.save(state,{**cancelled,'action':'restore'},self.user)
        self.assertEqual(restored['technicians'],['Scott','Bala'])
        for technicians in [[],['Scott','Scott'],['Unknown'],'Scott']:
            with self.assertRaises(Problem):schedule.save(self.state,{**self.booking,'technicians':technicians},self.user)
        self.assertTrue(schedule.overlaps(booking,{'technician':'Bala','start':'09:15','duration':60}))
    def test_appointment_type_settings_permissions_and_history(self):
        api=test_accounts.AccountsAPI();api.setUp()
        self.assertEqual(api.call('/api/schedule-settings',token='tech')[0],403)
        self.assertEqual(api.call('/api/schedule-settings','POST',{'appointmentTypes':['Install']},token='tech')[0],403)
        self.assertEqual(api.call('/api/schedule-settings','POST',{'appointmentTypes':['Install']},match=False)[0],409)
        self.assertEqual(api.call('/api/schedule-settings','POST',{'appointmentTypes':['Install','Delivery']})[0],200)
        self.assertEqual(api.call('/api/schedule-settings')[1]['appointmentTypes'],['Install','Delivery'])
        state,booking=schedule.save(self.state,self.booking,self.user)
        updated=schedule.save_settings(state,{'appointmentTypes':['New type']})
        self.assertEqual(updated['appointments'],state['appointments'])
        self.assertEqual(schedule.read(updated,self.booking['date'])['appointmentTypes'],['New type'])
        for types in [[],['One','one'],[''],['x'*121],'Not a list']:
            with self.assertRaises(Problem):schedule.save_settings(state,{'appointmentTypes':types})
    def test_default_lunch_moves_removes_and_restores_without_changing_other_days(self):
        result=schedule.read(self.state,'2027-02-01')
        self.assertEqual(len(result['lunchBlocks']),2)
        lunch=result['lunchBlocks'][0]
        self.assertEqual((lunch['start'],lunch['duration']),('12:00',30))
        self.assertNotIn('appointments',self.state)
        state,moved=schedule.save(self.state,{**lunch,'start':'13:00'},self.user)
        self.assertEqual(len(schedule.read(state,'2027-02-01')['lunchBlocks']),1)
        self.assertEqual(schedule.read(state,'2027-02-02')['lunchBlocks'][0]['start'],'12:00')
        state,cancelled=schedule.save(state,{**moved,'action':'cancel'},self.user)
        self.assertTrue(cancelled['cancelled'])
        self.assertEqual(len(schedule.read(state,'2027-02-01')['lunchBlocks']),1)
        state,restored=schedule.save(state,{**cancelled,'action':'restore'},self.user)
        self.assertEqual(restored['start'],'13:00')
        self.assertFalse(restored['cancelled'])
    def test_lunch_settings_manual_booking_and_leave(self):
        import leave
        state=schedule.save_settings(self.state,{'appointmentTypes':['Repair'],'lunchStart':'12:45'})
        self.assertEqual(schedule.read(state,'2027-02-01')['lunchBlocks'][0]['start'],'12:45')
        for start in ['12:10','23:45','bad']:
            with self.assertRaises(Problem):schedule.save_settings(state,{'appointmentTypes':['Repair'],'lunchStart':start})
        state,manual=schedule.save(state,{**self.booking,'type':'Lunch','start':'13:30','duration':30,'client':'','address':'','technicians':['Scott','Bala']},self.user)
        self.assertEqual(manual['source'],'lunch')
        self.assertEqual(schedule.read(state,'2027-02-01')['lunchBlocks'],[])
        # A lunch marker can sit alongside a long client booking.
        schedule.save(state,{**self.booking,'duration':360},self.user)
        state,request=leave.create(self.state,{'technician':'Scott','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','hoursPerDay':8,'reason':'Test'})
        state,_=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Approved'},self.user['email'])
        self.assertEqual([a['technician'] for a in schedule.read(state,'2027-02-01')['lunchBlocks']],['Bala'])
    def test_move_resize_and_stale_record(self):
        state,booking=schedule.save(self.state,self.booking,self.user)
        updated={**booking,'technician':'Bala','technicians':['Bala'],'start':'10:15','duration':90}
        state,new=schedule.save(state,updated,self.user)
        self.assertEqual((new['start'],new['duration'],new['technician']),('10:15',90,'Bala'))
        with self.assertRaises(Problem):schedule.save(state,booking,self.user)
    def test_office_staff_are_last_with_stable_order(self):
        state=copy.deepcopy(self.state)
        state['staffSettings']['technicians']=[{'name':'Office A','rego':'','staffType':'office','hasVehicle':False},{'name':'Scott','rego':''},{'name':'Office B','rego':'','staffType':'office','hasVehicle':False},{'name':'Bala','rego':''}]
        result=schedule.read(state,'2027-02-01')
        self.assertEqual(result['technicians'],['Scott','Bala','Office A','Office B'])
        self.assertEqual(result['staffTypes']['Office A'],'office')
    def test_staff_vehicle_options_validate_and_preserve_history(self):
        import timesheets
        legacy=timesheets.settings(self.state)['technicians'][0]
        self.assertEqual((legacy['staffType'],legacy['hasVehicle']),('technician',True))
        row={'name':'Office A','rego':'ABC123','staffType':'office','hasVehicle':False}
        result=timesheets.save_settings(self.state,{'technicians':[row]})
        self.assertEqual(result['staffSettings']['technicians'][0],{**row,'rego':''})
        self.assertEqual(result['quotes'],self.state['quotes'])
        self.assertEqual(self.state['staffSettings']['technicians'][0],{'name':'Scott','rego':''})
        for changes in [{'staffType':'other'},{'hasVehicle':'false'}]:
            with self.assertRaises(Problem):timesheets.save_settings(self.state,{'technicians':[{**row,**changes}]})
    def test_overlap_blocked_but_adjacent_and_other_technicians_allowed(self):
        state,_=schedule.save(self.state,self.booking,self.user)
        with self.assertRaises(Problem):schedule.save(state,{**self.booking,'start':'09:45'},self.user)
        state,_=schedule.save(state,{**self.booking,'start':'10:00'},self.user)
        schedule.save(state,{**self.booking,'technician':'Bala'},self.user)
    def test_cancel_restore_and_restore_overlap(self):
        state,booking=schedule.save(self.state,self.booking,self.user)
        state,cancelled=schedule.save(state,{**booking,'action':'cancel'},self.user)
        self.assertTrue(cancelled['cancelled'])
        state,restored=schedule.save(state,{**cancelled,'action':'restore'},self.user)
        self.assertFalse(restored['cancelled'])
        state,cancelled=schedule.save(state,{**restored,'action':'cancel'},self.user)
        state,_=schedule.save(state,self.booking,self.user)
        with self.assertRaises(Problem):schedule.save(state,{**cancelled,'action':'restore'},self.user)
    def test_invalid_input_and_removed_technician_history(self):
        for key,value in [('date','2027-02-30'),('start','09:10'),('duration',20),('duration',True),('duration',1500),('technician','Unknown'),('client',''),('address',''),('timing','maybe')]:
            with self.assertRaises(Problem,msg=key):schedule.save(self.state,{**self.booking,key:value},self.user)
        state,booking=schedule.save(self.state,self.booking,self.user)
        state['staffSettings']['technicians']=[]
        self.assertEqual(schedule.read(state,'2027-02-01')['technicians'],['Scott'])
        schedule.save(state,{**booking,'duration':90},self.user)
    def test_api_view_for_techs_admin_only_mutations_and_conflicts(self):
        api=test_accounts.AccountsAPI();api.setUp()
        raw=b'';meta=[]
        env={'REQUEST_METHOD':'GET','PATH_INFO':'/api/schedule','QUERY_STRING':'date=2027-02-01','HTTP_ORIGIN':'http://127.0.0.1:18780','HTTP_AUTHORIZATION':'Bearer tech','CONTENT_LENGTH':'0','wsgi.input':io.BytesIO(raw)}
        payload=json.loads(b''.join(api.app(env,lambda s,h:meta.append((s,h)))))
        self.assertEqual(meta[0][0],'200 OK');self.assertIn('Scott Yearbury',payload['technicians'])
        booking={**self.booking,'technician':'Scott Yearbury'}
        for action in ['save','cancel','restore']:
            self.assertEqual(api.call('/api/schedule','POST',{**booking,'action':action},token='tech')[0],403)
        self.assertEqual(api.call('/api/schedule','POST',booking,match=False)[0],409)
        self.assertEqual(api.call('/api/schedule','POST',booking)[0],200)
        self.assertEqual(api.call('/api/schedule',token='')[0],401)

    def test_approved_leave_syncs_pending_does_not_and_cancellation_removes_it(self):
        import leave
        state,request=leave.create(self.state,{'technician':'Scott','leaveType':'Sick leave','startDate':'2027-02-01','endDate':'2027-02-02','hoursPerDay':8,'reason':'Private medical note'})
        self.assertEqual(schedule.read(state,'2027-02-01')['leaveBlocks'],[])
        state,request=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Approved'},self.user['email'])
        for date in ['2027-02-01','2027-02-02']:
            block=schedule.read(state,date)['leaveBlocks'][0]
            self.assertEqual((block['technician'],block['start'],block['duration']),('Scott','08:00',480))
            self.assertNotIn('reason',block);self.assertNotIn('leaveType',block)
            self.assertEqual(block['type'],'Approved leave')
        state,_=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Cancelled'},self.user['email'])
        self.assertEqual(schedule.read(state,'2027-02-01')['leaveBlocks'],[])

    def test_leave_prevents_bookings_and_flags_existing_appointments(self):
        import leave
        state,booking=schedule.save(self.state,self.booking,self.user)
        state,request=leave.create(state,{'technician':'Scott','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','hoursPerDay':8,'reason':'Holiday'})
        state,request=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Approved'},self.user['email'])
        self.assertTrue(schedule.read(state,'2027-02-01')['appointments'][0]['leaveConflict'])
        with self.assertRaisesRegex(Problem,'approved leave'):schedule.save(state,{**self.booking,'start':'11:00'},self.user)
        schedule.save(state,{**self.booking,'start':'16:00'},self.user)
        schedule.save(state,{**self.booking,'technician':'Bala'},self.user)
        schedule.save(state,{**booking,'action':'cancel'},self.user)

    def test_leave_uses_default_start_and_handles_full_days(self):
        import leave
        state={**self.state,'timeSettings':{'start':'07:30','finish':'16:00'}}
        state,request=leave.create(state,{'technician':'Scott','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','hoursPerDay':24,'reason':'Test'})
        state,_=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Approved'},self.user['email'])
        block=schedule.read(state,'2027-02-01')['leaveBlocks'][0]
        self.assertEqual((block['start'],block['duration']),('00:00',1440))

if __name__=='__main__':unittest.main()
