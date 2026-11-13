const fs = require('fs')
let h = fs.readFileSync('mockup-handover.html', 'utf8')
const before = '<span class="avatar">BC</span><span class="avatar">AS</span>'
if (!h.includes(before)) throw new Error('anchor missing')
h = h.replace(before, '<span class="avatar">BC</span>')
fs.writeFileSync('mockup-handover.html', h)
console.log('fixed')
