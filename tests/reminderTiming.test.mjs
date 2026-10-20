import test from 'node:test'
import assert from 'node:assert/strict'
import {reminderPlan} from '../src/reminderTiming.js'

const config={timesheetWeekday:0,timesheetTime:'17:00',timesheetLeadHours:24,timesheetRepeatHours:24}

test('Monday deadline with Sunday lead waits for completed week',()=>{
 const plan=reminderPlan(config,new Date('2026-10-20T23:00:00Z'))
 assert.equal(plan.weekStart,'2026-10-12')
 assert.equal(plan.clamped,true)
 assert.equal(plan.slots[0].iso,'2026-10-18T11:00:00.000Z')
 assert.equal(plan.slots.length,4)
 assert.deepEqual(plan.slots.map(s=>s.hoursAfterFirst),[0,24,48,72])
})

test('Tuesday deadline starts Monday at configured lead time',()=>{
 const plan=reminderPlan({...config,timesheetWeekday:1},new Date('2026-10-21T00:00:00Z'))
 assert.equal(plan.clamped,false)
 assert.equal(plan.slots[0].iso,'2026-10-19T04:00:00.000Z')
})

test('Zero lead starts at deadline and follows custom interval',()=>{
 const plan=reminderPlan({...config,timesheetLeadHours:0,timesheetRepeatHours:6},new Date('2026-10-21T00:00:00Z'))
 assert.equal(plan.slots[0].iso,'2026-10-19T04:00:00.000Z')
 assert.equal(plan.slots[3].iso,'2026-10-19T22:00:00.000Z')
})

test('Auckland date rather than browser date chooses previous week',()=>{
 assert.equal(reminderPlan(config,new Date('2026-10-18T10:59:59Z')).weekStart,'2026-10-05')
 assert.equal(reminderPlan(config,new Date('2026-10-18T11:00:00Z')).weekStart,'2026-10-12')
})

test('Year boundary stays aligned to Monday',()=>{
 assert.equal(reminderPlan(config,new Date('2027-01-03T12:00:00Z')).weekStart,'2026-12-28')
})

test('Followup interval is elapsed hours across both DST boundaries',()=>{
 for(const date of ['2026-04-01T00:00:00Z','2026-09-23T00:00:00Z']){
  const plan=reminderPlan({...config,timesheetWeekday:5,timesheetLeadHours:0},new Date(date))
  for(let i=1;i<4;i++)assert.equal(Date.parse(plan.slots[i].iso)-Date.parse(plan.slots[i-1].iso),86400000)
 }
})

test('Skipped and repeated Auckland deadline times match server policy',()=>{
 const spring=reminderPlan({...config,timesheetWeekday:6,timesheetTime:'02:30',timesheetLeadHours:0},new Date('2026-09-23T00:00:00Z'))
 assert.equal(spring.slots[0].iso,'2026-09-26T14:30:00.000Z')
 const autumn=reminderPlan({...config,timesheetWeekday:6,timesheetTime:'02:30',timesheetLeadHours:0},new Date('2026-04-01T00:00:00Z'))
 assert.equal(autumn.slots[0].iso,'2026-04-04T13:30:00.000Z')
})

test('Incomplete or invalid timing shows no misleading schedule',()=>{
 for(const patch of [{timesheetTime:''},{timesheetTime:'25:00'},{timesheetRepeatHours:0},{timesheetRepeatHours:169},{timesheetWeekday:-1},{timesheetLeadHours:-1}])assert.equal(reminderPlan({...config,...patch}),null)
})
