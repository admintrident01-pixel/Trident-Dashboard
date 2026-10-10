import base64,copy,io,json,unittest
import weekly_report,leave,test_accounts
from core import Problem
from pypdf import PdfReader

class WeeklyReportTests(unittest.TestCase):
    def setUp(self):
        self.week='2026-10-05'
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]},'quotes':{'1753':{'kept':True}}}
    def approve(self,state,name,kind,start,end,hours):
        state,r=leave.create(state,{'technician':name,'leaveType':kind,'startDate':start,'endDate':end,'hoursPerDay':hours,'reason':'Private leave reason'})
        return leave.decide(state,{'id':r['id'],'revision':r['revision'],'status':'Approved'},'bala@trice.nz')[0]
    def test_approved_annual_leave_visible_without_timesheet(self):
        state=self.approve(self.state,'Scott','Annual leave',self.week,'2026-10-10',4)
        row=weekly_report.read(state,self.week)['rows'][0]
        self.assertFalse(row['submitted'])
        self.assertEqual([d['annual'] for d in row['days']],[4,4,4,4,4,0,0])
        self.assertEqual(sum(d['paid'] for d in row['days']),0)
        self.assertEqual(sum(d['all'] for d in row['days']),20)
        self.assertNotIn('Private leave reason',json.dumps(row))
    def test_sick_is_in_paid_hours_once_with_latest_timesheet(self):
        state=self.approve(self.state,'Bala','Sick leave',self.week,self.week,8)
        days=[{'status':'Sick leave','hours':8}]+[{'status':'Work','hours':4}]*6
        state['timesheets']={'old':{'technician':'Bala','weekStart':self.week,'submittedAt':'2026-10-09','days':[{'status':'Work','hours':10}]*7},'new':{'technician':'Bala','weekStart':self.week,'submittedAt':'2026-10-10','days':days}}
        row=weekly_report.read(state,self.week)['rows'][1]
        self.assertEqual(row['days'][0]['paid'],8)
        self.assertEqual(sum(d['paid'] for d in row['days']),32)
    def test_cancelled_leave_removed_and_notes_preserve_business_data(self):
        state=self.approve(self.state,'Scott','Annual leave',self.week,self.week,4)
        r=next(iter(state['leaveRequests'].values()))
        state,_=leave.decide(state,{'id':r['id'],'revision':r['revision'],'status':'Cancelled'},'bala@trice.nz')
        self.assertEqual(weekly_report.read(state,self.week)['rows'][0]['days'][0]['annual'],0)
        before=copy.deepcopy(state)
        state=weekly_report.save_notes(state,{'week':self.week,'notes':[{'technician':'Scott','date':self.week,'note':'Workshop inspection <complete>'}]})
        self.assertEqual(state['quotes'],before['quotes'])
        self.assertNotIn('weeklyReportNotes',before)
        self.assertEqual(weekly_report.read(state,self.week)['rows'][0]['days'][0]['note'],'Workshop inspection <complete>')
    def test_notes_validate_dates_staff_length_and_duplicates(self):
        row={'technician':'Scott','date':self.week,'note':'Test'}
        for changes in [{'date':'2026-10-12'},{'technician':'Unknown'},{'note':'x'*2001}]:
            with self.assertRaises(Problem):weekly_report.save_notes(self.state,{'week':self.week,'notes':[{**row,**changes}]})
        with self.assertRaises(Problem):weekly_report.save_notes(self.state,{'week':self.week,'notes':[row,row]})
        with self.assertRaises(Problem):weekly_report.read(self.state,'2026-10-06')
    def test_pdf_has_sick_annual_and_daily_notes_and_handles_long_notes(self):
        state=self.approve(self.state,'Scott','Annual leave',self.week,self.week,4)
        state=self.approve(state,'Bala','Sick leave',self.week,self.week,8)
        state=weekly_report.save_notes(state,{'week':self.week,'notes':[{'technician':'Scott','date':self.week,'note':'Equipment repaired & tested'},{'technician':'Bala','date':self.week,'note':'Long note\n'*190}]})
        pdf=weekly_report.pdf(state,{'week':self.week,'mode':'work'})
        reader=PdfReader(io.BytesIO(base64.b64decode(pdf['pdf'])))
        text='\n'.join(p.extract_text() for p in reader.pages)
        for required in ['Weekly work and sick hours','Annual 4h','Sick 8h','Equipment repaired & tested','Page 1']:
            self.assertIn(required,text)
        self.assertNotIn('Private leave reason',text)
    def test_report_endpoints_are_admin_only_and_notes_require_revision(self):
        api=test_accounts.AccountsAPI();api.setUp()
        for path,method,data in [('/api/weekly-report','GET',None),('/api/weekly-report-notes','POST',{'week':self.week,'notes':[]}),('/api/weekly-report-pdf','POST',{'week':self.week,'mode':'work'})]:
            self.assertEqual(api.call(path,method,data,token='tech')[0],403)
        self.assertEqual(api.call('/api/weekly-report-notes','POST',{'week':self.week,'notes':[]},match=False)[0],409)
        self.assertEqual(api.call('/api/weekly-report-notes','POST',{'week':self.week,'notes':[]})[0],200)
        self.assertEqual(api.call('/api/weekly-report-pdf','POST',{'week':self.week,'mode':'work'})[0],200)

if __name__=='__main__':unittest.main()
