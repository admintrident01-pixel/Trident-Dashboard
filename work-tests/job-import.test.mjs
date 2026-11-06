import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import {canAccessPage} from '../src/navigation.js'
import {validateJobImport,transferId,jobAddress,jobImportNotes,appointmentImport,quoteImport} from '../src/jobImportModel.js'
const id='12345678-1234-4234-8234-123456789012',now=Date.now(),source='https://capitalmobility.dbflex.net/secure/db/96562/preview.aspx?t=736016&id=70001&back=private-return-state'
const payload=()=>({version:1,transferId:id,createdAt:now,source:{recordId:'70001',jobNumber:'90001',url:source},fields:{client:'Example Client',street:'12 Example Road',suburb:'Example Town',city:'Example Town',phone:'Example phone',invoiceTo:'Example payer',make:'Example make',model:'Example model',problem:'Repair notes',jobNotes:'Plain job notes'}})

test('job import permits admins except Scott without changing their other page permissions',()=>{
 assert.equal(canAccessPage('job-import',{role:'admin',email:'bala@trice.nz'}),true)
 assert.equal(canAccessPage('job-import',{role:'admin',email:'another-admin@example.invalid'}),true)
 for(const session of [null,{role:'tech',email:'tech@example.invalid'},{role:'admin',email:' Scott@trice.nz '},{role:'admin',email:'other@example.invalid',technician:' Scott Yearbury '}])assert.equal(canAccessPage('job-import',session),false)
 assert.equal(canAccessPage('schedule',{role:'admin',email:'scott@trice.nz'}),true)
 assert.equal(canAccessPage('quotes',{role:'admin',email:'scott@trice.nz'}),true)
})
test('import validates source and expiry, drops unrequested fields and strips return-state URL',()=>{
 const raw=payload();raw.fields.accClaimNumber='PRIVATE';raw.fields.attachments=['private'];const copy=structuredClone(raw)
 const result=validateJobImport(raw,id,now)
 assert.equal(result.source.jobNumber,'90001');assert.equal(result.source.recordId,'70001');assert.equal(new URL(result.source.url).searchParams.has('back'),false)
 assert.equal(result.fields.accClaimNumber,undefined);assert.equal(result.fields.attachments,undefined);assert.deepEqual(raw,copy)
 for(const bad of [{...raw,createdAt:now-600001},{...raw,createdAt:now+60001},{...raw,transferId:'other'}, {...raw,source:{...raw.source,url:'https://evil.invalid/'}},{...raw,fields:{...raw.fields,client:''}},{...raw,fields:{...raw.fields,client:'x'.repeat(161)}}])assert.throws(()=>validateJobImport(bad,id,now))
 assert.equal(transferId('#job-import?transfer='+id),id);assert.equal(transferId('#job-import?transfer=------------------------------------'),'')
})
test('appointment and quote mappings preserve values without importing prices or recipient email',()=>{
 const raw=payload();raw.fields.email='client@example.invalid';raw.fields.problem='Text <script> is plain text'
 const job=validateJobImport(raw,id,now),notes=jobImportNotes(job)
 assert.equal(jobAddress(job.fields),'12 Example Road, Example Town')
 assert.deepEqual(appointmentImport(job,notes),{client:'Example Client',address:'12 Example Road, Example Town',notes})
 const quote=quoteImport(job,notes);assert.equal(quote.to,'Example payer');assert.equal(quote.recipientEmail,undefined);assert.equal(quote.number,undefined);assert.equal(quote.lines,undefined);assert.equal(quote.clientAddress,'12 Example Road')
 assert.match(notes,/90001.*70001/);assert.match(notes,/Text <script> is plain text/);assert.match(notes,/client@example.invalid/)
})
const script=fs.readFileSync(new URL('../public/trident-dbflex.user.js',import.meta.url),'utf8')
function sourceRuntime(client='Example Client'){
 let menu,opened,writes=0;const values=new Map(),boxes=new Map()
 const dd=value=>({tagName:'DD',innerText:value,getClientRects:()=>[{}]})
 const section=(name,labels)=>({querySelector:()=>({textContent:name}),querySelectorAll:()=>Object.entries(labels).map(([text,value])=>({textContent:text,nextElementSibling:dd(value),closest:()=>null}))})
 const sections=[section('Client',{'Client Name':client,Address:'12 Example Road',Suburb:'Town',City:'Town','ACC Claim Number':'PRIVATE CLAIM','Home Phone':'Example phone'}),section('Job Detail',{'Invoice To:':'Example payer'}),section('Job Notes',{'Job Notes':'Review this job'})]
 const doc={querySelector:()=>({textContent:'Job: 90001'}),querySelectorAll:()=>sections,getElementById:key=>boxes.get(key),createElement:()=>({style:{},setAttribute(){}}),body:{append:b=>boxes.set(b.id,b)}}
 const win={};win.top=win;win.self=win
 const context={window:win,document:doc,location:new URL(source),URL,URLSearchParams,crypto:{randomUUID:()=>id},Date,GM_registerMenuCommand:(name,fn)=>{assert.equal(name,'Send job to Trident');menu=fn},GM_setValue:(key,value)=>{writes++;values.set(key,value)},GM_getValue:key=>values.get(key),GM_deleteValue:key=>values.delete(key),GM_listValues:()=>[],GM_openInTab:url=>{opened=url}}
 vm.runInNewContext(script,context)
 return {send:()=>menu(),values,get opened(){return opened},get writes(){return writes}}
}
test('userscript sends only on explicit command and keeps private data out of target URL',async()=>{
 const run=sourceRuntime();assert.equal(run.writes,0);assert.equal(run.opened,undefined);await run.send()
 assert.equal(run.writes,1);const value=run.values.get('trident-dbflex:'+id)
 assert.equal(value.fields.client,'Example Client');assert.equal(value.fields.accClaimNumber,undefined);assert.equal(JSON.stringify(value).includes('PRIVATE CLAIM'),false)
 assert.equal(run.opened,'https://trident-dashboard.admintrident01.workers.dev/#job-import?transfer='+id)
 assert.equal(run.opened.includes('Example'),false);validateJobImport(value,id)
 const missing=sourceRuntime('');await missing.send();assert.equal(missing.writes,0);assert.equal(missing.opened,undefined)
})
test('recipient rejects foreign senders, uses ready handshake and deletes transfer after acknowledgement',async()=>{
 const value=payload(),key='trident-dbflex:'+id,store=new Map([[key,value]]),posted=[];let listener
 const win={addEventListener:(type,fn)=>{listener=fn},postMessage:(data,origin)=>posted.push({data,origin})};win.top=win;win.self=win
 const target='https://trident-dashboard.admintrident01.workers.dev'
 vm.runInNewContext(script,{window:win,location:new URL(target+'/#job-import?transfer='+id),URL,URLSearchParams,Date,GM_listValues:()=>[],GM_getValue:k=>store.get(k),GM_deleteValue:k=>store.delete(k)})
 const ready={source:win,origin:target,data:{type:'trident-dbflex-ready',transferId:id}}
 await listener({...ready,origin:'https://evil.invalid'});await listener({...ready,source:{}});assert.equal(posted.length,0)
 await listener(ready);assert.equal(posted.length,1);assert.equal(posted[0].data.payload,value);assert.equal(posted[0].origin,target);assert.equal(store.size,1)
 await listener({...ready,data:{type:'trident-dbflex-accepted',transferId:id}});assert.equal(store.size,0);await listener(ready);assert.equal(posted.length,1)
})
test('quote handoff is parent-only, duplicate-safe and keeps an existing quote when cancelled',async()=>{
 const html=fs.readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8'),code=html.slice(html.indexOf('const importedJobTransfers='),html.indexOf("$('deleteDraft').onclick="))
 const values={client:{value:'Existing client'},job:{value:'Existing work'}},replies=[];let receive,starts=0,allow=false
 const origin='https://trident-dashboard.admintrident01.workers.dev',parent={location:{origin},postMessage:data=>replies.push(data)}
 vm.runInNewContext(code,{window:{addEventListener:(_,fn)=>{receive=fn}},parent,location:{origin},quoteStartup:Promise.resolve(),startNewQuote:async()=>{starts++;return allow},$:key=>values[key]||(values[key]={value:''}),render(){},quoteConfirmationStatus(){}})
 const event={source:parent,origin,data:{type:'trident-import-quote',id,fields:{client:'Imported client',job:'Imported work'}}}
 await receive({...event,source:{}});assert.equal(starts,0)
 await receive(event);assert.equal(starts,1);assert.equal(values.client.value,'Existing client');assert.equal(replies.at(-1).accepted,false)
 allow=true;await receive(event);assert.equal(values.client.value,'Imported client');assert.equal(replies.at(-1).accepted,true)
 await receive(event);assert.equal(starts,2)
 await receive({...event,data:{...event.data,id:'22345678-1234-4234-8234-123456789012',fields:{number:'9999'}}});assert.equal(starts,2);assert.equal(replies.at(-1).accepted,false)
})
