import base64,copy,io,unittest
import openpyxl,timesheet_drafts,timesheets,weekly_export,weekly_report,test_timesheet_release
from core import Problem

def sheet(on_call=None):
    data={'technician':'Scott Yearbury','weekStart':'2027-02-01','signature':'Scott','notes':'', 'days':[{'status':'Work','method':'direct','hours':8 if i<5 else 0,'notes':''} for i in range(7)]}
    if on_call is not None:data['onCall']=on_call
    return data

class OnCallSubmissionTests(unittest.TestCase):
    def setUp(self):
        self.user={'email':'tech@example.nz','role':'technician','technician':'Scott Yearbury'}
        self.state={'staffSettings':{'technicians':[{'name':'Scott Yearbury','rego':''}]}}

    def test_web_submission_must_answer_yes_or_no(self):
        with self.assertRaisesRegex(Problem,'on-call allowance'):
            timesheet_drafts.submit(self.state,sheet(),self.user)
        for value in ('yes','no',1,0,[]):
            with self.subTest(value=value),self.assertRaisesRegex(Problem,'on-call allowance'):
                timesheet_drafts.submit(self.state,sheet(value),self.user)
        for value in (True,False):
            with self.subTest(value=value):
                state,entry=timesheet_drafts.submit(self.state,sheet(value),self.user)
                self.assertIs(entry['onCall'],value)

    def test_corrections_keep_the_recorded_answer(self):
        state,entry=timesheets.save(self.state,sheet(True))
        change={**entry,'revision':1,'editReason':'Fix hours'}
        change.pop('onCall')
        state,updated=timesheets.edit_submission(state,change,'admin@example.nz')
        self.assertIs(updated['onCall'],True)
        legacy=copy.deepcopy(state)
        legacy['timesheets'][entry['id']].pop('onCall')
        self.assertNotIn('onCall',timesheets.edit_submission(legacy,{**change,'revision':2},'admin@example.nz')[1])

    def test_draft_round_trip_and_submit(self):
        state,draft=timesheet_drafts.save(self.state,{'technician':'Scott Yearbury','weekStart':'2027-02-01','signature':'','onCall':True,'days':[{'status':'Work','method':'direct','hours':''} for _ in range(7)]},self.user)
        self.assertIs(draft['onCall'],True)
        unresolved=timesheet_drafts.save(state,{'technician':'Scott Yearbury','weekStart':'2027-02-01','signature':'','days':draft['days'],'draftId':draft['id'],'draftRevision':draft['revision']},self.user)[1]
        self.assertIsNone(unresolved['onCall'])
        state,submitted=timesheet_drafts.submit(state,{**sheet(True),'draftId':draft['id'],'draftRevision':draft['revision']},self.user)
        self.assertIs(submitted['onCall'],True)
        self.assertEqual(state['timesheetDrafts'],{})

    def test_weekly_note_is_derived_not_stored_twice(self):
        state,entry=timesheets.save(self.state,sheet(True))
        self.assertTrue(all('On-call allowance needed' not in (day['notes'] or '') for day in entry['days']))
        self.assertEqual(entry['notes'],'')
        row=weekly_report.read(state,'2027-02-01')['rows'][0]
        self.assertEqual(row['weeklyNote'],'On-call allowance needed')
        self.assertTrue(row['onCall'])
        quiet=weekly_report.read(timesheets.save(self.state,sheet(False))[0],'2027-02-01')['rows'][0]
        self.assertEqual(quiet['weeklyNote'],'')
        self.assertFalse(quiet['onCall'])
        self.assertEqual(weekly_report.read(self.state,'2027-02-01')['rows'][0]['weeklyNote'],'')

    def test_excel_notes_column_marks_the_weekly_total_row(self):
        fixture=test_timesheet_release.ExcelExport();fixture.setUp();week=fixture.week
        quiet=openpyxl.load_workbook(io.BytesIO(base64.b64decode(weekly_export.weekly(fixture.state,{'week':week})['file'])))['Labour Report']
        self.assertIsNone(quiet['G9'].value)
        state=copy.deepcopy(fixture.state)
        for record in state['timesheets'].values():record['onCall']=True
        book=openpyxl.load_workbook(io.BytesIO(base64.b64decode(weekly_export.weekly(state,{'week':week})['file'])))['Labour Report']
        self.assertEqual(book['A9'].value,'Weekly total')
        self.assertEqual(book['G9'].value,'On-call allowance needed')
        self.assertNotEqual(book['G2'].value,'On-call allowance needed')
        self.assertIsNone(fixture.state['timesheets'][next(iter(fixture.state['timesheets']))].get('onCall'))

if __name__=='__main__':
    unittest.main()
