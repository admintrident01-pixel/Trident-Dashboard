import copy,datetime,decimal,re,uuid
from core import Problem

TYPES=('Annual leave','Sick leave','Other')
def value(data,key,label,limit,required=False):
 v=data.get(key,'')
 if not isinstance(v,str) or len(v)>limit or (required and not v.strip()):raise Problem(400,f'Enter a valid {label}.')
 return v.strip()
def day(text):
 try:
  if len(text)!=10:raise ValueError()
  return datetime.date.fromisoformat(text)
 except (ValueError,TypeError):raise Problem(400,'Enter valid leave dates.')

def time_minutes(text,end=False):
 if end and text=='24:00':return 1440
 if not isinstance(text,str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):(?:00|15|30|45)',text):raise Problem(400,'Choose leave times in 15-minute increments.')
 hour,minute=map(int,text.split(':'));return hour*60+minute

def time_range(data):
 if not data.get('startTime') and not data.get('endTime'):return None
 start=time_minutes(data.get('startTime'));end=time_minutes(data.get('endTime'),True)
 if end<=start:raise Problem(400,'Leave To time must be after From time on the same day.')
 return start,end
def create(state,data):
 if not isinstance(data,dict):raise Problem(400,'Invalid leave request.')
 tech=value(data,'technician','technician',160,True)
 # Only registered technicians can request leave, so names match time sheets.
 from timesheets import settings
 names={t['name'].casefold():t['name'] for t in settings(state)['technicians']}
 if tech.casefold() not in names:raise Problem(400,'Choose a technician from Settings.')
 tech=names[tech.casefold()]
 kind=data.get('leaveType')
 if kind not in TYPES:raise Problem(400,'Choose a valid leave type.')
 other=value(data,'other','other leave description',200,kind=='Other')
 start=day(value(data,'startDate','start date',10,True));end=day(value(data,'endDate','end date',10,True))
 if end<start or (end-start).days>365:raise Problem(400,'Choose a date range of up to one year, with end after start.')
 try:
  hours=decimal.Decimal(str(data.get('hoursPerDay','')))
  valid=hours.is_finite() and 0<hours<=24 and hours*4==(hours*4).to_integral_value()
 except decimal.InvalidOperation:valid=False
 if not valid:raise Problem(400,'Enter hours per day above 0 and up to 24 in 0.25-hour increments.')
 period=time_range(data)
 if period and hours*60>period[1]-period[0]:raise Problem(400,'Paid leave hours cannot exceed the From–To period. Reduce paid hours to exclude any unpaid break.')
 weekends=data.get('includeWeekends',False)
 if not isinstance(weekends,bool):raise Problem(400,'Choose whether to include weekends.')
 dates=[(start+datetime.timedelta(days=i)).isoformat() for i in range((end-start).days+1) if weekends or (start+datetime.timedelta(days=i)).weekday()<5]
 if not dates:raise Problem(400,'The request has no working days. Include weekends if needed.')
 for r in state.get('leaveRequests',{}).values():
  if r['technician'].casefold()==tech.casefold() and r['status'] in ('Pending','Approved') and set(dates)&set(r['dates']):raise Problem(409,'A pending or approved request already covers one of these dates.')
 now=datetime.datetime.now(datetime.timezone.utc).isoformat()
 r={'id':str(uuid.uuid4()),'revision':1,'technician':tech,'leaveType':kind,'other':other,'startDate':start.isoformat(),'endDate':end.isoformat(),'dates':dates,'hoursPerDay':float(hours),'includeWeekends':weekends,'totalHours':float(hours*len(dates)),'reason':value(data,'reason','reason / notes',4000,True),'status':'Pending','submittedAt':now,'updatedAt':now,'decisionNotes':'','decidedBy':'','decidedAt':''}
 if period:r.update(startTime=data['startTime'],endTime=data['endTime'])
 result=copy.deepcopy(state);result.setdefault('leaveRequests',{})[r['id']]=r
 return result,r
def decide(state,data,email):
 if not isinstance(data,dict):raise Problem(400,'Invalid leave decision.')
 r=state.get('leaveRequests',{}).get(data.get('id'))
 if not r:raise Problem(404,'Leave request not found.')
 if data.get('revision')!=r['revision']:raise Problem(409,'This leave request changed. Refresh before deciding.')
 action=data.get('status')
 if action not in ('Approved','Declined','Cancelled'):raise Problem(400,'Choose a valid leave decision.')
 if (action in ('Approved','Declined') and r['status']!='Pending') or (action=='Cancelled' and r['status'] not in ('Pending','Approved')):raise Problem(409,'This request can no longer receive that decision.')
 notes=value(data,'decisionNotes','decision notes',2000,action=='Declined')
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();result=copy.deepcopy(state);entry=result['leaveRequests'][r['id']]
 entry.update(status=action,revision=r['revision']+1,decisionNotes=notes,decidedBy=email,decidedAt=now,updatedAt=now)
 return result,entry
def approved(state):
 return [{k:r[k] for k in ('id','technician','leaveType','other','dates','hoursPerDay','startTime','endTime') if k in r} for r in state.get('leaveRequests',{}).values() if r['status']=='Approved']
def enforce_timesheet(state,entry):
 approved_days={date:r for r in approved(state) if r['technician'].casefold()==entry['technician'].casefold() for date in r['dates']}
 start=day(entry['weekStart'])
 for i,row in enumerate(entry['days']):
  date=(start+datetime.timedelta(days=i)).isoformat();r=approved_days.get(date)
  if r and r.get('startTime') and row['status']=='Work':
   if row['method']=='times' and time_minutes(row['start'])<time_minutes(r['endTime'],True) and time_minutes(row['finish'])>time_minutes(r['startTime']):raise Problem(400,f'{date}: work times overlap approved leave. Use Direct hours for separate work periods, excluding leave.')
   if row['hours']+r['hoursPerDay']>24:raise Problem(400,f'{date}: work plus approved leave cannot exceed 24 hours.')
   row['leave']={k:r[k] for k in ('id','leaveType','other','hoursPerDay','startTime','endTime')}
   entry['total']=float(decimal.Decimal(str(entry['total']))+decimal.Decimal(str(r['hoursPerDay'])))
   continue
  if r and (row['status']!=r['leaveType'] or row['hours']!=r['hoursPerDay'] or (row['status']=='Other' and row['other']!=r['other'])):raise Problem(400,f'{date}: use the approved leave type and hours. Refresh the time sheet.')
  if not r and row['status']!='Work' and row['hours']>0:raise Problem(400,f'{date}: submit a leave request and have it approved before recording leave hours.')
 return [r['id'] for r in {r['id']:r for r in approved_days.values() if set(r['dates'])&{(start+datetime.timedelta(days=i)).isoformat() for i in range(7)}}.values()]
