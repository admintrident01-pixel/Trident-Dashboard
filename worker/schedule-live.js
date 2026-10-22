/* global WebSocketPair */
const encoder=new TextEncoder()
async function signature(secret,message){
 const key=await crypto.subtle.importKey('raw',encoder.encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign'])
 return Array.from(new Uint8Array(await crypto.subtle.sign('HMAC',key,encoder.encode(message))),byte=>byte.toString(16).padStart(2,'0')).join('')
}
function same(a,b){if(typeof a!=='string'||typeof b!=='string'||a.length!==b.length)return false;let difference=0;for(let i=0;i<a.length;i++)difference|=a.charCodeAt(i)^b.charCodeAt(i);return difference===0}
export async function verifyTicket(secret,ticket,now=Date.now()){
 try{
  const [payload,mac,...extra]=ticket.split('.')
  if(extra.length||!same(mac,await signature(secret,payload)))return null
  const value=JSON.parse(atob(payload.replace(/-/g,'+').replace(/_/g,'/')))
  return value.room==='schedule'&&Number.isInteger(value.exp)&&value.exp>now/1000&&value.exp<=now/1000+310?value:null
 }catch{return null}
}
export default {
 async fetch(request,env){
  const url=new URL(request.url),secret=env.SCHEDULE_LIVE_SECRET
  if(!['/schedule-live','/__schedule-publish'].includes(url.pathname))return env.ASSETS.fetch(request)
  if(!secret||secret.length<32)return new Response('Live updates unavailable',{status:503})
  const room=env.SCHEDULE_ROOM.get(env.SCHEDULE_ROOM.idFromName('trident-schedule-v1'))
  if(url.pathname==='/__schedule-publish'){
   if(request.method!=='POST')return new Response(null,{status:405})
   const stamp=request.headers.get('X-Schedule-Time'),mac=request.headers.get('X-Schedule-Signature')
   if(!/^\d+$/.test(stamp||'')||!/^[a-f0-9]{64}$/.test(mac||'')||Math.abs(Date.now()/1000-Number(stamp))>30)return new Response(null,{status:401})
   if(Number(request.headers.get('Content-Length')||0)>128)return new Response(null,{status:413})
   const body=await request.text()
   if(body.length>128||!same(mac,await signature(secret,stamp+'.'+body)))return new Response(null,{status:401})
   if(body!=='{"type":"schedule-changed"}')return new Response(null,{status:400})
   return room.fetch(new Request('https://room/publish',{method:'POST'}))
  }
  if(request.method!=='GET'||request.headers.get('Upgrade')?.toLowerCase()!=='websocket')return new Response(null,{status:426})
  if(request.headers.get('Origin')!==url.origin)return new Response(null,{status:403})
  const protocols=(request.headers.get('Sec-WebSocket-Protocol')||'').split(',').map(value=>value.trim())
  const token=protocols.find(value=>value.startsWith('ticket.'))?.slice(7)
  const ticket=token&&protocols.includes('trident-schedule')?await verifyTicket(secret,token):null
  if(!ticket)return new Response(null,{status:401})
  const headers=new Headers(request.headers);headers.set('X-Ticket-Expiry',String(ticket.exp))
  return room.fetch(new Request('https://room/connect',{headers}))
 }
}

export class ScheduleRoom {
 constructor(ctx){this.ctx=ctx}
 async fetch(request){
  if(new URL(request.url).pathname==='/publish'){
   for(const socket of this.ctx.getWebSockets())try{socket.send('{"type":"schedule-changed"}')}catch{socket.close(1011,'Reconnect')}
   return new Response(null,{status:204})
  }
  const expiry=Number(request.headers.get('X-Ticket-Expiry'))
  if(!expiry||expiry<=Date.now()/1000)return new Response(null,{status:401})
  const pair=new WebSocketPair(),[client,server]=Object.values(pair)
  this.ctx.acceptWebSocket(server);server.serializeAttachment({expiry})
  const alarm=await this.ctx.storage.getAlarm();if(!alarm)await this.ctx.storage.setAlarm(Date.now()+30000)
  return new Response(null,{status:101,webSocket:client,headers:{'Sec-WebSocket-Protocol':'trident-schedule'}})
 }
 webSocketMessage(socket){socket.close(1008,'Read-only connection')}
 webSocketClose(socket){socket.close(1000,'')}
 webSocketError(socket){socket.close(1011,'Reconnect')}
 async alarm(){
  let remaining=false
  for(const socket of this.ctx.getWebSockets()){
   if((socket.deserializeAttachment()?.expiry||0)<=Date.now()/1000)socket.close(1000,'Renew connection')
   else remaining=true
  }
  if(remaining)await this.ctx.storage.setAlarm(Date.now()+30000)
 }
}
