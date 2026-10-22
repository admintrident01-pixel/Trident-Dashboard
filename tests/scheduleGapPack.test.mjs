import {test} from 'node:test'
import assert from 'node:assert/strict'
import {gapPackPlan} from '../src/scheduleGapPack.js'
const b=(id,start,other={})=>({id,start,duration:60,client:id,technician:'Scott',timing:'flexible',...other})
const gap={upperId:'upper',lowerId:'lower',start:600,end:660}
const rows=[b('early','07:00'),b('upper','09:00'),b('lower','11:00'),b('later','13:00')]
test('preview shifts every block on the chosen side preserving spacing and durations',()=>{
 const above=gapPackPlan(rows,[],'Scott',gap,'above')
 assert.equal(above.error,'');assert.equal(above.delta,60)
 assert.deepEqual(above.drafts.map(b=>[b.id,b.start,b.duration]),[['early','08:00',60],['upper','10:00',60]])
 const below=gapPackPlan(rows,[],'Scott',gap,'below')
 assert.deepEqual(below.drafts.map(b=>[b.id,b.start]),[['lower','10:00'],['later','12:00']])
 assert.equal(rows[0].start,'07:00')
})
test('team links and anchored travel appear in the complete preview',()=>{
 const blocks=[...rows.map(x=>x.id==='upper'?{...x,technicians:['Scott','Bala']}:x),b('team-neighbour','10:00',{technician:'Bala',duration:30}),b('travel','08:45',{source:'travel',anchorId:'upper',linked:true,duration:15,timing:'fixed'})]
 const plan=gapPackPlan(blocks,[{leftId:'upper',rightId:'team-neighbour',linked:true}],'Scott',gap,'above')
 assert.equal(plan.error,'');assert.ok(plan.ids.includes('team-neighbour'));assert.ok(plan.ids.includes('travel'))
 assert.equal(plan.drafts.find(b=>b.id==='travel').start,'09:45')
})
test('fixed confirmed leave recurring notes and locked detached travel prevent preview save',()=>{
 for(const change of [{timing:'fixed'},{bookingStatus:'confirmed'},{source:'leave'},{source:'note'},{source:'travel',linked:false,locked:true}]){
  const plan=gapPackPlan(rows.map(x=>x.id==='early'?{...x,...change}:x),[],'Scott',gap,'above')
  assert.ok(plan.error);assert.equal(plan.drafts.length,0)
 }
})
test('shared booking collisions, cross-gap links and day bounds reject complete action',()=>{
 const team=rows.map(x=>x.id==='upper'?{...x,technicians:['Scott','Bala']}:x)
 assert.match(gapPackPlan([...team,b('other','10:00',{technician:'Bala'})],[],'Scott',gap,'above').error,/overlap/)
 assert.match(gapPackPlan(rows,[{leftId:'upper',rightId:'lower',linked:true}],'Scott',gap,'above').error,/crosses/)
 assert.match(gapPackPlan([...team,b('long','10:00',{technician:'Bala',duration:840})],[{leftId:'upper',rightId:'long',linked:true}],'Scott',gap,'above').error,/selected day/)
})
