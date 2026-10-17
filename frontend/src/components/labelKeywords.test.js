import { test } from 'node:test'
import assert from 'node:assert/strict'
import { labelKeywords, splitHighlight } from './labelKeywords.js'

test('label terms include variants and deduplicate casing and spacing', () => {
  assert.deepEqual(labelKeywords('HIGH SLIT, high slit; deep V neckline, S-curve, curvy', 'is_xx'),
    ['high slit', 'deep v neckline', 's-curve', 'curvy'])
  assert.deepEqual(labelKeywords('boob boobs nipple nipples exposed breasts', 'is_xxx'),
    ['boob', 'boobs', 'nipple', 'nipples', 'exposed breasts'])
  assert.deepEqual(labelKeywords('booby trap and nippleless dress', 'is_xxx'), [])
  assert.deepEqual(labelKeywords('écurvy curvyé _curvy curves2', 'is_xx'), [])
})

test('highlight preserves original text and matches repeated whole terms', () => {
  const text = 'Curvy, CURVY; curvyness; high\nslit; <script>curvy</script>'
  const parts = splitHighlight(text, 'curvy')
  assert.deepEqual(parts.filter((_, i) => i % 2), ['Curvy', 'CURVY', 'curvy'])
  assert.equal(parts.join(''), text)
  assert.deepEqual(splitHighlight(text, 'high slit').filter((_, i) => i % 2), ['high\nslit'])
  assert.deepEqual(splitHighlight('écurvy curvyé', 'curvy'), ['écurvy curvyé'])
  assert.deepEqual(splitHighlight('a+b aab', 'a+b'), ['', 'a+b', ' aab'])
  assert.deepEqual(splitHighlight(text, ''), [text])
})
