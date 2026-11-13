const fs = require('fs')
let s = fs.readFileSync('_working/build-handover.cjs', 'utf8')
function rep(find, replace) { if (!s.includes(find)) throw new Error('Missing: ' + find.slice(0, 60)); s = s.replace(find, replace) }
rep(`  .fields{display:grid;grid-template-columns:170px 1fr;gap:10px;margin-top:12px}
  .fields label{display:grid;gap:4px;font-size:10px;font-weight:700;color:#526b89}
  .fields select,.fields input{font:inherit;font-size:11.5px;padding:8px 9px;border:1px solid #c9d5e4;border-radius:5px;color:#20334d;background:#fff;min-width:0}
`, '')
rep(`      <div class="fields">
        <label>Reason<select><option>Illness</option><option>Family</option><option>Workload</option><option>Other</option></select></label>
        <label>Note for the team (optional)<input value="Back Monday — thanks Sione"></label>
      </div>
`, '')
rep('and includes your reason.', '.')
rep('<span class="avatar">BC</span><span class="avatar">AS</span>', '<span class="avatar">BC</span>')
fs.writeFileSync('_working/build-handover.cjs', s)
console.log('handover builder patched')
