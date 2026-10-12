import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
const html=fs.readFileSync(new URL('../public/timesheet.html',import.meta.url),'utf8')
function fn(name){const start=html.indexOf('function '+name+'('),brace=html.indexOf('{',start);let depth=1,i=brace+1;for(;depth&&i<html.length;i++){if(html[i]==='{')depth++;if(html[i]==='}')depth--}return html.slice(start,i)}
const context={};vm.createContext(context);vm.runInContext(fn('qmins')+fn('payableHours'),context)
assert.equal(context.payableHours({status:'Work',method:'direct',hours:8,unpaidLunch:true}),7.5)
assert.equal(context.payableHours({status:'Work',method:'times',start:'07:30',finish:'16:00',unpaidLunch:true}),8)
assert.equal(context.payableHours({status:'Annual leave',method:'direct',hours:8,unpaidLunch:true}),8)
assert.equal(context.payableHours({status:'Work',method:'direct',hours:0,unpaidLunch:true}),0)
const fields={'.status':{value:'Work'},'.mode':{value:'direct'},'.direct':{},'.start':{},'.finish':{}}
const row={querySelector:s=>fields[s],querySelectorAll:()=>[fields['.start'],fields['.finish']]}
context.calc=()=>{};vm.runInContext(fn('modeChange')+fn('timeEntry'),context)
fields['.mode'].closest=()=>row
context.timeEntry({closest:()=>row});assert.equal(fields['.mode'].value,'times');assert.equal(fields['.direct'].disabled,true);assert.equal(fields['.finish'].disabled,false)
fields['.status'].value='Annual leave';fields['.mode'].value='direct';context.timeEntry({closest:()=>row});assert.equal(fields['.mode'].value,'direct')
console.log('Lunch calculations and automatic time-entry switching passed.')

const defaultValues=html.match(/defaults=\[([^\]]+)\]/)[1].split(',').map(Number)
assert.deepEqual(defaultValues,[8.5,8.5,8.5,8.5,8.5,0,0])
assert.equal(context.payableHours({status:'Work',method:'direct',hours:defaultValues[0],unpaidLunch:true}),8)
const makeDefaultRow=(i,hours)=>{const inputs={'.start':{value:'07:30'},'.finish':{value:'16:00'},'.direct':{value:hours},'.status':{value:'Work'}};return {dataset:{i:String(i)},querySelector:s=>inputs[s],inputs}}
const defaultRows=[makeDefaultRow(0,8.5),makeDefaultRow(1,9),makeDefaultRow(5,0)]
context.document={querySelectorAll:()=>defaultRows};context.currentDefaultTimes={start:'07:30',finish:'16:00'}
vm.runInContext(fn('applyTimeDefaults'),context)
context.applyTimeDefaults({start:'08:00',finish:'16:00'})
assert.equal(Number(defaultRows[0].inputs['.direct'].value),8)
assert.equal(Number(defaultRows[1].inputs['.direct'].value),9)
assert.equal(Number(defaultRows[2].inputs['.direct'].value),0)
context.applyTimeDefaults({start:'07:30',finish:'16:00'})
assert.equal(Number(defaultRows[0].inputs['.direct'].value),8.5)
console.log('Default gross workday hours follow saved times while edited entries/weekends are retained.')

for(const method of ['direct','times']){
 const day={status:'Work',method,hours:8.5,start:'07:30',finish:'16:00',unpaidLunch:true}
 const paidWithLunch=context.payableHours(day)
 day.unpaidLunch=false
 assert.equal(paidWithLunch,8)
 assert.equal(context.payableHours(day),8.5)
 assert.equal(context.payableHours(day)-paidWithLunch,0.5)
}
console.log('Unchecking lunch adds exactly 0.5 payable hours in both entry methods.')
