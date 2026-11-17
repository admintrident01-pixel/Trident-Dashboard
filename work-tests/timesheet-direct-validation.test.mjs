import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const code=fs.readFileSync(new URL('../public/timesheet-direct-validation.js',import.meta.url),'utf8')

function row({hours='8',start='07:30',finish='16:00',lunch='unpaid',status='Work',method='direct',notes='',dataset={}}={}){
 const fields={'.status':{value:status},'.mode':{value:method},'.direct':{value:String(hours)},'.start':{value:start},'.finish':{value:finish},'.unpaid-lunch':{value:lunch},'.daynotes':{value:notes}}
 const check={hidden:false,className:'direct-check',textContent:'',setAttribute(name,value){this[name]=value}}
 return {fields,check,dataset,querySelector:selector=>selector==='.direct-check'?check:fields[selector]}
}

function harness(rows){
 const context={document:{querySelectorAll:selector=>selector==='#rows tr'?rows:[],querySelector:selector=>selector==='#rows tr'?rows[0]:selector==='.timesheet-help p'?null:null}}
 context.window=context
 context.calc=()=>{}
 context.collectSheet=draft=>({days:rows.map((row,index)=>({status:row.fields['.status'].value,method:row.fields['.mode'].value,hours:row.fields['.direct'].value,start:row.fields['.start'].value,finish:row.fields['.finish'].value,leaveHours:0,index}))})
 vm.createContext(context)
 vm.runInContext(code,context)
 return context
}

const defaults=row()
const customMismatch=row({hours:'6'})
const customMatching=row({hours:'6',start:'08:00',finish:'14:30'})
const timedLeave=row({hours:'4.5',dataset:{leaveHours:'3.5',leaveStart:'10:00',leaveEnd:'14:00',leaveLunchStart:'12:30',leaveLunchEnd:'13:00'}})
const weekend=row({hours:'0'})
const context=harness([defaults,customMismatch,customMatching,timedLeave,weekend,...Array.from({length:2},()=>row({hours:'0'}))])
const short=row({hours:'0.25',start:'07:30',finish:'08:00'})
const shortContext=harness([short])

assert.equal(context.directRowError(defaults),'')
assert.match(context.directRowError(customMismatch),/Enter actual start and finish times/)
assert.equal(context.directRowError(customMatching),'')
assert.equal(context.directRowError(timedLeave),'')
assert.equal(shortContext.directRowError(short),'')
assert.throws(()=>context.collectSheet(false),/Tuesday: Start, finish and lunch do not match 6\.00 paid hours/)

defaults.fields['.direct'].value='6'
assert.throws(()=>context.collectSheet(false),/Monday: Start, finish and lunch do not match 6\.00 paid hours/)
assert.equal(context.collectSheet(true).days[0].hours,'6')
defaults.fields['.direct'].value='8'

const notes=row({hours:'7',notes:'Separate work periods'})
assert.match(context.directRowError(notes),/do not match 7.00 paid hours/)

customMismatch.fields['.direct'].value='8'
const zero=context.collectSheet(false)
assert.equal(zero.days[4].start,'')
assert.equal(zero.days[4].finish,'')

console.log('Direct-hour default, custom, mismatch, notes and zero-day validation passed.')
