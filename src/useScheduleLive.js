import {useEffect,useRef,useState} from 'react'

// The socket carries invalidations only. All reads and writes remain authenticated API requests.
export function useScheduleLive(request,active,onChange){
 const callback=useRef(onChange),[status,setStatus]=useState('checking')
 useEffect(()=>{callback.current=onChange},[onChange])
 useEffect(()=>{
  if(!active)return
  let stopped=false,socket,timer,changeTimer,attempt=0,connecting=false
  async function changed(){clearTimeout(changeTimer);if(stopped)return;const result=await callback.current();if(result===undefined&&!stopped)changeTimer=setTimeout(changed,250)}
  function schedule(){if(!stopped&&!document.hidden)timer=setTimeout(connect,Math.min(30000,1000*2**Math.min(attempt++,5)))}
  async function connect(){
   if(stopped||document.hidden||connecting||socket?.readyState===WebSocket.OPEN)return
   connecting=true
   try{
    const result=await request('/api/schedule/live-ticket',{cache:'no-store'})
    if(stopped||document.hidden)return
    if(!result.data.enabled){setStatus('fallback');timer=setTimeout(connect,60000);return}
    const url=new URL('/schedule-live',location.origin);url.protocol=location.protocol==='https:'?'wss:':'ws:'
    socket=new WebSocket(url,['trident-schedule','ticket.'+result.data.ticket])
    socket.onopen=()=>{attempt=0;setStatus('live');changed()}
    socket.onmessage=event=>{try{if(JSON.parse(event.data).type==='schedule-changed')changed()}catch{/* Ignore invalid frames. */}}
    socket.onclose=()=>{if(!stopped){setStatus('fallback');schedule()}}
    socket.onerror=()=>socket?.close()
   }catch{setStatus('fallback');schedule()}
   finally{connecting=false}
  }
  function resume(){clearTimeout(timer);if(document.hidden){socket?.close();setStatus('fallback')}else{callback.current();connect()}}
  connect();window.addEventListener('online',resume);document.addEventListener('visibilitychange',resume)
  return()=>{stopped=true;clearTimeout(timer);clearTimeout(changeTimer);socket?.close();window.removeEventListener('online',resume);document.removeEventListener('visibilitychange',resume)}
 },[request,active])
 return status
}
