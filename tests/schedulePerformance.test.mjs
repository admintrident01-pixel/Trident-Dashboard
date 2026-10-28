import test from 'node:test'
import assert from 'node:assert/strict'
import {canApplyRouteSnapshot,schedulePollInterval} from '../src/scheduleSync.js'
import {travelReview} from '../src/scheduleResize.js'
import {travelSourceLabel} from '../src/scheduleMath.js'

test('late route results cannot replace another date, a save, or newer bookings',()=>{
 const request={target:'2026-10-29',generation:1},sync={date:request.target,generation:1,writing:false},result={data:{date:request.target},etag:'a'}
 assert.equal(canApplyRouteSnapshot(result,request,sync,'a'),true)
 for(const change of [{date:'2026-10-30'},{generation:2},{writing:true}])assert.equal(canApplyRouteSnapshot(result,request,{...sync,...change},'a'),false)
 assert.equal(canApplyRouteSnapshot(result,request,sync,'b'),false)
 assert.equal(canApplyRouteSnapshot({...result,data:{date:'2026-10-28'}},request,sync,'a'),false)
})
test('live sockets retain a minute safety check and fallback still polls',()=>{
 assert.equal(schedulePollInterval('live'),60000);assert.equal(schedulePollInterval('fallback'),10000)
})
test('pending route is clear, with the missing-location warning taking priority',()=>{
 assert.equal(travelReview({routePending:true}),'pending');assert.match(travelSourceLabel({routePending:true}),/Calculating/)
 assert.equal(travelReview({routePending:true,routeError:'Location missing'}),'review')
 assert.match(travelSourceLabel({routePending:true,estimatedSeconds:2000}),/Cached route/)
})
