import base64,io,unittest,zipfile
from xml.etree import ElementTree as ET
from core import Problem
import leave,schedule,timesheets,weekly_export,weekly_report,weekly_template
import openpyxl
from pypdf import PdfReader

class LeaveTypeTests(unittest.TestCase):
 def setUp(self):
  self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''}]},'timeSettings':{'start':'08:00','finish':'16:00'}}
  self.types={
   'Paid annual leave':True,
   'Unpaid annual leave':False,
   'Sick leave paid':True,
   'Sick leave unpaid':False,
   'Other paid':True,
   'Other unpaid':False,
  }
 def request(self,kind,**changes):
  data={'technician':'Alex','leaveType':kind,'other':'Community event' if 'Other' in kind else '', 'startDate':'2027-02-01','endDate':'2027-02-01','hoursPerDay':8,'reason':'Synthetic test leave'}
  data.update(changes);return data
 def approved(self,data):
  state,request=leave.create(self.state,data)
  return leave.decide(state,{'id':request['id'],'revision':1,'status':'Approved'},'admin@example.nz')[0]

 def approved_six_types(self):
  state=self.state;dates=['2027-02-0%d' % i for i in range(1,7)]
  for kind,date in zip(self.types,dates):
   state,request=leave.create(state,self.request(kind,startDate=date,endDate=date,includeWeekends=True))
   state=leave.decide(state,{'id':request['id'],'revision':1,'status':'Approved'},'admin@example.nz')[0]
  return state,dates
 def sheet(self,status='Work',other=''):
  return {'technician':'Alex','weekStart':'2027-02-01','signature':'Alex','days':[{'status':status,'method':'direct','hours':8 if i==0 and status!='Work' else 0,'other':other,'notes':''} for i in range(7)]}

 def test_all_six_types_store_the_explicit_paid_status(self):
  for kind,paid in self.types.items():
   with self.subTest(kind=kind):
    _,request=leave.create(self.state,self.request(kind))
    self.assertEqual(request['leaveType'],kind)
    self.assertIs(request['paid'],paid)
    self.assertEqual(request['paidHours'],8 if paid else 0)
    self.assertEqual(request['unpaidHours'],0 if paid else 8)
    self.assertEqual(request['typeCategory'],'annual' if 'annual' in kind.casefold() else 'sick' if 'sick' in kind.casefold() else 'other')

 def test_mixed_daily_types_keep_paid_and_unpaid_totals(self):
  kinds=list(self.types)
  dates=['2027-02-0%d' % i for i in range(1,7)]
  data=self.request(kinds[0],startDate=dates[0],endDate=dates[-1],includeWeekends=True,other='Community event',dailyBreakdown=[{'date':date,'leaveType':kind,'duration':'full'} for date,kind in zip(dates,kinds)])
  state,request=leave.create(self.state,data)
  self.assertEqual(request['totalHours'],48)
  self.assertEqual(request['paidHours'],24)
  self.assertEqual(request['unpaidHours'],24)
  self.assertEqual([row['paid'] for row in request['dailyBreakdown']],[True,False,True,False,True,False])
  state=leave.decide(state,{'id':request['id'],'revision':1,'status':'Approved'},'admin@example.nz')[0]
  days=weekly_report.week_rows(state,dates[0])[0]['days']
  self.assertEqual([day['leaveLabel'] for day in days[:6]],kinds)
  self.assertEqual([day['paid'] for day in days[:6]],[8,0,8,0,8,0])
  self.assertEqual([day['all'] for day in days[:6]],[8]*6)
  self.assertEqual(days[4]['otherDescription'],'Community event')
  self.assertEqual(days[5]['otherDescription'],'Community event')

 def test_new_other_types_require_a_description(self):
  for kind in ('Other paid','Other unpaid'):
   with self.subTest(kind=kind),self.assertRaisesRegex(Problem,'other leave description'):
    leave.create(self.state,self.request(kind,other=''))

 def test_legacy_types_keep_their_existing_paid_meaning(self):
  for kind,paid,category in [('Annual leave',False,'annual'),('Sick leave',True,'sick'),('Other',False,'other')]:
   with self.subTest(kind=kind):
    state,request=leave.create(self.state,self.request(kind))
    self.assertIs(request['paid'],paid)
    self.assertEqual(request['typeCategory'],category)
    state=leave.decide(state,{'id':request['id'],'revision':1,'status':'Approved'},'admin@example.nz')[0]
    day=weekly_report.week_rows(state,'2027-02-01')[0]['days'][0]
    self.assertEqual(day['paid'],8 if paid else 0)
    self.assertEqual(day['all'],8)

 def test_approved_new_type_is_required_and_added_to_payables(self):
  state=self.approved(self.request('Other paid'))
  state,entry=timesheets.save(state,self.sheet('Other paid','Community event'))
  self.assertEqual(entry['total'],8)
  self.assertEqual(entry['days'][0]['status'],'Other paid')
  day=weekly_report.week_rows(state,'2027-02-01')[0]['days'][0]
  self.assertEqual((day['other'],day['paid'],day['all']),(8,8,8))
  with self.assertRaisesRegex(Problem,'submit a leave request'):
   timesheets.save(self.state,self.sheet('Other paid','Community event'))

 def test_all_six_types_reach_the_schedule_with_the_exact_label(self):
  state,dates=self.approved_six_types()
  for kind,date in zip(self.types,dates):
   with self.subTest(kind=kind):
    block=schedule.read(state,date)['leaveBlocks'][0]
    self.assertEqual((block['leaveType'],block['type']),(kind,kind))
    self.assertEqual(block['otherDescription'],'Community event' if kind.startswith('Other') else '')

 def test_pending_detailed_leave_reaches_the_schedule_but_not_payables(self):
  state,request=leave.create(self.state,self.request('Sick leave unpaid',startDate='2027-02-08',endDate='2027-02-08'))
  block=schedule.read(state,'2027-02-08')['leaveBlocks'][0]
  self.assertEqual((block['leaveStatus'],block['leaveType'],block['type']),('Pending','Sick leave unpaid','Sick leave unpaid'))
  self.assertEqual(schedule.leave_blocks(state,'2027-02-08'),[])

 def test_new_other_time_sheet_requires_the_approved_description(self):
  state=self.approved(self.request('Other unpaid',other='Unpaid community day'))
  with self.assertRaisesRegex(Problem,'other leave description'):
   timesheets.save(state,self.sheet('Other unpaid',''))

 def test_reports_show_explicit_new_labels_and_keep_legacy_labels(self):
  state=self.approved(self.request('Paid annual leave'))
  day=weekly_report.week_rows(state,'2027-02-01')[0]['days'][0]
  self.assertEqual(weekly_export.day_annotations(day),'Paid annual leave 8h')
  pdf=weekly_report.pdf(state,{'week':'2027-02-01','mode':'all'})
  text='\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(base64.b64decode(pdf['pdf']))).pages)
  self.assertIn('Paid annual leave 8h',' '.join(text.split()))
  legacy=self.approved(self.request('Annual leave'))
  legacy_day=weekly_report.week_rows(legacy,'2027-02-01')[0]['days'][0]
  self.assertEqual(weekly_export.day_annotations(legacy_day),'Annual 8h')

 def test_workbook_keeps_exact_labels_default_shift_fields_and_paid_totals(self):
  state,dates=self.approved_six_types()
  raw=base64.b64decode(weekly_export.weekly(state,{'week':dates[0],'mode':'all'})['file'])
  sheet=openpyxl.load_workbook(io.BytesIO(raw))['Labour Report']
  for row,(kind,date) in enumerate(zip(self.types,dates),2):
   with self.subTest(kind=kind):
    self.assertEqual(sheet[f'B{row}'].value.date().isoformat(),date)
    self.assertEqual([sheet[f'{column}{row}'].value for column in 'CDEF'],['08:00','16:00',8,0])
    self.assertIn(kind,sheet[f'H{row}'].value)
    if kind.startswith('Other'):self.assertIn('Community event',sheet[f'H{row}'].value)

 def test_workbook_package_is_valid_for_excel_and_has_no_orphan_sheets(self):
  state,dates=self.approved_six_types()
  raw=base64.b64decode(weekly_export.weekly(state,{'week':dates[0],'mode':'all'})['file'])
  with zipfile.ZipFile(io.BytesIO(raw)) as package:
   self.assertIsNone(package.testzip())
   types=ET.fromstring(package.read('[Content_Types].xml'))
   defaults={item.get('Extension'):item.get('ContentType') for item in types if item.tag.rsplit('}',1)[-1]=='Default'}
   overrides={item.get('PartName'):item.get('ContentType') for item in types if item.tag.rsplit('}',1)[-1]=='Override'}
   self.assertEqual(defaults.get('xml'),'application/xml')
   self.assertEqual(overrides.get('/xl/workbook.xml'),weekly_template.WORKBOOK_MIME)
   self.assertEqual(set(overrides),{'/xl/workbook.xml','/xl/styles.xml','/xl/theme/theme1.xml','/xl/sharedStrings.xml','/xl/worksheets/sheet1.xml'})
   relationships=ET.fromstring(package.read('xl/_rels/workbook.xml.rels'))
   targets={item.get('Target') for item in relationships}
   self.assertIn('worksheets/sheet1.xml',targets)
   self.assertFalse(any('sheet2' in target for target in targets))
   root=ET.fromstring(package.read('_rels/.rels'))
   self.assertEqual(root[0].get('Target'),'xl/workbook.xml')

if __name__=='__main__':unittest.main()
