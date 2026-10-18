import test from 'node:test'
import assert from 'node:assert/strict'
import {extraNumbers,setAssetChecks,entryProblem} from '../src/stocktakeEntry.js'
const row={assets:[{id:'a'},{id:'b'}]}
const blank={count:'',decisions:{},numbers:[],notes:''}
test('bulk and individual changes preserve separately counted unnumbered items',()=>{
 const original={...blank,count:5,decisions:{a:'found'},numbers:[' extra ']}
 const missing=setAssetChecks(original,{a:'missing',b:'missing'})
 assert.equal(missing.count,4)
 assert.equal(setAssetChecks(missing,{a:'found',b:'found'}).count,6)
 assert.deepEqual(original.decisions,{a:'found'})
})
test('empty additional lines do not count as assets',()=>{
 assert.deepEqual(extraNumbers({...blank,numbers:[' ',' 123 ','']}),['123'])
 assert.equal(setAssetChecks({...blank,numbers:['']},{a:'found',b:'found'}).count,2)
})
test('unchecked, incomplete, fractional and duplicate counts explain how to fix them',()=>{
 assert.match(entryProblem(row,blank),/Mark each/)
 const checked={...blank,decisions:{a:'found',b:'missing'}}
 assert.match(entryProblem(row,checked),/Enter how many/)
 assert.match(entryProblem(row,{...checked,count:1.5}),/whole number/)
 assert.match(entryProblem(row,{...checked,count:0}),/total must include/)
 assert.match(entryProblem(row,{...checked,count:3,numbers:[' X ','x']}),/twice/)
 assert.equal(entryProblem(row,{...checked,count:2,numbers:['extra',' ']}),'')
})
test('zero is a valid physical count when all assets are missing or none are listed',()=>{
 assert.equal(entryProblem(row,{...blank,count:0,decisions:{a:'missing',b:'retire'}}),'')
 assert.equal(entryProblem({assets:[]},{...blank,count:0}),'')
})
