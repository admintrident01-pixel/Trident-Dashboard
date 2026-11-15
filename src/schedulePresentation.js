import {columnWidth} from './scheduleCalendar.js'

// A view preference only: shared technician widths and business settings are intact.
export function scheduleColumns(snapshot,names,equal=false){
 const weights=names.map(name=>equal?1:Math.max(.25,Number(columnWidth(snapshot,name))/100||1))
 return {template:'32px '+weights.map(weight=>`minmax(160px,${weight}fr)`).join(' '),minimum:32+weights.reduce((sum,weight)=>sum+Math.max(160,weight*120),0)}
}

export function menuPosition(anchor,size,viewport){
 const margin=8,maxHeight=Math.max(1,viewport.height-margin*2)
 return {left:Math.max(margin,Math.min(anchor.x,viewport.width-size.width-margin)),top:Math.max(margin,Math.min(anchor.y,viewport.height-Math.min(size.height,maxHeight)-margin)),maxHeight}
}
