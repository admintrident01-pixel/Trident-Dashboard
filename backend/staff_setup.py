"""Save staff details and account access together against one snapshot."""
import copy, accounts, timesheets, vehicles
from core import Problem

def read(state):
    return {**timesheets.settings(state),'users':[accounts.public(u) for u in accounts.users(state).values()],'vehicles':[{k:v.get(k,'') for k in ('id','registration','driver','active')} for v in vehicles.fleet(state)]}

def allocate_vehicle(state,name,vehicle_id,registration=None,active=True):
    from timesheets import text
    if not isinstance(active,bool):raise Problem(400,'Choose Yes or No for Active vehicle.')
    result=copy.deepcopy(state);fleet=copy.deepcopy(vehicles.fleet(state));people=copy.deepcopy(timesheets.settings(state)['technicians'])
    person=next((row for row in people if name and row['name'].casefold()==name.strip().casefold()),None)
    if name and not person:raise Problem(400,'Choose an existing staff member.')
    name=person['name'] if person else ''
    if active and vehicle_id and not name:raise Problem(400,'Allocate active vehicles to a staff member.')
    selected=next((row for row in fleet if row['id']==vehicle_id),None)
    if vehicle_id=='new':
        number=len(fleet)+1;used={v['id'] for v in fleet}|set(state.get('removedVehicles',{}))
        while f'VEH-{number:02}' in used:number+=1
        selected={'id':f'VEH-{number:02}','registration':'','driver':'','active':False,'baseline':{}};fleet.append(selected)
    elif vehicle_id and not selected:raise Problem(400,'Choose a vehicle from the current fleet.')
    reg=text(registration if registration is not None else selected.get('registration','') if selected else '', 'vehicle registration',30,bool(selected)).upper()
    if selected and reg!=selected.get('registration','') and any(v['id']!=selected['id'] and v.get('registration','').upper()==reg for v in fleet):raise Problem(400,'This registration already belongs to another vehicle.')
    previous=selected.get('driver','') if selected else ''
    for vehicle in fleet:
        if name and vehicle.get('driver','').casefold()==name.casefold():vehicle.update(driver='',active=False)
    for row in people:
        if previous and previous.casefold()!=name.casefold() and row['name'].casefold()==previous.casefold():row.update(hasVehicle=False,rego='')
        if name and row['name'].casefold()==name.casefold():row.update(hasVehicle=bool(selected),rego=reg if selected else '')
    if selected:selected.update(registration=reg,driver=name,active=bool(active and name))
    result['vehicles']=fleet;result['staffSettings']={'technicians':people}
    return result

def save_vehicle(state,data):
    vehicle=data.get('vehicle')
    if not isinstance(vehicle,dict):raise Problem(400,'Enter vehicle details.')
    vehicle_id=vehicle.get('id') or 'new'
    if not isinstance(vehicle_id,str):raise Problem(400,'Choose a valid vehicle.')
    name=vehicle.get('staff','')
    if not isinstance(name,str):raise Problem(400,'Choose a staff member.')
    return allocate_vehicle(state,name,vehicle_id,vehicle.get('registration'),vehicle.get('active',False))


def save(state, data, actor):
    if data.get('action')=='vehicle':return save_vehicle(state,data)
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
        if 'vehicleId' in staff:
            if staff.get('hasVehicle',True) and not staff.get('vehicleId'):raise Problem(400,'Choose a vehicle or select No vehicle.')
            result=allocate_vehicle(result,staff['name'],staff.get('vehicleId','') if staff.get('hasVehicle',True) else '',staff.get('rego'),staff.get('vehicleActive',True))

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
