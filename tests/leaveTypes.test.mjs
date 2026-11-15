import test from 'node:test'
import assert from 'node:assert/strict'
import {requestLeaveDescription,requestLeaveTypeLabel,requestLeaveTypes,requestPaidTotals} from '../src/leaveTypes.js'

test('Mixed leave keeps the other description and paid totals',()=>{
 const request={
  leaveType:'Paid annual leave',
  other:'Community event',
  dailyBreakdown:[
   {date:'2026-11-16',leaveType:'Paid annual leave',paid:true,hoursPerDay:8},
   {date:'2026-11-17',leaveType:'Other unpaid',paid:false,hoursPerDay:4},
  ],
 }
 assert.equal(requestLeaveTypeLabel(request),'Mixed leave')
 assert.deepEqual(requestLeaveTypes(request),['Paid annual leave','Other unpaid'])
 assert.equal(requestLeaveDescription(request),'Community event')
 assert.deepEqual(requestPaidTotals(request),{paid:8,unpaid:4,total:12})
})
