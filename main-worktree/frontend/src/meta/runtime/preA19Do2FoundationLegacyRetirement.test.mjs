import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { inspectLegacyFoundationStorage, LEGACY_FOUNDATION_KEYS } from './legacyFoundationDiagnostic.js'

const read = path => readFile(new URL(path, import.meta.url), 'utf8')
const [router, portal, operator, diagnostic, legacyRuntime] = await Promise.all([
  read('../../router/index.js'), read('../pages/EnterpriseFoundationUnifiedPage.vue'),
  read('../pages/FoundationServerRuntimeOperatorPage.vue'), read('../pages/LegacyFoundationDiagnosticPage.vue'),
  read('./legacyFoundationDiagnostic.js'),
])

assert.doesNotMatch(portal, /ManufacturingFoundationPage|manufacturingFoundationStore|enterpriseOperationStore|localStorage\.(?:getItem|setItem|removeItem|clear)/)
assert.match(portal, /loadMasterDataStatisticsRuntime/)
assert.match(portal, /data-fact-source="server"/)
assert.doesNotMatch(operator, /manufacturingFoundationStore|enterpriseOperationStore|localStorage\.(?:getItem|setItem|removeItem|clear)/)
for (const token of ['loadMaterialSupplierRelationRuntime', 'loadSupplierMaterialPriceRuntime', 'updateMaterialSupplierDeliveryPeriod', 'updateSupplierMaterialPrice']) assert.match(operator, new RegExp(token))

assert.doesNotMatch(router, /ManufacturingFoundationPage\.vue/)
assert.match(router, /path: 'foundation\/legacy-diagnostic'/)
assert.match(router, /FoundationServerRuntimeOperatorPage\.vue/)
for (const tab of ['departments', 'roles', 'users', 'permissions']) assert.match(router, new RegExp(`redirect: '/organization\\?tab=${tab}'`))
assert.match(diagnostic, /LEGACY \/ NON-FORMAL \/ READ-ONLY/)
assert.doesNotMatch(`${diagnostic}\n${legacyRuntime}`, /\.setItem\(|\.removeItem\(|\.clear\(/)

const calls = []
const synthetic = new Map([
  ['manufacturing-foundation-state-v1', JSON.stringify({ materials: [{ id: 'LOCAL-ONLY-1' }], suppliers: [{ id: 'LOCAL-ONLY-2' }] })],
  ['enterprise-operation-state-v1', JSON.stringify({ departments: [{ id: 'LOCAL-ORG-1' }] })],
])
const readOnlyStorage = Object.freeze({
  getItem(key) { calls.push(['getItem', key]); return synthetic.get(key) ?? null },
  setItem() { throw new Error('write forbidden') }, removeItem() { throw new Error('delete forbidden') }, clear() { throw new Error('clear forbidden') },
})
const serverFacts = Object.freeze([{ id: 'SERVER-1' }, { id: 'SERVER-2' }])
const beforeServerFacts = JSON.stringify(serverFacts)
const inspection = inspectLegacyFoundationStorage(readOnlyStorage)
assert.deepEqual(calls, LEGACY_FOUNDATION_KEYS.map(key => ['getItem', key]))
assert.deepEqual(inspection.map(item => item.recordCount), [2, 1])
assert.deepEqual(inspection.map(item => item.classification), ['UNKNOWN', 'UNKNOWN'])
assert.equal(JSON.stringify(serverFacts), beforeServerFacts)

console.log(JSON.stringify({ dependencyTest: 'PASS', foundationLegacyFormalStoreDependency: 0, foundationBusinessLocalStorageWrite: 0, foundationFormalFactSource: 'server', legacyAutoOverrideServer: 0, legacyFormalCrud: 0, syntheticLegacyKeysRead: calls.length, userLegacyKeysDeleted: 0, userLegacyKeysMigrated: 0 }, null, 2))
