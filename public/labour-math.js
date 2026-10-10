export const categories=['consumables','parts','labour','travel','mileage']
export const sellingRate=(cost,margin)=>Math.round((Number(cost)/(1-Number(margin)/100)+Number.EPSILON)*100)/100
export function calculateLabour(rows,gstPercent){
 if(!Array.isArray(rows)||rows.some(row=>!categories.includes(row.category)))throw Error('Choose valid calculator items.')
 const gst=Number(gstPercent)
 if(!Number.isFinite(gst)||gst<0||gst>100)throw Error('GST must be between 0 and 100%.')
 const groups=Object.fromEntries(categories.map(category=>[category,0])),lines=[]
 for(const category of categories)for(const row of rows.filter(r=>r.category===category)){
  const qty=Number(row.qty),cost=Number(row.cost),margin=Number(row.margin)
  if([row.qty,row.cost,row.margin].some(v=>String(v).trim()==='')||!Number.isFinite(qty)||qty<0||qty>1000000||!Number.isFinite(cost)||cost<0||cost>1000000||!Number.isFinite(margin)||margin<0||margin>99)throw Error('Use quantities and costs from 0 to 1,000,000 and margins from 0 to 99%.')
  if(['labour','travel'].includes(category)&&!Number.isInteger(qty*4))throw Error('Labour and travel hours must use 0.25 increments. 1.0 is one hour.')
  const description=String(row.description||'').trim()
  if(!description||description.length>4000)throw Error('Enter an item description.')
  // Round selling unit prices first, exactly as the editable quote lines do.
  const rate=sellingRate(cost,margin)
  const amount=Math.round(qty*rate*100)
  if(!Number.isSafeInteger(amount))throw Error('This calculation is too large.')
  groups[category]+=amount
  if(qty>0)lines.push({description,qty,rate})
 }
 const subtotal=Object.values(groups).reduce((sum,value)=>sum+value,0)
 if(!Number.isSafeInteger(subtotal))throw Error('This calculation is too large.')
 const tax=Math.round(subtotal*gst/100)
 return {groups,lines,subtotal,tax,total:subtotal+tax}
}
