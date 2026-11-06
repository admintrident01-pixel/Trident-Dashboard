import test from 'node:test'
import assert from 'node:assert/strict'
import {myDayEnabled,recordedMinutes,shiftDay,mapsLink,nzTime} from '../src/myDayModel.js'
import {canAccessPage,loadPage,homePage} from '../src/navigation.js'
test('all signed-in members can open My day while privileged pages stay restricted',()=>{
 assert.equal(myDayEnabled({email:'tech@trice.nz',role:'tech'}),true)
 assert.equal(canAccessPage('my-day',{email:'bala@trice.nz',role:'admin'}),true)
 assert.equal(canAccessPage('my-day',{email:'other@trice.nz',role:'tech'}),true)
 assert.equal(canAccessPage('settings',{email:'other@trice.nz',role:'tech'}),false)
 for(const session of [null,{email:'',role:'admin'},{email:'other@trice.nz',role:'guest'}])assert.equal(canAccessPage('my-day',session),false)
})
test('My day is the default home while the existing workspace stays reachable',()=>{
 const previous=global.window
 try{for(const hash of ['','#home','#unknown']){global.window={location:{hash}};assert.equal(loadPage(),'my-day')}
 global.window={location:{hash:'#workspace'}};assert.equal(loadPage(),'workspace')
 }finally{global.window=previous}
})
test('Scott stays on the existing home with his other permissions unchanged',()=>{
 for(const session of [{email:' SCOTT@TRICE.NZ ',role:'admin'},{email:'other@trice.nz',technician:' Scott Yearbury ',role:'tech'}]){
  assert.equal(canAccessPage('my-day',session),false)
  assert.equal(homePage(session),'workspace')
  assert.equal(canAccessPage('workspace',session),true)
  assert.equal(canAccessPage('schedule',session),true)
 }
 assert.equal(canAccessPage('settings',{email:'scott@trice.nz',role:'admin'}),true)
 assert.equal(homePage({email:'other@trice.nz',role:'tech'}),'my-day')
})
test('recorded time sums multiple periods and one active clock without planned hours',()=>{
 const now=Date.parse('2026-11-05T01:00:00Z')
 assert.equal(recordedMinutes({a:{sessions:[{start:'2026-11-05T00:00:00Z',end:'2026-11-05T00:30:00Z'},{start:'2026-11-05T00:45:00Z',end:null}]},b:undefined},now),45)
 assert.equal(recordedMinutes({},now),0)
})
test('date navigation and maps link do not require paid API',()=>{
 assert.equal(shiftDay('2026-12-31',1),'2027-01-01')
 assert.equal(nzTime('2026-11-05T00:00:00Z'),'13:00')
 assert.equal(mapsLink(''),null)
 assert.equal(mapsLink('12 Example Rd & Lane'),'https://www.google.com/maps/search/?api=1&query=12%20Example%20Rd%20%26%20Lane')
})
