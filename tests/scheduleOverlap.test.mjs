import {test} from 'node:test'
import assert from 'node:assert/strict'
import {overlapLanes,blockPosition,travelSourceLabel,travelTooltip} from '../src/scheduleMath.js'
const range={start:450,end:960}
const block=(id,start,duration)=>({id,start,duration,technician:'Rick'})
test('overlapping lunch and travel retain full duration in separate lanes',()=>{
 const travel=block('travel','11:45',30),lunch=block('lunch','12:00',30),next=block('next','12:30',30)
 const lanes=overlapLanes([lunch,next,travel],'Rick',range)
 assert.equal(lanes.get('travel').count,2);assert.notEqual(lanes.get('travel').lane,lanes.get('lunch').lane)
 assert.deepEqual(lanes.get('next'),{lane:0,count:1})
 assert.equal(blockPosition(travel,range).width,blockPosition(lunch,range).width)
 assert.equal(blockPosition(travel,range).width,2*blockPosition(block('short','09:30',15),range).width)
})
test('touching blocks stay full width; other technicians and cancellations do not add lanes',()=>{
 const a=block('a','09:00',30),b=block('b','09:30',30)
 const lanes=overlapLanes([a,b,{...a,id:'other',technician:'Allan'},{...a,id:'cancel',cancelled:true}],'Rick',range)
 assert.equal(lanes.size,2);assert.equal(lanes.get('a').count,1);assert.equal(lanes.get('b').count,1)
})
test('travel provenance distinguishes successful Google estimates, manual and failed estimates',()=>{
 const a={...block('a','11:45',30),origin:'Depot',destination:'Client',estimatedSeconds:1000,locked:true}
 assert.equal(travelSourceLabel(a),'Calculated by Google Maps')
 assert.equal(travelSourceLabel({...a,locked:false}),'Manual travel')
 assert.match(travelSourceLabel({...a,routeError:'Unavailable'}),/needs review/)
 assert.match(travelTooltip(a),/From: Depot\nTo: Client\n11:45–12:15/)
})
