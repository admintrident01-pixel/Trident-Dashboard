import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
const html=fs.readFileSync(new URL('../public/quote-builder.html',import.meta.url),'utf8')
const code=html.slice(html.indexOf('function fitQuotePreview(){'),html.indexOf('const previewObserver='))
const properties={},paper={style:{}},panel={style:{},clientHeight:600},main={clientWidth:1200,style:{getPropertyValue:k=>properties[k]||'',setProperty:(k,v)=>properties[k]=v,removeProperty:k=>delete properties[k]}}
let mobile=false,calculator=false
const context={$:()=>paper,document:{querySelector:s=>s==='main'?main:panel,body:{classList:{contains:()=>calculator}}},window:{matchMedia:()=>({matches:!mobile})}}
vm.createContext(context);vm.runInContext(code,context);context.fitQuotePreview();const scale=paper.style.zoom,column=properties['--preview-column']
for(const height of [200,800,6000,300,12000]){panel.clientHeight=height;context.fitQuotePreview();assert.equal(paper.style.zoom,scale);assert.equal(properties['--preview-column'],column)}
calculator=true;context.fitQuotePreview();assert.ok(Number(paper.style.zoom)<Number(scale))
mobile=true;context.fitQuotePreview();assert.equal(paper.style.zoom,'');assert.equal(properties['--preview-column'],undefined)
console.log('Preview zoom stays stable as long content grows; calculator/mobile resizing still works.')
