import {myDayEnabled} from './myDayModel.js'
const pages=['home','workspace','my-day','job-import','quotes','schedule','oncall','timesheet','leave','reports','vehicles','stock','settings','office']
const staffPages=['home','workspace','schedule','oncall','timesheet','leave','vehicles']
export const homePage=session=>myDayEnabled(session)?'my-day':'workspace'
export function loadPage(){
 const page=window.location.hash.slice(1).split('?')[0]
 return pages.includes(page)&&page!=='home'?page:'my-day'
}
export function canAccessPage(page,session){
 if(page==='job-import')return false
 if(page==='my-day')return myDayEnabled(session)
 return pages.includes(page)&&(session?.role==='admin'||staffPages.includes(page))
}
