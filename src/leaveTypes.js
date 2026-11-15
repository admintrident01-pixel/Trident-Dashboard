export const LEAVE_TYPE_OPTIONS = [
 {value:'Paid annual leave',category:'annual',paid:true},
 {value:'Unpaid annual leave',category:'annual',paid:false},
 {value:'Sick leave paid',category:'sick',paid:true},
 {value:'Sick leave unpaid',category:'sick',paid:false},
 {value:'Other paid',category:'other',paid:true},
 {value:'Other unpaid',category:'other',paid:false},
]

export const DEFAULT_LEAVE_TYPE=LEAVE_TYPE_OPTIONS[0].value

const LEGACY_TYPES={
 'Annual leave':{category:'annual',paid:false},
 'Sick leave':{category:'sick',paid:true},
 'Other':{category:'other',paid:false},
}

const TYPE_DETAILS=Object.fromEntries(LEAVE_TYPE_OPTIONS.map(option=>[option.value,option]))

export function leaveTypeInfo(value){
 return TYPE_DETAILS[value]||LEGACY_TYPES[value]||{category:'other',paid:false}
}

export function leaveTypeShortLabel(value){
 return {'Annual leave':'Annual','Sick leave':'Sick','Other':'Other'}[value]||value||'Leave'
}

export function validLeaveType(value){
 return !!TYPE_DETAILS[value]||!!LEGACY_TYPES[value]
}

export function requestLeaveTypeLabel(request){
 if(!request)return ''
 const types=requestLeaveTypes(request)
 if(types.length===1)return types[0]
 if(types.length>1)return 'Mixed leave'
 return request.leaveType==='Other'?(request.other||'Other leave'):(request.leaveType||'Leave')
}

export function requestLeaveTypes(request){
 const daily=[...new Set((request?.dailyBreakdown||[]).map(row=>row.leaveType).filter(Boolean))]
 return daily.length?daily:(request?.leaveType?[request.leaveType]:[])
}

export function requestLeaveDescription(request){
 if(!request)return ''
 return requestLeaveTypes(request).some(type=>leaveTypeInfo(type).category==='other')?(request.other||''):''
}

export function requestPaidTotals(request){
 if(!request)return {paid:0,unpaid:0,total:0}
 if(request.dailyBreakdown?.length){
  return request.dailyBreakdown.reduce((totals,row)=>{
   const hours=Number(row.hoursPerDay)||0,paid=typeof row.paid==='boolean'?row.paid:leaveTypeInfo(row.leaveType||request.leaveType).paid
   totals[paid?'paid':'unpaid']+=hours;totals.total+=hours;return totals
  },{paid:0,unpaid:0,total:0})
 }
 if(Number.isFinite(Number(request.paidHours))&&Number.isFinite(Number(request.unpaidHours))){
  const paid=Number(request.paidHours),unpaid=Number(request.unpaidHours)
  return {paid,unpaid,total:paid+unpaid}
 }
 const total=Number(request.totalHours)||0,isPaid=typeof request.paid==='boolean'?request.paid:leaveTypeInfo(request.leaveType).paid
 return {paid:isPaid?total:0,unpaid:isPaid?0:total,total}
}
