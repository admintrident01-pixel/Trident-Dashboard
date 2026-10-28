import {useEffect,useRef} from 'react'

// Nonmodal dialog: the schedule remains visible and usable behind the editor.
export function useAppointmentWindow(open){
 const dialog=useRef(null),drag=useRef(null)
 function place(left,top){
  const node=dialog.current,rect=node.getBoundingClientRect()
  node.style.left=Math.max(8,Math.min(left,window.innerWidth-rect.width-8))+'px'
  node.style.top=Math.max(8,Math.min(top,window.innerHeight-rect.height-8))+'px'
 }
 useEffect(()=>{
  const node=dialog.current
  if(!open){if(node.open)node.close();return}
  const previous=document.activeElement
  if(!node.open){node.show();place((window.innerWidth-node.offsetWidth)/2,40)}
  const resize=()=>{const r=node.getBoundingClientRect();place(r.left,r.top)}
  window.addEventListener('resize',resize)
  return()=>{window.removeEventListener('resize',resize);drag.current=null;if(previous?.isConnected)previous.focus({preventScroll:true})}
 // The dialog ref is stable; opening and closing own the focus lifecycle.
 },[open])
 return {dialog,windowDrag:{
  onPointerDown(event){
   if(event.button!==0||event.target.closest('button,input,select,textarea'))return
   const rect=dialog.current.getBoundingClientRect()
   drag.current={x:event.clientX,y:event.clientY,left:rect.left,top:rect.top}
   event.currentTarget.setPointerCapture(event.pointerId);event.preventDefault()
  },
  onPointerMove(event){const d=drag.current;if(d)place(d.left+event.clientX-d.x,d.top+event.clientY-d.y)},
  onPointerUp(){drag.current=null},onPointerCancel(){drag.current=null},
  onKeyDown(event){
   if(event.target!==event.currentTarget||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(event.key))return
   event.preventDefault();const r=dialog.current.getBoundingClientRect(),step=event.shiftKey?40:10
   place(r.left+(event.key==='ArrowLeft'?-step:event.key==='ArrowRight'?step:0),r.top+(event.key==='ArrowUp'?-step:event.key==='ArrowDown'?step:0))
  }
 }}
}
