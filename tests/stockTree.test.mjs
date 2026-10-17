import {test} from 'node:test'
import assert from 'node:assert/strict'
import {stockProductGroups} from '../src/stockTree.js'
const product=(id,code)=>({id,code,description:'Product '+code,sourceRow:2,quantityBasis:'listed_assets',sourceQuantity:null})
const data={products:{p:product('p','100050'),q:product('q','100034')},assets:{},receipts:{}}
for(const [id,status] of [['a','Available'],['b','Allocated'],['c','With client'],['d','Incoming'],['e','Refurbishing'],['f','Awaiting new asset number'],['g','Retired']])data.assets[id]={id,productId:'p',number:'NUMBER-'+id,status,pool:'New stock',previousNumbers:id==='a'?['OLD-42']:[],numberHistory:[{reference:'HISTORY-PO'}]}
data.receipts={incoming:{id:'incoming',productId:'p',quantity:3,assetIds:['d'],pool:'New stock',reference:'INCOMING-PO'},opening:{id:'opening',productId:'p',quantity:2,assetIds:[],pool:'New stock',openingBalance:true},refurb:{id:'refurb',productId:'p',quantity:2,assetIds:['e'],pool:'Trident refurb stock'}}
const groups=(tab,options={})=>stockProductGroups({data,tab,...options})
test('product order and unknown quantities remain distinct from zero',()=>{const all=groups('products');assert.deepEqual(all.map(g=>g.product.code),['100034','100050']);assert.equal(all[0].known,false);assert.equal(all[1].assets.length,7)})
test('each stage includes only its own assets and unnumbered balances',()=>{for(const [tab,ids,quantity] of [['intake',['d'],3],['refurbing',['e','f'],3],['assets',['a','b'],4],['allocations',['b'],1],['delivered',['c'],1]]){const [g]=groups(tab);assert.deepEqual(g.assets.map(a=>a.id),ids);assert.equal(g.quantity,quantity)}})
test('search finds past numbers, label references and receipt references',()=>{assert.deepEqual(groups('products',{query:'OLD-42'})[0].assets.map(a=>a.id),['a']);assert.equal(groups('products',{query:'HISTORY-PO'})[0].assets.length,7);assert.equal(groups('intake',{query:'INCOMING-PO'})[0].quantity,2);assert.equal(groups('assets',{query:'no match'}).length,0)})
test('stock filters apply to both numbered and pending units',()=>{assert.equal(groups('assets',{status:'Allocated'})[0].quantity,1);assert.equal(groups('assets',{pool:'Trident refurb stock'}).length,0);assert.equal(groups('assets',{status:'Retired'})[0].assets[0].id,'g')})
test('matching one asset never changes the product refurbishment total',()=>{assert.equal(groups('products',{query:'NUMBER-a'})[0].awaitingRefurbQuantity,1)})
