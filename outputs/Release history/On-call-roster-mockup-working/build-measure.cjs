const fs = require('fs')
let h = fs.readFileSync('mockup-standalone.html', 'utf8')
const script = `<script>
window.addEventListener('load', () => {
  const w = window.innerWidth
  const bad = []
  document.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect()
    if (r.right > w + 1 || r.width > w + 1) bad.push(el.tagName + '.' + (el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className) + ' w=' + Math.round(r.width) + ' right=' + Math.round(r.right))
  })
  const out = document.createElement('pre')
  out.id = 'overflow-report'
  out.textContent = 'VIEWPORT=' + w + ' SCROLL=' + document.documentElement.scrollWidth + ' BODYSCROLL=' + document.body.scrollWidth + '\\n' + bad.slice(0, 40).join('\\n')
  document.body.appendChild(out)
})
</script>`
h = h.replace('</body>', script + '</body>')
fs.writeFileSync('measure.html', h)
console.log('ok')
