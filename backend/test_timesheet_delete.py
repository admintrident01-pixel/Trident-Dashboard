import copy, unittest
import timesheets, weekly_report, recycle, test_accounts
from core import Problem
class TimesheetDeleteTests(unittest.TestCase):
    def setUp(self):
        self.payload={'technician':'Scott Yearbury','signature':'Scott','weekStart':'2027-02-01','days':[{'status':'Work','method':'direct','hours':8}]+[{'status':'Work','method':'direct','hours':0} for _ in range(6)]}
        self.state,self.old=timesheets.save({},self.payload)
        new=copy.deepcopy(self.payload);new['days'][0]['hours']=9
        self.state,self.current=timesheets.save(self.state,new)
        self.old['submittedAt']='2027-02-01T00:00:00Z';self.current['submittedAt']='2027-02-02T00:00:00Z'
        self.body={'id':self.current['id'],'revision':1,'confirmed':True}
    def test_validation_and_immutability(self):
        before=copy.deepcopy(self.state)
        for data in [None,{**self.body,'confirmed':False},{**self.body,'revision':2},{**self.body,'id':'missing'}]:
            with self.assertRaises(Problem):timesheets.delete_submission(self.state,data)
        result=timesheets.delete_submission(self.state,self.body)
        self.assertEqual(self.state,before);self.assertNotIn(self.current['id'],result['timesheets'])
    def test_admin_delete_restore_and_report_fallback(self):
        api=test_accounts.AccountsAPI();api.setUp();api.store.state.update(copy.deepcopy(self.state))
        self.assertEqual(api.call('/api/timesheet-delete','POST',self.body,token='tech')[0],403)
        self.assertEqual(api.call('/api/timesheet-delete','POST',self.body,match=False)[0],409)
        self.assertEqual(api.call('/api/timesheet-delete','POST',self.body)[0],200)
        state=api.store.state
        deleted=state['recycleBin']['timesheet:'+self.current['id']]
        self.assertEqual(deleted['value']['signature'],'Scott');self.assertEqual(deleted['deletedBy'],test_accounts.accounts.FIRST_ADMIN)
        row=next(row for row in weekly_report.read(state,'2027-02-01')['rows'] if row['name']=='Scott Yearbury')
        self.assertEqual(row['days'][0]['work'],8)
        self.assertEqual(api.call('/api/recycle-bin','POST',{'action':'restore','ids':[deleted['id']]})[0],200)
        row=next(row for row in weekly_report.read(api.store.state,'2027-02-01')['rows'] if row['name']=='Scott Yearbury')
        self.assertEqual(row['days'][0]['work'],9)
