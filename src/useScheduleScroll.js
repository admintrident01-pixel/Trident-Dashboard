import {useLayoutEffect,useRef} from 'react'
import {scrollDayLayout} from './scheduleMath'

// A full day scrolls at the same minutes-to-pixels scale as the normal workday.
export function useScheduleScroll(enabled,date,start,end){
 const ref=useRef(null)
 useLayoutEffect(()=>{
  const scroller=ref.current
  if(!enabled||!scroller)return
  const heading=scroller.querySelector('.schedule-column-headings'),tracks=scroller.querySelector('.schedule-column-tracks')
  if(!heading||!tracks)return
  let initial=true
  const measure=()=>{
   const previousHeight=tracks.getBoundingClientRect().height,previousTop=scroller.scrollTop
   const layout=scrollDayLayout(scroller.clientHeight,heading.offsetHeight,{start,end})
   tracks.style.height=layout.trackHeight+'px'
   scroller.scrollTop=initial?layout.scrollTop:previousHeight?previousTop/previousHeight*layout.trackHeight:layout.scrollTop
   initial=false
  }
  measure()
  const observer=new ResizeObserver(measure);observer.observe(scroller);observer.observe(heading)
  return()=>{observer.disconnect();tracks.style.removeProperty('height');scroller.scrollTop=0}
 },[enabled,date,start,end])
 return ref
}
