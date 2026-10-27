"""Travel locks and explicit links between touching schedule blocks."""
import copy, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from core import Problem
import schedule_routes

def active(state):
    return bool(schedule_routes.configuration()['key'] or state.get('scheduleLinks') or any('locked' in row for row in state.get('travelBlocks',{}).values()))

def travel_blocks(state,date):
    import schedule as s
    rows=[]
    candidates=s.travel_candidates(state,date)
    pairs={(c.get('origin',''),c.get('destination','')) for c in candidates if (c['automatic'] or state.get('travelBlocks',{}).get(c['id'])) and state.get('travelBlocks',{}).get(c['id'],{}).get('locked',True)}
    with ThreadPoolExecutor(max_workers=4) as executor:
        routes=dict(zip(pairs,executor.map(lambda pair:schedule_routes.estimate(*pair),pairs)))
    for c in candidates:
        if state.get('scheduleHiddenTravel',{}).get(c['id']):continue
        saved=state.get('travelBlocks',{}).get(c['id'],{})
        if not saved and not c['automatic']:continue
        locked=saved.get('locked',True)
        linked=saved.get('linked',True)
        route=routes.get((c.get('origin',''),c.get('destination','')),{}) if locked else {}
        duration=route.get('defaultDuration',route.get('duration')) if locked else saved.get('duration',15)
        if duration is None:duration=saved.get('duration',15)
        if duration==0:continue
        start=c['edge']-duration if c['side']=='before' else c['edge']
        if not linked:start=s.minutes(saved.get('start',s.time_string(start)))
        # Keep the complete estimate visible; never silently shorten a journey.
        conflict=duration>c['maxDuration'] if linked else False
        if not 0<=start<1440 or start+duration>1440:continue
        block={**c,'source':'travel','type':'Travel','timing':'fixed','cancelled':False,'start':s.time_string(start),'duration':duration,'version':saved.get('version',0),'locked':locked,'linked':linked,'routeError':route.get('error',''),'estimatedSeconds':route.get('seconds'),'routeConflict':conflict,'notes':('Calculated by Google Maps; rounded up to 15 minutes.' if route.get('duration') else 'Manual travel time.' if not locked else route.get('error',''))}
        if not linked and saved.get('technician'):
            block.update(technician=saved['technician'],technicians=[saved['technician']])
        barriers=s.leave_blocks(state,date)+s.schedule_notes.blocks(state,date)+s.lunch_blocks(state,date)
        if not linked:barriers+=s.read_without_travel(state,date)
        if any(s.overlaps(block,b) for b in barriers):block['routeConflict']=True
        if route.get('locationMissing'):block['routeLocationMissing']=True
        rows.append(block)
    return rows

def edge_id(name,left,right):return name+'|'+left+'|'+right

def connections(state,date,travels=None):
    import schedule as s
    blocks=[a for a in state.get('appointments',{}).values() if a['date']==date and not a.get('cancelled') ]+s.lunch_blocks(state,date)+(travels if travels is not None else s.travel_blocks(state,date))
    result=[]
    for name in {n for b in blocks for n in s.assigned(b)}:
        rows=sorted([b for b in blocks if name in s.assigned(b)],key=lambda b:s.minutes(b['start']))
        for left in rows:
            end=s.minutes(left['start'])+left['duration']
            for right in rows:
                if left['id']==right['id'] or s.minutes(right['start'])!=end:continue
                key=edge_id(name,left['id'],right['id'])
                result.append({'id':key,'technician':name,'leftId':left['id'],'rightId':right['id'],'minute':end,'linked':state.get('scheduleLinks',{}).get(key,True),'leftLabel':left['client'],'rightLabel':right['client']})
    return result

