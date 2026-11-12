const fs = require('fs')
let h = fs.readFileSync('mockup.html', 'utf8')
function rep(find, replace) { if (!h.includes(find)) throw new Error('Missing: ' + find.slice(0, 50)); h = h.replace(find, replace) }
rep(`    .upcoming{overflow-x:auto}
    table{min-width:620px}`, `    .upcoming{overflow-x:auto}
    .upcoming table{min-width:0}
    .upcoming th:nth-child(4),.upcoming td:nth-child(4),.upcoming th:nth-child(6),.upcoming td:nth-child(6){display:none}`)
rep(`<div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#repeat"></use></svg><div><b>Accept, hand over or release</b>All technicians and admins — with who, which week and why.</div></div>
      <div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#users"></use></svg><div><b>A week enters the public pool</b>Every technician, so anyone can grab it.</div></div>
      <div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#clock"></use></svg><div><b>Weekly reminder · Mondays 7:00 am</b>The rostered technician and admins, until the week is accepted.</div></div>`,
`<div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#user-check"></use></svg><div><b>Accepted by the technician</b>The technician and admins, with the week and time accepted.</div></div>
      <div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#repeat"></use></svg><div><b>Handed over or reassigned</b>Outgoing and incoming technicians, plus all admins.</div></div>
      <div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#users"></use></svg><div><b>A week enters the public pool</b>Every technician, so anyone can grab it.</div></div>
      <div class="rule"><svg class="i"><use href="icons/feather-sprite.svg#clock"></use></svg><div><b>Weekly reminder · Mondays 7:00 am</b>The rostered technician and admins, until the week is accepted.</div></div>`)
rep('<span>6 technicians</span>', '<span>5 technicians</span>')
fs.writeFileSync('mockup.html', h)
console.log('patched')
