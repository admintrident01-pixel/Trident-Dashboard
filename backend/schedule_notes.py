"""Weekly notes series: computed occurrences, recoverable deletion and audit history."""
import copy,datetime as dt,math,uuid
from core import Problem

def staff(state):
    import timesheets
    return [r['name'] for r in timesheets.settings(state)['technicians']]

def first(rule):
    start=dt.date.fromisoformat(rule['fromDate'])
    return start+dt.timedelta(days=(rule['weekday']-start.weekday())%7)

def occurs(rule,date):
    if rule.get('deleted'):return False
    day=dt.date.fromisoformat(date);anchor=first(rule)
    return day>=anchor and (not rule.get('toDate') or date<=rule['toDate']) and (day-anchor).days%(7*rule['intervalWeeks'])==0

def blocks(state,date):
    result=[]
    for rule in state.get('scheduleNoteSeries',{}).values():
        if not occurs(rule,date):continue
        for name in rule['technicians']:
            result.append({'id':f"note:{rule['id']}:{date}:"+str(uuid.uuid5(uuid.NAMESPACE_URL,name)),
                'seriesId':rule['id'],'source':'note','date':date,'technician':name,'technicians':[name],
                'client':rule['title'],'address':rule['notes'],'notes':rule['notes'],'type':'Recurring notes',
                'start':rule['start'],'duration':rule['duration'],'timing':'fixed','cancelled':False,'version':rule['version']})
    return result

def read(state):
    return {'technicians':staff(state),'series':sorted(copy.deepcopy(list(state.get('scheduleNoteSeries',{}).values())),key=lambda r:r['createdAt'],reverse=True)}

def collides(a,b):
    import schedule as s
    if not set(a['technicians'])&set(b['technicians']) or a['weekday']!=b['weekday']:return False
    if s.minutes(a['start'])>=s.minutes(b['start'])+b['duration'] or s.minutes(b['start'])>=s.minutes(a['start'])+a['duration']:return False
    # At most 52 candidates find a common phase, without expanding an infinite series.
    start=max(first(a),first(b));anchor=first(a);period=7*a['intervalWeeks']
    candidate=anchor+dt.timedelta(days=((start-anchor).days+period-1)//period*period)
    limit=min([dt.date.fromisoformat(r['toDate']) for r in (a,b) if r.get('toDate')]+[dt.date.max])
    for _ in range(b['intervalWeeks']//math.gcd(a['intervalWeeks'],b['intervalWeeks'])):
        if candidate>limit:return False
        if (candidate-first(b)).days%(7*b['intervalWeeks'])==0:return True
        if (dt.date.max-candidate).days<period:return False
        candidate+=dt.timedelta(days=period)
    return False

def validate_conflicts(state,rule):
    import schedule as s
    for other in state.get('scheduleNoteSeries',{}).values():
        if other['id']!=rule['id'] and not other.get('deleted') and collides(rule,other):
            raise Problem(409,'This repeats over another notes series for the selected staff. Choose a different day or time.')
    for booking in state.get('appointments',{}).values():
        if not booking.get('cancelled') and occurs(rule,booking['date']) and s.overlaps(booking,{**rule,'technician':rule['technicians'][0]}):
            raise Problem(409,f"This repeats over {booking['client']} on {booking['date']}. Choose a different time.")

def save(state,data,user):
    import schedule as s
    action=data.get('action');old=state.get('scheduleNoteSeries',{}).get(data.get('id'))
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    if action=='create':
        names=data.get('technicians');interval=data.get('intervalWeeks');weekday=data.get('weekday')
        if not isinstance(names,list) or not names or any(not isinstance(n,str) or n not in staff(state) for n in names) or len(set(names))!=len(names):raise Problem(400,'Select at least one current staff member.')
        if type(interval) is not int or not 1<=interval<=52 or type(weekday) is not int or not 0<=weekday<=6:raise Problem(400,'Choose a day and a repeat interval from 1 to 52 weeks.')
        start=s.minutes(data.get('start'));end=1440 if data.get('finish')=='24:00' else s.minutes(data.get('finish'))
        if end<=start:raise Problem(400,'Finish must be after start on the same day.')
        from_date=s.day(data.get('fromDate'));to_date=s.day(data['toDate']) if data.get('toDate') else ''
        if to_date and to_date<from_date:raise Problem(400,'The last date must be on or after the first date.')
        if from_date>'9998-12-24' or to_date>'9998-12-31':raise Problem(400,'Choose a date before the year 9999.')
        rule={'id':str(uuid.uuid4()),'title':s.text(data.get('title'),'a block title',160),'notes':str(data.get('notes','')).strip(),
            'technicians':names,'weekday':weekday,'intervalWeeks':interval,'fromDate':from_date,'toDate':to_date,
            'start':data['start'],'duration':end-start,'createdAt':now,'createdBy':user['email'],'deleted':False,'version':1,'history':[]}
        if len(rule['notes'])>4000:raise Problem(400,'Keep notes under 4,000 characters.')
        if to_date and first(rule).isoformat()>to_date:raise Problem(400,'The date range does not include the chosen weekday.')
        validate_conflicts(state,rule)
    elif action in ('delete','restore'):
        if not old:raise Problem(404,'This series is no longer available. Refresh the list.')
        if data.get('version')!=old['version']:raise Problem(409,'This series changed. Refresh before trying again.')
        rule=copy.deepcopy(old);rule['deleted']=action=='delete';rule['version']+=1
        if action=='restore':validate_conflicts(state,rule)
    else:raise Problem(400,'Choose Create, Delete or Restore.')
    rule['history'].append({'action':action,'at':now,'by':user['email']})
    result=copy.deepcopy(state);result.setdefault('scheduleNoteSeries',{})[rule['id']]=rule
    return result
