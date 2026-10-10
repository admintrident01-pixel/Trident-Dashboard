export function checkDueStatus(checkDate, currentDate, nextCheckDue) {
 if (!checkDate) return {colour:'unknown',label:'No check recorded',due:''}
 const start=Date.parse(checkDate+'T00:00:00Z'),current=Date.parse(currentDate+'T00:00:00Z')
 if (!Number.isFinite(start)||!Number.isFinite(current)) return {colour:'unknown',label:'No check recorded',due:''}
 const due=nextCheckDue?Date.parse(nextCheckDue+'T00:00:00Z'):start+30*86400000,days=Math.round((due-current)/86400000)
 return {colour:days<=7?'red':days<=14?'orange':days<=21?'yellow':'green',due:new Date(due).toISOString().slice(0,10),days,label:days<0?`Overdue by ${-days} day${days===-1?'':'s'}`:days===0?'Due today':`Up to date · due in ${days} day${days===1?'':'s'}`}
}
