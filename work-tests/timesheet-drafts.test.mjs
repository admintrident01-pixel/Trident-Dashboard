import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
const html=fs.readFileSync(new URL('../public/timesheet.html',import.meta.url),'utf8')
test('opening a draft waits for initial settings before requesting its saved fields',async()=>{
 const code=html.slice(html.indexOf('async function resumeDraft('),html.indexOf("window.addEventListener('message',function(e){if(e.origin===parent.location.origin&&e.source===parent&&e.data&&e.data.type==='trident-resume-timesheet-draft')"))
 let ready,calls=0
 const context={initialConfigReady:new Promise(resolve=>{ready=resolve}),sheetDirty:false,busy:()=>{},apiRequest:async()=>{calls++;throw Error('Stop after the tested request')},message:()=>{}}
 vm.createContext(context);vm.runInContext(code,context)
 const opening=context.resumeDraft('fixture');await Promise.resolve();assert.equal(calls,0)
 ready();await opening;assert.equal(calls,1)
})
