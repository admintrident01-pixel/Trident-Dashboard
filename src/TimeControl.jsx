import {useEffect,useRef} from 'react'
import '../public/time-controls.js'
const choices=Array.from({length:96},(_,i)=>`${String(Math.floor(i/4)).padStart(2,'0')}:${String(i%4*15).padStart(2,'0')}`)
export default function TimeControl({label,value,disabled,required,onActivate,onChange}){
 const input=useRef(null),latest=useRef(null)
 useEffect(()=>{latest.current={value,disabled,onActivate,onChange}})
 const step=direction=>{const current=latest.current;if(current.disabled)return;current.onActivate();current.onChange(globalThis.TridentTimeControls.step(current.value,direction))}
 useEffect(()=>{const element=input.current;const wheel=event=>{if(latest.current.disabled||!event.deltaY)return;event.preventDefault();const current=latest.current;current.onActivate();current.onChange(globalThis.TridentTimeControls.step(current.value,event.deltaY<0?1:-1))};element.addEventListener('wheel',wheel,{passive:false});return()=>element.removeEventListener('wheel',wheel)},[])
 return <div className="time-control"><select ref={input} className="time" aria-label={label} value={value} disabled={disabled} required={required} onFocus={onActivate} onChange={e=>{onActivate();onChange(e.target.value)}} onKeyDown={e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();step(e.key==='ArrowUp'?1:-1)}}}>{choices.map(time=><option key={time} value={time}>{time}</option>)}</select><span className="time-arrows">{[1,-1].map(direction=><button key={direction} type="button" className="time-step" disabled={disabled} aria-label={`${direction>0?'Increase':'Decrease'} ${label} by 15 minutes`} onClick={()=>step(direction)}>{direction>0?'▲':'▼'}</button>)}</span></div>
}
