import base64,copy,datetime as dt,io,unittest
import openpyxl,weekly_export,weekly_template,test_timesheet_release,test_labour_leave_descriptions
from pathlib import Path

class TemplateExport(unittest.TestCase):
 def setUp(self):
  fixture=test_timesheet_release.ExcelExport();fixture.setUp();self.state=fixture.state;self.week=fixture.week
 def books(self,state=None):
  raw=base64.b64decode(weekly_export.weekly(state or self.state,{'week':self.week})['file'])
  return openpyxl.load_workbook(io.BytesIO(raw)),openpyxl.load_workbook(io.BytesIO(raw),data_only=True)
 def test_actual_times_lunch_charged_hours_and_blank_money(self):
  self.state['users']={'staff@example.invalid':{'email':'staff@example.invalid','technician':'Scott Yearbury','active':True}}
  before=copy.deepcopy(self.state);book,cached=self.books();sheet=book['Labour Report']
  self.assertEqual(sheet['A2'].value,'Scott Yearbury <staff@example.invalid>');self.assertEqual(sheet['B2'].value.date(),dt.date(2027,2,1))
  for cell,value in {'C2':0,'F2':8,'G2':17,'H2':8.5,'I2':.5}.items():self.assertEqual(sheet[cell].value,value)
  self.assertTrue(all(sheet[f'D{n}'].value is None for n in range(2,12)));self.assertIsNone(sheet['C3'].value)
  self.assertEqual(sheet['J2'].data_type,'s');self.assertEqual(self.state,before)
 def test_subtotals_have_valid_formulas_and_correct_cached_values(self):
  book,cached=self.books();self.assertEqual(book.active['C9'].value,'=SUM(C2:C8)');self.assertEqual(book.active['H9'].value,'=SUM(H2:H8)')
  self.assertEqual(cached.active['C9'].value,0);self.assertEqual(cached.active['H9'].value,8.5)
 def test_missing_submission_is_not_an_invented_shift(self):
  self.state['timesheets']={};book,_=self.books();row=book.active
  for cell in ('F2','G2','H2','I2'):self.assertIsNone(row[cell].value)
  self.assertIn('No submission',row['J2'].value);self.assertEqual(row['C2'].value,0)
 def test_other_leave_and_notes_preserved_without_private_request_reason(self):
  fixture=test_labour_leave_descriptions.LeaveDescriptions();fixture.setUp();self.week=fixture.week
  book,_=self.books(fixture.approved());sheet=book.active
  self.assertEqual(sheet['H2'].value,8);self.assertIn(fixture.description,sheet['J2'].value)
  self.assertNotIn('PRIVATE REQUEST REASON',' '.join(str(c.value) for row in sheet for c in row))
 def test_uploaded_column_sizes_font_colours_and_margins(self):
  book,_=self.books();sheet=book.active
  self.assertEqual([sheet.column_dimensions[c].width for c in ('A','B','C')],[41,12,13])
  self.assertEqual(sheet.column_dimensions['C'].max,4)
  self.assertEqual(sheet.sheet_format.defaultRowHeight,15)
  self.assertEqual(sheet.page_margins,openpyxl.worksheet.page.PageMargins(left=.7,right=.7,top=.75,bottom=.75,header=.3,footer=.3))
  self.assertIsNone(sheet.page_setup.orientation)
  for coordinate in ('A1','B1','C1','D1','A2','B2','C2','D2','A9','C9','H9'):
   cell=sheet[coordinate]
   self.assertEqual(cell.font.name,'Calibri');self.assertEqual(cell.font.sz,11)
   self.assertIn(cell.fill.patternType,(None,'none'))
   self.assertIsNone(cell.border.bottom.style)
  self.assertTrue(sheet['A1'].font.bold);self.assertFalse(sheet['A2'].font.bold)
  self.assertEqual(sheet['B2'].number_format,'mm-dd-yy')
  self.assertEqual(sheet['C2'].number_format,'0.??"";"-"0.??""')
  self.assertEqual(sheet['D2'].number_format,'"$"0.00;"$""-"0.00')
 def test_extra_fields_and_supporting_sheets_keep_their_existing_layout(self):
  sheet=self.books()[0].active
  self.assertEqual(sheet.column_dimensions['J'].width,55)
  self.assertEqual(sheet['F1'].value,'Start');self.assertEqual(sheet['J1'].value,'Notes')
  self.assertEqual(weekly_template.row_height(['Short name']),15)
  self.assertGreater(weekly_template.row_height(['x'*100]),15)
  reference=openpyxl.load_workbook(io.BytesIO(weekly_template.template()))
  book,_=self.books()
  for name in book.sheetnames[1:]:
   self.assertEqual(copy.copy(book[name]['A1'].font),copy.copy(reference[name]['A1'].font))
   self.assertEqual(copy.copy(book[name]['A1'].fill),copy.copy(reference[name]['A1'].fill))
 def test_format_is_packaged_and_contains_no_reference_workbook_records(self):
  root=Path(__file__).resolve().parent
  self.assertIn('COPY weekly_report_format.json ./',(root/'Dockerfile').read_text())
  self.assertEqual(set(weekly_template.report_format()),{'version','styles','sheetFormat','columns','pageMargins'})

if __name__=='__main__':unittest.main()
