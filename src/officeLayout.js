export const defaultOfficeLayout={x:0,y:0,width:0,height:0,split:50}
const clamp=(n,min,max)=>Math.max(min,Math.min(max,n))
export function resizeOffice(layout,edge,dx,dy,bounds){
 const minWidth=Math.min(480,bounds.width),minHeight=Math.min(300,bounds.height)
 let {x=0,y=0,width=bounds.width,height=bounds.height}=layout
 width=width||bounds.width;height=height||bounds.height
 if(edge.includes('e'))width=clamp(width+dx,minWidth,bounds.width-x)
 if(edge.includes('s'))height=clamp(height+dy,minHeight,bounds.height-y)
 if(edge.includes('w')){const next=clamp(x+dx,0,x+width-minWidth);width+=x-next;x=next}
 if(edge.includes('n')){const next=clamp(y+dy,0,y+height-minHeight);height+=y-next;y=next}
 return {...layout,x,y,width,height}
}
export function splitOffice(value){return clamp(Number(value)||50,20,80)}
export function fitOfficeLayout(layout,bounds){
 const minWidth=Math.min(480,bounds.width),minHeight=Math.min(300,bounds.height)
 const x=clamp(layout.x,0,Math.max(0,bounds.width-minWidth)),y=clamp(layout.y,0,Math.max(0,bounds.height-minHeight))
 return {...layout,x,y,width:layout.width?clamp(layout.width,minWidth,bounds.width-x):0,height:layout.height?clamp(layout.height,minHeight,bounds.height-y):0,split:splitOffice(layout.split)}
}

export function resetOfficeLayout(){try{localStorage.removeItem('trident-office-layout-v1');localStorage.removeItem('trident-office-layout-v2')}catch{/* Storage may be disabled. */}}
