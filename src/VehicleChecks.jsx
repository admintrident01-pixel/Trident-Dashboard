import SortableTable from './SortableTable'
import {useEffect,useState} from 'react'

import {checkDueStatus} from './vehicleStatus'

import ReminderDashboard from './ReminderDashboard'



function today(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Pacific/Auckland',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}

function dateLabel(value){return value?new Date(value+'T12:00:00').toLocaleDateString('en-NZ',{day:'2-digit',month:'short',year:'numeric'}):'—'}

function addDays(value,days){if(!value)return '';const d=new Date(value+'T12:00:00');d.setDate(d.getDate()+days);return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`}

function months(value){if(!value)return '';const a=new Date(today()+'T12:00:00'),b=new Date(value+'T12:00:00');return (b.getFullYear()-a.getFullYear())*12+b.getMonth()-a.getMonth()-(b.getDate()<a.getDate()?1:0)}

function remaining(due,odo){return due!==''&&due!==null&&due!==undefined&&odo!==''&&odo!==null&&odo!==undefined?Number(due)-Number(odo):''}

const number=n=>n===undefined||n===null||n===''?'—':Number(n).toLocaleString('en-NZ')

function latestFor(checks,id,baseline={}){const latest=checks.filter(c=>c.vehicleId===id).sort((a,b)=>b.checkDate.localeCompare(a.checkDate)||b.createdAt.localeCompare(a.createdAt))[0];return latest&&latest.checkDate>=(baseline.checkDate||'')?latest:undefined}

function assignedVehicle(v,techs){const tech=techs.find(t=>t.name.toLowerCase()===v.driver.toLowerCase());return {...v,registration:tech?.rego||v.registration}}

const metrics=[

 ['Check status','check',()=> ''],

 ['Registration','identity',v=>v.registration],['Make / Model','identity',v=>v.makeModel],['Driver','identity',v=>v.driver],['Active','active',v=>v.active?'TRUE':'FALSE'],

 ['Last Check','check',(_,c)=>dateLabel(c.checkDate)],['Next Check','check',(_,c)=>dateLabel(c.nextCheckDue||addDays(c.checkDate,30)),(_,c)=>!!c.checkDate&&(c.nextCheckDue||addDays(c.checkDate,30))<today()],

 ['WOF Expiry','wof',(_,c)=>dateLabel(c.wofExpiry),(_,c)=>!!c.wofExpiry&&c.wofExpiry<today()],['WOF Months to Expiry','wof',(_,c)=>number(months(c.wofExpiry))],

 ['Rego Expiry','rego',(_,c)=>dateLabel(c.regoExpiry),(_,c)=>!!c.regoExpiry&&c.regoExpiry<today()],['Rego Months to Expiry','rego',(_,c)=>number(months(c.regoExpiry))],

 ['RUC Current','ruc',(_,c)=>number(c.rucCurrent)],['RUC Due','ruc',(_,c)=>number(c.rucDue)],['RUC Remaining','ruc',(_,c)=>number(remaining((c.rucDue!==''&&c.rucDue!==null&&c.rucDue!==undefined?c.rucDue:c.rucCurrent),c.odometer)),(_,c)=>remaining((c.rucDue!==''&&c.rucDue!==null&&c.rucDue!==undefined?c.rucDue:c.rucCurrent),c.odometer)!==''&&remaining((c.rucDue!==''&&c.rucDue!==null&&c.rucDue!==undefined?c.rucDue:c.rucCurrent),c.odometer)<=0],

 ['Current Odometer','service',(_,c)=>number(c.odometer)],['Service Due','service',(_,c)=>dateLabel(c.serviceDue),(_,c)=>!!c.serviceDue&&c.serviceDue<today()],['Service Due KM','service',(_,c)=>number(c.serviceDueKm)],['Service KM Remaining','service',(_,c)=>number(remaining(c.serviceDueKm,c.odometer)),(_,c)=>remaining(c.serviceDueKm,c.odometer)!==''&&remaining(c.serviceDueKm,c.odometer)<=0],

 ['Wheel Alignment Due','alignment',(_,c)=>dateLabel(c.alignmentDue),(_,c)=>!!c.alignmentDue&&c.alignmentDue<today()],['Wheel Alignment Due KM','alignment',(_,c)=>number(c.alignmentDueKm)],['Wheel Alignment KM Remaining','alignment',(_,c)=>number(remaining(c.alignmentDueKm,c.odometer)),(_,c)=>remaining(c.alignmentDueKm,c.odometer)!==''&&remaining(c.alignmentDueKm,c.odometer)<=0],['Notes','notes',(_,c)=>c.comments],

]

function blankCheck(v,checks,count){const c={...v.baseline,...latestFor(checks,v.id,v.baseline)};return {vehicleId:v.id,registration:v.registration||c.registration||'',makeModel:v.makeModel||c.makeModel||'',vehicleYear:c.vehicleYear||'',driver:v.driver,checkDate:today(),nextCheckDue:addDays(today(),30),overall:'',checklist:Array(count).fill(''),comments:'',signature:'',...Object.fromEntries(['serviceDue','serviceDueKm','wofExpiry','alignmentDue','alignmentDueKm','regoExpiry','odometer','rucCurrent','rucDue'].map(k=>[k,c[k]??'']))}}



export default function VehicleChecks({request,active,isAdmin,technician}){

 const [asOf,setAsOf]=useState(today)

 useEffect(()=>{const timer=setInterval(()=>setAsOf(today()),60000);return()=>clearInterval(timer)},[])

 const [data,setData]=useState(null),[etag,setEtag]=useState(''),[screen,setScreen]=useState('dashboard'),[form,setForm]=useState(null),[step,setStep]=useState(0),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[fleet,setFleet]=useState(null),[filter,setFilter]=useState('')

 useEffect(()=>{if(!active)return;let cancelled=false;request('/api/vehicles').then(r=>{if(!cancelled){setData(r.data);setEtag(r.etag)}}).catch(e=>{if(!cancelled)setError(e.message)});return()=>{cancelled=true}},[request,active])

 async function refresh(){setError('');try{const r=await request('/api/vehicles');setData(r.data);setEtag(r.etag);setMessage('Vehicle dashboard refreshed.')}catch(e){setError(e.message)}}

 function edit(field,value){setForm(f=>({...f,[field]:value,...(field==='checkDate'&&!f.id?{nextCheckDue:addDays(value,30)}:{})}));setError('')}

 function openNew(){setError('');setMessage('');setStep(0);setForm(blankCheck(assignedVehicle(data.vehicles.find(v=>v.active)||data.vehicles[0],data.technicians),data.checks,data.checklist.length));if(!isAdmin)setForm(f=>({...f,driver:technician}));setScreen('form');requestAnimationFrame(()=>window.scrollTo(0,0))}

 function openCheck(check,view=false){if(!isAdmin)view=true;setError('');setMessage('');setForm({...check,checklist:[...check.checklist]});setStep(0);setScreen(view?'view':'form');requestAnimationFrame(()=>window.scrollTo(0,0))}

 function leave(){if(screen==='form'&&!window.confirm('Leave this check without saving your changes?'))return;setScreen('dashboard');setError('')}

 function next(e){e.preventDefault();if(!e.currentTarget.form.reportValidity())return;if(step===0&&form.overall==='Issues found'&&form.checklist.some(a=>!a)){setError('Complete every checklist row.');return}setError('');setStep(step+1);requestAnimationFrame(()=>window.scrollTo(0,0))}

 async function submit(e){e.preventDefault();if(readonly||step!==2)return;setBusy(true);setError('');try{const r=await request('/api/vehicle-checks',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(form)});setData({...data,checks:[...data.checks.filter(c=>c.id!==r.data.check.id),r.data.check]});setEtag(r.etag);setForm(r.data.check);setScreen('dashboard');setMessage(form.id?'Vehicle check updated.':'Vehicle check submitted.')}catch(e){setError(e.message)}finally{setBusy(false)}}

 async function saveFleet(e){e.preventDefault();setBusy(true);setError('');try{const r=await request('/api/vehicles',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify({vehicles:fleet})});setEtag(r.etag);setData({...data,vehicles:fleet,removedVehicles:[...(data.removedVehicles||[]),...data.vehicles.filter(v=>!fleet.some(row=>row.id===v.id))]});setFleet(null);setScreen('dashboard');setMessage('Vehicle details saved.')}catch(e){setError(e.message)}finally{setBusy(false)}}

 if(!data)return <main className="workspace-page"><h1>Vehicle checks</h1>{error?<p role="alert">{error}</p>:<p role="status">Loading vehicles…</p>}</main>

 const readonly=screen==='view'||(!isAdmin&&!!form?.id),history=data.checks.filter(c=>!filter||c.vehicleId===filter).sort((a,b)=>b.checkDate.localeCompare(a.checkDate)||b.createdAt.localeCompare(a.createdAt))

 const field=(key,label,type='text',required=false)=> <label className="vehicle-field" key={key}>{label}{required&&<span className="required-mark"> *</span>}<input aria-label={label} type={type} required={required} min={type==='number'?0:undefined} step={type==='number'?1:undefined} max={type==='number'?10000000:undefined} maxLength={key==='vehicleYear'?4:160} disabled={readonly} value={form[key]??''} onChange={e=>edit(key,e.target.value)}/></label>

 return <main className={`workspace-page vehicles-page ${screen==='form'||readonly?'vehicle-form-page':''}`}>

  <div className="page-heading"><div><h1>{screen==='dashboard'?'Vehicle checks':screen==='fleet'?'Manage vehicles':readonly?'View vehicle check':form?.id?'Edit vehicle check':'New vehicle check'}</h1><p>{screen==='dashboard'?'Monthly checks, compliance dates and vehicle history.':screen==='fleet'?'Manage the fleet and driver assignments. Remove vehicles from the dashboard while keeping submitted check history. Changes apply when you save.':'Trident Monthly Vehicle Check'}</p></div><div className="settings-actions">{screen==='dashboard'?<><button className="primary-action" disabled={!data.vehicles.length} onClick={openNew}>New vehicle check</button>{isAdmin&&<button onClick={()=>{setFleet(data.vehicles.map(v=>({...v})));setScreen('fleet');setError('');setMessage('')}}>Manage vehicles</button>}<button onClick={refresh}>Refresh dashboard</button></>:<button onClick={leave}>Back to dashboard</button>}</div></div>

  {error&&<div role="alert">{error} <button className="inline-button" onClick={refresh}>Refresh saved data</button></div>}{message&&<p role="status" className="save-message">{message}</p>}

  {screen==='dashboard'&&<>{isAdmin&&<ReminderDashboard request={request} kind="vehicle"/>}<div className="check-due-legend" aria-label="Vehicle check due colours"><span className="due-red">Red: due, overdue or 1–7 days</span><span className="due-orange">Orange: 8–14 days</span><span className="due-yellow">Yellow: 15–21 days</span><span className="due-green">Green: 22+ days</span></div>{!data.vehicles.length&&<p>No vehicles in the fleet. Use Manage vehicles to add one.</p>}<div className="fleet-scroll" hidden={!data.vehicles.length}><table className="fleet-dashboard"><thead><tr><th scope="col">Vehicle ID</th>{data.vehicles.map(v=><th scope="col" key={v.id}>{v.id}</th>)}</tr></thead><tbody>{metrics.map(([label,group,value,overdue])=><tr key={label} className={`fleet-${group}`}><th scope="row">{label}</th>{data.vehicles.map(vehicle=>{const latest=latestFor(data.checks,vehicle.id,vehicle.baseline),check={...vehicle.baseline,...latest},v=assignedVehicle({...vehicle,registration:latest?.registration||vehicle.registration,makeModel:latest?.makeModel||vehicle.makeModel,driver:latest?.driver||vehicle.driver},data.technicians),text=value({...v,registration:v.registration||latest?.registration,makeModel:v.makeModel||latest?.makeModel},check);const status=checkDueStatus(check.checkDate,asOf,check.nextCheckDue),isDue=label==='Next Check'||label==='Check status';return <td key={vehicle.id} className={isDue?`due-${status.colour}`:overdue?.(v,check)?'overdue':''}>{label==='Check status'?status.label:text||'—'}</td>})}</tr>)}</tbody></table></div><p className="report-hint">Dashboard uses the most recent check date for each vehicle. Next check uses the expiry saved on the latest check, or 30 days later for older records. Red figures are due or overdue. Initial fleet readings come from your supplied dashboard image.</p>

   {data.vehicles.length>0&&<section className="latest-checklists"><h2>Latest submitted checklists</h2><p className="report-hint">The most recent check date for each vehicle is shown. Edits to that check update this checklist.</p><div className="fleet-scroll"><table className="fleet-dashboard latest-checklist-table"><thead><tr><th scope="col">Checklist item</th>{data.vehicles.map(v=>{const c=latestFor(data.checks,v.id);return <th scope="col" key={v.id}>{v.id}{c&&<button className="inline-button" aria-label={`View latest checklist ${v.id}`} onClick={()=>openCheck(c,true)}>View check</button>}</th>})}</tr></thead><tbody><tr><th scope="row">Check date</th>{data.vehicles.map(v=><td key={v.id}>{dateLabel(latestFor(data.checks,v.id)?.checkDate)}</td>)}</tr><tr><th scope="row">Overall result</th>{data.vehicles.map(v=>{const c=latestFor(data.checks,v.id);return <td key={v.id}>{c?.overall||'No submitted checklist'}</td>})}</tr>{data.checklist.map((item,i)=><tr key={item}><th scope="row">{item}</th>{data.vehicles.map(v=>{const answer=latestFor(data.checks,v.id)?.checklist[i];return <td key={v.id} className={answer==='Fail'?'check-fail':answer==='Pass'?'check-pass':'check-na'}>{answer||'—'}</td>})}</tr>)}</tbody></table></div></section>}

   <section className="vehicle-history"><div className="page-heading"><h2>Check history</h2><label>Vehicle <select aria-label="History vehicle" value={filter} onChange={e=>setFilter(e.target.value)}><option value="">All vehicles</option>{[...data.vehicles,...(data.removedVehicles||[])].map(v=><option key={v.id} value={v.id}>{v.id} · {v.registration||'Unassigned'}{data.vehicles.some(row=>row.id===v.id)?'':' (removed)'}</option>)}</select></label></div>{history.length?<div className="table-scroll"><SortableTable><thead><tr><th>Check date</th><th>Vehicle</th><th>Registration</th><th>Inspector</th><th>Result</th><th>Revision</th><th>Actions</th></tr></thead><tbody>{history.map(c=><tr key={c.id}><td data-sort-value={c.checkDate}>{dateLabel(c.checkDate)}</td><td>{c.vehicleId}</td><td>{c.registration}</td><td>{c.driver}</td><td>{c.overall}</td><td>{c.revision}</td><td><button onClick={()=>openCheck(c,true)} aria-label={`View check ${c.registration} ${c.checkDate}`}>View</button>{isAdmin&&<button onClick={()=>openCheck(c)} aria-label={`Edit check ${c.registration} ${c.checkDate}`}>Edit</button>}</td></tr>)}</tbody></SortableTable></div>:<p>No submitted vehicle checks yet.</p>}</section></>}

  {screen==='fleet'&&<form onSubmit={saveFleet}><div className="table-scroll"><table className="settings-table"><thead><tr><th>Vehicle ID</th><th>Registration</th><th>Make / model</th><th>Driver</th><th>Active</th><th>Actions</th></tr></thead><tbody>{fleet.map((v,i)=><tr key={i}>{['id','registration','makeModel','driver'].map(k=><td key={k}><input aria-label={`${k} ${i+1}`} required={k==='id'} disabled={k==='id'&&data.vehicles.some(old=>old.id===v.id)} value={v[k]} list={k==='driver'?'vehicle-drivers':undefined} onChange={e=>setFleet(fleet.map((r,n)=>n===i?{...r,[k]:e.target.value}:r))}/></td>)}<td><input type="checkbox" aria-label={`Active ${v.id}`} checked={v.active} onChange={e=>setFleet(fleet.map((r,n)=>n===i?{...r,active:e.target.checked}:r))}/></td><td><button type="button" className="remove-row" aria-label={`Remove vehicle ${v.id}`} onClick={()=>{setFleet(fleet.filter((_,n)=>n!==i));setMessage('Vehicle removed from this list. Save vehicles to apply.')}}>Remove</button></td></tr>)}</tbody></table></div><div className="settings-actions"><button type="button" onClick={()=>{let n=fleet.length+1;while([...fleet,...data.vehicles,...(data.removedVehicles||[])].some(v=>v.id===`VEH-${String(n).padStart(2,'0')}`))n++;setFleet([...fleet,{id:`VEH-${String(n).padStart(2,'0')}`,registration:'',makeModel:'',driver:'',active:true}])}}>Add vehicle</button><button className="primary-action" type="submit" disabled={busy}>Save vehicles</button></div></form>}

  {(screen==='form'||readonly)&&<form className="vehicle-check-form" onSubmit={submit}><div className="vehicle-form-banner"><img src="/trident-logo.png" alt="Trident Community Equipment"/><h2>Trident Monthly Vehicle Check</h2><p>Inspect each item, select the result and record damage or comments.</p></div><ol className="vehicle-steps">{['Vehicle and inspection','Service and compliance','Readings and sign-off'].map((s,i)=><li key={s} className={step===i?'current':''}>{i+1}. {s}</li>)}</ol>

   {(step===0||readonly)&&<><section className="vehicle-form-card"><h2>Vehicle and driver details</h2><label className="vehicle-field">Vehicle ID *<select aria-label="Vehicle ID" disabled={readonly||!!form.id} value={form.vehicleId} onChange={e=>setForm({...blankCheck(assignedVehicle(data.vehicles.find(v=>v.id===e.target.value),data.technicians),data.checks,data.checklist.length),...(!isAdmin?{driver:technician}:{})})}>{[...data.vehicles,...(data.removedVehicles||[]).filter(v=>v.id===form.vehicleId&&form.id)].map(v=><option key={v.id} value={v.id}>{v.id} · {assignedVehicle(v,data.technicians).registration||'Unassigned'}{data.vehicles.some(row=>row.id===v.id)?!v.active?' (inactive)':'':' (removed)'}</option>)}</select></label>{field('checkDate','Check date','date',true)}<label className="vehicle-field">Driver / inspector name *<input aria-label="Driver / inspector name" list="vehicle-drivers" required disabled={readonly||!isAdmin} value={form.driver} onChange={e=>edit('driver',e.target.value)}/></label>{field('registration','Vehicle registration','text',true)}{field('makeModel','Make / model')}{field('vehicleYear','Vehicle year')}</section>

   <section className="vehicle-form-card"><h2>Monthly inspection</h2><fieldset className="overall-result"><legend>Overall vehicle check result *</legend><p>Choose All OK only when every item passes. For any fail or N/A, choose Issues found and complete every checklist row.</p>{['All OK','Issues found'].map(result=><label key={result}><input type="radio" name="overall" value={result} required disabled={readonly} checked={form.overall===result} onChange={()=>setForm({...form,overall:result,checklist:result==='All OK'?Array(data.checklist.length).fill('Pass'):form.checklist})}/>{result==='Issues found'?'Issues found — complete checklist below':result}</label>)}</fieldset><h3>Monthly vehicle checklist</h3><div className="table-scroll"><table className="inspection-checklist"><thead><tr><th>Check item</th>{['Pass','Fail','N/A'].map(s=><th key={s}>{s}</th>)}</tr></thead><tbody>{data.checklist.map((item,i)=><tr key={item}><th scope="row">{item}</th>{['Pass','Fail','N/A'].map(answer=><td key={answer}><input type="radio" name={`check-${i}`} aria-label={`${item}: ${answer}`} disabled={readonly||form.overall==='All OK'} checked={form.checklist[i]===answer} onChange={()=>edit('checklist',form.checklist.map((a,n)=>n===i?answer:a))}/></td>)}</tr>)}</tbody></table></div><label className="vehicle-field">Any damage or comments *<textarea aria-label="Any damage or comments" required maxLength={4000} rows={4} disabled={readonly} placeholder="Describe faults or work needed. Enter No issues if everything is OK." value={form.comments} onChange={e=>edit('comments',e.target.value)}/></label></section></>}

   {(step===1||readonly)&&<section className="vehicle-form-card"><h2>Service and compliance dates</h2>{field('nextCheckDue','Next vehicle check due','date',true)}{field('serviceDue','Service due','date',true)}{field('serviceDueKm','Service due KM','number',true)}{field('wofExpiry','WOF due','date')}{field('alignmentDue','Wheel alignment due','date',true)}{field('alignmentDueKm','Wheel alignment due KM','number',true)}{field('regoExpiry','Registration due','date',true)}</section>}

   {(step===2||readonly)&&<section className="vehicle-form-card"><h2>Readings and sign-off</h2>{field('odometer','Odometer reading KM','number',true)}{field('rucCurrent','Road user charge KM','number',true)}{field('rucDue','RUC due KM','number')}{field('signature','Signed / inspector name','text',true)}<div className="vehicle-calculated" aria-label="Calculated remaining values"><h3>Calculated remaining</h3><dl>{[['RUC KM remaining',remaining(form.rucDue!==''&&form.rucDue!==null&&form.rucDue!==undefined?form.rucDue:form.rucCurrent,form.odometer)],['Service KM remaining',remaining(form.serviceDueKm,form.odometer)],['Wheel alignment KM remaining',remaining(form.alignmentDueKm,form.odometer)],['WOF months to expiry',months(form.wofExpiry)],['Rego months to expiry',months(form.regoExpiry)]].map(([label,value])=><div key={label}><dt>{label}</dt><dd>{number(value)}</dd></div>)}</dl><p>Calculated automatically from the readings and dates above. Negative values are overdue.</p></div></section>}

   <div className="settings-actions">{readonly?(isAdmin&&<button type="button" className="primary-action" onClick={()=>{setScreen('form');setStep(0)}}>Edit this check</button>):<>{step>0&&<button type="button" onClick={()=>setStep(step-1)}>Back</button>}{step<2?<button type="button" className="primary-action" onClick={next}>Next</button>:<button type="submit" className="primary-action" disabled={busy}>{busy?'Saving…':form.id?'Save check changes':'Submit vehicle check'}</button>}</>}</div>

  </form>}

  <datalist id="vehicle-drivers">{data.technicians.map(t=><option key={t.name} value={t.name}/>)}</datalist>

 </main>

}

