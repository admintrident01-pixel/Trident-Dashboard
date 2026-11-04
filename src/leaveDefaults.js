export function defaultLeaveTechnician(technicians,ownName){
 return technicians.some(t=>t.name===ownName)?ownName:technicians[0]?.name||''
}
