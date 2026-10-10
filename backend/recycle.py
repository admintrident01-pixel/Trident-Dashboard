"""Admin recycle bin. Snapshots travel with the same transactional app state."""
import base64, copy, datetime as dt, hashlib, io, json, zipfile
from xml.etree import ElementTree as ET
from core import Problem, decode
import timesheets, vehicles, schedule, leave, labour, quote_settings

LABELS={'quote':'Quotes','appointment':'Appointments','lunch':'Lunch breaks','leave':'Leave requests','staff':'Staff','vehicle':'Vehicles','timesheet':'Time sheets','check':'Vehicle checks','appointmentType':'Appointment types','calculator':'Calculator items','quoteType':'Quote types','defaultItem':'Quote default items'}

def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()
def identifier(kind,key):return kind+':'+str(key)
def put(state,kind,key,value,title,actor='',extra=None):
    row={'id':identifier(kind,key),'type':kind,'typeLabel':LABELS[kind],'key':str(key),'title':title,'deletedAt':stamp(),'deletedBy':actor,'value':copy.deepcopy(value),**(extra or {})}
    state.setdefault('recycleBin',{})[row['id']]=row

def materialise(state):
    result=copy.deepcopy(state)
    for key,row in result.get('quotes',{}).items():
        if row.get('state')=='Deleted' and not row.get('purged') and identifier('quote',key) not in result.get('recycleBin',{}):
            value={**row,'state':'Finalised' if row.get('pdfFilename') in result.get('pdfs',{}) else 'Draft'}
            put(result,'quote',key,value,'Quote '+key,extra={'pdfKey':result.get('pdfs',{}).get(row.get('pdfFilename')),'legacy':True,'deletedAt':row.get('updatedAt') or row.get('submittedAt') or stamp()})
    for key,row in result.get('appointments',{}).items():
        if row.get('cancelled') and identifier('lunch' if row.get('source')=='lunch' else 'appointment',key) not in result.get('recycleBin',{}):
            put(result,'lunch' if row.get('source')=='lunch' else 'appointment',key,{**row,'cancelled':False},row['client']+' · '+row['date'])
    for key,row in result.get('leaveRequests',{}).items():
        if row.get('status')=='Cancelled' and identifier('leave',key) not in result.get('recycleBin',{}):
            put(result,'leave',key,{**row,'status':'Pending'},row['technician']+' · '+row['startDate'],extra={'legacy':True,'deletedAt':row.get('updatedAt') or row.get('submittedAt') or stamp()})
    for key,row in result.get('removedVehicles',{}).items():
        if identifier('vehicle',key) not in result.get('recycleBin',{}):put(result,'vehicle',key,row,row.get('registration') or key)
    return result

def read(state):
    return {'items':sorted([{k:v for k,v in row.items() if k not in ('value','pdfKey')} for row in materialise(state).get('recycleBin',{}).values()],key=lambda r:(r['typeLabel'],r['deletedAt']),reverse=True)}

def capture(before,after,actor):
    # Never change a caller's snapshot, and do not capture overwritten field values.
    result=copy.deepcopy(after)
    mappings=[('quotes','quote','state','Deleted'),('appointments','appointment','cancelled',True),('leaveRequests','leave','status','Cancelled'),('timesheets','timesheet',None,None),('vehicleChecks','check',None,None)]
    for collection,kind,flag,deleted in mappings:
        for key,old in before.get(collection,{}).items():
            new=after.get(collection,{}).get(key)
            was_deleted=flag and old.get(flag)==deleted
            now_deleted=new is None or (flag and new.get(flag)==deleted)
            actual_kind='lunch' if collection=='appointments' and old.get('source')=='lunch' else kind
            bin_id=identifier(actual_kind,key)
            if now_deleted and not was_deleted:
                title=('Quote '+key) if kind=='quote' else (old.get('client') or old.get('technician') or old.get('registration') or key)+' · '+(old.get('date') or old.get('weekStart') or old.get('startDate') or old.get('checkDate') or '')
                extra={'pdfKey':before.get('pdfs',{}).get(old.get('pdfFilename'))} if kind=='quote' else None
                put(result,actual_kind,key,old,title,actor,extra)
            elif was_deleted and new is not None and not now_deleted:result.get('recycleBin',{}).pop(bin_id,None)
    def removed(oldrows,newrows,kind,keyfn,titlefn,extra=None):
        counts={}
        for row in newrows:counts[keyfn(row)]=counts.get(keyfn(row),0)+1
        for index,row in enumerate(oldrows):
            key=keyfn(row)
            if counts.get(key,0):counts[key]-=1;continue
            uid=key if kind in ('staff','vehicle','calculator','appointmentType','quoteType') else hashlib.sha256((str(extra or '')+key+str(index)).encode()).hexdigest()
            put(result,kind,uid,row,titlefn(row),actor,extra)
    if before.get('staffSettings')!=after.get('staffSettings'):removed(timesheets.settings(before)['technicians'],timesheets.settings(after)['technicians'],'staff',lambda r:r['name'],lambda r:r['name'])
    if before.get('vehicles')!=after.get('vehicles'):removed(vehicles.fleet(before),vehicles.fleet(after),'vehicle',lambda r:r['id'],lambda r:r.get('registration') or r['id'])
    if before.get('scheduleSettings')!=after.get('scheduleSettings'):removed(schedule.settings(before)['appointmentTypes'],schedule.settings(after)['appointmentTypes'],'appointmentType',str,str)
    if before.get('labourSettings')!=after.get('labourSettings'):removed(labour.read(before)['items'],labour.read(after)['items'],'calculator',lambda r:r['id'],lambda r:r['name'])
    if before.get('workbook')!=after.get('workbook') and before.get('workbook') and after.get('workbook'):
        old=quote_settings.read(before);new=quote_settings.read(after)
        removed(old['types'],new['types'],'quoteType',lambda r:r['name'],lambda r:r['name'])
        for previous in old['types']:
            current=next((r for r in new['types'] if r['name']==previous['name']),None)
            if current:removed(previous['items'],current['items'],'defaultItem',lambda r:r['description'],lambda r:r['description'],{'quoteType':previous['name']})
    return result

