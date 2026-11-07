import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {defaultQuoteFields,quoteImport,defaultQuoteMappings} from '../src/jobImportModel.js'
import {importedItems,defaultChoices,categoryChoices,allocationLines} from '../src/jobImportAllocation.js'
const job=JSON.parse(fs.readFileSync(new URL('./fixtures/dbflex-full-job.json',import.meta.url),'utf8'))

test('new quote defaults copy only requested client details and allow optional job fields',()=>{
 const source=structuredClone(job),selection=defaultQuoteFields(),fields=quoteImport(source,'',selection)
 assert.equal(fields.client,source.fields.client);assert.equal(fields.recipientEmail,source.fields.email)
 assert.equal(fields.equipment,source.fields.model);assert.match(fields.clientAddress,/Phone number 1/)
 assert.equal(fields.clientLocality,'Example Town')
 for(const key of ['to','ref','job','notes'])assert.equal(fields[key],'')
 const expanded=quoteImport(source,'',{...selection,problem:true,reference:true,jobNumber:true,invoiceTo:true})
 assert.equal(expanded.job,source.fields.problem);assert.match(expanded.ref,/90001/);assert.equal(expanded.to,source.fields.invoiceTo)
 assert.equal(expanded.notes,'Trident Job no : 90001');assert.deepEqual(source,job)
})
test('deselected contact details stay out of quote fields without removing the source capture',()=>{
 const fields=defaultQuoteFields();fields.email=false;fields.address=false;fields.phones=false;fields.equipment=false;fields.client=false
 const result=quoteImport(job,'',fields);assert.ok(Object.values(result).every(v=>v===''))
 const phones=quoteImport({...job,fields:{...job.fields,workPhone:'Second number'}},'',{phones:true})
 assert.equal(phones.clientAddress,'Phone number 1: Example phone\nPhone number 2: Second number');assert.equal(phones.clientLocality,'')
 const street=quoteImport(job,'',{address:true});assert.equal(street.clientAddress,job.fields.street)
 assert.equal(job.fields.email,'client@example.invalid')
})
test('cost-category toggles preserve edits and do not double-count labour',()=>{
 const items=importedItems(job),choices=defaultChoices(items),part=items.find(i=>i.category==='Parts')
 choices[part.id]={...choices[part.id],rate:47,qty:3,description:'Reviewed castor'}
 const none=categoryChoices(items,choices,'Parts',false)
 assert.equal(allocationLines(items,none).some(l=>l.description==='Reviewed castor'),false)
 assert.equal(none[part.id].rate,47);assert.equal(none[part.id].qty,3)
 const restored=categoryChoices(items,none,'Parts',true);assert.equal(restored[part.id].selected,true);assert.equal(restored[part.id].description,'Reviewed castor')
 const labour=categoryChoices(items,categoryChoices(items,restored,'Labour',false),'Labour',true)
 assert.equal(items.filter(i=>i.category==='Labour'&&labour[i.id].selected).length,1)
 assert.ok(allocationLines(items,labour).some(l=>l.description==='Labour — total hours'))
 assert.deepEqual(choices[part.id],{selected:true,rate:47,qty:3,description:'Reviewed castor'})
})
test('saved mappings affect only selected fields in future transfers and preserve full source',()=>{
 const original=structuredClone(job),fields=defaultQuoteFields(),mapping=defaultQuoteMappings()
 const normal=quoteImport(job,'',fields,mapping);assert.equal(normal.clientLocality,'Example Town');assert.match(normal.clientAddress,/Phone number 1/)
 mapping.email='notes';mapping.equipment='job';mapping.phones=''
 const moved=quoteImport(job,'',fields,mapping)
 assert.equal(moved.notes,'client@example.invalid');assert.equal(moved.recipientEmail,'');assert.equal(moved.job,'Mobility chair');assert.equal(moved.clientAddress,'12 Example Road')
 fields.email=false;assert.equal(quoteImport(job,'',fields,mapping).notes,'')
 assert.deepEqual(job,original);assert.equal(normal.recipientEmail,'client@example.invalid')
 const merged=quoteImport(job,'',{...fields,email:true,client:true},{...mapping,client:'notes'});assert.equal(merged.notes,'Example Client\nclient@example.invalid')
 assert.throws(()=>quoteImport(job,'',fields,{...mapping,client:'number'}))
})
