import assert from 'node:assert/strict'
import {createHmac} from 'node:crypto'
import test from 'node:test'
import {verifyTicket} from '../worker/schedule-live.js'

const secret='test-secret-'.padEnd(32,'x')
const signed=exp=>{
 const payload=Buffer.from(JSON.stringify({exp,room:'schedule',nonce:'test'})).toString('base64url')
 return payload+'.'+createHmac('sha256',secret).update(payload).digest('hex')
}

test('live tickets accept the thirty-minute renewal window',async()=>{
 const now=Date.now()
 assert.equal((await verifyTicket(secret,signed(Math.floor(now/1000)+1800),now))?.room,'schedule')
 assert.equal(await verifyTicket(secret,signed(Math.floor(now/1000)+1861),now),null)
 assert.equal(await verifyTicket(secret,signed(Math.floor(now/1000)-1),now),null)
})

test('live tickets reject altered payloads',async()=>{
 const now=Date.now(),ticket=signed(Math.floor(now/1000)+1800),[payload,mac]=ticket.split('.')
 assert.equal(await verifyTicket(secret,payload+'.'+mac.replace(/^./,mac[0]==='0'?'1':'0'),now),null)
})
