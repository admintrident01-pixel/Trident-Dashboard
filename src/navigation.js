import {myDayPilot} from './myDayModel.js'
const pages=['home','my-day','quotes','schedule','timesheet','leave','reports','vehicles','stock','settings','office']
const staffPages=['home','schedule','timesheet','leave','vehicles']
export function loadPage(){
 const page=window.location.hash.slice(1)
 return pages.includes(page)?page:'home'
}
export function canAccessPage(page,session){
 if(page==='my-day')return myDayPilot(session)
 return pages.includes(page)&&(session?.role==='admin'||staffPages.includes(page))
}
