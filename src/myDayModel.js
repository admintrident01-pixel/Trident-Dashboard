export const myDayEnabled=session=>!!session?.email&&['admin','tech'].includes(session.role)
export const nzDay=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'Pacific/Auckland',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())
export function shiftDay(day,amount){const d=new Date(day+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+amount);return d.toISOString().slice(0,10)}
export function recordedMinutes(jobs,now){return Object.values(jobs||{}).reduce((sum,j)=>sum+(j?.sessions||[]).reduce((n,s)=>n+Math.max(0,((s.end?Date.parse(s.end):now)-Date.parse(s.start))/60000),0),0)}
export const hours=minutes=>(minutes/60).toFixed(2)
export const nzTime=value=>value?new Intl.DateTimeFormat('en-GB',{timeZone:'Pacific/Auckland',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(value)):''
export const mapsLink=address=>address?.trim()?'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(address):null
