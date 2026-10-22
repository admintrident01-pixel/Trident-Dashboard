import test from 'node:test'
import assert from 'node:assert/strict'
import '../public/time-entry.js'

const {minutes,parts,fromParts,normalize,shift}=globalThis.TridentTimeEntry

test('12-hour clock round-trips every quarter-hour without changing stored values',()=>{
 for(let value=0;value<1440;value+=15){
  const clock=`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`
  const display=parts(clock)
  assert.equal(fromParts(display.hour,display.minute,display.period),clock)
 }
 assert.deepEqual(parts('00:00'),{hour:'12',minute:'00',period:'AM',endOfDay:false})
 assert.deepEqual(parts('12:00'),{hour:'12',minute:'00',period:'PM',endOfDay:false})
})

test('quarter-hour edits stay within day limits and preserve midnight end-of-day',()=>{
 assert.equal(normalize('07:37'),'07:30')
 assert.equal(normalize('07:38'),'07:45')
 assert.equal(shift('00:00',-1),'00:00')
 assert.equal(shift('23:45',1),'23:45')
 assert.equal(shift('23:45',1,{allowEndOfDay:true}),'24:00')
 assert.equal(shift('24:00',-1,{allowEndOfDay:true}),'23:45')
 assert.equal(normalize('24:00',{allowEndOfDay:true}),'24:00')
 assert.equal(parts('24:00').endOfDay,true)
 assert.equal(normalize('00:00',{min:'00:15'}),'00:15')
})

test('reminder minute precision survives while malformed values remain invalid',()=>{
 assert.equal(normalize('17:23',{step:60}),'17:23')
 assert.equal(shift('17:23',1,{step:60}),'17:24')
 for(const value of ['',null,'25:00','24:15','12:60','7:30'])assert.equal(minutes(value),null)
 for(const hour of ['00','13','oops'])assert.equal(fromParts(hour,'30','AM'),null)
 assert.equal(fromParts('12','00','AM'),'00:00')
 assert.equal(fromParts('12','00','PM'),'12:00')
})
