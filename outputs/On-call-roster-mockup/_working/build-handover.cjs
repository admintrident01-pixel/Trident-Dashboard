const fs = require('fs')
let h = fs.readFileSync('mockup.html', 'utf8')
const sprite = fs.readFileSync('icons/feather-sprite.svg', 'utf8')
const inner = sprite.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')

const css = `
  .overlay{position:fixed;inset:0;background:#101f3388;z-index:60;display:flex;align-items:flex-start;justify-content:center;padding:64px 18px;overflow:hidden}
  .dialog{width:600px;max-width:100%;background:#fff;border-radius:12px;box-shadow:0 30px 80px #08182c55;overflow:hidden}
  .dialog-head{display:flex;align-items:flex-start;gap:12px;padding:18px 20px 14px;border-bottom:1px solid #edf1f7}
  .dialog-head .eyebrow{margin-bottom:5px;font-size:9px}
  .dialog-head h2{margin:0;font-size:21px;color:#17345f}
  .dialog-head p{margin:5px 0 0;font-size:11.5px;color:#7a8aa0}
  .icon-btn{margin-left:auto;border:0;background:#f2f5fa;color:#526b89;width:28px;height:28px;border-radius:6px;display:grid;place-items:center;flex:none}
  .dialog-tabs{display:grid;grid-template-columns:1fr 1fr;gap:5px;padding:12px 20px 0}
  .dialog-tabs button{border:1px solid #d9e3ef;background:#f7f9fc;color:#526b89;border-radius:6px;padding:8px 10px;font-size:11px;font-weight:700}
  .dialog-tabs button.active{background:#17345f;border-color:#17345f;color:#fff}
  .dialog-body{padding:14px 20px 4px}
  .field-label{font-size:10px;font-weight:700;letter-spacing:.9px;color:#8292a8;text-transform:uppercase;margin:0 0 7px}
  .tech-options{border:1px solid #e2eaf4;border-radius:8px;overflow:hidden}
  .tech-opt{display:flex;align-items:center;gap:9px;padding:9px 11px;border-top:1px solid #eef2f8;cursor:pointer;background:#fff}
  .tech-opt:first-child{border-top:0}
  .tech-opt.sel{background:#f3f7fd;box-shadow:inset 3px 0 0 #17345f}
  .tech-opt.off{opacity:.55}
  .radio{width:15px;height:15px;border:1.5px solid #b7c6d9;border-radius:50%;flex:none;display:grid;place-items:center;background:#fff}
  .tech-opt.sel .radio{border-color:#17345f}
  .tech-opt.sel .radio:after{content:"";width:7px;height:7px;border-radius:50%;background:#17345f}
  .tech-opt .who{flex:1;min-width:0}
  .tech-opt .who b{display:block;font-size:12px;color:#17345f}
  .tech-opt .who small{display:block;font-size:10px;color:#8292a8;margin-top:1px}
  .tech-opt .tag{font-size:9px;font-weight:700;color:#526b89;background:#eef2f8;border-radius:3px;padding:2px 6px;white-space:nowrap}
  .tech-opt .tag.warn{background:#fff4e2;color:#8a5a12}
  .callout{display:flex;gap:9px;align-items:flex-start;background:#f0f6f2;border:1px solid #cfe4d8;border-radius:7px;padding:9px 11px;margin:13px 0 4px}
  .callout .i{color:#2f6f50;margin-top:1px}
  .callout b{display:block;font-size:11px;color:#245b41}
  .callout span{display:block;font-size:10.5px;color:#4d6f5e;line-height:1.5;margin-top:2px}
  .recipients{display:flex;align-items:center;gap:3px;margin-top:6px}
  .recipients .avatar{width:18px;height:18px;font-size:7px;border:1.5px solid #fff;margin-left:-4px}
  .recipients .avatar:first-child{margin-left:0}
  .recipients em{font-size:9.5px;color:#5d7d6c;font-style:normal;margin-left:4px}
  .dialog-foot{display:flex;align-items:center;gap:8px;padding:12px 20px;border-top:1px solid #edf1f7;background:#fbfcfe}
  .dialog-foot .hint{flex:1;font-size:10px;color:#8a99ad}
`
const modal = `
<div class="overlay">
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="handover-title">
    <div class="dialog-head">
      <div>
        <div class="eyebrow">On-call roster · Week 46</div>
        <h2 id="handover-title">Hand over on-call</h2>
        <p>Daniel Whitiora · Mon 9 – Sun 15 November</p>
      </div>
      <button class="icon-btn" aria-label="Close"><svg class="i" style="width:13px;height:13px"><use href="#x"></use></svg></button>
    </div>
    <div class="dialog-tabs">
      <button class="active">Assign to a technician</button>
      <button>Release to public pool</button>
    </div>
    <div class="dialog-body">
      <div class="field-label">Choose a technician</div>
      <div class="tech-options">
        <div class="tech-opt">
          <span class="radio"></span><span class="avatar a-34">MK</span>
          <div class="who"><b>Mereana Kingi</b><small>Next in order · already covers Week 47</small></div>
          <span class="tag warn">2 weeks in a row</span>
        </div>
        <div class="tech-opt sel">
          <span class="radio"></span><span class="avatar a-34">ST</span>
          <div class="who"><b>Sione Tuilagi</b><small>Available · 021 555 0197 · Auckland</small></div>
          <span class="tag">Next available</span>
        </div>
        <div class="tech-opt">
          <span class="radio"></span><span class="avatar a-34">AP</span>
          <div class="who"><b>Aroha Patel</b><small>Available · last on call 19–25 Oct</small></div>
        </div>
        <div class="tech-opt off">
          <span class="radio"></span><span class="avatar a-34">BC</span>
          <div class="who"><b>Ben Carter</b><small>On leave · returns Mon 30 Nov</small></div>
          <span class="tag">Unavailable</span>
        </div>
      </div>
      <div class="callout">
        <svg class="i"><use href="#mail"></use></svg>
        <div>
          <b>6 people will be emailed when you confirm</b>
          <span>All technicians and admins. The email names Sione as the new on-call technician for Week 46.</span>
          <div class="recipients">
            <span class="avatar">DW</span><span class="avatar">MK</span><span class="avatar">ST</span><span class="avatar">AP</span><span class="avatar">BC</span>
            <em>+ Adele (admin)</em>
          </div>
        </div>
      </div>
    </div>
    <div class="dialog-foot">
      <span class="hint">Daniel will be removed from Week 46 and notified.</span>
      <button class="btn">Cancel</button>
      <button class="btn primary">Confirm handover</button>
    </div>
  </div>
</div>
`
let out = h.replace('</head>', '<style>' + css + '</style></head>').replace('</body>', modal + '</body>')
out = out.replace('</body>', '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">' + inner + '</svg></body>')
out = out.split('icons/feather-sprite.svg#').join('#')
fs.writeFileSync('mockup-handover.html', out)
console.log('written', out.length)
