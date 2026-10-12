import assert from 'node:assert/strict'
import {moveVehicle} from '../src/vehicle-order.js'
const rows=[{id:'A'},{id:'B'},{id:'C'}]
assert.deepEqual(moveVehicle(rows,0,1).map(row=>row.id),['B','A','C'])
assert.deepEqual(moveVehicle(rows,2,-1).map(row=>row.id),['A','C','B'])
assert.equal(moveVehicle(rows,0,-1),rows)
assert.equal(moveVehicle(rows,2,1),rows)
assert.deepEqual(rows.map(row=>row.id),['A','B','C'])
console.log('Vehicle columns move left/right, stay within bounds and preserve vehicle identities.')
