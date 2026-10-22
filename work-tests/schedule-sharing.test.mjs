import test from 'node:test'
import assert from 'node:assert/strict'
import {webcrypto} from 'node:crypto'
import {mergeAppointment,saveSharedAppointment,readScheduleDrafts} from '../src/scheduleSync.js'
import worker,{verifyTicket,ScheduleRoom} from '../worker/schedule-live.js'

globalThis.crypto ||= webcrypto
const base={id:'a',version:1,date:'2026-10-22',technician:'Rick',technicians:['Rick'],client:'Sample',start:'09:00',duration:60,timing:'flexible',notes:'',bookingStatus:'confirmed'}
const snapshot=item=>({date:base.date,appointments:[item],lunchBlocks:[],travelBlocks:[]})
test('Independent edits on one appointment merge without dropping remote fields',()=>{
 const result=mergeAppointment(base,{...base,notes:'My note'},{...base,version:2,start:'10:00'})
 assert.deepEqual(result.conflicts,[]);assert.equal(result.value.notes,'My note');assert.equal(result.value.start,'10:00');assert.equal(result.value.version,2)
})
test('Same-field divergence requires a choice; matching edits do not',()=>{
 assert.deepEqual(mergeAppointment(base,{...base,notes:'Mine'},{...base,notes:'Theirs'}).conflicts,[{key:'notes',mine:'Mine',theirs:'Theirs'}])
 assert.equal(mergeAppointment(base,{...base,notes:'Same'},{...base,notes:'Same'}).conflicts.length,0)
 assert.equal(mergeAppointment(base,base,undefined).deleted,true)
 assert.equal(mergeAppointment(base,{...base,notes:'Draft'},{...base,cancelled:true}).deleted,true)
})
test('Technician order alone is not a conflicting change',()=>{
 const old={...base,technicians:['Rick','Scott']}
 assert.equal(mergeAppointment(old,{...old,technicians:['Scott','Rick'],notes:'Mine'},{...old,notes:''}).conflicts.length,0)
})
test('Explicit rejected save refreshes and retries against the current token',async()=>{
 const calls=[],remote={...base,version:2,start:'10:00'}
 const result=await saveSharedAppointment(async(path,options)=>{
  calls.push({path,options})
  if(calls.length===1)throw Object.assign(Error('Conflict'),{status:409})
  if(calls.length===2)return {data:snapshot(remote),etag:'new'}
  return {data:{appointment:JSON.parse(options.body)},etag:'saved'}
 },{appointment:{...base,notes:'My note',_base:base,_draftKey:'private'},base,snapshot:snapshot(base),etag:'old'})
 assert.equal(calls.length,3);assert.equal(calls[2].options.headers['If-Match'],'new')
 assert.equal(result.data.appointment.start,'10:00');assert.equal(result.data.appointment.notes,'My note');assert.equal(result.data.appointment._base,undefined)
})
test('Network failure is never retried because the write may already have committed',async()=>{
 let calls=0
 await assert.rejects(saveSharedAppointment(async()=>{calls++;throw Error('Offline')},{appointment:base,base,snapshot:snapshot(base),etag:'old'}),/Offline/)
 assert.equal(calls,1)
})
test('A remotely moved booking is found before deciding that it was deleted',async()=>{
 let saved
 await saveSharedAppointment(async(path,options)=>{if(path.includes('?'))return {data:{...snapshot(undefined),appointments:[],editingAppointment:{...base,date:'2026-10-23',version:2}},etag:'new'};saved=JSON.parse(options.body);return {}},{appointment:{...base,notes:'Kept after move'},base,snapshot:{...snapshot(base),appointments:[]},etag:'old'})
 assert.equal(saved.date,'2026-10-23');assert.equal(saved.notes,'Kept after move')
})
test('A conflicting second edit is kept instead of being posted over a remote edit',async()=>{
 let calls=0
 await assert.rejects(saveSharedAppointment(async()=>{calls++;if(calls===1)throw Object.assign(Error('Conflict'),{status:409});return {data:snapshot({...base,version:2,notes:'Remote'}),etag:'new'}},{appointment:{...base,notes:'Local'},base,snapshot:snapshot(base),etag:'old'}),error=>error.conflict.conflicts[0].mine==='Local')
 assert.equal(calls,2)
})
test('Automatic retry is bounded during repeated contention',async()=>{
 let writes=0
 await assert.rejects(saveSharedAppointment(async(path)=>{if(path.includes('?'))return {data:snapshot(base),etag:'new'};writes++;throw Object.assign(Error('Busy'),{status:409})},{appointment:base,base,snapshot:snapshot(base),etag:'old'}),/schedule is busy/)
 assert.equal(writes,3)
})
test('Resize edge and lunch source/date survive serialization',async()=>{
 let body
 await saveSharedAppointment(async(_path,options)=>{body=JSON.parse(options.body);return {}},{appointment:{...base,source:'lunch',edge:'end',originalDate:'2026-10-21'},base,snapshot:snapshot(base),etag:'old',action:'resize'})
 assert.equal(body.edge,'end');assert.equal(body.originalDate,'2026-10-21');assert.equal(body.source,'lunch')
})
test('Multiple drafts survive parsing and corrupt storage recovers safely',()=>{
 const drafts={a:{form:base},b:{form:{...base,client:'Second'}}}
 assert.deepEqual(readScheduleDrafts({getItem:()=>JSON.stringify(drafts)},'key'),drafts)
 assert.deepEqual(readScheduleDrafts({getItem:()=>'{broken'},'key'),{})
 assert.deepEqual(readScheduleDrafts({getItem:()=>{throw Error('Blocked')}},'key'),{})
})
const secret='test-only-secret-value-at-least-32-characters'
async function mac(text){const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(secret),{name:'HMAC',hash:'SHA-256'},false,['sign']);return Buffer.from(await crypto.subtle.sign('HMAC',key,new TextEncoder().encode(text))).toString('hex')}
async function ticket(exp=Math.floor(Date.now()/1000)+300){const payload=Buffer.from(JSON.stringify({room:'schedule',exp})).toString('base64url');return payload+'.'+await mac(payload)}
test('Live tickets require a valid signature, room and short expiry',async()=>{
 assert.ok(await verifyTicket(secret,await ticket()))
 assert.equal(await verifyTicket(secret,await ticket(1)),null)
 assert.equal(await verifyTicket(secret,(await ticket())+'bad'),null)
 assert.equal(await verifyTicket(secret,await ticket(Math.floor(Date.now()/1000)+1000)),null)
})
test('Worker protects the socket origin and publish endpoint; assets still work',async()=>{
 let forwarded=0
 const env={SCHEDULE_LIVE_SECRET:secret,ASSETS:{fetch:()=>new Response('asset')},SCHEDULE_ROOM:{idFromName:name=>name,get:()=>({fetch:()=>{forwarded++;return new Response(null,{status:204})}})}}
 assert.equal(await (await worker.fetch(new Request('https://test/settings'),env)).text(),'asset')
 assert.equal((await worker.fetch(new Request('https://test/schedule-live',{headers:{Upgrade:'websocket',Origin:'https://evil'}}),env)).status,403)
 assert.equal((await worker.fetch(new Request('https://test/__schedule-publish',{method:'POST',body:'{}'}),env)).status,401)
 const body='{"type":"schedule-changed"}',stamp=String(Math.floor(Date.now()/1000))
 assert.equal((await worker.fetch(new Request('https://test/__schedule-publish',{method:'POST',body,headers:{'X-Schedule-Time':stamp,'X-Schedule-Signature':await mac(stamp+'.'+body)}}),env)).status,204)
 assert.equal(forwarded,1)
})
test('Shared room broadcasts invalidations only and rejects client writes',async()=>{
 const messages=[],closed=[],socket={send:value=>messages.push(value),close:(...args)=>closed.push(args),deserializeAttachment:()=>({expiry:1})}
 const room=new ScheduleRoom({getWebSockets:()=>[socket],storage:{setAlarm:async()=>{}}})
 await room.fetch(new Request('https://room/publish',{method:'POST'}));assert.deepEqual(messages,['{"type":"schedule-changed"}'])
 room.webSocketMessage(socket,'business-data');assert.equal(closed[0][0],1008)
 await room.alarm();assert.equal(closed[1][1],'Renew connection')
})
