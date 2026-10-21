import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {resizeSchedule,travelReview,appointmentColour} from '../src/scheduleResize.js'
const cases=JSON.parse(fs.readFileSync(new URL('./fixtures/schedule-resize.json',import.meta.url),'utf8'))
for(const scenario of cases)test(scenario.name,()=>{
 const before=JSON.stringify(scenario),original=scenario.blocks.find(b=>b.id===scenario.root)
 const draft={...original,start:scenario.start,duration:scenario.duration}
 const plan=resizeSchedule(scenario.blocks,scenario.travel,original,draft,scenario.edge)
 assert.equal(!!plan.error,scenario.error,plan.error)
 if(!scenario.error)assert.deepEqual(Object.fromEntries(plan.drafts.map(b=>[b.id,b.start])),scenario.expected)
 assert.equal(JSON.stringify(scenario),before)
})
test('successful calculation, review and manual travel indicators',()=>{
 assert.equal(travelReview({estimatedSeconds:600,locked:true}),'calculated')
 assert.equal(travelReview({estimatedSeconds:600,routeConflict:true}),'review')
 assert.equal(travelReview({estimatedSeconds:600,routeError:'Address required'}),'review')
 assert.equal(travelReview({locked:true}),'review')
 assert.equal(travelReview({locked:false}),'manual')
})
test('appointment types get stable distinct standard colours',()=>{
 const types=['Equipment repair','Equipment assessment','Delivery','Collection','Vehicle service','Client visit','Other']
 assert.equal(new Set(types.map(appointmentColour)).size,types.length)
 assert.equal(appointmentColour('Delivery'),appointmentColour(' delivery '))
})
