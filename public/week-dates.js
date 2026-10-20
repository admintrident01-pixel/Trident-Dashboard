(function(){
function lastWeekMonday(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-NZ',{timeZone:'Pacific/Auckland',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now)
 const value=type=>Number(parts.find(part=>part.type===type).value)
 const date=new Date(Date.UTC(value('year'),value('month')-1,value('day'),12))
 date.setUTCDate(date.getUTCDate()-(date.getUTCDay()+6)%7-7)
 return date.toISOString().slice(0,10)
}
window.TridentWeekDates={lastWeekMonday};
})();
