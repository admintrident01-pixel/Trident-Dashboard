export const timeMinutes=value=>Number(value.slice(0,2))*60+Number(value.slice(3,5))
export const timeText=value=>`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
export const snapMinutes=value=>Math.round(value/15)*15
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