def save_control(state,data,user):
    import schedule as s
    date=s.day(data.get('date'));action=data.get('action');result=copy.deepcopy(state)
    if action=='link_block':
        if type(data.get('linked')) is not bool:raise Problem(400,'Choose link or unlink.')
        edges=[e for e in connections(state,date) if data.get('blockId') in (e['leftId'],e['rightId'])]
        if not edges:raise Problem(409,'No blocks touch this appointment. Click an empty gap to snap and link them first.')
        for edge in edges:result=save_control(result,{'date':date,'action':'link','edgeId':edge['id'],'linked':data['linked']},user)
        return result
    if action=='link':
        edge=next((e for e in connections(state,date) if e['id']==data.get('edgeId')),None)
        if not edge:raise Problem(409,'These edges no longer touch. Refresh the schedule.')
        if type(data.get('linked')) is not bool:raise Problem(400,'Choose link or unlink.')
        result.setdefault('scheduleLinks',{})[edge['id']]=data['linked']
        for block in s.travel_blocks(state,date):
            if block['id'] not in (edge['leftId'],edge['rightId']):continue
            other=edge['rightId'] if block['id']==edge['leftId'] else edge['leftId']
            if other==block['anchorId']:
                old=result.setdefault('travelBlocks',{}).get(block['id'],{})
                result['travelBlocks'][block['id']]={**old,'duration':block['duration'],'locked':block.get('locked',True),'linked':data['linked'],'start':block['start'],'date':date,'version':old.get('version',0)+1,'updatedBy':user['email']}
        return result
    current=next((b for b in s.travel_blocks(state,date) if b['id']==data.get('id')),None)
    if not current or current['version']!=data.get('version'):raise Problem(409,'This travel block changed. Refresh the schedule.')
    old=result.setdefault('travelBlocks',{}).get(current['id'],{})
    update={**old,'duration':current['duration'],'locked':current.get('locked',True),'linked':current.get('linked',True),'start':current['start'],'date':date,'version':old.get('version',0)+1,'updatedBy':user['email']}
    if action=='recalculate':
        route=schedule_routes.estimate(current.get('origin',''),current.get('destination',''),force=True)
        if 'duration' not in route:raise Problem(400,route.get('error','Travel could not be calculated. Check the route addresses.'))
        update.update(locked=True,duration=route['duration'])
    elif action=='lock':
        if type(data.get('locked')) is not bool:raise Problem(400,'Choose lock or unlock.')
        update['locked']=data['locked']
    elif action=='move':
        if update['locked'] or update['linked']:raise Problem(400,'Unlock and unlink travel before moving it independently.')
        start=s.minutes(data.get('start'))
        trial={**current,'start':s.time_string(start)}
        barriers=s.read_without_travel(state,date)+[b for b in s.travel_blocks(state,date) if b['id']!=current['id']]
        if start+trial['duration']>1440 or any(s.overlaps(trial,b) for b in barriers):raise Problem(409,'Travel would overlap another block or leave the selected day.')
        update['start']=trial['start']
    elif action=='resize':
        if update['locked']:raise Problem(400,'Unlock travel before adjusting its time.')
        delta=data.get('delta')
        if type(delta) is not int or delta not in (-15,15):raise Problem(400,'Adjust travel in 15-minute increments.')
        duration=current['duration']+delta
        start=s.minutes(current['start'])-(delta if current['side']=='before' and update['linked'] else 0)
        trial={**current,'start':s.time_string(start),'duration':duration}
        barriers=[a for a in s.read_without_travel(state,date) if a['id']!=current['anchorId'] or not update['linked']]+[b for b in s.travel_blocks(state,date) if b['id']!=current['id']]
        if duration<15 or start<0 or start+duration>1440 or any(s.overlaps(trial,b) for b in barriers):raise Problem(409,'Travel would overlap another block or leave the day. Unlink or move the neighbouring block first.')
        update.update(duration=duration,start=trial['start'])
    else:raise Problem(400,'Choose a travel control.')
    result['travelBlocks'][current['id']]=update
    return result

