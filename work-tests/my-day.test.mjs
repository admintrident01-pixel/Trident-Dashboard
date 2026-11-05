import test from 'node:test'
import assert from 'node:assert/strict'
import {myDayPilot,recordedMinutes,shiftDay,mapsLink,nzTime} from '../src/myDayModel.js'
import {canAccessPage} from '../src/navigation.js'
test('pilot gates navigation regardless of admin role',()=>{
 assert.equal(myDayPilot({email:'bala@trice.nz'}),true)
 assert.equal(canAccessPage('my-day',{email:'bala@trice.nz',role:'admin'}),true)
 for(const email of ['other@trice.nz','bala@trice.nz.evil',''])assert.equal(canAccessPage('my-day',{email,role:'admin'}),false)
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
