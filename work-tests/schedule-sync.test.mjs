import assert from 'node:assert/strict'
import {pendingSchedule} from '../src/scheduleSync.js'
const appointment={id:'a',date:'2027-02-01',start:'10:00',duration:60,technician:'Scott',technicians:['Scott'],timing:'flexible'}
const snapshot={date:appointment.date,appointments:[appointment],lunchBlocks:[],travelBlocks:[{id:'t',anchorId:'a',side:'before',technician:'Scott',duration:15,start:'09:45'}]}
const moved=pendingSchedule(snapshot,{...appointment,start:'11:00'})
assert.equal(moved.appointments[0].start,'11:00');assert.equal(moved.travelBlocks[0].start,'10:45')
assert.equal(snapshot.appointments[0].start,'10:00');assert.equal(snapshot.travelBlocks[0].start,'09:45')
assert.equal(pendingSchedule(snapshot,appointment,'cancel').travelBlocks.length,0)
assert.equal(pendingSchedule(snapshot,{...appointment,date:'2027-02-02'}).appointments.length,0)
assert.equal(pendingSchedule(snapshot,{...appointment,technicians:['Bala']}).travelBlocks.length,0)
assert.equal(pendingSchedule(snapshot,{...appointment,id:undefined}),snapshot)
console.log('Immediate move, travel snapping and untouched rollback snapshot checks passed.')
