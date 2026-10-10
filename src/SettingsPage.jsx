import {useState} from 'react'
import RecycleBin from './RecycleBin'
import StaffSetup from './StaffSetup'
import TimeSettings from './TimeSettings'
import ScheduleSettings from './ScheduleSettings'
import QuoteSettings from './QuoteSettings'
import ReminderSettings from './ReminderSettings'
import LabourSettings from './LabourSettings'
export default function SettingsPage({request,onSaved}){
 const [tab,setTab]=useState('staff'),[quoteSection,setQuoteSection]=useState('defaults')
 return <div className="settings-workspace">
 <nav className="settings-tabs" aria-label="Settings sections">{[['staff','Staff setup'],['time','Time sheet defaults'],['schedule','Schedule settings'],['quotes','Quote settings'],['reminders','Email reminders'],['bin','Recycle bin']].map(([key,name])=><button key={key} aria-current={tab===key?'page':undefined} onClick={()=>setTab(key)}>{name}</button>)}</nav>
 {tab==='bin'&&<RecycleBin request={request} onSaved={onSaved}/>}
 {tab==='staff'&&<StaffSetup request={request} onSaved={onSaved}/>}
 {tab==='schedule'&&<ScheduleSettings request={request} onSaved={onSaved}/>}
 {tab==='time'&&<TimeSettings request={request} onSaved={onSaved}/>}
 {tab==='quotes'&&<><nav className="settings-subtabs" aria-label="Quote settings">{[['defaults','Quote defaults'],['labour','Labour calculator']].map(([key,name])=><button key={key} aria-current={quoteSection===key?'page':undefined} onClick={()=>setQuoteSection(key)}>{name}</button>)}</nav><section hidden={quoteSection!=='defaults'}><QuoteSettings request={request} onSaved={onSaved}/></section><section hidden={quoteSection!=='labour'}><LabourSettings request={request} onSaved={onSaved}/></section></>}
 {tab==='reminders'&&<ReminderSettings request={request}/>}
 </div>
}
