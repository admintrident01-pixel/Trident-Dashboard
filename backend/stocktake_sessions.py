"""Resumable physical counts. Apply all adjustments atomically after explicit review."""
import copy, datetime as dt, hashlib, json, uuid
from zoneinfo import ZoneInfo
from core import Problem
import stock

ONSITE = ('Available','Allocated','Incoming','Refurbishing','Awaiting new asset number','Repair')

def today(): return dt.datetime.now(ZoneInfo('Pacific/Auckland')).date()

def config(state):
    return {'intervalDays':90,'automatic':True,**state.get('stockTakeSettings',{})}

def status(state, date=None):
    date=date or today()
    completed=[s for s in state.get('stockTakes',{}).values() if s['status']=='completed']
    last=max((s['date'] for s in completed),default='')
    due=(dt.date.fromisoformat(last)+dt.timedelta(days=config(state)['intervalDays'])).isoformat() if last else date.isoformat()
    return {**config(state),'lastCompleted':last,'nextDue':due,'daysRemaining':(dt.date.fromisoformat(due)-date).days}

def fingerprint(state):
    data={k:v for k,v in state.get('stock',stock.empty()).items() if k not in ('workbookTemplate','sourceSnapshot')}
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def snapshot(state):
    data=state.get('stock',stock.empty()); rows=[]
    for p in sorted(data['products'].values(),key=lambda p:(p['code'],p.get('condition',''))):
        assets=[{'id':a['id'],'number':a['number'],'status':a['status'],'location':a['location']} for a in data['assets'].values() if a['productId']==p['id'] and a['status'] in ONSITE]
        pending=sum(max(0,r['quantity']-len(r['assetIds'])) for r in data['receipts'].values() if r['productId']==p['id'] and (r['pool']!='Trident refurb stock' or not r.get('refurbComplete')))
        rows.append({'id':p['id'],'code':p['code'],'condition':p.get('condition',''),'description':p['description'],'assets':assets,'expected':len(assets)+pending if stock.quantity_known(data,p) else None})
    return rows

def read(state,actor):
    draft=next((s for s in state.get('stockTakes',{}).values() if s['status']=='draft' and s['createdBy']==actor),None)
    return {'draft':copy.deepcopy(draft),'stockTakeStatus':status(state),'stockChanged':bool(draft and draft['fingerprint']!=fingerprint(state))}

def count(value):
    if type(value) is not int or not 0<=value<=10000:raise Problem(400,'Enter a counted total from 0 to 10,000.')
    return value

def review(session,entries,strict=False):
    if not isinstance(entries,dict):raise Problem(400,'Enter valid count entries.')
    result={}
    if any(key not in {r['id'] for r in session['rows']} for key in entries):raise Problem(400,'Choose a product in this stocktake.')
    for row in session['rows']:
        if row['id'] not in entries:continue
        entry=entries[row['id']]
        if not isinstance(entry,dict):raise Problem(400,'Enter a valid product count.')
        decisions=entry.get('decisions',{})
        if not isinstance(decisions,dict) or not set(decisions)<={a['id'] for a in row['assets']} or any(v not in ('found','missing','retire') for v in decisions.values()):raise Problem(400,'Mark every asset Found, Not found or Retire before saving this product.')
        if strict and set(decisions)!={a['id'] for a in row['assets']}:raise Problem(400,'Check every asset before finishing.')
        numbers=entry.get('numbers',[])
        if not isinstance(numbers,list) or len(numbers)>1000:raise Problem(400,'Enter up to 1,000 additional asset numbers per product.')
        numbers=[stock.text(n,'additional asset number',80,True) for n in numbers]
        total=count(entry.get('count')) if strict or entry.get('count') is not None else None
        if total is not None and total<sum(v=='found' for v in decisions.values())+len(numbers):raise Problem(400,'Counted total must include all found assets and additional asset numbers.')
        result[row['id']]={'count':total,'decisions':decisions,'numbers':numbers,'notes':stock.text(entry.get('notes',''),'stocktake notes',4000)}
    return result

