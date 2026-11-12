const fs = require('fs')
let h = fs.readFileSync('mockup.html', 'utf8')
function rep(find, replace) { if (!h.includes(find)) throw new Error('Missing: ' + find.slice(0, 70)); h = h.replace(find, replace) }

rep('.now-body{display:flex;gap:16px;align-items:flex-start}', '.now-body{display:flex;gap:16px;align-items:center}')
rep(`      <div class="now-body">
        <div class="avatar a-72">DW</div>
        <div style="min-width:0;flex:1">
          <div class="now-name"><h2>Daniel Whitiora</h2><span class="chip grey">Senior technician</span></div>
          <p class="now-role">Auckland · Covers North Shore, Rodney and Central</p>
          <div class="now-contact">
            <span><svg class="i"><use href="icons/feather-sprite.svg#phone"></use></svg>021 555 0142</span>
            <span><svg class="i"><use href="icons/feather-sprite.svg#mail"></use></svg>daniel@trice.nz</span>
          </div>
        </div>
      </div>`,
`      <div class="now-body">
        <div class="avatar a-72">DW</div>
        <div style="min-width:0;flex:1">
          <div class="now-name"><h2>Daniel Whitiora</h2></div>
        </div>
      </div>`)

rep(`        <div class="fact"><small>Accepted</small><div>Mon 9 Nov, 7:02 am<br>by Daniel Whitiora</div></div>
        <div class="fact"><small>Weekend backup</small><div>Sione Tuilagi<br>021 555 0197</div></div>`,
`        <div class="fact"><small>Accepted</small><div>Mon 9 Nov, 7:02 am</div></div>
        <div class="fact"><small>Weekend backup</small><div>Sione Tuilagi</div></div>`)

const start = h.indexOf('  <section class="card weekcard">')
const end = h.indexOf('  <section class="grid-two">')
if (start < 0 || end < 0 || end <= start) throw new Error('week section anchors missing')
h = h.slice(0, start) + h.slice(end)

rep(`      <h2>Upcoming weeks</h2>`, `      <h2>Roster by week</h2>
      <span class="sub" style="font-size:10.5px;color:#8292a8">One technician per week · Monday to Sunday</span>`)

rep(`      <thead><tr><th>Week</th><th>Dates</th><th>On call</th><th>Backup</th><th>Status</th><th>Notified</th></tr></thead>
      <tbody>
        <tr><td class="week"><b>Week 47</b></td>`,
`      <thead><tr><th>Week</th><th>Dates</th><th>On call</th><th>Backup</th><th>Status</th><th>Notified</th></tr></thead>
      <tbody>
        <tr><td class="week"><b>Week 46</b> <span class="chip green" style="font-size:8px;padding:1px 5px">This week</span></td><td>Mon 9 – Sun 15 Nov</td><td><span class="person"><span class="avatar a-28">DW</span><b>Daniel Whitiora</b></span></td><td>Sione Tuilagi</td><td><span class="chip green">Confirmed</span></td><td><span class="notified"><svg class="i"><use href="icons/feather-sprite.svg#mail"></use></svg>6 people · 9 Nov</span></td></tr>
        <tr><td class="week"><b>Week 47</b></td>`)

fs.writeFileSync('mockup.html', h)
console.log('desktop patched', h.length)
