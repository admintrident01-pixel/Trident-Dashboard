import copy,unittest
from core import Problem
import leave,schedule,timesheets,timesheet_drafts,weekly_report

class TimedLeaveTests(unittest.TestCase):
 def setUp(self):
  self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''}]},'timeSettings':{'start':'08:00','finish':'16:00'}}
  self.request={'technician':'Scott','leaveType':'Annual leave','other':'','startDate':'2027-02-01','endDate':'2027-02-01','startTime':'12:00','endTime':'16:00','hoursPerDay':4,'reason':'Sample afternoon leave'}
  self.actor={'email':'admin@example.nz','role':'admin'}
 def approved(self,**changes):
  state,request=leave.create(self.state,{**self.request,**changes});return leave.decide(state,{'id':request['id'],'revision':1,'status':'Approved'},self.actor['email'])[0]
 def sheet(self,**first):
  return {'technician':'Scott','weekStart':'2027-02-01','signature':'Scott','notes':'','days':[{'status':'Work','method':'direct','hours':4 if i==0 else 0,'unpaidLunch':False,'notes':'',**(first if i==0 else {})} for i in range(7)]}
 def test_schedule_blocks_the_time_range_not_the_paid_hours_or_default_start(self):
  block=schedule.leave_blocks(self.approved(hoursPerDay=3.5),'2027-02-01')[0]
  self.assertEqual((block['start'],block['duration'],block['hoursPerDay']),('12:00',240,3.5))
 def test_work_and_leave_are_added_once_in_submission_and_payables(self):
  state,entry=timesheets.save(self.approved(),self.sheet());day=entry['days'][0]
  self.assertEqual(day['hours'],4);self.assertEqual(day['leave']['hoursPerDay'],4);self.assertEqual(entry['total'],8)
  report=weekly_report.week_rows(state,'2027-02-01')[0]['days'][0]
  self.assertEqual((report['work'],report['annual'],report['all']),(4,4,8));self.assertEqual(report['leaveFrom'],'12:00')
  payload={**self.sheet(),'id':entry['id'],'revision':1,'editReason':'Sample correction'}
  corrected,new=timesheets.edit_submission(state,payload,self.actor);self.assertEqual(new['total'],8)
  self.assertEqual(weekly_report.week_rows(corrected,'2027-02-01')[0]['days'][0]['all'],8)
 def test_sick_leave_and_work_both_count_in_paid_metric(self):
  state,_=timesheets.save(self.approved(leaveType='Sick leave'),self.sheet())
  report=weekly_report.week_rows(state,'2027-02-01')[0]['days'][0];self.assertEqual(report['paid'],8)
 def test_unsubmitted_work_is_excluded_from_payables_but_draft_total_includes_leave(self):
  state=self.approved();state,entry=timesheet_drafts.save(state,self.sheet(),{**self.actor,'technician':'Scott'})
  self.assertEqual(entry['total'],8);self.assertEqual(weekly_report.week_rows(state,'2027-02-01')[0]['days'][0]['all'],4)
 def test_work_times_must_not_overlap_leave_and_direct_hours_allow_split_work(self):
  with self.assertRaisesRegex(Problem,'overlap'):timesheets.save(self.approved(),self.sheet(method='times',start='09:00',finish='13:00'))
  _,entry=timesheets.save(self.approved(),self.sheet(method='times',start='08:00',finish='12:00'));self.assertEqual(entry['total'],8)
 def test_client_cannot_forge_approved_leave_hours(self):
  _,entry=timesheets.save(self.state,self.sheet(leave={'hoursPerDay':20},leaveHours=20));self.assertEqual(entry['total'],4);self.assertNotIn('leave',entry['days'][0])
 def test_invalid_and_overnight_ranges_are_rejected(self):
  for changes in [{'startTime':'12:07'},{'endTime':'11:00'},{'startTime':'','endTime':'16:00'},{'hoursPerDay':4.25}]:
   with self.subTest(changes=changes),self.assertRaises(Problem):leave.create(self.state,{**self.request,**changes})
 def test_midnight_end_is_supported(self):
  state=self.approved(startTime='23:00',endTime='24:00',hoursPerDay=1);self.assertEqual(schedule.leave_blocks(state,'2027-02-01')[0]['duration'],60)
 def test_existing_leave_without_times_keeps_previous_behaviour(self):
  request=copy.deepcopy(self.request);request.pop('startTime');request.pop('endTime');request['hoursPerDay']=8
  state,entry=leave.create(self.state,request);state,_=leave.decide(state,{'id':entry['id'],'revision':1,'status':'Approved'},self.actor['email'])
  self.assertEqual(schedule.leave_blocks(state,'2027-02-01')[0]['start'],'08:00')
  with self.assertRaises(Problem):timesheets.save(state,self.sheet())
 def test_cancelling_leave_preserves_submitted_history_and_removes_future_blocks(self):
  state,entry=timesheets.save(self.approved(),self.sheet());request=next(iter(state['leaveRequests'].values()))
  state,_=leave.decide(state,{'id':request['id'],'revision':request['revision'],'status':'Cancelled'},self.actor['email'])
  self.assertEqual(schedule.leave_blocks(state,'2027-02-01'),[]);self.assertEqual(state['timesheets'][entry['id']]['total'],8)
  self.assertEqual(weekly_report.week_rows(state,'2027-02-01')[0]['days'][0]['all'],8)

if __name__=='__main__':unittest.main()
