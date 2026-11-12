export function leaveDates(form){
 const first=Date.parse(form.startDate+'T00:00:00Z'),last=Date.parse(form.endDate+'T00:00:00Z'),dates=[]
 if(!Number.isFinite(first)||!Number.isFinite(last)||last<first||last-first>365*86400000)return dates
 for(let n=first;n<=last;n+=86400000){const d=new Date(n);if(form.includeWeekends||![0,6].includes(d.getUTCDay()))dates.push(d.toISOString().slice(0,10))}
 return dates
}
export const minutes=value=>{if(!/^\d{2}:\d{2}$/.test(value||''))return NaN;const [h,m]=value.split(':').map(Number);return h*60+m}
export function leaveCalculation(row){
 if(row.duration==='full')return {hours:8,lunch:0,valid:true}
 const start=minutes(row.startTime),end=minutes(row.endTime),first=minutes(row.lunchStart),last=minutes(row.lunchEnd)
 const lunch=row.lunchChoice==='none'?0:Math.max(0,Math.min(end,last)-Math.max(start,first))/60
 const hours=(end-start)/60-lunch
 return {hours:Number.isFinite(hours)?hours:0,lunch:Number.isFinite(lunch)?lunch:0,valid:end>start&&hours>0&&['usual','none'].includes(row.lunchChoice)&&(row.lunchChoice==='none'||last>first)&&row.lunchConfirmed&&(row.lunchChoice==='usual'||!!row.lunchReason?.trim())}
}
export function defaultLeaveDay(date,lunchStart='12:00'){
 const end=minutes(lunchStart)+30,lunchEnd=`${String(Math.floor(end/60)).padStart(2,'0')}:${String(end%60).padStart(2,'0')}`
 return {date,duration:'full',startTime:'10:00',endTime:'14:00',lunchStart,lunchEnd,lunchChoice:'usual',lunchConfirmed:false,lunchReason:''}
}