def register(state,number,record,purge=False):
    # Patch only this quote's register cells; keep all reserved numbers and other rows.
    entries,paths,sheet=quote_settings.unpack(state);ns=quote_settings.NS
    doc=ET.fromstring(entries[paths['Quote Register']]);body=doc.find('{'+ns+'}sheetData')
    rows=sheet('Quote Register')
    def number_for(values):
        try:return int(values.get('A',''))
        except ValueError:
            import re
            match=re.search(r' - (\d+) - \d{2}-\d{2}-\d{4}\.pdf$',values.get('AC',''))
            return int(match.group(1)) if match else None
    target=next((row for row,values in zip(list(body),rows) if number_for(values)==int(number)),None)
    if target is None:raise Problem(409,'Quote register row is missing. Restore the workbook before this quote.')
    n=target.get('r')
    if purge:
        for cell in list(target):
            col=''.join(c for c in cell.get('r','') if c.isalpha())
            if col not in ('A','AE','AF','AG'):target.remove(cell)
    for col,value in {'A':str(number),'AE':record['state'],'AF':record['id'],'AG':record['revision']}.items():
        cell=next((c for c in target if c.get('r')==col+n),None)
        if cell is None:cell=ET.SubElement(target,'{'+ns+'}c',r=col+n)
        for child in list(cell):cell.remove(child)
        cell.set('t','inlineStr');ET.SubElement(ET.SubElement(cell,'{'+ns+'}is'),'{'+ns+'}t').text=str(value)
    entries[paths['Quote Register']]=ET.tostring(doc,encoding='utf-8',xml_declaration=True)
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for key,value in entries.items():archive.writestr(key,value)
    state['workbook']=base64.b64encode(output.getvalue()).decode()

