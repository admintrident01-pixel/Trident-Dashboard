import {test} from 'node:test'
import assert from 'node:assert/strict'
import {bookingControls,withBookingStatus,isBooked} from '../src/scheduleBooking.js'
import {mergeAppointment,appointmentChanged} from '../src/scheduleSync.js'
const legacy={id:'a',timing:'flexible',bookingStatus:'high-priority',date:'2026-10-21',technician:'Alex',start:'11:00',duration:45,notes:'Keep'}
test('legacy interpretation retains details and does not mutate source',()=>{
 const before=structuredClone(legacy),mapped=bookingControls(legacy)
 assert.equal(mapped.bookingStatus,'action-needed');assert.equal(mapped.urgency,'high');assert.deepEqual(legacy,before)
 assert.equal(appointmentChanged(legacy,mapped),false)
})
test('approved conflict exception and no guesses for a new conflict',()=>{
 const conflict={...legacy,id:'ba7a4325-00a6-46a1-8ec5-82549ca1f3df',timing:'fixed',bookingStatus:'option'}
 assert.equal(isBooked(conflict),false);assert.equal(bookingControls(conflict).timing,'flexible')
 assert.throws(()=>bookingControls({...conflict,id:'different'}),/Fixed and Optional/)
})
test('booking and urgency edits from different users merge independently',()=>{
 const base=bookingControls(legacy),mine=withBookingStatus(base,'confirmed'),latest={...base,urgency:'low',version:2}
 const result=mergeAppointment(base,mine,latest)
 assert.deepEqual(result.conflicts,[]);assert.equal(result.value.bookingStatus,'confirmed');assert.equal(result.value.urgency,'low');assert.equal(result.value.timing,'fixed')
 assert.equal(mergeAppointment(base,{...base,urgency:'low'},{...base,notes:'Remote note'}).value.notes,'Remote note')
})
test('different concurrent booking decisions require a choice and drafts retain urgency',()=>{
 const base=bookingControls(legacy),result=mergeAppointment(base,withBookingStatus(base,'confirmed'),withBookingStatus(base,'option'))
 assert.ok(result.conflicts.some(c=>c.key==='bookingStatus'))
 assert.equal(withBookingStatus(legacy,'option').urgency,'high')
})
