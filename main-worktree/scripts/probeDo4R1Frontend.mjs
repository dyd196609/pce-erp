// Confirm the actual DO4 component contract: action labels come from server facts.
import { writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
const url = 'http://127.0.0.1:5176/src/meta/pages/WholeHouseOrderPreview.vue'
const response = await fetch(url)
const body = await response.text()
const markers = Object.fromEntries(['save-mapping', 'create-draft', 'sourceAction', 'createSourceDraft', 'preview.actions', 'action.label'].map(marker => [marker, body.includes(marker)]))
const result = { observedAt: new Date().toISOString(), url, status: response.status, markers,
  servedCompiledSha256: createHash('sha256').update(body).digest('hex'),
  correction: 'First probe searched for hard-coded action labels. The original component correctly renders action.label from server preview.actions; lack of hard-coded Chinese action labels is expected, not stale code.' }
writeFileSync('D:/Dev-PCE/Source/frontend/test-results/pce-order-delivery-planning-do4-r1-runtime-20260913/FRONTEND_COMPONENT_PROOF.json', JSON.stringify(result, null, 2) + '\n')
console.log(JSON.stringify(result, null, 2))
if (response.status !== 200 || Object.values(markers).some(value => !value)) process.exitCode = 1
