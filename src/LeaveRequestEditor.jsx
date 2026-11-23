import TimeEntry from './TimeEntry'
import {DEFAULT_LEAVE_TYPE,LEAVE_TYPE_OPTIONS,leaveTypeInfo} from './leaveTypes'
import {defaultLeaveDay,leaveDates,leaveCalculation} from './leaveRequestModel'

const label=date=>new Date(date+'T12:00:00').toLocaleDateString('en-NZ',{weekday:'short',day:'numeric',month:'short'})

export default function LeaveRequestEditor({form,setForm,technicians,lunchStart='12:00',busy,onSubmit,onCancel}){
 const defaultType=LEAVE_TYPE_OPTIONS.some(option=>option.value===form.leaveType)?form.leaveType:DEFAULT_LEAVE_TYPE
 const dates=leaveDates(form)
 const rows=dates.map(date=>{
  const fallback=defaultLeaveDay(date,lunchStart,defaultType),stored=form.dailyBreakdown?.find(row=>row.date===date)
  return stored?{...fallback,...stored,leaveType:stored.leaveType||defaultType}:fallback
 })
 const calculations=rows.map(leaveCalculation),total=calculations.reduce((sum,item)=>sum+item.hours,0),paidTotal=calculations.reduce((sum,item)=>sum+(item.paid?item.hours:0),0),unpaidTotal=total-paidTotal,hasOtherType=rows.some(row=>leaveTypeInfo(row.leaveType).category==='other'),valid=rows.length>0&&calculations.every(item=>item.valid)&&(!hasOtherType||!!form.other?.trim())
 const edit=(key,value)=>setForm(current=>({...current,[key]:value}))
 const update=(date,key,value)=>{const resetsLunch=['duration','startTime','endTime','lunchChoice'].includes(key),next=rows.map(row=>row.date===date?{...row,[key]:value,...(resetsLunch?{lunchConfirmed:false}:{})}:row);edit('dailyBreakdown',next)}
 const setDefaultType=value=>setForm(current=>({...current,leaveType:value,dailyBreakdown:rows.map(row=>({...row,leaveType:row.leaveType===defaultType?value:row.leaveType}))}))
 const setLunch=(row,choice)=>{const usual=defaultLeaveDay(row.date,lunchStart,row.leaveType);edit('dailyBreakdown',rows.map(item=>item.date===row.date?{...item,lunchChoice:choice,lunchConfirmed:false,...(choice==='usual'?{lunchStart:usual.lunchStart,lunchEnd:usual.lunchEnd}:{})}:item))}
 function submit(event){event.preventDefault();if(!valid)return;onSubmit(event,{...form,leaveType:rows[0]?.leaveType||defaultType,hoursPerDay:8,startTime:'',endTime:'',dailyBreakdown:rows})}
 return <form className="leave-form vehicle-form-card" onSubmit={submit}>
  <div className="leave-form-heading"><h2>New leave request</h2><p className="leave-total">{rows.length} working day{rows.length===1?'':'s'} · {total.toFixed(2)} hours{unpaidTotal>0?` · ${paidTotal.toFixed(2)} paid / ${unpaidTotal.toFixed(2)} unpaid`:''}</p></div>
  <div className="leave-form-body">
   <fieldset disabled={busy} className="leave-editor-fields">
    <div className="leave-field-grid">
     <label className="vehicle-field">Technician *<select aria-label="Leave technician" required value={form.technician} onChange={event=>edit('technician',event.target.value)}>{technicians.map(person=><option key={person.name}>{person.name}</option>)}</select></label>
     <label className="vehicle-field">Default leave type *<select aria-label="Default leave type" value={defaultType} onChange={event=>setDefaultType(event.target.value)}>{LEAVE_TYPE_OPTIONS.map(option=><option key={option.value}>{option.value}</option>)}</select></label>
     {hasOtherType&&<label className="vehicle-field">Other leave description *<input required aria-label="Other leave description" maxLength={200} value={form.other||''} onChange={event=>edit('other',event.target.value)}/></label>}
     <label className="vehicle-field">From date *<input aria-label="Leave from date" required type="date" value={form.startDate} onInput={event=>edit('startDate',event.target.value)}/></label>
     <label className="vehicle-field">To date *<input aria-label="Leave to date" required type="date" min={form.startDate} value={form.endDate} onInput={event=>edit('endDate',event.target.value)}/></label>
    </div>
    <label className="leave-weekends"><input type="checkbox" checked={form.includeWeekends} onChange={event=>edit('includeWeekends',event.target.checked)}/>Include Saturday and Sunday</label>
    <p className="report-hint">The default applies to every day, and you can choose a different leave type for any individual day below. Full-day leave defaults to 8 hours. Part-day leave excludes only overlapping unpaid lunch.</p>
    <div className="leave-daily-editors">{rows.map((row,index)=><section className="leave-day-editor" key={row.date}>
     <div className="leave-day-heading">
      <h3>{label(row.date)}</h3>
      <div className="leave-day-controls">
       <label><span>Leave type</span><select aria-label={`Leave type ${row.date}`} value={row.leaveType} onChange={event=>update(row.date,'leaveType',event.target.value)}>{LEAVE_TYPE_OPTIONS.map(option=><option key={option.value}>{option.value}</option>)}</select></label>
       <label><span>Duration</span><select aria-label={`Duration ${row.date}`} value={row.duration} onChange={event=>update(row.date,'duration',event.target.value)}><option value="full">Full day · 8 hours</option><option value="part">Part day / hourly</option></select></label>
      </div>
     </div>
     {row.duration==='part'&&<>
      <div className="leave-time-pair"><label className="vehicle-field">From *<TimeEntry label={`Leave from ${row.date}`} required value={row.startTime} onChange={value=>update(row.date,'startTime',value)}/></label><label className="vehicle-field">To *<TimeEntry label={`Leave to ${row.date}`} allowEndOfDay required value={row.endTime} onChange={value=>update(row.date,'endTime',value)}/></label></div>
      <fieldset className="leave-lunch"><legend>Confirm unpaid lunch</legend><p>Which unpaid lunch arrangement applies to this working day?</p>{[['usual',`Usual lunch (${lunchStart}–${defaultLeaveDay(row.date,lunchStart,row.leaveType).lunchEnd})`],['none','No unpaid lunch applies']].map(([choice,text])=><label key={choice}><input type="radio" name={`lunch-${row.date}`} checked={row.lunchChoice===choice} onChange={()=>setLunch(row,choice)}/>{text}</label>)}{row.lunchChoice==='none'&&<label className="vehicle-field">Reason for correction *<input required maxLength={1000} aria-label={`Lunch reason ${row.date}`} value={row.lunchReason} onChange={event=>update(row.date,'lunchReason',event.target.value)}/></label>}<p className="leave-calculation">{((Number.isFinite(calculations[index].hours)?calculations[index].hours:0)+calculations[index].lunch).toFixed(2)}h absent − {calculations[index].lunch.toFixed(2)}h unpaid lunch = <strong>{calculations[index].hours.toFixed(2)}h leave</strong></p><label><input type="checkbox" checked={row.lunchConfirmed} disabled={!row.lunchChoice} onChange={event=>update(row.date,'lunchConfirmed',event.target.checked)}/>I confirm this lunch arrangement for {label(row.date)}</label><small>Corrections are shown to the approver. Changing times requires confirmation again.</small></fieldset>
     </>}
    </section>)}</div>
    <label className="vehicle-field">Reason / notes *<textarea aria-label="Leave reason" required rows={2} maxLength={4000} value={form.reason} onChange={event=>edit('reason',event.target.value)}/></label>
   </fieldset>
   {rows.length>0&&<aside className="leave-summary-panel" aria-label="Leave summary"><div className="leave-summary-sticky"><div className="leave-summary-heading"><div><span>Request summary</span><h3>Leave breakdown</h3></div><strong>{total.toFixed(2)}h</strong></div><div className="leave-summary-count">{rows.length} working day{rows.length===1?'':'s'}{unpaidTotal>0?` · ${paidTotal.toFixed(2)} paid · ${unpaidTotal.toFixed(2)} unpaid`:''}</div><table className="leave-breakdown leave-breakdown-compact"><thead><tr><th>Date</th><th>Leave</th></tr></thead><tbody>{rows.map((row,index)=><tr key={row.date}><td><b>{label(row.date)}</b><small>{row.leaveType} · {row.duration==='full'?'Full day · no lunch excluded':`${row.startTime}–${row.endTime} · ${calculations[index].lunch.toFixed(2)}h lunch excluded`}</small></td><td><strong>{calculations[index].hours.toFixed(2)}h</strong><small>{calculations[index].paid?'Paid':'Unpaid'}</small></td></tr>)}</tbody></table></div></aside>}
  </div>
  <div className="settings-actions"><button type="button" disabled={busy} onClick={onCancel}>Cancel</button><button className="primary-action" type="submit" disabled={busy||!valid}>{busy?'Submitting…':'Submit'}</button></div>
 </form>
}

export function SavedLeaveBreakdown({request}){
 if(!request.dailyBreakdown)return null
 return <div className="table-scroll"><table className="leave-breakdown"><thead><tr><th>Date</th><th>Leave</th><th>From–To</th><th>Lunch excluded</th><th>Lunch confirmation / correction</th></tr></thead><tbody>{request.dailyBreakdown.map(row=>{const type=row.leaveType||request.leaveType,paid=leaveTypeInfo(type).paid;return <tr key={row.date}><td>{label(row.date)}<small>{type} · {paid?'Paid':'Unpaid'}</small></td><td>{row.hoursPerDay.toFixed(2)}h</td><td>{row.duration==='full'?'Full day':row.startTime+'–'+row.endTime}</td><td>{row.duration==='full'?'—':row.lunchHours.toFixed(2)+'h'}</td><td>{row.duration==='full'?'8h default':`${row.lunchChoice==='none'?'No unpaid lunch':row.lunchStart+'–'+row.lunchEnd} · Confirmed${row.lunchReason?' · '+row.lunchReason:''}`}</td></tr>})}</tbody></table></div>
}
