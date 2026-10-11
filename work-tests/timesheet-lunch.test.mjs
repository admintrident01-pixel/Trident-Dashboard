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
