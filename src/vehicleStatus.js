export function checkDueStatus(checkDate, currentDate, nextCheckDue, bands={red:7,orange:14,yellow:21}) {
 if (!checkDate) return {colour:'unknown',label:'No check recorded',due:''}
 const start=Date.parse(checkDate+'T00:00:00Z'),current=Date.parse(currentDate+'T00:00:00Z')
 if (!Number.isFinite(start)||!Number.isFinite(current)) return {colour:'unknown',label:'No check recorded',due:''}
 const due=nextCheckDue?Date.parse(nextCheckDue+'T00:00:00Z'):start+30*86400000,days=Math.round((due-current)/86400000)
 return {colour:days<=bands.red?'red':days<=bands.orange?'orange':days<=bands.yellow?'yellow':'green',due:new Date(due).toISOString().slice(0,10),days,label:days<0?`Overdue by ${-days} day${days===-1?'':'s'}`:days===0?'Due today':`Up to date · due in ${days} day${days===1?'':'s'}`}
}

export const defaultVehicleColours={
 checkDays:{red:7,orange:14,yellow:21},km:{red:500,yellow:2000,green:4000},rucKm:{red:500,yellow:2000,green:4000},
 colours:{red:'#f9d4d1',orange:'#ffd8ae',yellow:'#fff1a3',green:'#cdebd3'},followUp:{yes:'orange',no:'green'}
}
export function kilometreColour(value,bands=defaultVehicleColours.km,ruc=false){
 if(value===null||value===undefined||value===''||!Number.isFinite(Number(value)))return 'unknown'
 const km=Number(value)
 if(ruc?km<bands.red:km<=bands.red)return 'red'
 return km<bands.yellow?'orange':km<bands.green?'yellow':'green'
}
export function followUpColour(value,settings=defaultVehicleColours){
 return value===true?settings.followUp.yes:value===false?settings.followUp.no:'unknown'
}
export function vehicleColourStyle(settings=defaultVehicleColours){
 return Object.fromEntries(Object.entries(settings.colours).flatMap(([name,hex])=>{
  const channels=hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4)
  const luminance=.2126*channels[0]+.7152*channels[1]+.0722*channels[2]
  return [[`--vehicle-${name}`,hex],[`--vehicle-${name}-text`,luminance>.179?'#111827':'#ffffff']]
 }))
}