def restore(state,row,actor):
    kind=row['type'];key=row['key'];value=copy.deepcopy(row['value'])
    if kind in ('appointment','lunch'):
        old=state.get('appointments',{}).get(key)
        if not old:
            old={**value,'cancelled':True}
            state.setdefault('appointments',{})[key]=old
        state,record=schedule.save(state,{**old,'action':'restore'},actor)
    elif kind=='leave':
        old=state.get('leaveRequests',{}).get(key)
        if not old or old.get('status')!='Cancelled':raise Problem(409,'This leave request has changed.')
        if any(r['id']!=key and r['technician']==value['technician'] and r['status'] in ('Pending','Approved') and set(r['dates'])&set(value['dates']) for r in state.get('leaveRequests',{}).values()):raise Problem(409,'Another leave request now covers these dates.')
        if value['status']=='Approved':
            block_state=copy.deepcopy(state);block_state['leaveRequests'][key]=value
            for appointment in state.get('appointments',{}).values():
                if not appointment.get('cancelled') and appointment.get('source')!='lunch' and any(schedule.overlaps(appointment,b) for b in schedule.leave_blocks(block_state,appointment['date']) if b['id'].startswith('leave:'+key+':')):raise Problem(409,'An appointment overlaps this leave. Move it before restoring leave.')
        value.update(revision=old['revision']+1,updatedAt=stamp(),decidedBy=actor['email'])
        state['leaveRequests'][key]=value
    elif kind=='quote':
        old=state.get('quotes',{}).get(key)
        if not old or old.get('state')!='Deleted' or old.get('purged'):raise Problem(409,'This quote cannot be restored.')
        value.update(revision=old['revision']+1,updatedAt=stamp())
        name=value.get('pdfFilename')
        if row.get('pdfKey') and name:
            if name in state.get('pdfs',{}) and state['pdfs'][name]!=row['pdfKey']:raise Problem(409,'Another quote uses this PDF filename.')
            state.setdefault('pdfs',{})[name]=row['pdfKey']
        elif value['state']=='Finalised':value['state']='Draft'
        state['quotes'][key]=value;register(state,key,value)
    elif kind=='staff':
        rows=timesheets.settings(state)['technicians']
        if any(r['name'].casefold()==value['name'].casefold() for r in rows):raise Problem(409,'A staff member with this name already exists.')
        state=timesheets.save_settings(state,{'technicians':rows+[value]})
    elif kind=='vehicle':
        rows=vehicles.fleet(state)
        if any(r['id']==key or (value.get('registration') and r['registration']==value['registration']) for r in rows):raise Problem(409,'This vehicle ID or registration is already in use.')
        state.get('removedVehicles',{}).pop(key,None);state['vehicles']=rows+[value]
    elif kind in ('timesheet','check'):
        collection='timesheets' if kind=='timesheet' else 'vehicleChecks'
        if key in state.get(collection,{}):raise Problem(409,'This record already exists.')
        state.setdefault(collection,{})[key]=value
    elif kind=='appointmentType':
        settings=schedule.settings(state)
        if any(r.casefold()==value.casefold() for r in settings['appointmentTypes']):raise Problem(409,'This appointment type already exists.')
        settings['appointmentTypes'].append(value);state=schedule.save_settings(state,settings)
    elif kind=='calculator':
        settings=labour.read(state)
        if any(r['id']==key for r in settings['items']):raise Problem(409,'This calculator item already exists.')
        settings['items'].append(value);state=labour.save(state,settings)
    elif kind in ('quoteType','defaultItem'):
        settings=quote_settings.read(state)
        if kind=='quoteType':
            if any(r['name'].casefold()==value['name'].casefold() for r in settings['types']):raise Problem(409,'This quote type already exists.')
            settings['types'].append(value)
        else:
            target=next((r for r in settings['types'] if r['name']==row['quoteType']),None)
            if target is None:raise Problem(409,'Restore the quote type before its default item.')
            target['items'].append(value)
        state=quote_settings.save(state,settings)
    state.get('recycleBin',{}).pop(row['id'],None)
    return state

def action(state,data,actor):
    ids=data.get('ids');mode=data.get('action')
    if mode not in ('restore','purge') or not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise Problem(400,'Select items and choose an action.')
    if mode=='purge' and data.get('confirmed') is not True:raise Problem(400,'Confirm permanent deletion first.')
    result=materialise(state);rows=result.get('recycleBin',{})
    if any(key not in rows for key in ids):raise Problem(409,'The recycle bin changed. Refresh and select the items again.')
    selected=[rows[key] for key in ids];garbage=[]
    priority={'staff':0,'vehicle':0,'quoteType':0,'defaultItem':1}
    for row in sorted(selected,key=lambda r:priority.get(r['type'],2)):
        key=row['key'];kind=row['type']
        if mode=='restore':result=restore(result,row,actor);continue
        if kind=='quote':
            old=result.get('quotes',{}).get(key)
            if old:
                tombstone={'id':old['id'],'revision':old['revision']+1,'state':'Deleted','purged':True,'data':{'fields':{'number':key},'lines':[]},'pdfFilename':''}
                result['quotes'][key]=tombstone;register(result,key,tombstone,purge=True)
            if row.get('pdfKey'):garbage.append(row['pdfKey'])
            name=row['value'].get('pdfFilename')
            if result.get('pdfs',{}).get(name)==row.get('pdfKey'):result['pdfs'].pop(name,None)
        elif kind in ('appointment','lunch'):
            result.get('appointments',{}).pop(key,None)
            if kind=='lunch':result.setdefault('deletedLunchIds',[]).append(key)
        elif kind=='leave':result.get('leaveRequests',{}).pop(key,None)
        elif kind=='vehicle':result.get('removedVehicles',{}).pop(key,None)
        result['recycleBin'].pop(row['id'],None)
    referenced=set(result.get('pdfs',{}).values())|{r.get('pdfKey') for r in result.get('recycleBin',{}).values()}
    return result,[key for key in garbage if key not in referenced]
