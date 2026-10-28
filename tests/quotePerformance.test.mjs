import test from 'node:test'
import assert from 'node:assert/strict'
import vm from 'node:vm'
import {readFileSync} from 'node:fs'
const html=readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8')
test('opening quote home requests a page and defaults without downloading a workbook',async()=>{
 const code=html.slice(html.indexOf('async function showHome('),html.indexOf('\nasync function startNewQuote('))
 const calls=[],elements={},context={quoteOpenGeneration:0,confirmingQuote:false,editorChanged:()=>false,$:id=>elements[id]??={},updateDeleteDraftButton:()=>{},renderHome:async defaults=>calls.push(defaults),connectLocalWorkbook:()=>assert.fail('Initial home must not download Excel')}
 vm.createContext(context);vm.runInContext(code,context);await context.showHome(false)
 assert.deepEqual(calls,[true]);assert.equal(elements.quoteEditor.hidden,true)
})
test('a slow detail read cannot replace an editor opened or closed in the meantime',async()=>{
 const code=html.slice(html.indexOf('async function openQuote(q){'),html.indexOf('\nasync function saveQuote('))
 let release;const context={quoteOpenGeneration:0,sourceDraftName:'',quoteDetail:()=>new Promise(resolve=>{release=resolve}),quoteConfirmationStatus:()=>assert.fail('A stale quote must not open')}
 vm.createContext(context);vm.runInContext(code,context);const opening=context.openQuote({summary:true});context.quoteOpenGeneration++;release({});await opening
})
test('focus refresh uses JSON for both the list and editor, preserving workbook for saves',async()=>{
 const code=html.slice(html.indexOf('async function refreshExcel('),html.indexOf("\n$('refreshExcel').onclick"))
 const calls=[],home={hidden:false},context={localHelperMode:true,refreshingExcel:false,confirmingQuote:false,$:()=>home,renderHome:async()=>calls.push('page'),loadQuoteDefaults:async()=>calls.push('defaults'),connectLocalWorkbook:()=>assert.fail('Focus must not download Excel'),quoteConfirmationStatus:assert.fail}
 vm.createContext(context);vm.runInContext(code,context);await context.refreshExcel(false);home.hidden=true;await context.refreshExcel(false)
 assert.deepEqual(calls,['page','defaults']);assert.equal(context.refreshingExcel,false)
})
test('PDF tools load only on demand, share concurrent loads and retry failures',async()=>{
 const start=html.indexOf('let pdfLibraryPromise;'),code=html.slice(start,html.indexOf('</script>',start)),scripts=[],context={window:{},document:{head:{append:s=>scripts.push(s)},createElement:()=>({remove(){}})}}
 vm.createContext(context);vm.runInContext(code,context);assert.equal(scripts.length,0)
 const first=context.loadPdfLibrary(),second=context.loadPdfLibrary();assert.equal(first,second);assert.equal(scripts.length,1);assert.equal(scripts[0].src,'/pdf-lib.min.js')
 scripts[0].onerror();await assert.rejects(first,/Unable to load PDF tools/)
 const retry=context.loadPdfLibrary();assert.equal(scripts.length,2);scripts[1].onload();await retry
})
