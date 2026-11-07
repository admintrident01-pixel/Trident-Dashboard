import test from 'node:test'
import assert from 'node:assert/strict'
import {workshopLocationForm} from '../src/scheduleWorkshop.js'
import {mergeAppointment,appointmentChanged,saveSharedAppointment} from '../src/scheduleSync.js'

const base={id:'example',version:1,date:'2026-11-09',client:'Example',address:'12 Client Road',technicians:['Alex'],start:'10:00',duration:60,bookingControlsVersion:1,bookingStatus:'action-needed'}
test('Workshop checkbox uses configured address and restores the unfinished client address',()=>{
 const workshop=workshopLocationForm(base,true,'255 Workshop Road')
 assert.equal(workshop.address,'255 Workshop Road');assert.equal(workshop.includeWorkshopTravel,false)
 assert.equal(workshopLocationForm(workshop,false,'255 Workshop Road').address,base.address)
 assert.equal(base.address,'12 Client Road')
})
test('Workshop changes merge independent edits and preserve policy on other updates',()=>{
 const mine=workshopLocationForm(base,true,'Workshop'),remote={...base,version:2,notes:'Remote note'}
 const merged=mergeAppointment(base,mine,remote)
 assert.deepEqual(merged.conflicts,[]);assert.equal(merged.value.notes,'Remote note')
 assert.equal(merged.value.workshopLocation,true);assert.equal(merged.value.address,'Workshop')
 assert.equal(appointmentChanged(base,mine),true)
 assert.equal(appointmentChanged(base,{...base,workshopLocation:false,includeWorkshopTravel:false}),false)
})
test('Unsaved original address stays private to the browser',async()=>{
 let payload
 await saveSharedAppointment(async(_path,options)=>{payload=JSON.parse(options.body);return {}},{appointment:workshopLocationForm({...base,id:undefined},true,'Workshop'),snapshot:{date:base.date,appointments:[]},etag:'local'})
 assert.equal(payload._clientAddress,undefined);assert.equal(payload.workshopLocation,true)
})
