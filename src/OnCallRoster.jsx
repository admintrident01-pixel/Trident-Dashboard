import Icon from './Icon'
import {useCallback,useEffect,useState} from 'react'
import './OnCallRoster.css'

const STATUS={
 accepted:{label:'Accepted',tone:'green'},
 awaiting:{label:'Awaiting accept',tone:'amber'},
 open:{label:'Open',tone:'amber'},
 scheduled:{label:'Scheduled',tone:'grey'},
}

function statusOf(row){return STATUS[row.status]||STATUS.scheduled}

function acceptedTime(value){
 if(!value)return ''
 return new Intl.DateTimeFormat('en-NZ',{hour:'numeric',minute:'2-digit',timeZone:'Pacific/Auckland'}).format(new Date(value))
}

function activityTime(value){
 if(!value)return ''
 return new Intl.DateTimeFormat('en-NZ',{day:'numeric',month:'short',hour:'numeric',minute:'2-digit',timeZone:'Pacific/Auckland'}).format(new Date(value))
}

function WeekHalf({row,label,next,busy,onAccept,onGrab,onHandover,onRelease,onResend}){
 const status=statusOf(row)
 const showManage=row.canHandover&&(!next||row.mine||row.status==='open')
 const showRelease=row.canRelease&&(!next||row.mine)
 return <div className={'oncall-half'+(next?' next':'')}>
  <div className="oncall-wlabel"><span>{label}</span><span className={'oncall-state '+status.tone}><i/>{row.statusLabel}</span></div>
  <h2 className={row.technician?'':'muted'}>{row.technician||'Open to anyone'}</h2>
  <p className="oncall-dates">{row.datesLong}</p>
  {row.status==='accepted'&&row.acceptedAt&&<p className="oncall-accepted">Accepted {acceptedTime(row.acceptedAt)}</p>}
  {row.status==='awaiting'&&<p className="oncall-hint">{row.isCurrent?'Accept to confirm you are on call this week.':`Accept by ${row.deadlineLabel} or it moves to the open pool.`}</p>}
  {row.status==='open'&&<p className="oncall-hint">Any technician can grab this week.</p>}
  <div className="oncall-actions">
   {row.canAccept&&<button className="oncall-btn primary" disabled={busy} onClick={()=>onAccept(row)}><Icon name="check" size={14}/>Accept on call</button>}
   {showManage&&<button className={'oncall-btn'+(row.canAccept?'':' primary')} disabled={busy} onClick={()=>onHandover(row)}><Icon name="repeat" size={14}/>Hand over</button>}
   {showRelease&&<button className="oncall-btn" disabled={busy} onClick={()=>onRelease(row)}><Icon name="users" size={14}/>Release to pool</button>}
   {row.canGrab&&<button className="oncall-btn primary" disabled={busy} onClick={()=>onGrab(row)}><Icon name="users" size={14}/>Grab this week</button>}
   {row.canResend&&<button className="oncall-text" disabled={busy} onClick={()=>onResend(row)}><Icon name="mail" size={13}/>Resend email</button>}
  </div>
 </div>
}

function RowAction({row,busy,onAccept,onGrab,onHandover,onResend}){
 if(row.status==='open'){
  if(row.canHandover)return <button className="oncall-btn tiny" disabled={busy} onClick={()=>onHandover(row)}>Assign</button>
  return row.canGrab?<button className="oncall-btn tiny" disabled={busy} onClick={()=>onGrab(row)}>Grab</button>:<span className="oncall-dash">—</span>
 }
 if(row.status==='awaiting'){
  if(row.canAccept)return <button className="oncall-text" disabled={busy} onClick={()=>onAccept(row)}><Icon name="check" size={12}/>Accept</button>
  if(row.canResend)return <button className="oncall-text" disabled={busy} onClick={()=>onResend(row)}>Resend</button>
 }
 if(row.status==='accepted'&&row.canHandover)return <button className="oncall-text" disabled={busy} onClick={()=>onHandover(row)}>Hand over <Icon name="arrow-right" size={12}/></button>
 return <span className="oncall-dash">—</span>
}

