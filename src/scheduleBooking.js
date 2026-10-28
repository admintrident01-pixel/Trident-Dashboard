// Read-only interpretation; matches backend/schedule_booking.py. No bulk migration.
const legacyNotBooked=new Set(['ba7a4325-00a6-46a1-8ec5-82549ca1f3df'])
export const bookingLabel=status=>({confirmed:'Booked','action-needed':'Not booked',option:'Optional'}[status]||'Not booked')
export function bookingControls(row){
 if(!row||row.source)return row
 let status=row.bookingStatus||'action-needed'
 if(row.bookingControlsVersion!==1){
  if(row.timing==='fixed'&&status==='option'){
   if(!legacyNotBooked.has(row.id))throw Error('This appointment is both Fixed and Optional. Ask which booking status to keep.')
   status='action-needed'
  }else status=row.timing==='fixed'||status==='confirmed'?'confirmed':status==='option'?'option':'action-needed'
 }
 return {...row,bookingStatus:status,urgency:row.urgency||(row.bookingStatus==='high-priority'?'high':'low'),timing:status==='confirmed'?'fixed':'flexible',bookingControlsVersion:1}
}
export const isBooked=row=>row.source?row.timing==='fixed':bookingControls(row).bookingStatus==='confirmed'
export const withBookingStatus=(row,status)=>({...bookingControls(row),bookingStatus:status,timing:status==='confirmed'?'fixed':'flexible',bookingControlsVersion:1})
