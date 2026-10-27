import {assignedTechs,timeMinutes} from './scheduleMath.js'
const mapsUrl=stops=>{const query=new URLSearchParams({api:'1',origin:stops[0],destination:stops.at(-1),travelmode:'driving'});if(stops.length>2)query.set('waypoints',stops.slice(1,-1).join('|'));return 'https://www.google.com/maps/dir/?'+query}
export function wholeRoute(appointments,technician,depot,travelBlocks=[]){
 const bookings=appointments.filter(a=>!a.cancelled&&!a.source&&assignedTechs(a).includes(technician)).slice().sort((a,b)=>timeMinutes(a.start)-timeMinutes(b.start)||a.id.localeCompare(b.id))
 if(!bookings.length)return {error:'No appointments for this technician on this day.'}
 if(!depot)return {error:'Set the depot address before showing the route.'}
 if(travelBlocks.some(b=>b.technician===technician&&b.routeLocationMissing))return {error:'Add a confirmed location to every appointment before showing the whole route. Placeholder locations are not sent to Google.'}
 if(bookings.some(a=>!a.address?.trim()))return {error:'Add an address to every appointment before showing the whole route.'}
 const stops=[depot],parts=[]
 for(const booking of bookings){
  const workshop=side=>travelBlocks.some(b=>b.workshop&&b.technician===technician&&b.anchorId===booking.id&&b.side===side)
  if(workshop('before')&&stops.at(-1)!==depot)stops.push(depot)
  stops.push(booking.address)
  if(workshop('after'))stops.push(depot)
 }
 if(stops.at(-1)!==depot)stops.push(depot)
 let start=0
 while(start<stops.length-1){
  let end=Math.min(start+10,stops.length-1)
  while(end>start+1&&mapsUrl(stops.slice(start,end+1)).length>2048)end--
  const segment=stops.slice(start,end+1),url=mapsUrl(segment)
  if(url.length>2048)return {error:'One route address is too long. Shorten it before showing the map.'}
  parts.push({url,stops:segment});start=end
 }
 return {bookings,stops,parts}
}
export function routeDistanceLabel(total){return total?.complete&&Number.isFinite(total.distanceMeters)?`${(total.distanceMeters/1000).toFixed(1)} km`:'— km'}
