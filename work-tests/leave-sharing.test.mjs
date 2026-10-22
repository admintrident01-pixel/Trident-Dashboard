import test from 'node:test'
import assert from 'node:assert/strict'
import {leaveOperationId,mergeLeaveRequest,refreshLeaveRequests,saveLeaveOperation} from '../src/leaveSync.js'

test('An uncertain response retries exactly the same submission identity and body',async()=>{
 const payload={operationId:leaveOperationId(),technician:'Synthetic staff',reason:'Unfinished notes'},calls=[]
 const result=await saveLeaveOperation(async(path,options)=>{calls.push({path,options});if(calls.length===1)throw Error('Response lost after commit');return {data:{request:{id:'single'}}}},'/api/leave',payload)
 assert.equal(result.data.request.id,'single');assert.equal(calls.length,2);assert.equal(calls[0].options.body,calls[1].options.body);assert.equal(calls[0].options.headers['If-Match'],undefined);assert.equal(payload.reason,'Unfinished notes')
})
test('Decision retries keep their original per-leave version, notes and identity',async()=>{
 const payload={operationId:leaveOperationId(),id:'leave',revision:3,status:'Declined',decisionNotes:'Keep these notes'},bodies=[]
 await saveLeaveOperation(async(_path,options)=>{bodies.push(JSON.parse(options.body));if(bodies.length===1)throw Object.assign(Error('Service timeout'),{status:503});return {}},'/api/leave-decision',payload)
 assert.deepEqual(bodies,[payload,payload])
})
test('A same-request revision conflict is shown for review without automatic approval retry',async()=>{
 let calls=0
 await assert.rejects(saveLeaveOperation(async()=>{calls++;throw Object.assign(Error('Leave request changed'),{status:409})},'/api/leave-decision',{operationId:leaveOperationId()}),/Leave request changed/)
 assert.equal(calls,1)
})
test('Connection retries are bounded and preserve the editable source object',async()=>{
 let calls=0;const payload={operationId:leaveOperationId(),reason:'Retain my form'}
 await assert.rejects(saveLeaveOperation(async()=>{calls++;throw Error('Offline')},'/api/leave',payload),/Offline/)
 assert.equal(calls,2);assert.equal(payload.reason,'Retain my form')
})
test('Replayed success replaces its existing row while preserving other saved requests',()=>{
 const data={technicians:[{name:'Staff'}],requests:[{id:'a',revision:1},{id:'b',revision:1}]},merged=mergeLeaveRequest(data,{id:'a',revision:2})
 assert.equal(merged.requests.length,2);assert.equal(merged.requests.find(r=>r.id==='a').revision,2);assert.deepEqual(merged.requests.find(r=>r.id==='b'),{id:'b',revision:1});assert.equal(data.requests[0].revision,1)
})
test('A delayed manual refresh follows the current selection and keeps its decision notes',async()=>{
 let selected={id:'a',revision:1},notes='Notes for A',finish,loaded
 const pending=new Promise(resolve=>{finish=resolve})
 const refreshing=refreshLeaveRequests(()=>pending,{onData:value=>{loaded=value},setSelected:update=>{selected=update(selected)}})
 selected={id:'b',revision:1};notes='New notes for B'
 finish({data:{requests:[{id:'a',revision:2},{id:'b',revision:3}]}})
 assert.equal(await refreshing,true);assert.deepEqual(selected,{id:'b',revision:3});assert.equal(notes,'New notes for B');assert.equal(loaded.requests.length,2)
})
test('A delayed manual refresh cannot reopen a closed review or overwrite a newer save',async()=>{
 let selected={id:'a'},finish,writes=0
 const pending=new Promise(resolve=>{finish=resolve})
 const refreshing=refreshLeaveRequests(()=>pending,{onData:()=>{writes++},setSelected:update=>{selected=update(selected)}})
 selected=null;finish({data:{requests:[{id:'a',revision:2}]}});await refreshing
 assert.equal(selected,null);assert.equal(writes,1)
 assert.equal(await refreshLeaveRequests(async()=>({data:{requests:[]}}),{accept:()=>false,onData:()=>{writes++},setSelected:()=>{throw Error('Stale response changed selection')}}),false)
 assert.equal(writes,1)
})
