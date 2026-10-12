import copy, datetime, uuid
from core import Problem
from timesheets import text

CHECKLIST = ['Oil level', 'Coolant level', 'Tyre pressure', 'Spare tyre pressure', 'Condition of tyres', 'Visual inspection / walk around', 'Interior clean', 'Windscreen wipers', 'Wiper blades work', 'Windscreen condition', 'Headlights', 'Tail lights', 'Brake lights', 'Indicators', 'Battery condition', 'Water level', 'Condition of drive belts', 'Condition of alternator belt', 'General overlook of motor', 'Safety belts', 'Masks and sanitiser available', 'First aid kit']

def _fleet(state):
    if 'vehicles' in state:
        return state['vehicles']
    regs = ['QEK183','CMT409','LMY240','KWG268','RYZ672','RWB869','','','','']
    drivers = ['Joby Shearing','Allan Burney','Daryll Anderson','Rick Leef','Scott Yearbury','Andrew Thomas','Bala Ganesh Venkatesan','Spare 1','Spare 2','Spare 3']
    rows = [{'id':f'VEH-{i+1:02}', 'registration':regs[i], 'makeModel':'Toyota' if i<7 else '', 'driver':drivers[i], 'active':i<6, 'baseline':{}} for i in range(10)]
    # Initial dashboard readings transcribed from the user's fleet screenshot.
    rows[0]['baseline'] = {'checkDate':'2026-10-08','wofExpiry':'2027-09-25','wofDueKm':0,'regoExpiry':'2027-09-26','rucCurrent':101020,'odometer':90009,'serviceDueKm':100000,'alignmentDueKm':0,'comments':'Topped up coolant level, 1x chip on windscreen, both rear tyres worn, rusty paint chips above windscreen.'}
    rows[3]['baseline'] = {'checkDate':'2026-10-09','wofExpiry':'2027-09-22','wofDueKm':300415,'regoExpiry':'2027-03-11','rucCurrent':311205,'odometer':300415,'serviceDueKm':311000,'alignmentDueKm':300000,'comments':'No issues'}
    return rows

def fleet(state):
    rows=_fleet(state)
    order=state.get('vehicleColumnOrder',[])
    if not isinstance(order,list):order=[]
    positions={key:index for index,key in enumerate(order) if isinstance(key,str)}
    return sorted(rows,key=lambda row:positions.get(row['id'],len(positions)+rows.index(row)))

def save_order(state,data):
    order=data.get('order') if isinstance(data,dict) else None
    ids={row['id'] for row in fleet(state)}
    if not isinstance(order,list) or any(not isinstance(key,str) for key in order) or len(order)!=len(ids) or set(order)!=ids:
        raise Problem(400,'Include every current vehicle once. Reload vehicle settings and try again.')
    result=copy.deepcopy(state);result['vehicleColumnOrder']=list(order)
    return result


def save_fleet(state, data):
    rows = data.get('vehicles') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not 0 <= len(rows) <= 200:
        raise Problem(400, 'Enter a valid vehicle list.')
    old = {v['id']:v for v in fleet(state)}
    cleaned, seen, regs = [], set(), set()
    for row in rows:
        if not isinstance(row, dict):raise Problem(400, 'Invalid vehicle.')
        key = text(row.get('id'), 'vehicle ID', 40, True)
        if key in state.get('removedVehicles', {}):raise Problem(400, 'That vehicle ID belongs to a removed vehicle. Use a new ID.')
        reg = text(row.get('registration',''), 'registration', 30).upper()
        if key in seen or (reg and reg in regs):raise Problem(400, 'Vehicle IDs and registrations must be unique.')
        if not isinstance(row.get('active'), bool):raise Problem(400, 'Choose an active status.')
        seen.add(key)
        if reg:regs.add(reg)
        cleaned.append({'id':key,'registration':reg,'makeModel':text(row.get('makeModel',''),'make/model',160),'driver':text(row.get('driver',''),'driver',160),'active':row['active'],'baseline':old.get(key,{}).get('baseline',{})})
    result=copy.deepcopy(state);result['vehicles']=cleaned
    result.setdefault('removedVehicles', {}).update({key:row for key,row in old.items() if key not in seen})
    return result

