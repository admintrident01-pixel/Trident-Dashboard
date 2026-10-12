/* Improvement A: shared pagination for React histories and the quote workspace. */
;(function(root){
 const sizes=[20,50,100]
 function pageWindow(total,page=1,size=20){
  size=sizes.includes(Number(size))?Number(size):20
  total=Math.max(0,Math.floor(Number(total)||0))
  const pages=Math.max(1,Math.ceil(total/size));page=Math.min(pages,Math.max(1,Math.floor(Number(page)||1)))
  const offset=(page-1)*size
  return {total,size,page,pages,offset,first:total?offset+1:0,last:Math.min(total,offset+size)}
 }
 function pageNumbers(page,pages){
  const keys=new Set([1,pages]);for(let n=Math.max(1,page-2);n<=Math.min(pages,page+2);n++)keys.add(n)
  const result=[];let previous=0
  for(const n of [...keys].sort((a,b)=>a-b)){if(previous&&n-previous>1)result.push(null);result.push(n);previous=n}
  return result
 }
 function rangeLabel(range,label){if(!range.total)return '0 '+label;const shown=range.first===range.last?String(range.first):`${range.first}–${range.last}`;return `${shown} of ${range.total} ${range.total===1?label.replace(/s$/,''):label}`}
 function orderedPage(items,compare,page,size){const all=compare?[...items].sort(compare):items;const range=pageWindow(all.length,page,size);return {...range,rows:all.slice(range.offset,range.offset+range.size)}}
 function renderControls(container,{range,label='records',onPage,onSize}){
  container.replaceChildren();container.className='history-pagination'
  const selectLabel=document.createElement('label');selectLabel.className='pagination-size';selectLabel.append('Rows per page ')
  const select=document.createElement('select');select.setAttribute('aria-label',label+' rows per page')
  for(const size of sizes){const option=document.createElement('option');option.value=size;option.textContent=size;select.append(option)}
  select.value=range.size;select.onchange=()=>onSize(Number(select.value));selectLabel.append(select)
  const count=document.createElement('span');count.className='pagination-count';count.setAttribute('role','status');count.setAttribute('aria-live','polite');count.textContent=rangeLabel(range,label)
  const nav=document.createElement('nav');nav.className='pagination-pages';nav.setAttribute('aria-label',label+' pages')
  function button(text,page,disabled,current=false){const b=document.createElement('button');b.type='button';b.textContent=text;b.disabled=disabled;if(current)b.setAttribute('aria-current','page');b.setAttribute('aria-label',/^\d+$/.test(String(text))?`Page ${page}`:text+' page');b.onclick=()=>onPage(page);nav.append(b)}
  button('Previous',range.page-1,range.page===1)
  for(const page of pageNumbers(range.page,range.pages)){if(page===null){const dots=document.createElement('span');dots.textContent='…';dots.setAttribute('aria-hidden','true');nav.append(dots)}else button(page,page,false,page===range.page)}
  button('Next',range.page+1,range.page===range.pages)
  container.append(selectLabel,count,nav)
 }
 root.TridentHistoryPagination=Object.freeze({sizes,pageWindow,pageNumbers,rangeLabel,orderedPage,renderControls})
})(globalThis)