export default function OnCallRoster({request}){
 const [data,setData]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[focus,setFocus]=useState(0)
 const [dialog,setDialog]=useState(null),[selectedTech,setSelectedTech]=useState(''),[orderDraft,setOrderDraft]=useState([]),[planDraft,setPlanDraft]=useState([]),[eligibleDraft,setEligibleDraft]=useState([])

 const load=useCallback(async()=>{
  const result=await request('/api/on-call',{cache:'no-store'})
  setData(result.data)
  return result.data
 },[request])

 useEffect(()=>{
  let active=true
  request('/api/on-call',{cache:'no-store'}).then(result=>{if(active)setData(result.data)}).catch(problem=>{if(active)setError(problem.message)})
  return()=>{active=false}
 },[request])

 useEffect(()=>{
  if(!data)return
  const refresh=()=>{if(document.visibilityState==='hidden')return;load().catch(()=>{})}
  const timer=setInterval(refresh,60000)
  window.addEventListener('focus',refresh)
  document.addEventListener('visibilitychange',refresh)
  return()=>{clearInterval(timer);window.removeEventListener('focus',refresh);document.removeEventListener('visibilitychange',refresh)}
 },[data,load])

 useEffect(()=>{
  if(!dialog)return
  const close=event=>{if(event.key==='Escape'&&!busy)setDialog(null)}
  window.addEventListener('keydown',close)
  return()=>window.removeEventListener('keydown',close)
 },[dialog,busy])

 function openHandover(row){setSelectedTech('');setDialog({type:'handover',row})}
 function openOrder(){setOrderDraft([...(data?.order||[])]);setDialog({type:'order'})}
 function openPlan(){setPlanDraft((data?.defaultPlan||[]).map(row=>({...row})));setDialog({type:'plan'})}
 function openEligibility(){setEligibleDraft([...(data?.eligible||[])]);setDialog({type:'eligibility'})}
 function openActivity(){setDialog({type:'activity'})}
 function closeDialog(){if(!busy)setDialog(null)}

 async function act(payload){
  if(busy)return
  setBusy(true);setError('');setNotice('')
  try{
   const result=await request('/api/on-call',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)})
   setData(result.data);setDialog(null)
   const row=result.data.rows.find(item=>item.weekStart===payload.weekStart)
   const number=row?.weekNumber||''
   if(payload.action==='accept')setNotice('Week '+number+' accepted. You are on call.')
   else if(payload.action==='grab')setNotice('Week '+number+' is yours. You are on call.')
   else if(payload.action==='release')setNotice('Week '+number+' is now open to all technicians.')
   else if(payload.action==='handover')setNotice(payload.technician?'Week '+number+' has been handed over.':'Week '+number+' is now open to all technicians.')
   else if(payload.action==='order')setNotice('Rotation order saved. Future weeks now follow the new order.')
   else if(payload.action==='plan')setNotice('Next three months confirmed. Every planned week now follows this roster.')
   else if(payload.action==='eligibility')setNotice('On-call staff selection saved.')
   else if(payload.action==='resend')setNotice('Acceptance email queued for '+row?.technician+'.')
   window.dispatchEvent(new Event('trident-mail-updated'))
  }catch(problem){setError(problem.message)}
  finally{setBusy(false)}
 }

 function accept(row){act({action:'accept',weekStart:row.weekStart})}
 function grab(row){
  if(!window.confirm('Grab Week '+row.weekNumber+'? You will be on call and everyone will be emailed.'))return
  act({action:'grab',weekStart:row.weekStart})
 }
 function release(row){
  if(!window.confirm('Release Week '+row.weekNumber+' to the open pool? Any technician can then grab it.'))return
  act({action:'release',weekStart:row.weekStart})
 }
 function resend(row){act({action:'resend',weekStart:row.weekStart})}
 function toggleEligible(name){setEligibleDraft(current=>current.includes(name)?current.filter(item=>item!==name):[...current,name])}
 function setPlanWeek(weekStart,name){setPlanDraft(current=>current.map(row=>row.weekStart===weekStart?{...row,technician:name}:row))}
 function move(index,delta){
  setOrderDraft(current=>{
   const next=[...current],target=index+delta
   if(target<0||target>=next.length)return current
   const [item]=next.splice(index,1);next.splice(target,0,item)
   return next
  })
 }

 if(!data)return <main className="oncall-page"><div className="oncall-head"><div><h1>On call</h1><p>Loading this week’s roster…</p></div></div>{error&&<p role="alert" className="oncall-alert">{error} <button className="oncall-text" onClick={()=>{setError('');load().catch(problem=>setError(problem.message))}}>Try again</button></p>}</main>

 const rows=data.rows,maxFocus=Math.max(0,rows.length-2),index=Math.min(focus,maxFocus),current=rows[index],next=rows[index+1]

 return <main className="oncall-page">
  <div className="oncall-head">
   <div><h1>On call</h1><p>Week {data.weekNumber} · {data.headerDates}</p></div>
   <div className="oncall-switch" role="group" aria-label="Roster week">
    <button aria-label="Previous week" disabled={index===0} onClick={()=>setFocus(Math.max(0,index-1))}><Icon name="chevron-left" size={18}/></button>
    <button className="oncall-switch-current" onClick={()=>setFocus(0)}><Icon name="calendar" size={15}/>{index===0?'This week':'Week '+current.weekNumber}</button>
    <button aria-label="Next week" disabled={index>=maxFocus} onClick={()=>setFocus(Math.min(maxFocus,index+1))}><Icon name="chevron-right" size={18}/></button>
   </div>
  </div>

  {error&&<p role="alert" className="oncall-alert">{error}</p>}
  {notice&&<p role="status" className="oncall-notice">{notice}</p>}

  <section className="oncall-card oncall-weeks" aria-label="Current and next on-call weeks">
   <WeekHalf row={current} label={index===0?'This week':'Week '+current.weekNumber} busy={busy} onAccept={accept} onGrab={grab} onHandover={openHandover} onRelease={release} onResend={resend}/>
   <WeekHalf row={next} label={index===0?'Next week':'Week '+next.weekNumber} next busy={busy} onAccept={accept} onGrab={grab} onHandover={openHandover} onRelease={release} onResend={resend}/>
  </section>

  <section className="oncall-card oncall-roster">
   <div className="oncall-rhead">
    <div><h2>Roster</h2><p>One technician covers each week.</p></div>
    <div className="oncall-rright">
     {data.openWeeks>0&&<span className="oncall-open-count">{data.openWeeks} open week{data.openWeeks===1?'':'s'}</span>}
     <button className="oncall-text" onClick={openActivity}>Recent activity <Icon name="arrow-right" size={12}/></button>
    </div>
   </div>
   <div className="oncall-table-wrap">
    <table className="oncall-table">
     <thead><tr><th>Week</th><th>On call</th><th>Status</th><th><span className="oncall-sr">Action</span></th></tr></thead>
     <tbody>{rows.map(row=>{
      const status=statusOf(row)
      return <tr key={row.weekStart} className={row.isCurrent?'current':''}>
       <td><span className="oncall-week"><b>Week {row.weekNumber}</b><small>{row.dates}</small></span></td>
       <td><div className="oncall-who">
        {row.technician?<span className="oncall-avatar">{row.initials}</span>:<span className="oncall-open-icon"><Icon name="users" size={13}/></span>}
        <span className="oncall-who-text"><b className={row.technician?'':'muted'}>{row.technician||'Open to anyone'}</b><small className={'oncall-mini '+status.tone}>{row.statusLabel}</small></span>
       </div></td>
       <td><span className={'oncall-state '+status.tone}><i/>{row.statusLabel}</span></td>
       <td className="oncall-row-action"><RowAction row={row} busy={busy} onAccept={accept} onGrab={grab} onHandover={openHandover} onResend={resend}/></td>
      </tr>
     })}</tbody>
    </table>
   </div>
   <div className="oncall-rfoot"><Icon name="mail" size={14}/><span>Every change is emailed to all technicians and admins.</span><button className="oncall-text" onClick={openActivity}>Recent activity</button></div>
  </section>

  <section className="oncall-card oncall-order">
   <div className="oncall-otop">
    <span className="oncall-olabel">Rotation order <span className="oncall-admin">Admin</span></span>
    {data.isAdmin&&<div className="oncall-admin-actions"><button className="oncall-btn tiny" onClick={openEligibility}><Icon name="users" size={12}/>Who can be on call</button><button className="oncall-btn tiny" onClick={openPlan}><Icon name="calendar" size={12}/>Plan next 3 months</button><button className="oncall-btn tiny" onClick={openOrder}><Icon name="edit-2" size={12}/>Edit order</button></div>}
   </div>
   <div className="oncall-onames">{data.order.map((name,position)=><span className="oncall-oname" key={name}>{position>0&&<i aria-hidden="true">→</i>}<span>{name}</span></span>)}</div>
   <p className="oncall-onote">Sets who takes each new week. Position 1 is on call now.</p>
  </section>

  <div className="oncall-foot"><span>Week runs Monday 12:00 am – Sunday 11:59 pm · {data.timezone}</span><span>Week {data.weekNumber} of {data.year}</span></div>

  {dialog?.type==='handover'&&<div className="oncall-overlay" onMouseDown={event=>{if(event.target===event.currentTarget)closeDialog()}}>
   <div className="oncall-dialog" role="dialog" aria-modal="true" aria-labelledby="oncall-handover-title">
    <div className="oncall-dialog-head">
     <div><h2 id="oncall-handover-title">{dialog.row.status==='open'?'Assign':'Hand over'} Week {dialog.row.weekNumber}</h2><p>{dialog.row.technician&&dialog.row.technician+' · '}{dialog.row.datesLong}</p></div>
     <button className="oncall-icon-btn" aria-label="Close hand over" disabled={busy} onClick={closeDialog}><Icon name="x" size={16}/></button>
    </div>
    <fieldset className="oncall-choices"><legend>Choose a technician</legend>
     {dialog.row.handoverOptions.map(option=><label key={option.name} className={'oncall-choice'+(option.away?' away':'')}>
      <input type="radio" name="oncall-handover" value={option.name} checked={selectedTech===option.name} disabled={option.away||busy} onChange={event=>setSelectedTech(event.target.value)}/>
      <span>{option.name}</span>{option.away&&<small>Away</small>}
     </label>)}
     {dialog.row.status!=='open'&&<label className="oncall-choice open">
      <input type="radio" name="oncall-handover" value="__open__" checked={selectedTech==='__open__'} disabled={busy} onChange={event=>setSelectedTech(event.target.value)}/>
      <span className="oncall-open-icon"><Icon name="users" size={13}/></span>
      <span className="oncall-choice-text"><b>Open to everyone</b><small>Any technician can grab this week</small></span>
     </label>}
    </fieldset>
    <p className="oncall-dialog-note"><Icon name="mail" size={13}/>All technicians and admins will be emailed.</p>
    <div className="oncall-dialog-actions"><button className="oncall-btn" disabled={busy} onClick={closeDialog}>Cancel</button><button className="oncall-btn primary" disabled={busy||!selectedTech} onClick={()=>act({action:'handover',weekStart:dialog.row.weekStart,technician:selectedTech==='__open__'?'':selectedTech})}>{busy?'Saving…':'Confirm'}</button></div>
   </div>
  </div>}

  {dialog?.type==='order'&&<div className="oncall-overlay" onMouseDown={event=>{if(event.target===event.currentTarget)closeDialog()}}>
   <div className="oncall-dialog" role="dialog" aria-modal="true" aria-labelledby="oncall-order-title">
    <div className="oncall-dialog-head"><div><h2 id="oncall-order-title">Rotation order</h2><p>Position 1 is on call now, then the roster follows this order.</p></div><button className="oncall-icon-btn" aria-label="Close rotation order" disabled={busy} onClick={closeDialog}><Icon name="x" size={16}/></button></div>
    <ol className="oncall-order-list">{orderDraft.map((name,position)=><li key={name}><span className="oncall-order-pos">{position+1}</span><span>{name}</span><span className="oncall-order-move"><button aria-label={'Move '+name+' up'} disabled={busy||position===0} onClick={()=>move(position,-1)}><Icon name="chevron-up" size={14}/></button><button aria-label={'Move '+name+' down'} disabled={busy||position===orderDraft.length-1} onClick={()=>move(position,1)}><Icon name="chevron-down" size={14}/></button></span></li>)}</ol>
    <p className="oncall-dialog-note"><Icon name="mail" size={13}/>All technicians and admins will be emailed.</p>
    <div className="oncall-dialog-actions"><button className="oncall-btn" disabled={busy} onClick={closeDialog}>Cancel</button><button className="oncall-btn primary" disabled={busy||!orderDraft.length} onClick={()=>act({action:'order',order:orderDraft})}>{busy?'Saving…':'Save order'}</button></div>
   </div>
  </div>}

  {dialog?.type==='plan'&&<div className="oncall-overlay" onMouseDown={event=>{if(event.target===event.currentTarget)closeDialog()}}>
   <div className="oncall-dialog oncall-plan-dialog" role="dialog" aria-modal="true" aria-labelledby="oncall-plan-title">
    <div className="oncall-dialog-head"><div><h2 id="oncall-plan-title">Plan next three months</h2><p>{planDraft.length} weeks · starts from the default rotation order</p></div><button className="oncall-icon-btn" aria-label="Close three-month plan" disabled={busy} onClick={closeDialog}><Icon name="x" size={16}/></button></div>
    <p className="oncall-plan-help">Each week starts with the default rotation order. Change any week, then confirm to lock the plan.</p>
    <div className="oncall-plan-list">{planDraft.map(row=><label className="oncall-plan-row" key={row.weekStart}><span><b>Week {row.weekNumber}</b><small>{row.dates}</small></span><select aria-label={`On call for week ${row.weekNumber}`} disabled={busy} value={row.technician} onChange={event=>setPlanWeek(row.weekStart,event.target.value)}><option value="">Open to anyone</option>{(data.eligible||data.order).map(name=><option key={name} value={name}>{name}</option>)}</select></label>)}</div>
    <p className="oncall-dialog-note"><Icon name="mail" size={13}/>Confirming sends one summary email to all staff.</p>
    <div className="oncall-dialog-actions"><button className="oncall-btn" disabled={busy} onClick={closeDialog}>Cancel</button><button className="oncall-btn primary" disabled={busy||!planDraft.length} onClick={()=>act({action:'plan',plan:planDraft.map(({weekStart,technician})=>({weekStart,technician}))})}>{busy?'Saving…':'Confirm 3-month roster'}</button></div>
   </div>
  </div>}

  {dialog?.type==='eligibility'&&<div className="oncall-overlay" onMouseDown={event=>{if(event.target===event.currentTarget)closeDialog()}}>
   <div className="oncall-dialog" role="dialog" aria-modal="true" aria-labelledby="oncall-eligibility-title">
    <div className="oncall-dialog-head"><div><h2 id="oncall-eligibility-title">Who can be on call</h2><p>Choose from every staff member, including admins and office staff.</p></div><button className="oncall-icon-btn" aria-label="Close on-call staff selection" disabled={busy} onClick={closeDialog}><Icon name="x" size={16}/></button></div>
    <fieldset className="oncall-choices"><legend>Eligible staff</legend>
     {(data.staffOptions||[]).map(option=><label key={option.name} className={'oncall-choice'+(eligibleDraft.includes(option.name)?' is-selected':'')}>
      <input type="checkbox" checked={eligibleDraft.includes(option.name)} disabled={busy} onChange={()=>toggleEligible(option.name)}/>
      <span>{option.name}</span>{option.admin?<small>Admin</small>:option.staffType==='office'?<small>Office</small>:null}
     </label>)}
    </fieldset>
    <p className="oncall-dialog-note"><Icon name="users" size={13}/>Only selected staff appear in the rotation, handover list and open-week pool.</p>
    <div className="oncall-dialog-actions"><button className="oncall-btn" disabled={busy} onClick={closeDialog}>Cancel</button><button className="oncall-btn primary" disabled={busy||!eligibleDraft.length} onClick={()=>act({action:'eligibility',eligible:eligibleDraft})}>{busy?'Saving…':'Save staff selection'}</button></div>
   </div>
  </div>}

  {dialog?.type==='activity'&&<div className="oncall-overlay" onMouseDown={event=>{if(event.target===event.currentTarget)closeDialog()}}>
   <div className="oncall-dialog" role="dialog" aria-modal="true" aria-labelledby="oncall-activity-title">
    <div className="oncall-dialog-head"><div><h2 id="oncall-activity-title">Recent activity</h2><p>Every roster change is recorded here and emailed.</p></div><button className="oncall-icon-btn" aria-label="Close activity" onClick={closeDialog}><Icon name="x" size={16}/></button></div>
    {data.activity.length?<ul className="oncall-activity">{data.activity.map((item,position)=><li key={item.at+item.action+position}><span className="oncall-activity-dot"/><div><p>{item.detail}</p><small>{activityTime(item.at)}</small></div></li>)}</ul>:<p className="oncall-empty">No roster changes yet.</p>}
    <div className="oncall-dialog-actions"><button className="oncall-btn" onClick={closeDialog}>Close</button></div>
   </div>
  </div>}
 </main>
}
