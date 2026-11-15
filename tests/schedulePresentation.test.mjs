import test from 'node:test'
import assert from 'node:assert/strict'
import {scheduleColumns,menuPosition} from '../src/schedulePresentation.js'

test('schedule keeps office and narrow custom columns readable without overwriting shared widths',()=>{
 const snapshot={staffTypes:{Office:'office'},columnWidths:{Alex:125}},before=JSON.stringify(snapshot)
 assert.deepEqual(scheduleColumns(snapshot,['Alex','Office']),{template:'32px minmax(160px,1.25fr) minmax(160px,0.5fr)',minimum:352})
 assert.equal(scheduleColumns(snapshot,['Alex','Office'],true).template,'32px minmax(160px,1fr) minmax(160px,1fr)')
 assert.equal(JSON.stringify(snapshot),before)
})

test('context menus fit the viewport at all corners including tall mobile menus',()=>{
 for(const anchor of [{x:0,y:0},{x:390,y:844},{x:180,y:800}]){
  const position=menuPosition(anchor,{width:300,height:1000},{width:390,height:844})
  assert.ok(position.left>=8&&position.left+300<=382)
  assert.ok(position.top>=8&&position.top+Math.min(1000,position.maxHeight)<=836)
 }
 assert.deepEqual(menuPosition({x:1300,y:880},{width:280,height:400},{width:1440,height:900}),{left:1152,top:492,maxHeight:884})
})
