import copy, datetime as dt, io, json, os, sys, threading, time, unittest
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
sys.path.insert(0, str(Path(__file__).resolve().parent))
import accounts, reminders, vehicles
from app import Application
from core import Problem

class MemoryStore:
    def __init__(self, state): self.state, self.revision, self.lock = copy.deepcopy(state), 1, threading.Lock()
    def read(self):
        with self.lock: return self.revision, copy.deepcopy(self.state)
    def commit(self, revision, state):
        with self.lock:
            if revision != self.revision: return False
            self.state, self.revision = copy.deepcopy(state), revision + 1
            return True

class AccountsAPI(unittest.TestCase):
    def setUp(self):
        rows = accounts.users({})
        rows['tech@example.nz'] = {'email':'tech@example.nz','name':'Scott','technician':'Scott Yearbury','role':'tech','active':True,'verified':True}
        self.store = MemoryStore({'users':rows,'quotes':{},'pdfs':{},'timesheets':{},'leaveRequests':{}})
        self.app = Application(self.store, object(), lambda t: accounts.FIRST_ADMIN if t == 'admin' else 'tech@example.nz' if t == 'tech' else '', 'http://127.0.0.1:18780', local=True)
    def call(self, path, method='GET', body=None, token='admin', match=True, origin='http://127.0.0.1:18780'):
        raw = json.dumps(body).encode() if body is not None else b''
        env = {'REQUEST_METHOD':method,'PATH_INFO':path,'QUERY_STRING':'','HTTP_ORIGIN':origin,'HTTP_AUTHORIZATION':'Bearer '+token if token else '', 'HTTP_IF_MATCH':f'"{self.store.revision}"' if match else '"0"','CONTENT_LENGTH':str(len(raw)),'REMOTE_ADDR':'127.0.0.1','wsgi.input':io.BytesIO(raw)}
        meta=[]; result=b''.join(self.app(env,lambda s,h:meta.append((int(s[:3]),dict(h)))))
        return meta[0][0], json.loads(result), meta[0][1]
    def test_admin_and_technician_permissions(self):
        self.assertEqual(self.call('/api/session',token='tech')[1]['role'],'tech')
        for path in ['/api/users','/api/time-settings','/api/staff-settings','/api/quote-settings','/api/catalog','/api/drafts','/api/workbook','/api/pdf','/api/reminder-dashboard','/api/reminder-settings','/api/mail-outbox']:
            self.assertEqual(self.call(path,token='tech')[0],403,path)
        for path in ['/api/users','/api/user-invite','/api/send-reminder','/api/reminder-settings','/api/leave-decision','/api/quote-save','/api/vehicles']:
            self.assertEqual(self.call(path,'POST',{},token='tech')[0],403,path)
        self.assertEqual(self.call('/api/vehicles',token='tech')[0],200)
        config=self.call('/api/timesheets/config',token='tech')[1]
        self.assertEqual(config['technicians'],['Scott Yearbury'])
        self.assertEqual(config['lockedTechnician'],'Scott Yearbury')
    def test_technician_cannot_impersonate_another_person(self):
        for path in ['/api/timesheets','/api/leave']:
            self.assertEqual(self.call(path,'POST',{'technician':'Another person'},token='tech')[0],403)
        status,body,_=self.call('/api/leave','POST',{'technician':'Scott Yearbury','leaveType':'Annual leave','startDate':'2027-02-01','endDate':'2027-02-01','hoursPerDay':8,'reason':'Holiday'},token='tech')
        self.assertEqual(status,200)
        self.assertEqual(body['request']['submittedBy'],'tech@example.nz')
        self.assertEqual(len(self.call('/api/leave',token='tech')[1]['requests']),1)
        self.store.state['leaveRequests']['other']={**body['request'],'technician':'Andrew Thomas'}
        self.assertEqual(len(self.call('/api/leave',token='tech')[1]['requests']),1)
    def test_technician_cannot_edit_saved_vehicle_check_or_backdate(self):
        self.assertEqual(self.call('/api/vehicle-checks','POST',{'id':'old'},token='tech')[0],403)
        self.assertEqual(self.call('/api/vehicle-checks','POST',{'checkDate':'2020-01-01'},token='tech')[0],403)
    def test_email_confirmation_single_use_and_logout(self):
        status,data,_=self.call('/api/auth/request','POST',{'email':accounts.FIRST_ADMIN},token='')
        self.assertEqual(status,200)
        self.assertIn('no email',data['message'].lower())
        link=data['previewLink'].split('#confirm=')[1]
        self.assertNotIn(link,self.store.state['loginLinks'])
        status,session,_=self.call('/api/auth/confirm','POST',{'token':link},token='')
        self.assertEqual(status,200)
        self.assertTrue(session['verified'])
        self.assertEqual(session['role'],'admin')
        self.assertEqual(self.call('/api/auth/confirm','POST',{'token':link},token='')[0],401)
        self.assertEqual(self.call('/api/session',token=session['token'])[0],200)
        self.assertEqual(self.call('/api/auth/logout','POST',token=session['token'])[0],200)
        self.assertEqual(self.call('/api/session',token=session['token'])[0],401)
    def test_expired_confirmation_and_session(self):
        r=accounts.issue(self.store.state,accounts.FIRST_ADMIN,'http://127.0.0.1:18780',invitation=True)
        raw=list(r['mailOutbox'].values())[-1]['body'].split('#confirm=')[1].split('\n')[0]
        r['loginLinks'][accounts.digest(raw)]['expires']=0
        with self.assertRaises(Problem):accounts.consume(r,raw)
        self.store.state['sessions']={accounts.digest('trident_expired'):{'email':accounts.FIRST_ADMIN,'expires':0}}
        self.assertEqual(self.call('/api/session',token='trident_expired')[0],401)
    def confirmed_session(self, remember=False):
        status,data,_=self.call('/api/auth/request','POST',{'email':accounts.FIRST_ADMIN},token='')
        self.assertEqual(status,200)
        link=data['previewLink'].split('#confirm=')[1]
        return self.call('/api/auth/confirm','POST',{'token':link,'remember':remember},token='')[1]
    def test_password_setup_login_and_recovery_revokes_old_sessions(self):
        session=self.confirmed_session()
        password='a long private password'
        self.assertEqual(self.call('/api/auth/password','POST',{'password':'short'},token=session['token'])[0],400)
        self.assertEqual(self.call('/api/auth/password','POST',{'password':password},token=session['token'])[0],200)
        stored=self.store.state['passwords'][accounts.FIRST_ADMIN]
        self.assertNotIn(password,json.dumps(stored))
        self.assertEqual(self.call('/api/auth/password','POST',{'password':password},token=session['token'])[0],403)
        status,login,_=self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':password,'remember':True},token='')
        self.assertEqual(status,200)
        self.assertTrue(login['hasPassword'])
        self.assertGreater(self.store.state['sessions'][accounts.digest(login['token'])]['expires'],time.time()+29*86400)
        self.assertEqual(self.call('/api/auth/password','POST',{'password':password},token=login['token'])[0],403)
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'wrong password'},token='')[0],401)
        self.store.state['loginRates']={}
        reset=self.confirmed_session()
        self.assertEqual(self.call('/api/auth/password','POST',{'password':'a new private password'},token=reset['token'])[0],200)
        self.assertEqual(self.call('/api/session',token=login['token'])[0],401)
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':password},token='')[0],401)
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'a new private password'},token='')[0],200)
        self.assertNotIn('passwords',self.call('/api/users')[1])
    def test_password_attempts_throttled_and_cannot_bypass_confirmation(self):
        self.store.state['passwords']={accounts.FIRST_ADMIN:accounts.password_hash('a long private password')}
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'a long private password'},token='')[0],401)
        for _ in range(9):
            self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'wrong'},token='')[0],401)
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'wrong'},token='')[0],429)
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'a long private password'},token='',origin='https://evil.nz')[0],403)
        self.assertEqual(self.call('/api/auth/password','POST',{'password':'a long private password'},token='admin')[0],403)
    def test_password_setup_recent_email_required_and_disabled_account_blocked(self):
        session=self.confirmed_session()
        self.store.state['sessions'][accounts.digest(session['token'])]['emailVerifiedAt']=time.time()-901
        self.assertEqual(self.call('/api/auth/password','POST',{'password':'a long private password'},token=session['token'])[0],403)
        self.store.state['users'][accounts.FIRST_ADMIN].update(active=False,verified=True)
        self.store.state['passwords']={accounts.FIRST_ADMIN:accounts.password_hash('a long private password')}
        self.assertEqual(self.call('/api/auth/login','POST',{'email':accounts.FIRST_ADMIN,'password':'a long private password'},token='')[0],401)
    def test_disable_account_revokes_access(self):
        status,_,_=self.call('/api/users','POST',{**self.store.state['users']['tech@example.nz'],'active':False})
        self.assertEqual(status,200)
        self.assertEqual(self.call('/api/session',token='tech')[0],403)
    def test_roles_are_read_from_storage_each_request(self):
        self.assertEqual(self.call('/api/users',token='tech')[0],403)
        self.store.state['users']['tech@example.nz']['role']='admin'
        self.assertEqual(self.call('/api/users',token='tech')[0],200)
        self.store.state['users']['tech@example.nz']['role']='tech'
        self.assertEqual(self.call('/api/users',token='tech')[0],403)
    def test_user_validation_and_admin_lockout(self):
        bala=self.store.state['users'][accounts.FIRST_ADMIN]
        self.assertEqual(self.call('/api/users','POST',{**bala,'role':'tech'})[0],400)
        self.assertEqual(self.call('/api/users','POST',{**bala,'active':False})[0],400)
        tech=self.store.state['users']['tech@example.nz']
        self.assertEqual(self.call('/api/users','POST',{**tech,'technician':''})[0],400)
        self.assertEqual(self.call('/api/users','POST',{**tech,'role':'owner'})[0],400)
        self.assertEqual(self.call('/api/users','POST',{**tech,'email':'x\r\nBcc:test@bad.nz'})[0],400)
        self.assertEqual(self.call('/api/users','POST',tech,match=False)[0],409)
    def test_signin_rate_limit_and_origin(self):
        self.assertEqual(self.call('/api/auth/request','POST',{'email':'unknown@example.nz'},token='')[0],200)
        self.assertEqual(self.call('/api/auth/request','POST',{'email':'unknown@example.nz'},token='')[0],429)
        self.assertEqual(self.call('/api/auth/request','POST',{'email':accounts.FIRST_ADMIN},token='',origin='https://evil.nz')[0],403)
    def test_invite_preview_and_no_unconfigured_production_delivery(self):
        self.assertEqual(self.call('/api/user-invite','POST',{'email':accounts.FIRST_ADMIN})[0],200)
        self.assertEqual(self.call('/api/mail-outbox')[1]['messages'][0]['status'],'preview')
        self.app.local=False
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(self.call('/api/auth/request','POST',{'email':accounts.FIRST_ADMIN},token='')[0],503)
    def test_scheduler_requires_private_job_token(self):
        self.assertEqual(self.call('/api/reminders/run','POST',token='admin')[0],401)
        with patch.dict(os.environ,{'REMINDER_JOB_TOKEN':'job-secret'}):
            self.assertEqual(self.call('/api/reminders/run','POST',token='job-secret')[0],200)

