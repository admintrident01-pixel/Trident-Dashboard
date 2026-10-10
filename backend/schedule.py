"""Shared technician appointments with optimistic edits and overlap checks."""
import copy, datetime as dt, re, uuid
from core import Problem
import timesheets, leave

def leave_blocks(state,date):
    blocks=[]
    start=state.get('timeSettings',{}).get('start','08:00')
    try: default_start=minutes(start)
    except Problem: default_start=480
    for request in leave.approved(state):
        if date not in request['dates']: continue
        duration=int(round(request['hoursPerDay']*60))
        start_minute=min(default_start,1440-duration)
        blocks.append({'id':'leave:'+request['id']+':'+date,'source':'leave','date':date,'technician':request['technician'],
                       'start':f'{start_minute//60:02d}:{start_minute%60:02d}','duration':duration,'hoursPerDay':request['hoursPerDay'],
                       'client':'On leave','address':f"{request['hoursPerDay']:g} hours",'type':'Approved leave','timing':'fixed','cancelled':False})
    return blocks

DEFAULT_TYPES=['Equipment repair','Equipment assessment','Delivery','Collection','Vehicle service','Client visit','Other']

def settings(state):
    result=copy.deepcopy(state.get('scheduleSettings',{'appointmentTypes':DEFAULT_TYPES}))
    result.setdefault('lunchStart','12:00')
    staff=timesheets.settings(state)['technicians']
    names=[row['name'] for row in staff]
    order=[name for name in result.get('technicianOrder',[]) if name in names]
    order+= [name for name in names if name not in order]
    office={row['name'] for row in staff if row.get('staffType')=='office'}
    result['technicianOrder']=sorted(order,key=lambda name:name in office)
    result['staffTypes']={row['name']:row.get('staffType','technician') for row in staff}
    return result

def save_settings(state,data):
    rows=data.get('appointmentTypes') if isinstance(data,dict) else None
    if not isinstance(rows,list) or not 1<=len(rows)<=100: raise Problem(400,'Add between 1 and 100 appointment types.')
    cleaned=[text(value,'an appointment type',120) for value in rows]
    if len({value.casefold() for value in cleaned})!=len(cleaned): raise Problem(400,'Use a different name for each appointment type.')
    result=copy.deepcopy(state)
    lunch_start=data.get('lunchStart',settings(state)['lunchStart'])
    if minutes(lunch_start)>1410: raise Problem(400,'Lunch must finish before midnight.')
    order=data.get('technicianOrder',settings(state)['technicianOrder'])
    names={row['name'] for row in timesheets.settings(state)['technicians']}
    if not isinstance(order,list) or any(not isinstance(name,str) for name in order) or len(order)!=len(set(order)) or set(order)!=names:
        raise Problem(400,'Include each current staff member once in the schedule order. Refresh settings and try again.')
    result['scheduleSettings']={'appointmentTypes':cleaned,'lunchStart':lunch_start,'technicianOrder':order}
    return result

def assigned(appointment):
    return appointment.get('technicians') or [appointment['technician']]

def overlaps(first,second):
    start=minutes(first['start']);other_start=minutes(second['start'])
    return bool(set(assigned(first)) & set(assigned(second))) and start<other_start+second['duration'] and other_start<start+first['duration']

def day(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):
        raise Problem(400,'Choose a valid appointment date.')
    try: dt.date.fromisoformat(value)
    except ValueError: raise Problem(400,'Choose a valid appointment date.')
    return value

