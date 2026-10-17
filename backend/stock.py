"""Asset-based stock. Confirmed opening quantities are linked to receipts to prevent double counting."""
import copy, datetime as dt, uuid
from zoneinfo import ZoneInfo
from core import Problem

STATES=('Incoming','Available','Allocated','With client','Refurbishing','Awaiting new asset number','Repair','Retired')
POOLS=('New stock','Existing stock','Trident refurb stock')
def text(value,label,limit=200,required=False):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()):raise Problem(400,f'Enter a valid {label}.')
    return value.strip()
def quantity(value):
    if type(value) is not int or not 1<=value<=1000:raise Problem(400,'Enter a whole quantity from 1 to 1,000.')
    return value
def day(value):
    try:return dt.date.fromisoformat(value).isoformat()
    except (TypeError,ValueError):raise Problem(400,'Choose a valid date.')
def worker(state,value,required=False):
    from timesheets import settings
    name=text(value,'refurbishment technician',160,required)
    if name and name not in [r['name'] for r in settings(state)['technicians'] if r.get('staffType','technician')=='technician']:raise Problem(400,'Choose a current technician for refurbishment.')
    return name
def empty():return {'allocations':{},'products':{},'receipts':{},'assets':{},'movements':[],'imports':[]}
def reference_type(value):
    if value not in ('PO','SO'):raise Problem(400,'Choose SO or PO for the reference.')
    return value

def label_added(label):
    return label.get('addedAt') or ((label['addedAtText']+' (year not recorded)') if label.get('addedAtText') else 'Not recorded')

def label_reference(label):
    if not label.get('reference'):return 'Not recorded'
    value=(label.get('referenceType') or 'Reference')+' '+label['reference']
    return value+(' — '+label['referenceContext'] if label.get('referenceContext') else '')

def quantity_known(data,product):
    if product.get('stocktakeQuantityConfirmed'):return True
    if product.get('quantityBasis')=='listed_assets':return bool(product.get('sourceQuantity')) or any(a['productId']==product['id'] for a in data['assets'].values())
    return bool(product.get('openingQuantityConfirmed') or not product.get('sourceRow') or any(a['productId']==product['id'] for a in data['assets'].values()))

def ready_refurb(asset):
    return asset['pool']=='Trident refurb stock' and (bool(asset.get('refurbCompletedAt')) or asset.get('sourceCondition')=='REFURB' and asset.get('sourceStockReady')) and asset['status'] in ('Available','Allocated','Awaiting new asset number')

def number_history(data,asset):
    """Reconstruct only known effective dates; never fabricate dates for old labels."""
    if asset.get('numberHistory'):return copy.deepcopy(asset['numberHistory'])
    labels=[*asset.get('previousNumbers',[]),asset['number']]
    history=[{'number':n,'validFrom':None,'validTo':None} for n in labels]
    for movement in data['movements']:
        if movement.get('assetId')!=asset['id']:continue
        if movement['kind'] not in ('Asset registered','Asset number changed'):continue
        index=next((i for i,h in enumerate(history) if h['number']==movement.get('number')),None)
        if index is not None:
            history[index]['validFrom']=movement['date']
            if index:history[index-1]['validTo']=movement['date']
    return history

def label_details(p,default_added=None,default_reference=None):
    added=p.get('assetAddedAt') or default_added
    ref=text(p.get('labelReference',default_reference or ''),'asset history reference',200)
    kind=p.get('labelReferenceType','Reference')
    if kind not in ('PO','SO','Reference'):raise Problem(400,'Choose PO, SO or Reference for the asset history.')
    return {'addedAt':day(added) if added else None,'referenceType':kind,'reference':ref}

