const fs = require('fs')
const h = fs.readFileSync('mockup.html', 'utf8')
const sprite = fs.readFileSync('icons/feather-sprite.svg', 'utf8')
const inner = sprite.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')

const css = `
  .overlay{position:fixed;inset:0;background:#101f338c;z-index:60;display:flex;align-items:flex-start;justify-content:center;padding:66px 16px}
  .dialog{width:440px;max-width:100%;background:#fff;border-radius:12px;box-shadow:0 28px 70px #08182c55;overflow:hidden}
  .dhead{display:flex;align-items:flex-start;gap:12px;padding:18px 20px 13px;border-bottom:1px solid #eef2f7}
  .dhead h2{margin:0;font-size:19px;color:#17345f}
  .dhead p{margin:4px 0 0;font-size:11px;color:#8a99ad}
  .xbtn{margin-left:auto;border:0;background:#f2f5fa;color:#5c7089;width:26px;height:26px;border-radius:5px;display:grid;place-items:center;flex:none}
  .dbody{padding:14px 20px 16px}
  .dlabel{font-size:9px;font-weight:700;letter-spacing:.9px;text-transform:uppercase;color:#8a99ad;margin-bottom:6px}
  .opts{border:1px solid #e2e9f2;border-radius:7px;overflow:hidden}
  .opt{display:flex;align-items:center;gap:9px;padding:10px 12px;border-top:1px solid #eef2f7;background:#fff;cursor:pointer}
  .opt:first-child{border-top:0}
  .opt.sel{background:#f3f7fd;box-shadow:inset 3px 0 0 #17345f}
  .opt.off{opacity:.5}
  .radio{width:14px;height:14px;border:1.5px solid #b9c6d8;border-radius:50%;flex:none;display:grid;place-items:center;background:#fff}
  .opt.sel .radio{border-color:#17345f}
  .opt.sel .radio:after{content:"";width:6px;height:6px;border-radius:50%;background:#17345f}
  .oname{font-size:12.5px;color:#20334d;font-weight:400}
  .tag{margin-left:auto;font-size:9px;color:#93a2b5}
  .pool-opt{display:flex;align-items:center;gap:9px;padding:10px 12px;border:1px solid #e2e9f2;border-radius:7px;margin-top:8px;background:#fbfcfe}
  .pool-icon{width:26px;height:26px;border-radius:50%;background:#eef3fa;color:#6b83a4;display:grid;place-items:center;flex:none}
  .pool-icon .i{width:12px;height:12px}
  .oname small{display:block;font-size:9.5px;color:#93a2b5;margin-top:1px}
  .dmail{display:flex;align-items:center;gap:6px;margin-top:12px;font-size:10px;color:#8a99ad}
  .dmail .i{width:12px;height:12px;color:#9aabc0}
  .dfoot{display:flex;justify-content:flex-end;gap:7px;padding:11px 20px;border-top:1px solid #eef2f7;background:#fbfcfe}
`
const modal = `
<div class="overlay">
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="h-title">
    <div class="dhead">
      <div><h2 id="h-title">Hand over Week 46</h2><p>Daniel Whitiora · Mon 9 – Sun 15 Nov</p></div>
      <button class="xbtn" aria-label="Close"><svg class="i" style="width:12px;height:12px"><use href="#x"></use></svg></button>
    </div>
    <div class="dbody">
      <div class="dlabel">Choose a technician</div>
      <div class="opts">
        <div class="opt"><span class="radio"></span><span class="oname">Mereana Kingi</span></div>
        <div class="opt sel"><span class="radio"></span><span class="oname">Sione Tuilagi</span></div>
        <div class="opt"><span class="radio"></span><span class="oname">Aroha Patel</span></div>
        <div class="opt off"><span class="radio"></span><span class="oname">Ben Carter</span><span class="tag">Away</span></div>
      </div>
      <div class="pool-opt">
        <span class="radio"></span><span class="pool-icon"><svg class="i"><use href="#users"></use></svg></span>
        <span class="oname">Open to everyone<small>Any technician can grab this week</small></span>
      </div>
      <div class="dmail"><svg class="i"><use href="#mail"></use></svg>All technicians and admins will be emailed.</div>
    </div>
    <div class="dfoot"><button class="btn">Cancel</button><button class="btn primary">Confirm</button></div>
  </div>
</div>
`
let out = h.replace('</head>', '<style>' + css + '</style></head>').replace('</body>', modal + '</body>')
out = out.replace('</body>', '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">' + inner + '</svg></body>')
out = out.split('icons/feather-sprite.svg#').join('#')
fs.writeFileSync('mockup-handover.html', out)
console.log('handover written', out.length)
