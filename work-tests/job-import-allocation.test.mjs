import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import {validateJobImport,savedCaptureId} from '../src/jobImportModel.js'
import {importedItems,sourceNumber,sourceRate,allocationLines,appointmentItemNotes,defaultChoices,itemChoice} from '../src/jobImportAllocation.js'
const raw=JSON.parse(fs.readFileSync(new URL('./fixtures/dbflex-full-job.json',import.meta.url),'utf8'))
const job=validateJobImport(raw,raw.transferId,raw.createdAt)
test('a fresh transfer cannot be mistaken for an already saved capture',()=>{assert.equal(savedCaptureId('#job-import?transfer='+raw.transferId),'');assert.equal(savedCaptureId('#job-import?job='+raw.transferId),raw.transferId)})
test('full capture retains source costings, custom fields and attachment references without executing markup',()=>{
 assert.equal(job.capture.tables[0].rows[0].cells[5].text,'25%')
 assert.equal(job.capture.sections[0].fields[1].text,'EXAMPLE-CLAIM')
 assert.match(job.capture.sections[2].fields[0].text,/<script>/)
 assert.equal(job.capture.extras[0].links[0].label,'Example job document.pdf')
 const bad=structuredClone(raw);bad.capture.tables[0].rows[0].cells.pop();assert.throws(()=>validateJobImport(bad,raw.transferId,raw.createdAt))
 bad.capture=structuredClone(raw.capture);bad.capture.extras[0].links[0].url='javascript:alert(1)';assert.throws(()=>validateJobImport(bad,raw.transferId,raw.createdAt))
})
test('allocations separate cost from selling subtotal and do not add margins or summary totals twice',()=>{
 const items=importedItems(job);assert.equal(items.length,6)
 assert.equal(sourceRate(items[0],'manual',15),null);assert.equal(sourceRate(items[0],'excl',15),50)
 assert.equal(sourceRate({...items[0],sourceTotal:'$115.00'},'incl',15),50)
 const choices=defaultChoices(items);for(const i of items)choices[i.id].rate=sourceRate(i,'excl',15)??0
 const lines=allocationLines(items,choices);assert.equal(lines.reduce((n,l)=>n+l.qty*l.rate,0),253)
 choices[items[0].id].qty=1;choices[items[1].id].selected=false;assert.equal(allocationLines(items,choices)[0].qty,1)
 assert.equal(sourceNumber('25%'),null);assert.equal(sourceNumber('unknown'),null);assert.equal(sourceNumber('$0.00'),0);assert.equal(sourceNumber('$1,234.56'),1234.56)
 choices[items[0].id].qty='';assert.throws(()=>allocationLines(items,choices))
})
test('appointment item notes contain selected descriptions and quantities, not internal cost columns',()=>{
 globalThis.location={origin:'http://127.0.0.1:18790'}
 const notes=appointmentItemNotes('Inspect the brakes',[{description:'Replacement castor',qty:2,rate:50}],job.transferId)
 assert.match(notes,/2 × Replacement castor/);assert.match(notes,/#job-import\?job=/);assert.equal(notes.includes('50'),false);delete globalThis.location
})
test('existing draft allocation appends once and preserves its client, recipient and existing lines',async()=>{
 const html=fs.readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8'),code=html.slice(html.indexOf('const importedJobTransfers='),html.indexOf("$('deleteDraft').onclick="))
 const values={client:{value:'Existing Client'},recipientEmail:{value:'recipient@example.invalid'},quoteEditor:{hidden:false}},replies=[];let receive,allow=true
 const origin='https://trident-dashboard.admintrident01.workers.dev',parent={location:{origin},postMessage:data=>replies.push(data)}
 const context={window:{addEventListener:(_,fn)=>{receive=fn}},parent,structuredClone,quoteStartup:Promise.resolve(),document:{dispatchEvent(){}},Event:class{},activeQuote:{number:1754,state:'Draft',revision:2},lines:[{description:'Existing work',qty:1,rate:100}],sourceImports:[],quoteDetail:async()=>({revision:2,state:'Draft',data:{fields:{client:'Existing Client'}}}),$:key=>values[key]||(values[key]={value:''}),confirm:()=>allow,drawLines(){},render(){},quoteConfirmationStatus(){}}
 vm.createContext(context);vm.runInContext(code,context)
 const event={source:parent,origin,data:{type:'trident-import-quote',id:job.transferId,fields:{client:'Example Client'},allocation:{targetNumber:1754,jobImportId:job.transferId,jobNumber:'90001',lines:[{description:'Castor',qty:2,rate:50}]}}}
 allow=false;await receive(event);assert.equal(context.lines.length,1);assert.equal(replies.at(-1).accepted,false)
 allow=true;await receive(event);assert.equal(context.lines.length,2);assert.equal(context.lines[1].rate,50);assert.equal(values.client.value,'Existing Client');assert.equal(values.recipientEmail.value,'recipient@example.invalid');assert.equal(context.sourceImports.length,1)
 await receive(event);assert.equal(context.lines.length,2)
 await receive({...event,data:{...event.data,id:'22345678-1234-4234-8234-123456789012',allocation:{...event.data.allocation,lines:[{description:'Invalid',qty:1,rate:-1}]}}});assert.equal(context.lines.length,2);assert.equal(replies.at(-1).accepted,false)
})

test('named labour rates use the recorded total without guessing or billing rows twice',()=>{const items=importedItems(job),summary=items.find(i=>i.summary),labour=items.find(i=>i.category==='Labour'&&!i.summary);let choices=defaultChoices(items);assert.equal(choices[summary.id].selected,true);assert.equal(choices[labour.id].selected,false);assert.equal(sourceRate(labour,'excl',15),null);choices=itemChoice(items,choices,labour.id,{selected:true,rate:90});assert.equal(choices[summary.id].selected,false);choices[summary.id].selected=true;assert.throws(()=>allocationLines(items,choices))})
test('Hire/Loan and Wheelchair Services are excluded from captures and allocations',()=>{const extra=structuredClone(raw);extra.capture.tables.push({title:'Wheelchair Services',columns:['Comment'],rows:[{cells:[{text:'Excluded service'}]}]});const result=validateJobImport(extra,extra.transferId,extra.createdAt);assert.equal(result.capture.tables.some(t=>['Hire/Loan','Wheelchair Services'].includes(t.title)),false);assert.equal(result.capture.sections.flatMap(s=>s.fields).some(f=>f.label==='Hire Total'),false);assert.equal(importedItems(result).some(i=>i.category==='Hire'),false)})

test('labour hourly price is total cost divided by captured hours and stays editable',()=>{
 const example=structuredClone(job),table=example.capture.tables.find(t=>t.title==='Labour')
 const hours=table.columns.indexOf('Hours'),row=table.rows.find(r=>r.kind!=='summary')
 row.cells[hours].text='3.25'
 example.capture.sections.flatMap(s=>s.fields).find(f=>f.label==='Labour Total').text='$295.75'
 const items=importedItems(example),summary=items.find(i=>i.summary)
 assert.equal(summary.qty,3.25);assert.equal(sourceRate(summary,'excl',15),91)
 const choices=defaultChoices(items);assert.equal(choices[summary.id].rate,91);choices[summary.id].rate=95
 assert.equal(allocationLines(items,choices).find(l=>l.description===summary.description).rate,95)
})

test('Solution/Invoice Remarks never enters a cleaned capture, mappings or notes',()=>{
 const extra=structuredClone(raw);extra.fields.solution='EXCLUDED REMARKS'
 extra.capture.sections[0].fields.push({label:'Solution/Invoice Remarks',text:'EXCLUDED REMARKS',links:[]})
 const result=validateJobImport(extra,extra.transferId,extra.createdAt)
 assert.equal(JSON.stringify(result).includes('EXCLUDED REMARKS'),false)
})
