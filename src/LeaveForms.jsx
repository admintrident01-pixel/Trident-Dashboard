import SortableTable from './SortableTable'
import {defaultLeaveTechnician} from './leaveDefaults'
import LeaveRequestEditor,{SavedLeaveBreakdown} from './LeaveRequestEditor'
import {leaveOperationId,mergeLeaveRequest,refreshLeaveRequests,saveLeaveOperation} from './leaveSync.js'
import './LeaveForms.css'
import {useEffect,useRef,useState} from 'react'

const today=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Pacific/Auckland',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())

const label=d=>new Date(d+'T12:00:00').toLocaleDateString('en-NZ')

export default function LeaveForms({request,active,onChanged,isAdmin,technician}){

 const [data,setData]=useState(null),[form,setForm]=useState(null),[selected,setSelected]=useState(null),[notes,setNotes]=useState(''),[filter,setFilter]=useState('Pending'),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false)
 const busyRef=useRef(false),loadEpoch=useRef(0),decisionOperation=useRef(null)

 useEffect(()=>{
  if(!active)return
  let cancelled=false,inFlight=false
  const refresh=async()=>{
   if(inFlight||busyRef.current||document.visibilityState==='hidden')return
   inFlight=true;const epoch=++loadEpoch.current
   try{const r=await request('/api/leave',{cache:'no-store'});if(!cancelled&&epoch===loadEpoch.current)setData(r.data)}
   catch(e){if(!cancelled&&epoch===loadEpoch.current)setError(e.message)}
   finally{inFlight=false}
  }
  refresh();const timer=setInterval(refresh,30000)
  window.addEventListener('focus',refresh);window.addEventListener('trident-leave-updated',refresh);document.addEventListener('visibilitychange',refresh)
  return()=>{cancelled=true;clearInterval(timer);window.removeEventListener('focus',refresh);window.removeEventListener('trident-leave-updated',refresh);document.removeEventListener('visibilitychange',refresh)}
 },[request,active])

 async function reload(){if(busyRef.current)return;setError('');const epoch=++loadEpoch.current;try{if(await refreshLeaveRequests(request,{accept:()=>epoch===loadEpoch.current,onData:setData,setSelected}))setMessage('Leave requests refreshed. Your unfinished form and decision notes are kept.')}catch(e){setError(e.message)}}

 function newRequest(){setSelected(null);setError('');setMessage('');setForm({operationId:leaveOperationId(),technician:defaultLeaveTechnician(data.technicians,technician),leaveType:'Annual leave',other:'',startDate:today(),endDate:today(),dailyBreakdown:[],hoursPerDay:8,includeWeekends:false,reason:''})}

 const checkingSave=()=>setMessage('Checking whether your leave save completed… Your details are kept.')

 async function submit(e,payload=form){e.preventDefault();if(busyRef.current)return;busyRef.current=true;loadEpoch.current++;setBusy(true);setError('');setMessage('');try{const r=await saveLeaveOperation(request,'/api/leave',payload,checkingSave);setData(current=>mergeLeaveRequest(current,r.data.request));setForm(null);setSelected(r.data.request);setFilter(r.data.request.status);setNotes('');setMessage(r.data.request.status==='Pending'?'Leave request submitted. Awaiting approval; it will not fill the time sheet until approved.':`This leave request was already saved. Its current status is ${r.data.request.status.toLowerCase()}.`);onChanged()}catch(e){setMessage('');setError(e.message)}finally{busyRef.current=false;setBusy(false)}}

 async function decide(status){if(busyRef.current)return;if(status==='Declined'&&!notes.trim()){setError('Enter a reason for declining this request.');return}const command={id:selected.id,revision:selected.revision,status,decisionNotes:notes},identity=JSON.stringify(command);if(decisionOperation.current?.identity!==identity)decisionOperation.current={identity,operationId:leaveOperationId()};busyRef.current=true;loadEpoch.current++;setBusy(true);setError('');setMessage('');try{const r=await saveLeaveOperation(request,'/api/leave-decision',{...command,operationId:decisionOperation.current.operationId},checkingSave);setData(current=>mergeLeaveRequest(current,r.data.request));setSelected(r.data.request);setMessage(r.data.request.status==='Approved'?'Leave approved. It will fill the matching technician’s time sheet and appear on the schedule.':r.data.request.status==='Cancelled'?'Leave cancelled. It will no longer appear on the schedule or fill future time sheet entries.':'Leave request declined.');setNotes('');onChanged()}catch(e){setMessage('');setError(e.message)}finally{busyRef.current=false;setBusy(false)}}

 const visible=data?.requests.filter(r=>filter==='All'||r.status===filter).sort((a,b)=>b.submittedAt.localeCompare(a.submittedAt))||[],latestSelected=data?.requests.find(item=>item.id===selected?.id),selectedChanged=!!selected&&!!data&&latestSelected?.revision!==selected.revision

 return <main className="workspace-page leave-page"><div className="page-heading"><div><h1>Leave forms</h1><p>Submit leave requests, manage approvals and sync approved leave to time sheets and the schedule.</p></div><div className="settings-actions"><button disabled={busy} onClick={reload}>Refresh requests</button>{data&&<button className="primary-action" disabled={busy||!!form||!data.technicians.length} onClick={newRequest}>New leave request</button>}</div></div>{error&&<div role="alert">{error} <button className="inline-button" onClick={reload}>Reload saved requests</button></div>}{message&&<p role="status" className="save-message">{message}</p>}{!data&&!error&&<p role="status">Loading leave requests…</p>}

 {form&&<LeaveRequestEditor form={form} setForm={setForm} technicians={data.technicians} lunchStart={data.lunchStart} busy={busy} onSubmit={submit} onCancel={()=>setForm(null)}/>}

 {data&&<><div className="leave-summary">{['Pending','Approved','Declined','Cancelled'].map(status=><button key={status} className={`leave-pill leave-${status.toLowerCase()}`} aria-pressed={filter===status} onClick={()=>setFilter(status)}>{status} · {data.requests.filter(r=>r.status===status).length}</button>)}<button className="leave-pill" aria-pressed={filter==='All'} onClick={()=>setFilter('All')}>All requests / history</button></div><section className="vehicle-history"><h2>{filter==='Pending'?'Awaiting approval':'Leave request history'}</h2><div className="table-scroll"><SortableTable paginate paginationLabel="leave requests" paginationReset={filter}><thead><tr><th>Technician</th><th>Leave type</th><th>Dates</th><th>Hours</th><th>Status</th><th>Actions</th></tr></thead><tbody>{visible.map(r=><tr key={r.id}><td>{r.technician}</td><td>{r.leaveType==='Other'?r.other:r.leaveType}</td><td data-sort-value={r.startDate}>{label(r.startDate)} – {label(r.endDate)}{r.startTime&&<small>{r.startTime}–{r.endTime} each day</small>}</td><td>{r.totalHours}</td><td><span className={`leave-pill leave-${r.status.toLowerCase()}`}>{r.status}</span></td><td><button disabled={busy} aria-label={`Review leave ${r.technician} ${r.startDate}`} onClick={()=>{setSelected(r);setNotes('');setError('');setMessage('')}}>{isAdmin&&r.status==='Pending'?'Review':'View'}</button></td></tr>)}</tbody></SortableTable></div>{!visible.length&&<p>No {filter==='All'?'leave':filter.toLowerCase()} requests.</p>}</section></>}

 {selected&&<section className="leave-detail vehicle-form-card"><div className="page-heading"><h2>Leave request · {selected.technician}</h2><span className={`leave-pill leave-${selected.status.toLowerCase()}`}>{selected.status}</span></div><dl><dt>Leave type</dt><dd>{selected.leaveType==='Other'?selected.other:selected.leaveType}</dd><dt>Dates</dt><dd>{label(selected.startDate)} – {label(selected.endDate)}</dd><dt>Time each day</dt><dd>{selected.dailyBreakdown?'See daily breakdown below':selected.startTime?selected.startTime+'–'+selected.endTime:'Full day · existing request'}</dd><dt>Paid leave hours</dt><dd>{selected.dailyBreakdown?'Per-date hours below':selected.hoursPerDay+' per day'} · {selected.totalHours} total</dd><dt>Reason / notes</dt><dd>{selected.reason}</dd><dt>Leave days</dt><dd>{selected.dates.map(label).join(', ')}</dd>{selected.decidedAt&&<><dt>Decision</dt><dd>{selected.status} by {selected.decidedBy} · {new Date(selected.decidedAt).toLocaleString('en-NZ',{timeZone:'Pacific/Auckland'})}</dd><dt>Decision notes</dt><dd>{selected.decisionNotes||'—'}</dd></>}</dl><SavedLeaveBreakdown request={selected}/>{selectedChanged&&<p role="status">This request changed in the background. Your decision notes are kept. <button disabled={busy} className="inline-button" onClick={()=>{setSelected(latestSelected||null);setError('')}}>Review latest saved request</button></p>}{isAdmin&&['Pending','Approved'].includes(selected.status)&&<><label className="vehicle-field">Decision notes{selected.status==='Pending'?' (required when declining)':''}<textarea aria-label="Leave decision notes" disabled={busy} rows={3} maxLength={2000} value={notes} onChange={e=>setNotes(e.target.value)}/></label><div className="settings-actions">{selected.status==='Pending'&&<><button className="primary-action" disabled={busy||selectedChanged} onClick={()=>decide('Approved')}>Approve leave</button><button disabled={busy||selectedChanged} onClick={()=>decide('Declined')}>Decline leave</button></>}<button disabled={busy||selectedChanged} onClick={()=>decide('Cancelled')}>Cancel leave request</button></div></>}<p className="report-hint">Approved leave syncs to matching time sheet dates and blocks the matching hours on the schedule. Cancelling it stops future syncing; previously submitted time sheets remain in history.</p><button disabled={busy} className="inline-button" onClick={()=>setSelected(null)}>Close request</button></section>}

 </main>

}

