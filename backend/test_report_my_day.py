import copy,datetime as dt,json,unittest
import weekly_report,test_accounts

class ReportMyDayTests(unittest.TestCase):
    def setUp(self):
        self.week='2026-11-02'
        self.state={'staffSettings':{'technicians':[{'name':'Alex','rego':''},{'name':'Blair','rego':''}]},
            'users':{'old@example.invalid':{'technician':'Blair'}},
            'myDayLogs':{'old@example.invalid':{'days':{self.week:{'jobs':{
                'appointment':{'technician':'Alex','title':'Private client','sessions':[{'start':'2026-11-01T20:00:00+00:00','end':'2026-11-01T21:30:00+00:00'}]},
                'custom':{'technician':'Alex','title':'Private custom job','sessions':[{'start':'2026-11-02T11:00:00+13:00','end':'2026-11-02T11:45:00+13:00'}]}
            }}}}}}

    def test_saved_and_custom_hours_use_saved_person_not_relinked_account(self):
        before=copy.deepcopy(self.state);report=weekly_report.read(self.state,self.week)
        alex,blair=report['rows']
        self.assertEqual(alex['days'][0]['myDayHours'],2.25)
        self.assertEqual(blair['days'][0]['myDayHours'],0)
        self.assertEqual(sum(d['all'] for d in alex['days']),0)
        self.assertEqual(alex['chargedHours'],[None]*7)
        self.assertEqual(self.state,before)
        for secret in ('Private client','Private custom job','old@example.invalid','sessions'):
            self.assertNotIn(secret,json.dumps(report))
        self.assertEqual(sum(d['myDayHours'] for d in weekly_report.read(self.state,'2026-11-09')['rows'][0]['days']),0)

    def test_running_timer_is_snapshot_and_clipped_at_recorded_day_end(self):
        jobs=self.state['myDayLogs']['old@example.invalid']['days'][self.week]['jobs']
        jobs.clear();jobs['running']={'technician':'Alex','sessions':[{'start':'2026-11-02T23:00:00+13:00','end':None}]}
        now=dt.datetime.fromisoformat('2026-11-02T23:30:00+13:00')
        day=weekly_report.my_day_hours(self.state,self.week,now)['alex']['days'][self.week]
        self.assertEqual(day,{'hours':.5,'running':True})
        later=now+dt.timedelta(days=2)
        day=weekly_report.my_day_hours(self.state,self.week,later)['alex']['days'][self.week]
        self.assertEqual(day,{'hours':1,'running':False})

    def test_future_manual_periods_and_zero_rows(self):
        now=dt.datetime.fromisoformat('2026-10-01T00:00:00+00:00')
        result=weekly_report.my_day_hours(self.state,self.week,now)
        self.assertEqual(result['alex']['days'][self.week]['hours'],2.25)
        self.assertFalse(result['alex']['days'][self.week]['running'])
        rows=weekly_report.read({},self.week)['rows']
        self.assertTrue(all(d['myDayHours']==0 for r in rows for d in r['days']))

    def test_admin_endpoint_never_exposes_work_log_to_tech(self):
        api=test_accounts.AccountsAPI();api.setUp()
        self.assertEqual(api.call('/api/weekly-report','GET',token='tech')[0],403)

if __name__=='__main__':unittest.main()
