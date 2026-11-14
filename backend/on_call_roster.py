"""Weekly on-call roster, day cover, public pool and change notifications."""
import copy, datetime as dt, uuid
from zoneinfo import ZoneInfo
from core import Problem
import accounts, leave, timesheets

NZ = ZoneInfo('Pacific/Auckland')
LINK = 'https://trident-dashboard.admintrident01.workers.dev/#oncall'
PLAN_MONTHS = 6
HORIZON = 26  # Monday-start weeks; twenty-six weeks covers the next six months.
STATUSES = ('scheduled', 'awaiting', 'accepted', 'open')
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def now_auckland():
    return dt.datetime.now(NZ)


def _now(value=None):
    value = value or now_auckland()
    if value.tzinfo is None:
        value = value.replace(tzinfo=NZ)
    return value.astimezone(NZ)


def _monday(day):
    return day - dt.timedelta(days=day.weekday())


def _week(value):
    if not isinstance(value, str) or len(value) != 10:
        raise Problem(400, 'Choose a valid roster week.')
    try:
        day = dt.date.fromisoformat(value)
    except ValueError:
        raise Problem(400, 'Choose a valid roster week.')
    if day.weekday() != 0:
        raise Problem(400, 'Roster weeks must start on a Monday.')
    return day


def _short_dates(start):
    end = start + dt.timedelta(days=6)
    if start.month == end.month:
        return f"{start.day}–{end.day} {start:%b}"
    return f"{start.day} {start:%b} – {end.day} {end:%b}"


def _long_dates(start):
    end = start + dt.timedelta(days=6)
    if start.year == end.year and start.month == end.month:
        return f"Mon {start.day} – Sun {end.day} {start:%B %Y}"
    if start.year == end.year:
        return f"Mon {start.day} {start:%b} – Sun {end.day} {end:%b %Y}"
    return f"Mon {start.day} {start:%b %Y} – Sun {end.day} {end:%b %Y}"


def _header_dates(start):
    end = start + dt.timedelta(days=6)
    if start.year == end.year and start.month == end.month:
        return f"Mon {start.day} – Sun {end.day} {start:%B %Y}"
    if start.year == end.year:
        return f"Mon {start.day} {start:%b} – Sun {end.day} {end:%b %Y}"
    return f"Mon {start.day} {start:%b %Y} – Sun {end.day} {end:%b %Y}"


def _deadline(start):
    return dt.datetime.combine(start - dt.timedelta(days=1), dt.time(17, 0), NZ)


def _deadline_label(start):
    day = start - dt.timedelta(days=1)
    return f"Sun {day.day} {day:%b}, 5 pm"


def _day_label(day):
    return f"{WEEKDAYS[day.weekday()]} {day.day} {day:%b}"


def _month_label(day):
    return f"{day:%B %Y}"


def _initials(name):
    parts = [part for part in (name or '').split() if part]
    if not parts:
        return '?'
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _staff_rows(state):
    rows = []
    seen = set()
    for row in timesheets.settings(state)['technicians']:
        name = (row.get('name') or '').strip()
        if name and name.casefold() not in seen:
            rows.append({'name': name, 'staffType': row.get('staffType', 'technician')})
            seen.add(name.casefold())
    return rows


def _all_staff(state):
    return [row['name'] for row in _staff_rows(state)]


def _eligible_names(state, block):
    options = {row['name'].casefold(): row['name'] for row in _staff_rows(state)}
    raw = block.get('eligible') if isinstance(block.get('eligible'), list) else None
    if raw is None:
        raw = [row['name'] for row in _staff_rows(state) if row.get('staffType', 'technician') == 'technician']
    rows, seen = [], set()
    for name in raw:
        if not isinstance(name, str):
            continue
        key = name.strip().casefold()
        if key in options and key not in seen:
            rows.append(options[key])
            seen.add(key)
    if not rows:
        rows = [row['name'] for row in _staff_rows(state) if row.get('staffType', 'technician') == 'technician'] or _all_staff(state)
    block['eligible'] = rows
    return rows


def _staff_options(state):
    admins = {
        (user.get('technician') or user.get('name') or '').casefold()
        for user in accounts.users(state).values()
        if user.get('role') == 'admin' and user.get('active')
    }
    return [{'name': row['name'], 'staffType': row['staffType'], 'admin': row['name'].casefold() in admins}
            for row in _staff_rows(state)]