def past_number_rows(data,rows,numbers,current_starts,existing=None):
    if not isinstance(rows,list) or len(rows)>1000:raise Problem(400,'Enter a valid list of past asset numbers.')
    grouped={n:[] for n in numbers};canonical={n.casefold():n for n in numbers}
    used={n.casefold() for a in data['assets'].values() for n in [a['number'],*a.get('previousNumbers',[])]}|set(canonical)
    for row in rows:
        if not isinstance(row,dict):raise Problem(400,'Enter a valid past asset number row.')
        target=text(row.get('currentNumber'),'current asset number',80,True)
        if target.casefold() not in canonical:raise Problem(400,'Link each past number to one of the current asset numbers.')
        target=canonical[target.casefold()];number=text(row.get('number'),'past asset number',80,True)
        if number.casefold() in used:raise Problem(409,'Each current and past asset number must be unique, including earlier labels.')
        start=day(row.get('validFrom'));end=day(row.get('validTo'))
        if start>=end:raise Problem(400,'A past number must end after it starts. The end date is the first day it is no longer valid.')
        current_start=current_starts[target]
        if not current_start and end>dt.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat():raise Problem(400,'A past-number period cannot extend into the future.')
        if current_start and end>current_start:raise Problem(400,'A past number must end on or before the current number starts.')
        added=row.get('addedAt');kind=row.get('referenceType','Reference')
        if kind not in ('PO','SO','Reference'):raise Problem(400,'Choose PO, SO or Reference for the past number.')
        record={'number':number,'validFrom':start,'validTo':end,'addedAt':day(added) if added else None,'referenceType':kind,'reference':text(row.get('reference',''),'past asset reference',200)}
        grouped[target].append(record);used.add(number.casefold())
    for target,records in grouped.items():
        intervals=[r for r in [*(existing or {}).get(target,[]),*records] if r.get('validFrom') and r.get('validTo')]
        intervals.sort(key=lambda r:r['validFrom'])
        if any(a['validTo']>b['validFrom'] for a,b in zip(intervals,intervals[1:])):raise Problem(400,'Past asset-number dates cannot overlap for the same item.')
        records.sort(key=lambda r:r['validFrom'])
    return grouped

def chronological(data,asset,date):
    dates=[m['date'] for m in data['movements'] if m.get('assetId')==asset['id'] and m['kind']!='Past asset numbers added']
    current=number_history(data,asset)[-1].get('validFrom')
    if current:dates.append(current)
    if dates and date<max(dates):raise Problem(400,'The movement date cannot be before this asset’s latest recorded movement or current label start date.')

def opening_pending(data,product_id=None):
    return sum(max(0,r['quantity']-len(r['assetIds'])) for r in data['receipts'].values() if r.get('openingBalance') and (product_id is None or r['productId']==product_id))

def balances(data,product_id):
    assets=[a for a in data['assets'].values() if a['productId']==product_id]
    pending=opening_pending(data,product_id)
    available=pending+sum(a['status']=='Available' for a in assets)
    allocated=sum(a['status']=='Allocated' for a in assets)
    incoming=sum(a['status']=='Incoming' for a in assets)+sum(max(0,r['quantity']-len(r['assetIds'])) for r in data['receipts'].values() if r['productId']==product_id and r['pool']!='Trident refurb stock' and not r.get('openingBalance'))
    refurbing=sum(a['status']=='Refurbishing' for a in assets)+sum(max(0,r['quantity']-len(r['assetIds'])) for r in data['receipts'].values() if r['productId']==product_id and r['pool']=='Trident refurb stock' and not r.get('refurbComplete'))
    refurbed=sum(ready_refurb(a) for a in assets)
    return {'incomingQuantity':incoming,'refurbingQuantity':refurbing,'refurbedQuantity':refurbed,'availableQuantity':available,'onHandQuantity':available+allocated,'awaitingOpeningNumbers':pending,'allocatedQuantity':allocated,'deliveredQuantity':sum(a['status']=='With client' for a in assets)}

def read(state):
    data=copy.deepcopy(state.get('stock',empty()))
    data.setdefault('allocations',{})
    data.pop('workbookTemplate',None);data.pop('sourceSnapshot',None)
    for asset in data['assets'].values():
        asset['numberHistory']=number_history(data,asset)
        current_group=data['allocations'].get(asset.get('allocationId'))
        if current_group:
            asset.setdefault('allocatedAt',current_group['assetStates'][asset['id']].get('allocatedAt'))
            asset.setdefault('referenceType',current_group.get('referenceType','PO'))
        asset['clientHistory']=[{'allocationId':g['id'],'client':g['client'],'jobId':g['jobId'],'reference':g['reference'],'referenceType':g.get('referenceType','PO'),**g['assetStates'][asset['id']]} for g in data['allocations'].values() if asset['id'] in g['assetStates']]
    from timesheets import settings
    data['technicians']=[r['name'] for r in settings(state)['technicians'] if r.get('staffType','technician')=='technician']
    data['summary']={status:sum(a['status']==status for a in data['assets'].values()) for status in STATES}
    data['summary']['Available stock']=data['summary']['Available']+opening_pending(data)
    for row in data['products'].values():row.update(balances(data,row['id']))
    data['summary']['Awaiting asset numbers']=sum(r['quantity']-len(r['assetIds']) for r in data['receipts'].values())
    import stocktake_sessions
    data['stockTakeStatus']=stocktake_sessions.status(state)
    return data
