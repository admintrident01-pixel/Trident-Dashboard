export const timeMinutes=value=>Number(value.slice(0,2))*60+Number(value.slice(3,5))
export const timeText=value=>`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
export const snapMinutes=value=>Math.round(value/15)*15
export function pointerMinute(range,rect,point,vertical=true){
 const coordinate=vertical?point.y:point.x,origin=vertical?rect.top:rect.left,size=vertical?rect.height:rect.width
 if(!Number.isFinite(coordinate)||!Number.isFinite(origin)||!Number.isFinite(size)||size<=0||!Number.isFinite(range.start)||!Number.isFinite(range.end)||range.end<=range.start)throw Error('Choose a visible schedule time.')
 return Math.min(1425,range.end-15,Math.max(0,range.start,snapMinutes(range.start+(coordinate-origin)/size*(range.end-range.start))))
}
export function moveAppointment(original,delta,mode){
 const start=timeMinutes(original.start),end=start+original.duration
 if(mode==='end')return {...original,duration:Math.min(1440-start,Math.max(15,original.duration+snapMinutes(delta)))}
 if(mode==='start'){
  const next=Math.min(end-15,Math.max(0,start+snapMinutes(delta)))
  return {...original,start:timeText(next),duration:end-next}
 }
 return {...original,start:original.timing==='fixed'?original.start:timeText(Math.min(1440-original.duration,Math.max(0,start+snapMinutes(delta))))}
}
export function rangeFor(appointments,view='fit',workHours={start:'08:00',finish:'16:00'}){
 if(view===true||view==='full')return {start:0,end:1440}
 const configuredStart=timeMinutes(workHours.start||'08:00'),configuredEnd=timeMinutes(workHours.finish||'16:00')
 const normal=Number.isFinite(configuredStart)&&Number.isFinite(configuredEnd)&&configuredEnd>configuredStart?{start:configuredStart,end:configuredEnd}:{start:480,end:960}
 if(view==='normal')return normal
 const active=appointments.filter(a=>!a.cancelled)
 return {start:Math.min(Math.floor(normal.start/60)*60,...active.map(a=>Math.floor(timeMinutes(a.start)/60)*60)),end:Math.max(Math.ceil(normal.end/60)*60,...active.map(a=>Math.ceil((timeMinutes(a.start)+a.duration)/60)*60))}
}
export const hourMarks=range=>Array.from({length:Math.ceil((range.end-range.start)/60)},(_,i)=>range.start+i*60)
export function blockPosition(appointment,range){
 const start=Math.max(range.start,timeMinutes(appointment.start)),end=Math.min(range.end,timeMinutes(appointment.start)+appointment.duration)
 return {left:100*(start-range.start)/(range.end-range.start),width:100*Math.max(0,end-start)/(range.end-range.start)}
}
export const assignedTechs=appointment=>Array.isArray(appointment.technicians)?appointment.technicians:[appointment.technician]
export function reassignTechnician(appointment,from,to){
 const technicians=[...new Set(assignedTechs(appointment).map(name=>name===from?to:name))]
 return {...appointment,technician:technicians[0],technicians}
}

// Sum each assigned technician's full bookings and travel for the selected day.
export function technicianBookedMinutes(appointments,travelBlocks,technician){
 return [...appointments,...travelBlocks].filter(a=>!a.cancelled&&!['lunch','leave'].includes(a.source)&&assignedTechs(a).includes(technician)).reduce((total,a)=>total+Math.max(0,Number(a.duration)||0),0)
}
export function bookedTimeLabel(minutes){
 return `${Number((minutes/60).toFixed(2))}h`
}


export function scheduleGaps(blocks,technician,range){
 const rows=blocks.filter(b=>!b.cancelled&&assignedTechs(b).includes(technician)).slice().sort((a,b)=>timeMinutes(a.start)-timeMinutes(b.start)||a.id.localeCompare(b.id))
 const gaps=[];let upper=null,end=0
 for(const lower of rows){
  const start=timeMinutes(lower.start)
  if(upper&&start>end&&Math.min(start,range.end)>Math.max(end,range.start))gaps.push({upperId:upper.id,lowerId:lower.id,start:end,end:start,visibleStart:Math.max(end,range.start),visibleEnd:Math.min(start,range.end)})
  const nextEnd=start+lower.duration
  if(!upper||nextEnd>end){upper=lower;end=nextEnd}
 }
 return gaps
}

// Keep intersecting time blocks visible without changing their start or duration.
export function overlapLanes(blocks,technician,range){
 const rows=blocks.filter(b=>!b.cancelled&&assignedTechs(b).includes(technician)&&blockPosition(b,range).width>0).slice().sort((a,b)=>timeMinutes(a.start)-timeMinutes(b.start)||a.id.localeCompare(b.id))
 const result=new Map();let group=[],ends=[],groupEnd=-1
 function finish(){for(const row of group)result.set(row.id,{lane:row.lane,count:ends.length})}
 for(const row of rows){
  const start=timeMinutes(row.start),end=start+row.duration
  if(start>=groupEnd){finish();group=[];ends=[];groupEnd=-1}
  let lane=ends.findIndex(value=>value<=start);if(lane<0)lane=ends.length
  ends[lane]=end;group.push({id:row.id,lane});groupEnd=Math.max(groupEnd,end)
 }
 finish();return result
}
export function travelSourceLabel(block){
 if(block.routePending)return block.estimatedSeconds!=null?'Cached route · refreshing…':'Calculating travel…'
 if(block.locked===false)return 'Manual travel'
 return block.estimatedSeconds!=null&&!block.routeError?'Calculated by Google Maps':'Automatic travel — calculation needs review'
}
export function travelTooltip(block){
 return `${travelSourceLabel(block)}\nFrom: ${block.origin||'Not recorded'}\nTo: ${block.destination||'Not recorded'}\n${block.start}–${timeText(timeMinutes(block.start)+block.duration)} · ${(block.duration/60).toFixed(2)} hours${block.routeError?'\n'+block.routeError:''}${block.routeConflict?'\nOverlaps another block or exceeds the available gap.':''}`
}
