const fs = require('fs')
let h = fs.readFileSync('mockup.html', 'utf8')
function rep(find, replace) { if (!h.includes(find)) throw new Error('Missing: ' + find.slice(0, 50)); h = h.replace(find, replace) }
rep('.wlabel{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}', '.wlabel{display:flex;align-items:center;justify-content:flex-start;gap:10px;margin-bottom:9px}')
rep('Open to pool</button>', 'Release to pool</button>')
rep('<small>30 Nov–6 Dec</small>', '<small>30 Nov – 6 Dec</small>')
fs.writeFileSync('mockup.html', h)
console.log('patched')