def move_connected(state,result,old,appointment,user):
    import schedule as s
    if not active(state) or not old or appointment.get('cancelled'):return result
    changed=old['start']!=appointment['start'] or old['date']!=appointment['date'] or s.assigned(old)!=s.assigned(appointment)
    if not changed:return result
    edges=[e for e in connections(state,old['date']) if e['linked']]
    component={old['id']}
    while True:
        added={e[k] for e in edges if e['leftId'] in component or e['rightId'] in component for k in ('leftId','rightId')}
        if added<=component:break
        component|=added
    siblings=component-{old['id']}
    if not siblings:return result
    lunches={a['id']:a for a in s.lunch_blocks(state,old['date'])}
    sibling_bookings=siblings & (set(state.get('appointments',{}))|set(lunches))
    if not sibling_bookings and (old['date']!=appointment['date'] or s.assigned(old)!=s.assigned(appointment)):return result
    if old['date']!=appointment['date'] or s.assigned(old)!=s.assigned(appointment):raise Problem(409,'Unlink the touching blocks before changing this booking’s date or technician.')
    delta=s.minutes(appointment['start'])-s.minutes(old['start'])
    if not delta:return result
    for identifier in siblings:
        other=state.get('appointments',{}).get(identifier) or lunches.get(identifier)
        if not other:continue
        require_movable(other)
        start=s.minutes(other['start'])+delta
        if start<0 or start+other['duration']>1440:raise Problem(409,'The linked group would leave the selected day.')
        result['appointments'][identifier]={**other,'start':s.time_string(start),'version':other['version']+1,'updatedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'updatedBy':user['email']}
    for identifier in siblings:
        block=next((b for b in s.travel_blocks(state,old['date']) if b['id']==identifier),None)
        if block and not block.get('linked',True):
            saved=result.setdefault('travelBlocks',{}).get(identifier,{})
            result['travelBlocks'][identifier]={**saved,'duration':block['duration'],'locked':block.get('locked',True),'linked':False,'start':s.time_string(s.minutes(block['start'])+delta),'date':old['date'],'version':saved.get('version',0)+1}
    changed_rows=[a for identifier,a in result.get('appointments',{}).items() if identifier in component]
    for a in changed_rows:
        for b in s.read_without_travel(result,a['date'])+[b for b in s.travel_blocks(result,a['date']) if not b.get('linked',True)]:
            if b['id']!=a['id'] and s.overlaps(a,b):raise Problem(409,'The linked group would overlap another booking, lunch or approved leave.')
    return result


def connected_ids(state,old):
    if not active(state):return {old['id']}
    edges=[e for e in connections(state,old['date']) if e['linked']]
    ids={old['id']}
    while True:
        added={e[k] for e in edges if e['leftId'] in ids or e['rightId'] in ids for k in ('leftId','rightId')}
        if added<=ids:return ids
        ids|=added


def day_blocks(state,date,travels=None):
    import schedule as s
    return s.read_without_travel(state,date)+(travels if travels is not None else s.travel_blocks(state,date))


def free_gaps(state,date,name,blocks=None):
    import schedule as s
    rows=sorted([b for b in (blocks if blocks is not None else day_blocks(state,date)) if name in s.assigned(b)],key=lambda b:(s.minutes(b['start']),b['id']))
    result=[];upper=None;end=0
    for lower in rows:
        start=s.minutes(lower['start'])
        if upper and start>end:result.append({'upperId':upper['id'],'lowerId':lower['id'],'start':end,'end':start})
        lower_end=start+lower['duration']
        if upper is None or lower_end>end:upper=lower;end=lower_end
    return result


def snap_gap(state,data,user):
    import schedule as s
    date=s.day(data.get('date'));name=data.get('technician')
    blocks=day_blocks(state,date);by_id={b['id']:b for b in blocks}
    gap=next((g for g in free_gaps(state,date,name,blocks) if g['upperId']==data.get('upperId') and g['lowerId']==data.get('lowerId')),None)
    if not gap:raise Problem(409,'This empty space changed. Refresh the schedule and try again.')
    edges=[e for e in connections(state,date,[b for b in blocks if b.get('source')=='travel']) if e['linked']]
    def component(identifier):
        ids={identifier}
        while True:
            added={e[k] for e in edges if e['leftId'] in ids or e['rightId'] in ids for k in ('leftId','rightId')}
            if added<=ids:return ids
            ids|=added
    above=component(gap['upperId']);below=component(gap['lowerId'])
    # Only the lower group moves. A fixed upper booking is a valid anchor.
    for label,ids in [('below',below)]:
        for identifier in ids:
            block=by_id[identifier]
            if block.get('source')=='leave':raise Problem(409,f'The block {label} is approved leave. It cannot be snapped or linked across this gap.')
            if block.get('source')!='travel' and block.get('timing')=='fixed':raise Problem(409,f"The appointment {label} is fixed ({block['client']}). Consider making it flexible before moving.")
            require_movable(block)
    if above & below:raise Problem(409,'These blocks already belong to the same linked group. Unlink them before closing this gap.')
    delta=gap['start']-gap['end'];result=copy.deepcopy(state);now=dt.datetime.now(dt.timezone.utc).isoformat()
    for identifier in below:
        block=by_id[identifier];start=s.minutes(block['start'])+delta
        if start<0 or start+block['duration']>1440:raise Problem(409,'The snapped group would leave the selected day.')
        if block.get('source')=='travel':
            # Its anchor moves it when linked; detached travel keeps an explicit start.
            if not block.get('linked',True):
                old=result.setdefault('travelBlocks',{}).get(identifier,{})
                result['travelBlocks'][identifier]={**old,'start':s.time_string(start),'date':date,'duration':block['duration'],'locked':block.get('locked',True),'linked':False,'version':old.get('version',0)+1,'updatedBy':user['email']}
        else:
            result.setdefault('appointments',{})[identifier]={**block,'start':s.time_string(start),'version':block.get('version',0)+1,'updatedAt':now,'updatedBy':user['email']}
    updated=day_blocks(result,date);updated_by_id={b['id']:b for b in updated}
    for identifier in below:
        moved=updated_by_id.get(identifier)
        if not moved:raise Problem(409,'A travel block could not follow this move. Refresh the schedule.')
        for other in updated:
            if other['id']!=identifier and s.overlaps(moved,other):raise Problem(409,'Snapping would overlap another booking, travel, lunch or approved leave. Unlink or adjust the neighbouring blocks first.')
    join=next((e for e in connections(result,date,[b for b in updated if b.get('source')=='travel']) if e['technician']==name and e['leftId']==gap['upperId'] and e['rightId']==gap['lowerId']),None)
    if not join:raise Problem(409,'These blocks could not be joined without changing their travel time.')
    return save_control(result,{'date':date,'action':'link','edgeId':join['id'],'linked':True},user)


def move_selection(state,data,user):
    """Move explicitly selected blocks; separate links to unchecked bookings."""
    import schedule as s
    date=s.day(data.get('date'));ids=data.get('ids');delta=data.get('delta')
    if not isinstance(ids,list) or not ids or len(ids)>1000 or any(not isinstance(i,str) for i in ids):raise Problem(400,'Select schedule blocks to move.')
    if type(delta) is not int or delta%15 or not -1440<delta<1440:raise Problem(400,'Move blocks in quarter-hour increments.')
    source=data.get('fromTechnician');target=data.get('toTechnician');transfer=source!=target
    names={t['name'] for t in s.timesheets.settings(state)['technicians']}
    if transfer and (source not in names or target not in names):raise Problem(400,'Choose technicians from Settings.')
    blocks=day_blocks(state,date);by_id={b['id']:b for b in blocks};selected=set(ids)
    if not selected<=by_id.keys():raise Problem(409,'The selected blocks changed. Refresh and select them again.')
    anchors={i for i in selected if by_id[i].get('source') not in ('travel','leave')}
    moving=selected|{b['id'] for b in blocks if b.get('source')=='travel' and b.get('linked',True) and b.get('anchorId') in anchors}
    result=copy.deepcopy(state);now=dt.datetime.now(dt.timezone.utc).isoformat();remapped={}
    for edge in connections(state,date,[b for b in blocks if b.get('source')=='travel']):
        if (edge['leftId'] in moving)!=(edge['rightId'] in moving):result.setdefault('scheduleLinks',{})[edge['id']]=False
    def technicians(block):return list(dict.fromkeys(target if transfer and n==source else n for n in s.assigned(block)))
    for identifier in moving:
        block=by_id[identifier]
        if block.get('source')=='leave':raise Problem(409,'Approved leave cannot be moved with a selection.')
        require_movable(block)
        start=s.minutes(block['start'])+delta
        if start<0 or start+block['duration']>1440:raise Problem(409,'The selection would leave the selected day.')
        assigned=technicians(block)
        if block.get('source')=='travel':
            destination_id=s.travel_id(date,assigned[0],block['anchorId'],block['side']) if transfer and block.get('anchorId') in anchors and block['technician']==source else identifier
            remapped[identifier]=destination_id
            if destination_id!=identifier:
                previous=result.setdefault('travelBlocks',{}).pop(identifier,None)
                if previous:result['travelBlocks'][destination_id]=previous
            if block.get('anchorId') not in anchors or not block.get('linked',True):
                old=result.setdefault('travelBlocks',{}).get(identifier,{})
                result['travelBlocks'][destination_id]={**old,'start':s.time_string(start),'date':date,'duration':block['duration'],'locked':block.get('locked',True),'linked':False,'technician':assigned[0],'version':old.get('version',0)+1,'updatedBy':user['email']}
        else:
            result.setdefault('appointments',{})[identifier]={**block,'start':s.time_string(start),'technician':assigned[0],'technicians':assigned,'version':block.get('version',0)+1,'updatedAt':now,'updatedBy':user['email']}
    updated=day_blocks(result,date);updated_by_id={b['id']:b for b in updated}
    changed={i for i in selected if by_id[i].get('source')!='travel'}
    changed|={b['id'] for b in updated if b.get('source')=='travel' and b.get('linked',True) and b.get('anchorId') in anchors}
    changed|={remapped.get(i,i) for i in selected if by_id[i].get('source')=='travel' and (by_id[i].get('anchorId') not in anchors or not by_id[i].get('linked',True))}
    for identifier in changed:
        moved=updated_by_id.get(identifier)
        if not moved:raise Problem(409,'A selected block could not follow this move. Refresh the schedule.')
        for other in updated:
            if other['id'] not in changed and s.overlaps(moved,other):raise Problem(409,'The selection would overlap another booking, travel, lunch or approved leave.')
    for edge in connections(result,date,[b for b in updated if b.get('source')=='travel']):
        if (edge['leftId'] in changed)!=(edge['rightId'] in changed):result.setdefault('scheduleLinks',{})[edge['id']]=False
    return result


def delete_selection(state,data,user):
    import schedule as s
    date=s.day(data.get('date'));ids=data.get('ids')
    if not isinstance(ids,list) or not ids or len(ids)>1000 or any(not isinstance(i,str) for i in ids):raise Problem(400,'Select blocks to delete.')
    blocks={b['id']:b for b in day_blocks(state,date)}
    if any(i not in blocks for i in ids):raise Problem(409,'The selected blocks changed. Refresh and select them again.')
    if any(blocks[i].get('source') in ('leave','note') for i in ids):raise Problem(409,'Approved leave and recurring notes must be managed in their own settings.')
    result=copy.deepcopy(state);now=dt.datetime.now(dt.timezone.utc).isoformat()
    for identifier in set(ids):
        block=blocks[identifier]
        if block.get('source')=='travel':result.setdefault('scheduleHiddenTravel',{})[identifier]=True
        else:result.setdefault('appointments',{})[identifier]={**block,'cancelled':True,'version':block.get('version',0)+1,'updatedAt':now,'updatedBy':user['email']}
    return result


def travel_next(state,data,user):
    """Anchor Google travel after the upper booking; optionally pull the next one."""
    import schedule as s
    date=s.day(data.get('date'));name=data.get('technician')
    rows=sorted([b for b in s.read_without_travel(state,date) if b.get('source') not in ('leave','lunch','note') and name in s.assigned(b)],key=lambda b:(s.minutes(b['start']),b['id']))
    index=next((i for i,b in enumerate(rows) if b['id']==data.get('upperId')),None)
    if index is None or index+1>=len(rows):raise Problem(409,'There is no next appointment for this technician.')
    top=rows[index];bottom=rows[index+1]
    if bottom['id']!=data.get('lowerId'):raise Problem(409,'The next appointment changed. Reopen the menu and try again.')
    make_flexible=data.get('makeFlexible')
    if bottom.get('timing')=='fixed' and data.get('pullBelow') is not False and type(make_flexible) is not bool:raise Problem(400,'Choose whether to make the lower appointment flexible.')
    route=schedule_routes.estimate(top['address'],bottom['address'],force=True)
    if 'duration' not in route:raise Problem(400,route.get('error','Travel could not be calculated. Check both appointment addresses.'))
    duration=route['duration'];end=s.minutes(top['start'])+top['duration']
    if duration<=0:raise Problem(400,'These addresses need no driving time. Use Snap & link to join the blocks.')
    if end+duration>1440:raise Problem(409,'This journey would finish outside the selected day.')
    result=copy.deepcopy(state);after_id=s.travel_id(date,name,top['id'],'after');before_id=s.travel_id(date,name,bottom['id'],'before')
    old=result.setdefault('travelBlocks',{}).get(after_id,{})
    result['travelBlocks'][after_id]={**old,'date':date,'start':s.time_string(end),'duration':duration,'locked':True,'linked':True,'version':old.get('version',0)+1,'updatedBy':user['email']}
    result.setdefault('scheduleHiddenTravel',{}).pop(after_id,None)
    result['scheduleHiddenTravel'][before_id]=True
    result.setdefault('scheduleLinks',{})[edge_id(name,top['id'],bottom['id'])]=False
    pull=data.get('pullBelow') is not False and (bottom.get('timing')!='fixed' or make_flexible is True)
    if pull:
        if bottom.get('bookingStatus')=='confirmed':require_movable(bottom)
        if make_flexible is True:result['appointments'][bottom['id']]={**result['appointments'][bottom['id']],'timing':'flexible'}
        delta=end+duration-s.minutes(bottom['start'])
        result=move_selection(result,{'date':date,'ids':[bottom['id']],'delta':delta},user)
        result.setdefault('scheduleLinks',{})[edge_id(name,after_id,bottom['id'])]=True
    else:
        result.setdefault('scheduleLinks',{})[edge_id(name,after_id,bottom['id'])]=False
    result['scheduleLinks'][edge_id(name,top['id'],after_id)]=True
    # The upper appointment remains byte-for-byte unchanged, even if fixed.
    if result['appointments'][top['id']]!=state['appointments'][top['id']]:raise Problem(409,'The upper appointment must stay in place.')
    return result


def require_movable(block):
    if block.get('source')=='travel':return
    if block.get('bookingStatus')=='confirmed':raise Problem(409,f"{block['client']} is booked (Confirmed). Unbook it before moving.")
    if block.get('timing')=='fixed':raise Problem(409,f"{block['client']} is fixed. Consider making it flexible before moving.")


def move_to_date(state,data,user,edited=None):
    import schedule as s
    source=s.day(data.get('date'));target=s.day(data.get('targetDate'));ids=data.get('ids')
    if source==target:raise Problem(400,'Choose a different date to move these blocks.')
    if not isinstance(ids,list) or not ids or len(ids)>1000 or any(not isinstance(i,str) for i in ids):raise Problem(400,'Select appointments to move.')
    original=day_blocks(state,source);by_id={b['id']:b for b in original};selected=set(ids)
    if not selected<=by_id.keys():raise Problem(409,'The selection changed. Refresh and select it again.')
    anchors={i for i in selected if by_id[i].get('source') not in ('travel','leave')}
    if any(by_id[i].get('source')=='travel' and by_id[i].get('anchorId') not in anchors for i in selected):raise Problem(400,'Select the associated appointment when moving travel to another date.')
    moving=selected|{b['id'] for b in original if b.get('source')=='travel' and b.get('anchorId') in anchors}
    for identifier in moving:
        block=by_id[identifier]
        if block.get('source')=='leave':raise Problem(409,'Approved leave must be changed in Leave forms.')
        require_movable(block)
    delta=s.minutes(edited['start'])-s.minutes(by_id[edited['id']]['start']) if edited else 0
    result=copy.deepcopy(state);now=dt.datetime.now(dt.timezone.utc).isoformat();moved_ids=set()
    for edge in connections(state,source,[b for b in original if b.get('source')=='travel']):
        if (edge['leftId'] in moving)!=(edge['rightId'] in moving):result.setdefault('scheduleLinks',{})[edge['id']]=False
    for identifier in anchors:
        block=by_id[identifier];start=s.minutes(block['start'])+delta
        if start<0 or start+block['duration']>1440:raise Problem(409,'A moved block would finish outside the selected day.')
        value={**block,'date':target,'start':s.time_string(start),'version':block.get('version',0)+1,'updatedAt':now,'updatedBy':user['email']}
        if edited and identifier==edited['id']:value.update(edited,version=block.get('version',0)+1,updatedAt=now,updatedBy=user['email'])
        if block.get('source')=='lunch':
            target_id='lunch:'+str(s.uuid.uuid5(s.uuid.NAMESPACE_URL,target+':'+s.assigned(block)[0]))
            if target_id in state.get('appointments',{}) and not state['appointments'][target_id].get('cancelled'):raise Problem(409,'There is already a saved lunch block on the destination date.')
            result.setdefault('appointments',{})[identifier]={**block,'cancelled':True,'version':block.get('version',0)+1,'updatedAt':now,'updatedBy':user['email']}
            value['id']=target_id;identifier=target_id
        result.setdefault('appointments',{})[identifier]=value;moved_ids.add(identifier)
    for identifier in moving-anchors:
        block=by_id[identifier]
        if block.get('source')!='travel':continue
        old=result.setdefault('travelBlocks',{}).get(identifier)
        if old:
            value={**old,'date':target,'version':old.get('version',0)+1,'updatedBy':user['email']}
            if not block.get('linked',True):value['start']=s.time_string(s.minutes(block['start'])+delta)
            result['travelBlocks'][identifier]=value
    destination=day_blocks(result,target)
    moved_ids|={b['id'] for b in destination if b.get('source')=='travel' and b.get('anchorId') in anchors}
    for block in destination:
        if block['id'] not in moved_ids:continue
        for other in destination:
            if other['id'] not in moved_ids and s.overlaps(block,other):raise Problem(409,f"Cannot move to {target}: the selection overlaps {other.get('client','another booking')} for this technician.")
    return result
