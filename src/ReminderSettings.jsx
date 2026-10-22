import Icon from './Icon'
import TimeEntry from './TimeEntry'
import {reminderPlan} from './reminderTiming'
import {compareValues} from './tableSort'
import {useCallback,useEffect,useState} from 'react'
import HistoryPagination from './HistoryPagination'
import {pageWindow} from './pagination'
function EmailList({messages,archived,busy,onArchive,sortKey,direction}){
 const [paging,setPaging]=useState({key:'',page:1,size:10})
 const rows=messages.filter(m=>!!m.archived===archived).sort((a,b)=>compareValues(a[sortKey],b[sortKey])*(direction==='asc'?1:-1))
 const key=JSON.stringify([sortKey,direction,rows.map(m=>m.id)])
 const range=pageWindow(rows.length,paging.key===key?paging.page:1,paging.size)
 return <><HistoryPagination range={range} label={archived?'archived emails':'emails'} onPage={page=>setPaging(p=>({...p,key,page}))} onSize={size=>setPaging({key,page:1,size})}/>{rows.slice(range.offset,range.offset+range.size).map(m=><details className="mail-preview" key={m.id}><summary>{m.to} · {m.subject} · <b>{m.status==='preview'?'Local preview · not sent':m.status==='failed'?'Delivery failed · request a new email':m.status==='cancelled'?'Cancelled · time sheet submitted':m.status}</b></summary><p>{new Date(m.createdAt).toLocaleString('en-NZ',{timeZone:'Pacific/Auckland'})}</p>{m.body&&<pre>{m.body}</pre>}{archived&&<p className="report-hint">Archived {new Date(m.archivedAt).toLocaleString('en-NZ',{timeZone:'Pacific/Auckland'})} by {m.archivedBy}</p>}<button type="button" disabled={busy} onClick={()=>onArchive({id:m.id,archived:!archived})}>{archived?'Restore to email history':'Archive email'}</button></details>)}{!rows.length&&<p>{archived?'No archived emails.':'No email activity yet.'}</p>}</>
}
export function MailHistory({request}){
 const [messages,setMessages]=useState([]),[error,setError]=useState(''),[notice,setNotice]=useState(''),[sortKey,setSortKey]=useState('createdAt'),[direction,setDirection]=useState('desc'),[busy,setBusy]=useState(false),[confirming,setConfirming]=useState(false)
 const load=useCallback(()=>request('/api/mail-outbox').then(r=>{setMessages(r.data.messages);return r}),[request])
 useEffect(()=>{const refresh=()=>load().catch(e=>setError(e.message));refresh();window.addEventListener('trident-mail-updated',refresh);return()=>window.removeEventListener('trident-mail-updated',refresh)},[load])
 async function archive(change){setBusy(true);setError('');setNotice('');try{const latest=await load();const body=change||{ids:latest.data.messages.filter(m=>!m.archived).map(m=>m.id),archived:true};if(body.ids&&!body.ids.length){setConfirming(false);return}await request('/api/mail-archive',{method:'POST',headers:{'Content-Type':'application/json','If-Match':latest.etag},body:JSON.stringify(body)});await load();setConfirming(false);setNotice(change?(change.archived?'Email archived.':'Email restored.'):'All emails moved to the archive.')}catch(e){setError(e.message)}finally{setBusy(false)}}
 const activeCount=messages.filter(m=>!m.archived).length
 return <><section className="settings-section"><div className="page-heading"><h2>Email history</h2><div className="settings-actions"><button disabled={busy} onClick={()=>{setError('');load().catch(e=>setError(e.message))}}>Refresh emails</button><button disabled={busy||!activeCount} onClick={()=>setConfirming(true)}>Archive all emails</button></div></div>{error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}<div className="history-tools"><label>Sort emails by <select aria-label="Sort email history by" value={sortKey} onChange={e=>setSortKey(e.target.value)}>{[['createdAt','Date'],['to','Recipient'],['subject','Subject'],['status','Status']].map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><select aria-label="Email history sort order" value={direction} onChange={e=>setDirection(e.target.value)}><option value="asc">Ascending / A–Z</option><option value="desc">Descending / Z–A</option></select></div><EmailList {...{messages,busy,sortKey,direction}} archived={false} onArchive={archive}/></section><section className="settings-section archived-reminders"><h2>Archived emails ({messages.filter(m=>m.archived).length})</h2><p className="report-hint">Archived emails stay saved and can be restored. Archiving does not change delivery status or cancel queued emails.</p><EmailList {...{messages,busy,sortKey,direction}} archived onArchive={archive}/></section>{confirming&&<div className="staff-setup-overlay"><section className="staff-setup-dialog" role="dialog" aria-modal="true" aria-labelledby="archive-emails-title"><h2 id="archive-emails-title">Archive all emails?</h2><p>Move all {activeCount} emails from the history to Archived emails. You can restore them later.</p><p className="report-hint">This keeps the email records and their delivery status.</p>{error&&<p role="alert">{error}</p>}<div className="settings-actions"><button autoFocus disabled={busy} onClick={()=>setConfirming(false)}>Cancel</button><button className="primary-action" disabled={busy} onClick={()=>archive()}>{busy?'Archiving…':'Confirm archive all'}</button></div></section></div>}</>
}
const preferenceKeys=['timesheetWeekday','timesheetTime','timesheetLeadHours','timesheetRepeatHours','vehicleLeadDays','automaticTimesheets','automaticVehicles','timesheetRecipients','vehicleRecipients','stocktakeRecipients','leaveRecipients','stocktakeIntervalDays','automaticStocktakes']
const preferenceSnapshot=data=>JSON.stringify(Object.fromEntries(preferenceKeys.map(k=>[k,data[k]])))
const dateLabel=value=>value?new Date(value+'T12:00:00').toLocaleDateString('en-NZ'):'Not yet recorded'
function Recipients({kind,data,onChange}){
 const adminOnly=['stocktake','leave'].includes(kind),key=kind+'Recipients'
 const people=(data.recipientOptions||[]).filter(p=>adminOnly?p.admin:p.technician)
 const available=people.filter(p=>p.active&&p.verified)
 const selected=data[key]??(kind==='leave'?[]:available.map(p=>p.email))
 return <fieldset className="reminder-recipients"><legend>{adminOnly?'Admin recipients':'Staff recipients'}</legend>
  <div className="reminder-recipient-tools"><span>{selected.filter(email=>available.some(p=>p.email===email)).length} selected</span><button type="button" onClick={()=>onChange(key,available.map(p=>p.email))}>Select all</button><button type="button" onClick={()=>onChange(key,[])}>Clear</button></div>
  <div className="reminder-recipient-list">{people.map(p=><label key={p.email} className="reminder-recipient"><input type="checkbox" checked={selected.includes(p.email)} onChange={e=>onChange(key,e.target.checked?[...selected,p.email]:selected.filter(email=>email!==p.email))}/><span>{p.name}<small>{p.email}{!p.active?' · Inactive':!p.verified?' · Email not confirmed':''}</small></span></label>)}</div>
  {!people.length&&<p className="report-hint">No {adminOnly?'admin':'linked staff'} accounts yet. Add them in Staff &amp; vehicles.</p>}
  {!selected.length&&<p className="report-hint">{kind==='leave'?'No admin notices. Technician confirmation and decision emails still apply.':'No recipients selected. No automatic emails will be sent.'}</p>}
  <p className="report-hint">Only active accounts with confirmed emails receive messages.{data[key]==null?' Current rule: all eligible accounts. Saving keeps the people selected here.':''}</p>
 </fieldset>
}
function Automatic({checked,onChange,label='Send automatically'}){
 return <label className="check-option reminder-enable"><input type="checkbox" checked={checked} onChange={e=>onChange(e.target.checked)}/>{label}</label>
}
function OtherRule({title,summary,children}){
 return <details className="settings-section reminder-rule reminder-secondary"><summary><h2>{title}</h2><span>{summary}</span><Icon name="chevron-down" className="reminder-disclosure-icon"/></summary><div className="reminder-secondary-body">{children}</div></details>
}
export default function ReminderSettings({request}){
 const [data,setData]=useState(null),[baseline,setBaseline]=useState(''),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const load=useCallback(()=>request('/api/reminder-settings').then(r=>{setData(r.data);setBaseline(preferenceSnapshot(r.data));return r}),[request])
 useEffect(()=>{load().catch(e=>setError(e.message))},[load])
 function change(key,value){setData(d=>({...d,[key]:value}));setMessage('')}
 async function save(e){
  e.preventDefault();setBusy(true);setError('');setMessage('')
  try{
   const r=await request('/api/reminder-settings')
   if(preferenceSnapshot(r.data)!==baseline)throw Error('Reminder settings changed. Reload before saving.')
   const body=Object.fromEntries(preferenceKeys.map(key=>[key,data[key]]))
   for(const kind of ['timesheet','vehicle','stocktake','leave']){
    const key=kind+'Recipients'
    body[key]=data[key]??(kind==='leave'?[]:(data.recipientOptions||[]).filter(p=>p.active&&p.verified&&(['stocktake','leave'].includes(kind)?p.admin:p.technician)).map(p=>p.email))
   }
   await request('/api/reminder-settings',{method:'POST',headers:{'Content-Type':'application/json','If-Match':r.etag},body:JSON.stringify(body)})
   await load();setMessage('Reminder settings saved.')
  }catch(e){setError(e.message)}finally{setBusy(false)}
 }
 const dirty=!!data&&preferenceSnapshot(data)!==baseline,plan=data?reminderPlan(data):null
 return <main className="workspace-page reminder-settings-page">
  <div className="page-heading"><div><h1>Email reminders</h1><p>Choose the timing and the people who receive each email.</p></div><button type="button" disabled={busy||dirty} onClick={()=>{setError('');load().catch(e=>setError(e.message))}}><Icon name="refresh-cw"/>Refresh status</button></div>
  {error&&<p role="alert">{error}</p>}
  {data&&<form onSubmit={save} onInvalidCapture={e=>{const panel=e.target.closest('details');if(panel)panel.open=true}}>
   <div className="settings-section reminder-service"><p><Icon name="mail"/>{data.emailMode==='preview'?'Local preview · emails are saved here and never sent.':data.emailMode==='smtp'?'Email service connected.':'Email service is not connected. Ask your administrator.'}</p><p role="status">{data.schedulerStatus?.status==='preview'?'Automatic checks: local preview only.':data.schedulerStatus?.status==='running'?'Automatic checks are running.':data.schedulerStatus?.status==='stale'?'Automatic checks have stopped. Ask your administrator to check the scheduler.':data.schedulerStatus?.status==='not-running'?'Waiting for the first successful automatic check.':'Automatic checks are not connected.'}{data.schedulerStatus?.lastRunAt&&<> Last checked: {new Date(data.schedulerStatus.lastRunAt).toLocaleString('en-NZ',{timeZone:'Pacific/Auckland'})}.</>}</p></div>
   <section className="settings-section reminder-rule reminder-timesheet">
    <div className="reminder-rule-heading"><div><h2><Icon name="calendar"/>Time sheet reminders</h2><p>For the previous completed week · Monday to Sunday</p></div><Automatic checked={data.automaticTimesheets} onChange={v=>change('automaticTimesheets',v)} label="Enable time sheet reminders"/></div>
    <div className="reminder-timesheet-body"><div className="reminder-timing">
     <fieldset className="reminder-timing-step"><legend><span>1</span> Submission deadline</legend><p className="report-hint">Set a day in the following week. All times are Auckland time.</p><div className="reminder-field-pair"><label className="vehicle-field">Deadline day<select value={data.timesheetWeekday} onChange={e=>change('timesheetWeekday',Number(e.target.value))}>{['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'].map((d,i)=><option key={d} value={i}>{d}</option>)}</select></label><label className="vehicle-field">Deadline time<TimeEntry label="Deadline time" step={60} required value={data.timesheetTime} onChange={value=>change('timesheetTime',value)}/></label></div></fieldset>
     <div className="reminder-field-pair reminder-step-pair"><fieldset className="reminder-timing-step"><legend><span>2</span> First reminder</legend><label className="vehicle-field">Hours before deadline<input type="number" min={0} max={168} required value={data.timesheetLeadHours} onChange={e=>change('timesheetLeadHours',Number(e.target.value))}/></label><p className="report-hint">Only after the week has finished.</p></fieldset><fieldset className="reminder-timing-step"><legend><span>3</span> Follow-up reminders</legend><label className="vehicle-field">Repeat every (hours)<input type="number" min={1} max={168} required value={data.timesheetRepeatHours} onChange={e=>change('timesheetRepeatHours',Number(e.target.value))}/></label><p className="report-hint">Up to 3 more emails. Use 24 for once a day.</p></fieldset></div>
     <div className="reminder-plan" aria-live="polite"><h3>{plan?`Schedule for ${plan.weekLabel}`:'Your email schedule'} <small>Auckland time</small></h3>{plan?<><ol>{plan.slots.map((slot,i)=><li key={i}><span className="reminder-plan-dot">{i+1}</span><span><strong>{i===0?'First email':`Follow-up ${i}`}</strong><time>{slot.label}</time></span></li>)}</ol>{plan.clamped&&<p className="report-hint">The lead time falls before the week ends, so the first email waits until Monday at midnight.</p>}<p className="report-hint">This preview assumes each check runs on time. If delayed, follow-ups remain at least {data.timesheetRepeatHours} hours apart.</p></>:<p>Enter valid timing to preview the schedule.</p>}<p className="reminder-stop"><Icon name="check-circle"/>Stops as soon as that week’s time sheet is submitted. Maximum 4 automatic emails per person, per week.</p></div>
    </div><Recipients kind="timesheet" data={data} onChange={change}/></div>
   </section>
   <div className="reminder-other-rules">
    <OtherRule title="Vehicle check reminders" summary={data.automaticVehicles?'Automatic emails on':'Automatic emails off'}><div><label className="vehicle-field">Days before due date<input type="number" min={0} max={30} required value={data.vehicleLeadDays} onChange={e=>change('vehicleLeadDays',Number(e.target.value))}/></label><Automatic checked={data.automaticVehicles} onChange={v=>change('automaticVehicles',v)}/><p className="report-hint">Remind selected staff about their assigned vehicle. Once daily while due. The latest check sets the due date; no recorded check means due now.</p></div><Recipients kind="vehicle" data={data} onChange={change}/></OtherRule>
    <OtherRule title="Leave notifications" summary="Submission confirmations and decisions"><p className="report-hint">Selected admins are notified when leave is submitted. The technician receives a confirmation and an approval or rejection email, with the reason for rejection. Private leave reasons stay in Leave forms.</p><Recipients kind="leave" data={data} onChange={change}/></OtherRule>
    <OtherRule title="Stock take reminders" summary={data.automaticStocktakes?'Automatic emails on':'Automatic emails off'}><div><label className="vehicle-field">Stock take every (days)<input type="number" min={1} max={730} required value={data.stocktakeIntervalDays} onChange={e=>change('stocktakeIntervalDays',Number(e.target.value))}/></label><Automatic checked={data.automaticStocktakes} onChange={v=>change('automaticStocktakes',v)}/><p className="report-hint">Last completed: <strong>{dateLabel(data.stocktakeLastCompleted)}</strong><br/>Next due: <strong>{dateLabel(data.stocktakeNextDue)}</strong>. Once daily when due. Shared with Stock settings.</p></div><Recipients kind="stocktake" data={data} onChange={change}/></OtherRule>
   </div>
   <div className="reminder-save-bar"><button className="primary-action" disabled={busy}>{busy?'Saving…':'Save reminder settings'}</button><button type="button" disabled={busy||!dirty} onClick={()=>{setError('');setMessage('');load().catch(e=>setError(e.message))}}>Undo changes</button><span role="status">{message||(dirty?'Unsaved changes':'All settings saved')}</span></div>
  </form>}
  <MailHistory request={request}/>
 </main>
}
