import assert from 'node:assert/strict'
import {loadSession,saveSession} from '../src/session.js'
function memory(){const map=new Map();return {getItem:k=>map.get(k)||null,setItem:(k,v)=>map.set(k,v),removeItem:k=>map.delete(k)}}
globalThis.sessionStorage=memory();globalThis.localStorage=memory()
const session={token:'trident_test',email:'tech@example.nz',role:'tech'}
saveSession(session);assert.deepEqual(loadSession(),session)
assert.equal(localStorage.getItem('trident-session-v1'),null)
saveSession({...session,remember:true});assert.equal(loadSession().remember,true)
assert.equal(sessionStorage.getItem('trident-session-v1'),null)
globalThis.sessionStorage=memory();assert.equal(loadSession().token,session.token)
saveSession(null);assert.equal(loadSession(),null)
saveSession({token:'local-only'});assert.equal(loadSession(),null)
sessionStorage.setItem('trident-session-v1','bad JSON');assert.equal(loadSession(),null)
console.log('Session persistence and sign-out checks passed.')
