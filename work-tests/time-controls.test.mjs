import assert from 'node:assert/strict'
import '../public/time-controls.js'
const {step}=globalThis.TridentTimeControls
assert.equal(step('07:30',1),'07:45')
assert.equal(step('16:00',-1),'15:45')
assert.equal(step('00:00',-1),'00:00')
assert.equal(step('23:45',1),'23:45')
assert.equal(step(step('16:00',1),-1),'16:00')
console.log('Quarter-hour time stepping, both directions and day boundaries passed.')
