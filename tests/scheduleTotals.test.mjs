import {test} from 'node:test'
import assert from 'node:assert/strict'
import {technicianBookedMinutes,bookedTimeLabel} from '../src/scheduleMath.js'
test('booked time includes travel and excludes lunch, leave and cancelled records',()=>{
 const appointments=[{technician:'Andrew',duration:90},{technicians:['Andrew','Allan'],duration:60},{technician:'Andrew',source:'lunch',duration:30},{technician:'Andrew',source:'leave',duration:240},{technician:'Andrew',cancelled:true,duration:60},{technician:'Allan',duration:45}]
 const travel=[{technician:'Andrew',source:'travel',duration:15},{technician:'Andrew',source:'travel',duration:30,cancelled:true}]
 assert.equal(technicianBookedMinutes(appointments,travel,'Andrew'),165)
 assert.equal(technicianBookedMinutes(appointments,travel,'Allan'),105)
 assert.equal(technicianBookedMinutes(appointments,travel,'Jackie'),0)
})
test('totals use complete bookings including early and late appointments',()=>{assert.equal(technicianBookedMinutes([{technician:'Andrew',duration:60,start:'05:00'},{technician:'Andrew',duration:90,start:'20:00'}],[],'Andrew'),150)})
test('time labels show decimal hours',()=>{assert.equal(bookedTimeLabel(0),'0h');assert.equal(bookedTimeLabel(60),'1h');assert.equal(bookedTimeLabel(165),'2.75h');assert.equal(bookedTimeLabel(15),'0.25h')})

test('6 hours 45 minutes displays as 6.75 hours',()=>assert.equal(bookedTimeLabel(405),'6.75h'))