def event(data,kind,actor,date,**values):
    data['movements'].append({'id':str(uuid.uuid4()),'kind':kind,'actor':actor,'date':date,'recordedAt':dt.datetime.now(dt.timezone.utc).isoformat(),**values})
def product(data,key):
    if not isinstance(key,str) or key not in data['products']:raise Problem(404,'This product no longer exists.')
    return data['products'][key]
def custom_move(state,p,actor):
    """Move existing identities atomically; use normal allocation/return history paths."""
    date=day(p.get('date'));reason=text(p.get('notes',''),'move reason / work notes',4000,True)
    destination=p.get('destination')
    if p.get('completeRefurb') is True and destination!='assets':raise Problem(400,'Completed refurbishment must move to stock on hand.')
    targets={'intake':'Incoming','refurbing':'Refurbishing','refurbed':'Awaiting new asset number','assets':'Available','allocations':'Allocated','delivered':'With client'}
    if destination not in targets:raise Problem(400,'Choose a stock destination.')
    ids=p.get('assetIds');versions=p.get('revisions',{})
    if not isinstance(ids,list) or not ids or len(ids)>1000 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):raise Problem(400,'Choose one or more numbered assets.')
    original=state.get('stock',empty())
    for key in ids:
        a=original['assets'].get(key)
        if not a:raise Problem(404,'An asset no longer exists.')
        if not isinstance(versions,dict) or type(versions.get(key)) is not int or versions[key]!=a['revision']:raise Problem(409,'An asset changed. Refresh and reopen the move.')
        if a['status']=='Retired':raise Problem(400,'Retired stock cannot be moved through this workflow.')
        if a['status']==targets[destination]:raise Problem(400,f"{a['number']} is already in the selected destination.")
        chronological(original,a,date)
    result=copy.deepcopy(state);audit=[]
    def normal(kind,keys,**values):
        nonlocal result
        result=action(result,{'action':kind,'date':date,'notes':reason,'assetIds':keys,'revisions':{key:result['stock']['assets'][key]['revision'] for key in keys},**values},actor)
    for key in ids:
        data=result['stock'];a=data['assets'][key];old=a['status']
        if p.get('completeRefurb') is True:
            if old not in ('Refurbishing','Awaiting new asset number'):raise Problem(400,'Choose an item awaiting refurbishment completion.')
            a.update(requiresRelabel=True,refurbRelabelled=False)
        context={'client':a.get('client',''),'reference':a.get('reference',''),'referenceType':a.get('referenceType','PO'),'jobId':a.get('jobId','')}
        # Existing delivery allocations can be delivered without creating a second allocation.
        keep_allocation=destination=='delivered' and old=='Allocated'
        if old in ('Allocated','With client') and not keep_allocation:
            normal('return',[key],condition='Ready for stock');data=result['stock'];a=data['assets'][key]
        if destination=='refurbing':
            tech=worker(result,p.get('technician',''),True)
            a.update(status='Refurbishing',pool='Trident refurb stock',location='Refurb workshop',refurbTechnician=tech,refurbCompletedAt='',refurbWorkComplete=False,requiresRelabel=True,refurbRelabelled=False)
        elif destination=='refurbed':
            tech=worker(result,p.get('technician') or a.get('refurbTechnician',''),True)
            a.update(status='Awaiting new asset number',pool='Trident refurb stock',location='Refurb workshop',refurbTechnician=tech,refurbCompletedAt=date,refurbWorkComplete=True,requiresRelabel=True,refurbRelabelled=False)
        elif not keep_allocation:
            if destination!='intake' and (a['status'] in ('Refurbishing','Awaiting new asset number','Repair') or a.get('requiresRelabel') and not a.get('refurbRelabelled')):
                if a.get('requiresRelabel') and not a.get('refurbWorkComplete') and a['status'] not in ('Refurbishing','Repair'):a['status']='Refurbishing'
                if a['status'] in ('Refurbishing','Repair'):normal('ready',[key],technician=worker(result,p.get('technician',''),True));data=result['stock'];a=data['assets'][key]
                if a.get('requiresRelabel') and not a.get('refurbRelabelled'):
                    numbers=p.get('newNumbers',{})
                    if not isinstance(numbers,dict) or not numbers.get(key):raise Problem(400,f"Enter a new asset number for {a['number']} before moving it into ready stock.")
                    normal('relabel',[key],number=numbers[key],**{k:p[k] for k in ('assetAddedAt','labelReferenceType','labelReference') if k in p});data=result['stock'];a=data['assets'][key]
            if destination=='intake':a.update(status='Incoming',location='Receiving area')
            else:a.update(status='Available',location='Store')
        a['revision']+=1
        audit.append((key,old,context))
    if destination in ('allocations','delivered'):
        available=[key for key in ids if result['stock']['assets'][key]['status']=='Available']
        if available:normal('allocate',available,client=p.get('client',''),reference=p.get('reference',''),referenceType=p.get('referenceType','PO'),jobId=p.get('jobId',''))
        if destination=='delivered':normal('dispatch',ids)
    for key,old,context in audit:
        a=result['stock']['assets'][key]
        if destination in ('allocations','delivered'):context={k:a.get(k,'') for k in ('client','reference','referenceType','jobId')}
        event(result['stock'],'Custom stock move',actor,date,assetId=key,number=a['number'],productId=a['productId'],fromStatus=old,toStatus=a['status'],destination=destination,pool=a['pool'],technician=a.get('refurbTechnician',''),notes=reason,**context)
    return result

