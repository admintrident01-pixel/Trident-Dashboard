import copy, datetime, decimal, re, uuid
from zoneinfo import ZoneInfo
from core import Problem

DEFAULT_NAMES = ['Scott Yearbury', 'Daryll Anderson', 'Bala Ganesh Venkatesan', 'Andrew Thomas', 'Rick Leef', 'Allan Burney', 'Joby Shearing', 'Jackie Gough']

def settings(state):
    rows=state.get('staffSettings', {'technicians': [{'name': name, 'rego': ''} for name in DEFAULT_NAMES]})['technicians']
    return {'technicians':[{**row,'staffType':row.get('staffType','technician'),'hasVehicle':row.get('hasVehicle',True)} for row in rows]}

def save_settings(state, data):
    if not isinstance(data, dict) or not isinstance(data.get('technicians'), list) or len(data['technicians']) > 200:
        raise Problem(400, 'Enter a valid technician list (up to 200 people).')
    cleaned, seen = [], set()
    for row in data['technicians']:
        if not isinstance(row, dict):
            raise Problem(400, 'Invalid technician details.')
        name = text(row.get('name'), 'technician name', 160, True)
        rego = text(row.get('rego', ''), 'vehicle registration', 30).upper()
        staff_type=row.get('staffType','technician')
        has_vehicle=row.get('hasVehicle',True)
        if staff_type not in ('technician','office') or not isinstance(has_vehicle,bool): raise Problem(400,'Choose Technician or Office and a valid vehicle option.')
        if not has_vehicle: rego=''
        if name.casefold() in seen:
            raise Problem(400, 'Each technician name must be unique.')
        seen.add(name.casefold())
        cleaned.append({'name': name, 'rego': rego,'staffType':staff_type,'hasVehicle':has_vehicle})
    result = copy.deepcopy(state)
    result['staffSettings'] = {'technicians': cleaned}
    return result

def config(state):
    import leave
    today = datetime.datetime.now(ZoneInfo('Pacific/Auckland')).date()
    monday = today - datetime.timedelta(days=today.weekday())
    technicians = sorted({s['technician'] for s in state.get('timesheets', {}).values()} | {s['name'] for s in settings(state)['technicians']}, key=str.casefold)
    return {'technicians': technicians, 'weekStart': monday.isoformat(), 'approvedLeave':leave.approved(state), 'defaultTimes':state.get('timeSettings',{'start':'07:30','finish':'16:00'})}

