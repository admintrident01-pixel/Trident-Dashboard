export const stockTreeSections=['products','intake','refurbing','assets','allocations','delivered']
export function stockQuantityKnown(product,assets){
 if(product.stocktakeQuantityConfirmed)return true
 return product.quantityBasis==='listed_assets'?product.sourceQuantity>0||assets.length>0:Boolean(product.openingQuantityConfirmed||!product.sourceRow||assets.length)
}
export function stockProductGroups({data,tab,query='',status='',pool=''}){
 if(!data||!stockTreeSections.includes(tab))return []
 const assets=Object.values(data.assets),receipts=Object.values(data.receipts),needle=query.trim().toLowerCase()
 const matches=(...values)=>values.flat(Infinity).filter(v=>v!==null&&v!==undefined).join(' ').toLowerCase().includes(needle)
 const assetMatches=a=>matches(a.number,a.previousNumbers,a.pool,a.status,a.location,a.client,a.reference,a.jobId,a.refurbTechnician,a.sourceAssetCell,(a.numberHistory||[]).map(h=>[h.number,h.referenceType,h.reference]))
 const receiptMatches=r=>matches(r.client,r.reference,r.jobId,r.pool,r.notes)
 const stageAsset=a=>tab==='products'||tab==='intake'&&a.status==='Incoming'||tab==='refurbing'&&['Refurbishing','Awaiting new asset number'].includes(a.status)||tab==='assets'&&(status?a.status===status:['Available','Allocated'].includes(a.status))&&(!pool||a.pool===pool)||tab==='allocations'&&a.status==='Allocated'||tab==='delivered'&&a.status==='With client'
 const stageReceipt=r=>tab==='products'||tab==='intake'&&r.pool!=='Trident refurb stock'&&!r.openingBalance||tab==='refurbing'&&r.pool==='Trident refurb stock'||tab==='assets'&&r.openingBalance&&(!status||status==='Available')&&(!pool||r.pool===pool)
 return Object.values(data.products).map(product=>{
  const allAssets=assets.filter(a=>a.productId===product.id),allPending=receipts.filter(r=>r.productId===product.id&&r.quantity>r.assetIds.length)
  const productMatch=matches(product.code,product.condition,product.description)
  const shownAssets=allAssets.filter(a=>stageAsset(a)&&(productMatch||assetMatches(a)))
  const pending=allPending.filter(r=>stageReceipt(r)&&(productMatch||receiptMatches(r)))
  const quantity=shownAssets.length+pending.reduce((n,r)=>n+r.quantity-r.assetIds.length,0)
  return {product,assets:shownAssets,pending,quantity,awaitingRefurbQuantity:allAssets.filter(a=>a.status==='Awaiting new asset number').length,known:stockQuantityKnown(product,allAssets),show:tab==='products'?(productMatch||shownAssets.length>0||pending.length>0):quantity>0}
 }).filter(g=>g.show).sort((a,b)=>a.product.code.localeCompare(b.product.code,undefined,{numeric:true})||({'NEW':0,'REFURB':1}[a.product.condition]??-1)-({'NEW':0,'REFURB':1}[b.product.condition]??-1))
}
