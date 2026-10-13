import {useState} from 'react'
import RecycleBin from './RecycleBin'
import StaffSetup from './StaffSetup'
import TimeSettings from './TimeSettings'
import ScheduleSettings from './ScheduleSettings'
import VehicleSettings from './VehicleSettings'
import QuoteSettings from './QuoteSettings'
import ReminderSettings from './ReminderSettings'
import LabourSettings from './LabourSettings'
export default function SettingsPage({request,onSaved,initialManagementSection='staff'}){
 const [managementSection,setManagementSection]=useState(initialManagementSection==='dashboard'?'dashboard':'staff')
 const [tab,setTab]=useState('staff'),[quoteSection,setQuoteSection]=useState('defaults')
 return <div className="settings-workspace">
 <nav className="settings-tabs" aria-label="Settings sections">{[['staff','Staff & vehicles'],['time','Time sheet defaults'],['schedule','Schedule settings'],['quotes','Quote settings'],['reminders','Email reminders'],['bin','Recycle bin']].map(([key,name])=><button key={key} aria-current={tab===key?'page':undefined} onClick={()=>setTab(key)}>{name}</button>)}</nav>
 {tab==='bin'&&<RecycleBin request={request} onSaved={onSaved}/>}
 {tab==='staff'&&<><nav className="settings-subtabs" aria-label="Staff and vehicle settings">{[['staff','Staff & vehicle setup'],['dashboard','Dashboard settings']].map(([key,name])=><button key={key} aria-current={managementSection===key?'page':undefined} onClick={()=>setManagementSection(key)}>{name}</button>)}</nav>{managementSection==='staff'&&<StaffSetup title="Staff & vehicle management" request={request} onSaved={onSaved}/>}{managementSection==='dashboard'&&<VehicleSettings request={request} onSaved={onSaved}/>}</>}
 {tab==='schedule'&&<ScheduleSettings request={request} onSaved={onSaved}/>}
 {tab==='time'&&<TimeSettings request={request} onSaved={onSaved}/>}
 {tab==='quotes'&&<><nav className="settings-subtabs" aria-label="Quote settings">{[['defaults','Quote defaults'],['labour','Labour calculator']].map(([key,name])=><button key={key} aria-current={quoteSection===key?'page':undefined} onClick={()=>setQuoteSection(key)}>{name}</button>)}</nav><section hidden={quoteSection!=='defaults'}><QuoteSettings request={request} onSaved={onSaved}/></section><section hidden={quoteSection!=='labour'}><LabourSettings request={request} onSaved={onSaved}/></section></>}
 {tab==='reminders'&&<ReminderSettings request={request}/>}
 </div>
}
