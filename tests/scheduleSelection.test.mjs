import {test} from 'node:test'
import assert from 'node:assert/strict'
import {linkedSelection,selectionDraft,selectionMoveError,intersectingIds} from '../src/scheduleSelection.js'
const a={id:'a',start:'09:00',duration:60,timing:'flexible',client:'A'},b={...a,id:'b',start:'11:00'}
test('selection moves preserve spacing and duration without changing originals',()=>{
 const rows=selectionDraft([a,b],45)
 assert.deepEqual(rows.map(x=>x.start),['09:45','11:45']);assert.equal(rows[0].duration,60);assert.equal(a.start,'09:00')
})
test('checked bookings include only their own travel, not unchecked neighbours',()=>{
 const travel={...a,id:'t',source:'travel',anchorId:'a',linked:true}
 assert.deepEqual(linkedSelection(['t'],[a,b,travel],[{leftId:'a',rightId:'b',linked:true}]).map(x=>x.id),['t'])
 assert.deepEqual(linkedSelection(['a'],[a,b,travel],[{leftId:'a',rightId:'b',linked:true}]).map(x=>x.id),['a','t'])
})
test('fixed appointments, leave and crossing midnight block the whole move',()=>{
 assert.match(selectionMoveError([a,{...b,timing:'fixed'}],15),/booked/)
 assert.match(selectionMoveError([{...a,source:'leave'}],15),/leave/)
 assert.match(selectionMoveError([a],-600),/day/)
 assert.equal(selectionMoveError([a,b],15),'')
})
test('marquee selects intersecting blocks across columns without selecting touching boundaries',()=>{
 const rows=[{id:'a',left:0,right:50,top:0,bottom:50},{id:'b',left:60,right:100,top:0,bottom:50},{id:'c',left:100,right:150,top:0,bottom:50}]
 assert.deepEqual(intersectingIds(rows,{left:25,right:100,top:20,bottom:30}),['a','b'])
})

test('selected blocks move to the target technician without changing other team members',()=>{
 const rows=selectionDraft([{...a,technician:'Rick',technicians:['Rick','Allan']},{...b,technician:'Scott',technicians:['Scott']}],0,'Rick','Daryll')
 assert.deepEqual(rows[0].technicians,['Daryll','Allan']);assert.equal(rows[0].start,'09:00');assert.deepEqual(rows[1].technicians,['Scott'])
})

test('confirmed bookings require unbooking before selected movement',()=>assert.match(selectionMoveError([{...a,bookingStatus:'confirmed'}],15),/Unbook/))
