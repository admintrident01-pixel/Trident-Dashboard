import copy, datetime, decimal, re, uuid
from zoneinfo import ZoneInfo
from core import Problem
from leave import TYPES as LEAVE_TYPES, approved as approved_leave, type_paid

TIME_SHEET_STATUSES=('Work',)+LEAVE_TYPES

DEFAULT_NAMES = ['Scott Yearbury', 'Daryll Anderson', 'Bala Ganesh Venkatesan', 'Andrew Thomas', 'Rick Leef', 'Allan Burney', 'Joby Shearing', 'Jackie Gough']
DAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

ON_CALL_NOTE = 'ON CALL ALLOWANCE NEEDED'

def on_call_note(sheet):
    """Weekly note derived from the sign-off on-call choice; never stored twice."""
    return ON_CALL_NOTE if isinstance(sheet, dict) and sheet.get('onCall') is True else ''

def weekly_note(sheet):
    """Combine the derived on-call marker and any saved weekly note."""
    if not isinstance(sheet,dict):return ''
    notes=sheet.get('notes')
    notes=notes.strip() if isinstance(notes,str) else ''
    return ' / '.join(part for part in (on_call_note(sheet),notes) if part)

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

def default_work_times(state):
    """Return the configured workday window, falling back safely if it is unavailable."""
    if not isinstance(state, dict):
        state = {}
    settings = state.get('timeSettings') if isinstance(state.get('timeSettings'), dict) else {}
    start = settings.get('start', '07:30')
    finish = settings.get('finish', '16:00')
    try:
        span = minutes(finish) - minutes(start)
    except Problem:
        span = 0
    if span <= 0:
        return '07:30', '16:00'
    return start, finish

def clock_minutes(value):
    if value == '24:00':
        return 1440
    try:
        return minutes(value)
    except Problem:
        return None

def timed_leave_for_week(state, technician, week):
    """Map timed approved leave to each date in the time sheet week."""
    try:
        start = datetime.date.fromisoformat(week)
    except (TypeError, ValueError):
        return {}
    dates = {(start + datetime.timedelta(days=index)).isoformat() for index in range(7)}
    result = {}
    for row in approved_leave(state):
        if str(row.get('technician', '')).casefold() != technician.casefold():
            continue
        if not row.get('startTime') or not row.get('endTime'):
            continue
        for date in row.get('dates', []):
            if date in dates:
                result[date] = row
    return result

def paid_leave_hours(row, start, finish):
    """Return approved paid leave minutes inside a work start/finish window."""
    if not row or start is None or finish is None:
        return decimal.Decimal(0)
    leave_start = clock_minutes(row.get('startTime'))
    leave_end = clock_minutes(row.get('endTime'))
    if leave_start is None or leave_end is None or leave_end <= leave_start:
        return decimal.Decimal(0)
    overlap = max(0, min(finish, leave_end) - max(start, leave_start))
    if not overlap:
        return decimal.Decimal(0)
    lunch_start = clock_minutes(row.get('lunchStart'))
    lunch_end = clock_minutes(row.get('lunchEnd'))
    lunch_overlap = max(0, min(finish, lunch_end) - max(start, lunch_start)) if lunch_start is not None and lunch_end is not None else 0
    try:
        approved_hours = decimal.Decimal(str(row.get('hoursPerDay') or 0))
    except decimal.InvalidOperation:
        approved_hours = decimal.Decimal(0)
    leave_span = leave_end - leave_start
    if lunch_start is None or lunch_end is None:
        if leave_span > 0 and approved_hours > 0 and abs(decimal.Decimal(leave_span) / 60 - approved_hours) > decimal.Decimal('0.001'):
            return approved_hours * decimal.Decimal(overlap) / decimal.Decimal(leave_span)
    return decimal.Decimal(max(0, overlap - lunch_overlap)) / 60

