import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { assertLatestBaseDataTemplateContract, LATEST_BASE_DATA_TEMPLATE_AUTHORITY, LATEST_BASE_DATA_TEMPLATE_VERSION } from '../src/meta/contracts/latestBaseDataTemplateContract.js'
import { foundationCanonicalModules } from '../src/meta/master-data/foundationEntryUnificationRegistry.js'
import { orderProductionBaseDataTemplateAdoption } from '../src/meta/master-data/orderProductionBaseDataTemplateAdoption.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const fail = message => { throw new Error(`[latest-base-data-template-adoption] ${message}`) }
assertLatestBaseDataTemplateContract()
for (const [key, relativePath] of Object.entries(LATEST_BASE_DATA_TEMPLATE_AUTHORITY)) {
  if (String(relativePath).startsWith('src/') && !fs.existsSync(path.join(root, relativePath))) fail(`authority file missing (${key}): ${relativePath}`)
}
const expectedIds = foundationCanonicalModules.map(item => item.moduleId).sort()
const actualIds = orderProductionBaseDataTemplateAdoption.map(item => item.moduleId).sort()
if (JSON.stringify(expectedIds) !== JSON.stringify(actualIds)) fail('adoption scope differs from foundationCanonicalModules')
const allowed = new Set(['ADOPTING', 'ADOPTED', 'ADOPTING_PROTECTED_BASELINE', 'ADOPTING_IMPORT_BACKEND_PENDING', 'ADOPTING_IMPORT_MANUAL_VALIDATION_PENDING', 'ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED', 'ADOPTING_DATA_PROVIDER_BLOCKED', 'DATA_PROVIDER_BLOCKED'])
for (const row of orderProductionBaseDataTemplateAdoption) {
  if (row.templateVersion !== LATEST_BASE_DATA_TEMPLATE_VERSION) fail(`${row.moduleId} has wrong template version`)
  if (!allowed.has(row.adoptionStatus)) fail(`${row.moduleId} has invalid adoption status`)
  if (row.legacyFallbackAllowed !== false) fail(`${row.moduleId} permits a legacy fallback`)
  if (!row.formalModel || !row.api || !row.routePath) fail(`${row.moduleId} lacks DB/API/UI authority evidence`)
}
const wave1Ids = orderProductionBaseDataTemplateAdoption.filter(row => row.wave === 'WAVE1').map(row => row.moduleId).sort()
const expectedWave1Ids = ['capacity', 'customer', 'equipment', 'material', 'operation', 'product-definition', 'supplier', 'work-center', 'workshop']
if (JSON.stringify(wave1Ids) !== JSON.stringify(expectedWave1Ids)) fail(`unexpected Wave 1 scope: ${wave1Ids.join(', ')}`)
if (orderProductionBaseDataTemplateAdoption.filter(row => row.wave === 'WAVE1').some(row => row.adoptionStatus !== 'ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED')) {
  fail('Wave 1 modules must remain ADOPTING_IMPORT_ACTOR_CONTEXT_BLOCKED until user commit/replay validation passes')
}
if (orderProductionBaseDataTemplateAdoption.filter(row => row.wave === 'WAVE1').some(row => row.userManualValidation !== 'PASS')) {
  fail('Every Wave 1 module must retain the explicit user manual PASS')
}
if (orderProductionBaseDataTemplateAdoption.find(row => row.moduleId === 'operation')?.protectedBaseline !== true) {
  fail('Operation must retain its independent protected-baseline marker')
}
const wave1Sources = [
  fs.readFileSync(path.join(root, 'src/meta/pages/EnterpriseMasterDataPage.vue'), 'utf8'),
  fs.readFileSync(path.join(root, 'src/meta/components/ProductionFoundationMaintenance.vue'), 'utf8'),
].join('\n')
for (const marker of ['data-latest-base-data-template', 'PceEnterpriseListTable', 'LatestBaseDataImportToolbarExtension']) {
  if (!wave1Sources.includes(marker)) fail(`Wave 1 runtime marker missing: ${marker}`)
}
console.log(`PASS latest base-data template authority=${LATEST_BASE_DATA_TEMPLATE_VERSION} scope=${actualIds.length}`)
