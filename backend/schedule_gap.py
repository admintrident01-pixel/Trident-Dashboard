"""Atomic whole-side gap moves, planned against the complete day."""
import copy,datetime as dt
from core import Problem

def pack_gap(state,data,user):
 import schedule as s
 import schedule_links as links
 date=s.day(data.get('date'));name=data.get('technician');direction=data.get('direction')
 if direction not in ('above','below'):raise Problem(400,'Choose blocks above or below the gap.')
 blocks=links.day_blocks(state,date);by_id={b['id']:b for b in blocks}
 gap=next((g for g in links.free_gaps(state,date,name,blocks) if g['upperId']==data.get('upperId') and g['lowerId']==data.get('lowerId') and g['start']==data.get('start') and g['end']==data.get('end')),None)
 if not gap:raise Problem(409,'This empty space changed. Refresh the schedule and preview again.')
 delta=(gap['end']-gap['start'])*(1 if direction=='above' else -1)
 if not delta or delta%15:raise Problem(409,'Choose a gap in 15-minute steps.')
 moving={b['id'] for b in blocks if name in s.assigned(b) and (s.minutes(b['start'])+b['duration']<=gap['start'] if direction=='above' else s.minutes(b['start'])>=gap['end'])}
 edges=links.connections(state,date,[b for b in blocks if b.get('source')=='travel']) if links.active(state) else []
 while True:
  before=set(moving)
  for edge in edges:
   if edge['linked'] and (edge['leftId'] in moving or edge['rightId'] in moving):moving.update((edge['leftId'],edge['rightId']))
  for block in blocks:
   if block.get('source')=='travel' and block.get('linked',True) and (block['id'] in moving or block.get('anchorId') in moving):moving.update((block['id'],block['anchorId']))
  if moving==before:break
 if not moving:raise Problem(409,'There are no blocks on this side of the gap.')
 if (gap['lowerId'] if direction=='above' else gap['upperId']) in moving:raise Problem(409,'The linked group crosses this gap. Unlink it before closing the gap.')
 for identifier in moving:
  block=by_id.get(identifier)
  if not block:raise Problem(409,'A linked block changed. Refresh the schedule and preview again.')
  if block.get('source')=='leave':raise Problem(409,'Approved leave cannot move. Choose the other side of the gap, or update Leave forms.')
  if block.get('source')=='note':raise Problem(409,'Recurring notes cannot move. Choose the other side, or update Schedule settings.')
  links.require_movable(block)
  if block.get('source')=='travel' and not block.get('linked',True) and block.get('locked',True):raise Problem(409,'Unlock detached travel before moving it.')
  if block.get('source')=='travel' and (block.get('routeError') or block.get('routeConflict')):raise Problem(409,'Review the affected travel before closing this gap.')
  if s.minutes(block['start'])+delta<0 or s.minutes(block['start'])+delta+block['duration']>1440:raise Problem(409,'The blocks or their travel would leave the selected day.')
 result=copy.deepcopy(state);now=dt.datetime.now(dt.timezone.utc).isoformat()
 for identifier in moving:
  block=by_id[identifier];start=s.time_string(s.minutes(block['start'])+delta)
  if block.get('source')=='travel':
   if not block.get('linked',True):
    old=result.setdefault('travelBlocks',{}).get(identifier,{})
    result['travelBlocks'][identifier]={**old,'start':start,'date':date,'duration':block['duration'],'locked':block.get('locked',True),'linked':False,'technician':block['technician'],'version':old.get('version',0)+1,'updatedBy':user['email']}
  else:result.setdefault('appointments',{})[identifier]={**block,'start':start,'version':block.get('version',0)+1,'updatedAt':now,'updatedBy':user['email']}
 updated=links.day_blocks(result,date);new_by_id={b['id']:b for b in updated}
 # Recalculation may expose different travel or generated lunches. Do not silently
 # shorten, discard, introduce or move anything outside the reviewed plan.
 if new_by_id.keys()!=by_id.keys():raise Problem(409,'Travel or lunch changed during this move. Review those blocks before closing the gap.')
 for identifier,old in by_id.items():
  new=new_by_id[identifier];expected=s.time_string(s.minutes(old['start'])+(delta if identifier in moving else 0))
  if new['start']!=expected or new['duration']!=old['duration'] or s.assigned(new)!=s.assigned(old):raise Problem(409,'Travel could not follow this move without changing the reviewed times. Adjust its links first.')
 for identifier in moving:
  block=new_by_id[identifier]
  for other in updated:
   if identifier!=other['id'] and s.overlaps(block,other):raise Problem(409,f"This would overlap {other.get('client','another block')}. Adjust the affected blocks first.")
 # Closing space does not also request linking a new neighbour.
 if links.active(state):
  for edge in links.connections(result,date,[b for b in updated if b.get('source')=='travel']):
   if (edge['leftId'] in moving)!=(edge['rightId'] in moving):result.setdefault('scheduleLinks',{})[edge['id']]=False
 return result
