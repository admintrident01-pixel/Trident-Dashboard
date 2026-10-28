import {test} from 'node:test'
import assert from 'node:assert/strict'
import {calendarPeriods,quickWeekDays,scheduleAppointments} from '../src/scheduleCalendar.js'
import {blockPosition} from '../src/scheduleMath.js'
test('quick weekdays cross month/year boundaries and remain Monday to Friday on weekends',()=>{
 assert.deepEqual(quickWeekDays('2026-10-31'),['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30'])
 assert.deepEqual(quickWeekDays('2027-01-01'),['2026-12-28','2026-12-29','2026-12-30','2026-12-31','2027-01-01'])
 assert.deepEqual(quickWeekDays('2026-11-01'),quickWeekDays('2026-10-28'))
})
test('lunch and holidays produce background periods without changing stored appointments',()=>{
 const snapshot={date:'2026-10-28',lunchShading:{start:'13:15',duration:30},publicHolidays:[{date:'2026-10-28',name:'Example holiday'}],appointments:[{id:'old',source:'lunch'},{id:'old-type',type:'Lunch'},{id:'booking',start:'13:15',duration:60}]}
 const before=structuredClone(snapshot),periods=calendarPeriods(snapshot)
 assert.deepEqual(periods.map(p=>p.kind),['holiday','lunch'])
 assert.deepEqual(blockPosition(periods[0],{start:480,end:960}),{left:0,width:100})
 assert.equal(periods[1].start,'13:15');assert.equal(periods[1].duration,30)
 assert.deepEqual(scheduleAppointments(snapshot).map(a=>a.id),['booking']);assert.deepEqual(snapshot,before)
})
test('unconfigured or other-day holidays never shade the current day',()=>{
 assert.deepEqual(calendarPeriods(null),[])
 assert.equal(calendarPeriods({date:'2026-10-29',publicHolidays:[{date:'2026-10-28',name:'Example'}]})[0].kind,'lunch')
 assert.equal(calendarPeriods({lunchStart:'23:30'})[0].label,'Lunch 23:30–24:00')
})
