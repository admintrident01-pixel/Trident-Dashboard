export const extraNumbers=entry=>entry.numbers.map(n=>n.trim()).filter(Boolean)
export const foundCount=entry=>Object.values(entry.decisions).filter(v=>v==='found').length
export function setAssetChecks(entry,decisions){
 const extra=extraNumbers(entry).length,unnumbered=Math.max(0,(Number(entry.count)||0)-foundCount(entry)-extra)
 return {...entry,decisions,count:foundCount({decisions})+extra+unnumbered}
}
export function entryProblem(row,entry){
 if(row.assets.some(a=>!['found','missing','retire'].includes(entry.decisions[a.id])))return 'Mark each listed asset Found, Not found or Retire.'
 if(entry.count===''||entry.count==null)return 'Enter how many items you counted, including zero.'
 const total=Number(entry.count),numbers=extraNumbers(entry)
 if(!Number.isInteger(total)||total<0||total>10000)return 'Enter a whole number from 0 to 10,000.'
 if(new Set(numbers.map(n=>n.toLowerCase())).size!==numbers.length)return 'An additional asset number is entered twice. Remove the duplicate.'
 if(total<foundCount(entry)+numbers.length)return 'The total must include every found asset and additional number.'
 return ''
}
