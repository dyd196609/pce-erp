import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '../../..')
const page = readFileSync(resolve(root, 'src/meta/pages/ManufacturingStructureWave2Page.vue'), 'utf8')
const api = readFileSync(resolve(root, 'src/api/pde.js'), 'utf8')
const router = readFileSync(resolve(root, 'src/router/index.js'), 'utf8')
const nameRegistry = readFileSync(resolve(root, 'src/meta/governance/businessNameRegistry.js'), 'utf8')
const acceptanceRegistry = readFileSync(resolve(root, 'src/meta/runtime/pcePageAcceptanceRegistry.js'), 'utf8')

assert.match(page, /data-fact-source="server"/)
assert.match(page, /正式写入（未授权）/)
assert.match(page, /button type="button" disabled/)
assert.match(page, /facts\.recordCounts/)
assert.match(page, /facts\.canonicalModels/)
assert.match(page, /migration\.applyStatus/)
assert.match(page, /migration\.schemaAvailability/)
assert.match(page, /migration\.authorization/)
assert.doesNotMatch(page, /auth\.productionMigration/)
assert.doesNotMatch(page, /localStorage\./)
assert.doesNotMatch(page, /mockData|CabinetBOM|DoorBOM|WallPanelBOM/)
assert.match(api, /wave2ManufacturingFoundation/)
assert.match(api, /\/api\/pde\/wave2-manufacturing-foundation\//)
assert.match(router, /pde\/wave2-manufacturing-foundation/)
assert.match(router, /ManufacturingStructureWave2Page\.vue/)
assert.match(nameRegistry, /ManufacturingStructureWave2.*manufacturing-structure-wave2.*制造结构与工艺基础验收.*pce-foundation-wave2/)
assert.match(acceptanceRegistry, /pce-foundation-wave2.*制造结构与工艺基础验收.*wave2-manufacturing-foundation/)

console.log('manufacturingStructureWave2.test: PASS')
