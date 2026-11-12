const fs = require('fs')
let html = fs.readFileSync('mockup.html', 'utf8')
const sprite = fs.readFileSync('icons/feather-sprite.svg', 'utf8')
const inner = sprite.replace(/^<svg[^>]*>/, '').replace(/<\/svg>\s*$/, '')
const embed = '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">' + inner + '</svg>'
html = html.replace('</body>', embed + '</body>')
html = html.split('icons/feather-sprite.svg#').join('#')
fs.writeFileSync('mockup-standalone.html', html)
console.log('written', html.length)