def _clean_order(block, state, strict=False):
    staff = _eligible_names(state, block)
    canonical = {name.casefold(): name for name in staff}
    raw = block.get('order') if isinstance(block.get('order'), list) else []
    order, seen = [], set()
    for name in raw:
        if not isinstance(name, str):
            continue
        key = name.strip().casefold()
        if key in canonical and key not in seen:
            order.append(canonical[key])
            seen.add(key)
    if strict and seen != set(canonical):
        raise Problem(400, 'Include every eligible staff member in the rotation order. Refresh the roster if staff changed.')
    for name in staff:
        if name.casefold() not in seen:
            order.append(name)
            seen.add(name.casefold())
    return order


def _anchor(block, monday):
    try:
        anchor = _week(block.get('anchor'))
    except Problem:
        anchor = monday
        block['anchor'] = anchor.isoformat()
    return anchor


def _rotation_name(order, anchor, week):
    if not order:
        return ''
    return order[((week - anchor).days // 7) % len(order)]


def _bump(record):
    record['revision'] = int(record.get('revision') or 0) + 1


def _log(block, at, actor, action, week, detail):
    block.setdefault('activity', []).append({
        'at': at.isoformat(), 'actor': actor, 'action': action,
        'weekStart': week.isoformat(), 'detail': detail,
    })
    block['activity'] = block['activity'][-100:]


def _open(record, at, actor, reason):
    record.update({
        'technician': '', 'status': 'open', 'manual': True,
        'acceptedAt': '', 'acceptedBy': '',
        'releasedAt': at.isoformat(), 'releasedBy': actor,
        'releaseReason': reason, 'updatedAt': at.isoformat(),
    })
    _bump(record)


def _clean_day_cover(record, week, eligible):
    """Keep only valid day overrides. Missing keys inherit the weekly owner."""
    canonical = {name.casefold(): name for name in eligible}
    raw = record.get('days')
    if not isinstance(raw, dict):
        record['days'] = {}
        return
    cleaned = {}
    for offset in range(7):
        key = (week + dt.timedelta(days=offset)).isoformat()
        if key not in raw:
            continue
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        name = value.strip()
        if not name:
            cleaned[key] = ''
            continue
        match = canonical.get(name.casefold())
        if match:
            cleaned[key] = match
    if cleaned != raw:
        record['days'] = cleaned


def _day_name(record, day):
    overrides = record.get('days') if isinstance(record.get('days'), dict) else {}
    key = day.isoformat()
    if key in overrides:
        return overrides.get(key) or ''
    return record.get('technician') or ''


def _day_rows(record, week, today):
    overrides = record.get('days') if isinstance(record.get('days'), dict) else {}
    rows = []
    for offset in range(7):
        day = week + dt.timedelta(days=offset)
        key = day.isoformat()
        override = key in overrides
        name = (overrides.get(key) or '') if override else (record.get('technician') or '')
        rows.append({
            'date': key,
            'weekday': WEEKDAYS[day.weekday()],
            'day': day.day,
            'month': f"{day:%b}",
            'label': _day_label(day),
            'technician': name,
            'initials': _initials(name),
            'override': override,
            'open': not name,
            'isToday': day == today,
        })
    return rows


def _manual_after_deadline(record, deadline):
    if not record.get('manual'):
        return False
    try:
        changed = dt.datetime.fromisoformat(record.get('updatedAt') or '')
    except ValueError:
        return False
    if changed.tzinfo is None:
        changed = changed.replace(tzinfo=NZ)
    return changed.astimezone(NZ) >= deadline


def _base(state, at):
    monday = _monday(at.date())
    block = state.setdefault('onCallRoster', {})
    block['eligible'] = _eligible_names(state, block)
    block['order'] = _clean_order(block, state)
    anchor = _anchor(block, monday)
    if not isinstance(block.get('weeks'), dict):
        block['weeks'] = {}
    if not isinstance(block.get('activity'), list):
        block['activity'] = []
    for offset in range(HORIZON):
        week = monday + dt.timedelta(days=7 * offset)
        key = week.isoformat()
        record = block['weeks'].get(key)
        if not isinstance(record, dict):
            record = {
                'weekStart': key,
                'technician': _rotation_name(block['order'], anchor, week),
                'status': 'scheduled', 'manual': False,
                'acceptedAt': '', 'acceptedBy': '',
                'releasedAt': '', 'releasedBy': '', 'releaseReason': '',
                'days': {},
                'updatedAt': at.isoformat(), 'revision': 1,
            }
            block['weeks'][key] = record
            continue
        record.setdefault('weekStart', key)
        record.setdefault('manual', False)
        record.setdefault('acceptedAt', '')
        record.setdefault('acceptedBy', '')
        record.setdefault('releasedAt', '')
        record.setdefault('releasedBy', '')
        record.setdefault('releaseReason', '')
        record.setdefault('days', {})
        record.setdefault('updatedAt', at.isoformat())
        record.setdefault('revision', 1)
        if record.get('status') not in STATUSES:
            record['status'] = 'scheduled'
        if record['status'] in ('scheduled', 'awaiting') and not record.get('technician'):
            record['technician'] = _rotation_name(block['order'], anchor, week)
    return block, monday


def _prepare(state, at, events=None):
    block, monday = _base(state, at)
    order_keys = {name.casefold() for name in block['order']}
    for offset in range(HORIZON):
        week = monday + dt.timedelta(days=7 * offset)
        record = block['weeks'][week.isoformat()]
        _clean_day_cover(record, week, block['eligible'])
        if record['status'] in ('scheduled', 'awaiting') and record.get('technician') and record['technician'].casefold() not in order_keys:
            previous = record['technician']
            detail = f"Week {week.isocalendar()[1]} moved to the open pool because {previous} is no longer eligible for on call."
            _open(record, at, 'Automatic', 'Staff member removed from on-call eligibility')
            _log(block, at, 'Automatic', 'open', week, detail)
            if events is not None:
                events.append({'kind': 'open', 'weekStart': week.isoformat(), 'technician': previous})
            continue
        if record['status'] == 'scheduled' and offset <= 1:
            record['status'] = 'awaiting'
            record['updatedAt'] = at.isoformat()
            _bump(record)
            if events is not None:
                events.append({'kind': 'awaiting', 'weekStart': week.isoformat(), 'technician': record['technician']})
        deadline = _deadline(week)
        missed = record['status'] == 'awaiting' and offset >= 1 and at >= deadline
        missed = missed and not _manual_after_deadline(record, deadline)
        if missed:
            previous = record['technician']
            detail = f"Week {week.isocalendar()[1]} moved to the open pool because {previous or 'the assigned technician'} did not accept by {_deadline_label(week)}."
            _open(record, at, 'Automatic', 'Acceptance deadline passed')
            _log(block, at, 'Automatic', 'open', week, detail)
            if events is not None:
                events.append({'kind': 'open', 'weekStart': week.isoformat(), 'technician': previous})
    return block, monday


def initialise(state, actor='', now=None):
    result = copy.deepcopy(state)
    _base(result, _now(now))
    return result


def _recipients(state):
    return [user for user in accounts.users(state).values()
            if user.get('active') and user.get('verified') and user.get('email')]


def _tech_users(state, technician):
    wanted = (technician or '').casefold()
    return [user for user in _recipients(state)
            if (user.get('technician') or '').casefold() == wanted]


def _actor_name(state, email):
    if not email or email == 'Automatic':
        return 'Automatic'
    user = accounts.users(state).get(email)
    return (user or {}).get('name') or email


def _status_label(record):
    return record['status'].capitalize() if record['status'] != 'awaiting' else 'Awaiting accept'


def _notify(state, block, week, event, detail, at):
    import reminders
    record = block['weeks'][week.isoformat()]
    number = week.isocalendar()[1]
    subjects = {
        'accept': f"On-call accepted — Week {number}",
        'handover': f"On-call changed — Week {number}",
        'release': f"On-call opened to the pool — Week {number}",
        'grab': f"On-call grabbed — Week {number}",
        'awaiting': f"Accept your on-call week — Week {number}",
        'auto-open': f"On-call open for grabs — Week {number}",
    }
    subject = subjects.get(event, f"On-call roster changed — Week {number}")
    body = (
        f"{detail}\n\n"
        f"Week {number}: {_long_dates(week)}\n"
        f"On call: {record.get('technician') or 'Open to anyone'}\n"
        f"Status: {_status_label(record)}\n\n"
        f"View the roster: {LINK}"
    )
    key = f"oncall:{week.isoformat()}:{event}:{record.get('revision', 0)}"
    context = {'weekStart': week.isoformat(), 'event': event}
    for user in _recipients(state):
        reminders.queue(state, user['email'], subject, body, 'oncall', key + ':' + user['email'], context)


def _notify_order(state, block, detail, at):
    import reminders
    key = f"oncall:order:{block.get('orderRevision', 0)}"
    subject = 'On-call rotation order updated'
    body = f"{detail}\n\nPosition 1 is on call now, then the roster rotates in this order.\n\nView the roster: {LINK}"
    for user in _recipients(state):
        reminders.queue(state, user['email'], subject, body, 'oncall', key + ':' + user['email'], {'event': 'order'})


def _notify_plan(state, block, plan, detail, at):
    import reminders
    key = f"oncall:plan:{block.get('planRevision', 0)}"
    subject = 'On-call roster planned for the next six months'
    rows = []
    for week, name in plan:
        rows.append(f"Week {week.isocalendar()[1]} ({_short_dates(week)}): {name or 'Open to anyone'}")
    body = detail + "\n\n" + "\n".join(rows) + f"\n\nView the roster: {LINK}"
    for user in _recipients(state):
        reminders.queue(state, user['email'], subject, body, 'oncall', key + ':' + user['email'], {'event': 'plan'})


def _notify_days(state, block, week, detail, at):
    import reminders
    record = block['weeks'][week.isoformat()]
    number = week.isocalendar()[1]
    key = f"oncall:days:{week.isoformat()}:{record.get('daysRevision', 0)}"
    subject = f"On-call day cover updated — Week {number}"
    lines = []
    for offset in range(7):
        day = week + dt.timedelta(days=offset)
        name = _day_name(record, day)
        lines.append(f"{_day_label(day)}: {name or 'Open to anyone'}")
    body = (
        f"{detail}\n\n"
        f"Week {number}: {_long_dates(week)}\n"
        f"Weekly cover: {record.get('technician') or 'Open to anyone'}\n"
        + "\n".join(lines) +
        f"\n\nView the roster: {LINK}"
    )
    for user in _recipients(state):
        reminders.queue(state, user['email'], subject, body, 'oncall', key + ':' + user['email'], {'event': 'days'})


def _notify_eligibility(state, block, detail, at):
    import reminders
    key = f"oncall:eligibility:{block.get('eligibilityRevision', 0)}"
    subject = 'On-call roster eligibility updated'
    body = detail + f"\n\nEligible staff: {', '.join(block.get('eligible', []))}\n\nView the roster: {LINK}"
    for user in _recipients(state):
        reminders.queue(state, user['email'], subject, body, 'oncall', key + ':' + user['email'], {'event': 'eligibility'})


def _actor(user):
    return user.get('name') or user.get('technician') or user.get('email') or 'A user'


def _my_technician(user):
    return (user.get('technician') or '').strip()


def _leave_days(state):
    rows = {}
    for request in leave.approved(state):
        rows.setdefault((request.get('technician') or '').casefold(), set()).update(request.get('dates') or [])
    return rows


def _away(state, technician, week):
    days = _leave_days(state).get((technician or '').casefold(), set())
    return any((week + dt.timedelta(days=offset)).isoformat() in days for offset in range(7))


def read(state, user, now=None):
    at = _now(now)
    snapshot = copy.deepcopy(state)
    block, monday = _prepare(snapshot, at)
    today = at.date()
    technician = _my_technician(user)
    admin = user.get('role') == 'admin'
    eligible_keys = {name.casefold() for name in block['eligible']}
    leave_days = _leave_days(snapshot)
    day_leave = {}
    horizon_end = monday + dt.timedelta(days=7 * HORIZON)
    for name in block['eligible']:
        for value in leave_days.get(name.casefold(), ()):
            if not isinstance(value, str):
                continue
            try:
                leave_day = dt.date.fromisoformat(value)
            except ValueError:
                continue
            if monday <= leave_day < horizon_end:
                day_leave.setdefault(value, []).append(name)
    rows = []
    default_plan = []
    for offset in range(HORIZON):
        week = monday + dt.timedelta(days=7 * offset)
        record = block['weeks'][week.isoformat()]
        days = _day_rows(record, week, today)
        custom_days = [day for day in days if day['override']]
        default_plan.append({
            'weekStart': week.isoformat(),
            'weekNumber': week.isocalendar()[1],
            'dates': _short_dates(week),
            'monthLabel': _month_label(week),
            'technician': record.get('technician') or '',
        })
        mine = bool(technician and record.get('technician') and technician.casefold() == record['technician'].casefold())
        status = record['status']
        options = []
        for name in block['order']:
            if name.casefold() == (record.get('technician') or '').casefold():
                continue
            options.append({'name': name, 'away': _away(snapshot, name, week)})
        rows.append({
            'weekStart': week.isoformat(),
            'weekNumber': week.isocalendar()[1],
            'year': week.isocalendar()[0],
            'monthLabel': _month_label(week),
            'dates': _short_dates(week),
            'datesLong': _long_dates(week),
            'status': status,
            'statusLabel': _status_label(record),
            'technician': record.get('technician') or '',
            'initials': _initials(record.get('technician')),
            'mine': mine,
            'isCurrent': offset == 0,
            'acceptedAt': record.get('acceptedAt') or '',
            'acceptedBy': record.get('acceptedBy') or '',
            'deadline': _deadline(week).isoformat(),
            'deadlineLabel': _deadline_label(week),
            'canAccept': mine and status == 'awaiting',
            'canHandover': (admin and status in ('awaiting', 'accepted', 'open')) or (mine and status in ('awaiting', 'accepted')),
            'canRelease': (admin or mine) and status in ('awaiting', 'accepted'),
            'canGrab': status == 'open' and bool(technician) and technician.casefold() in eligible_keys,
            'canResend': (admin or mine) and status == 'awaiting',
            'days': days,
            'customDays': len(custom_days),
            'dayNote': ', '.join(f"{day['weekday']} {day['day']} {day['technician'] or 'Open'}" for day in custom_days),
            'handoverOptions': options,
        })
    activity = []
    for row in reversed(block.get('activity', [])[-20:]):
        activity.append({**row, 'actorName': _actor_name(snapshot, row.get('actor', ''))})
    return {
        'currentWeek': monday.isoformat(),
        'weekNumber': monday.isocalendar()[1],
        'year': monday.isocalendar()[0],
        'headerDates': _header_dates(monday),
        'rows': rows,
        'order': block['order'],
        'eligible': block['eligible'],
        'staffOptions': _staff_options(snapshot),
        'defaultPlan': default_plan,
        'dayLeave': day_leave,
        'planMonths': PLAN_MONTHS,
        'planWeeks': HORIZON,
        'planRange': f"{_short_dates(monday)} – {_short_dates(monday + dt.timedelta(days=7 * (HORIZON - 1)))}",
        'openWeeks': sum(1 for row in rows if row['status'] == 'open'),
        'activity': activity,
        'myTechnician': technician,
        'isAdmin': admin,
        'timezone': 'NZDT' if at.dst() else 'NZST',
    }


def _record_for(block, week):
    record = block['weeks'].get(week.isoformat())
    if not record:
        raise Problem(404, 'That roster week is no longer available. Refresh the page.')
    return record


def action(state, data, user, now=None):
    if not isinstance(data, dict):
        raise Problem(400, 'Invalid on-call change.')
    kind = data.get('action')
    if kind not in ('accept', 'handover', 'release', 'grab', 'order', 'plan', 'eligibility', 'days', 'resend'):
        raise Problem(400, 'Choose a valid on-call action.')
    at = _now(now)
    result = copy.deepcopy(state)
    events = []
    block, monday = _prepare(result, at, events)
    _notify_events(result, block, [event for event in events if event['kind'] == 'open'], at)
    actor_name = _actor(user)
    technician = _my_technician(user)
    admin = user.get('role') == 'admin'
    quiet = data.get('notify') is False and admin
    if kind == 'order':
        accounts.admin(user)
        names = data.get('order')
        if not isinstance(names, list) or not 1 <= len(names) <= 200:
            raise Problem(400, 'Choose a valid rotation order.')
        staff = {name.casefold(): name for name in _eligible_names(result, block)}
        order, seen = [], set()
        for name in names:
            if not isinstance(name, str) or not name.strip():
                raise Problem(400, 'Choose a valid rotation order.')
            key = name.strip().casefold()
            if key not in staff:
                raise Problem(400, 'Choose only eligible staff from Settings.')
            if key in seen:
                raise Problem(400, 'Each staff member can appear only once.')
            order.append(staff[key])
            seen.add(key)
        if seen != set(staff):
            raise Problem(400, 'Include every eligible staff member in the rotation order. Refresh if staff changed.')
        block['order'] = order
        block['anchor'] = monday.isoformat()
        block['orderRevision'] = int(block.get('orderRevision') or 0) + 1
        for offset in range(HORIZON):
            week = monday + dt.timedelta(days=7 * offset)
            record = block['weeks'][week.isoformat()]
            if record.get('manual') or record['status'] == 'accepted':
                continue
            record.update({
                'technician': _rotation_name(order, monday, week),
                'status': 'awaiting' if offset <= 1 else 'scheduled',
                'acceptedAt': '', 'acceptedBy': '', 'updatedAt': at.isoformat(),
            })
            _bump(record)
        detail = f"{actor_name} updated the rotation order: {' → '.join(order)}."
        _log(block, at, user['email'], 'order', monday, detail)
        if not quiet:
            _notify_order(result, block, detail, at)
        return result

    if kind == 'eligibility':
        accounts.admin(user)
        names = data.get('eligible')
        if not isinstance(names, list) or not 1 <= len(names) <= 200:
            raise Problem(400, 'Choose at least one staff member for the on-call roster.')
        options = {row['name'].casefold(): row['name'] for row in _staff_rows(result)}
        eligible, seen = [], set()
        for name in names:
            if not isinstance(name, str) or not name.strip():
                raise Problem(400, 'Choose a valid staff member.')
            key = name.strip().casefold()
            if key not in options:
                raise Problem(400, 'Choose staff members from Settings. Refresh if staff changed.')
            if key in seen:
                raise Problem(400, 'Each staff member can appear only once.')
            eligible.append(options[key])
            seen.add(key)
        before = tuple(block['eligible'])
        block['eligible'] = eligible
        old_order = block.get('order') or []
        kept = [name for name in old_order if name.casefold() in seen]
        kept_keys = {name.casefold() for name in kept}
        block['order'] = kept + [name for name in eligible if name.casefold() not in kept_keys]
        block['eligibilityRevision'] = int(block.get('eligibilityRevision') or 0) + 1
        anchor = _anchor(block, monday)
        horizon_end = monday + dt.timedelta(days=7 * (HORIZON - 1))
        for offset in range(HORIZON):
            week = monday + dt.timedelta(days=7 * offset)
            record = block['weeks'][week.isoformat()]
            current = record.get('technician') or ''
            if record['status'] == 'accepted':
                continue
            if current and current.casefold() in seen and record.get('manual'):
                continue
            if record['status'] in ('scheduled', 'awaiting') and not record.get('manual'):
                replacement = _rotation_name(block['order'], anchor, week)
                if replacement.casefold() != current.casefold():
                    record.update({'technician': replacement,
                                   'status': 'awaiting' if offset <= 1 else 'scheduled',
                                   'acceptedAt': '', 'acceptedBy': '', 'updatedAt': at.isoformat()})
                    _bump(record)
                continue
            if current and current.casefold() not in seen:
                record.update({'technician': _rotation_name(block['order'], anchor, week),
                               'status': 'awaiting' if offset <= 1 else 'scheduled', 'manual': False,
                               'acceptedAt': '', 'acceptedBy': '', 'updatedAt': at.isoformat()})
                _bump(record)
        detail = f"{actor_name} set on-call eligibility: {', '.join(eligible)}."
        _log(block, at, user['email'], 'eligibility', monday, detail)
        if tuple(eligible) != before and not quiet:
            _notify_eligibility(result, block, detail, at)
        return result

    if kind == 'plan':
        accounts.admin(user)
        entries = data.get('plan')
        if not isinstance(entries, list) or not 1 <= len(entries) <= HORIZON:
            raise Problem(400, 'Choose the weeks to plan for the next six months.')
        eligible = {name.casefold(): name for name in block['eligible']}
        horizon_end = monday + dt.timedelta(days=7 * (HORIZON - 1))
        plan, seen = [], set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise Problem(400, 'Choose a valid on-call plan.')
            week = _week(entry.get('weekStart'))
            if week < monday or week > horizon_end:
                raise Problem(400, 'Choose a week from the next six months.')
            if week in seen:
                raise Problem(400, 'Choose each week only once.')
            name = entry.get('technician') or ''
            if not isinstance(name, str):
                raise Problem(400, 'Choose a valid staff member.')
            key = name.strip().casefold()
            if key and key not in eligible:
                raise Problem(400, 'Choose only staff selected for the on-call roster.')
            plan.append((week, eligible.get(key, '')))
            seen.add(week)
        block['planRevision'] = int(block.get('planRevision') or 0) + 1
        changed = 0
        for week, name in plan:
            record = _record_for(block, week)
            offset = (week - monday).days // 7
            current = record.get('technician') or ''
            if not name:
                if record['status'] != 'open' or current:
                    _open(record, at, user['email'], 'Planned as an open week')
                    changed += 1
                record['manual'] = True
                continue
            same = current.casefold() == name.casefold()
            if same and record['status'] == 'accepted':
                record['manual'] = True
                continue
            record.update({
                'technician': name,
                'status': 'awaiting' if offset <= 1 else 'scheduled',
                'manual': True,
                'acceptedAt': record.get('acceptedAt', '') if same else '',
                'acceptedBy': record.get('acceptedBy', '') if same else '',
                'releasedAt': '', 'releasedBy': '', 'releaseReason': '',
                'updatedAt': at.isoformat(),
            })
            _bump(record)
            changed += 1
        detail = f"{actor_name} confirmed the next six months of the on-call roster."
        _log(block, at, user['email'], 'plan', monday, detail)
        if changed and not quiet:
            _notify_plan(result, block, plan, detail, at)
        return result

    if kind == 'days':
        accounts.admin(user)
        week = _week(data.get('weekStart'))
        horizon_end = monday + dt.timedelta(days=7 * (HORIZON - 1))
        if week < monday or week > horizon_end:
            raise Problem(400, 'Choose a week from the current roster.')
        record = _record_for(block, week)
        entries = data.get('days')
        if not isinstance(entries, list) or not 1 <= len(entries) <= 7:
            raise Problem(400, 'Choose day cover for at least one day.')
        eligible = {name.casefold(): name for name in block['eligible']}
        approved = _leave_days(result)
        current_days = record.get('days') if isinstance(record.get('days'), dict) else {}
        next_days = dict(current_days)
        changes, seen = [], set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise Problem(400, 'Choose valid day cover.')
            value = entry.get('date')
            if not isinstance(value, str) or len(value) != 10:
                raise Problem(400, 'Choose a valid day.')
            try:
                day = dt.date.fromisoformat(value)
            except ValueError:
                raise Problem(400, 'Choose a valid day.')
            if day < week or day > week + dt.timedelta(days=6):
                raise Problem(400, 'Choose a day from the selected week.')
            key = day.isoformat()
            if key in seen:
                raise Problem(400, 'Choose each day only once.')
            seen.add(key)
            choice = entry.get('technician')
            if choice is None:
                new_name = None
            elif not isinstance(choice, str):
                raise Problem(400, 'Choose a valid staff member for each day.')
            else:
                value = choice.strip()
                if not value:
                    new_name = ''
                else:
                    canonical = eligible.get(value.casefold())
                    if not canonical:
                        raise Problem(400, 'Choose only staff selected for the on-call roster.')
                    if key in approved.get(canonical.casefold(), set()):
                        raise Problem(409, f"{canonical} has approved leave on {_day_label(day)}. Choose another person or open the day.")
                    new_name = canonical
            previous = current_days.get(key) if key in current_days else None
            if new_name != previous:
                changes.append((day, previous, new_name))
            if new_name is None:
                next_days.pop(key, None)
            else:
                next_days[key] = new_name
        if not changes:
            return result
        record['days'] = next_days
        record['daysRevision'] = int(record.get('daysRevision') or 0) + 1
        record['updatedAt'] = at.isoformat()
        _bump(record)
        number = week.isocalendar()[1]
        labels = []
        for day, _, new_name in changes:
            shown = record.get('technician') or '' if new_name is None else new_name
            labels.append(f"{_day_label(day)} {shown or 'Open'}")
        detail = f"{actor_name} updated day cover for Week {number}: {', '.join(labels)}."
        _log(block, at, user['email'], 'days', week, detail)
        if not quiet:
            _notify_days(result, block, week, detail, at)
        return result

    week = _week(data.get('weekStart'))
    horizon_end = monday + dt.timedelta(days=7 * (HORIZON - 1))
    if week < monday or week > horizon_end:
        raise Problem(400, 'Choose a week from the current roster.')
    record = _record_for(block, week)
    number = week.isocalendar()[1]
    mine = bool(technician and record.get('technician') and technician.casefold() == record['technician'].casefold())

    if kind == 'accept':
        if not mine:
            raise Problem(403, 'Only the assigned technician can accept this week.')
        if record['status'] != 'awaiting':
            raise Problem(409, 'This week is not waiting for acceptance.')
        record.update({
            'status': 'accepted', 'acceptedAt': at.isoformat(),
            'acceptedBy': user['email'], 'updatedAt': at.isoformat(),
        })
        _bump(record)
        detail = f"{actor_name} accepted on call for Week {number}."
        _log(block, at, user['email'], 'accept', week, detail)
        _notify(result, block, week, 'accept', detail, at)
        return result

    if kind == 'release':
        if not (admin or mine):
            raise Problem(403, 'Only the assigned technician or an admin can release this week.')
        if record['status'] == 'open':
            raise Problem(409, 'This week is already open to everyone.')
        if record['status'] not in ('awaiting', 'accepted'):
            raise Problem(409, 'This week is not published for handover yet.')
        previous = record.get('technician')
        _open(record, at, user['email'], 'Released by ' + actor_name)
        detail = f"{actor_name} released Week {number} to the open pool."
        if previous and previous.casefold() != (technician or '').casefold():
            detail = f"{actor_name} released {previous}'s Week {number} to the open pool."
        _log(block, at, user['email'], 'release', week, detail)
        if not quiet:
            _notify(result, block, week, 'release', detail, at)
        return result

    if kind == 'handover':
        if not (admin or mine):
            raise Problem(403, 'Only the assigned technician or an admin can hand over this week.')
        if record['status'] not in ('awaiting', 'accepted') and not (admin and record['status'] == 'open'):
            raise Problem(409, 'This week is not published for handover yet.')
        target = (data.get('technician') or '').strip() if isinstance(data.get('technician') or '', str) else ''
        if len(target) > 160:
            raise Problem(400, 'Choose a valid technician.')
        if not target:
            if record['status'] == 'open':
                raise Problem(400, 'Choose a technician for this open week.')
            previous = record.get('technician')
            _open(record, at, user['email'], 'Released by ' + actor_name)
            detail = f"{actor_name} released Week {number} to the open pool."
            if previous and previous.casefold() != (technician or '').casefold():
                detail = f"{actor_name} released {previous}'s Week {number} to the open pool."
            _log(block, at, user['email'], 'release', week, detail)
            if not quiet:
                _notify(result, block, week, 'release', detail, at)
            return result
        staff = {name.casefold(): name for name in block['eligible']}
        canonical = staff.get(target.casefold())
        if not canonical:
            raise Problem(400, 'Choose an eligible staff member from the roster.')
        if record.get('technician') and canonical.casefold() == record['technician'].casefold():
            raise Problem(400, 'Choose a different technician, or release the week to the pool.')
        if _away(result, canonical, week):
            raise Problem(409, f"{canonical} has approved leave that week. Choose another technician or open the pool.")
        record.update({
            'technician': canonical, 'status': 'awaiting', 'manual': True,
            'acceptedAt': '', 'acceptedBy': '', 'releasedAt': '', 'releasedBy': '',
            'releaseReason': '', 'updatedAt': at.isoformat(),
        })
        _bump(record)
        detail = f"{actor_name} handed Week {number} to {canonical}."
        _log(block, at, user['email'], 'handover', week, detail)
        if not quiet:
            _notify(result, block, week, 'handover', detail, at)
        return result

    if kind == 'grab':
        if record['status'] != 'open':
            raise Problem(409, 'Someone else already took this week. Refresh the roster.')
        if not technician:
            raise Problem(403, 'Only eligible staff can grab an open week.')
        if technician.casefold() not in {name.casefold() for name in block['order']}:
            raise Problem(403, 'Your staff profile is not eligible for the on-call roster. Ask an admin to update it.')
        if _away(result, technician, week):
            raise Problem(409, 'You have approved leave that week, so you cannot take it.')
        record.update({
            'technician': technician, 'status': 'accepted', 'manual': True,
            'acceptedAt': at.isoformat(), 'acceptedBy': user['email'],
            'updatedAt': at.isoformat(),
        })
        _bump(record)
        detail = f"{actor_name} grabbed Week {number}."
        _log(block, at, user['email'], 'grab', week, detail)
        _notify(result, block, week, 'grab', detail, at)
        return result

    if kind == 'resend':
        if not (admin or mine):
            raise Problem(403, 'Only the assigned technician or an admin can resend this email.')
        if record['status'] != 'awaiting':
            raise Problem(409, 'Only a week waiting for acceptance can resend the email.')
        import reminders
        recipients = _tech_users(result, record.get('technician'))
        if not recipients:
            raise Problem(404, f"No active Trident account is linked to {record.get('technician') or 'this technician'}.")
        for recipient in recipients:
            body = (
                f"Hello {recipient.get('name') or record.get('technician')},\n\n"
                f"You are on call for Week {number} ({_long_dates(week)}).\n"
                f"Please accept by {_deadline_label(week)}. If you do not accept, the week moves to the open pool.\n\n"
                f"Accept or view the roster: {LINK}"
            )
            reminders.queue(result, recipient['email'], f"Accept your on-call week — Week {number}", body,
                            'oncall', f"oncall:resend:{week.isoformat()}:{uuid.uuid4().hex}:{recipient['email']}",
                            {'weekStart': week.isoformat(), 'event': 'resend'})
        detail = f"{actor_name} resent the acceptance email to {record.get('technician')}."
        _log(block, at, user['email'], 'resend', week, detail)
        return result

    raise Problem(400, 'Choose a valid on-call action.')


def _notify_events(state, block, events, at):
    for event in events:
        week = dt.date.fromisoformat(event['weekStart'])
        number = week.isocalendar()[1]
        if event['kind'] == 'awaiting':
            detail = f"Week {number} is waiting for {event.get('technician') or 'the assigned technician'} to accept."
            _notify(state, block, week, 'awaiting', detail, at)
        else:
            detail = f"Week {number} is now open to all technicians because {event.get('technician') or 'the assigned technician'} did not accept in time."
            _notify(state, block, week, 'auto-open', detail, at)


def rollover(state, now=None):
    at = _now(now)
    events = []
    block, _ = _prepare(state, at, events)
    _notify_events(state, block, events, at)
    return len(events)
