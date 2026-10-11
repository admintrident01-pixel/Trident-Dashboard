import assert from 'node:assert/strict'
import {compareValues} from '../src/tableSort.js'
assert.deepEqual(['Rick','allan','Bala'].sort(compareValues),['allan','Bala','Rick'])
assert.deepEqual([10,2,8.5,-1].sort(compareValues),[-1,2,8.5,10])
assert.deepEqual(['2027-02-01','2026-12-31'].sort(compareValues),['2026-12-31','2027-02-01'])
assert.deepEqual(['Tech 10','Tech 2'].sort(compareValues),['Tech 2','Tech 10'])
console.log('Alphabetical, numeric and date sorting passed.')
