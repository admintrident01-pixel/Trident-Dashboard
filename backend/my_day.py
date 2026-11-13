"""Private member work log. No schedule, payroll, mail or routing side effects."""
import copy, datetime as dt, hashlib, json, re, uuid
from zoneinfo import ZoneInfo
from core import Problem
import schedule, schedule_booking, schedule_notes, reminders, timesheets, timesheet_drafts

ZONE=ZoneInfo('Pacific/Auckland')
def require(user,linked=True):
    if not user.get('email') or user.get('role') not in ('admin','tech'):raise Problem(403,'Sign in to view your day.')
    if user['email'].strip().lower()=='scott@trice.nz' or user.get('technician','').strip().casefold()=='scott yearbury':raise Problem(403,'My day is not enabled for this account.')
    if linked and not user.get('technician'):raise Problem(409,'Ask an administrator to link your account to your staff identity first.')

def date(value):
    try:
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError()
        return dt.date.fromisoformat(value).isoformat()
    except (ValueError,TypeError):raise Problem(400,'Choose a valid day.')

def own_appointments(state,user,day):
    return sorted([copy.deepcopy(a) for a in state.get('appointments',{}).values()
        if a.get('date')==day and not a.get('cancelled') and not schedule.is_lunch(a)
        and user['technician'] in schedule.assigned(a)],key=lambda a:(a['start'],a['id']))

def book(state,user):return state.get('myDayLogs',{}).get(user['email'],{'revision':0,'days':{},'operations':{}})

def read(state,user,day,now=None):
    require(user,linked=False);day=date(day);now=now or dt.datetime.now(dt.timezone.utc);local=now.astimezone(ZONE)
    if not user.get('technician'):return {'date':day,'today':local.date().isoformat(),'serverNow':now.isoformat(),'technician':user.get('name') or user['email'],'setupRequired':True,'revision':0}
    rows=[schedule_booking.controls(a) for a in own_appointments(state,user,day)]
    notes=[a for a in schedule_notes.blocks(state,day) if user['technician'] in schedule.assigned(a)]
    log=book(state,user);record=copy.deepcopy(log['days'].get(day,{'jobs':{},'finishedAt':None}))
    active=next(({'date':d,'jobId':key,'title':j['title'],'start':s['start']}
        for d,v in log['days'].items() for key,j in v['jobs'].items() for s in j['sessions'] if not s.get('end')),None)
    due=[r for r in reminders.dashboard(state,now) if r.get('recipient')==user['email'] and r['kind'] in ('timesheet','vehicle')]
    monday=local.date()-dt.timedelta(days=local.weekday()+7)
    sheet=next((r for r in state.get('timesheets',{}).values() if r.get('technician')==user['technician'] and r.get('weekStart')==monday.isoformat()),None)
    draft=next((r for r in timesheet_drafts.visible(state,user) if r.get('technician')==user['technician'] and r.get('weekStart')==monday.isoformat()),None)
    cfg=reminders.settings(state);sheet_due=dt.datetime.combine(monday+dt.timedelta(days=7+cfg['timesheetWeekday']),dt.time.fromisoformat(cfg['timesheetTime']),ZONE)
    leaves=sorted([copy.deepcopy(r) for r in state.get('leaveRequests',{}).values() if r.get('technician')==user['technician']],key=lambda r:r.get('submittedAt',''),reverse=True)[:5]
    return {'date':day,'today':local.date().isoformat(),'serverNow':now.isoformat(),'technician':user['technician'],'clientSearchUrlTemplate':schedule.settings(state)['clientSearchUrlTemplate'],
        'appointments':rows,'recurringNotes':notes,'plannedMinutes':sum(a['duration'] for a in rows if a.get('type','').casefold()!='notes'),
        'revision':log['revision'],'day':record,'active':active,'attention':due,'leave':leaves,
        'timesheet':{'weekStart':monday.isoformat(),'due':sheet_due.isoformat(),'daysRemaining':(sheet_due.date()-local.date()).days,
            'status':'Submitted' if sheet else 'Draft' if draft else 'Not submitted'}}

def instant(value,day):
    try:
        result=dt.datetime.fromisoformat(value)
        if result.tzinfo is None or result.astimezone(ZONE).date().isoformat()!=day:raise ValueError()
        return result.astimezone(dt.timezone.utc)
    except (ValueError,TypeError):raise Problem(400,'Enter start and finish times on the selected Auckland day.')

