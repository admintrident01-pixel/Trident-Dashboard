import {useLayoutEffect,useRef} from 'react'
import '../public/time-entry.js'
import './TimeEntry.css'

export default function TimeEntry({value='',onChange,label='Time',disabled=false,id,name,required=false,className='',step=900,min='00:00',max,allowEndOfDay=false,onActivate}){
 const source=useRef(null),control=useRef(null)
 useLayoutEffect(()=>{
  control.current=globalThis.TridentTimeEntry.enhance(source.current)
  return()=>{control.current.destroy();control.current=null}
 },[])
 useLayoutEffect(()=>{
  control.current.update({value,onChange,label,disabled,id,required,step,min,max:max||(allowEndOfDay?'24:00':'23:59'),allowEndOfDay,onActivate})
 },[value,onChange,label,disabled,id,required,step,min,max,allowEndOfDay,onActivate])
 return <span className={`trident-time-host ${className}`}><input ref={source} type="hidden" name={name} value={value} disabled={disabled}/></span>
}
