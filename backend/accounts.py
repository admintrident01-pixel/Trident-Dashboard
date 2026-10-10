"""Invited work-email accounts and single-use email sign-in links."""
import copy, datetime as dt, hashlib, re, secrets, time
from core import Problem

FIRST_ADMIN = 'bala@trice.nz'
LEGACY_OWNER = 'nikita.trident2024@gmail.com'

def users(state):
    return state.get('users', {
        LEGACY_OWNER: {'email': LEGACY_OWNER, 'name': 'Existing owner', 'technician': '', 'role': 'admin', 'active': True, 'verified': True},
        FIRST_ADMIN: {'email': FIRST_ADMIN, 'name': 'Bala', 'technician': 'Bala Ganesh Venkatesan', 'role': 'admin', 'active': True, 'verified': False},
    })

def email(value):
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,63}", value):
        raise Problem(400, 'Enter a valid work email address.')
    return value.lower()

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def public(user):
    return {key: user.get(key) for key in ('email', 'name', 'technician', 'role', 'active', 'verified')}

def resolve(state, token, verify):
    if token.startswith('trident_'):
        session = state.get('sessions', {}).get(digest(token))
        if not session or session['expires'] <= time.time():
            raise Problem(401, 'Your session expired. Sign in again.')
        address = session['email']
    else:
        address = verify(token)
    user = users(state).get(address)
    if not user or not user['active']:
        raise Problem(403, 'Your account is not active. Contact an administrator.')
    if token.startswith('trident_') and not user['verified']:
        raise Problem(401, 'Confirm your email address first.')
    return public(user)

def admin(user):
    if user['role'] != 'admin':
        raise Problem(403, 'Administrator access is required.')

def own(user, technician):
    if user['role'] != 'admin' and (not user['technician'] or technician != user['technician']):
        raise Problem(403, 'You can only submit or view your own time sheets and leave requests.')

def save_user(state, data, actor):
    if not isinstance(data, dict):
        raise Problem(400, 'Invalid user details.')
    address = email(data.get('email'))
    name, technician = data.get('name'), data.get('technician', '')
    if not isinstance(name, str) or not name.strip() or len(name) > 160 or not isinstance(technician, str) or len(technician) > 160:
        raise Problem(400, 'Enter a name and valid technician assignment.')
    if data.get('role') not in ('admin', 'tech') or not isinstance(data.get('active'), bool):
        raise Problem(400, 'Choose Admin or Technician and an active status.')
    from timesheets import settings
    if technician and technician not in {t['name'] for t in settings(state)['technicians']}:
        raise Problem(400, 'Choose a technician from Settings.')
    if data['role'] == 'tech' and not technician:
        raise Problem(400, 'Assign a technician so this user can submit their own time sheet and leave.')
    rows = copy.deepcopy(users(state))
    if len(rows) >= 200 and address not in rows:
        raise Problem(400, 'The account limit is 200 users.')
    if technician and any(u['email'] != address and u['active'] and u['technician'] == technician for u in rows.values()):
        raise Problem(400, 'This technician is already linked to another active account.')
    old = rows.get(address, {})
    rows[address] = {'email': address, 'name': name.strip(), 'technician': technician, 'role': data['role'], 'active': data['active'], 'verified': old.get('verified', False)}
    if not any(u['active'] and u['role'] == 'admin' for u in rows.values()):
        raise Problem(400, 'Keep at least one active Admin account.')
    if address == actor['email'] and (not data['active'] or data['role'] != 'admin'):
        raise Problem(400, 'Another administrator must change your own Admin access.')
    result = copy.deepcopy(state)
    result['users'] = rows
    # Any privilege change revokes existing email sessions and sign-in links.
    for collection in ('sessions', 'loginLinks'):
        result[collection] = {k: v for k, v in result.get(collection, {}).items() if v['email'] != address}
    result.setdefault('accountAudit', []).append({'by': actor['email'], 'email': address, 'role': data['role'], 'active': data['active'], 'at': dt.datetime.now(dt.timezone.utc).isoformat()})
    result['accountAudit'] = result['accountAudit'][-500:]
    return result

def issue(state, address, origin, ip='', invitation=False):
    import reminders
    result = copy.deepcopy(state)
    now = time.time()
    rates = {k: v for k, v in result.get('loginRates', {}).items() if v['until'] > now}
    key, ipkey = digest(address), 'ip:' + digest(ip)
    if not invitation:
        if rates.get(key, {}).get('until', 0) > now or rates.get(ipkey, {}).get('count', 0) >= 30:
            raise Problem(429, 'Please wait before requesting another sign-in email.')
        rates[key] = {'until': now + 60, 'count': 1}
        previous = rates.get(ipkey, {'until': now + 3600, 'count': 0})
        rates[ipkey] = {**previous, 'count': previous['count'] + 1}
    result['loginRates'] = dict(list(rates.items())[-2000:])
    user = users(result).get(address)
    if not user or not user['active']:
        return result
    result['users'] = copy.deepcopy(users(result))
    token = secrets.token_urlsafe(32)
    result['loginLinks'] = {k: v for k, v in result.get('loginLinks', {}).items() if v['expires'] > now and v['email'] != address}
    result['loginLinks'][digest(token)] = {'email': address, 'expires': now + 900}
    link = origin + '/#confirm=' + token
    subject = 'Confirm your Trident account' if invitation or not user['verified'] else 'Your Trident sign-in link'
    body = f"Hello {user['name']},\n\nConfirm your work email and sign in to Trident:\n{link}\n\nThis link expires in 15 minutes and can be used once. If you did not request it, ignore this email.\n\nTrident Community Equipment"
    reminders.queue(result, address, subject, body, 'account')
    return result

def consume(state, value):
    if not isinstance(value, str) or len(value) > 200:
        raise Problem(400, 'Invalid sign-in link.')
    item = state.get('loginLinks', {}).get(digest(value))
    if not item or item['expires'] <= time.time():
        raise Problem(401, 'This sign-in link expired or was already used. Request a new email.')
    user = users(state).get(item['email'])
    if not user or not user['active']:
        raise Problem(403, 'Your account is not active.')
    result = copy.deepcopy(state)
    result['users'] = copy.deepcopy(users(state))
    result['users'][item['email']]['verified'] = True
    del result['loginLinks'][digest(value)]
    now = time.time()
    existing = [(k, v) for k, v in result.get('sessions', {}).items() if v['expires'] > now]
    own_sessions = [k for k, v in existing if v['email'] == item['email']]
    discard = set(own_sessions[:-4])
    result['sessions'] = dict([(k, v) for k, v in existing if k not in discard][-999:])
    token = 'trident_' + secrets.token_urlsafe(32)
    result['sessions'][digest(token)] = {'email': item['email'], 'expires': now + 8 * 3600}
    return result, {'token': token, **public(result['users'][item['email']])}
