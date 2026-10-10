import {test} from 'node:test'
import assert from 'node:assert/strict'
import {assignedTechs,reassignTechnician,blockPosition,moveAppointment,rangeFor} from '../src/scheduleMath.js'
const booking={start:'09:00',duration:60,timing:'flexible'}
test('block width follows booked duration',()=>{
 assert.deepEqual(blockPosition(booking,{start:480,end:1080}),{left:10,width:10})
 assert.equal(blockPosition({...booking,duration:90},{start:480,end:1080}).width,15)
})
test('drag snaps to quarter hours and stays inside the day',()=>{
 assert.equal(moveAppointment(booking,23,'move').start,'09:30')
 assert.equal(moveAppointment(booking,-9999,'move').start,'00:00')
 assert.equal(moveAppointment(booking,9999,'move').start,'23:00')
})
test('fixed booking start does not move while dragging',()=>{
 assert.equal(moveAppointment({...booking,timing:'fixed'},120,'move').start,'09:00')
})
test('resizing preserves valid durations and opposite edge',()=>{
 assert.equal(moveAppointment(booking,30,'end').duration,90)
 const resized=moveAppointment(booking,30,'start')
 assert.equal(resized.start,'09:30');assert.equal(resized.duration,30)
 assert.equal(moveAppointment(booking,9999,'start').duration,15)
})
test('hours expand to show early and late appointments',()=>{
 assert.deepEqual(rangeFor([{...booking,start:'07:15'},{...booking,start:'18:30'}]),{start:420,end:1200})
 assert.deepEqual(rangeFor([],true),{start:0,end:1440})
})

test('normal workday uses exact configured times without expanding for bookings',()=>{
 const workHours={start:'07:30',finish:'16:15'}
 const bookings=[{...booking,start:'06:00'},{...booking,start:'18:30'}]
 assert.deepEqual(rangeFor(bookings,'normal',workHours),{start:450,end:975})
 assert.deepEqual(rangeFor(bookings,'fit',workHours),{start:360,end:1200})
 assert.deepEqual(rangeFor(bookings,'full',workHours),{start:0,end:1440})
})
test('normal workday clips partially visible bookings and hides out-of-hours blocks',()=>{
 const range={start:480,end:960}
 assert.deepEqual(blockPosition({...booking,start:'07:30',duration:60},range),{left:0,width:6.25})
 assert.equal(blockPosition({...booking,start:'18:00'},range).width,0)
})
test('dragging a shared booking replaces only the dragged technician and avoids duplicates',()=>{
 const team={...booking,technician:'Scott',technicians:['Scott','Bala']}
 assert.deepEqual(assignedTechs(reassignTechnician(team,'Bala','Rick')),['Scott','Rick'])
 assert.deepEqual(assignedTechs(reassignTechnician(team,'Scott','Bala')),['Bala'])
 assert.deepEqual(assignedTechs({technician:'Scott'}),['Scott'])
 assert.deepEqual(assignedTechs({technician:'',technicians:[]}),[])
})