/* Shared quarter-hour stepping for the original form and admin corrections. */
(function(root){
  function step(value,direction){
    const match=/^(\d{2}):(\d{2})$/.exec(value);
    const minutes=match?Number(match[1])*60+Number(match[2]):0;
    const next=Math.max(0,Math.min(1425,Math.round(minutes/15)*15+(direction>0?15:-15)));
    return String(Math.floor(next/60)).padStart(2,'0')+':'+String(next%60).padStart(2,'0');
  }
  root.TridentTimeControls={step};
})(globalThis);
