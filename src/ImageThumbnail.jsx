import Icon from './Icon'
import {useEffect,useRef,useState} from 'react'
const services=new WeakMap()
const isImage=item=>item.kind==='file'&&/\.(png|jpe?g|gif|webp|bmp|avif)$/i.test(item.name)
export default function ImageThumbnail({item,request,enabled=true}){
 const host=useRef(null),[visible,setVisible]=useState(false),[preview,setPreview]=useState(null)
 useEffect(()=>{if(!enabled||!isImage(item))return;const observer=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)){setVisible(true);observer.disconnect()}},{rootMargin:'100px'});observer.observe(host.current);return()=>observer.disconnect()},[enabled,item])
 useEffect(()=>{if(!visible||!enabled||!isImage(item))return;let live=true,url=''
  thumbnail(item,request).then(blob=>{if(live){url=URL.createObjectURL(blob);setPreview({id:item.id,version:item.version,url})}}).catch(()=>{/* Keep the file icon if the image cannot be decoded. */})
  return()=>{live=false;if(url)URL.revokeObjectURL(url)}
 },[visible,enabled,item,request])
 const url=enabled&&preview?.id===item.id&&preview.version===item.version?preview.url:''
 return <span ref={host} className="office-file-icon" aria-hidden="true">{url?<img src={url} alt="" draggable={false}/>:<Icon name={item.kind==='folder'?'folder':isImage(item)?'image':/\.(xlsx?|csv)$/i.test(item.name)?'grid':/\.(mp4|mov|webm)$/i.test(item.name)?'film':/\.(mp3|wav|ogg)$/i.test(item.name)?'music':'file-text'} size={24}/>}</span>
}
function thumbnail(item,request){
 let service=services.get(request)
 if(!service){service={cache:new Map(),pending:new Map(),queue:[],active:0};services.set(request,service)}
 const key=item.id+':'+item.version
 if(service.cache.has(key))return Promise.resolve(service.cache.get(key))
 if(service.pending.has(key))return service.pending.get(key)
 const promise=new Promise((resolve,reject)=>{service.queue.push(async()=>{try{
  const {data}=await request('/api/office-files/content?id='+encodeURIComponent(item.id))
  const original=new Blob([Uint8Array.from(atob(data.content),c=>c.charCodeAt(0))],{type:data.mime}),bitmap=await createImageBitmap(original)
  try{const scale=Math.min(1,320/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement('canvas');canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height)
   const blob=await new Promise(done=>canvas.toBlob(done,'image/webp',.82));if(!blob)throw Error('Thumbnail unavailable')
   service.cache.set(key,blob);while(service.cache.size>48)service.cache.delete(service.cache.keys().next().value);resolve(blob)
  }finally{bitmap.close()}
 }catch(error){reject(error)}finally{service.pending.delete(key);service.active--;run(service)}});run(service)})
 service.pending.set(key,promise);return promise
}
function run(service){while(service.active<2&&service.queue.length){service.active++;service.queue.shift()()}}