def minutes(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{2}:\d{2}',value):
        raise Problem(400,'Enter a valid start time.')
    hour,minute=map(int,value.split(':'))
    if hour>23 or minute>59 or minute%15: raise Problem(400,'Use 15-minute time increments.')
    return hour*60+minute

def text(value,label,limit):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:
        raise Problem(400,f'Enter {label} (up to {limit} characters).')
    return value.strip()

def lunch_blocks(state,date):
    rows=state.get('appointments',{})
    start=settings(state)['lunchStart']
    blocks=[]
    for staff in timesheets.settings(state)['technicians']:
        name=staff['name']
        identifier='lunch:'+str(uuid.uuid5(uuid.NAMESPACE_URL,date+':'+name))
        if identifier in rows or identifier in state.get('deletedLunchIds',[]): continue
        if any(a['date']==date and a.get('source')=='lunch' and name in assigned(a) for a in rows.values()): continue
        block={'id':identifier,'source':'lunch','date':date,'technician':name,'technicians':[name],
               'start':start,'duration':30,'client':'Lunch','address':'','type':'Lunch','timing':'flexible',
               'notes':'','cancelled':False,'version':0,'createdAt':''}
        if not any(overlaps(block,leave_block) for leave_block in leave_blocks(state,date)): blocks.append(block)
    return blocks

def read(state,date):
    date=day(date)
    appointments=[copy.deepcopy(a) for a in state.get('appointments',{}).values() if a['date']==date]
    blocks=leave_blocks(state,date)
    for appointment in appointments:
        if not appointment.get('cancelled') and any(overlaps(appointment,block) for block in blocks): appointment['leaveConflict']=True
    staff=timesheets.settings(state)['technicians']
    types={t['name']:t.get('staffType','technician') for t in staff}
    names=settings(state)['technicianOrder']
    names+=sorted({name for a in appointments+blocks for name in assigned(a)}-set(names))
    names.sort(key=lambda name:types.get(name,'technician')=='office')
    return {'date':date,'lunchStart':settings(state)['lunchStart'],'appointmentTypes':settings(state)['appointmentTypes'],'technicians':names,'staffTypes':types,'workHours':copy.deepcopy(state.get('timeSettings',{'start':'08:00','finish':'16:00'})),'appointments':sorted(appointments,key=lambda a:(a['start'],a['client'])),'leaveBlocks':blocks,'lunchBlocks':lunch_blocks(state,date)}

def save(state,data,user):
    rows=state.get('appointments',{})
    identifier=data.get('id')
    old=rows.get(identifier) if isinstance(identifier,str) else None
    if identifier and not old and isinstance(identifier,str) and identifier.startswith('lunch:'):
        old=next((block for block in lunch_blocks(state,day(data.get('date'))) if block['id']==identifier),None)
    if identifier and not old: raise Problem(404,'This appointment is no longer available. Refresh the schedule.')
    if old and data.get('version')!=old['version']: raise Problem(409,'This appointment changed. Refresh and reopen it.')
    action=data.get('action','save')
    if action not in ('save','cancel','restore'): raise Problem(400,'Choose a valid appointment action.')
    if action!='save':
        if not old: raise Problem(400,'Save the appointment first.')
        appointment={**old,'cancelled':action=='cancel'}
    else:
        date=day(data.get('date'))
        raw=data.get('technicians',[data.get('technician')])
        if not isinstance(raw,list) or not raw or len(raw)>200: raise Problem(400,'Select at least one technician.')
        technicians=[text(name,'a technician',160) for name in raw]
        if len(set(technicians))!=len(technicians): raise Problem(400,'Select each technician once.')
        names={t['name'] for t in timesheets.settings(state)['technicians']}
        if any(name not in names and (not old or name not in assigned(old)) for name in technicians): raise Problem(400,'Choose technicians from Settings.')
        technician=technicians[0]
        start=data.get('start');start_minute=minutes(start)
        duration=data.get('duration')
        if isinstance(duration,bool) or not isinstance(duration,int) or duration<15 or duration>1440 or duration%15 or start_minute+duration>1440:
            raise Problem(400,'Use a duration in 15-minute increments that finishes on the same day.')
        timing=data.get('timing')
        if timing not in ('fixed','flexible'): raise Problem(400,'Choose Fixed time or Flexible time.')
        is_lunch=str(data.get('type','')).strip().casefold()=='lunch'
        appointment={'id':identifier or str(uuid.uuid4()),'date':date,'technician':technician,'technicians':technicians,'start':start,'duration':duration,'timing':timing,
                     'client':'Lunch' if is_lunch else text(data.get('client'),'a client name',160),'address':'' if is_lunch else text(data.get('address'),'an address',500),
                     'type':text(data.get('type'),'an appointment type',120),'notes':str(data.get('notes','')).strip(),'cancelled':False}
        if is_lunch: appointment['source']='lunch'
        if len(appointment['notes'])>4000: raise Problem(400,'Keep appointment notes under 4,000 characters.')
    if not appointment['cancelled']:
        if any(overlaps(appointment,block) for block in leave_blocks(state,appointment['date'])):
            raise Problem(409,'This technician has approved leave during that time. Choose another time or technician.')
        start_minute=minutes(appointment['start']);end=start_minute+appointment['duration']
        for other in rows.values():
            if appointment.get('source')=='lunch' or other.get('source')=='lunch': continue
            if other['id']==appointment['id'] or other.get('cancelled') or other['date']!=appointment['date'] or not set(assigned(other)) & set(assigned(appointment)): continue
            other_start=minutes(other['start'])
            if start_minute<other_start+other['duration'] and other_start<end:
                raise Problem(409,f"This time overlaps {other['client']}'s appointment. Choose another time or technician.")
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    appointment.update(version=(old['version'] if old else 0)+1,createdAt=old['createdAt'] if old else now,updatedAt=now,updatedBy=user['email'])
    result=copy.deepcopy(state)
    result.setdefault('appointments',{})[appointment['id']]=appointment
    return result,appointment
