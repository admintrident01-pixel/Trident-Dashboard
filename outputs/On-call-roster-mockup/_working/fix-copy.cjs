const fs = require('fs')
let s = fs.readFileSync('_working/build-handover.cjs', 'utf8')
if (!s.includes('for Week 46 .')) throw new Error('period anchor missing')
s = s.replace('for Week 46 .', 'for Week 46.')
fs.writeFileSync('_working/build-handover.cjs', s)

let r = fs.readFileSync('README.md', 'utf8')
const oldLine = "- **This week's coverage**: Monday–Sunday strip with today highlighted and weekend backup noted."
if (!r.includes(oldLine)) throw new Error('README anchor missing')
r = r.replace(oldLine, "- **Roster by week**: one technician per week (Monday–Sunday), including the current week, with status and email confirmation.")
const oldDialog = "- `oncall-handover.png` — \"Hand over on-call\" dialog with technician selection, public-pool option and email notice."
r = r.replace(oldDialog, "- `oncall-handover.png` — \"Hand over on-call\" dialog with technician selection, public-pool option and email notice. No reason or free-text note fields.")
fs.writeFileSync('README.md', r)
console.log('fixed')
