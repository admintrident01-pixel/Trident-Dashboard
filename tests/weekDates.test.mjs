import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import {lastWeekMonday} from '../src/weekDates.js'
const context={window:{},Intl,Date};vm.createContext(context)
vm.runInContext(fs.readFileSync(new URL('../public/week-dates.js',import.meta.url),'utf8'),context)
test('Last week uses the previous Auckland Monday across week, year and daylight-saving boundaries',()=>{
 for(const [now,expected] of [['2026-10-19T11:00:00Z','2026-10-12'],['2026-10-18T10:59:00Z','2026-10-05'],['2026-10-18T11:01:00Z','2026-10-12'],['2027-01-03T11:01:00Z','2026-12-28'],['2026-09-27T11:01:00Z','2026-09-21'],['2026-04-05T12:01:00Z','2026-03-30']]){
  assert.equal(lastWeekMonday(new Date(now)),expected)
  assert.equal(context.window.TridentWeekDates.lastWeekMonday(new Date(now)),expected)
 }
})
const html=fs.readFileSync(new URL('../public/timesheet.html',import.meta.url),'utf8')
const shortcut=html.slice(html.indexOf('function selectLastWeek(){'),html.indexOf("document.getElementById('week').addEventListener('change'"))
test('time sheet shortcut follows the existing change event and respects locked drafts and busy controls',()=>{
 let changes=0
 const week={value:'2026-10-19',readOnly:false,disabled:false,dispatchEvent:e=>{assert.equal(e.type,'change');changes++}}
 const button={disabled:false}
 const c={document:{getElementById:id=>id==='week'?week:button},window:{TridentWeekDates:{lastWeekMonday:()=> '2026-10-12'}},Event}
 vm.createContext(c);vm.runInContext(shortcut,c);c.selectLastWeek();assert.equal(week.value,'2026-10-12');assert.equal(changes,1)
 c.selectLastWeek();assert.equal(changes,1)
 week.value='2026-10-19';week.readOnly=true;c.selectLastWeek();assert.equal(week.value,'2026-10-19')
 week.readOnly=false;button.disabled=true;c.selectLastWeek();assert.equal(week.value,'2026-10-19')
})
