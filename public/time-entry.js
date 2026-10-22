/* Shared 12-hour entry. Stored values remain HH:mm for existing records and APIs. */
(function(root){
  const pad=value=>String(value).padStart(2,'0');
  function minutes(value){
    const match=/^(\d{2}):(\d{2})$/.exec(String(value||''));
    if(!match)return null;
    const hour=Number(match[1]),minute=Number(match[2]);
    return hour<=24&&minute<60&&(hour<24||minute===0)?hour*60+minute:null;
  }
  function parts(value){
    const total=minutes(value);
    if(total===null)return {hour:'',minute:'',period:'AM',endOfDay:false};
    const hour=Math.floor(total/60)%24;
    return {hour:pad(hour%12||12),minute:pad(total%60),period:hour<12?'AM':'PM',endOfDay:total===1440};
  }
  function fromParts(hour,minute,period){
    if(!/^\d{1,2}$/.test(String(hour))||!/^\d{1,2}$/.test(String(minute)))return null;
    hour=Number(hour);minute=Number(minute);
    if(hour<1||hour>12||minute<0||minute>59||!['AM','PM'].includes(period))return null;
    return pad(hour%12+(period==='PM'?12:0))+':'+pad(minute);
  }
  function normalize(value,{step=900,min='00:00',max,allowEndOfDay=false}={}){
    const total=minutes(value);
    if(total===null)return '';
    const increment=Math.max(1,Number(step)/60||15),lower=minutes(min)??0;
    const upper=Math.min(minutes(max)??(allowEndOfDay?1440:1439),allowEndOfDay?1440:1439);
    const last=Math.floor(upper/increment)*increment,first=Math.ceil(lower/increment)*increment;
    const rounded=Math.max(first,Math.min(last,Math.round(total/increment)*increment));
    return pad(Math.floor(rounded/60))+':'+pad(Math.round(rounded%60));
  }
  function shift(value,direction,options={}){
    const current=minutes(value)??0,increment=Math.max(1,Number(options.step??900)/60||15);
    const next=Math.max(0,Math.min(1440,current+(direction>0?increment:-increment)));
    return normalize(pad(Math.floor(next/60))+':'+pad(Math.round(next%60)),options);
  }
  function enhance(source,initialOptions={}){
    if(source.tridentTimeEntry){source.tridentTimeEntry.update(initialOptions);return source.tridentTimeEntry;}
    let options={...initialOptions},period='AM',destroyed=false;
    const container=document.createElement('span');container.className='trident-time-entry';container.setAttribute('role','group');
    const hour=document.createElement('input'),minute=document.createElement('input');
    [hour,minute].forEach(input=>{input.type='text';input.inputMode='numeric';input.maxLength=2;input.autocomplete='off';input.className='trident-time-digit';input.spellcheck=false;input.pattern='[0-9]{1,2}';});
    hour.classList.add('trident-time-hour');minute.classList.add('trident-time-minute');
    const colon=document.createElement('span');colon.className='trident-time-colon';colon.textContent=':';colon.setAttribute('aria-hidden','true');
    const periods=document.createElement('span');periods.className='trident-time-period';periods.setAttribute('role','group');
    const buttons=['AM','PM'].map(value=>{const button=document.createElement('button');button.type='button';button.textContent=value;button.className='trident-time-period-button';button.addEventListener('click',()=>{if(isDisabled())return;period=value;commit(true);});periods.append(button);return button;});
    const end=document.createElement('label');end.className='trident-time-end';
    const endCheck=document.createElement('input');endCheck.type='checkbox';endCheck.className='trident-time-end-checkbox';
    end.append(endCheck,document.createTextNode('End of day'));
    endCheck.addEventListener('change',()=>write(endCheck.checked?'24:00':fromParts(hour.value,minute.value,period)||'00:00'));
    container.append(hour,colon,minute,periods,end);source.after(container);
    const originalHidden=source.hidden;source.hidden=true;
    const isDisabled=()=>options.disabled??source.disabled;
    const activate=()=>{if(!isDisabled())options.onActivate?.();};
    function setParts(force=false){
      const value=options.value??source.value,display=parts(value);
      period=display.period;
      if(force||document.activeElement!==hour)hour.value=display.hour;
      if(force||document.activeElement!==minute)minute.value=display.minute;
      endCheck.checked=display.endOfDay;
      buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.textContent===period)));
    }
    function validate(){
      const validHour=/^\d{1,2}$/.test(hour.value)&&Number(hour.value)>=1&&Number(hour.value)<=12;
      const validMinute=/^\d{1,2}$/.test(minute.value)&&Number(minute.value)<60;
      hour.setCustomValidity(hour.value&&!validHour?'Enter an hour from 1 to 12.':'');
      minute.setCustomValidity(minute.value&&!validMinute?'Enter minutes from 00 to 59.':'');
      return validHour&&validMinute;
    }
    function write(value){
      const next=normalize(value,options);
      if(!next)return;
      activate();
      const changed=source.value!==next;source.value=next;
      if(options.value!==undefined)options.value=next;
      setParts(true);validate();
      if(changed){
        source.dispatchEvent(new Event('input',{bubbles:true}));
        source.dispatchEvent(new Event('change',{bubbles:true}));
        options.onChange?.(next);
      }
    }
    function commit(force=false){
      if(isDisabled())return;
      if(validate()){
        const value=endCheck.checked?'24:00':fromParts(hour.value,minute.value,period);
        // Keep typed digits intact until the segment is complete or focus leaves it.
        if(force||(hour.value.length===2&&minute.value.length===2))write(value);
      }else if(force&&!hour.value&&!minute.value){
        source.value='';if(options.value!==undefined)options.value='';
        source.dispatchEvent(new Event('change',{bubbles:true}));options.onChange?.('');
      }else if(force){
        setParts(true);validate();
      }
      buttons.forEach(button=>button.setAttribute('aria-pressed',String(button.textContent===period)));
    }
    function step(direction){if(!isDisabled())write(shift(endCheck.checked?'24:00':fromParts(hour.value,minute.value,period)||source.value,direction,options));}
    [hour,minute].forEach((input,index)=>{
      input.addEventListener('focus',()=>{activate();input.select();});
      input.addEventListener('input',()=>{input.value=input.value.replace(/\D/g,'').slice(0,2);endCheck.checked=false;validate();commit();});
      input.addEventListener('blur',()=>commit(true));
      input.addEventListener('keydown',event=>{
        if(event.key==='ArrowUp'||event.key==='ArrowDown'){event.preventDefault();step(event.key==='ArrowUp'?1:-1);input.select();}
        else if(event.key==='Enter'){commit(true);}
        else if(event.key==='Escape'){setParts(true);validate();}
        else if(event.key===':'&&index===0){event.preventDefault();minute.focus();}
        else if(event.key.toLowerCase()==='a'||event.key.toLowerCase()==='p'){event.preventDefault();period=event.key.toLowerCase()==='a'?'AM':'PM';commit(true);}
      });
      input.addEventListener('wheel',event=>{if(isDisabled()||!event.deltaY||!container.contains(document.activeElement))return;event.preventDefault();step(event.deltaY<0?1:-1);},{passive:false});
    });
    function sync(force=false){
      if(destroyed)return;
      const label=options.label||source.getAttribute('aria-label')||'Time';
      const disabled=isDisabled(),required=options.required??source.required;
      container.setAttribute('aria-label',label);container.classList.toggle('is-disabled',disabled);
      hour.setAttribute('aria-label',label+' hour');minute.setAttribute('aria-label',label+' minute');
      hour.placeholder='hh';minute.placeholder='mm';hour.required=required;minute.required=required;
      hour.disabled=disabled;minute.disabled=disabled;buttons.forEach(button=>{button.disabled=disabled;button.setAttribute('aria-label',label+' '+button.textContent);});
      periods.setAttribute('aria-label',label+' AM or PM');
      const allowsEnd=!!options.allowEndOfDay;
      end.hidden=!allowsEnd;endCheck.disabled=disabled;endCheck.setAttribute('aria-label',label+' at end of day');
      container.classList.toggle('has-end-of-day',allowsEnd);
      if(options.id)hour.id=options.id;
      setParts(force);validate();
    }
    const observer=new MutationObserver(()=>sync());observer.observe(source,{attributes:true,attributeFilter:['disabled','required','aria-label']});
    const sourceChange=()=>sync();source.addEventListener('change',sourceChange);
    const controller={sync,update(next={}){options={...options,...next};sync();},destroy(){destroyed=true;observer.disconnect();source.removeEventListener('change',sourceChange);container.remove();source.hidden=originalHidden;delete source.tridentTimeEntry;}};
    source.tridentTimeEntry=controller;sync(true);return controller;
  }
  root.TridentTimeEntry={minutes,parts,fromParts,normalize,shift,enhance,sync:source=>source.tridentTimeEntry?.sync()};
})(globalThis);
