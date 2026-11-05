import {useCallback,useEffect,useRef,useState} from 'react'
import Icon from './Icon'
import {nzDay,shiftDay,recordedMinutes,hours,nzTime,mapsLink} from './myDayModel'
import './MyDay.css'

const label=day=>new Date(day+'T00:00:00Z').toLocaleDateString('en-NZ',{timeZone:'Pacific/Auckland',weekday:'short',day:'numeric',month:'short',year:'numeric'})
const remaining=n=>n==null?'Due date not recorded':n<0?`${Math.abs(n)} day${n===-1?'':'s'} overdue`:n===0?'Due today':`${n} day${n===1?'':'s'} left`
const status=a=>({'confirmed':'Booked','option':'Optional','action-needed':'Not booked'}[a.bookingStatus]||'Note')

export default function MyDay({request,session,onNavigate}){
 const key='trident-my-day-pending:'+session.email
 const [day,setDay]=useState(nzDay),[savedData,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[pending,setPending]=useState(()=>{try{return JSON.parse(localStorage.getItem(key))}catch{return null}}),[modal,setModal]=useState(null),[title,setTitle]=useState(''),[periods,setPeriods]=useState([]),[now,setNow]=useState(0)
 const dialog=useRef(null),epoch=useRef(0),saving=useRef(false),operation=useRef(pending),clock=useRef({server:0,local:0}),lastLoad=useRef(0)
 const data=savedData?.date===day?savedData:null
 const accept=useCallback(value=>{clock.current={server:Date.parse(value.serverNow),local:performance.now()};setNow(Date.parse(value.serverNow));setData(value)},[])
 const refresh=useCallback(async()=>{if(saving.current)return;const n=++epoch.current;try{const r=await request('/api/my-day?date='+day);if(n===epoch.current){accept(r.data);setError('');lastLoad.current=Date.now()}}catch(e){if(n===epoch.current)setError(e.message)}},[request,day,accept])
 useEffect(()=>{let mounted=true;Promise.resolve().then(()=>{if(mounted)refresh()});return()=>{mounted=false}},[refresh])

 useEffect(()=>{const timer=setInterval(()=>setNow(clock.current.server+performance.now()-clock.current.local),1000);const focus=()=>{if(!document.hidden&&Date.now()-lastLoad.current>60000)refresh()};window.addEventListener('focus',focus);document.addEventListener('visibilitychange',focus);return()=>{clearInterval(timer);window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',focus)}},[refresh])
 useEffect(()=>{if(modal&&!dialog.current.open)dialog.current.showModal();if(!modal&&dialog.current.open)dialog.current.close()},[modal])
 const clearPending=()=>{operation.current=null;setPending(null);try{localStorage.removeItem(key)}catch{/* Server receipts still deduplicate retries. */}}
 async function save(action,extra={},retry=false){
  if(saving.current||!data||operation.current&&!retry)return
  const command=retry?operation.current:{action,date:day,revision:data.revision,operationId:crypto.randomUUID(),...extra}
  if(!command)return
  operation.current=command;setPending(command);try{localStorage.setItem(key,JSON.stringify(command))}catch{/* In-memory retry retains the operation key. */}
  saving.current=true;epoch.current++;setBusy(true);setError('')
  try{const r=await request('/api/my-day',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(command)});clearPending();if(command.date===day)accept(r.data);else setDay(command.date);setModal(null)}
  catch(e){if(e.status>=400&&e.status<500){clearPending();saving.current=false;await refresh()}setError(e.message)}
  finally{saving.current=false;setBusy(false)}
 }
 function open(job){setError('');setTitle(job.client||job.title||'');setPeriods((data.day.jobs[job.id]?.sessions||[]).map(s=>({start:nzTime(s.start),end:nzTime(s.end)})));setModal({kind:'job',job})}
 const logs=data?.day.jobs||{},actual=recordedMinutes(logs,now),locked=busy||!!pending,finished=!!data?.day.finishedAt
 const custom=Object.values(logs).filter(j=>j.source==='custom'||!data?.appointments.some(a=>a.id===j.id))
 const due=data?.timesheet
 const go=page=>{if(!busy)onNavigate(page)}
 return <main className="my-day workspace-page">
  <header className="my-day-heading"><div><p className="my-day-eyebrow">My day · Pilot</p><h1>{data?.technician||session.technician}</h1></div><button disabled={busy} onClick={refresh} aria-label="Refresh My day"><Icon name="refresh-cw" size={18}/></button></header>
  <div className="my-day-dates"><button disabled={busy} aria-label="Previous day" onClick={()=>setDay(shiftDay(day,-1))}><Icon name="chevron-left"/></button><label><span className="sr-only">My day date</span><input type="date" value={day} onInput={e=>e.target.value&&setDay(e.target.value)}/></label><button disabled={busy} aria-label="Next day" onClick={()=>setDay(shiftDay(day,1))}><Icon name="chevron-right"/></button><button disabled={busy} onClick={()=>setDay(nzDay())}>Today</button></div>
  <p className="my-day-date-label">{label(day)} · Auckland time</p>
  {error&&<p role="alert" className="my-day-error">{error}</p>}
  {pending&&<aside className="my-day-retry" role="status">An action is waiting for confirmation. Your saved timer may already be running. <button disabled={busy||!data} onClick={()=>save(null,{},true)}>Retry saved action</button></aside>}
  {!data?<p role="status">Loading your day…</p>:<>
   {data.active&&data.active.date!==day&&<aside className="my-day-retry">Timer running on {label(data.active.date)}: {data.active.title}. <button onClick={()=>setDay(data.active.date)}>Open that day</button></aside>}
   <section className="my-day-hours" aria-label="Daily hours"><div><span>Recorded work</span><strong>{hours(actual)} <small>hrs</small></strong><span>{data.active?.date===day?'Timer running':'Saved work periods'}</span></div><div><span>Planned appointments</span><strong>{hours(data.plannedMinutes)} <small>hrs</small></strong><button onClick={()=>setModal({kind:'summary'})}>Day summary</button></div><button className="primary-action" disabled={locked} onClick={()=>save(finished?'reopen':'finish')}>{finished?'Reopen day':'Finish day'}</button>{finished&&<p>Day finished. Reopen to correct your work log.</p>}</section>
   <section className="my-day-attention"><h2>Needs attention</h2>
    {data.attention.filter(r=>r.kind==='vehicle').map(r=><button key={r.id} onClick={()=>go('vehicles')}><Icon name="truck"/><span><strong>Vehicle check · {r.registration||'Your vehicle'}</strong><small>{remaining(r.daysRemaining)}{r.due?' · '+label(r.due):''}</small></span><Icon name="chevron-right"/></button>)}
    {!data.attention.some(r=>r.kind==='vehicle')&&<button onClick={()=>go('vehicles')}><Icon name="truck"/><span><strong>Vehicle checks</strong><small>No active vehicle assigned</small></span><Icon name="chevron-right"/></button>}
    <button onClick={()=>go('timesheet')}><Icon name="clock"/><span><strong>Time sheet · {due.status}</strong><small>Week {label(due.weekStart)} · {remaining(due.daysRemaining)}</small><small>Due {label(due.due.slice(0,10))} at {nzTime(due.due)}</small></span><Icon name="chevron-right"/></button>
    <button onClick={()=>go('leave')}><Icon name="calendar"/><span><strong>Leave requests</strong><small>{data.leave[0]?`${data.leave[0].status} · ${label(data.leave[0].startDate)}`:'No submitted requests'}</small></span><Icon name="chevron-right"/></button>
   </section>
   <div className="my-day-section-heading"><h2>Appointments ({data.appointments.length})</h2><span>Tap a job for actual times</span></div>
   {!data.appointments.length&&<p className="my-day-empty">No appointments assigned to you on this day.</p>}
   {data.appointments.map(a=><article className="my-day-job" key={a.id}><button className="my-day-job-open" onClick={()=>open(a)}><span className="my-day-job-time">{a.start}–{String(Math.floor((Number(a.start.slice(0,2))*60+Number(a.start.slice(3))+a.duration)/60)).padStart(2,'0')}:{String((Number(a.start.slice(3))+a.duration)%60).padStart(2,'0')}<small>{status(a)}</small></span><h3>{a.client}</h3><p>{a.type}</p>{a.address&&<p><Icon name="map-pin" size={16}/>{a.address}</p>}{a.notes&&<p className="my-day-job-notes">{a.notes}</p>}<span className="my-day-recorded">Recorded {hours(recordedMinutes({job:logs[a.id]},now))} hrs{data.active?.jobId===a.id&&data.active.date===day?' · Running':''}</span></button>{mapsLink(a.address)&&<a className="my-day-map" href={mapsLink(a.address)} target="_blank" rel="noopener noreferrer"><Icon name="navigation" size={18}/>Open in Google Maps</a>}</article>)}
   {!!data.recurringNotes.length&&<section className="my-day-notes"><h2>Schedule notes</h2>{data.recurringNotes.map(a=><p key={a.id}><strong>{a.start} · {a.client}</strong>{a.notes&&<span>{a.notes}</span>}</p>)}</section>}
   <div className="my-day-section-heading"><h2>Other recorded work</h2><button disabled={locked||finished} onClick={()=>{setTitle('');setModal({kind:'custom'})}}>+ Custom job</button></div>
   {custom.map(j=><button className="my-day-custom" key={j.id} onClick={()=>open(j)}><strong>{j.title}</strong><span>{hours(recordedMinutes({job:j},now))} hrs{data.active?.jobId===j.id&&data.active.date===day?' · Running':''}</span><Icon name="chevron-right"/></button>)}
   <p className="my-day-footnote">Recorded hours are your personal work log. Submit your time sheet separately.</p>
   <nav className="my-day-links" aria-label="My day shortcuts"><button onClick={()=>go('schedule')}>Schedule</button><button onClick={()=>go('timesheet')}>Time sheet</button><button onClick={()=>go('leave')}>Leave</button><button onClick={()=>go('vehicles')}>Vehicles</button></nav>
  </>}
  <dialog aria-labelledby="my-day-dialog-title" className="my-day-dialog" ref={dialog} onCancel={e=>{if(busy)e.preventDefault();else setModal(null)}} onClose={()=>setModal(null)}>
   {modal&&data&&<><header><h2 id="my-day-dialog-title">{modal.kind==='summary'?'Day summary':modal.kind==='custom'?'Custom job':title}</h2><button disabled={busy} aria-label="Close job window" onClick={()=>setModal(null)}><Icon name="x"/></button></header>
    {error&&<p role="alert" className="my-day-error">{error}</p>}
    {modal.kind==='summary'?<><p>{label(day)}</p><dl><dt>Planned appointment hours</dt><dd>{hours(data.plannedMinutes)}</dd><dt>Recorded work hours</dt><dd>{hours(actual)}</dd></dl><p>Planned hours sum your assigned appointments, excluding Notes, travel and cancelled bookings. Actual work uses the saved periods below.</p>{Object.values(logs).map(j=><p key={j.id}>{j.title}: <strong>{hours(recordedMinutes({job:j},now))} hrs</strong></p>)}</>:modal.kind==='custom'?<form onSubmit={e=>{e.preventDefault();save('create',{jobId:'custom:'+crypto.randomUUID(),title})}}><label>Job name<input autoFocus required maxLength={160} value={title} onChange={e=>setTitle(e.target.value)}/></label><p>This records your own work without adding a shared schedule appointment.</p><button className="primary-action" disabled={locked||finished}>Add custom job</button></form>:<>
     {modal.job.notes&&<p className="my-day-job-notes">{modal.job.notes}</p>}
     <div className="my-day-timer-actions"><button className="primary-action" disabled={locked||finished||!!data.active||day!==data.today} onClick={()=>save('start',{jobId:modal.job.id})}>Start timer</button><button disabled={locked||finished||data.active?.jobId!==modal.job.id||data.active?.date!==day} onClick={()=>save('stop',{jobId:modal.job.id})}>Stop timer</button></div>
     {data.active?.jobId===modal.job.id&&data.active.date===day&&<p role="status">Running since {nzTime(data.active.start)}. Stop it when work ends; the timer remains running after you close this window.</p>}
     <form onSubmit={e=>{e.preventDefault();save('times',{jobId:modal.job.id,sessions:periods})}}><h3>Actual work periods</h3><p>Enter start and finish times in Auckland time. Save replaces this job’s periods; previous values remain in its audit history.</p>
      {periods.map((s,i)=><div className="my-day-period" key={i}><label>Start<input aria-label={`Period ${i+1} start`} required type="time" step="60" value={s.start} onInput={e=>setPeriods(periods.map((v,n)=>n===i?{...v,start:e.target.value}:v))}/></label><label>Finish<input aria-label={`Period ${i+1} finish`} required type="time" step="60" value={s.end} onInput={e=>setPeriods(periods.map((v,n)=>n===i?{...v,end:e.target.value}:v))}/></label><button type="button" disabled={locked||finished} aria-label={`Remove period ${i+1}`} onClick={()=>setPeriods(periods.filter((_,n)=>n!==i))}><Icon name="trash-2" size={18}/></button></div>)}
      <div className="my-day-timer-actions"><button type="button" disabled={locked||finished} onClick={()=>setPeriods([...periods,{start:'',end:''}])}>+ Work period</button><button className="primary-action" disabled={locked||finished}>Save actual times</button></div></form>
    </>}
   </>}
  </dialog>
 </main>
}