def receive_numbered_stock(state,p,actor):
    """Receive and register a complete numbered delivery as one atomic transaction."""
    if p.get('pool') not in ('New stock','Existing stock'):raise Problem(400,'Use the collection workflow for refurbishment pickups.')
    qty=quantity(p.get('quantity'));numbers=p.get('numbers')
    if not isinstance(numbers,list) or len(numbers)!=qty:raise Problem(400,'Enter one asset number per received item. The number of lines must match the quantity received.')
    numbers=[text(number,'asset number',80,True) for number in numbers]
    result=action(state,{**p,'action':'receive'},actor)
    receipt_id=next(key for key in result['stock']['receipts'] if key not in state.get('stock',empty())['receipts'])
    return action(result,{'action':'asset','receiptId':receipt_id,'receiptRevision':1,'numbers':numbers,'date':p.get('date',dt.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat()),'notes':p.get('notes','')},actor)

def action(state,p,actor):
    if not isinstance(p,dict):raise Problem(400,'Invalid stock request.')
    if p.get('action')=='custom_move':return custom_move(state,p,actor)
    if p.get('action')=='receive_stock':return receive_numbered_stock(state,p,actor)
    result=copy.deepcopy(state);data=result.setdefault('stock',empty());data.setdefault('allocations',{});kind=p.get('action');date=day(p.get('date',dt.datetime.now(ZoneInfo('Pacific/Auckland')).date().isoformat()))
    notes=text(p.get('notes',''),'notes',4000)
    if kind=='stock_settings':
        minimums=p.get('minimums')
        if not isinstance(minimums,dict) or (not minimums and 'stocktakeIntervalDays' not in p):raise Problem(400,'Choose product minimum stock levels to save.')
        for key,value in minimums.items():
            product(data,key)
            if value is not None and (type(value) is not int or not 0<=value<=10000):raise Problem(400,'Minimum stock must be a whole number from 0 to 10,000, or left blank.')
        if 'stocktakeIntervalDays' in p:
            interval=p['stocktakeIntervalDays']
            if type(interval) is not int or not 1<=interval<=730:raise Problem(400,'Choose a stocktake interval from 1 to 730 days.')
            if type(p.get('automaticStocktakes')) is not bool:raise Problem(400,'Choose whether to send automatic stocktake reminders.')
            result['stockTakeSettings']={'intervalDays':interval,'automatic':p['automaticStocktakes']}
            event(data,'Stocktake settings updated',actor,date,**result['stockTakeSettings'])
        changes=[]
        for key,value in minimums.items():
            row=data['products'][key];previous=row.get('minimumStock')
            if previous!=value:
                if value is None:row.pop('minimumStock',None)
                else:row['minimumStock']=value
                changes.append({'productId':key,'previous':previous,'minimum':value})
        if changes:event(data,'Minimum stock levels updated',actor,date,changes=changes,notes=notes)
    elif kind=='product':
        code=text(p.get('code'),'product code',100,True);description=text(p.get('description'),'description',400,True)
        condition=p.get('condition','')
        if condition not in ('','NEW','REFURB'):raise Problem(400,'Choose NEW, REFURB or an unspecified condition.')
        if any(row['code'].casefold()==code.casefold() and row.get('condition','')==condition for row in data['products'].values()):raise Problem(409,'That product code already exists. Use the existing product.')
        key=str(uuid.uuid4());data['products'][key]={'id':key,'code':code,'condition':condition,'description':description,'sourceRow':None,'sourceQuantity':None,'quantityReviewed':False,'sourceNotes':{},'reviewIssues':[]}
        event(data,'Product added',actor,date,productId=key,notes=notes)
    elif kind=='receive':
        prod=product(data,p.get('productId'));pool=p.get('pool')
        if pool not in POOLS:raise Problem(400,'Choose a stock type.')
        qty=quantity(p.get('quantity'));reference=text(p.get('reference',''),'PO / pickup reference',160,pool=='Trident refurb stock')
        job=text(p.get('jobId',''),'collection Trident job ID',100,pool=='Trident refurb stock')
        ref_type=reference_type(p.get('referenceType','PO'))
        old_start=day(p['oldNumberValidFrom']) if p.get('oldNumberValidFrom') else None
        if old_start and old_start>date:raise Problem(400,'The existing asset number cannot start after the collection date.')
        client=text(p.get('client',''),'pickup client / source',200,pool=='Trident refurb stock')
        key=str(uuid.uuid4());data['receipts'][key]={'id':key,'productId':prod['id'],'quantity':qty,'pool':pool,'client':client,'reference':reference,'referenceType':ref_type,'jobId':job,'date':date,'notes':notes,'assetIds':[],'refurbComplete':False,'technician':worker(state,p.get('technician','')) if pool=='Trident refurb stock' else '', 'refurbCompletedAt':'','revision':1}
        event(data,'Refurb pickup' if pool=='Trident refurb stock' else 'Stock received',actor,date,receiptId=key,productId=prod['id'],quantity=qty,pool=pool,client=client,reference=reference,referenceType=ref_type,jobId=job,notes=notes)
        if pool=='Trident refurb stock':
            numbers=p.get('oldNumbers')
            if not isinstance(numbers,list) or len(numbers)!=qty:raise Problem(400,'Enter one existing asset number for each collected item.')
            numbers=[text(n,'existing asset number',80,True) for n in numbers]
            if len({n.casefold() for n in numbers})!=qty:raise Problem(400,'Collected asset numbers must be distinct.')
            for number in numbers:
                asset=next((a for a in data['assets'].values() if a['number'].casefold()==number.casefold()),None)
                if asset:
                    if asset['productId']!=prod['id'] or asset['status']!='With client' or asset['client'].casefold()!=client.casefold():raise Problem(409,'An existing asset can be collected only from its client and with the same product.')
                    chronological(data,asset,date)
                    group=data['allocations'].get(asset.get('allocationId'))
                    if group:group['assetStates'][asset['id']].update(status='Returned',returnedAt=date,condition='Refurb pickup')
                    asset.setdefault('receiptHistory',[]).append(asset['receiptId'])
                    asset.update(revision=asset['revision']+1,client='',reference='',jobId='',allocationId='',allocatedAt='',dispatchedAt='')
                else:
                    if any(number.casefold() in [n.casefold() for n in a.get('previousNumbers',[])] for a in data['assets'].values()):raise Problem(409,'This is an earlier label. Use the asset’s current number.')
                    asset={'id':str(uuid.uuid4()),'number':number,'previousNumbers':[],'productId':prod['id'],'client':'','reference':'','jobId':'','allocationId':'','lastAllocationId':'','revision':1,'numberHistory':[{'number':number,'validFrom':old_start,'validTo':None,**label_details({'assetAddedAt':p.get('oldAssetAddedAt'),'labelReferenceType':p.get('oldLabelReferenceType','Reference'),'labelReference':p.get('oldLabelReference','')})}]}
                    data['assets'][asset['id']]=asset
                asset.update(receiptId=key,pool=pool,status='Refurbishing',location='Refurb workshop',requiresRelabel=True,refurbRelabelled=False,refurbWorkComplete=False,refurbTechnician=data['receipts'][key]['technician'],refurbCompletedAt='',pickupClient=client,pickupReference=reference,pickupReferenceType=ref_type,pickupJobId=job)
                data['receipts'][key]['assetIds'].append(asset['id'])
                event(data,'Asset collected for refurb',actor,date,assetId=asset['id'],number=number,receiptId=key,productId=prod['id'],client=client,reference=reference,jobId=job,notes=notes)
    elif kind=='refurb_receipt_ready':
        receipt=data['receipts'].get(text(p.get('receiptId'),'stock receipt ID',80,True))
        if not receipt or receipt['pool']!='Trident refurb stock':raise Problem(400,'Choose a refurbishment pickup.')
        if type(p.get('receiptRevision')) is not int or p['receiptRevision']!=receipt['revision']:raise Problem(409,'This pickup changed. Reopen it.')
        if date<receipt['date']:raise Problem(400,'Work completion cannot be before the collection date.')
        if receipt.get('refurbComplete'):raise Problem(409,'This pickup is already marked complete.')
        if not notes:raise Problem(400,'Record refurbishment work and the readiness check.')
        tech=worker(state,p.get('technician') or receipt.get('technician',''),True)
        receipt.update(refurbComplete=True,revision=receipt['revision']+1,refurbNotes=notes,technician=tech,refurbCompletedAt=date)
        for key in receipt['assetIds']:
            asset=data['assets'][key]
            if asset['receiptId']==receipt['id'] and asset['status']=='Refurbishing':
                chronological(data,asset,date)
                target='Awaiting new asset number' if asset.get('requiresRelabel') and not asset.get('refurbRelabelled') else 'Available'
                asset.update(status=target,location='Refurb workshop' if target!='Available' else 'Store',revision=asset['revision']+1,refurbTechnician=tech,refurbCompletedAt=date,refurbWorkComplete=True)
                event(data,'Refurb complete',actor,date,assetId=key,number=asset['number'],productId=asset['productId'],fromStatus='Refurbishing',toStatus=target,pool=asset['pool'],technician=tech,notes=notes)
        event(data,'Pickup refurbishment completed',actor,date,receiptId=receipt['id'],productId=receipt['productId'],quantity=receipt['quantity'],pool=receipt['pool'],technician=tech,notes=notes)
    elif kind=='assign_refurb':
        receipt=data['receipts'].get(text(p.get('receiptId'),'stock receipt ID',80,True))
        if not receipt or receipt['pool']!='Trident refurb stock' or receipt.get('refurbComplete'):raise Problem(400,'Choose an unfinished refurbishment pickup.')
        if type(p.get('receiptRevision')) is not int or p['receiptRevision']!=receipt['revision']:raise Problem(409,'This pickup changed. Reopen it.')
        tech=worker(state,p.get('technician'),True);receipt.update(technician=tech,revision=receipt['revision']+1)
        for key in receipt['assetIds']:
            if data['assets'][key]['status']=='Refurbishing':data['assets'][key].update(refurbTechnician=tech,revision=data['assets'][key]['revision']+1)
        event(data,'Refurb technician assigned',actor,date,receiptId=receipt['id'],productId=receipt['productId'],technician=tech,notes=notes)
    elif kind=='past_history':
        ids=p.get('assetIds');versions=p.get('revisions',{})
        if not isinstance(ids,list) or len(ids)!=1 or not isinstance(ids[0],str):raise Problem(400,'Choose one asset to add its history.')
        asset=data['assets'].get(ids[0])
        if not asset:raise Problem(404,'This asset no longer exists.')
        if not isinstance(versions,dict) or type(versions.get(asset['id'])) is not int or versions.get(asset['id'])!=asset['revision']:raise Problem(409,'This asset changed. Refresh and reopen its history.')
        history=number_history(data,asset)
        rows=p.get('pastNumbers',[])
        if not rows:raise Problem(400,'Add at least one past asset number.')
        additions=past_number_rows(data,rows,[asset['number']],{asset['number']:history[-1].get('validFrom')},{asset['number']:history})[asset['number']]
        previous=[*history[:-1],*additions];previous.sort(key=lambda r:r.get('validFrom') or '')
        asset['numberHistory']=[*previous,history[-1]];asset['previousNumbers']=[r['number'] for r in previous];asset['revision']+=1
        event(data,'Past asset numbers added',actor,date,assetId=asset['id'],number=asset['number'],productId=asset['productId'],pastNumbers=additions,notes=notes)
    elif kind=='asset':
        receipt=data['receipts'].get(text(p.get('receiptId'),'stock receipt ID',80,True))
        if not receipt:raise Problem(404,'This stock receipt no longer exists.')
        if type(p.get('receiptRevision')) is not int or p['receiptRevision']!=receipt['revision']:raise Problem(409,'This receipt changed. Reopen it before assigning asset numbers.')
        numbers=p.get('numbers')
        if not isinstance(numbers,list) or not numbers:raise Problem(400,'Enter at least one asset number.')
        numbers=[text(n,'asset number',80,True) for n in numbers]
        if len(numbers)>receipt['quantity']-len(receipt['assetIds']):raise Problem(400,'There are more asset numbers than unlabelled units on this receipt.')
        used={n.casefold() for a in data['assets'].values() for n in [a['number'],*a.get('previousNumbers',[])]}
        if len({n.casefold() for n in numbers})!=len(numbers) or any(n.casefold() in used for n in numbers):raise Problem(409,'Each asset number must be unique, including earlier labels.')
        histories=past_number_rows(data,p.get('pastNumbers',[]),numbers,{n:date for n in numbers})
        metadata=label_details(p,default_added=None if receipt.get('openingBalance') else receipt['date'],default_reference=receipt.get('reference',''))
        if 'labelReferenceType' not in p:metadata['referenceType']=receipt.get('referenceType','Reference')
        for number in numbers:
            key=str(uuid.uuid4());status='Refurbishing' if receipt['pool']=='Trident refurb stock' and not receipt.get('refurbComplete') else 'Available'
            asset={'id':key,'number':number,'numberHistory':[*histories[number],{'number':number,'validFrom':date,'validTo':None,**metadata}],'previousNumbers':[r['number'] for r in histories[number]],'receiptId':receipt['id'],'productId':receipt['productId'],'pool':receipt['pool'],'status':status,'location':'Refurb workshop' if status=='Refurbishing' else 'Store','client':'','reference':'','jobId':'','allocationId':'','lastAllocationId':'','refurbTechnician':receipt.get('technician',''),'refurbCompletedAt':receipt.get('refurbCompletedAt',''),'revision':1}
            data['assets'][key]=asset;receipt['assetIds'].append(key)
            event(data,'Asset registered',actor,date,assetId=key,number=number,productId=asset['productId'],receiptId=receipt['id'],toStatus=status,pool=asset['pool'],technician=asset['refurbTechnician'],pastNumbers=histories[number],labelDetails=metadata,notes=notes)
        receipt['revision']+=1
    elif kind in ('allocate','dispatch','return','ready','repair','retire','relabel'):
        ids=p.get('assetIds');versions=p.get('revisions',{})
        if not isinstance(ids,list) or not ids or len(ids)>1000 or any(not isinstance(key,str) for key in ids) or len(set(ids))!=len(ids):raise Problem(400,'Choose one or more assets.')
        selected=[]
        for key in ids:
            asset=data['assets'].get(key)
            if not asset:raise Problem(404,'An asset no longer exists.')
            if not isinstance(versions,dict) or type(versions.get(key)) is not int or versions[key]!=asset['revision']:raise Problem(409,'An asset changed. Refresh and reopen the action.')
            selected.append(asset)
        client=text(p.get('client',''),'client name',200,kind=='allocate');reference=text(p.get('reference',''),'PO reference',160,kind=='allocate')
        job=text(p.get('jobId',''),'Trident job ID',100,kind=='allocate')
        ref_type=reference_type(p.get('referenceType','PO'))
        allocationId=str(uuid.uuid4()) if kind=='allocate' else ''
        if kind=='allocate':data['allocations'][allocationId]={'id':allocationId,'jobId':job,'reference':reference,'referenceType':ref_type,'client':client,'date':date,'assetIds':ids[:],'assetStates':{a['id']:{'status':'Allocated','number':a['number'],'allocatedAt':date} for a in selected},'notes':notes}
        if kind=='relabel' and len(selected)!=1:raise Problem(400,'Relabel one asset at a time.')
        for asset in selected:
            chronological(data,asset,date)
            old=asset['status'];allocation={'client':asset['client'],'reference':asset['reference'],'jobId':asset.get('jobId','')}
            existingAllocation=data['allocations'].get(asset.get('allocationId'))
            allowed={'allocate':('Available',),'dispatch':('Allocated',),'return':('With client','Allocated'),'ready':('Refurbishing','Repair'),'repair':('Available',),'retire':('Available','Refurbishing','Repair'),'relabel':STATES}
            if old not in allowed[kind]:raise Problem(400,f"{asset['number']} cannot be {kind} from {old}.")
            if kind=='allocate':asset.update(status='Allocated',client=client,reference=reference,referenceType=ref_type,allocatedAt=date,location='Store · allocated',jobId=job,allocationId=allocationId,lastAllocationId=allocationId)
            elif kind=='dispatch':
                asset.update(status='With client',location=asset['client'],dispatchedAt=date)
                if existingAllocation:existingAllocation['assetStates'][asset['id']].update(status='With client',dispatchedAt=date)
            elif kind=='return':
                condition=p.get('condition')
                if condition not in ('Ready for stock','Needs work'):raise Problem(400,'Choose the returned condition.')
                status='Available' if condition=='Ready for stock' else 'Refurbishing' if asset['pool']=='Trident refurb stock' else 'Repair'
                if existingAllocation:
                    entry=existingAllocation['assetStates'][asset['id']]
                    entry.update(status='Cancelled' if old=='Allocated' else 'Returned',condition=condition)
                    entry['cancelledAt' if old=='Allocated' else 'returnedAt']=date
                asset.update(status=status,client='',reference='',jobId='',allocationId='',allocatedAt='',dispatchedAt='',location='Store' if status=='Available' else 'Refurb workshop' if status=='Refurbishing' else 'Repair workshop')
            elif kind=='ready':
                if not notes:raise Problem(400,'Record the refurbishment / repair work and readiness check.')
                if old=='Refurbishing':asset.update(refurbTechnician=worker(state,p.get('technician') or asset.get('refurbTechnician',''),True),refurbCompletedAt=date,refurbWorkComplete=True)
                target='Awaiting new asset number' if old=='Refurbishing' and asset.get('requiresRelabel') and not asset.get('refurbRelabelled') else 'Available'
                asset.update(status=target,location='Store' if target=='Available' else 'Refurb workshop')
            elif kind=='repair':asset.update(status='Repair',location='Repair workshop')
            elif kind=='retire':
                if not notes:raise Problem(400,'Record why the asset is being retired.')
                asset.update(status='Retired',location='Retired')
            elif kind=='relabel':
                number=text(p.get('number'),'new asset number',80,True)
                if not notes:raise Problem(400,'Record why the asset number changed.')
                if any(number.casefold()==n.casefold() for a in data['assets'].values() for n in [a['number'],*a.get('previousNumbers',[])]):raise Problem(409,'That asset number has already been used.')
                history=number_history(data,asset);history[-1]['validTo']=date
                history.append({'number':number,'validFrom':date,'validTo':None,**label_details(p,default_added=date)});asset['numberHistory']=history
                asset['previousNumbers'].append(asset['number']);asset['number']=number
                if asset.get('requiresRelabel'):
                    asset['refurbRelabelled']=True
                    if asset.get('refurbWorkComplete') and old in ('Refurbishing','Awaiting new asset number'):asset.update(status='Available',location='Store')
            asset['revision']+=1
            labels={'allocate':'Allocated to PO / client','dispatch':'Dispatched','return':'Allocation cancelled' if old=='Allocated' else 'Returned','ready':'Refurb complete' if old=='Refurbishing' else 'Repair complete','repair':'Sent for repair','retire':'Retired','relabel':'Asset number changed'}
            event(data,labels[kind],actor,date,assetId=asset['id'],number=asset['number'],productId=asset['productId'],fromStatus=old,toStatus=asset['status'],client=client or allocation['client'],reference=reference or allocation['reference'],referenceType=ref_type if kind=='allocate' else asset.get('referenceType',existingAllocation.get('referenceType','PO') if existingAllocation else 'PO'),jobId=job or allocation['jobId'],technician=asset.get('refurbTechnician',''),previousNumbers=asset['previousNumbers'][:],pool=asset['pool'],notes=notes)
    elif kind=='review':
        row=product(data,p.get('productId'));review=text(p.get('review'),'review note',4000,True)
        row.update(quantityReviewed=True,reviewNote=review,reviewedBy=actor)
        event(data,'Workbook row reviewed',actor,date,productId=row['id'],notes=review)
    else:raise Problem(400,'Choose a valid stock action.')
    return result
