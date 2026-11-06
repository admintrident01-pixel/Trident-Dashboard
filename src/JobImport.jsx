import {useEffect,useRef,useState} from 'react'
import {transferId,validateJobImport,jobImportNotes,jobAddress} from './jobImportModel'
import './JobImport.css'

export default function JobImport({onAppointment,onQuote}){
 const [job,setJob]=useState(null),[notes,setNotes]=useState(''),[error,setError]=useState(''),[waiting,setWaiting]=useState(true)
 const accepted=useRef('')
 useEffect(()=>{
  const id=transferId(location.hash)
  if(!id){const timer=setTimeout(()=>setWaiting(false),0);return()=>clearTimeout(timer)}
  let timer,timeout,finished=false
  const stopWaiting=()=>{finished=true;clearInterval(timer);clearTimeout(timeout)}
  const receive=event=>{
   if(event.source!==window||event.origin!==location.origin||event.data?.type!=='trident-dbflex-job'||event.data.transferId!==id)return
   if(accepted.current===id)return
   try{const next=validateJobImport(event.data.payload,id);accepted.current=id;stopWaiting();setJob(next);setNotes(jobImportNotes(next));setError('');setWaiting(false);window.postMessage({type:'trident-dbflex-accepted',transferId:id},location.origin)}catch(e){stopWaiting();setError(e.message);setWaiting(false)}
  }
  const ready=()=>{if(!finished&&accepted.current!==id)window.postMessage({type:'trident-dbflex-ready',transferId:id},location.origin)}
  window.addEventListener('message',receive);timer=setInterval(ready,800);timeout=setTimeout(()=>{if(accepted.current!==id){stopWaiting();setWaiting(false);setError('No job received. Check that this userscript is enabled on both sites, in the same browser profile, then send the job again.')}},20000);ready()
  return()=>{window.removeEventListener('message',receive);clearInterval(timer);clearTimeout(timeout)}
 },[])
 const tooLong=notes.length>4000
 return <main className="workspace-page job-import"><header><h1>Import job from dbFLEX</h1><p>Review the job details before opening a new appointment or quote.</p></header>
  {error&&<p role="alert" className="job-import-error">{error}</p>}
  {waiting&&<p role="status">Waiting for the job from Tampermonkey…</p>}
  {!job&&<section className="job-import-card"><h2>Set up the browser shortcut</h2><ol><li><a href="/trident-dbflex.user.js" download>Download the Tampermonkey userscript</a> and install it in Tampermonkey.</li><li>Use the same browser profile for dbFLEX and Trident. Open a job, then right-click → Tampermonkey → Send job to Trident. The command is also in the Tampermonkey toolbar menu.</li><li>Sign in to Trident and review the imported details. Nothing is booked automatically.</li></ol><p className="job-import-hint">The script reads visible job fields only. ACC claim numbers, attachments and hidden fields are excluded. No API key or new cloud service is needed.</p></section>}
  {job&&<><section className="job-import-card"><h2>Job {job.source.jobNumber}</h2><a href={job.source.url} target="_blank" rel="noopener noreferrer">Open source job</a><dl>
   <dt>Client</dt><dd>{job.fields.client}</dd><dt>Address</dt><dd>{jobAddress(job.fields)||'Not recorded'}</dd><dt>Contact</dt><dd>{[job.fields.contact,job.fields.phone,job.fields.workPhone,job.fields.email].filter(Boolean).join(' · ')||'Not recorded'}</dd><dt>Invoice to</dt><dd>{job.fields.invoiceTo||'Not recorded'}</dd><dt>Asset / equipment</dt><dd>{[job.fields.assetNumber,job.fields.make,job.fields.model].filter(Boolean).join(' · ')||'Not recorded'}</dd>
  </dl></section><label className="job-import-notes">Job details and notes<textarea rows={12} value={notes} onChange={e=>setNotes(e.target.value)}/></label><p className={tooLong?'job-import-error':'job-import-hint'}>{notes.length} / 4000 characters{tooLong?' · Shorten these notes before continuing. The source record stays unchanged.':''}</p>
   <p className="job-import-hint">Choose the appointment date, technician and time in the booking window. Quotes use your Trident prices and normal draft autosave. Client/contact email is kept in the notes; choose the quote recipient separately.</p>
   <div className="job-import-actions"><button disabled={tooLong} className="primary-action" onClick={()=>onAppointment(job,notes)}>Use for appointment</button><button disabled={tooLong} onClick={()=>onQuote(job,notes)}>Use for quote</button></div>
  </>}
 </main>
}
