import {test} from 'node:test'
import assert from 'node:assert/strict'
import {calculateLabour} from '../public/labour-math.js'
const row=(category,cost,qty=1,margin=0)=>({category,cost,qty,margin,description:category})
test('requested rates and GST match transferred quote totals',()=>{
 const result=calculateLabour([row('mileage',1.2,10),row('travel',95,1),row('labour',91,2),row('parts',100),row('consumables',20)],15)
 assert.deepEqual(result.lines.map(l=>l.description),['consumables','parts','labour','travel','mileage'])
 assert.equal(result.subtotal,40900);assert.equal(result.tax,6135);assert.equal(result.total,47035)
 assert.equal(result.subtotal,result.lines.reduce((sum,l)=>sum+Math.round(l.qty*l.rate*100),0))
})
test('margin uses selling-price percentage, not markup',()=>{
 const result=calculateLabour([row('consumables',20,1,20)],15)
 assert.equal(result.lines[0].rate,25);assert.equal(result.subtotal,2500);assert.equal(result.total,2875)
})
test('selling rates round to cents before fractional quantities, matching quotes',()=>{
 const result=calculateLabour([row('labour',91,1.25,33),row('travel',110,.75,15)],15)
 assert.equal(result.subtotal,result.lines.reduce((sum,l)=>sum+Math.round(l.qty*l.rate*100),0))
})
test('unselected zero quantities stay out of transferred lines',()=>{
 const result=calculateLabour([row('labour',91,0),row('consumables',20)],0)
 assert.equal(result.lines.length,1);assert.equal(result.total,2000)
})

test('labour and travel allow quarter hours and reject other increments',()=>{
 for(const category of ['labour','travel']){
  for(const hours of [0,.25,.5,.75,1,1.25,2.5])assert.doesNotThrow(()=>calculateLabour([row(category,100,hours)],15))
  for(const hours of [.1,.3,1.1])assert.throws(()=>calculateLabour([row(category,100,hours)],15),/0.25 increments/)
 }
 assert.equal(calculateLabour([row('labour',100,.25),row('travel',100,1)],0).subtotal,12500)
 assert.doesNotThrow(()=>calculateLabour([row('mileage',1.2,.3)],15))
})
test('invalid margins, quantities and costs block transfer',()=>{
 for(const bad of [row('labour',91,1,100),row('parts',-1),row('mileage',1.2,-1),row('travel',Infinity),row('other',10),{...row('parts',1),qty:''}])assert.throws(()=>calculateLabour([bad],15))
 assert.throws(()=>calculateLabour([row('labour',91)],-1))
})

test('markup applies before margin and GST and survives transfer rounding',()=>{
 const result=calculateLabour([{...row('parts',100,2,20),markup:10}],15)
 assert.equal(result.lines[0].rate,137.5)
 assert.equal(result.subtotal,27500)
 assert.equal(result.total,31625)
 for(const markup of [-1,1001,NaN,Infinity,''])assert.throws(()=>calculateLabour([{...row('parts',100),markup}],15),/Markup/)
})
