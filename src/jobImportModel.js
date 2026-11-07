export const importFields={client:160,street:500,suburb:160,city:160,contact:160,phone:200,workPhone:200,email:254,invoiceTo:160,poNumber:200,assetNumber:200,make:200,model:200,serial:200,jobType:120,problem:16000,jobNotes:16000}
export function transferId(hash){const value=new URLSearchParams(hash.split('?')[1]||'').get('transfer');return /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(value||'')?value:''}
export function savedCaptureId(hash){const value=new URLSearchParams(hash.split('?')[1]||'').get('job');return value?transferId('#job-import?transfer='+value):''}
export function validateJobImport(raw,id,now=Date.now()){
 if(!/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(id||'')||!raw||![1,2].includes(raw.version)||raw.transferId!==id||!Number.isFinite(raw.createdAt)||raw.createdAt>now+60000||now-raw.createdAt>600000)throw Error('This transfer expired or is invalid. Send the job again from dbFLEX.')
 const source=raw.source||{},url=new URL(source.url)
 if(url.origin!=='https://capitalmobility.dbflex.net'||url.pathname!=='/secure/db/96562/preview.aspx'||url.searchParams.get('t')!=='736016'||!/^\d{1,12}$/.test(source.recordId||'')||url.searchParams.get('id')!==source.recordId||!/^\d{1,20}$/.test(source.jobNumber||''))throw Error('This is not a supported dbFLEX job link.')
 const fields={}
 for(const [key,max] of Object.entries(importFields)){const value=raw.fields?.[key]??'';if(typeof value!=='string'||value.length>max||[...value].some(ch=>ch.charCodeAt(0)<32&&![9,10,13].includes(ch.charCodeAt(0))))throw Error('The imported '+key+' is invalid or too long.');fields[key]=value.trim()}
 if(!fields.client)throw Error('A client name is required. Check that the job page has finished loading.')
 const cleanUrl=url.origin+url.pathname+'?t=736016&id='+source.recordId
 const capture=raw.version===2?validateCapture(raw.capture):undefined
 return {version:raw.version,transferId:id,createdAt:raw.createdAt,source:{recordId:source.recordId,jobNumber:source.jobNumber,url:cleanUrl},fields,...(capture?{capture}:{})}
}
const captureText=(v,max)=>{if(typeof v!=='string'||v.length>max||[...v].some(ch=>ch.charCodeAt(0)<32&&![9,10,13].includes(ch.charCodeAt(0))))throw Error('The captured job contains invalid or oversized text. Nothing was shortened.');return v}
const excludedCapture=value=>['hireloan','wheelchairservices','hiretotal','loanhireitems','solutioninvoiceremarks'].includes(String(value).toLowerCase().replace(/[^a-z0-9]/g,''))
export function validateCapture(raw){
 if(!raw||JSON.stringify(raw).length>1500000)throw Error('The job capture is missing or too large. Nothing was shortened.')
 const list=(v,max)=>{if(!Array.isArray(v)||v.length>max)throw Error('The job contains too many fields or rows. Nothing was shortened.');return v}
 const links=v=>list(v||[],30).map(l=>{const url=new URL(l.url);if(url.origin!=='https://capitalmobility.dbflex.net'||url.username||url.password||!/^\/secure\/db\/96562\/(preview|documentopen|file|attachment|download|image)[^/]*$/i.test(url.pathname))throw Error('An imported reference link is not supported.');url.searchParams.delete('back');return {label:captureText(l.label,1000),url:url.href}})
 const cell=c=>({text:captureText(c.text,16000),links:links(c.links)})
 return {sections:list(raw.sections,100).filter(s=>!excludedCapture(s.title)).map(s=>({title:captureText(s.title,200),fields:list(s.fields,200).filter(f=>!excludedCapture(f.label)).map(f=>({label:captureText(f.label,200),...cell(f)}))})),tables:list(raw.tables,30).filter(t=>!excludedCapture(t.title)).map(t=>{const columns=list(t.columns,40).map(c=>captureText(c,200));return {title:captureText(t.title,200),columns,rows:list(t.rows,1000).map(r=>{if(r.cells?.length!==columns.length||r.kind&&!['data','summary'].includes(r.kind))throw Error('A captured table row does not match its headings.');return {kind:r.kind||'data',cells:list(r.cells,40).map(cell)}})}}),extras:list(raw.extras||[],30).filter(s=>!excludedCapture(s.title)).map(s=>({title:captureText(s.title,200),...cell(s)})),warnings:list(raw.warnings||[],100).map(s=>captureText(s,1000))}
}
export const locality=fields=>[...new Set([fields.suburb,fields.city].filter(Boolean))].join(', ')
export const jobAddress=fields=>[fields.street,locality(fields)].filter(Boolean).join(', ')
export function jobImportNotes(job){const f=job.fields;return [
 'dbFLEX job '+job.source.jobNumber+' · record '+job.source.recordId,job.source.url,
 f.poNumber&&'PO: '+f.poNumber,f.contact&&'Contact: '+f.contact,f.phone&&'Phone: '+f.phone,f.workPhone&&'Work phone: '+f.workPhone,f.email&&'Client/contact email: '+f.email,
 [f.assetNumber&&'Asset '+f.assetNumber,f.make,f.model,f.serial&&'Serial '+f.serial].filter(Boolean).join(' · '),
 f.jobType&&'Source job type: '+f.jobType,f.problem&&'Problem:\n'+f.problem,f.jobNotes&&'Job notes:\n'+f.jobNotes
 ].filter(Boolean).join('\n\n')}
export function appointmentImport(job,notes){return {client:job.fields.client,address:jobAddress(job.fields),type:job.fields.jobType||'Unspecified',notes}}
export function quoteImport(job){const f=job.fields;return {client:f.client,clientAddress:[f.street,f.phone&&'Phone number 1: '+f.phone,f.workPhone&&'Phone number 2: '+f.workPhone].filter(Boolean).join('\n'),clientLocality:locality(f),to:f.invoiceTo,recipientEmail:f.email||'',ref:[job.source.jobNumber,f.poNumber&&'PO '+f.poNumber].filter(Boolean).join(' · '),equipment:f.model,job:f.problem,notes:'Trident Job no : '+job.source.jobNumber}}
export const jobImportEnabled=session=>session?.role==='admin'&&!!session.email&&session.email.trim().toLowerCase()!=='scott@trice.nz'&&session.technician?.trim().toLowerCase()!=='scott yearbury'
