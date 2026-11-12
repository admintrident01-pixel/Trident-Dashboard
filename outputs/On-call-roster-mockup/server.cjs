const http = require('http')
const fs = require('fs')
const path = require('path')
const root = __dirname
const types = { '.png': 'image/png', '.html': 'text/html; charset=utf-8', '.svg': 'image/svg+xml', '.md': 'text/plain; charset=utf-8' }
http.createServer((req, res) => {
  const urlPath = decodeURIComponent(req.url.split('?')[0])
  const file = path.join(root, urlPath === '/' ? 'oncall-desktop.png' : urlPath)
  if (!file.startsWith(root)) { res.writeHead(403).end(); return }
  fs.readFile(file, (err, data) => {
    if (err) { res.writeHead(404).end('Not found'); return }
    res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream', 'Cache-Control': 'no-store' })
    res.end(data)
  })
}).listen(18811, '127.0.0.1', () => console.log('mockup server on 18811'))
