import {useState} from 'react'
import SortableTable from './SortableTable'
function Condition({value}){return value?<span className={'stock-badge stock-'+value.toLowerCase()}>{value}</span>:null}
function Status({value}){return <span className={'stock-badge stock-'+value.toLowerCase().replaceAll(' ','-')}>{value}</span>}
const date=(value,raw)=>value?new Date(value+'T12:00:00').toLocaleDateString('en-NZ'):raw?raw+' (year not recorded)':'Not recorded'
export default function StockProductTree({groups,tab,query,status,pool,open,onViewAsset,onAssetAction,onReceiptAction,onAllocation}){
 const [expanded,setExpanded]=useState({})
 const key=g=>[tab,query,status,pool,g.product.id].join('|')
 const isOpen=g=>expanded[key(g)]??Boolean(query.trim())
 const toggle=g=>setExpanded(current=>({...current,[key(g)]:!isOpen(g)}))
 const overview=tab==='products',columns=overview?8:5
 function assetActions(a){return <>
  {a.status==='Incoming'&&<button onClick={()=>open('custom_move',{assetIds:[a.id],destination:'assets',stageTitle:'Receive numbered stock'})}>Receive to stock on hand</button>}
  {a.status==='Refurbishing'&&<button onClick={()=>open('custom_move',{assetIds:[a.id],destination:'assets',stageTitle:'Complete refurb'})}>Complete refurb</button>}
  {a.status==='Available'&&<button onClick={()=>onAssetAction('allocate',a)}>Allocate to client</button>}
  {a.status==='Allocated'&&<button onClick={()=>onAssetAction('dispatch',a)}>Deliver to client</button>}
  {a.status==='Awaiting new asset number'&&<button onClick={()=>onAssetAction('relabel',a)}>Assign new asset number</button>}
  <button onClick={()=>onViewAsset(a)}>View / history</button>
  {a.allocationId&&<button onClick={()=>onAllocation(a.allocationId)}>View order</button>}
 </>}
 function productActions(g){const ids=g.assets.filter(a=>a.status==='Available').map(a=>a.id);return <>
  {['products','intake'].includes(tab)&&<button onClick={()=>open('receive',{productId:g.product.id})}>Receive stock</button>}
  {tab==='assets'&&ids.length>0&&<button onClick={()=>open('allocate',{assetIds:ids})}>Allocate to client</button>}
  {tab==='refurbing'&&g.assets.length>0&&<button onClick={()=>open('custom_move',{assetIds:g.assets.map(a=>a.id),destination:'assets',stageTitle:'Complete refurb'})}>Complete refurb</button>}
  {tab==='allocations'&&<button onClick={()=>open('dispatch',{assetIds:g.assets.map(a=>a.id)})}>Deliver stock</button>}
 </>}
 return <section className="stock-product-tree" aria-label="Products and their assets">
  <div className="stock-tree-toolbar"><span>Open a product to see its stock and asset numbers.</span><div><button onClick={()=>setExpanded(current=>({...current,...Object.fromEntries(groups.map(g=>[key(g),true]))}))}>Expand all</button><button onClick={()=>setExpanded(current=>({...current,...Object.fromEntries(groups.map(g=>[key(g),false]))}))}>Collapse all</button></div></div>
  <div className="table-scroll"><SortableTable groupSize={2} paginate paginationLabel="products" paginationReset={[tab,query,status,pool].join('|')} className={'settings-table stock-table stock-tree-table'+(overview?' stock-product-overview':'')}>
   <thead><tr><th>Product code</th><th>Description</th>{(overview?['Incoming stock','Refurbishment','Stock on hand','Stock allocated to client','Stock delivered to client']:['Quantity in this section','Asset numbers / awaiting numbers']).map(label=><th key={label}>{label}</th>)}<th>Actions</th></tr></thead>
   <tbody>{groups.flatMap(g=>{const p=g.product,opened=isOpen(g),detailId='stock-tree-'+tab+'-'+p.id;return [
    <tr className={'stock-product-parent'+(opened?' is-expanded':'')} key={p.id} onClick={e=>{if(!e.target.closest('button,a,input,select'))toggle(g)}}>
     <td data-sort-value={p.code+' '+(p.condition||'')}><button className="stock-product-toggle" aria-expanded={opened} aria-controls={detailId} aria-label={(opened?'Collapse':'Expand')+' product '+p.code+(p.condition?' '+p.condition:'')} onClick={()=>toggle(g)}><span className="stock-tree-chevron" aria-hidden="true">›</span><span className="stock-product-code">{p.code}<Condition value={p.condition}/></span></button></td>
     <td data-sort-value={p.description}><button className="stock-product-name" aria-expanded={opened} aria-controls={detailId} onClick={()=>toggle(g)}>{p.description}</button></td>
     {overview?[p.incomingQuantity,p.refurbingQuantity+g.awaitingRefurbQuantity,g.known?p.onHandQuantity:'Not recorded',p.allocatedQuantity,p.deliveredQuantity].map((value,index)=><td key={index}>{value}</td>):[<td key="quantity">{g.quantity}</td>,<td key="numbers">{g.assets.length} numbered{g.pending.length>0&&<small>{g.quantity-g.assets.length} awaiting numbers</small>}</td>]}
     <td className="stock-tree-actions">{productActions(g)}</td>
    </tr>,
    <tr key={p.id+'-assets'} id={detailId} hidden={!opened} className="stock-product-children"><td colSpan={columns}>{opened&&<div className="stock-product-content">
     <div className="stock-product-content-heading"><strong>{p.code}{p.condition?' · '+p.condition:''} — {p.description}</strong><span>{g.assets.length} numbered {g.assets.length===1?'asset':'assets'}{g.pending.length?', '+(g.quantity-g.assets.length)+' awaiting numbers':''}{query.trim()?' matching this search':''}</span></div>
     {g.assets.length>0&&<div className="stock-child-scroll"><table className="settings-table stock-table stock-asset-children"><thead><tr><th>Asset number</th><th>Status / location</th><th>Client / SO / PO / job</th><th>Dates</th><th>Actions</th></tr></thead><tbody>{g.assets.map(a=>{const label=a.numberHistory?.at(-1);return <tr key={a.id}><td><button className="stock-asset-number" onClick={()=>onViewAsset(a)}>{a.number}</button>{a.previousNumbers?.length>0&&<small>Earlier: {a.previousNumbers.join(', ')}</small>}</td><td><Status value={a.status}/><small>{a.location||a.pool}</small></td><td>{a.client||'—'}{a.reference&&<small>{a.referenceType||'PO'} {a.reference}</small>}{a.jobId&&<small>Job {a.jobId}</small>}</td><td><small>Added: {date(label?.addedAt,label?.addedAtText)}</small>{a.allocatedAt&&<small>Allocated: {date(a.allocatedAt)}</small>}{a.dispatchedAt&&<small>Delivered: {date(a.dispatchedAt)}</small>}{a.refurbCompletedAt&&<small>Refurb completed: {date(a.refurbCompletedAt)}</small>}</td><td className="stock-tree-actions">{assetActions(a)}</td></tr>})}</tbody></table></div>}
     {g.pending.map(r=><div className="stock-pending-row" key={r.id}><div><strong>{r.quantity-r.assetIds.length} {r.openingBalance?'opening stock units':'received units'} awaiting asset numbers</strong><small>{r.pool} · {date(r.date)}{r.client?' · '+r.client:''}{r.reference?' · '+(r.referenceType||'PO')+' '+r.reference:''}{r.jobId?' · Job '+r.jobId:''}</small></div><div className="stock-actions"><button onClick={()=>onReceiptAction('asset',r)}>Assign asset numbers</button>{r.pool==='Trident refurb stock'&&!r.refurbComplete&&<button onClick={()=>onReceiptAction('refurb_receipt_ready',r)}>Complete work</button>}</div></div>)}
     {!g.quantity&&<p className="stock-product-no-assets">{g.known?'No asset records in this section.':'No asset numbers or confirmed stock quantity recorded for this product yet.'}</p>}
    </div>}</td></tr>
   ]})}</tbody>
  </SortableTable></div>
 </section>
}
