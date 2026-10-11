"""Save staff details and account access together against one snapshot."""
import copy, accounts, timesheets, vehicles
from core import Problem

def read(state):
    return {**timesheets.settings(state),'users':[accounts.public(u) for u in accounts.users(state).values()],'vehicles':[{k:v.get(k,'') for k in ('id','registration','driver','makeModel')} for v in vehicles.fleet(state) if v.get('active',True)]}

def save(state, data, actor):
    original_name=data.get('originalName','')
    original_email=data.get('originalEmail','')
    staff=data.get('staff')
    account=data.get('account')
    if not staff and not account: raise Problem(400,'Enter staff or account details.')
    result=state
    if staff is not None:
        if not isinstance(staff,dict): raise Problem(400,'Invalid staff details.')
        rows=timesheets.settings(state)['technicians']
        if original_name:
            if staff.get('name')!=original_name: raise Problem(400,'Keep the existing staff name to preserve linked records.')
            if not any(r['name']==original_name for r in rows): raise Problem(409,'This staff member changed. Reload staff setup.')
            rows=[staff if r['name']==original_name else r for r in rows]
        else:
            rows=rows+[staff]
        result=timesheets.save_settings(state,{'technicians':rows})
    if account is not None:
        if not isinstance(account,dict): raise Problem(400,'Invalid account details.')
        address=accounts.email(account.get('email'))
        if original_email:
            if address!=original_email or original_email not in accounts.users(state): raise Problem(400,'Keep the existing sign-in email.')
        elif address in accounts.users(state): raise Problem(400,'This email already has an account. Edit its existing row.')
        if staff is not None and account.get('technician')!=staff['name']: raise Problem(400,'Link this account to the staff member being saved.')
        old=accounts.users(result).get(address)
        public={**account,'email':address,'name':account.get('name','').strip()}
        if old is None or any(old.get(k)!=public.get(k) for k in ('email','name','technician','role','active')):
            result=accounts.save_user(result,public,actor)
    elif original_email:
        raise Problem(400,'Keep the account email; disable account access instead.')
    return result


def delete(state,data,actor):
    if data.get('confirmed') is not True: raise Problem(400,'Confirm staff deletion first.')
    name=data.get('originalName','');address=data.get('originalEmail','')
    staff=timesheets.settings(state)['technicians'];users=accounts.users(state)
    if name and not any(row['name']==name for row in staff): raise Problem(409,'This staff member changed. Refresh Staff setup.')
    if address and address not in users: raise Problem(409,'This account changed. Refresh Staff setup.')
    if name and address and users[address].get('technician')!=name: raise Problem(409,'This account belongs to another staff member.')
    targets={email for email,user in users.items() if (name and user.get('technician')==name) or email==address}
    if not name and not targets: raise Problem(400,'Choose a staff member or account.')
    if actor['email'] in targets: raise Problem(400,'Another administrator must delete your own account.')
    remaining={email:user for email,user in users.items() if email not in targets}
    if not any(user.get('active') and user['role']=='admin' for user in remaining.values()): raise Problem(400,'Keep at least one active Admin account.')
    result=copy.deepcopy(state)
    if name:
        result=timesheets.save_settings(result,{'technicians':[row for row in staff if row['name']!=name]})
        result['vehicles']=copy.deepcopy(vehicles.fleet(state))
        for vehicle in result['vehicles']:
            if vehicle.get('driver')==name: vehicle['driver']=''
    result['users']=copy.deepcopy(remaining)
    for collection in ('sessions','loginLinks'):
        result[collection]={key:value for key,value in result.get(collection,{}).items() if value.get('email') not in targets}
    for email in targets: result.get('passwords',{}).pop(email,None)
    for item in result.get('mailOutbox',{}).values():
        if item.get('to') in targets and item.get('status')=='queued': item.update(status='cancelled',body='Cancelled when staff access was removed.')
    return result
