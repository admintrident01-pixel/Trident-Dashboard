import {myDayEnabled} from './myDayModel.js'
const pages=['home','workspace','my-day','quotes','schedule','timesheet','leave','reports','vehicles','stock','settings','office']
const staffPages=['home','workspace','schedule','timesheet','leave','vehicles']
export function loadPage(){
 const page=window.location.hash.slice(1)
 return pages.includes(page)&&page!=='home'?page:'my-day'
}
export function canAccessPage(page,session){
 if(page==='my-day')return myDayEnabled(session)
 return pages.includes(page)&&(session?.role==='admin'||staffPages.includes(page))
}
