import {test} from 'node:test'
import assert from 'node:assert/strict'
import {clientSearchUrl,defaultClientSearchUrl} from '../src/clientSearch.js'
test('client search encodes only the name, preserving template parameters',()=>{
 const name="Anne & Co / O'Neil? #北"
 const url=new URL(clientSearchUrl('https://clients.example.nz/search?name={client}&sort=name',name))
 assert.equal(url.searchParams.get('name'),name)
 assert.equal(url.searchParams.get('sort'),'name')
 assert.equal(url.hash,'')
 assert.equal(url.username,'')
 assert.equal(new URL(clientSearchUrl(defaultClientSearchUrl,name)).searchParams.get('q'),name)
 assert.match(clientSearchUrl('https://example.nz/{client}',name),/%26.*%2F.*%27.*%3F.*%23/)
})
test('search rejects unsafe schemes, credentials, dynamic hosts and invalid templates',()=>{
 for(const template of ['javascript:alert({client})','data:text/html,{client}','https://user:password@example.nz/{client}','https://{client}.example.nz/','https://example.nz/{other}','https://example.nz/?name={client}\n','https://example.nz/','https:example.nz/{client}','https:/example.nz/{client}','',null])assert.equal(clientSearchUrl(template,'Name'),'')
 assert.equal(clientSearchUrl(defaultClientSearchUrl,'   '),'')
 assert.ok(clientSearchUrl('http://localhost/search?name={client}','Name'))
})
