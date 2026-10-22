"""Unsubmitted sheets are kept separately from payable business records."""
import copy, datetime as dt, decimal, uuid
import accounts, timesheets
from core import Problem

def visible(state,user):
    return [dict(row,isDraft=True) for row in state.get('timesheetDrafts',{}).values() if user['role']=='admin' or (row['owner']==user['email'] and row['technician']==user['technician'])]

def existing(state,data,user):
    key=data.get('draftId')
    if not key:return None
    row=state.get('timesheetDrafts',{}).get(key)
    if not row:raise Problem(404,'This draft no longer exists. Refresh history.')
    if user['role']!='admin' and row['owner']!=user['email']:raise Problem(403,'You can only edit your own drafts.')
    accounts.own(user,row['technician'])
    if type(data.get('draftRevision')) is not int or data['draftRevision']!=row['revision']:raise Problem(409,'This draft changed. Reopen it from history.')
    if row['technician']!=data.get('technician') or row['weekStart']!=data.get('weekStart'):raise Problem(400,'Keep this draft’s technician and week. Start a new sheet for another week.')
    return row

def save(state,data,user):
    if not isinstance(data,dict):raise Problem(400,'Invalid time sheet draft.')
    name=timesheets.text(data.get('technician'),'technician',160,True);accounts.own(user,name)
    week=timesheets.text(data.get('weekStart'),'week starting date',10,True)
    try:date=dt.date.fromisoformat(week)
    except ValueError:raise Problem(400,'Choose a valid Monday.')
    if date.weekday()!=0:raise Problem(400,'Choose a Monday for the week starting date.')
    old=existing(state,data,user)
    if not old:
        duplicate=next((r for r in state.get('timesheetDrafts',{}).values() if r['owner']==user['email'] and r['technician']==name and r['weekStart']==week),None)
        if duplicate:raise Problem(409,'A draft already exists for this week. Reopen it from history.')
    days=data.get('days')
    if not isinstance(days,list) or len(days)!=7:raise Problem(400,'The draft must contain seven days.')
    cleaned=[];total=decimal.Decimal(0)
    for day in days:
        if not isinstance(day,dict) or day.get('status') not in ('Work','Annual leave','Sick leave','Other') or day.get('method') not in ('direct','times'):raise Problem(400,'Choose valid day types and entry methods.')
        row={k:timesheets.text(day.get(k,''),k,limit) for k,limit in [('other',200),('notes',2000),('start',5),('finish',5)]}
        for k in ('start','finish'):
            if row[k]:timesheets.minutes(row[k])
        value=day.get('hours','')
        try:
            hours=decimal.Decimal(str(value)) if str(value).strip() else decimal.Decimal(0)
            valid=hours.is_finite() and 0<=hours<=24 and hours*4==(hours*4).to_integral_value()
        except decimal.InvalidOperation:valid=False
        if not valid:raise Problem(400,'Enter hours from 0 to 24 in 0.25-hour increments, or leave them blank.')
        unpaid=day.get('unpaidLunch',False)
        if not isinstance(unpaid,bool):raise Problem(400,'Choose a valid lunch option.')
        row.update(status=day['status'],method=day['method'],hours=str(value),unpaidLunch=unpaid and day['status']=='Work')
        gross=hours if row['method']=='direct' else decimal.Decimal(max(0,timesheets.minutes(row['finish'])-timesheets.minutes(row['start'])))/60 if row['start'] and row['finish'] else decimal.Decimal(0)
        total+=max(decimal.Decimal(0),gross-(decimal.Decimal('0.5') if row['unpaidLunch'] else 0));cleaned.append(row)
    stamp=dt.datetime.now(dt.timezone.utc).isoformat()
    import leave
    timed={leave_date:r for r in leave.approved(state) if r['technician'].casefold()==name.casefold() and r.get('startTime') for leave_date in r['dates']}
    for index,row in enumerate(cleaned):
        approved=timed.get((date+dt.timedelta(days=index)).isoformat())
        if row['status']=='Work' and approved:total+=decimal.Decimal(str(approved['hoursPerDay']))
    entry={'id':old['id'] if old else str(uuid.uuid4()),'revision':old['revision']+1 if old else 1,'owner':old['owner'] if old else user['email'],'technician':name,'weekStart':week,'signature':timesheets.text(data.get('signature',''),'signature',160),'notes':timesheets.text(data.get('notes',''),'weekly notes',4000),'days':cleaned,'total':float(total),'createdAt':old['createdAt'] if old else stamp,'updatedAt':stamp,'isDraft':True}
    result=copy.deepcopy(state);result.setdefault('timesheetDrafts',{})[entry['id']]=entry
    return result,entry

def submit(state,data,user):
    if not isinstance(data,dict):raise Problem(400,'Invalid time sheet.')
    accounts.own(user,data.get('technician'))
    old=existing(state,data,user)
    result,entry=timesheets.save(state,data)
    if old:del result['timesheetDrafts'][old['id']]
    return result,entry
