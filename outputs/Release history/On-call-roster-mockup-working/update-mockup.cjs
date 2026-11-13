const fs = require('fs')
let h = fs.readFileSync('mockup.html', 'utf8')
function rep(find, replace) {
  if (!h.includes(find)) throw new Error('Missing anchor: ' + find.slice(0, 70))
  h = h.replace(find, replace)
}

rep("  .day-today-tag{font-size:8px;font-weight:700;background:#e78932;color:#fff;border-radius:3px;padding:1px 4px;letter-spacing:.4px}",
`  .mini-steps{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin:12px 0 14px;border:1px solid #e6edf5;border-radius:7px;overflow:hidden}
  .mini-step{padding:8px 9px;border-right:1px solid #edf1f7;background:#fbfcfe}
  .mini-step:last-child{border-right:0}
  .mini-step b{display:block;font-size:10px;color:#526b89;font-weight:700}
  .mini-step small{display:block;font-size:9.5px;color:#8a99ad;margin-top:2px;line-height:1.4}
  .mini-step .pip{display:inline-grid;place-items:center;width:14px;height:14px;border-radius:50%;background:#e8eef7;color:#526b89;font-size:8px;font-weight:700;margin-bottom:4px}
  .mini-step.done .pip{background:#e2f1e8;color:#2a6b4a}`)

rep("  .pool .btn{flex:none}",
`  .pool .btn{flex:none}
  .pool-note{margin:12px 18px 6px;padding-top:11px;border-top:1px solid #edf1f7;display:flex;gap:8px;flex-wrap:wrap}
  .pool-note .step{display:flex;align-items:flex-start;gap:6px;flex:1;min-width:150px;font-size:10px;line-height:1.45;color:#7a8aa0}
  .pool-note .step b{display:block;color:#526b89;font-size:10px}
  .pool-note .n{width:16px;height:16px;border-radius:50%;background:#eef3fa;color:#4a6c9b;font-size:9px;font-weight:700;display:grid;place-items:center;flex:none;margin-top:1px}`)

rep("If not accepted by <b>Fri 20 Nov, 5 pm</b>", "If not accepted by <b>Sun 15 Nov, 5 pm</b>")

rep(`        <span>Reminder email sent Mon 9 Nov. If not accepted by <b>Sun 15 Nov, 5 pm</b>, the week moves to the public pool.</span>
      </div>
      <div class="next-foot">`,
`        <span>Reminder email sent Mon 9 Nov. If not accepted by <b>Sun 15 Nov, 5 pm</b>, the week moves to the public pool.</span>
      </div>
      <div class="mini-steps">
        <div class="mini-step done"><span class="pip">✓</span><b>Reminder sent</b><small>Mon 9 Nov, 7:00 am</small></div>
        <div class="mini-step"><span class="pip">2</span><b>Accept by</b><small>Sun 15 Nov, 5:00 pm</small></div>
        <div class="mini-step"><span class="pip">3</span><b>Starts</b><small>Mon 16 Nov, 12:00 am</small></div>
      </div>
      <div class="next-foot">`)

rep(`<span class="day-name">Fri <span class="day-today-tag">TODAY</span></span>`, '<span class="day-name">Fri</span>')

rep(`        <button class="btn primary">Grab this week</button>
      </div>
    </div>

    <div class="card order">`,
`        <button class="btn primary">Grab this week</button>
      </div>
      <div class="pool-note">
        <div class="step"><span class="n">1</span><span><b>Everyone is emailed</b>All technicians get the open-week alert.</span></div>
        <div class="step"><span class="n">2</span><span><b>First to accept wins</b>The slot locks as soon as it is grabbed.</span></div>
        <div class="step"><span class="n">3</span><span><b>Team is updated</b>Admin and technicians get a confirmation.</span></div>
      </div>
    </div>

    <div class="card order">`)

fs.writeFileSync('mockup.html', h)
console.log('updated', h.length)
