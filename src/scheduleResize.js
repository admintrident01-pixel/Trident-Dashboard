import {isBooked} from './scheduleBooking.js'
import {assignedTechs,timeMinutes,timeText} from './scheduleMath.js'

// Pure, synchronous planner. No routing requests or persistence on pointer movement.
export function resizeSchedule(blocks,travels,original,draft,edge){
 const originals=new Map(blocks.filter(b=>!b.cancelled).map(b=>[b.id,b]))
 const rows=new Map([...originals].map(([id,b])=>[id,{...b}]))
 rows.set(original.id,{...draft})
 const attached=travels.filter(t=>t.linked!==false&&originals.has(t.anchorId))
 const barriers=travels.filter(t=>!attached.includes(t)&&!t.cancelled)
 const changed=new Set([original.id]),direction=edge==='start'?-1:1
 const bounds=(b,name)=>{
  const start=timeMinutes(b.start),end=start+b.duration
  const own=attached.filter(t=>t.anchorId===b.id&&assignedTechs(t).includes(name))
  return [Math.min(start,...own.filter(t=>t.side==='before').map(t=>start-t.duration)),Math.max(end,...own.filter(t=>t.side==='after').map(t=>end+t.duration))]
 }
 const issue=message=>({drafts:[draft],travels:[],error:message})
 const queue=[original.id];let steps=0
 while(queue.length){
  if(++steps>Math.max(20,blocks.length*blocks.length*4))return issue('There is not enough clear time to resize this booking.')
  const a=rows.get(queue.shift())
  for(const name of assignedTechs(a)){
   const [as,ae]=bounds(a,name)
   if(as<0||ae>1440)return issue('The booking or its travel would leave this day.')
   for(const b of [...rows.values(),...barriers]){
    if(a.id===b.id||!assignedTechs(b).includes(name))continue
    const [bs,be]=bounds(b,name)
    if(as>=be||bs>=ae)continue
    // Shrinking creates space, and does not rearrange unrelated existing conflicts.
    if(a.id===original.id&&timeMinutes(draft.start)>=timeMinutes(original.start)&&timeMinutes(draft.start)+draft.duration<=timeMinutes(original.start)+original.duration)continue
    const oldA=originals.get(a.id),oldB=originals.get(b.id)
    const inDirection=oldB&&(direction>0?timeMinutes(oldB.start)>=timeMinutes(oldA.start):timeMinutes(oldB.start)<=timeMinutes(oldA.start))
    if(b.id===original.id||b.source==='leave'||b.source==='travel'||isBooked(b)||!inDirection)return issue(`${b.client} cannot move. Resize less, or unbook the neighbouring appointment.`)
    const delta=direction>0?ae-bs:as-be
    const start=timeMinutes(b.start)+delta
    if(start<0||start+b.duration>1440)return issue('The booking or its travel would leave this day.')
    rows.set(b.id,{...b,start:timeText(start)});changed.add(b.id);queue.push(b.id)
   }
  }
 }
 const drafts=[...changed].map(id=>rows.get(id))
 const travelDrafts=attached.filter(t=>changed.has(t.anchorId)).map(t=>{const a=rows.get(t.anchorId);return {...t,start:timeText(t.side==='before'?timeMinutes(a.start)-t.duration:timeMinutes(a.start)+a.duration)}})
 return {drafts,travels:travelDrafts,error:''}
}

export function travelReview(block){
 if(block.routePending&&!block.routeError&&!block.routeConflict)return 'pending'
 if(block.routeError||block.routeConflict||block.locked!==false&&block.estimatedSeconds==null)return 'review'
 return block.locked===false?'manual':'calculated'
}

const palette=['#e5efff','#e1f3eb','#f1e7fa','#fff0d5','#dff3f5','#f9e5ee','#e9eddf']
export function appointmentColour(type){
 const standard=['equipment repair','equipment assessment','delivery','collection','vehicle service','client visit','other'].indexOf((type||'Other').trim().toLowerCase())
 if(standard>=0)return palette[standard]
 let hash=0;for(const c of (type||'Other').trim().toLowerCase())hash=(Math.imul(hash,31)+c.charCodeAt(0))|0
 return palette[(hash>>>0)%palette.length]
}
