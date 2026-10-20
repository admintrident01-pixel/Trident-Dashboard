import {lastWeekMonday} from './weekDates.js'
const zone='Pacific/Auckland'
const formatter=new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'})
function wallValue(date){const parts=formatter.formatToParts(date),get=k=>Number(parts.find(p=>p.type===k).value);return Date.UTC(get('year'),get('month')-1,get('day'),get('hour'),get('minute'))}
function localInstant(wall){
 // First occurrence of a repeated clock time; skipped DST times move forward.
 const offsets=[...new Set([-86400000,0,86400000].map(delta=>wallValue(new Date(wall+delta))-(wall+delta)))]
 const candidates=offsets.map(offset=>wall-offset),valid=candidates.filter(value=>wallValue(new Date(value))===wall)
 return valid.length?Math.min(...valid):Math.max(...candidates)
}
export function reminderPlan(data,now=new Date()){
 const [hour,minute]=(data.timesheetTime||'').split(':').map(Number)
 const {timesheetWeekday:day,timesheetLeadHours:lead,timesheetRepeatHours:repeat}=data
 if(!Number.isInteger(day)||day<0||day>6||!Number.isInteger(hour)||!Number.isInteger(minute)||hour<0||hour>23||minute<0||minute>59||!Number.isInteger(lead)||lead<0||lead>168||!Number.isInteger(repeat)||repeat<1||repeat>168)return null
 const weekStart=lastWeekMonday(now),week=Date.parse(weekStart+'T00:00:00Z'),monday=week+7*86400000
 const finished=localInstant(monday),deadline=localInstant(monday+day*86400000+(hour*60+minute)*60000),proposed=deadline-lead*3600000,first=Math.max(finished,proposed)
 const label=value=>new Date(value).toLocaleString('en-NZ',{timeZone:zone,weekday:'short',day:'numeric',month:'short',hour:'numeric',minute:'2-digit'})
 const dayLabel=value=>new Date(value).toLocaleDateString('en-NZ',{timeZone:'UTC',day:'numeric',month:'short'})
 return {weekStart,weekLabel:dayLabel(week)+' – '+dayLabel(week+6*86400000),clamped:proposed<finished,deadline:label(deadline),slots:Array.from({length:4},(_,i)=>({label:label(first+i*repeat*3600000),iso:new Date(first+i*repeat*3600000).toISOString(),hoursAfterFirst:i*repeat}))}
}
