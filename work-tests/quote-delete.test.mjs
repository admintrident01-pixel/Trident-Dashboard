import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
const html=fs.readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8')
const start=html.indexOf('async function deleteQuote(q){'),end=html.indexOf('\n}',start)+2,code=html.slice(start,end)
test('Quote Delete reaches its guarded request flow and restores controls after failure',async()=>{
 const controls=[{disabled:false},{disabled:true}],messages=[]
 const context={confirmingQuote:false,confirm:()=>true,document:{querySelectorAll:()=>controls},quoteConfirmationStatus:value=>messages.push(value),readLocalWorkbook:async()=>{throw Error('Synthetic request reached')},updateDeleteDraftButton:()=>{}}
 vm.createContext(context);vm.runInContext(code,context)
 await context.deleteQuote({state:'Draft',data:{fields:{number:1761,client:'Synthetic client'}}})
 assert.ok(messages.includes('Nothing deleted: Synthetic request reached'));assert.deepEqual(controls.map(a=>a.disabled),[false,true]);assert.equal(context.confirmingQuote,false)
})
test('Cancelling quote Delete does not lock controls or request a workbook',async()=>{
 const context={confirmingQuote:false,confirm:()=>false}
 vm.createContext(context);vm.runInContext(code,context)
 await context.deleteQuote({state:'Draft',data:{fields:{number:1761}}});assert.equal(context.confirmingQuote,false)
})
