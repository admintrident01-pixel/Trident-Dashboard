/** Preview a whole side of a technician's gap, including linked team work and travel. */
import {assignedTechs,timeMinutes,timeText} from './scheduleMath.js'
export function gapPackPlan(blocks,connections,technician,gap,direction){
 const rows=blocks.filter(b=>!b.cancelled),byId=new Map(rows.map(b=>[b.id,b]))
 const issue=error=>({ids:[...moving],drafts:[],delta,error})
 const delta=(gap.end-gap.start)*(direction==='above'?1:-1),moving=new Set()
 if(!['above','below'].includes(direction)||!Number.isInteger(delta)||!delta||delta%15)return issue('Choose a gap in 15-minute steps.')
 for(const b of rows)if(assignedTechs(b).includes(technician)&&(direction==='above'?timeMinutes(b.start)+b.duration<=gap.start:timeMinutes(b.start)>=gap.end))moving.add(b.id)
 if(!moving.size)return issue('There are no blocks on this side of the gap.')
 let changed=true
 while(changed){
  const before=moving.size
  for(const edge of connections||[])if(edge.linked&&(moving.has(edge.leftId)||moving.has(edge.rightId))){moving.add(edge.leftId);moving.add(edge.rightId)}
  for(const b of rows)if(b.source==='travel'&&b.linked!==false&&(moving.has(b.id)||moving.has(b.anchorId))){moving.add(b.id);moving.add(b.anchorId)}
  changed=before!==moving.size
 }
 if(moving.has(direction==='above'?gap.lowerId:gap.upperId))return issue('The linked group crosses this gap. Unlink it before closing the gap.')
 for(const id of moving){
  const b=byId.get(id)
  if(!b)return issue('A linked block changed. Refresh the schedule and preview again.')
  if(b.source==='leave')return issue('Approved leave cannot move. Choose the other side of the gap, or update Leave forms.')
  if(b.source==='note')return issue('Recurring notes cannot move. Choose the other side, or update Schedule settings.')
  if(b.source!=='travel'&&b.bookingStatus==='confirmed')return issue(`${b.client} is booked (Confirmed). Unbook it before moving.`)
  if(b.source!=='travel'&&b.timing==='fixed')return issue(`${b.client} is fixed. Make it flexible before moving.`)
  if(b.source==='travel'&&b.linked===false&&b.locked!==false)return issue('Unlock detached travel before moving it.')
  if(b.source==='travel'&&(b.routeError||b.routeConflict))return issue('Review the affected travel before closing this gap.')
  if(timeMinutes(b.start)+delta<0||timeMinutes(b.start)+delta+b.duration>1440)return issue('The blocks or their travel would leave the selected day.')
 }
 const drafts=[...moving].map(id=>({...byId.get(id),start:timeText(timeMinutes(byId.get(id).start)+delta)}))
 const updated=rows.map(b=>drafts.find(d=>d.id===b.id)||b)
 for(const a of drafts)for(const b of updated){
  if(a.id===b.id||!assignedTechs(a).some(n=>assignedTechs(b).includes(n)))continue
  if(timeMinutes(a.start)<timeMinutes(b.start)+b.duration&&timeMinutes(b.start)<timeMinutes(a.start)+a.duration)return issue(`This would overlap ${b.client||'another block'}. Adjust the affected blocks first.`)
 }
 return {ids:[...moving],drafts,delta,error:''}
}
