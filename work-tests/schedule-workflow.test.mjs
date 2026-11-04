import test from 'node:test'
import assert from 'node:assert/strict'
import {selectBlocks} from '../src/scheduleModifiers.js'
import {contactKinds,contactMarked,withContactMark} from '../src/scheduleContact.js'
import {defaultLeaveTechnician} from '../src/leaveDefaults.js'
import {mergeAppointment} from '../src/scheduleSync.js'
import {wholeRoute} from '../src/scheduleRoute.js'

test('Ctrl and Command toggle selections; Shift adds an inclusive range',()=>{
 const order=['a','b','c','d']
 assert.deepEqual(selectBlocks(['a'],'c',{ctrlKey:true},'a',order),['a','c'])
 assert.deepEqual(selectBlocks(['a','c'],'a',{metaKey:true},'a',order),['c'])
 assert.deepEqual(selectBlocks(['a'],'d',{shiftKey:true},'b',order),['a','b','c','d'])
 assert.deepEqual(selectBlocks(['d'],'b',{shiftKey:true},'d',order),['d','b','c'])
 assert.deepEqual(selectBlocks(['a','b'],'c',{},'a',order),['c'])
})
test('Existing Left notes light the right icon and explicit markers override them',()=>{
 const row={notes:'Keep this\nLeft Vmail\nLeft Text\nLeft Email'}
 assert.ok(contactKinds.every(kind=>contactMarked(row,kind)))
 const changed=withContactMark(row,'text')
 assert.equal(changed.notes,row.notes);assert.equal(contactMarked(changed,contactKinds[1]),false)
 assert.equal(contactMarked(withContactMark(changed,'text'),contactKinds[1]),true)
 assert.equal(row.contactStatus,undefined)
})
test('Contact edits merge with independent remote changes and detect conflicts',()=>{
 const base={id:'a',version:1,timing:'flexible',bookingStatus:'action-needed',bookingControlsVersion:1,technicians:['Alex'],notes:'old',contactStatus:{email:false}}
 const mine=withContactMark(base,'email'),latest={...base,version:2,notes:'New remote note'}
 const merged=mergeAppointment(base,mine,latest)
 assert.equal(merged.value.contactStatus.email,true);assert.equal(merged.value.notes,latest.notes);assert.equal(merged.conflicts.length,0)
 assert.equal(mergeAppointment(base,mine,{...base,contactStatus:{email:false,text:true}}).conflicts[0].key,'contactStatus')
})
test('Every signed-in admin defaults to their own staff identity',()=>{
 const staff=[{name:'First'},{name:'Admin A'},{name:'Admin B'}]
 assert.equal(defaultLeaveTechnician(staff,'Admin A'),'Admin A')
 assert.equal(defaultLeaveTechnician(staff,'Admin B'),'Admin B')
 assert.equal(defaultLeaveTechnician([],''),'')
})
test('Notes never enter the Google Maps route',()=>{
 const row={id:'a',type:'Repair',technicians:['Alex'],start:'09:00',address:'1 Road'}
 const note={...row,id:'n',type:'Notes',start:'10:00',address:''}
 assert.deepEqual(wholeRoute([row,note],'Alex','Depot').bookings,[row])
})