def text(value, label, limit, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise Problem(400, f'Enter a valid {label}.')
    return value.strip()

def minutes(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):(?:00|15|30|45)', value):
        raise Problem(400, 'Start and finish times must use 15-minute increments.')
    hour, minute = map(int, value.split(':'))
    return hour * 60 + minute

def save(state, data):
    if not isinstance(data, dict):
        raise Problem(400, 'Invalid time sheet.')
    technician = text(data.get('technician'), 'technician name', 160, True)
    signature = text(data.get('signature'), 'signature', 160, True)
    week = text(data.get('weekStart'), 'week starting date', 10, True)
    try:
        date = datetime.date.fromisoformat(week)
    except ValueError:
        raise Problem(400, 'Choose a valid week starting date.')
    if date.weekday() != 0:
        raise Problem(400, 'The week starting date must be a Monday.')
    days = data.get('days')
    if not isinstance(days, list) or len(days) != 7:
        raise Problem(400, 'The time sheet must contain seven days.')
    cleaned, total = [], decimal.Decimal(0)
    for day in days:
        if not isinstance(day, dict):
            raise Problem(400, 'Invalid day entry.')
        status, method = day.get('status'), day.get('method')
        if status not in ('Work', 'Annual leave', 'Sick leave', 'Other') or method not in ('direct', 'times'):
            raise Problem(400, 'Choose a valid work/leave type and entry method.')
        if status != 'Work' and method != 'direct':
            raise Problem(400, 'Enter leave using Direct hours.')
        other = text(day.get('other', ''), 'other leave description', 200, status == 'Other')
        notes = text(day.get('notes', ''), 'daily notes', 2000)
        start, finish = day.get('start', ''), day.get('finish', '')
        if method == 'times':
            duration = minutes(finish) - minutes(start)
            if duration < 0:
                raise Problem(400, 'Finish time must not be before start time.')
            hours = decimal.Decimal(duration) / 60
        else:
            try:
                hours = decimal.Decimal(str(day.get('hours', '')))
                valid = hours.is_finite() and 0 <= hours <= 24 and hours * 4 == (hours * 4).to_integral_value()
            except decimal.InvalidOperation:
                valid = False
            if not valid:
                raise Problem(400, 'Enter hours from 0 to 24 in 0.25-hour increments.')
        unpaid_lunch = day.get('unpaidLunch', False)
        if not isinstance(unpaid_lunch, bool):
            raise Problem(400, 'Invalid unpaid lunch choice.')
        if unpaid_lunch and status != 'Work':
            raise Problem(400, 'Unpaid lunch applies only to work hours.')
        entered_hours = hours
        lunch_hours = min(hours, decimal.Decimal('0.5')) if unpaid_lunch else decimal.Decimal(0)
        hours -= lunch_hours
        total += hours
        cleaned.append({'status': status, 'other': other, 'notes': notes, 'method': method, 'hours': float(hours), 'enteredHours': float(entered_hours), 'unpaidLunch': unpaid_lunch, 'lunchHours': float(lunch_hours), 'start': start if method == 'times' else '', 'finish': finish if method == 'times' else ''})
    entry = {'id': str(uuid.uuid4()), 'revision': 1, 'technician': technician, 'weekStart': week, 'signature': signature, 'notes': text(data.get('notes', ''), 'weekly notes', 4000), 'days': cleaned, 'total': float(total), 'submittedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    result = copy.deepcopy(state)
    import leave
    entry['approvedLeaveIds'] = leave.enforce_timesheet(state, entry)
    result.setdefault('timesheets', {})[entry['id']] = entry
    return result, entry


def edit_submission(state, data, actor):
    if not isinstance(data, dict):raise Problem(400, 'Invalid time sheet correction.')
    old=state.get('timesheets', {}).get(data.get('id'))
    if not old:raise Problem(404, 'This time sheet no longer exists.')
    if type(data.get('revision')) is not int or data['revision'] != old.get('revision',1):
        raise Problem(409, 'This time sheet changed. Refresh and reopen it.')
    if data.get('technician') != old['technician']:
        raise Problem(400, 'Keep the original technician for a correction.')
    if data.get('weekStart') != old['weekStart'] and any(s['id'] != old['id'] and s['technician'].casefold() == old['technician'].casefold() and s['weekStart'] == data.get('weekStart') for s in state.get('timesheets',{}).values()) and data.get('replaceWeekConfirmed') is not True:
        raise Problem(400, 'This person already has a submission for the new week. Confirm that this correction should become the current submission.')
    reason=text(data.get('editReason'), 'correction reason', 1000, True)
    payload={**data, 'signature':old['signature']}
    _, entry=save(state,payload)
    previous={k:copy.deepcopy(v) for k,v in old.items() if k!='editHistory'}
    history=copy.deepcopy(old.get('editHistory',[]))
    stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
    history.append({'editedBy':actor,'editedAt':stamp,'reason':reason,'previous':previous})
    entry.update(id=old['id'],submittedAt=old['submittedAt'],submittedBy=old.get('submittedBy',''),revision=old.get('revision',1)+1,updatedAt=stamp,updatedBy=actor,editReason=reason,editHistory=history[-50:])
    result=copy.deepcopy(state);result['timesheets'][old['id']]=entry
    return result,entry


def delete_submission(state,data):
    if not isinstance(data,dict) or data.get('confirmed') is not True:
        raise Problem(400,'Confirm time sheet deletion.')
    key=data.get('id')
    if not isinstance(key,str) or key not in state.get('timesheets',{}):
        raise Problem(404,'This time sheet no longer exists.')
    row=state['timesheets'][key]
    if type(data.get('revision')) is not int or data['revision']!=row.get('revision',1):
        raise Problem(409,'This time sheet changed. Refresh history before deleting.')
    result=copy.deepcopy(state)
    del result['timesheets'][key]
    return result
