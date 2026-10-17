import {useEffect,useRef,useState} from 'react'

export default function WordPreview({content,name}){
 const host=useRef(null),[document,setDocument]=useState(null),[width,setWidth]=useState(600),[zoom,setZoom]=useState('fit')
 useEffect(()=>{const observer=new ResizeObserver(entries=>setWidth(entries[0].contentRect.width));observer.observe(host.current);return()=>observer.disconnect()},[])
 useEffect(()=>{let live=true
  import('docx-preview').then(async({renderAsync})=>{
   const body=window.document.createElement('div'),styles=window.document.createElement('div')
   await renderAsync(Uint8Array.from(atob(content),c=>c.charCodeAt(0)),body,styles,{inWrapper:true,useBase64URL:true,renderAltChunks:false,ignoreLastRenderedPageBreak:true,renderHeaders:true,renderFooters:true,renderFootnotes:true,renderEndnotes:true})
   body.querySelectorAll('a').forEach(a=>{a.removeAttribute('href');a.removeAttribute('target')})
   const page=body.querySelector('section.docx'),pageWidth=page?.style.width||'612pt'
   const points=parseFloat(pageWidth),pixels=pageWidth.endsWith('pt')?points*4/3:points
   if(live)setDocument({html:styles.innerHTML+body.innerHTML,width:pixels||816})
  }).catch(()=>{if(live)setDocument({error:true})})
  return()=>{live=false}
 },[content])
 const scale=zoom==='fit'?Math.min(1,Math.max(.1,(width-16)/(document?.width||816))):zoom
 const html=document&&!document.error?`<!doctype html><html><head><meta charset="UTF-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; font-src data:; style-src 'unsafe-inline';"><style>html,body{margin:0;background:#e8edf3}body{font-family:Arial,sans-serif}.docx-wrapper{padding:6px!important;background:transparent!important}.docx-wrapper>section.docx{zoom:${scale};margin:0 auto 16px!important;box-shadow:0 1px 5px #24344c30!important}*{box-sizing:border-box}</style></head><body>${document.html}</body></html>`:''
 return <div className="office-word" ref={host}><div className="office-word-tools"><span>Word preview</span><label>Zoom <select aria-label="Document zoom" value={zoom} onChange={e=>setZoom(e.target.value==='fit'?'fit':Number(e.target.value))}><option value="fit">Fit width</option>{[.5,.75,1,1.25,1.5,2].map(n=><option key={n} value={n}>{n*100}%</option>)}</select></label></div>{!document?<p className="office-empty" role="status">Opening Word document…</p>:document.error?<p className="office-error" role="alert">This Word document could not be previewed. Download the original to open it in Word.</p>:<iframe title={'Word preview: '+name} sandbox="" srcDoc={html}/>}</div>
}
