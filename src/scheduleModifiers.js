// A stable, de-duplicated order also handles shared team bookings.
export function selectBlocks(selected,id,{ctrlKey=false,metaKey=false,shiftKey=false}={},anchor='',order=[]){
 if(shiftKey&&anchor&&order.includes(anchor)&&order.includes(id)){
  const a=order.indexOf(anchor),b=order.indexOf(id)
  return [...new Set([...selected,...order.slice(Math.min(a,b),Math.max(a,b)+1)])]
 }
 return ctrlKey||metaKey?selected.includes(id)?selected.filter(value=>value!==id):[...selected,id]:[id]
}
