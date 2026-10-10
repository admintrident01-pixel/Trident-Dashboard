const paper=document.getElementById('quote')
paper.setAttribute('role','button')
paper.setAttribute('tabindex','0')
paper.setAttribute('aria-label','Open enlarged quote preview')
paper.setAttribute('aria-haspopup','dialog')
const dialog=document.createElement('dialog')
dialog.id='enlargedQuotePreview'
dialog.setAttribute('aria-labelledby','enlargedPreviewTitle')
dialog.innerHTML='<div class="enlarged-preview-toolbar"><strong id="enlargedPreviewTitle">Quote preview</strong><button type="button" id="previewFitPage">Fit page</button><button type="button" id="previewFitWidth">Fit width</button><button type="button" id="closeQuotePreview" aria-label="Close quote preview">Close ×</button></div><div class="enlarged-preview-content"></div>'
document.body.append(dialog)
const content=dialog.querySelector('.enlarged-preview-content')
let fitPage=false
function fit(){
 if(!dialog.open||!content.firstElementChild)return
 const copy=content.firstElementChild
 copy.style.zoom='1'
 const width=copy.offsetWidth,height=copy.offsetHeight
 const widthScale=(content.clientWidth-32)/width
 copy.style.zoom=String(Math.max(.1,fitPage?Math.min(widthScale,(content.clientHeight-32)/height):widthScale))
}
function open(){
 const copy=paper.cloneNode(true)
 for(const element of [copy,...copy.querySelectorAll('[id]')])element.removeAttribute('id')
 for(const attribute of ['role','tabindex','aria-label','aria-haspopup'])copy.removeAttribute(attribute)
 copy.style.zoom='1'
 content.replaceChildren(copy)
 fitPage=false
 dialog.showModal()
 fit()
 content.scrollTop=0
 document.getElementById('closeQuotePreview').focus()
}
paper.addEventListener('click',open)
paper.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();open()}})
document.getElementById('closeQuotePreview').onclick=()=>dialog.close()
document.getElementById('previewFitPage').onclick=()=>{fitPage=true;fit();content.scrollTop=0}
document.getElementById('previewFitWidth').onclick=()=>{fitPage=false;fit();content.scrollTop=0}
dialog.addEventListener('close',()=>paper.focus())
window.addEventListener('resize',fit)
