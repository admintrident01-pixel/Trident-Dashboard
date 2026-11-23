import test from 'node:test'
import assert from 'node:assert/strict'
import {approvedLeavePaid,sheetPayableHours,timesheetPayableHours} from '../src/timesheetPayable.js'

test('Unpaid full-day leave contributes no payable hours',()=>{
 assert.equal(timesheetPayableHours({status:'Sick leave unpaid',method:'direct',hours:8}),0)
 assert.equal(timesheetPayableHours({status:'Unpaid annual leave',method:'direct',hours:8}),0)
 assert.equal(timesheetPayableHours({status:'Sick leave paid',method:'direct',hours:8}),8)
})

test('Timed unpaid leave leaves only actual work payable',()=>{
 const day={status:'Work',method:'times',start:'08:00',finish:'10:30',unpaidLunch:true,leaveHours:6,leavePaid:false,leaveLabel:'Sick leave unpaid 10:30–16:30'}
 assert.equal(timesheetPayableHours(day),2)
 assert.equal(timesheetPayableHours({...day,leavePaid:true}),8)
})

test('Saved sheets use payableTotal and derive it for older records',()=>{
 const days=[
  {status:'Work',method:'direct',hours:7.5,enteredHours:8,unpaidLunch:true},
  {status:'Work',method:'times',hours:2,enteredHours:2.5,start:'08:00',finish:'10:30',unpaidLunch:true,leave:{leaveType:'Sick leave unpaid',hoursPerDay:6,paid:false}},
 ]
 assert.equal(sheetPayableHours({payableTotal:9.5,total:15.5,days}),9.5)
 assert.equal(sheetPayableHours({total:15.5,days}),9.5)
})

test('Older drafts still use entered hours rather than stored net hours',()=>{
 const days=[{status:'Work',method:'direct',hours:8,unpaidLunch:true}]
 assert.equal(sheetPayableHours({isDraft:true,total:7.5,days}),7.5)
})

test('Approved leave paid status is derived from the leave type',()=>{
 assert.equal(approvedLeavePaid({leaveType:'Sick leave unpaid',paid:true}),false)
 assert.equal(approvedLeavePaid({leaveType:'Sick leave unpaid'}),false)
 assert.equal(approvedLeavePaid({leaveType:'Sick leave'}),true)
})
