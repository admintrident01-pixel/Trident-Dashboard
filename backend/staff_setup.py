"""Save staff details and account access together against one snapshot."""
import accounts, timesheets, vehicles
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
