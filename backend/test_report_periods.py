import unittest,base64,io
import weekly_report,test_accounts
from core import Problem
from pypdf import PdfReader
class PeriodTests(unittest.TestCase):
 def setUp(self):
  self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':''}]}}
  self.dates={'start':'2026-09-28','end':'2026-10-05'}
  for week,hours in [('2026-09-28',8),('2026-10-05',6),('2026-10-12',9)]:
   self.state.setdefault('timesheets',{})[week]={'technician':'Scott','weekStart':week,'submittedAt':week,'days':[{'status':'Work','hours':hours}]+[{'status':'Work','hours':0}]*6}
   self.state=weekly_report.save_charged(self.state,{'week':week,'charged':[{'technician':'Scott','date':week,'hours':hours-1}]})
 def test_inclusive_weeks_and_latest_correction(self):
  self.state['timesheets']['correction']={**self.state['timesheets']['2026-10-05'],'updatedAt':'2026-10-13','days':[{'status':'Work','hours':7}]+[{'status':'Work','hours':0}]*6}
  r=weekly_report.selected_period(self.state,self.dates)
  self.assertEqual(r['weeks'],2);self.assertEqual(r['end'],'2026-10-11');self.assertEqual(r['rows'][0]['paid'],15);self.assertEqual(r['rows'][0]['charged'],12);self.assertEqual(r['rows'][0]['paidAverage'],7.5);self.assertEqual(r['rows'][0]['chargedAverage'],6)
 def test_missing_weeks_use_selected_denominator_and_single_week(self):
  r=weekly_report.selected_period(self.state,{'start':'2026-09-21','end':'2026-10-05'})
  self.assertEqual(r['weeks'],3);self.assertAlmostEqual(r['rows'][0]['paidAverage'],14/3);self.assertEqual(r['rows'][0]['chargedAverage'],4);self.assertEqual(r['rows'][0]['workWeeks'],2)
  r=weekly_report.selected_period(self.state,{'start':'2026-10-12','end':'2026-10-12'})
  self.assertEqual(r['rows'][0]['paidAverage'],9)
 def test_invalid_ranges(self):
  for changes in [{'start':'2026-09-29'},{'end':'2026-09-21'},{'end':'2027-09-27'},{'end':''}]:
   with self.assertRaises(Problem):weekly_report.selected_period(self.state,{**self.dates,**changes})
 def test_pdf_totals_and_admin_only(self):
  result=weekly_report.period_pdf(self.state,self.dates);reader=PdfReader(io.BytesIO(base64.b64decode(result['pdf'])));text=' '.join(page.extract_text() for page in reader.pages)
  self.assertEqual(len(reader.pages),1)
  for expected in ['Selected week averages','Average payable','Average charged','Scott','Total','14','12']:self.assertIn(expected,text)
  api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(self.state)
  for path in ['/api/report-periods','/api/report-periods-pdf']:
   self.assertEqual(api.call(path,'POST',self.dates,token='tech')[0],403);self.assertEqual(api.call(path,'POST',self.dates)[0],200)
 def test_weekly_pdf_fits_one_page_with_eight_staff_and_notes(self):
  self.state['staffSettings']['technicians']=[{'name':f'Technician {i}','rego':''} for i in range(8)]
  self.state['weeklyReportNotes']={'2026-10-12':{f'technician {i}':{'2026-10-12':'Daily repair notes. '*12} for i in range(8)}}
  result=weekly_report.pdf(self.state,{'week':'2026-10-12'});reader=PdfReader(io.BytesIO(base64.b64decode(result['pdf'])))
  self.assertEqual(len(reader.pages),1)
  for expected in ['Technician 7','Total charged hours','Three-month weekly averages','Daily repair notes.']:self.assertIn(expected,reader.pages[0].extract_text())

 def test_five_weeks_with_zero_and_missing_values_average_to_5_6(self):
  for missing in [False,True]:
   state={'staffSettings':{'technicians':[{'name':'Scott','rego':''},{'name':'Empty','rego':''}]}}
   weeks=['2026-09-07','2026-09-14','2026-09-21','2026-09-28','2026-10-05']
   for week,hours in zip(weeks,[7,7,7,0,7]):
    if missing and hours==0:continue
    state.setdefault('timesheets',{})[week]={'technician':'Scott','weekStart':week,'submittedAt':week,'days':[{'status':'Work','hours':hours}]+[{'status':'Work','hours':0}]*6}
    state=weekly_report.save_charged(state,{'week':week,'charged':[{'technician':'Scott','date':week,'hours':hours}]})
   result=weekly_report.selected_period(state,{'start':weeks[0],'end':weeks[-1]})
   row=next(r for r in result['rows'] if r['name']=='Scott')
   for metric in ['paidAverage','allAverage','chargedAverage']:self.assertEqual(row[metric],5.6)
   empty=next(r for r in result['rows'] if r['name']=='Empty')
   for metric in ['paidAverage','allAverage','chargedAverage']:self.assertEqual(empty[metric],0)
   three_months=weekly_report.averages(state,'2026-10-12')
   row=next(r for r in three_months['rows'] if r['name']=='Scott')
   for metric in ['paidAverage','allAverage','chargedAverage']:self.assertAlmostEqual(row[metric],28/13)
