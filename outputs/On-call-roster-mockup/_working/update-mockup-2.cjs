const fs = require('fs')
let h = fs.readFileSync('mockup.html', 'utf8')
function rep(find, replace) {
  if (!h.includes(find)) throw new Error('Missing anchor: ' + find.slice(0, 60))
  h = h.replace(find, replace)
}
rep("  .pool{padding-bottom:8px}", "  .pool{padding-bottom:8px;display:flex;flex-direction:column}")
rep("  .pool-note{margin:12px 18px 6px;", "  .pool-note{margin:12px 18px 6px;margin-top:auto;")
rep('<span class="chip amber count">2 open weeks</span>', '<span class="chip amber count">3 open weeks</span>')
rep(`      <div class="pool-note">`,
`      <div class="pool-row">
        <div class="pool-week">
          <b>Week 51</b>
          <small>Mon 14 – Sun 20 December · added by Adele (Admin), 9 Nov</small>
        </div>
        <button class="btn primary">Grab this week</button>
      </div>
      <div class="pool-note">`)
fs.writeFileSync('mockup.html', h)
console.log('ok', h.length)
