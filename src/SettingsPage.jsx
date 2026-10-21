import {useLayoutEffect,useRef,useState} from 'react'
import Icon from './Icon'
import './SettingsLayout.css'
import RecycleBin from './RecycleBin'
import StaffSetup from './StaffSetup'
import TimeSettings from './TimeSettings'
import ScheduleSettings from './ScheduleSettings'
import VehicleSettings from './VehicleSettings'
import QuoteSettings from './QuoteSettings'
import ReminderSettings from './ReminderSettings'
import LabourSettings from './LabourSettings'
export default function SettingsPage({request,onSaved,initialManagementSection='staff'}){
 const workspaceRef=useRef(null)
 useLayoutEffect(()=>{const element=workspaceRef.current,header=document.querySelector('.portal-header');let active=true;const fit=()=>{if(active&&element?.isConnected&&element.getClientRects().length)element.style.setProperty('--settings-available-height',Math.max(180,window.innerHeight-element.getBoundingClientRect().top)+'px')};const observer=new ResizeObserver(fit);if(element)observer.observe(element);if(header)observer.observe(header);window.addEventListener('resize',fit);fit();return()=>{active=false;observer.disconnect();window.removeEventListener('resize',fit)}},[])
 const [managementSection,setManagementSection]=useState(initialManagementSection==='dashboard'?'dashboard':'staff')
 const [tab,setTab]=useState('staff'),[quoteSection,setQuoteSection]=useState('defaults')
 return <div ref={workspaceRef} className="settings-workspace settings-compact">
 <nav className="settings-tabs" aria-label="Settings sections"><div className="settings-nav-title"><Icon name="settings" size={17}/>Settings</div>{[['staff','Staff & vehicles'],['time','Time sheet defaults'],['schedule','Schedule settings'],['quotes','Quote settings'],['reminders','Email reminders'],['bin','Recycle bin']].map(([key,name])=><button key={key} aria-current={tab===key?'page':undefined} onClick={()=>setTab(key)}><Icon name={({staff:'users',time:'clock',schedule:'calendar',quotes:'file-text',reminders:'mail',bin:'trash-2'})[key]} size={16}/><span>{name}</span></button>)}</nav><div className="settings-content">
 {tab==='bin'&&<RecycleBin request={request} onSaved={onSaved}/>}
 {tab==='staff'&&<><nav className="settings-subtabs" aria-label="Staff and vehicle settings">{[['staff','Staff & vehicle setup'],['dashboard','Dashboard settings']].map(([key,name])=><button key={key} aria-current={managementSection===key?'page':undefined} onClick={()=>setManagementSection(key)}>{name}</button>)}</nav>{managementSection==='staff'&&<StaffSetup title="Staff & vehicle management" request={request} onSaved={onSaved}/>}{managementSection==='dashboard'&&<VehicleSettings request={request} onSaved={onSaved}/>}</>}
 {tab==='schedule'&&<ScheduleSettings request={request} onSaved={onSaved}/>}
 {tab==='time'&&<TimeSettings request={request} onSaved={onSaved}/>}
 {tab==='quotes'&&<><nav className="settings-subtabs" aria-label="Quote settings">{[['defaults','Quote defaults'],['labour','Labour calculator']].map(([key,name])=><button key={key} aria-current={quoteSection===key?'page':undefined} onClick={()=>setQuoteSection(key)}>{name}</button>)}</nav><section hidden={quoteSection!=='defaults'}><QuoteSettings request={request} onSaved={onSaved}/></section><section hidden={quoteSection!=='labour'}><LabourSettings request={request} onSaved={onSaved}/></section></>}
 {tab==='reminders'&&<ReminderSettings request={request}/>}
 </div></div>
}
