import copy,unittest
import leave,timesheets,schedule,weekly_report
from core import Problem
class BreakdownTests(unittest.TestCase):
 def setUp(self):
  self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''}]}}
  self.row={'date':'2026-11-10','duration':'part','startTime':'10:00','endTime':'14:00','lunchChoice':'usual','lunchStart':'12:00','lunchEnd':'12:30','lunchConfirmed':True,'hoursPerDay':22}
  self.data={'technician':'Alex','leaveType':'Sick leave','startDate':'2026-11-10','endDate':'2026-11-12','hoursPerDay':8,'reason':'PRIVATE','dailyBreakdown':[self.row,{'date':'2026-11-11','duration':'full'},{**self.row,'date':'2026-11-12','startTime':'13:00','endTime':'15:00'}]}
 def test_mixed_days_calculated_server_side_and_pending_is_not_payable(self):
  original=copy.deepcopy(self.state);state,r=leave.create(self.state,self.data)
  self.assertEqual(self.state,original);self.assertEqual(r['totalHours'],13.5)
  self.assertEqual([d['hoursPerDay'] for d in r['dailyBreakdown']],[3.5,8,2])
  self.assertEqual(leave.approved(state),[]);self.assertEqual(schedule.leave_blocks(state,'2026-11-10'),[])
  self.assertEqual(schedule.read(state,'2026-11-10')['leaveBlocks'][0]['leaveStatus'],'Pending')
  self.assertEqual(weekly_report.week_rows(state,'2026-11-09')[0]['days'][1]['sick'],0)
  state,_=leave.decide(state,{'id':r['id'],'revision':1,'status':'Approved'},'admin')
  days=weekly_report.week_rows(state,'2026-11-09')[0]['days']
  self.assertEqual([days[i]['sick'] for i in (1,2,3)],[3.5,8,2]);self.assertEqual(days[1]['leaveLunch'],.5)
  self.assertEqual(schedule.leave_blocks(state,'2026-11-10')[0]['duration'],240)
 def test_confirmation_invalid_dates_and_corrections_are_enforced(self):
  for changes in [{'lunchConfirmed':False},{'date':'2026-11-09'},{'lunchChoice':'none'},{'lunchChoice':'different'},{'lunchEnd':'11:00'},{'endTime':'09:00'}]:
   data=copy.deepcopy(self.data);data['dailyBreakdown'][0].update(changes)
   with self.subTest(changes=changes),self.assertRaises(Problem):leave.create(self.state,data)
 def test_no_lunch_correction_and_partial_overlap(self):
  data=copy.deepcopy(self.data);data['dailyBreakdown'][0].update(lunchChoice='none',lunchReason='No unpaid lunch applies')
  self.assertEqual(leave.create(self.state,data)[1]['dailyBreakdown'][0]['hoursPerDay'],4)
  data['dailyBreakdown'][0].update(lunchChoice='different',lunchStart='13:45',lunchEnd='14:15')
  self.assertEqual(leave.create(self.state,data)[1]['dailyBreakdown'][0]['hoursPerDay'],3.75)
 def test_direct_paid_hours_retain_actual_times_and_do_not_deduct_twice(self):
  day={'status':'Work','method':'direct','netDirectHours':True,'hours':8,'start':'07:00','finish':'15:30','unpaidLunch':True}
  data={'technician':'Alex','weekStart':'2026-11-09','signature':'Alex','days':[day]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]}
  state,r=timesheets.save(self.state,data);self.assertEqual(r['total'],8);self.assertEqual(r['days'][0]['start'],'07:00');self.assertEqual(r['days'][0]['lunchHours'],.5)
  day['hours']=7
  with self.assertRaisesRegex(Problem,'do not match'):timesheets.save(self.state,data)
  day['notes']='Separate work periods';self.assertEqual(timesheets.save(self.state,data)[1]['total'],7)
 def test_legacy_direct_hours_keep_start_and_finish_for_payables(self):
  day={'status':'Work','method':'direct','netDirectHours':False,'hours':8,'start':'07:30','finish':'16:00','unpaidLunch':True}
  data={'technician':'Alex','weekStart':'2026-11-09','signature':'Alex','days':[day]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]}
  state,entry=timesheets.save(self.state,data)
  self.assertEqual(entry['days'][0]['start'],'07:30');self.assertEqual(entry['days'][0]['finish'],'16:00')
  row=weekly_report.week_rows(state,'2026-11-09')[0]
  self.assertEqual(row['days'][0]['workFrom'],'07:30');self.assertEqual(row['days'][0]['workTo'],'16:00')
