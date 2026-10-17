import {timeMinutes,timeText} from './scheduleMath.js'
const clock=value=>/^([01]\d|2[0-3]):[0-5]\d$/.test(value||'')
const endMinutes=value=>value==='00:00'?1440:timeMinutes(value)
export function appointmentTimeForm(appointment){
 return {...appointment,timeBasis:appointment.timeBasis||'start',endTime:timeText((timeMinutes(appointment.start)+Number(appointment.duration))%1440)}
}
export function updateAppointmentTime(form,field,value){
 const next={...form,[field]:value}
 if(field==='timeBasis')return next
 if(next.timeBasis==='end'){
  const start=clock(next.endTime)&&next.duration!==''?endMinutes(next.endTime)-Number(next.duration):-1
  next.start=start>=0&&start<1440?timeText(start):''
 }else if(clock(next.start)&&next.duration!=='')next.endTime=timeText((timeMinutes(next.start)+Number(next.duration))%1440)
 return next
}
export function appointmentTimeError(form){
 if(form.duration===''||!Number.isInteger(form.duration)||form.duration<15||form.duration>1440||form.duration%15)return 'Use a duration in 15-minute steps.'
 if(form.timeBasis==='end'&&(!clock(form.endTime)||endMinutes(form.endTime)<form.duration))return 'Choose an end time that leaves enough time for this appointment on the same day.'
 if(form.timeBasis==='end'&&endMinutes(form.endTime)%15)return 'Choose an end time in 15-minute steps.'
 if(!clock(form.start)||timeMinutes(form.start)%15)return 'Choose a start time in 15-minute steps.'
 if(timeMinutes(form.start)+form.duration>1440)return 'The appointment must finish by midnight.'
 return ''
}
