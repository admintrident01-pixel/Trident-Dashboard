import base64,io,json,logging,os,random,time,uuid

from urllib.parse import parse_qs

from core import Problem,decode,save_quote,workbook_info

from storage import BigQueryStore,CloudObjects

import timesheets
import stock, stock_import, stock_reports, stocktake_sessions
import timesheet_drafts

import vehicles

import leave

import quote_settings

import labour

import schedule
import office_files
import schedule_history
import schedule_live

import staff_setup

import weekly_report
import weekly_export

import recycle

import accounts,reminders,secrets

MAX_BODY=40*1024*1024

OWNER='nikita.trident2024@gmail.com'

def google_user(token):

 from google.auth.transport.requests import Request

 from google.oauth2.id_token import verify_oauth2_token

 try:claims=verify_oauth2_token(token,Request(),os.environ['GOOGLE_CLIENT_ID'])

 except Exception:raise Problem(401,'Sign in again with Google.')

 if claims.get('iss') not in ('accounts.google.com','https://accounts.google.com') or claims.get('email_verified') is not True:raise Problem(401,'Google account verification failed.')

 return claims.get('email','').lower()

class Application:

 def __init__(self,store=None,objects=None,verify=google_user,origin=None,local=False,stock_source=None):self.stock_source=stock_source;self.store=store;self.objects=objects;self.verify=verify;self.origin=origin or os.environ.get('FRONTEND_ORIGIN','');self.local=local

 def body(self,environ):

  try:length=int(environ.get('CONTENT_LENGTH') or 0)

  except ValueError:raise Problem(400,'Invalid request size.')

  if length<1 or length>MAX_BODY:raise Problem(400,'Upload exceeds the allowed size.')

  raw=environ['wsgi.input'].read(length)

  if len(raw)!=length:raise Problem(400,'Incomplete upload.')

  try:data=json.loads(raw)

  except Exception:raise Problem(400,'Invalid request.')

  if not isinstance(data,dict):raise Problem(400,'Invalid request.')

  return data

 def commit(self,revision,state,actor='',capture=True,before=None):

  live_enabled=bool(schedule_live.configuration()[0])
  live_before=before

  if capture:

   if before is None:
    current,before=self.store.read()
   else:current=revision

   if current!=revision:raise Problem(409,'Another change was saved. Refresh and try again.')

   state=recycle.capture(before,state,actor)

   live_before=before

  elif live_enabled and live_before is None:_,live_before=self.store.read()

  if not self.store.commit(revision,state):raise Problem(409,'Another change was saved. Refresh and try again.')

  if live_enabled and live_before is not None and schedule_history.etag(live_before)!=schedule_history.etag(state):schedule_live.notify()

 def account_request(self,environ):

  path=environ['PATH_INFO'];p=self.body(environ)

  revision,state=self.store.read()

  if path=='/api/auth/request':

   address=accounts.email(p.get('email'));reminders.require_mail(self.local)

   result=accounts.issue(state,address,self.origin,environ.get('REMOTE_ADDR',''))

   payload={'message':'If this email has an active Trident account, a confirmation link will be sent. Check your inbox.'}

   if self.local:

    mail=next((m for m in reversed(list(result.get('mailOutbox',{}).values())) if m['to']==address and m['status']=='queued'),None)

    if mail:payload.update(message='Local preview only. No email was sent. Open the confirmation link below.',previewLink=mail['body'].split('\n')[3])

  elif path=='/api/auth/login':result,payload=accounts.password_login(state,p,environ.get('REMOTE_ADDR',''))

  else:result,payload=accounts.consume(state,p.get('token'),p.get('remember',False))

  self.commit(revision,result)

  if payload is None:raise Problem(401,'Email or password is incorrect. Use an email link to set or reset your password.')

  if path=='/api/auth/request':reminders.deliver(self.store,self.local)

  return payload

 def leave_request(self,revision,state,data,token,verified_email,submitted):
  # The browser's global ETag can be hours old. Rebase this scoped command on
  # current state; the CAS still atomically protects leave, permissions and mail.
  # Legacy clients receive a stable key for this request's internal retries.
  data={**data,'operationId':data.get('operationId',uuid.uuid4().hex)}
  for attempt in range(7):
   if attempt:
    try:revision,state=self.store.read()
    except Problem:raise
    except Exception:
     logging.warning('Leave save could not read the current register; retrying.')
     if attempt<6:time.sleep(random.uniform(.025,min(.25,.025*2**attempt)))
     continue
   # Recheck session revocation, current role and technician assignment for
   # every candidate write. The external identity was verified at request entry.
   user=accounts.resolve(state,token,lambda _:verified_email)
   if submitted:accounts.own(user,data.get('technician'))
   else:accounts.admin(user)
   result,entry,replayed=leave.operation(state,data,user['email'],submitted)
   if replayed:return revision,state,entry,True
   result=recycle.capture(state,result,user['email'])
   try:committed=self.store.commit(revision,result)
   except Problem:raise
   except Exception:
    # A database timeout may happen after commit. The next read recovers the
    # receipt; racing retries share the same key and cannot create two events.
    committed=False;logging.warning('Leave save outcome uncertain; checking its receipt.')
   if committed:
    if schedule_live.configuration()[0] and schedule_history.etag(state)!=schedule_history.etag(result):schedule_live.notify()
    return revision+1,result,entry,False
   if attempt<6:time.sleep(random.uniform(.025,min(.25,.025*2**attempt)))
  raise Problem(503,'Leave saving is busy or its result could not be confirmed. Your details are kept. Try the same save again; it will not create a duplicate.')

 def __call__(self,environ,start_response):

  status=200;headers=[('Cache-Control','no-store'),('X-Content-Type-Options','nosniff')];mime='application/json';payload=None

  origin=environ.get('HTTP_ORIGIN','');method=environ['REQUEST_METHOD'];path=environ['PATH_INFO']

  if origin==self.origin and origin:headers += [('Access-Control-Allow-Origin',origin),('Vary','Origin'),('Access-Control-Expose-Headers','ETag')]

  try:

   if method=='OPTIONS':

    if origin!=self.origin or not origin:raise Problem(403,'Origin is not allowed.')

    headers += [('Access-Control-Allow-Methods','GET,POST,OPTIONS'),('Access-Control-Allow-Headers','Authorization,Content-Type,If-Match,If-None-Match,X-Quote-Token')];payload={}

   elif path=='/api/health':payload={'ok':True,'version':'C'}

   elif path in ('/api/auth/request','/api/auth/confirm','/api/auth/login') and method=='POST':

    if origin!=self.origin or not origin:raise Problem(403,'Open the approved Trident website to sign in.')

    if self.store is None:self.store=BigQueryStore()

    payload=self.account_request(environ)

   elif path in ('/api/reminders/run','/api/reminders/check') and method=='POST':

    expected=os.environ.get('REMINDER_JOB_TOKEN','')

    if not expected or not secrets.compare_digest(environ.get('HTTP_AUTHORIZATION',''),'Bearer '+expected):raise Problem(401,'Scheduler authentication required.')

    if self.store is None:self.store=BigQueryStore()

    if path=='/api/reminders/check':
     _,state=self.store.read();_,count=reminders.due_reminders(state)
     payload={'checked':True,'wouldQueue':count,'emailMode':reminders.mail_mode(self.local)}
    else:
     reminders.require_mail(self.local)

     for attempt in range(5):

      revision,state=self.store.read();result,count=reminders.due_reminders(state)

      if self.store.commit(revision,result):break

     else:raise Problem(409,'A newer change was saved. Run the job again.')

     processed=reminders.deliver(self.store,self.local)
     reminders.record_run(self.store,count,processed)
     payload={'queued':count,'processed':processed}

   else:

    if origin and origin!=self.origin:raise Problem(403,'Origin is not allowed.')

    auth=environ.get('HTTP_AUTHORIZATION','')

    if not auth.startswith('Bearer '):raise Problem(401,'Sign in with your work email.')

    if self.store is None:self.store=BigQueryStore()

    revision,state=self.store.read()

    user=accounts.resolve(state,auth[7:],self.verify);email=user['email']

    if method=='POST' and origin!=self.origin:raise Problem(403,'Save requests must come from the approved website.')

    if path=='/api/session' and method=='GET':payload={**user,'hasPassword':email in state.get('passwords',{}),'token':'cloud','workbook':'Trident-Quote-Settings.xlsx'}

    elif path=='/api/auth/password' and method=='POST':

     state=accounts.set_password(state,user,auth[7:],self.body(environ).get('password'));self.commit(revision,state,actor=email);payload={'saved':True,'hasPassword':True}

    elif path=='/api/auth/logout' and method=='POST':

     state.get('sessions',{}).pop(accounts.digest(auth[7:]),None);self.commit(revision,state,actor=email);payload={'signedOut':True}

    else:

     if self.store is None:self.store=BigQueryStore()

     if self.objects is None:self.objects=CloudObjects()

     # Authorise and save against the same snapshot; a concurrent privilege

     # change invalidates the compare-and-swap rather than using stale access.

     headers.append(('ETag',f'"{revision}"'))

     admin_paths=('/api/schedule-notes','/api/recycle-bin','/api/schedule-settings','/api/labour-settings','/api/staff-settings','/api/time-settings','/api/quote-settings','/api/catalog','/api/drafts','/api/workbook','/api/pdf','/api/quote-save','/api/users','/api/user-invite','/api/reminder-settings','/api/reminder-dashboard','/api/send-reminder','/api/mail-outbox','/api/mail-archive','/api/leave-decision','/api/timesheet-edit','/api/timesheet-delete','/api/vehicle-order')

     if path.startswith('/api/office-files') or path.startswith('/api/stock') or path in admin_paths or path in ('/api/staff-setup','/api/weekly-report','/api/weekly-report-notes','/api/weekly-report-save','/api/weekly-report-pdf','/api/weekly-report-excel','/api/report-periods-excel','/api/report-periods','/api/report-periods-pdf') or (path in ('/api/vehicles','/api/schedule','/api/schedule/travel') and method=='POST'):accounts.admin(user)

     if path=='/api/schedule/live-ticket' and method=='GET':payload=schedule_live.ticket()
     elif path=='/api/office-files' and method=='GET':payload=office_files.listing(state)
     elif path=='/api/office-files/content' and method=='GET':payload=office_files.read(state,parse_qs(environ.get('QUERY_STRING','')).get('id',[''])[0],self.objects)
     elif path=='/api/office-files' and method=='POST':
      accounts.admin(user)
      payload=office_files.action(state,self.body(environ),user,self.objects,lambda result:self.commit(revision,result,actor=email))
     elif path=='/api/stock' and method=='GET':payload=stock.read(state)
     elif path=='/api/stocktake' and method=='GET':payload=stocktake_sessions.read(state,email)
     elif path=='/api/stocktake' and method=='POST':
      state=stocktake_sessions.action(state,self.body(environ),email);self.commit(revision,state,actor=email);payload=stocktake_sessions.read(state,email)
      headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/stock-report' and method=='POST':payload=stock_reports.create(state,self.body(environ),self.stock_source if self.local else None)
     elif path=='/api/stock-export' and method=='GET':
      raw=stock_import.export(state,self.stock_source if self.local else None);payload={'name':'Trident Community Equipment SOH '+stock.dt.datetime.now(stock.ZoneInfo('Pacific/Auckland')).strftime('%d.%m.%Y')+'.xlsx','workbook':base64.b64encode(raw).decode()}
     elif path=='/api/stock-source-preview' and method=='GET':
      if not self.local or not self.stock_source:raise Problem(404,'Choose an XLSX workbook to preview.')
      payload=stock_import.preview(self.stock_source,'Trident Community Equipment SOH 09.10.2026.xlsx')
     elif path in ('/api/stock-import-preview','/api/stock-import') and method=='POST':
      p=self.body(environ)
      if p.get('useLocalSource'):
       if not self.local or not self.stock_source:raise Problem(404,'The local stock source is unavailable.')
       raw=self.stock_source
      else:
       try:raw=base64.b64decode(p.get('workbook',''),validate=True)
       except Exception:raise Problem(400,'Choose a valid XLSX workbook.')
      candidate=stock_import.preview(raw,p.get('name','Stock workbook.xlsx'))
      if path=='/api/stock-import-preview':payload=candidate
      else:
       if p.get('confirmed') is not True:raise Problem(400,'Confirm importing product rows for review.')
       if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Stock changed. Refresh before importing.')
       state=stock_import.apply(state,candidate,email,raw);self.commit(revision,state,actor=email);payload={'saved':True,'message':'Opening product quantities loaded. Assign their existing asset numbers before allocation.'};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/stock' and method=='POST':
      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Stock changed. Refresh and try again.')
      state=stock.action(state,self.body(environ),email)
      if self.local and self.stock_source and not state['stock'].get('workbookTemplate'):state['stock']['workbookTemplate']=base64.b64encode(self.stock_source).decode()
      self.commit(revision,state,actor=email);payload={'saved':True,'message':'Stock record saved.'};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/recycle-bin' and method=='GET':payload=recycle.read(state)

     elif path=='/api/recycle-bin' and method=='POST':

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'The recycle bin changed. Refresh before trying again.')

      state,garbage=recycle.action(state,self.body(environ),user);self.commit(revision,state,capture=False);payload={'saved':True}

      for key in garbage:

       try:self.objects.delete(key)

       except Exception:logging.warning('A permanently deleted PDF needs storage cleanup.')

      headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))

     elif path=='/api/schedule' and method=='GET':
      tag=schedule_history.etag(state);headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',tag))
      payload={'unchanged':True} if environ.get('HTTP_IF_NONE_MATCH') in (tag,f'"{revision}"') and not schedule.schedule_links.active(state) else schedule_history.read(state,parse_qs(environ.get('QUERY_STRING','')).get('date',[''])[0],user)
      editing=parse_qs(environ.get('QUERY_STRING','')).get('appointment',[''])[0]
      if editing and user.get('role')=='admin' and not payload.get('unchanged'):payload['editingAppointment']=state.get('appointments',{}).get(editing)

     elif path=='/api/schedule' and method=='POST':

      if environ.get('HTTP_IF_MATCH') not in (f'"{revision}"',schedule_history.etag(state)):raise Problem(409,'The schedule changed while you were editing. Your edit has been kept; refresh to review the latest schedule.')

      p=self.body(environ);before=state;state,appointment=schedule.save(state,p,user);mail_ids=[]

      if p.get('sendEmail') is True:

       reminders.require_mail(self.local);state,mail_ids=schedule.queue_appointment_email(state,appointment)

      state=schedule_history.record(before,state,email,appointment['date'],'Appointment '+p.get('action','save'));self.commit(revision,state,actor=email,before=before);saved_revision=revision+1;payload={'saved':True,'appointment':appointment,'schedule':schedule_history.read(state,appointment['date'],user)}

      if mail_ids:

       reminders.deliver(self.store,self.local)

       saved_revision,current=self.store.read();statuses=[current['mailOutbox'][mid]['status'] for mid in mail_ids];payload['schedule']=schedule_history.read(current,appointment['date'],user)

       payload['message']='Email previews saved; no emails sent.' if self.local else f"Appointment saved. Emails sent: {statuses.count('sent')}; failed: {statuses.count('failed')}; pending: {len(statuses)-statuses.count('sent')-statuses.count('failed')}."

      headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',schedule_history.etag(current if mail_ids else state)))

     elif path=='/api/schedule/travel' and method=='POST':
      if environ.get('HTTP_IF_MATCH') not in (f'"{revision}"',schedule_history.etag(state)):raise Problem(409,'The schedule changed. Refresh and try again.')
      p=self.body(environ);before=state
      if p.get('action') in ('undo','redo'):state=schedule_history.apply(state,email,schedule.day(p.get('date')),p['action'])
      else:
       state=schedule.save_travel(state,p,user);state=schedule_history.record(before,state,email,p['date'],{'move_selection':'Move selected blocks','move_to_date':'Move selected to another date','delete_selection':'Delete selected blocks','pack_gap':'Close schedule gap','snap_gap':'Snap and link blocks','travel_next':'Travel to next appointment','link':'Change block link','recalculate':'Calculate travel'}.get(p.get('action'),'Change schedule blocks'))
      self.commit(revision,state,actor=email,before=before);payload=schedule_history.read(state,p['date'],user);headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',schedule_history.etag(state)))
     elif path=='/api/schedule-notes' and method=='GET':payload=schedule.schedule_notes.read(state)
     elif path=='/api/schedule-notes' and method=='POST':
      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'The schedule changed. Refresh and try again.')
      before=state;state=schedule.schedule_notes.save(state,self.body(environ),user);self.commit(revision,state,actor=email,before=before);payload=schedule.schedule_notes.read(state);headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/schedule-settings' and method=='GET':payload=schedule.settings(state)

     elif path=='/api/schedule-settings' and method=='POST':

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Schedule settings changed. Reload before saving.')

      state=schedule.save_settings(state,self.body(environ));self.commit(revision,state,actor=email);payload={'saved':True};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))

     elif path=='/api/labour-settings' and method=='GET':payload=labour.read(state)

     elif path=='/api/labour-settings' and method=='POST':

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh and try again.')

      state=labour.save(state,self.body(environ));self.commit(revision,state,actor=email);payload={'saved':True};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))

     elif path=='/api/weekly-report' and method=='GET':payload=weekly_report.read(state,parse_qs(environ.get('QUERY_STRING','')).get('week',[''])[0],parse_qs(environ.get('QUERY_STRING','')).get('comparison',[None])[0])

     elif path=='/api/report-periods' and method=='POST':payload=weekly_report.selected_period(state,self.body(environ))
     elif path=='/api/report-periods-pdf' and method=='POST':payload=weekly_report.period_pdf(state,self.body(environ))

     elif path=='/api/weekly-report-save' and method=='POST':
      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh the report before saving.')
      state=weekly_report.save_report(state,self.body(environ));self.commit(revision,state,actor=email);payload={'saved':True};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/weekly-report-notes' and method=='POST':

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh this report before saving notes.')

      state=weekly_report.save_notes(state,self.body(environ));self.commit(revision,state,actor=email);payload={'saved':True};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))

     elif path=='/api/weekly-report-excel' and method=='POST':payload=weekly_export.weekly(state,self.body(environ))
     elif path=='/api/report-periods-excel' and method=='POST':payload=weekly_export.period(state,self.body(environ))
     elif path=='/api/weekly-report-pdf' and method=='POST':payload=weekly_report.pdf(state,self.body(environ))

     elif path=='/api/staff-setup' and method=='GET':payload={**staff_setup.read(state),'emailMode':reminders.mail_mode(self.local)}

     elif path=='/api/staff-setup' and method=='POST':

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Reload staff setup before saving.')

      p=self.body(environ);state=staff_setup.delete(state,p,user) if p.get('action')=='delete' else staff_setup.save(state,p,user);self.commit(revision,state,actor=email);payload={'saved':True};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))

     elif path=='/api/users' and method=='GET':payload={'users':[accounts.public(u) for u in accounts.users(state).values()],'technicians':timesheets.settings(state)['technicians']}

     elif path=='/api/reminder-settings' and method=='GET':payload={**reminders.settings_view(state),'emailMode':reminders.mail_mode(self.local),'scheduler': 'local' if self.local else 'external','schedulerStatus':reminders.scheduler_status(state,self.local)}

     elif path=='/api/reminder-dashboard' and method=='GET':payload={'items':reminders.dashboard(state),'emailMode':reminders.mail_mode(self.local)}

     elif path=='/api/timesheet-delete' and method=='POST':
      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh history before deleting.')
      state=timesheets.delete_submission(state,self.body(environ));self.commit(revision,state,actor=email);payload={'saved':True,'message':'Time sheet moved to the Recycle bin. Labour payables now uses the remaining current submission.'};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/mail-archive' and method=='POST':
      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh emails and try again.')
      state=reminders.archive_mail(state,self.body(environ),email);self.commit(revision,state,actor=email);payload={'saved':True};headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))
     elif path=='/api/mail-outbox' and method=='GET':payload={'messages':[{k:v for k,v in m.items() if k!='body' or self.local} for m in reversed(list(state.get('mailOutbox',{}).values()))]}

     elif path in ('/api/users','/api/user-invite','/api/reminder-settings','/api/send-reminder') and method=='POST':

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh and try again.')

      p=self.body(environ)

      if path=='/api/users':state=accounts.save_user(state,p,user);payload={'saved':True}

      elif path=='/api/reminder-settings':state=reminders.save_settings(state,p);payload={'saved':True}

      elif path=='/api/user-invite':

       reminders.require_mail(self.local);address=accounts.email(p.get('email'))

       if address not in accounts.users(state) or not accounts.users(state)[address]['active']:raise Problem(400,'Save an active user before sending an invitation.')

       state=accounts.issue(state,address,self.origin,invitation=True);payload={'saved':True,'message':'Confirmation email queued.'}

      else:

       reminders.require_mail(self.local);row=next((r for r in reminders.dashboard(state) if r['id']==p.get('id')),None)

       if not row:raise Problem(404,'This reminder is no longer due or the vehicle was removed.')

       if p.get('recipient'):
        recipient=accounts.email(p['recipient']);target=accounts.users(state).get(recipient)
        if row['kind']!='vehicle' or not target or not target.get('active') or target.get('technician')!=row['name']:raise Problem(400,'Choose the email linked to this vehicle’s staff member.')
        row={**row,'recipient':recipient}
       reminders.enqueue_reminder(state,row);payload={'saved':True,'message':'Reminder queued.'}

      self.commit(revision,state)

      if path in ('/api/user-invite','/api/send-reminder'):

       reminders.deliver(self.store,self.local);payload['message']='Email preview saved; no email sent.' if self.local else 'Delivery attempted. Check Email history for the result.'

      headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{self.store.read()[0]}"'))

     elif path=='/api/timesheets/config' and method=='GET':

      payload=timesheets.config(state);payload['preferredTechnician']=user.get('technician','')

      if user['role']!='admin':payload.update(technicians=[user['technician']] if user['technician'] else [],lockedTechnician=user['technician'],approvedLeave=[r for r in payload['approvedLeave'] if r['technician']==user['technician']])

     elif path=='/api/staff-settings' and method=='GET':payload=timesheets.settings(state)

     elif path=='/api/time-settings' and method=='GET':payload=state.get('timeSettings',{'start':'07:30','finish':'16:00'})

     elif path=='/api/quote-settings' and method=='GET':payload=quote_settings.read(state)

     elif path=='/api/leave' and method=='GET':payload={'requests':[r for r in state.get('leaveRequests',{}).values() if user['role']=='admin' or r['technician']==user['technician']],'technicians':[t for t in timesheets.settings(state)['technicians'] if user['role']=='admin' or t['name']==user['technician']]}

     elif path in ('/api/leave','/api/leave-decision') and method=='POST':
      saved_revision,saved_state,entry,replayed=self.leave_request(revision,state,self.body(environ),auth[7:],email,path=='/api/leave')
      payload={'saved':True,'request':entry,'replayed':replayed}
      try:
       if reminders.mail_mode(self.local)!='unconfigured':reminders.deliver(self.store,self.local)
       saved_revision,_=self.store.read()
      except Exception:logging.exception('Leave saved; queued notification delivery will be checked by the scheduler.')
      headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{saved_revision}"'))

     elif path=='/api/vehicles' and method=='GET':payload={'vehicles':vehicles.fleet(state),'activeVehicles':vehicles.active_fleet(state),'removedVehicles':list(state.get('removedVehicles',{}).values()),'checks':list(state.get('vehicleChecks',{}).values()),'technicians':timesheets.settings(state)['technicians'],'checklist':vehicles.CHECKLIST,'colourSettings':vehicles.colour_settings(state)}

     elif path=='/api/timesheets' and method=='GET':

      payload={'timesheets':[r for r in state.get('timesheets',{}).values() if user['role']=='admin' or r['technician']==user['technician']],'drafts':timesheet_drafts.visible(state,user)}

     elif path=='/api/catalog' and method=='GET':payload={'quotes':list(state['quotes'].values()),'pdfs':list(state['pdfs'])}

     elif path=='/api/drafts' and method=='GET':payload={'drafts':[]}

     elif path=='/api/workbook' and method=='GET':payload=decode(state['workbook'],10*1024*1024);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

     elif path=='/api/pdf' and method=='GET':

      name=parse_qs(environ.get('QUERY_STRING','')).get('name',[''])[0];key=state['pdfs'].get(name)

      if not key:raise Problem(404,'This PDF is unavailable or has been deleted.')

      payload=self.objects.get(key);mime='application/pdf'

     elif method=='POST' and path in ('/api/workbook','/api/quote-save','/api/timesheets','/api/timesheet-drafts','/api/staff-settings','/api/vehicles','/api/vehicle-order','/api/vehicle-checks','/api/time-settings','/api/quote-settings','/api/timesheet-edit'):

      if environ.get('HTTP_IF_MATCH')!=f'"{revision}"':raise Problem(409,'Another change was saved. Refresh and try again.')

      length=int(environ.get('CONTENT_LENGTH') or 0)

      if length<1 or length>MAX_BODY:raise Problem(400,'Upload exceeds the allowed size.')

      body=environ['wsgi.input'].read(length)

      if len(body)!=length:raise Problem(400,'Incomplete upload.')

      upload=None;garbage=[]

      if path in ('/api/time-settings','/api/quote-settings'):

       try:p=json.loads(body)

       except Exception:raise Problem(400,'Invalid settings request.')

       if path=='/api/quote-settings':state=quote_settings.save(state,p)

       else:

        if not isinstance(p,dict) or timesheets.minutes(p.get('finish'))<=timesheets.minutes(p.get('start')):raise Problem(400,'Default finish time must be after start time, in 15-minute increments.')

        state['timeSettings']={'start':p['start'],'finish':p['finish']}

       payload={'saved':True}

      elif path=='/api/timesheet-edit':
       try:p=json.loads(body)
       except Exception:raise Problem(400,'Invalid time sheet correction.')
       state,entry=timesheets.edit_submission(state,p,email);payload={'saved':True,'timesheet':entry,'message':'Updated time sheet submitted. Labour payables now uses these corrected values for the week.'}

      elif path in ('/api/vehicles','/api/vehicle-order','/api/vehicle-checks'):

       try:p=json.loads(body)

       except Exception:raise Problem(400,'Invalid vehicle request.')

       if path=='/api/vehicles':state=vehicles.save_fleet(state,p);payload={'saved':True}

       elif path=='/api/vehicle-order':state=vehicles.save_order(state,p);payload={'saved':True}

       else:

        if p.get('id'):accounts.admin(user)

        if user['role']!='admin':

         import datetime

         from zoneinfo import ZoneInfo

         if p.get('checkDate')!=datetime.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat():raise Problem(403,'Technicians can submit checks for today. Ask an Admin to change previous values.')

         accounts.own(user,p.get('driver'))

         owner=next((vehicle for vehicle in vehicles.active_fleet(state) if vehicle['id']==p.get('vehicleId')),None)
         if not owner or owner['driver']!=user.get('technician'):raise Problem(403,'Choose your active allocated vehicle.')

        state,entry=vehicles.save_check(state,p);entry['submittedBy']=email;payload={'saved':True,'check':entry}

      elif path=='/api/staff-settings':

       try:p=json.loads(body)

       except Exception:raise Problem(400,'Invalid settings request.')

       state=timesheets.save_settings(state,p);payload={'saved':True}

      elif path=='/api/timesheet-drafts':
       try:p=json.loads(body)
       except Exception:raise Problem(400,'Invalid draft request.')
       state,entry=timesheet_drafts.save(state,p,user);payload={'saved':True,'draft':entry,'message':'Draft saved. Continue it from your time sheet history.'}

      elif path=='/api/timesheets':

       try:p=json.loads(body)

       except Exception:raise Problem(400,'Invalid time sheet request.')

       accounts.own(user,p.get('technician'));state,entry=timesheet_drafts.submit(state,p,user);entry['submittedBy']=email;payload={'saved':True,'id':entry['id'],'total':entry['total'],'message':'Signed time sheet saved.'}

      elif path=='/api/workbook':

       if len(body)>10*1024*1024:raise Problem(400,'Workbook exceeds 10 MB.')

       _,old=workbook_info(decode(state['workbook'],10*1024*1024));_,new=workbook_info(body)

       if not set(old).issubset(new):raise Problem(400,'Keep all existing quote numbers, including deleted numbers, in the workbook.')

       for n in old:

        if any(old[n].get(c,'')!=new[n].get(c,'') for c in ('AE','AF','AG')):raise Problem(400,'Change quotes in the quote form. Keep register identities, revisions and status intact when editing Excel.')

       state['workbook']=base64.b64encode(body).decode();payload={'saved':True}

      else:

       try:p=json.loads(body)

       except Exception:raise Problem(400,'Invalid quote request.')

       state,entry,upload,garbage=save_quote(state,p,self.objects,user);payload={'saved':True,'quote':entry}

      mutation_before=self.store.read()[1]
      state=recycle.capture(mutation_before,state,email)

      try:committed=self.store.commit(revision,state)

      except Exception:

       # Commit outcome may be uncertain: keep staged PDF rather than risk

       # deleting one referenced by a completed database commit.

       raise

      if not committed:

       if upload:self.objects.delete(upload)

       raise Problem(409,'A newer change was saved. Return Home and reopen the quote.')

      headers=[h for h in headers if h[0]!='ETag'];headers.append(('ETag',f'"{revision+1}"'))

      if schedule_live.configuration()[0] and schedule_history.etag(mutation_before)!=schedule_history.etag(state):schedule_live.notify()

      for key in garbage:

       try:self.objects.delete(key)

       except Exception:logging.warning('An obsolete PDF needs storage cleanup.')

     else:raise Problem(404,'Not found.')

  except Problem as e:status=e.status;payload={'error':str(e)};mime='application/json'

  except Exception:logging.exception('Quote API request failed');status=500;payload={'error':'The online service could not complete this request. Refresh Home before retrying.'};mime='application/json'

  data=payload if isinstance(payload,bytes) else json.dumps(payload).encode();headers += [('Content-Type',mime),('Content-Length',str(len(data)))];start_response(f'{status} '+{200:'OK',400:'Bad Request',401:'Unauthorized',403:'Forbidden',404:'Not Found',409:'Conflict',413:'Too Large',429:'Too Many Requests',500:'Internal Server Error',503:'Unavailable'}.get(status,'Error'),headers);return [data]

app=Application()
