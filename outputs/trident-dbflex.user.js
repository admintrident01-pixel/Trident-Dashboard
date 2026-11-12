// ==UserScript==
// @name         Trident - Send dbFLEX job
// @namespace    https://trident-dashboard.admintrident01.workers.dev/
// @version      1.0.0
// @description  Send the visible job to Trident for review. No API keys, automatic saves or background sync.
// @match        https://capitalmobility.dbflex.net/secure/db/96562/preview.aspx*
// @match        https://trident-dashboard.admintrident01.workers.dev/*
// @run-at       document-idle
// @grant        GM_registerMenuCommand
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_deleteValue
// @grant        GM_listValues
// @grant        GM_openInTab
// ==/UserScript==
/* global GM_registerMenuCommand, GM_setValue, GM_getValue, GM_deleteValue, GM_listValues, GM_openInTab */
(()=>{
 'use strict'
 if(window.top!==window.self)return
 const target='https://trident-dashboard.admintrident01.workers.dev',prefix='trident-dbflex:',ttl=600000
 const sourceHost='capitalmobility.dbflex.net'
 function notice(text){let box=document.getElementById('trident-transfer-status');if(!box){box=document.createElement('div');box.id='trident-transfer-status';box.setAttribute('role','status');box.style.cssText='position:fixed;bottom:18px;right:18px;z-index:2147483647;max-width:360px;background:#17345f;color:white;padding:14px;border-radius:8px;font:14px/1.5 Arial;box-shadow:0 3px 15px #0004';document.body.append(box)}box.textContent=text}
 async function prune(){for(const key of await GM_listValues()){if(!key.startsWith(prefix))continue;const value=await GM_getValue(key);if(!value||!Number.isFinite(value.createdAt)||Date.now()-value.createdAt>ttl)await GM_deleteValue(key)}}
 function field(sectionName,label){const section=[...document.querySelectorAll('#td-bodyframe section[id^="section_"]')].find(s=>s.querySelector('h3')?.textContent.trim()===sectionName);if(!section)return '';const dt=[...section.querySelectorAll('dt')].find(x=>x.textContent.trim()===label);const dd=dt?.nextElementSibling;if(!dd||dd.tagName!=='DD'||dt.closest('.ui-hidden,.v3-state-hidden,[hidden]')||!dd.getClientRects().length)return '';return dd.innerText.trim()}
 function readJob(){
  const url=new URL(location.href),heading=document.querySelector('#td-bodyframe h2')?.textContent||'',jobNumber=heading.match(/^\s*Job:\s*(\d+)\s*$/i)?.[1]
  if(url.origin!=='https://'+sourceHost||url.pathname!=='/secure/db/96562/preview.aspx'||url.searchParams.get('t')!=='736016'||!/^\d{1,12}$/.test(url.searchParams.get('id')||'')||!jobNumber)throw Error('Open a JOBS record and wait for its details to finish loading.')
  const fields={},map={client:['Client','Client Name'],street:['Client','Address'],suburb:['Client','Suburb'],city:['Client','City'],contact:['Client','Contact Name'],phone:['Client','Home Phone'],workPhone:['Client','Work Phone'],email:['Client','Email'],invoiceTo:['Job Detail','Invoice To:'],poNumber:['Job Detail','PO Number'],assetNumber:['Asset','Asset Number'],make:['Asset','Make'],model:['Asset','Model'],serial:['Asset','Serial'],jobType:['Job Detail','Job Type'],problem:['Problem/Solution','Problem'],solution:['Problem/Solution','Solution/Invoice Remarks'],jobNotes:['Job Notes','Job Notes']}
  for(const [key,[section,label]] of Object.entries(map))fields[key]=field(section,label)
  if(!fields.client)throw Error('Client Name was not found. Nothing was sent; check this job page.')
  const recordId=url.searchParams.get('id'),transferId=crypto.randomUUID()
  const payload={version:1,createdAt:Date.now(),transferId,source:{recordId,jobNumber,url:url.origin+url.pathname+'?t=736016&id='+recordId},fields}
  if(JSON.stringify(payload).length>60000)throw Error('This job is too long to transfer. Nothing was sent.')
  return payload
 }
 if(location.hostname===sourceHost){
  const url=new URL(location.href)
  if(url.searchParams.get('t')!=='736016')return
  prune().catch(()=>{})
  GM_registerMenuCommand('Send job to Trident',async()=>{try{await prune();const payload=readJob();await GM_setValue(prefix+payload.transferId,payload);GM_openInTab(target+'/#job-import?transfer='+payload.transferId,{active:true,insert:true,setParent:true});notice('Opened Trident for review. Choose appointment or quote there. The source job has not been changed.')}catch(e){notice(e.message)}})
 }else if(location.origin===target){
  const id=new URLSearchParams(location.hash.split('?')[1]||'').get('transfer')
  if(!/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(id||''))return
  let acknowledged=false
  window.addEventListener('message',async event=>{
   if(event.origin!==target||event.source!==window||event.data?.transferId!==id)return
   if(event.data.type==='trident-dbflex-accepted'){acknowledged=true;await GM_deleteValue(prefix+id);return}
   if(event.data.type!=='trident-dbflex-ready'||acknowledged)return
   const payload=await GM_getValue(prefix+id)
   if(!payload||payload.transferId!==id||Date.now()-payload.createdAt>ttl){await GM_deleteValue(prefix+id);notice('Job transfer expired. Send the job again from dbFLEX.');return}
   window.postMessage({type:'trident-dbflex-job',transferId:id,payload},target)
  })
  prune().catch(()=>notice('Unable to read the private transfer. Check Tampermonkey permissions.'))
 }
})()
