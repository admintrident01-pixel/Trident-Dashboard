import test from 'node:test'
import assert from 'node:assert/strict'
import {resizeOffice,splitOffice,fitOfficeLayout} from '../src/officeLayout.js'
const bounds={width:1200,height:700},initial={x:0,y:0,width:1200,height:700,split:50}
test('each workspace edge resizes while retaining the opposite edge',()=>{
 const left=resizeOffice(initial,'w',180,0,bounds);assert.equal(left.x,180);assert.equal(left.x+left.width,1200)
 const top=resizeOffice(initial,'n',0,120,bounds);assert.equal(top.y,120);assert.equal(top.y+top.height,700)
 assert.equal(resizeOffice(initial,'e',-180,0,bounds).width,1020)
 assert.equal(resizeOffice(initial,'s',0,-120,bounds).height,580)
 const corner=resizeOffice(initial,'nw',180,120,bounds);assert.equal(corner.width,1020);assert.equal(corner.height,580)
})
test('workspace stays usable and within bounds at drag extremes',()=>{
 for(const edge of ['n','s','e','w','ne','nw','se','sw'])for(const delta of [-10000,10000]){
  const r=resizeOffice(initial,edge,delta,delta,bounds);assert.ok(r.x>=0&&r.y>=0);assert.ok(r.width>=480&&r.height>=300);assert.ok(r.x+r.width<=1200&&r.y+r.height<=700)
 }
 assert.equal(splitOffice(0),50);assert.equal(splitOffice(5),20);assert.equal(splitOffice(99),80)
})
test('saved layout is clamped when returning on a smaller screen',()=>{
 const r=fitOfficeLayout({x:600,y:300,width:900,height:600,split:29},{width:750,height:450})
 assert.equal(r.split,29);assert.ok(r.x+r.width<=750);assert.ok(r.y+r.height<=450);assert.ok(r.width>=480&&r.height>=300)
})
