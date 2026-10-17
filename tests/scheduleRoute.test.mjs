import {test} from 'node:test'
import assert from 'node:assert/strict'
import {wholeRoute,routeDistanceLabel} from '../src/scheduleRoute.js'
const a={id:'a',technician:'Rick',start:'09:00',address:'1 Road & Lane',client:'A'},b={...a,id:'b',start:'11:00',address:'2 Road',client:'B'}
test('whole route keeps appointment order with depot at both ends and excludes non-bookings',()=>{
 const route=wholeRoute([b,{...a,id:'cancelled',cancelled:true},{...a,id:'lunch',source:'lunch'},a,{...a,id:'other',technician:'Daryll'}],'Rick','Depot')
 assert.deepEqual(route.stops,['Depot','1 Road & Lane','2 Road','Depot'])
 const url=new URL(route.parts[0].url);assert.equal(url.searchParams.get('waypoints'),'1 Road & Lane|2 Road');assert.equal(url.searchParams.get('origin'),'Depot');assert.equal(url.searchParams.get('destination'),'Depot');assert.equal(url.searchParams.get('api'),'1')
})
test('long routes split without dropping or reordering stops',()=>{
 const rows=Array.from({length:25},(_,i)=>({...a,id:String(i),start:`${String(8+Math.floor(i/4)).padStart(2,'0')}:${String(i%4*15).padStart(2,'0')}`,address:'Road '+i}))
 const route=wholeRoute(rows,'Rick','Depot')
 assert.deepEqual(route.parts.flatMap((p,i)=>i?p.stops.slice(1):p.stops),route.stops)
 assert.ok(route.parts.every(p=>p.stops.length<=11&&p.url.length<=2048))
})
test('missing stops and empty days are explicit errors',()=>{
 assert.match(wholeRoute([],'Rick','Depot').error,/No appointments/)
 assert.match(wholeRoute([{...a,address:''}],'Rick','Depot').error,/every appointment/)
 assert.match(wholeRoute([a],'Rick','').error,/depot/)
})
test('header kilometres require complete Google estimates',()=>{
 assert.equal(routeDistanceLabel({complete:true,distanceMeters:24310}),'24.3 km')
 assert.equal(routeDistanceLabel({complete:false,distanceMeters:24310}),'— km')
 assert.equal(routeDistanceLabel({complete:true,distanceMeters:0}),'0.0 km')
})
