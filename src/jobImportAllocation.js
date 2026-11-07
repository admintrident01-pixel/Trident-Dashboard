// Source strings stay intact; only explicit, reviewable amounts become quote lines.
export function sourceNumber(value){
 const text=String(value??'').trim().replace(/^(?:NZ\$|\$)\s*/,'')
 if(!/^(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$/.test(text))return null
 const n=Number(text.replaceAll(',',''));return Number.isFinite(n)&&n<=1e9?n:null
}
const key=value=>value.toLowerCase().replace(/[^a-z0-9]/g,'')
export function importedItems(job){
 const items=[]
 for(const [ti,table] of (job.capture?.tables||[]).entries()){
  const columns=table.columns.map(key),kind=key(table.title)
  const get=(row,...names)=>{for(const name of names){const i=columns.indexOf(key(name));if(i>=0)return row.cells[i]?.text||''}return ''}
  for(const [ri,row] of table.rows.entries()){
   if(row.kind==='summary')continue
   const add=(suffix,category,description,quantity,unit,total)=>{if(!description)return;items.push({id:`${ti}:${ri}:${suffix}`,category,description,qty:sourceNumber(quantity)??'',sourceQuantity:quantity,sourceUnit:unit,sourceTotal:total,table:table.title,row:ri})}
   if(kind==='parts')add('part','Parts',get(row,'Part Name','Stock Item'),get(row,'Qty','Quantity'),get(row,'Price'),get(row,'Subtotal'))
   else if(kind==='labour')add('labour','Labour','Labour — '+[get(row,'Name'),sourceNumber(get(row,'Labour Rate'))===null?get(row,'Labour Rate'):''].filter(Boolean).join(' · '),get(row,'Hours'),get(row,'Labour Rate'),get(row,'Labour Total','Total'))
   else if(kind==='charges'){
    const mileage=get(row,'Mileage'),freight=get(row,'Freight Total')||get(row,'Freight')
    if(mileage||get(row,'Mileage Total'))add('mileage','Mileage','Mileage'+(get(row,'Vehicle')?' — '+get(row,'Vehicle'):''),mileage,get(row,'Mileage Rate'),get(row,'Mileage Total'))
    if(freight)add('freight','Freight','Freight', '1',get(row,'Freight'),freight)
   }
  }
 }
 const labour=(job.capture?.sections||[]).flatMap(s=>s.fields).find(f=>key(f.label)==='labourtotal')?.text
 const labourRows=items.filter(i=>i.category==='Labour'),hours=labourRows.length&&labourRows.every(i=>typeof i.qty==='number'&&i.qty>=0)?labourRows.reduce((sum,i)=>sum+i.qty,0):0
 if(sourceNumber(labour)!==null)items.push({id:'totals:labour',category:'Labour',summary:true,description:'Labour — total hours',qty:hours||'',sourceQuantity:hours?hours+' hours':'Hours not recorded',sourceUnit:hours?String(sourceNumber(labour)/hours):'',sourceTotal:labour,table:'Totals'})
 return items
}
export function defaultChoices(items){
 const summary=items.find(i=>i.summary&&i.category==='Labour'),labour=items.filter(i=>!i.summary&&i.category==='Labour'),useSummary=!!summary&&(!labour.length||labour.some(i=>sourceRate(i,'excl',0)===null))
 return Object.fromEntries(items.map(i=>[i.id,{selected:i.qty>0&&(i.category!=='Labour'||(useSummary?!!i.summary:!i.summary)),description:i.description,qty:i.qty,rate:i.summary?sourceRate(i,'excl',0)??0:0}]))
}
export function itemChoice(items,choices,id,values){const next={...choices,[id]:{...choices[id],...values}},item=items.find(i=>i.id===id);if(values.selected&&item?.category==='Labour')for(const other of items)if(other.id!==id&&other.category==='Labour'&&(item.summary||other.summary))next[other.id]={...next[other.id],selected:false};return next}
export function categoryChoices(items,choices,category,selected){
 const defaults=defaultChoices(items)
 return Object.fromEntries(items.map(item=>[item.id,{...choices[item.id],...(item.category===category?{selected:selected&&(category==='Labour'?defaults[item.id].selected:Number(choices[item.id]?.qty)>0)}:{})}]))
}
export function sourceRate(item,basis,gstPercent){
 if(!['excl','incl'].includes(basis)||!(item.qty>0))return null
 const total=sourceNumber(item.sourceTotal),unit=sourceNumber(item.sourceUnit)
 let rate=total!==null?total/item.qty:unit
 if(rate===null)return null
 if(basis==='incl'){if(!Number.isFinite(gstPercent)||gstPercent<0||gstPercent>100)return null;rate/=1+gstPercent/100}
 return Math.round(rate*1e6)/1e6
}
export function allocationLines(items,choices){
 if(items.some(i=>i.summary&&choices[i.id]?.selected)&&items.some(i=>!i.summary&&i.category==='Labour'&&choices[i.id]?.selected))throw Error('Choose the source labour total or individual labour rows, not both.')
 return items.filter(item=>choices[item.id]?.selected).map(item=>{
  const choice=choices[item.id],qty=Number(choice.qty),rate=Number(choice.rate),description=String(choice.description||'').trim()
  if(!description||description.length>2000||choice.rate===''||!Number.isFinite(qty)||qty<=0||qty>1e9||!Number.isFinite(rate)||rate<0||rate>1e9)throw Error('Check the selected item descriptions, quantities and quote prices.')
  return {description,qty,rate}
 })
}
export function appointmentItemNotes(notes,lines,sourceId){
 return [notes,lines.length&&'Allocated items:\n'+lines.map(l=>`${l.qty} × ${l.description}`).join('\n'),sourceId&&'Full imported job: '+location.origin+'/#job-import?job='+sourceId].filter(Boolean).join('\n\n')
}
