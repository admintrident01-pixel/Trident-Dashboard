import {test} from 'node:test'
import assert from 'node:assert/strict'
import {appointmentTimeForm,updateAppointmentTime,appointmentTimeError} from '../src/appointmentTime.js'
import {moveAppointment} from '../src/scheduleMath.js'
const booking={start:'09:00',duration:60,timing:'fixed'}
test('start-based duration changes preserve the start and calculate the end',()=>{
 const original=appointmentTimeForm(booking),next=updateAppointmentTime(original,'duration',90)
 assert.equal(next.start,'09:00');assert.equal(next.endTime,'10:30');assert.equal(original.duration,60)
})
test('end-based editing keeps the end when duration changes',()=>{
 let form=updateAppointmentTime(appointmentTimeForm(booking),'timeBasis','end')
 form=updateAppointmentTime(form,'endTime','15:00');assert.equal(form.start,'14:00')
 form=updateAppointmentTime(form,'duration',90);assert.equal(form.start,'13:30');assert.equal(form.endTime,'15:00');assert.equal(appointmentTimeError(form),'')
})
test('switching time basis keeps the current appointment times',()=>{
 const form=appointmentTimeForm(booking);assert.equal(updateAppointmentTime(form,'timeBasis','end').start,form.start)
 assert.equal(updateAppointmentTime(form,'timeBasis','end').endTime,'10:00')
 assert.equal(appointmentTimeForm({...booking,timeBasis:'end'}).timeBasis,'end')
})
test('midnight finish is supported and crossing the day is rejected',()=>{
 const form=appointmentTimeForm({...booking,start:'23:00'});assert.equal(form.endTime,'00:00');assert.equal(appointmentTimeError(form),'')
 assert.match(appointmentTimeError(updateAppointmentTime(form,'duration',90)),/midnight/)
 const end=updateAppointmentTime({...form,timeBasis:'end'},'endTime','00:30');assert.match(appointmentTimeError(end),/same day/)
})
test('bottom-edge resizing of fixed and flexible bookings always preserves start',()=>{
 for(const timing of ['fixed','flexible'])for(const delta of [-10000,-30,30,10000]){
  const result=moveAppointment({...booking,timing},delta,'end');assert.equal(result.start,booking.start);assert.ok(result.duration>=15);assert.ok(result.duration<=900)
 }
})
