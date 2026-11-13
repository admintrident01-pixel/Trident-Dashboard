import {test} from 'node:test'
import assert from 'node:assert/strict'
import {assignedTechs,reassignTechnician,blockPosition,moveAppointment,rangeFor,scrollDayLayout,scheduleScale,pointerMinute} from '../src/scheduleMath.js'
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

test('scrolling a full day preserves normal workday scale and quarter-hour placement',()=>{
 const normal={start:450,end:960},full={start:0,end:1440}
 for(const viewport of [320,600,900]){
  const layout=scrollDayLayout(viewport,24,normal)
  const normalHourHeight=60/(normal.end-normal.start)*(viewport-24)
  const late=blockPosition({...booking,start:'19:00'},full)
  assert.ok(Math.abs(late.width/100*layout.trackHeight-normalHourHeight)<1e-9)
  assert.ok(Math.abs(layout.scrollTop/layout.trackHeight*1440-450)<1e-9)
  const rect={top:-layout.scrollTop+24,height:layout.trackHeight}
  assert.equal(pointerMinute(full,rect,{y:rect.top+19.25/24*rect.height},true),1155)
 }
})
test('vertical scale enlarges the time axis without changing the time position',()=>{
 const normal={start:480,end:960}
 const base=scrollDayLayout(600,24,normal),double=scrollDayLayout(600,24,normal,2)
 assert.equal(double.trackHeight,base.trackHeight*2)
 assert.equal(double.scrollTop,base.scrollTop*2)
 assert.equal(scheduleScale(99),3)
 assert.equal(scheduleScale(.1),.4)
 assert.equal(scheduleScale('bad'),1)
})
test('dragging a shared booking replaces only the dragged technician and avoids duplicates',()=>{
 const team={...booking,technician:'Scott',technicians:['Scott','Bala']}
 assert.deepEqual(assignedTechs(reassignTechnician(team,'Bala','Rick')),['Scott','Rick'])
 assert.deepEqual(assignedTechs(reassignTechnician(team,'Scott','Bala')),['Bala'])
 assert.deepEqual(assignedTechs({technician:'Scott'}),['Scott'])
 assert.deepEqual(assignedTechs({technician:'',technicians:[]}),[])
})
