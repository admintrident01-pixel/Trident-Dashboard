import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const html=fs.readFileSync(new URL('../public/timesheet.html',import.meta.url),'utf8')
const script=html.slice(html.indexOf('function onCallValue(){'),html.indexOf('function message(text,error)'))

function harness({answer=null,rows=[]}={}){
 const toggles={}
 const fields={
  tech:{value:'Scott Yearbury'},week:{value:'2026-11-09'},signature:{value:'Scott Yearbury'},notes:{value:''},
  'on-call-field':{classList:{toggle:(name,on)=>{toggles[name]=on}}},
  'on-call-hint':{hidden:true}
 }
 const radios=[{value:'yes',checked:answer===true},{value:'no',checked:answer===false}]
 const context={
  document:{getElementById:id=>fields[id]||{value:'',hidden:true,classList:{toggle(){}}},querySelector:selector=>selector.includes('oncall')?radios.find(radio=>radio.checked)||null:null,querySelectorAll:selector=>selector.includes('oncall')?radios:rows},
  names:['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'],
  qmins:value=>{const [hour,minute]=value.split(':').map(Number);return hour*60+minute},
  activeDraftId:'',activeDraftRevision:0,Error,Date,Math,Number,String,isNaN,toggles
 }
 vm.createContext(context)
 vm.runInContext(script,context)
 return {context,radios,toggles}
}

test('on-call choice is required before signing and travels with the sheet',()=>{
 const none=harness()
 assert.equal(none.context.onCallValue(),null)
 assert.throws(()=>none.context.collectSheet(false),/Choose Yes or No for the on-call allowance/)
 assert.equal(harness({answer:true}).context.collectSheet(false).onCall,true)
 assert.equal(harness({answer:false}).context.collectSheet(false).onCall,false)
})

test('a draft may stay unanswered and keeps its answered state',()=>{
 const draft=harness()
 assert.equal(draft.context.collectSheet(true).onCall,null)
 const yes=harness({answer:true})
 assert.equal(yes.context.collectSheet(true).onCall,true)
})

test('resuming, clearing and choosing update the radios and the reminder',()=>{
 const {context,radios,toggles}=harness()
 context.setOnCall(true)
 assert.deepEqual(radios.map(radio=>radio.checked),[true,false])
 assert.equal(toggles['is-yes'],true)
 assert.equal(toggles['is-no'],false)
 context.setOnCall(false)
 assert.deepEqual(radios.map(radio=>radio.checked),[false,true])
 assert.equal(toggles['is-no'],true)
 context.setOnCall(null)
 assert.deepEqual(radios.map(radio=>radio.checked),[false,false])
})

test('form markup offers a distinct compulsory Yes/No control at sign-off',()=>{
 const field=html.slice(html.indexOf('<div class="field on-call"'),html.indexOf('<div class="field"><label for="notes">'))
 assert.match(field,/role="radiogroup"/)
 assert.match(field,/value="yes"/)
 assert.match(field,/value="no"/)
 assert.match(field,/Required/)
 assert.match(field,/On-call allowance needed/)
 assert.ok(html.indexOf('id="signature"')<html.indexOf('id="on-call-field"'))
 const css=fs.readFileSync(new URL('../public/timesheet-form.css',import.meta.url),'utf8')
 assert.match(css,/\.timesheet-form \.on-call\{border:1px solid #e0a13c/)
})

test('drafts, corrections and the PDF keep the recorded answer',()=>{
 assert.match(html,/document\.getElementById\('notes'\)\.value=row\.notes\|\|'';setOnCall\(/)
 assert.match(html,/text\('On-call allowance: '\+\(data\.onCall\?'Yes':'No'\)/)
 assert.match(html,/if\(data\.onCall\)\{if\(y<45\)newPage\(\);text\('On-call allowance needed'/)
})
