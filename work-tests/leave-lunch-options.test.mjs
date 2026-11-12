import assert from 'node:assert/strict'
import {defaultLeaveDay,leaveCalculation} from '../src/leaveRequestModel.js'

const base={...defaultLeaveDay('2026-11-17','12:00'),duration:'part',startTime:'10:00',endTime:'14:00',lunchConfirmed:true}
assert.equal(base.lunchChoice,'usual')
assert.equal(leaveCalculation(base).hours,3.5)
assert.equal(leaveCalculation({...base,lunchChoice:'none',lunchReason:'No unpaid lunch applies'}).hours,4)
assert.equal(leaveCalculation({...base,lunchChoice:'different',lunchReason:'Legacy choice'}).valid,false)

console.log('Leave lunch choices exclude the alternate lunch-time option.')