def action(state,p,actor):
    if not isinstance(p,dict):raise Problem(400,'Invalid stocktake request.')
    result=copy.deepcopy(state);sessions=result.setdefault('stockTakes',{});kind=p.get('action')
    if kind=='start':
        if not any(s['status']=='draft' and s['createdBy']==actor for s in sessions.values()):
            key=str(uuid.uuid4());sessions[key]={'id':key,'status':'draft','createdBy':actor,'date':today().isoformat(),'version':1,'fingerprint':fingerprint(state),'rows':snapshot(state),'entries':{}}
        return result
    session=sessions.get(p.get('id'))
    if not session or session['createdBy']!=actor:raise Problem(404,'This stocktake was not found.')
    if session['status']!='draft' or type(p.get('version')) is not int or session['version']!=p['version']:raise Problem(409,'This stocktake changed. Refresh before continuing.')
    if kind=='discard':
        session.update(status='cancelled',version=session['version']+1);return result
    if kind=='refresh':
        # Keep old draft as an audit record; changed stock needs a fresh physical review.
        session.update(status='cancelled',version=session['version']+1)
        return action(result,{'action':'start'},actor)
    if kind=='remove_product':
        row=next((r for r in session['rows'] if r['id']==p.get('productId')),None)
        if not row or not row.get('newProduct'):raise Problem(400,'Only a product added during this count can be removed. Existing stock must still be checked.')
        session['rows'].remove(row);session['entries'].pop(row['id'],None);session['version']+=1
        return result
    if kind=='add_product':
        code=stock.text(p.get('code'),'product code',100,True);description=stock.text(p.get('description'),'description',400,True);condition=p.get('condition','')
        if condition not in ('','NEW','REFURB'):raise Problem(400,'Choose a valid condition.')
        if any(r['code'].casefold()==code.casefold() and r['condition']==condition for r in session['rows']):raise Problem(409,'This product already appears in the count. Search its product code.')
        session['rows'].append({'id':str(uuid.uuid4()),'code':code,'description':description,'condition':condition,'assets':[],'expected':0,'newProduct':True})
        session['version']+=1
        return result
    if kind not in ('save','complete'):raise Problem(400,'Choose a valid stocktake action.')
    entries=review(session,p.get('entries',session['entries']),strict=kind=='complete')
    session.update(entries=entries,version=session['version']+1)
    if kind=='save':return result
    if p.get('confirmed') is not True:raise Problem(400,'Review and confirm the stocktake adjustments first.')
    if session['fingerprint']!=fingerprint(state):raise Problem(409,'Stock changed during this count. Start a fresh count against the updated stock before applying changes. Your draft is still saved.')
    if len(entries)!=len(session['rows']):raise Problem(400,'Verify every product before finishing the stocktake.')
    date=today().isoformat();data=result.setdefault('stock',stock.empty());summary=[]
    for row in session['rows']:
        entry=entries[row['id']];pid=row['id'];retired=[]
        if row.get('newProduct'):
            before=set(data['products'])
            result=stock.action(result,{'action':'product','code':row['code'],'description':row['description'],'condition':row['condition'],'date':date},actor);data=result['stock']
            pid=next(k for k in data['products'] if k not in before)
        for aid,decision in entry['decisions'].items():
            if decision=='found':continue
            a=data['assets'][aid];stock.chronological(data,a,date)
            before=copy.deepcopy(a);group=data.get('allocations',{}).get(a.get('allocationId'))
            if group:group['assetStates'][aid].update(status='Cancelled',condition='Retired during stocktake',cancelledAt=date)
            a.update(status='Retired',location='Retired',revision=a['revision']+1,allocationId='',client='',reference='',jobId='',retiredAt=date)
            stock.event(data,'Stocktake asset retired',actor,date,assetId=aid,productId=pid,number=a['number'],reason='Not found' if decision=='missing' else 'Retired after inspection',previous=before,stockTakeId=session['id'],notes=entry['notes'])
            retired.append(a['number'])
        # Label existing unnumbered stock first; never change its pool or count it twice.
        nums=list(entry['numbers'])
        for rid in list(data['receipts']):
            r=data['receipts'][rid]
            if r['productId']!=pid or r['pool']=='Trident refurb stock' or not nums:continue
            capacity=max(0,r['quantity']-len(r['assetIds']));assigned=nums[:capacity]
            if not assigned:continue
            result=stock.action(result,{'action':'asset','receiptId':rid,'receiptRevision':r['revision'],'numbers':assigned,'date':date,'notes':'Identified during stocktake. '+entry['notes']},actor);data=result['stock'];nums=nums[len(assigned):]
        while nums:
            assigned=nums[:1000];nums=nums[1000:];before=set(data['receipts'])
            result=stock.action(result,{'action':'receive','productId':pid,'pool':'Existing stock','quantity':len(assigned),'date':date,'notes':'Stocktake addition. '+entry['notes']},actor);data=result['stock']
            rid=next(k for k in data['receipts'] if k not in before);data['receipts'][rid]['openingBalance']=True
            result=stock.action(result,{'action':'asset','receiptId':rid,'receiptRevision':1,'numbers':assigned,'date':date,'notes':'Added during stocktake. '+entry['notes']},actor);data=result['stock']
        found=sum(v=='found' for v in entry['decisions'].values())
        target=entry['count']-found-len(entry['numbers'])
        pending_receipts=[r for r in data['receipts'].values() if r['productId']==pid and (r['pool']!='Trident refurb stock' or not r.get('refurbComplete'))]
        pending=sum(max(0,r['quantity']-len(r['assetIds'])) for r in pending_receipts)
        reduce=max(0,pending-target)
        for r in reversed(pending_receipts):
            remove=min(reduce,max(0,r['quantity']-len(r['assetIds'])))
            if remove:
                previous=r['quantity'];r.update(quantity=previous-remove,revision=r['revision']+1);reduce-=remove
                stock.event(data,'Stocktake unnumbered balance adjusted',actor,date,receiptId=r['id'],productId=pid,previousQuantity=previous,quantity=r['quantity'],stockTakeId=session['id'],notes=entry['notes'])
        remaining=max(0,target-pending)
        while remaining:
            qty=min(remaining,1000);before=set(data['receipts'])
            result=stock.action(result,{'action':'receive','productId':pid,'pool':'Existing stock','quantity':qty,'date':date,'notes':'Stocktake unnumbered addition. '+entry['notes']},actor);data=result['stock']
            rid=next(k for k in data['receipts'] if k not in before);data['receipts'][rid]['openingBalance']=True;remaining-=qty
        data['products'][pid]['stocktakeQuantityConfirmed']=True
        summary.append({'productId':pid,'code':row['code'],'expected':row['expected'],'counted':entry['count'],'difference':entry['count']-row['expected'] if row['expected'] is not None else None,'retired':retired,'addedNumbers':entry['numbers'],'notes':entry['notes']})
    session=result['stockTakes'][session['id']]
    session.update(status='completed',date=date,completedAt=dt.datetime.now(dt.timezone.utc).isoformat(),summary=summary)
    stock.event(data,'Stocktake completed',actor,date,stockTakeId=session['id'],summary=summary)
    return result
