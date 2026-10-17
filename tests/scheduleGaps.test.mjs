import {test} from 'node:test'
import assert from 'node:assert/strict'
import {scheduleGaps} from '../src/scheduleMath.js'
test('gaps are bounded by actual blocks including travel and lunch',()=>{
 const blocks=[{id:'a',technician:'Scott',start:'09:00',duration:60},{id:'travel',technician:'Scott',start:'10:30',duration:30,source:'travel'},{id:'b',technician:'Scott',start:'11:00',duration:60},{id:'lunch',technician:'Scott',start:'12:00',duration:30,source:'lunch'},{id:'cancelled',technician:'Scott',start:'10:00',duration:15,cancelled:true}]
 assert.deepEqual(scheduleGaps(blocks,'Scott',{start:480,end:960}),[{upperId:'a',lowerId:'travel',start:600,end:630,visibleStart:600,visibleEnd:630}])
 assert.deepEqual(scheduleGaps(blocks,'Bala',{start:480,end:960}),[])
})
test('overlaps are merged and displayed gaps clip to the visible time range',()=>{
 const blocks=[{id:'a',technician:'Scott',start:'06:00',duration:60},{id:'inner',technician:'Scott',start:'06:15',duration:15},{id:'b',technician:'Scott',start:'09:00',duration:60}]
 assert.deepEqual(scheduleGaps(blocks,'Scott',{start:480,end:960}),[{upperId:'a',lowerId:'b',start:420,end:540,visibleStart:480,visibleEnd:540}])
 assert.deepEqual(scheduleGaps(blocks,'Scott',{start:600,end:960}),[])
})