def save(state, data, user=None, exclude_submission=None, exclude_draft=None, check_period=True, require_on_call=False):
    if not isinstance(data, dict):
        raise Problem(400, 'Invalid time sheet.')
    technician = text(data.get('technician'), 'technician name', 160, True)
    signature = text(data.get('signature'), 'signature', 160, True)
    on_call = data.get('onCall')
    if on_call is not None and not isinstance(on_call, bool):
        raise Problem(400, 'Choose Yes or No for the on-call allowance.')
    if require_on_call and on_call is None:
        raise Problem(400, 'Choose Yes or No for the on-call allowance.')
    week = text(data.get('weekStart'), 'week starting date', 10, True)
    try:
        date = datetime.date.fromisoformat(week)
    except ValueError:
        raise Problem(400, 'Choose a valid week starting date.')
    if date.weekday() != 0:
        raise Problem(400, 'The week starting date must be a Monday.')
    if check_period:
        from timesheet_period import require_available
        require_available(state,technician,week,user,exclude_submission,exclude_draft)
    days = data.get('days')
    if not isinstance(days, list) or len(days) != 7:
        raise Problem(400, 'The time sheet must contain seven days.')
    cleaned, total, payable_total = [], decimal.Decimal(0), decimal.Decimal(0)
    default_start, default_finish = default_work_times(state)
    default_direct_hours = decimal.Decimal(minutes(default_finish) - minutes(default_start)) / 60
    timed_leave = timed_leave_for_week(state, technician, week)
    for index, day in enumerate(days):
        if not isinstance(day, dict):
            raise Problem(400, 'Invalid day entry.')
        day_name = DAY_NAMES[index]
        status, method = day.get('status'), day.get('method')
        if status not in TIME_SHEET_STATUSES or method not in ('direct', 'times'):
            raise Problem(400, 'Choose a valid work/leave type and entry method.')
        if status != 'Work' and method != 'direct':
            raise Problem(400, 'Enter leave using Direct hours.')
        other = text(day.get('other', ''), 'other leave description', 200, str(status).startswith('Other'))
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
        leave_row = timed_leave.get((date + datetime.timedelta(days=index)).isoformat())
        leave_hours = paid_leave_hours(leave_row, minutes(default_start), minutes(default_finish)) if leave_row else decimal.Decimal(0)
        net_direct=day.get('netDirectHours',False)
        if not isinstance(net_direct,bool):raise Problem(400,'Invalid direct hours format.')
        if status=='Work' and method=='direct' and net_direct and hours>0:
            if not start and not finish:
                default_paid_hours = default_direct_hours - lunch_hours - leave_hours
                if hours != default_paid_hours:
                    suffix = ' after approved leave' if leave_hours else ''
                    raise Problem(400, f'{day_name}: enter both actual start and finish times for custom Direct hours{suffix}.')
                start, finish = default_start, default_finish
            elif not (start and finish):
                raise Problem(400, f'{day_name}: enter both actual start and finish times for Direct hours.')
            duration=minutes(finish)-minutes(start)
            if duration<=0:raise Problem(400,f'{day_name}: finish time must be after start time.')
            leave_hours = paid_leave_hours(leave_row, minutes(start), minutes(finish)) if leave_row else decimal.Decimal(0)
            expected=decimal.Decimal(duration)/60-lunch_hours-leave_hours
            if hours>decimal.Decimal(duration)/60-leave_hours:raise Problem(400,f'{day_name}: paid hours cannot exceed the actual start–finish period after approved leave.')
            if expected!=hours:
                label = 'start, finish, lunch and approved leave' if leave_hours else 'start, finish and lunch'
                raise Problem(400, f'{day_name}: {label} do not match {hours:.2f} Direct paid hours. Enter actual start and finish times.')
        elif status=='Work' and method=='direct' and (start or finish):
            if not (start and finish):raise Problem(400,f'{day_name}: enter both start and finish times.')
            if minutes(finish)<minutes(start):raise Problem(400,f'{day_name}: finish time must not be before start time.')
        if not (net_direct and method=='direct'):hours -= lunch_hours
        total += hours
        if status == 'Work' or type_paid(status):
            payable_total += hours
        keep_times = status == 'Work' and entered_hours > 0 and (method == 'times' or bool(start and finish))
        cleaned.append({'status': status, 'other': other, 'notes': notes, 'method': method, 'hours': float(hours), 'enteredHours': float(entered_hours), 'netDirectHours':net_direct,'unpaidLunch': unpaid_lunch, 'lunchHours': float(lunch_hours), 'start': start if keep_times else '', 'finish': finish if keep_times else ''})
    entry = {'id': str(uuid.uuid4()), 'revision': 1, 'technician': technician, 'weekStart': week, 'signature': signature, 'notes': text(data.get('notes', ''), 'weekly notes', 4000), 'days': cleaned, 'total': float(total), 'payableTotal': float(payable_total), 'submittedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    if isinstance(on_call, bool):
        entry['onCall'] = on_call
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
    reason=text(data.get('editReason'), 'correction reason', 1000, True)
    payload={**data, 'signature':old['signature']}
    if not isinstance(payload.get('onCall'), bool) and isinstance(old.get('onCall'), bool):
        payload['onCall'] = old['onCall']
    _, entry=save(state,payload,user={'role':'admin','email':actor},exclude_submission=old['id'],check_period=payload.get('weekStart')!=old['weekStart'],require_on_call=False)
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