def date(value, label, required=False):
    value=text(value,label,10,required)
    if not value:return ''
    try:datetime.date.fromisoformat(value)
    except ValueError:raise Problem(400,f'Enter a valid {label}.')
    return value

def km(value,label,required=False):
    if value in ('',None):
        if required:raise Problem(400,f'Enter {label}.')
        return None
    if isinstance(value,bool):raise Problem(400,f'Enter a valid {label}.')
    try:n=int(str(value))
    except (ValueError,TypeError):raise Problem(400,f'Enter a valid {label}.')
    if not 0 <= n <= 10000000:raise Problem(400,f'Enter a valid {label}.')
    return n

def save_check(state,data):
    if not isinstance(data,dict):raise Problem(400,'Invalid vehicle check.')
    vehicle_id=text(data.get('vehicleId'),'vehicle',40,True)
    key=data.get('id') or str(uuid.uuid4())
    if not isinstance(key,str):raise Problem(400,'Invalid check ID.')
    try:uuid.UUID(key)
    except ValueError:raise Problem(400,'Invalid check ID.')
    old=state.get('vehicleChecks',{}).get(key)
    if vehicle_id not in {v['id'] for v in fleet(state)} and not (old and old['vehicleId']==vehicle_id and vehicle_id in state.get('removedVehicles',{})):
        raise Problem(400,'Choose an existing vehicle. Removed vehicles cannot receive new checks.')
    if (old and data.get('revision')!=old['revision']) or (not old and data.get('revision',0)!=0):raise Problem(409,'This check has changed. Reopen it from history.')
    if old and old['vehicleId']!=vehicle_id:raise Problem(400,'An existing check must stay with its original vehicle.')
    overall=data.get('overall')
    if overall not in ('All OK','Issues found'):raise Problem(400,'Choose an overall check result.')
    answers=data.get('checklist')
    if not isinstance(answers,list) or len(answers)!=len(CHECKLIST):raise Problem(400,'Complete the vehicle checklist.')
    if overall=='All OK':
        if any(a not in ('','Pass') for a in answers):raise Problem(400,'Choose Issues found for failed or not-applicable checks.')
        answers=['Pass']*len(CHECKLIST)
    elif any(a not in ('Pass','Fail','N/A') for a in answers):raise Problem(400,'Complete all checklist rows with Pass, Fail or N/A.')
    entry={'id':key,'revision':old['revision']+1 if old else 1,'vehicleId':vehicle_id,'driver':text(data.get('driver'),'driver / inspector name',160,True),'registration':text(data.get('registration'),'vehicle registration',30,True).upper(),'makeModel':text(data.get('makeModel',''),'make/model',160),'vehicleYear':text(data.get('vehicleYear',''),'vehicle year',4),'checkDate':date(data.get('checkDate'),'check date',True),'overall':overall,'checklist':answers,'comments':text(data.get('comments'),'damage / comments',4000,True),'signature':text(data.get('signature'),'signed inspector name',160,True)}
    expiry=data.get('nextCheckDue') or (datetime.date.fromisoformat(entry['checkDate'])+datetime.timedelta(days=30)).isoformat()
    entry['nextCheckDue']=date(expiry,'next vehicle check due',True)
    if entry['nextCheckDue']<=entry['checkDate']:raise Problem(400,'The next vehicle check must be due after this check date.')
    if entry['vehicleYear'] and (not entry['vehicleYear'].isdigit() or not 1900<=int(entry['vehicleYear'])<=2100):raise Problem(400,'Enter a valid vehicle year.')
    for field,label,required in [('serviceDue','service due date',True),('wofExpiry','WOF due date',False),('alignmentDue','wheel alignment due date',True),('regoExpiry','registration due date',True)]:entry[field]=date(data.get(field,''),label,required)
    for field,label,required in [('serviceDueKm','service due KM',True),('wofDueKm','WOF due KM',False),('alignmentDueKm','wheel alignment due KM',True),('odometer','odometer reading',True),('rucCurrent','road user charge KM',True),('rucDue','RUC due KM',False)]:entry[field]=km(data.get(field),label,required)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry['createdAt']=old['createdAt'] if old else now;entry['updatedAt']=now
    result=copy.deepcopy(state);result.setdefault('vehicleChecks',{})[key]=entry
    return result,entry
