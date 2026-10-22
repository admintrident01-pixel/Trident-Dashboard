export const leaveOperationId=()=>globalThis.crypto?.randomUUID?.()||`leave_${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`

export function mergeLeaveRequest(data,entry){
 if(!data)return data
 return {...data,requests:[...data.requests.filter(item=>item.id!==entry.id),entry]}
}

export async function refreshLeaveRequests(request,{accept=()=>true,onData,setSelected}){
 const result=await request('/api/leave',{cache:'no-store'})
 if(!accept())return false
 onData(result.data)
 // Selection may change while the read is in flight. Match the current
 // selection, so notes typed for a different request stay with that request.
 setSelected(current=>current?result.data.requests.find(item=>item.id===current.id)||null:null)
 return true
}

// The durable operation identity makes retrying an uncertain response safe.
// Keep the exact body, including the original per-request decision revision.
export async function saveLeaveOperation(request,path,payload,onRetry=()=>{}){
 if(!payload.operationId)throw Error('This leave save has no identity. Reopen the leave form and try again.')
 const body=JSON.stringify(payload)
 for(let attempt=0;attempt<2;attempt++){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),90000)
  try{return await request(path,{method:'POST',headers:{'Content-Type':'application/json'},body,signal:controller.signal})}
  catch(error){
   if(attempt||error.status&&error.status<500)throw error
   onRetry()
  }finally{clearTimeout(timer)}
 }
}
