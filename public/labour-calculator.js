import {calculateLabour,categories,sellingRate} from './labour-math.js'
const titles={consumables:'Consumables',parts:'Parts',labour:'Labour',travel:'Travel',mileage:'Mileage'}
const units={consumables:'Quantity',parts:'Quantity',labour:'Hours',travel:'Hours',mileage:'Kilometres'}
const money=cents=>new Intl.NumberFormat('en-NZ',{style:'currency',currency:'NZD'}).format(cents/100)
const panel=document.getElementById('calculatorPanel'),fields=document.getElementById('quoteFields')
const detailsButton=document.getElementById('quoteDetailsTab'),calculatorButton=document.getElementById('labourTab')
let catalogue=[],rows=[],gst=15,configured=false,busy=false
panel.innerHTML='<div class="calculator-toolbar"><span>Excl GST · Margin % · Hours: 0.25 = 15 min, 1.0 = 1 hr</span><button id="reloadCalculator" type="button">Refresh rates</button></div><div id="calculatorRows"></div><div id="calculatorSummary" aria-live="polite"></div><div class="calculator-transfer"><label>Existing quote item<select id="calculatorTarget" aria-label="Existing quote item"></select></label><button id="transferCalculator" type="button" class="primary" disabled>Transfer final value</button><button id="transferIndividual" type="button" disabled>Transfer individual items</button></div><p class="hint calculator-help">Final value sets the selected item to quantity 1 and keeps its name. Individual items are added to your quote.</p><p id="calculatorStatus" role="status" class="status"></p>'
const status=document.getElementById('calculatorStatus'),summary=document.getElementById('calculatorSummary'),transfer=document.getElementById('transferCalculator')
const individual=document.getElementById('transferIndividual'),target=document.getElementById('calculatorTarget')
const customDialog=document.createElement('dialog')
customDialog.className='calculator-custom-dialog'
customDialog.setAttribute('aria-labelledby','customItemTitle')
customDialog.innerHTML='<form><h2 id="customItemTitle">Custom item</h2><label>Custom item name<input id="customItemName" name="itemName" required maxlength="4000" autocomplete="off" placeholder="Enter an item name"></label><p class="hint">Enter the value, quantity and margin in the calculator row.</p><div class="custom-dialog-actions"><button type="button" id="cancelCustomItem">Cancel</button><button type="submit" class="primary">Use custom item</button></div></form>'
document.body.append(customDialog)
const customName=customDialog.querySelector('input')
let customRow=null,customSelect=null
function openCustom(row,select){customRow=row;customSelect=select;select.value=row.custom?'__custom__':row.itemId;customName.value=row.custom?row.description:'';customName.setCustomValidity('');customDialog.querySelector('h2').textContent='Custom item';customDialog.showModal();customName.focus();customName.select()}
customName.oninput=()=>customName.setCustomValidity('')
customDialog.querySelector('form').onsubmit=e=>{e.preventDefault();const name=customName.value.trim();if(!name){customName.setCustomValidity('Enter a custom item name.');customName.reportValidity();return}Object.assign(customRow,{itemId:'custom-'+customRow.key,description:name,custom:true});customDialog.close();draw()}
document.getElementById('cancelCustomItem').onclick=()=>customDialog.close()
customDialog.addEventListener('close',()=>{customSelect?.focus();customRow=null;customSelect=null})
document.addEventListener('trident-calculator-targets',e=>{const previous=target.value;target.replaceChildren();for(const [index,line] of e.detail.entries()){const option=document.createElement('option');option.value=index;option.textContent=line.description||'Item '+(index+1);target.append(option)}if([...target.options].some(o=>o.value===previous))target.value=previous;recompute()})
function makeRow(item){return {...item,itemId:item.id,description:item.name,qty:item.category==='consumables'?1:0,key:crypto.randomUUID()}}
function activate(calculator){fields.hidden=calculator;panel.hidden=!calculator;document.body.classList.toggle('calculator-active',calculator);detailsButton.setAttribute('aria-selected',String(!calculator));calculatorButton.setAttribute('aria-selected',String(calculator));if(calculator){document.dispatchEvent(new Event('trident-calculator-request-targets'));if(!configured)load()}panel.parentElement.scrollTop=0}
detailsButton.onclick=()=>activate(false)
calculatorButton.onclick=()=>activate(true)
function recompute(){
 try{const result=calculateLabour(rows,gst);summary.replaceChildren();const title=document.createElement('h2');title.textContent='Calculation totals';summary.append(title)
  const dl=document.createElement('dl');dl.className='calculator-totals'
  for(const [label,amount] of [...categories.map(category=>[titles[category],result.groups[category]]),['Total excluding GST',result.subtotal],[`GST (${gst}%)`,result.tax],['Total including GST',result.total]]){const entry=document.createElement('div'),name=document.createElement('dt'),value=document.createElement('dd');name.textContent=label;value.textContent=money(amount);entry.append(name,value);dl.append(entry)}
  summary.append(dl);individual.disabled=busy||!result.lines.length;transfer.disabled=individual.disabled||!target.options.length;status.textContent='';status.classList.remove('calculator-error')
  for(const row of rows){const cell=document.getElementById('calc-amount-'+row.key),rate=document.getElementById('calc-rate-'+row.key);const unitRate=sellingRate(row.cost,row.margin)*100;if(cell)cell.textContent=money(Math.round(Number(row.qty)*unitRate));if(rate)rate.textContent=money(unitRate)}
  return result
 }catch(e){summary.textContent='Complete the calculation to see totals.';transfer.disabled=true;individual.disabled=true;status.textContent=e.message;status.classList.add('calculator-error');return null}
}
function labelInput(row,key,label,type='number'){
 const wrap=document.createElement('label'),input=document.createElement('input');input.type=type;input.value=row[key];input.setAttribute('aria-label',titles[row.category]+' '+label+' '+(rows.filter(r=>r.category===row.category).indexOf(row)+1));input.title=label
 if(type==='number'){input.min='0';input.max=key==='margin'?'99':'1000000';input.step=key==='qty'?(['labour','travel'].includes(row.category)?'0.25':'any'):'0.01';if(key==='qty'&&['labour','travel'].includes(row.category)){input.title='Hours in 0.25 increments · 1.0 = one hour'}}else input.maxLength=4000
 input.oninput=()=>{row[key]=input.value;recompute()};wrap.append(input);return wrap
}
function draw(){
 const host=document.getElementById('calculatorRows');host.innerHTML='<div class="calculator-columns"><span>Item / default rate</span><span>Quantity</span><span>Base value $</span><span>Margin %</span><span>Amount $</span><span></span></div>'
 for(const category of categories){const section=document.createElement('section');section.className='calculator-group';
  for(const row of rows.filter(r=>r.category===category)){const card=document.createElement('div');card.className='calculator-line';const pick=document.createElement('label');const select=document.createElement('select');select.setAttribute('aria-label',titles[category]+' item '+(rows.filter(r=>r.category===category).indexOf(row)+1));const options=catalogue.filter(item=>item.category===category)
   if(!row.custom&&!options.some(item=>item.id===row.itemId))options.push({id:row.itemId,name:row.description+' (saved calculation)'})
   for(const item of options){const option=document.createElement('option');option.value=item.id;option.textContent=item.name;select.append(option)}select.value=row.itemId
   const customOption=document.createElement('option');customOption.value='__custom__';customOption.textContent='Custom';select.append(customOption);select.value=row.custom?'__custom__':row.itemId
   select.onchange=()=>{if(select.value==='__custom__'){openCustom(row,select);return}const item=catalogue.find(item=>item.id===select.value);if(!item)return;Object.assign(row,{itemId:item.id,description:item.name,cost:item.cost,margin:item.margin,custom:false});draw()};pick.append(select);card.append(pick,labelInput(row,'qty',units[category]),labelInput(row,'cost','Base cost'),labelInput(row,'margin','Margin %'))
   const output=document.createElement('output');output.id='calc-amount-'+row.key;card.append(output)
   const remove=document.createElement('button');remove.textContent='×';remove.setAttribute('aria-label','Remove '+titles[category]+' line');remove.type='button';remove.onclick=()=>{rows=rows.filter(r=>r.key!==row.key);draw()};card.append(remove);section.append(card)
  }
  host.append(section)
 }
 const add=document.createElement('select');add.setAttribute('aria-label','Add calculation line');add.innerHTML='<option value="">+ Add another item…</option>';for(const category of categories){const option=document.createElement('option');option.value=category;option.textContent=titles[category];add.append(option)}add.onchange=()=>{const item=catalogue.find(item=>item.category===add.value);if(item){rows.push(makeRow(item));draw()}};host.append(add)
 recompute()
}
async function load(){
 if(busy)return;busy=true;transfer.disabled=true;individual.disabled=true;status.textContent='Loading calculator settings…'
 try{const [itemResponse,quoteResponse]=await Promise.all([fetch('/api/labour-settings'),fetch('/api/quote-settings')]);const items=await itemResponse.json(),quote=await quoteResponse.json();if(!itemResponse.ok||!quoteResponse.ok)throw Error(items.error||quote.error||'Unable to load settings.')
  const previous=catalogue;catalogue=items.items;gst=Number(quote.business.gstPercent)
  if(!configured){rows=categories.map(category=>makeRow(catalogue.find(item=>item.category===category)));configured=true}else for(const row of rows){const old=previous.find(item=>item.id===row.itemId),next=catalogue.find(item=>item.id===row.itemId);if(old&&next){if(Number(row.cost)===Number(old.cost))row.cost=next.cost;if(Number(row.margin)===Number(old.margin))row.margin=next.margin;if(row.description===old.name)row.description=next.name}}
  busy=false;draw()
 }catch(e){busy=false;status.textContent=e.message;status.classList.add('calculator-error');transfer.disabled=true;individual.disabled=true}
}
document.getElementById('reloadCalculator').onclick=load
transfer.onclick=()=>{const result=recompute();if(!result||transfer.disabled)return;document.dispatchEvent(new CustomEvent('trident-calculator-transfer',{detail:{subtotal:result.subtotal,target:Number(target.value),mode:'total',gst}}))}
individual.onclick=()=>{const result=recompute();if(!result||individual.disabled)return;document.dispatchEvent(new CustomEvent('trident-calculator-transfer',{detail:{lines:result.lines,mode:'append',gst}}))}
document.addEventListener('trident-calculator-transferred',()=>activate(false))
document.addEventListener('trident-quote-loaded',()=>{rows=[];configured=false;activate(false)})
window.addEventListener('message',e=>{if(e.source===parent&&e.origin===parent.location.origin&&e.data?.type==='trident-quote-settings-updated'&&configured)load()})
