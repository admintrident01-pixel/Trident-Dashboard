import copy,base64,io,unittest
import weekly_report,test_accounts
from core import Problem
from pypdf import PdfReader
class ChargedReportTests(unittest.TestCase):
    def setUp(self):
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Bala','rego':''}]},'quotes':{'keep':{'saved':True}}}
        self.week='2026-10-12'
    def charged(self,week='2026-10-12',hours=6.25):return {'week':week,'charged':[{'technician':'Scott','date':week,'hours':hours}]}
    def test_charged_persists_separately_and_can_clear(self):
        state=weekly_report.save_charged(self.state,self.charged());row=weekly_report.read(state,self.week)['rows'][0]
        self.assertEqual(row['chargedHours'][0],6.25);self.assertEqual(row['days'][0]['paid'],0);self.assertEqual(state['quotes'],self.state['quotes']);self.assertNotIn('weeklyChargedHours',self.state)
        state=weekly_report.save_charged(state,self.charged(hours=''));self.assertIsNone(weekly_report.read(state,self.week)['rows'][0]['chargedHours'][0])
    def test_validation(self):
        for hours in [-1,25,.1,True,float('nan'),float('inf'),'bad']:
            with self.assertRaises(Problem):weekly_report.save_charged(self.state,self.charged(hours=hours))
        for change in [{'technician':'Unknown'},{'date':'2026-10-19'}]:
            data=self.charged();data['charged'][0].update(change)
            with self.assertRaises(Problem):weekly_report.save_charged(self.state,data)
        data=self.charged();data['charged']*=2
        with self.assertRaises(Problem):weekly_report.save_charged(self.state,data)
    def test_averages_include_all_completed_weeks_and_zero_entries(self):
        state=copy.deepcopy(self.state)
        for week,hours in [('2026-10-05',40),('2026-09-28',32),('2026-10-12',100)]:
            state.setdefault('timesheets',{})[week]={'technician':'Scott','weekStart':week,'submittedAt':week,'days':[{'status':'Work','hours':hours/5}]*5+[{'status':'Work','hours':0}]*2}
        for week,hours in [('2026-10-05',8),('2026-09-28',0),('2026-10-12',24)]:state=weekly_report.save_charged(state,self.charged(week,hours))
        average=next(row for row in weekly_report.averages(state,self.week)['rows'] if row['name']=='Scott')
        self.assertAlmostEqual(average['paidAverage'],72/13);self.assertEqual(average['workWeeks'],2);self.assertAlmostEqual(average['chargedAverage'],8/13);self.assertEqual(average['chargedWeeks'],2)
    def test_comparison_pdf_and_admin_permissions(self):
        state=weekly_report.save_charged(self.state,self.charged())
        self.assertEqual(weekly_report.read(state,self.week,'2026-09-14')['previousWeek'],'2026-09-14')
        with self.assertRaises(Problem):weekly_report.read(state,self.week,'2026-09-15')
        pdf=weekly_report.pdf(state,{'week':self.week,'mode':'work'});text='\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(base64.b64decode(pdf['pdf']))).pages)
        for label in ['Charged hours','6.25','Total payable hours','Total charged hours','Three-month weekly averages']:self.assertIn(label,text)
        api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
        body={'updates':[self.charged()]}
        self.assertEqual(api.call('/api/weekly-report-save','POST',body,token='tech')[0],403)
        self.assertEqual(api.call('/api/weekly-report-save','POST',body,match=False)[0],409)
        self.assertEqual(api.call('/api/weekly-report-save','POST',body)[0],200)
        self.assertEqual(api.store.state['weeklyChargedHours'][self.week]['scott']['days'][self.week],6.25)