def local_time(day,value):
    if not isinstance(value,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',value):raise Problem(400,'Enter a valid time.')
    naive=dt.datetime.fromisoformat(day+'T'+value)
    first=naive.replace(tzinfo=ZONE,fold=0);second=naive.replace(tzinfo=ZONE,fold=1)
    if first.utcoffset()!=second.utcoffset():raise Problem(400,'This time is ambiguous or skipped by daylight saving. Choose another time.')
    return first.astimezone(dt.timezone.utc)

def operation(state,user,data,now=None):
    require(user);now=now or dt.datetime.now(dt.timezone.utc)
    oid=data.get('operationId');day=date(data.get('date'));action=data.get('action')
    if not isinstance(oid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,100}',oid):raise Problem(400,'A valid operation key is required.')
    digest=hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    old=book(state,user);receipt=old.get('operations',{}).get(oid)
    if receipt:
        if receipt['digest']!=digest:raise Problem(409,'This operation key was already used for different details.')
        return state,True
    if type(data.get('revision')) is not int or data['revision']!=old['revision']:raise Problem(409,'Your work log changed on another device. Refresh and review it before saving again.')
    if len(old.get('operations',{}))>=10000:raise Problem(409,'Your work log needs archiving. Contact the administrator; existing hours are preserved.')
    result=copy.deepcopy(state);log=copy.deepcopy(old);record=log['days'].setdefault(day,{'jobs':{},'finishedAt':None})
    if day>now.astimezone(ZONE).date().isoformat() and action not in ('create','times'):raise Problem(400,'Live timers and Finish day are available on today or a previous day.')
    if record.get('finishedAt') and action!='reopen':raise Problem(409,'This day is finished. Reopen it before changing recorded hours.')
    active=[(d,k,j,s) for d,v in log['days'].items() for k,j in v['jobs'].items() for s in j['sessions'] if not s.get('end')]
    if action=='reopen':record['finishedAt']=None
    elif action=='finish':
        if active and any(d!=day for d,_,_,_ in active):raise Problem(409,'Stop the timer on its recorded day before finishing another day.')
        for d,k,j,s in active:
            if now.astimezone(ZONE).date().isoformat()!=d:raise Problem(409,'This timer crossed midnight. Set its actual finish time on its recorded day first.')
            s['end']=now.isoformat()
        record['finishedAt']=now.isoformat()
    elif action in ('create','start','stop','times'):
        key=data.get('jobId')
        if not isinstance(key,str) or len(key)>200:raise Problem(400,'Choose a job.')
        job=record['jobs'].get(key)
        if action=='create':
            if not re.fullmatch(r'custom:[A-Za-z0-9_-]{16,100}',key) or job:raise Problem(409,'This custom job already exists or has an invalid ID.')
            title=data.get('title','').strip() if isinstance(data.get('title'),str) else ''
            if not title or len(title)>160:raise Problem(400,'Enter a custom job name, up to 160 characters.')
            job={'id':key,'title':title,'technician':user['technician'],'source':'custom','sessions':[]};record['jobs'][key]=job
        elif not job:
            source=next((a for a in own_appointments(state,user,day) if a['id']==key),None)
            if not source:raise Problem(403,'This job is not assigned to you on this day.')
            job={'id':key,'appointmentId':key,'title':source['client'],'technician':user['technician'],'source':'schedule','sessions':[]};record['jobs'][key]=job
        if action=='start':
            if active:raise Problem(409,'A timer is already running. Stop it before starting another job.')
            if day!=now.astimezone(ZONE).date().isoformat():raise Problem(400,'Live timers can start only today. Enter actual times for earlier days.')
            job['sessions'].append({'id':uuid.uuid4().hex,'start':now.isoformat(),'end':None})
        elif action=='stop':
            running=next((s for s in job['sessions'] if not s.get('end')),None)
            if not running:raise Problem(409,'This job has no running timer. Refresh its saved status.')
            if day!=now.astimezone(ZONE).date().isoformat():raise Problem(409,'This timer crossed midnight. Enter its actual finish time instead.')
            running['end']=now.isoformat()
        elif action=='times':
            raw=data.get('sessions')
            if not isinstance(raw,list) or len(raw)>100:raise Problem(400,'Enter up to 100 work periods for this job.')
            sessions=[]
            for item in raw:
                if not isinstance(item,dict):raise Problem(400,'Enter a valid work period.')
                start=local_time(day,item.get('start'));end=local_time(day,item.get('end'))
                if end<=start:raise Problem(400,'Finish must be after start.')
                sessions.append({'id':uuid.uuid4().hex,'start':start.isoformat(),'end':end.isoformat()})
            job['sessions']=sessions
        job['updatedAt']=now.isoformat()
    else:raise Problem(400,'Choose a valid work-log action.')
    # Reject overlapping actual work, including timers on another day. Never double-count it.
    spans=sorted([(instant(s['start'],d),instant(s['end'],d) if s.get('end') else now,k)
        for d,v in log['days'].items() for k,j in v['jobs'].items() for s in j['sessions']],key=lambda s:s[0])
    if any(b[0]<a[1] for a,b in zip(spans,spans[1:])):raise Problem(409,'Recorded work periods overlap. Adjust the times before saving.')
    log.setdefault('history',[]).append({'operationId':oid,'action':action,'date':day,'actor':user['email'],'at':now.isoformat(),'before':copy.deepcopy(old['days'].get(day))})
    log['revision']+=1;log.setdefault('operations',{})[oid]={'digest':digest,'revision':log['revision']}
    result.setdefault('myDayLogs',{})[user['email']]=log
    return result,False
