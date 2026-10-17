import {test} from 'node:test'
import assert from 'node:assert/strict'
import {parseClientAddress} from '../src/scheduleQuickEntry.js'
test('extracts client and joins the street with its suburb',()=>{
 assert.deepEqual(parseClientAddress(' Janet Smith - 88 Kamo Road - Kensington '),{client:'Janet Smith',address:'88 Kamo Road, Kensington'})
 assert.deepEqual(parseClientAddress('Mere Rangi – 12 Bank Street – Whangārei'),{client:'Mere Rangi',address:'12 Bank Street, Whangārei'})
})
test('preserves hyphenated names and street numbers',()=>{
 assert.deepEqual(parseClientAddress('Anne-Marie Smith - 1-3 Port Road - Whangārei'),{client:'Anne-Marie Smith',address:'1-3 Port Road, Whangārei'})
 assert.deepEqual(parseClientAddress('Anne - 1 - 3 Port Road - Whangārei'),{client:'Anne',address:'1 - 3 Port Road, Whangārei'})
})
test('incomplete or oversized input does not replace existing form fields',()=>{
 for(const value of ['', 'Janet - 88 Kamo Road','Janet - 88 Kamo Road - ',' - 88 Kamo Road - Kamo','x'.repeat(161)+' - Street - Suburb'])assert.equal(parseClientAddress(value),null)
})
