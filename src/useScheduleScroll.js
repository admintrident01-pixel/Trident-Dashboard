import {useEffect,useLayoutEffect,useRef} from 'react'
import {scrollDayLayout,scheduleScale} from './scheduleMath'

// A full day scrolls at the same minutes-to-pixels scale as the normal workday.
export function useScheduleScroll(enabled,date,start,end,scale=1,normalView=true){
 const ref=useRef(null)
 const initialView=useRef('')
 useLayoutEffect(()=>{
  const scroller=ref.current
  if(!enabled||!scroller)return
  const heading=scroller.querySelector('.schedule-column-headings'),tracks=scroller.querySelector('.schedule-column-tracks')
  if(!heading||!tracks)return
  let frame=0
  const measure=()=>{
   const previousHeight=tracks.getBoundingClientRect().height,previousTop=scroller.scrollTop
   const viewportHeight=Math.max(320,scroller.clientHeight),available=Math.max(220,viewportHeight-heading.offsetHeight)
   const layout=normalView?scrollDayLayout(viewportHeight,heading.offsetHeight,{start,end},scale):{trackHeight:available*scheduleScale(scale),scrollTop:0}
   tracks.style.height=layout.trackHeight+'px'
   const view=date+'|'+(normalView?'normal':'fit')
   if(initialView.current!==view){initialView.current=view;scroller.scrollTop=layout.scrollTop}
   else if(previousHeight>0){const center=(previousTop+scroller.clientHeight/2)/previousHeight;scroller.scrollTop=Math.max(0,center*layout.trackHeight-scroller.clientHeight/2)}
  }
  measure()
  const observer=new ResizeObserver(()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(measure)});observer.observe(scroller);observer.observe(heading)
  return()=>{cancelAnimationFrame(frame);observer.disconnect()}
 },[enabled,date,start,end,scale,normalView])
 useEffect(()=>{
  const scroller=ref.current
  return()=>{
   if(!scroller)return
   const tracks=scroller.querySelector('.schedule-column-tracks')
   if(tracks)tracks.style.removeProperty('height')
   scroller.scrollTop=0
   initialView.current=''
  }
 },[enabled])
 return ref
}
