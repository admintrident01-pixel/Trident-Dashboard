import test from 'node:test'
import assert from 'node:assert/strict'
import {pageWindow,pageNumbers,orderedPage} from '../src/pagination.js'
test('defaults to 10 and safely paginates 101 records at each supported size',()=>{
 for(const size of [10,20,50,100]){const records=Array.from({length:101},(_,i)=>i),seen=[];const pages=pageWindow(records.length,1,size).pages;for(let page=1;page<=pages;page++)seen.push(...orderedPage(records,null,page,size).rows);assert.deepEqual(seen,records)}
 assert.equal(pageWindow(101).size,10);assert.equal(pageWindow(101).pages,11)
})
test('sorts the full dataset before selecting a page',()=>{
 const records=Array.from({length:101},(_,i)=>101-i)
 assert.deepEqual(orderedPage(records,(a,b)=>a-b,1,20).rows,Array.from({length:20},(_,i)=>i+1))
 assert.deepEqual(orderedPage(records,(a,b)=>a-b,6,20).rows,[101])
 assert.deepEqual(orderedPage(records,(a,b)=>b-a,1,20).rows,Array.from({length:20},(_,i)=>101-i))
})
test('filtered and deleted records clamp pages without gaps or duplicates',()=>{
 const records=Array.from({length:101},(_,i)=>i).filter(i=>i%2===0)
 const last=orderedPage(records,null,99,20);assert.equal(last.page,3);assert.equal(last.total,51);assert.equal(last.first,41);assert.equal(last.last,51);assert.equal(last.rows.length,11)
 const empty=pageWindow(0,99,20);assert.equal(empty.page,1);assert.equal(empty.first,0);assert.equal(empty.last,0)
 assert.equal(pageWindow(3,-5,7).size,10)
})
test('page buttons remain compact and expose first, current and final page',()=>{
 assert.deepEqual(pageNumbers(1,2),[1,2]);const buttons=pageNumbers(50,100);assert.deepEqual(buttons,[1,null,48,49,50,51,52,null,100]);assert.equal(buttons.length,9)
})
