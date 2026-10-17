import {assignedTechs,timeMinutes,timeText} from './scheduleMath.js'

export function pendingSchedule(current,appointment,action='save'){
 if(!current||!appointment.id)return current
 const saved={...appointment,cancelled:action==='cancel'?true:action==='restore'?false:appointment.cancelled}
 const onDate=saved.date===current.date
 const travelBlocks=(current.travelBlocks||[]).filter(a=>a.anchorId!==saved.id||onDate&&!saved.cancelled&&assignedTechs(saved).includes(a.technician)).map(a=>a.anchorId===saved.id&&a.linked!==false?{...a,start:timeText(a.side==='before'?timeMinutes(saved.start)-a.duration:timeMinutes(saved.start)+saved.duration)}:a)
 return {...current,travelBlocks,lunchBlocks:(current.lunchBlocks||[]).filter(a=>a.id!==saved.id),appointments:[...current.appointments.filter(a=>a.id!==saved.id),...(onDate?[saved]:[])]}
}

export async function scheduleRequest(request,path,options={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),30000)
 try{return await request(path,{...options,signal:controller.signal})}
 finally{clearTimeout(timer)}
}
