export const importFields={client:160,street:500,suburb:160,city:160,contact:160,phone:200,workPhone:200,email:254,invoiceTo:160,poNumber:200,assetNumber:200,make:200,model:200,serial:200,jobType:120,problem:16000,solution:16000,jobNotes:16000}
export function transferId(hash){const value=new URLSearchParams(hash.split('?')[1]||'').get('transfer');return /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(value||'')?value:''}
export function validateJobImport(raw,id,now=Date.now()){
 if(!/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(id||'')||!raw||raw.version!==1||raw.transferId!==id||!Number.isFinite(raw.createdAt)||raw.createdAt>now+60000||now-raw.createdAt>600000)throw Error('This transfer expired or is invalid. Send the job again from dbFLEX.')
 const source=raw.source||{},url=new URL(source.url)
 if(url.origin!=='https://capitalmobility.dbflex.net'||url.pathname!=='/secure/db/96562/preview.aspx'||url.searchParams.get('t')!=='736016'||!/^\d{1,12}$/.test(source.recordId||'')||url.searchParams.get('id')!==source.recordId||!/^\d{1,20}$/.test(source.jobNumber||''))throw Error('This is not a supported dbFLEX job link.')
 const fields={}
 for(const [key,max] of Object.entries(importFields)){const value=raw.fields?.[key]??'';if(typeof value!=='string'||value.length>max||[...value].some(ch=>ch.charCodeAt(0)<32&&![9,10,13].includes(ch.charCodeAt(0))))throw Error('The imported '+key+' is invalid or too long.');fields[key]=value.trim()}
 if(!fields.client)throw Error('A client name is required. Check that the job page has finished loading.')
 const cleanUrl=url.origin+url.pathname+'?t=736016&id='+source.recordId
 return {version:1,transferId:id,createdAt:raw.createdAt,source:{recordId:source.recordId,jobNumber:source.jobNumber,url:cleanUrl},fields}
}
export const locality=fields=>[...new Set([fields.suburb,fields.city].filter(Boolean))].join(', ')
export const jobAddress=fields=>[fields.street,locality(fields)].filter(Boolean).join(', ')
export function jobImportNotes(job){const f=job.fields;return [
 'dbFLEX job '+job.source.jobNumber+' · record '+job.source.recordId,job.source.url,
 f.poNumber&&'PO: '+f.poNumber,f.contact&&'Contact: '+f.contact,f.phone&&'Phone: '+f.phone,f.workPhone&&'Work phone: '+f.workPhone,f.email&&'Client/contact email: '+f.email,
 [f.assetNumber&&'Asset '+f.assetNumber,f.make,f.model,f.serial&&'Serial '+f.serial].filter(Boolean).join(' · '),
 f.jobType&&'Source job type: '+f.jobType,f.problem&&'Problem:\n'+f.problem,f.solution&&'Solution / remarks:\n'+f.solution,f.jobNotes&&'Job notes:\n'+f.jobNotes
 ].filter(Boolean).join('\n\n')}
export function appointmentImport(job,notes){return {client:job.fields.client,address:jobAddress(job.fields),notes}}
export function quoteImport(job,notes){const f=job.fields;return {client:f.client,clientAddress:f.street,clientLocality:locality(f),to:f.invoiceTo,ref:[job.source.jobNumber,f.poNumber&&'PO '+f.poNumber].filter(Boolean).join(' · '),equipment:[f.make,f.model].filter(Boolean).join(' '),job:notes}}
export const jobImportEnabled=session=>session?.role==='admin'&&!!session.email&&session.email.trim().toLowerCase()!=='scott@trice.nz'&&session.technician?.trim().toLowerCase()!=='scott yearbury'
