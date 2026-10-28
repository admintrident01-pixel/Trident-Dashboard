import {timeMinutes,timeText} from './scheduleMath.js'

export const isLunch=row=>row.source==='lunch'||row.type?.trim().toLowerCase()==='lunch'
// Ignore old lunch records even during a rolling frontend/API release.
export const scheduleAppointments=snapshot=>(snapshot?.appointments||[]).filter(row=>!isLunch(row))
export function quickWeekDays(date){
 const monday=new Date(date+'T12:00:00')
 monday.setDate(monday.getDate()-(monday.getDay()+6)%7)
 return Array.from({length:5},(_,offset)=>{
  const day=new Date(monday);day.setDate(day.getDate()+offset)
  return `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,'0')}-${String(day.getDate()).padStart(2,'0')}`
 })
}
export function calendarPeriods(snapshot){
 if(!snapshot)return []
 const periods=[],holiday=snapshot.publicHolidays?.find(h=>h.date===snapshot.date)
 if(holiday)periods.push({kind:'holiday',start:'00:00',duration:1440,label:holiday.name+' · Public holiday'})
 const start=snapshot.lunchShading?.start||snapshot.lunchStart||'12:00',duration=30
 periods.push({kind:'lunch',start,duration,label:`Lunch ${start}–${timeText(timeMinutes(start)+duration)}`})
 return periods
}
