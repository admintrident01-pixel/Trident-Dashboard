import Icon from './Icon'
import TimesheetHistory from './TimesheetHistory'
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react'

import './App.css'





import EmailSignIn from './EmailSignIn'

import ReminderDashboard from './ReminderDashboard'
import {loadSession,saveSession} from './session'
import {loadPage,canAccessPage} from './navigation'

const StockPage=lazy(()=>import('./StockPage'))
const WeeklyReport=lazy(()=>import('./WeeklyReport'))
const SettingsPage=lazy(()=>import('./SettingsPage'))
const VehicleChecks=lazy(()=>import('./VehicleChecks'))
const LeaveForms=lazy(()=>import('./LeaveForms'))
const TechSchedule=lazy(()=>import('./TechSchedule'))
const OfficeFiles=lazy(()=>import('./OfficeFiles'))

const localMode=import.meta.env.DEV&&import.meta.env.VITE_LOCAL_DEVELOPMENT==='true'

const api=localMode?'http://127.0.0.1:18782':(import.meta.env.VITE_API_URL||'https://trident-quote-api-dsn2tnnc3q-ts.a.run.app').replace(/\/$/,'')

export default function App(){

 const [session,setSession]=useState(loadSession),[error,setError]=useState(''),[document,setDocument]=useState(''),[timesheetDocument,setTimesheetDocument]=useState(''),[selectedPage,setPage]=useState(loadPage)
 const page=canAccessPage(selectedPage,session)?selectedPage:'home'
 const [visitedPages,setVisitedPages]=useState(()=>({[loadPage()]:true}))
 const visitPage=useCallback(next=>{setVisitedPages(current=>current[next]?current:{...current,[next]:true});setPage(next)},[])

 useEffect(()=>saveSession(session),[session])
 useEffect(()=>{const titles={home:'Home',quotes:'Quotes',schedule:'Tech schedule',timesheet:'Time sheet',leave:'Leave forms',reports:'Labour payables',vehicles:'Vehicle checks',stock:'Stock & assets',settings:'Settings',office:'Shared resources'};window.document.title=(titles[page]||'Home')+' · Trident Dashboard'},[page])

 useEffect(()=>{if(session)window.history.replaceState(null,'',`${location.pathname}${location.search}#${page}`)},[page,session])
 useEffect(()=>{const change=()=>{const next=loadPage();if(page==='reports'&&next!==page&&window.tridentReportHasUnsavedChanges?.()&&!window.confirm('Report entries are unsaved. Leave anyway?')){window.history.replaceState(null,'',`#${page}`);return}if(page==='quotes'&&next!==page&&quoteFrame.current?.contentWindow.tridentQuoteHasUnsavedChanges?.()&&!window.confirm('Your quote has unsaved changes. Save your draft before leaving. Leave anyway?')){window.history.replaceState(null,'',`#${page}`);return}visitPage(next)};window.addEventListener('hashchange',change);return()=>window.removeEventListener('hashchange',change)},[page,visitPage])

 const timesheetFrame=useRef(null),quoteFrame=useRef(null),pendingDraft=useRef('')
 function continueTimesheetDraft(id){navigate('timesheet');pendingDraft.current=id;if(timesheetFrame.current){timesheetFrame.current.contentWindow.postMessage({type:'trident-resume-timesheet-draft',id},location.origin);pendingDraft.current='';timesheetFrame.current.scrollIntoView({block:'start',behavior:'smooth'})}}
 const [timesheetHeight,setTimesheetHeight]=useState(900)
 const [managementSection,setManagementSection]=useState('staff')

 const isAdmin=session?.role==='admin'

 const allowed=key=>isAdmin||['home','timesheet','leave','vehicles','schedule'].includes(key)

 const request=useCallback(async(path,init={})=>{

  const headers=new Headers(init.headers);headers.set('Authorization',`Bearer ${session?.token}`)

  const response=await fetch(api+path,{...init,headers}),data=await response.json()

  if(response.status===401||response.status===403&&data.error==='Your account is not active. Contact an administrator.'){setSession(null);setDocument('');setTimesheetDocument('');setPage('home')}

  if(!response.ok)throw Error(data.error||'Unable to complete this request.')

  return {data,etag:response.headers.get('ETag')}

 },[session])

 useEffect(()=>{

  if(!session||page!=='quotes'||document)return;let cancelled=false

  fetch('/quote-builder.html').then(r=>{if(!r.ok)throw Error('Unable to load the quote builder.');return r.text()}).then(html=>{

   const config=JSON.stringify({api,token:session.token,origin:location.origin}).replace(/</g,'\\u003c')

   const bridge=`<script>(()=>{const c=${config},original=window.fetch.bind(window);window.fetch=async(input,init={})=>{const url=typeof input==='string'?input:input.url;if(new URL(url,c.origin).pathname.startsWith('/api/')){const headers=new Headers(init.headers);headers.set('Authorization','Bearer '+c.token);const response=await original(c.api+new URL(url,c.origin).pathname+new URL(url,c.origin).search,{...init,headers});if(response.status===401)parent.postMessage({type:'trident-signin-expired'},c.origin);return response;}return original(input,init);};})();</script>`

   if(!cancelled)setDocument(html.replace('<head>','<head>'+bridge))

  }).catch(e=>setError(e.message));return()=>{cancelled=true}

 },[session,page,document])

 useEffect(()=>{

  if(!session||page!=='timesheet'||timesheetDocument)return;let cancelled=false

  fetch('/timesheet.html').then(r=>{if(!r.ok)throw Error('Unable to load the time sheet.');return r.text()}).then(html=>{

   const config=JSON.stringify({api,token:session.token,origin:location.origin}).replace(/</g,'\\u003c')

   const bridge=`<script>(()=>{const c=${config},original=window.fetch.bind(window);window.fetch=async(input,init={})=>{const url=typeof input==='string'?input:input.url;if(new URL(url,c.origin).pathname.startsWith('/api/')){const headers=new Headers(init.headers);headers.set('Authorization','Bearer '+c.token);const response=await original(c.api+new URL(url,c.origin).pathname+new URL(url,c.origin).search,{...init,headers});if(response.status===401)parent.postMessage({type:'trident-signin-expired'},c.origin);return response;}return original(input,init);};})();</script>`

   if(!cancelled)setTimesheetDocument(html.replace('<head>','<head>'+bridge))

  }).catch(e=>setError(e.message));return()=>{cancelled=true}

 },[session,page,timesheetDocument])

 useEffect(()=>{const handler=e=>{if(e.origin===location.origin&&e.data?.type==='trident-signin-expired'){setSession(null);setDocument('');setTimesheetDocument('');setPage('home');setError('Your session expired. Sign in again.')}};window.addEventListener('message',handler);return()=>window.removeEventListener('message',handler)},[])

 useEffect(()=>{const listener=e=>{if(e.origin===location.origin&&e.source===timesheetFrame.current?.contentWindow&&e.data?.type==='trident-timesheet-height'&&Number.isFinite(e.data.height)&&e.data.height>0&&e.data.height<20000)setTimesheetHeight(e.data.height);if(e.origin===location.origin&&e.source===timesheetFrame.current?.contentWindow&&e.data?.type==='trident-timesheets-updated')window.dispatchEvent(new Event('trident-timesheets-updated'))};window.addEventListener('message',listener);return()=>window.removeEventListener('message',listener)},[])
 useEffect(()=>{if(page==='timesheet'&&timesheetDocument)timesheetFrame.current?.contentWindow.postMessage({type:'trident-leave-updated'},location.origin)},[page,timesheetDocument])

 useEffect(()=>{const refresh=()=>quoteFrame.current?.contentWindow.postMessage({type:'trident-quote-settings-updated'},location.origin);window.addEventListener('trident-settings-saved',refresh);return()=>window.removeEventListener('trident-settings-saved',refresh)},[])

 useEffect(()=>{

  if(!session)return

  let cancelled=false
  const check=async()=>{try{const r=await fetch(api+'/api/session',{headers:{Authorization:'Bearer '+session.token}}),d=await r.json();if(cancelled)return;if(r.status===401||r.status===403){setSession(null);setDocument('');setTimesheetDocument('');setPage('home');return}if(!r.ok)return;if(d.role!==session.role||d.technician!==session.technician){setSession({...session,...d,token:session.token});setDocument('');setTimesheetDocument('')}}catch{/* Keep the session through temporary connection failures. */}}
  check()
  const resume=()=>{if(!window.document.hidden)check()}
  const timer=setInterval(resume,60000)
  window.document.addEventListener('visibilitychange',resume)

  return()=>{cancelled=true;clearInterval(timer);window.document.removeEventListener('visibilitychange',resume)}

 },[session])

 const openLocal=async()=>{try{setError('');const r=await fetch(`${api}/api/dev-session`);const data=await r.json();if(!r.ok)throw Error(data.error||'Start the local development server first.');setSession(data)}catch(e){setError(e.message)}}

 const navigate=next=>{if(next===page)return;if(page==='reports'&&next!==page&&window.tridentReportHasUnsavedChanges?.()&&!window.confirm('Report entries are unsaved. Save them before leaving. Leave anyway?'))return;if(page==='quotes'&&next!==page&&quoteFrame.current?.contentWindow.tridentQuoteHasUnsavedChanges?.()&&!window.confirm('Your quote has unsaved changes. Save your draft before leaving. Leave anyway?'))return;visitPage(next);window.scrollTo({top:0,behavior:'instant'})}
 useEffect(()=>{const warn=e=>{if(timesheetFrame.current?.contentWindow.tridentTimesheetHasUnsavedChanges?.()){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn)},[])
 const signOut=async()=>{if(timesheetFrame.current?.contentWindow.tridentTimesheetHasUnsavedChanges?.()&&!window.confirm('Your time sheet has unsaved changes. Save a draft before signing out. Sign out anyway?'))return;if(window.tridentReportHasUnsavedChanges?.()&&!window.confirm('Report entries are unsaved. Sign out anyway?'))return;if(quoteFrame.current?.contentWindow.tridentQuoteHasUnsavedChanges?.()&&!window.confirm('Your quote has unsaved changes. Save your draft before signing out. Sign out anyway?'))return;try{await request('/api/auth/logout',{method:'POST'})}catch{/* The browser session is still cleared on a failed sign-out. */}setSession(null);setDocument('');setTimesheetDocument('');setPage('home');setError('')}

 if(!api||api.includes('YOUR-'))return <main className="signin"><h1>Trident Dashboard</h1><p>Online setup is not finished. Configure the API address, then rebuild the website.</p></main>

 return session?<div className={`workspace${localMode?' is-local':''}`}>

  <a className="skip-content" href="#workspace-content" onClick={e=>{e.preventDefault();window.document.getElementById('workspace-content')?.focus()}}>Skip to page content</a><header className="portal-header">

   <button className="portal-brand" aria-label="Trident home" onClick={()=>navigate('home')}><img src="/trident-logo.png" alt="Trident Community Equipment"/></button>

   <nav aria-label="Main navigation">{[['home','Home'],['quotes','Quotes'],['schedule','Tech schedule'],['timesheet','Time sheet'],['leave','Leave forms'],['reports','Labour payables'],['vehicles','Vehicle checks'],['stock','Stock'],['settings','Settings'],['office','Shared resources']].filter(([key])=>allowed(key)).map(([key,name])=><button key={key} aria-current={page===key?'page':undefined} onClick={()=>navigate(key)}>{name}</button>)}</nav>

   <div className="portal-account"><span>{session.email} · {isAdmin?'Admin':'Technician'}</span><button onClick={signOut}>Sign out</button></div>

  </header>

  {localMode&&<div className="development-notice">Local development · Changes are saved on this computer.</div>}

  {error&&<p role="alert">{error}</p>}

  <Suspense fallback={<p className="module-loading" role="status">Opening page…</p>}><div id="workspace-content" tabIndex={-1}>
  {page==='home'&&<main className="portal-home">

   <div className="home-intro"><span className="home-eyebrow">Trident Community Equipment</span><h1>Welcome to your workspace</h1><p>Choose where you’d like to work.</p></div>

   <div className="module-grid">{[
 ['quotes','Quotes','Create quotes, manage drafts and view completed quotes.','file-text'],
 ['schedule','Tech schedule','Plan appointments and see the whole team’s day.','calendar'],
 ['timesheet','Time sheet','Enter weekly hours, review leave and submit your time sheet.','clock'],
 ['leave','Leave forms','Request leave and review approvals.','calendar'],
 ['reports','Labour payables','Review payable and charged hours, averages and reports.','bar-chart-2'],
 ['vehicles','Vehicle checks','Review due dates, complete checks and view vehicle history.','truck'],
 ['stock','Stock','Receive equipment, manage assets, allocate to POs and track refurbishment.','package'],
 ['office','Shared resources','Find SOPs, browse process folders and preview documents.','folder'],
 ['settings','Settings','Manage staff, defaults and email reminders.','sliders']
 ].filter(([key])=>allowed(key)).map(([key,name,description,icon])=><button className="module-card" key={key} onClick={()=>navigate(key)}><span className="module-icon" aria-hidden="true"><Icon name={icon} size={29}/></span><span className="module-heading">{name}</span><span className="module-description">{description}</span><span className="module-link">Open {name.toLowerCase()} <Icon name="arrow-right" size={18}/></span></button>)}</div>

   {isAdmin&&<><ReminderDashboard request={request}/><TimesheetHistory request={request} isAdmin={isAdmin} onContinueDraft={continueTimesheetDraft}/></>}
  </main>}

  {page==='quotes'&&!document&&<p className="module-loading" role="status">Loading your quotes…</p>}

  {document&&<section className="quote-module" hidden={page!=='quotes'} aria-label="Quotes"><iframe ref={quoteFrame} title="Trident quote builder" srcDoc={document}/></section>}

  {page==='timesheet'&&!timesheetDocument&&<p className="module-loading" role="status">Loading your time sheet…</p>}

  {timesheetDocument&&<section className="quote-module timesheet-module" hidden={page!=='timesheet'} aria-label="Time sheet"><iframe ref={timesheetFrame} title="Trident time sheet" onLoad={()=>{if(pendingDraft.current){timesheetFrame.current.contentWindow.postMessage({type:'trident-resume-timesheet-draft',id:pendingDraft.current},location.origin);pendingDraft.current=''}}} style={{height:timesheetHeight}} srcDoc={timesheetDocument}/>{page==='timesheet'&&<TimesheetHistory request={request} isAdmin={isAdmin} onContinueDraft={continueTimesheetDraft}/>}</section>}

  {(page==='leave'||visitedPages.leave)&&<section hidden={page!=='leave'}><LeaveForms isAdmin={isAdmin} request={request} active={page==='leave'} onChanged={()=>{timesheetFrame.current?.contentWindow.postMessage({type:'trident-leave-updated'},location.origin);window.dispatchEvent(new Event('trident-leave-updated'))}}/></section>}

  {page==='office'&&<Suspense fallback={<p className="module-loading" role="status">Opening shared resources…</p>}><OfficeFiles request={request} isAdmin={isAdmin}/></Suspense>}
  {isAdmin&&page==='stock'&&<StockPage request={request}/>}
  {isAdmin&&page==='reports'&&<WeeklyReport request={request}/>}
  {(page==='schedule'||visitedPages.schedule)&&<section hidden={page!=='schedule'}><TechSchedule request={request} isAdmin={isAdmin} active={page==='schedule'}/></section>}

  {(page==='vehicles'||visitedPages.vehicles)&&<section hidden={page!=='vehicles'}><VehicleChecks onManage={()=>{setManagementSection('fleet');navigate('settings')}} isAdmin={isAdmin} technician={session.technician} request={request} active={page==='vehicles'}/></section>}

  {isAdmin&&<section hidden={page!=='settings'}>{page==='settings'&&<SettingsPage initialManagementSection={managementSection} request={request} onSaved={()=>{timesheetFrame.current?.contentWindow.postMessage({type:'trident-staff-updated'},location.origin);window.dispatchEvent(new Event('trident-settings-saved'))}}/>}</section>}

 </div>
 </Suspense>
 </div>:<EmailSignIn api={api} localMode={localMode} onLocal={openLocal} onSignedIn={setSession}/>

}

