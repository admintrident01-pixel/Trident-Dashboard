import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
const html=fs.readFileSync(new URL('../public/timesheet.html',import.meta.url),'utf8')
function fn(name){const start=html.indexOf('function '+name+'('),brace=html.indexOf('{',start);let depth=1,index=brace+1;for(;depth&&index<html.length;index++){if(html[index]==='{')depth++;if(html[index]==='}')depth--}return html.slice(start,index)}
const rows=Array.from({length:7},()=>{const row={badge:null,fields:{}};for(const key of ['status','other','mode','direct','start','finish'])row.fields[key]={value:key==='status'?'Work':key==='mode'?'direct':key==='direct'?'8':'',disabled:false,closest:()=>row};row.querySelector=selector=>selector==='.approved-leave-badge'?row.badge:row.fields[selector.slice(1)];row.querySelectorAll=()=>[row.fields.start,row.fields.finish];row.fields.status.parentNode={append:badge=>{row.badge=badge;badge.remove=()=>row.badge=null}};return row})
const inputs={tech:{value:'  scott  '},week:{value:'2027-02-01'},download:{hidden:false}}
const context={document:{getElementById:id=>inputs[id],querySelectorAll:()=>rows,createElement:()=>({})},calc:()=>{},Map,Date,Number,String}
vm.createContext(context)
vm.runInContext("var approvedLeave=[],leaveBackups=new Map();"+fn('modeChange')+fn('statusChange')+fn('sheetDay')+fn('applyApprovedLeave'),context)
context.approvedLeave=[{technician:'Scott',leaveType:'Other',other:'Appointment',dates:['2027-02-03'],hoursPerDay:2.25}]
vm.runInContext('applyApprovedLeave()',context)
assert.equal(rows[2].fields.status.value,'Other');assert.equal(rows[2].fields.direct.value,2.25);assert.equal(rows[2].fields.other.value,'Appointment');assert.equal(rows[2].fields.status.disabled,true);assert.equal(rows[2].fields.direct.disabled,true);assert.match(rows[2].badge.textContent,/2.25 hours approved/);assert.equal(rows[1].fields.status.value,'Work')
vm.runInContext('applyApprovedLeave()',context);assert.equal(rows[2].fields.direct.value,2.25)
context.approvedLeave=[];vm.runInContext('applyApprovedLeave()',context);assert.equal(rows[2].fields.status.value,'Work');assert.equal(rows[2].fields.direct.value,'8');assert.equal(rows[2].fields.direct.disabled,false);assert.equal(rows[2].badge,null)
console.log('Approved leave type, exact hours, repeated refresh and cancellation checks passed.')
