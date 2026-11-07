import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import {sourceFieldMappings,quoteMappingTargets} from '../public/job-import-mapping.js'
const raw=JSON.parse(fs.readFileSync(new URL('./fixtures/dbflex-full-job.json',import.meta.url),'utf8'))
test('field mapping follows the requested email destination while keeping internal notes opt-in',()=>{
 const rows=sourceFieldMappings(raw)
 assert.equal(rows.find(r=>r.id==='client').target,'client');assert.equal(rows.find(r=>r.id==='payer').target,'to');assert.equal(rows.find(r=>r.id==='client-email').target,'recipientEmail');assert.equal(rows.find(r=>r.id==='job-notes').target,'');assert.equal(rows.some(r=>r.label.endsWith('Hire Total')),false);assert.equal(quoteMappingTargets.some(([id])=>id==='number'),false)
})
test('explicit mappings are reversible and reject stale quote values or unrelated fields',()=>{
 const html=fs.readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8'),code=html.slice(html.indexOf('function applyImportReview('),html.indexOf("document.addEventListener('trident-import-review-apply'"))
 const values={number:{value:'1750'},client:{value:'Old client'},job:{value:'Old job'}},ctx={$:key=>values[key],confirmingQuote:false,lines:[{description:'Old item',qty:2,rate:40}],drawLines(){},render(){}}
 vm.createContext(ctx);vm.runInContext(code,ctx)
 const result=ctx.applyImportReview({kind:'field',quoteNumber:'1750',field:'client',value:'New client',expected:'Old client'});assert.equal(result.before,'Old client');assert.equal(values.client.value,'New client')
 ctx.applyImportReview({kind:'field',quoteNumber:'1750',field:'client',value:result.before,expected:'New client'});assert.equal(values.client.value,'Old client')
 assert.throws(()=>ctx.applyImportReview({kind:'field',quoteNumber:'1750',field:'client',value:'Overwrite',expected:'stale'}));assert.throws(()=>ctx.applyImportReview({kind:'field',quoteNumber:'1750',field:'number',value:'9999',expected:'1750'}));assert.throws(()=>ctx.applyImportReview({kind:'field',quoteNumber:'1751',field:'client',value:'Overwrite',expected:'Old client'}))
 const expected=structuredClone(ctx.lines[0]);ctx.applyImportReview({kind:'line',quoteNumber:'1750',index:0,expected,value:{description:'Edited item',qty:1,rate:50}});assert.equal(ctx.lines[0].rate,50);assert.throws(()=>ctx.applyImportReview({kind:'line',quoteNumber:'1750',index:0,expected,value:{description:'Overwrite',qty:1,rate:30}}))
})
