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

export const appointmentFields=['date','technicians','start','duration','timing','client','address','type','notes','bookingStatus','timeBasis']
const comparable=(item,key)=>key==='technicians'?[...assignedTechs(item)].sort():item?.[key]??({bookingStatus:'action-needed',timeBasis:'start',notes:''}[key]??'')
const equal=(a,b)=>JSON.stringify(a)===JSON.stringify(b)
export const appointmentChanged=(base,mine)=>appointmentFields.some(key=>!equal(comparable(base,key),comparable(mine,key)))
export function scheduleItem(snapshot,id){return [...(snapshot?.appointments||[]),...(snapshot?.lunchBlocks||[]),...(snapshot?.travelBlocks||[]),...(snapshot?.editingAppointment?[snapshot.editingAppointment]:[])].find(a=>a.id===id)}
export function mergeAppointment(base,mine,latest){
 if(!base?.id)return {value:mine,conflicts:[]}
 if(!latest||!base.cancelled&&latest.cancelled)return {value:mine,conflicts:[],deleted:true}
 const value={...latest},conflicts=[]
 for(const key of appointmentFields){
  const old=comparable(base,key),own=comparable(mine,key),remote=comparable(latest,key)
  if(!equal(own,old)){
   if(!equal(remote,old)&&!equal(own,remote))conflicts.push({key,mine:mine[key],theirs:latest[key]})
   else value[key]=mine[key]
  }
 }
 value.technician=assignedTechs(value)[0]||''
 return {value,conflicts}
}

// Retry only an explicit rejected write, never an uncertain network outcome.
export async function saveSharedAppointment(request,{appointment,action='save',sendEmail=false,snapshot,etag,base,onRefresh=()=>{}}){
 let current=snapshot,token=etag
 const readLatest=async()=>{const refreshed=await scheduleRequest(request,'/api/schedule?date='+snapshot.date+(appointment.id?'&appointment='+encodeURIComponent(appointment.id):''),{cache:'no-store'});current=refreshed.data;token=refreshed.etag;onRefresh(refreshed)}
 if(base?.id&&!scheduleItem(current,base.id))await readLatest()
 for(let attempt=0;attempt<3;attempt++){
  const latest=appointment.id?scheduleItem(current,appointment.id):null
  const merged=mergeAppointment(base,appointment,latest)
  if(merged.deleted||merged.conflicts.length){
   throw Object.assign(Error(merged.deleted?'This appointment was removed by another user. Your unfinished booking is still saved.':'Someone changed the same details. Choose which values to keep below.'),{conflict:{...merged,mine:appointment,latest},snapshot:current})
  }
  const {_base,_draftKey,endTime,quickEntry,...payload}=merged.value
  // UI-only planning fields are recomputed from saved start and duration.
  void _base;void _draftKey;void endTime;void quickEntry
  if(action!=='save'&&base?.id&&latest?.version!==base.version)throw Object.assign(Error('This appointment changed. The latest schedule has loaded; review it before repeating this action.'),{snapshot:current})
  try{return await scheduleRequest(request,'/api/schedule',{method:'POST',headers:{'Content-Type':'application/json','If-Match':token},body:JSON.stringify({...payload,source:appointment.source||payload.source,edge:appointment.edge,originalDate:appointment.originalDate||base?.date||snapshot.date,action,sendEmail})})}
  catch(error){
   if(error.status!==409)throw Object.assign(error,{snapshot:current})
   await readLatest()
   if(attempt===2)throw Object.assign(Error('The schedule is busy. Your changes are kept; try Save again.'),{status:409,snapshot:current})
  }
 }
}

export function readScheduleDrafts(storage,key){
 try{const drafts=JSON.parse(storage.getItem(key)||'{}');return drafts&&typeof drafts==='object'&&!Array.isArray(drafts)?Object.fromEntries(Object.entries(drafts).filter(([,draft])=>draft?.form&&typeof draft.form==='object'&&!Array.isArray(draft.form))):{}}catch{return {}}
}
