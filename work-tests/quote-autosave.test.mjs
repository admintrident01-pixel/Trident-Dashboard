import {test} from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
const html=readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8')
const setup=html.slice(html.indexOf('const calculationState='),html.indexOf('async function refreshCatalog()'))
const save=html.slice(html.indexOf('async function saveQuote(state,automatic=false)'),html.indexOf('async function migrateOlderDrafts()'))
function harness(){
 const elements={quoteEditor:{hidden:false},client:{value:'Client'},number:{value:'1754'}}
 const state={posts:[],messages:[],lines:[{description:'Repair',qty:1,rate:100}],activeQuote:null,baseline:null,calculator:null,confirming:false}
 const context={console,structuredClone,JSON,Date,Number,String,Error,AbortSignal,Uint8Array,File:class{},crypto:{randomUUID:()=> 'test-id'},
 document:{querySelectorAll:()=>[],addEventListener:()=>{}},$:id=>elements[id]??={value:''},setInterval:(cb,delay)=>{state.tick=cb;state.delay=delay},window:{addEventListener:(type,cb)=>{state[type]=cb}},
 quoteFields:()=>({number:elements.number.value,client:elements.client.value,date:'2026-10-12',job:'Repair'}),quoteConfirmationStatus:m=>state.messages.push(m),
 readLocalWorkbook:async()=>{await state.wait;return {}},readXlsx:async()=>({}),parseQuoteRegister:()=>({rows:[]}),refreshCatalog:async()=>{},
 nextQuoteNumber:()=>1754,quoteRecord:(fields,lines,totals)=>({}),totals:()=>({}),appendQuoteToWorkbook:async()=>({arrayBuffer:async()=>new ArrayBuffer(0)}),
 base64Bytes:()=>'',remember:()=>{},updateLastQuote:()=>{},updateDeleteDraftButton:()=>{},render:()=>{},
 fetch:async(url,options)=>{state.posts.push(JSON.parse(options.body));return {ok:!state.fail,json:async()=>state.fail?{error:'Offline'}:{quote:{id:'test-id',revision:state.posts.length,state:'Draft',pdfFilename:''}},headers:{get:()=> 'etag'}}}}
 vm.createContext(context)
 vm.runInContext(`let lines=${JSON.stringify(state.lines)},editorBaseline='',confirmingQuote=false,localHelperMode=true,activeQuote=null,localSaveToken='',localWorkbookRevision='',quoteCatalog=[],sourceDraftName='',excelSourceFile,settings={},confirmedQuoteNumber; ${setup} ${save}; editorBaseline=editorSignature(); window.test={save:saveQuote,dirty:editorChanged,editLines:()=>lines[0].rate=200};`,context)
 return {state,context,elements,api:context.window.test}
}
test('ten-second timer saves changed drafts once and leaves clean drafts idle',async()=>{
 const h=harness();assert.equal(h.state.delay,10000);h.state.tick();assert.equal(h.state.posts.length,0)
 h.elements.client.value='Updated';h.state.tick();await new Promise(resolve=>setImmediate(resolve))
 assert.equal(h.state.posts.length,1);assert.equal(h.state.posts[0].data.fields.client,'Updated');assert.equal(h.api.dirty(),false)
 h.state.tick();assert.equal(h.state.posts.length,1);assert.match(h.state.messages.at(-1),/Autosaved.*All changes saved/)
})
test('edits during autosave are kept dirty and saved in the next snapshot',async()=>{
 const h=harness();let release;h.state.wait=new Promise(resolve=>release=resolve);h.elements.client.value='First'
 const saving=h.api.save('Draft',true);h.elements.client.value='Second';h.api.editLines();release();await saving
 assert.equal(h.state.posts[0].data.fields.client,'First');assert.equal(h.state.posts[0].data.lines[0].rate,100);assert.equal(h.api.dirty(),true)
 await h.api.save('Draft',true);assert.equal(h.state.posts[1].data.fields.client,'Second');assert.equal(h.state.posts[1].data.lines[0].rate,200);assert.equal(h.api.dirty(),false)
})
test('failed saves retain dirty state and browser leave warning',async()=>{
 const h=harness();h.elements.client.value='Unsaved';h.state.fail=true;await h.api.save('Draft',true)
 assert.equal(h.api.dirty(),true);assert.match(h.state.messages.at(-1),/Quote not saved: Offline/)
 let warned=false;h.state.beforeunload({preventDefault:()=>warned=true});assert.equal(warned,true)
})
test('calculator state including markup is persisted in quote snapshots',async()=>{
 const h=harness();h.context.window.tridentCalculator={getState:()=>({gst:15,rows:[{cost:100,markup:10,margin:20,qty:2}]})}
 await h.api.save('Draft',true);assert.equal(h.state.posts[0].data.calculation.rows[0].markup,10)
})
