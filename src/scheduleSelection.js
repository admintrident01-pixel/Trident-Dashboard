import {isBooked} from './scheduleBooking.js'
import {timeMinutes,timeText} from './scheduleMath.js'
// Explicit selection includes its own anchored travel, never neighbouring bookings.
export function linkedSelection(ids,blocks){
 const selected=new Set(ids)
 return blocks.filter(b=>!b.cancelled&&(selected.has(b.id)||b.source==='travel'&&b.linked!==false&&selected.has(b.anchorId)))
}
export function selectionDraft(blocks,delta,from='',to=''){
 return blocks.map(b=>{const technicians=(b.technicians||[b.technician]).map(n=>from&&to&&n===from?to:n);return {...b,start:timeText(timeMinutes(b.start)+delta),technician:technicians[0],technicians:[...new Set(technicians)]}})
}
export function selectionMoveError(blocks,delta){
 if(blocks.some(b=>b.source==='leave'))return 'Approved leave cannot be moved with a selection.'
 const booked=blocks.find(b=>b.source!=='travel'&&isBooked(b))
 if(booked)return `${booked.client} is booked. Unbook it before moving.`
 if(blocks.some(b=>timeMinutes(b.start)+delta<0||timeMinutes(b.start)+b.duration+delta>1440))return 'The selection would leave the selected day.'
 return ''
}
export function intersectingIds(rows,rect){
 return rows.filter(row=>row.right>rect.left&&row.left<rect.right&&row.bottom>rect.top&&row.top<rect.bottom).map(row=>row.id)
}
