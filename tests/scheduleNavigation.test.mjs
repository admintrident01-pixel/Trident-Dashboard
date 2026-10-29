import test from 'node:test'
import assert from 'node:assert/strict'
import {adjacentWeekday,columnWidth,columnTemplate} from '../src/scheduleCalendar.js'
test('arrows skip weekends across month/year boundaries and from a chosen weekend',()=>{
 for(const [day,direction,expected] of [['2026-10-30',1,'2026-11-02'],['2026-11-02',-1,'2026-10-30'],['2026-10-31',1,'2026-11-02'],['2026-11-01',-1,'2026-10-30'],['2027-01-01',1,'2027-01-04']])assert.equal(adjacentWeekday(day,direction),expected)
})
test('office defaults to half width and saved per-person widths override defaults',()=>{
 const snapshot={staffTypes:{Alex:'technician',Office:'office'},columnWidths:{Alex:125}}
 assert.equal(columnWidth(snapshot,'Office'),50);assert.equal(columnWidth(snapshot,'Alex'),125)
 assert.equal(columnTemplate(snapshot,['Alex','Office']),'32px minmax(0,1.25fr) minmax(0,0.5fr)')
 assert.equal(columnWidth({...snapshot,columnWidths:{Office:90}},'Office'),90)
})