class ReminderRules(unittest.TestCase):
    def setUp(self):
        self.now=dt.datetime(2026,10,9,12,tzinfo=ZoneInfo('Pacific/Auckland'))
        self.state={'staffSettings':{'technicians':[{'name':'Scott','rego':'ABC123','hasVehicle':True}]},'users':{'test@example.nz':{'email':'test@example.nz','name':'Test','role':'tech','active':True,'verified':True,'technician':'Scott'}},'vehicles':[{'id':'V1','driver':'Scott','active':True,'registration':'ABC123','baseline':{'checkDate':'2026-09-16'}}]}
    def test_weekly_deadline_and_vehicle_due(self):
        rows=reminders.dashboard(self.state,self.now)
        vehicle=next(r for r in rows if r['kind']=='vehicle')
        self.assertEqual(vehicle['due'],'2026-10-16')
        self.assertEqual(vehicle['daysRemaining'],7)
        sheet=next(r for r in rows if r.get('weekStart')=='2026-10-05')
        self.assertEqual(sheet['hoursRemaining'],5)
        self.assertIn('+13:00',sheet['due'])
    def test_latest_check_drives_deadline_and_submission_stops_sheet_reminder(self):
        self.state['vehicleChecks']={'a':{'vehicleId':'V1','checkDate':'2026-10-01','createdAt':'2026-10-01'}}
        self.state['timesheets']={'s':{'technician':'Scott','weekStart':'2026-10-05'}}
        rows=reminders.dashboard(self.state,self.now)
        self.assertEqual(next(r for r in rows if r['kind']=='vehicle')['due'],'2026-10-31')
        self.assertFalse(any(r.get('weekStart')=='2026-10-05' for r in rows))
    def test_saved_expiry_drives_reminder(self):
        self.state['vehicleChecks']={'a':{'vehicleId':'V1','checkDate':'2026-10-01','nextCheckDue':'2026-10-20','createdAt':'2026-10-01'}}
        row=next(r for r in reminders.dashboard(self.state,self.now) if r['kind']=='vehicle')
        self.assertEqual(row['due'],'2026-10-20')
        self.assertEqual(row['daysRemaining'],11)
    def test_configurable_deadline_and_automatic_deduplication(self):
        cfg={**reminders.DEFAULTS,'timesheetWeekday':6,'timesheetTime':'18:30','automaticVehicles':True,'automaticTimesheets':True}
        state=reminders.save_settings(self.state,cfg)
        sheet=next(r for r in reminders.dashboard(state,self.now) if r.get('weekStart')=='2026-10-05')
        self.assertIn('2026-10-11T18:30',sheet['due'])
        state,count=reminders.due_reminders(state,self.now)
        self.assertGreater(count,0)
        repeated,count2=reminders.due_reminders(state,self.now)
        self.assertEqual(count2,0)
        self.assertEqual(len(repeated['mailOutbox']),count)
    def test_missing_driver_email_and_unconfirmed_recipient(self):
        row=next(r for r in reminders.dashboard(self.state,self.now) if r['kind']=='vehicle')
        row['recipient']=''
        with self.assertRaises(Problem):reminders.enqueue_reminder(self.state,row)
        self.state['users']['test@example.nz']['verified']=False
        row['recipient']='test@example.nz'
        with self.assertRaises(Problem):reminders.enqueue_reminder(self.state,row)
    def test_local_mode_never_sends_smtp(self):
        reminders.queue(self.state,'test@example.nz','Test','Body','vehicle')
        store=MemoryStore(self.state)
        with patch('smtplib.SMTP') as smtp:
            reminders.deliver(store,local=True)
            smtp.assert_not_called()
        self.assertEqual(next(iter(store.state['mailOutbox'].values()))['status'],'preview')
    def test_smtp_success_failure_and_claim_no_duplicate(self):
        reminders.queue(self.state,'test@example.nz','Test','Body','vehicle')
        store=MemoryStore(self.state)
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.example.nz','SMTP_FROM':'noreply@example.nz'}),patch('smtplib.SMTP') as smtp:
            reminders.deliver(store)
            reminders.deliver(store)
            self.assertEqual(smtp.return_value.__enter__.return_value.send_message.call_count,1)
        self.assertEqual(next(iter(store.state['mailOutbox'].values()))['status'],'sent')
        reminders.queue(store.state,'test@example.nz','Test 2','Body','vehicle')
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.example.nz','SMTP_FROM':'noreply@example.nz'}),patch('smtplib.SMTP',side_effect=OSError):reminders.deliver(store)
        self.assertEqual(list(store.state['mailOutbox'].values())[-1]['status'],'failed')
    def test_reminder_validation(self):
        for cfg in [{**reminders.DEFAULTS,'timesheetWeekday':7},{**reminders.DEFAULTS,'timesheetTime':'25:00'},{**reminders.DEFAULTS,'vehicleLeadDays':-1}]:
            with self.assertRaises(Problem):reminders.save_settings(self.state,cfg)

if __name__=='__main__':unittest.main()
