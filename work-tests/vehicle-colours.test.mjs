import assert from 'node:assert/strict'
import {kilometreColour,followUpColour,checkDueStatus,defaultVehicleColours,vehicleColourStyle} from '../src/vehicleStatus.js'
for(const [km,colour] of [[-100,'red'],[0,'red'],[500,'red'],[501,'orange'],[1999,'orange'],[2000,'yellow'],[3999,'yellow'],[4000,'green'],[14784,'green']])assert.equal(kilometreColour(km),colour,km)
for(const [km,colour] of [[-1,'red'],[499,'red'],[500,'orange'],[1999,'orange'],[2000,'yellow'],[4000,'green']])assert.equal(kilometreColour(km,defaultVehicleColours.rucKm,true),colour,km)
for(const value of ['',null,undefined,'unknown'])assert.equal(kilometreColour(value),'unknown')
assert.equal(followUpColour(true),'orange');assert.equal(followUpColour(false),'green');assert.equal(followUpColour(null),'unknown')
assert.equal(checkDueStatus('2026-10-01','2026-10-13','2026-10-23',{red:2,orange:5,yellow:10}).colour,'yellow')
assert.equal(kilometreColour(4000,{red:100,yellow:1000,green:5000}),'yellow')
const settings={...defaultVehicleColours,colours:{...defaultVehicleColours.colours,green:'#000000'},followUp:{yes:'red',no:'yellow'}}
assert.equal(vehicleColourStyle(settings)['--vehicle-green-text'],'#ffffff');assert.equal(followUpColour(true,settings),'red')
console.log('Kilometre boundaries, missing/zero/overdue readings, configurable date bands, follow-up colours and readable text contrast passed.')
