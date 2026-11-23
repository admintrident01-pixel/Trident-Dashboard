import {leaveTypeInfo} from './leaveTypes.js'

export function approvedLeavePaid(leave){
 if(!leave)return false
 if(leave.leaveType)return leaveTypeInfo(leave.leaveType).paid
 return leave.paid===true
}

export function timesheetPayableHours(day){
 if(!day)return 0
 const status=day.status||'Work'
 const gross=day.method==='times'?Math.max(0,(Date.parse('2000-01-01T'+day.finish)-Date.parse('2000-01-01T'+day.start))/3600000):Number(day.hours)||0
 const work=Math.max(0,gross-(status==='Work'&&day.unpaidLunch&&!(day.method==='direct'&&day.netDirectHours)?0.5:0))
 if(status!=='Work')return leaveTypeInfo(status).paid?work:0
 const timedLeave=day.leave||{}
 const leaveHours=Number(day.leaveHours??timedLeave.hoursPerDay)||0
 const leavePaid=typeof day.leavePaid==='boolean'?day.leavePaid:approvedLeavePaid(timedLeave)
 return work+(leavePaid?leaveHours:0)
}

function savedDayPayableHours(day){
 if(!day)return 0
 const status=day.status||'Work',hours=Math.max(0,Number(day.hours)||0)
 if(status!=='Work')return leaveTypeInfo(status).paid?hours:0
 const leave=day.leave||{}
 const leaveHours=Math.max(0,Number(day.leaveHours??leave.hoursPerDay)||0)
 return hours+(approvedLeavePaid(leave)?leaveHours:0)
}

export function sheetPayableHours(sheet){
 if(!sheet)return 0
 if(Number.isFinite(Number(sheet.payableTotal)))return Number(sheet.payableTotal)
 if(!Array.isArray(sheet.days))return Number(sheet.total)||0
 const derive=sheet.isDraft?timesheetPayableHours:savedDayPayableHours
 return sheet.days.reduce((sum,day)=>sum+derive(day),0)
}
