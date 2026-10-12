"""Due-date calculations, durable mail queue, and TLS SMTP delivery."""
import copy, datetime as dt, os, smtplib, ssl, uuid
from email.message import EmailMessage
from zoneinfo import ZoneInfo
from core import Problem
import accounts, vehicles

DEFAULTS = {'timesheetWeekday': 4, 'timesheetTime': '17:00', 'timesheetLeadHours': 24, 'vehicleLeadDays': 7, 'automaticTimesheets': False, 'automaticVehicles': False}

def settings(state):
    return {**DEFAULTS, **state.get('reminderSettings', {})}

def save_settings(state, data):
    if not isinstance(data, dict): raise Problem(400, 'Invalid reminder settings.')
    for key, lo, hi in [('timesheetWeekday', 0, 6), ('timesheetLeadHours', 0, 168), ('vehicleLeadDays', 0, 30)]:
        if type(data.get(key)) is not int or not lo <= data[key] <= hi: raise Problem(400, 'Enter valid reminder timing.')
    import re
    if not isinstance(data.get('timesheetTime'), str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', data['timesheetTime']): raise Problem(400, 'Choose a valid time sheet due time.')
    if any(type(data.get(k)) is not bool for k in ('automaticTimesheets', 'automaticVehicles')): raise Problem(400, 'Choose whether automatic reminders are enabled.')
    result = copy.deepcopy(state)
    result['reminderSettings'] = {k: data[k] for k in DEFAULTS}
    return result

def mail_mode(local):
    # Local development never sends business email; previews remain private.
    return 'preview' if local else 'smtp' if os.environ.get('SMTP_HOST') and os.environ.get('SMTP_FROM') else 'unconfigured'

def require_mail(local):
    if mail_mode(local) == 'unconfigured': raise Problem(503, 'Email delivery is not configured. Ask your administrator to connect the email service.')

def queue(state, recipient, subject, body, kind, key=None):
    mails = state.setdefault('mailOutbox', {})
    if key and any(m.get('dedupe') == key for m in mails.values()): return False
    mid = str(uuid.uuid4())
    mails[mid] = {'id': mid, 'to': recipient, 'subject': subject, 'body': body, 'kind': kind, 'status': 'queued', 'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(), 'dedupe': key or ''}
    # Keep pending mail and a bounded history; automatic dedupe keys are separate.
    finished = [k for k, m in mails.items() if m['status'] in ('sent', 'preview', 'failed')]
    for k in finished[:-300]: del mails[k]
    return True

def dashboard(state, now=None):
    now = now or dt.datetime.now(ZoneInfo('Pacific/Auckland'))
    now = now.astimezone(ZoneInfo('Pacific/Auckland'))
    cfg = settings(state)
    active_users = [u for u in accounts.users(state).values() if u['active'] and u.get('technician')]
    rows = []
    monday = now.date() - dt.timedelta(days=now.weekday())
    for week in (monday - dt.timedelta(days=7), monday):
        due = dt.datetime.combine(week + dt.timedelta(days=cfg['timesheetWeekday']), dt.time.fromisoformat(cfg['timesheetTime']), ZoneInfo('Pacific/Auckland'))
        for user in active_users:
            if any(s['technician'] == user['technician'] and s['weekStart'] == week.isoformat() for s in state.get('timesheets', {}).values()): continue
            rows.append({'id': 'sheet:' + user['email'] + ':' + week.isoformat(), 'kind': 'timesheet', 'recipient': user['email'], 'name': user['technician'], 'weekStart': week.isoformat(), 'due': due.isoformat(), 'hoursRemaining': round((due - now).total_seconds() / 3600, 1)})
    for vehicle in vehicles.fleet(state):
        if not vehicle['active']: continue
        checks = [c for c in state.get('vehicleChecks', {}).values() if c['vehicleId'] == vehicle['id']]
        check = max(checks, key=lambda c: (c['checkDate'], c['createdAt'])) if checks else {}
        baseline = vehicle.get('baseline', {})
        if baseline.get('checkDate', '') > check.get('checkDate', ''): check = baseline
        checkdate = check.get('checkDate')
        due = check.get('nextCheckDue') or ((dt.date.fromisoformat(checkdate) + dt.timedelta(days=30)).isoformat() if checkdate else '')
        user = next((u for u in active_users if u['technician'] == vehicle['driver']), None)
        rows.append({'id': 'vehicle:' + vehicle['id'], 'kind': 'vehicle', 'vehicleId': vehicle['id'], 'registration': vehicle['registration'], 'name': vehicle['driver'], 'recipient': user['email'] if user else '', 'due': due, 'daysRemaining': (dt.date.fromisoformat(due) - now.date()).days if due else None})
    return rows

def enqueue_reminder(state, row, automatic=False, now=None):
    if not row['recipient']: raise Problem(400, 'Link the assigned driver to an active user in Settings before sending a reminder.')
    from accounts import users
    if not users(state)[row['recipient']].get('verified'): raise Problem(400, 'The recipient must confirm their email before receiving reminders.')
    now = now or dt.datetime.now(ZoneInfo('Pacific/Auckland'))
    if row['kind'] == 'vehicle':
        remaining = row['daysRemaining']
        timing = 'has no recorded check; please complete one' if remaining is None else f'is overdue by {abs(remaining)} days' if remaining < 0 else 'is due today' if remaining == 0 else f'is due in {remaining} days'
        subject = 'Vehicle check reminder · ' + (row['registration'] or row['vehicleId'])
        body = f"Hello {row['name']},\n\nYour vehicle check for {row['registration'] or row['vehicleId']} {timing}.\nDue date: {row['due'] or 'No check recorded'}.\n\nPlease sign in to Trident and submit a vehicle check.\n\nTrident Community Equipment"
    else:
        subject = 'Weekly time sheet reminder · ' + row['weekStart']
        body = f"Hello {row['name']},\n\nYour time sheet for the week starting {row['weekStart']} is still awaiting submission.\nDue: {row['due']} (Pacific/Auckland).\n\nPlease sign in to Trident, sign and submit your time sheet.\n\nTrident Community Equipment"
    key = f"{row['id']}:{row['due']}:{now.date().isoformat()}"
    # Automatic runs send at most once per recipient/due date/Auckland day.
    if automatic and key in state.get('reminderSentKeys', {}): return False
    if queue(state, row['recipient'], subject, body, row['kind'], key if automatic else None):
        if automatic:
            marks = state.setdefault('reminderSentKeys', {})
            marks[key] = now.date().isoformat()
            state['reminderSentKeys'] = {k: v for k, v in marks.items() if v >= (now.date() - dt.timedelta(days=45)).isoformat()}
        return True
    return False

def due_reminders(state, now=None):
    result = copy.deepcopy(state)
    cfg = settings(state)
    count = 0
    for row in dashboard(state, now):
        enabled = cfg['automaticVehicles'] if row['kind'] == 'vehicle' else cfg['automaticTimesheets']
        due = (row['daysRemaining'] is None or row['daysRemaining'] <= cfg['vehicleLeadDays']) if row['kind'] == 'vehicle' else row['hoursRemaining'] <= cfg['timesheetLeadHours']
        if enabled and due and row['recipient'] and accounts.users(state)[row['recipient']].get('verified'):
            count += enqueue_reminder(result, row, True, now)
    return result, count

def deliver(store, local=False):
    """Claim mail before sending: concurrent runners cannot send the same entry."""
    require_mail(local)
    processed = 0
    for _ in range(100):
        revision, state = store.read()
        item = next((m for m in state.get('mailOutbox', {}).values() if m['status'] == 'queued'), None)
        if not item: break
        mid = item['id']
        state['mailOutbox'][mid]['status'] = 'preview' if local else 'sending'
        if not store.commit(revision, state): continue
        if local:
            processed += 1
            continue
        status = 'sent'
        try:
            msg = EmailMessage()
            msg['From'], msg['To'], msg['Subject'] = os.environ['SMTP_FROM'], item['to'], item['subject']
            msg.set_content(item['body'])
            port = int(os.environ.get('SMTP_PORT', '587'))
            context = ssl.create_default_context()
            factory = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
            kwargs = {'context': context} if port == 465 else {}
            with factory(os.environ['SMTP_HOST'], port, timeout=20, local_hostname='trice.nz', **kwargs) as smtp:
                if port != 465: smtp.starttls(context=context)
                if os.environ.get('SMTP_USER'): smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
                smtp.send_message(msg)
        except Exception as mail_error:
            # A delivery error can be ambiguous; never retry silently.
            import logging
            logging.exception('SMTP delivery failed: %s; code=%s', type(mail_error).__name__, getattr(mail_error, 'smtp_code', 'none'))
            status = 'failed'
        for _ in range(10):
            rev, current = store.read()
            if mid not in current.get('mailOutbox', {}): break
            current['mailOutbox'][mid].update(status=status, finishedAt=dt.datetime.now(dt.timezone.utc).isoformat())
            if current['mailOutbox'][mid]['kind'] == 'account': current['mailOutbox'][mid]['body'] = 'Confirmation link removed after delivery attempt. Request a new email if needed.'
            if store.commit(rev, current): break
        processed += 1
    return processed


def archive_mail(state,data,actor):
    if not isinstance(data,dict) or type(data.get('archived')) is not bool:
        raise Problem(400,'Choose whether to archive or restore this email.')
    mid=data.get('id')
    if not isinstance(mid,str) or mid not in state.get('mailOutbox',{}):
        raise Problem(404,'This email no longer exists.')
    result=copy.deepcopy(state)
    message=result['mailOutbox'][mid]
    message['archived']=data['archived']
    message['archivedAt']=dt.datetime.now(dt.timezone.utc).isoformat() if data['archived'] else ''
    message['archivedBy']=actor if data['archived'] else ''
    return result
