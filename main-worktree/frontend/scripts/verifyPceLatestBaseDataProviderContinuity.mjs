import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { orderProductionBaseDataTemplateAdoption } from '../src/meta/master-data/orderProductionBaseDataTemplateAdoption.js'
import { LATEST_BASE_DATA_PROVIDER_STATES } from '../src/meta/runtime/latestBaseDataProviderState.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const projectRoot = path.resolve(root, '..')
const fail = message => { throw new Error(`[latest-base-data-provider-continuity] ${message}`) }
const read = relativePath => fs.readFileSync(path.join(root, relativePath), 'utf8')

const requiredStates = [
  'LOADING', 'LOADED_EMPTY', 'LOADED_WITH_DATA', 'AUTH_FAILED',
  'SERVER_CONTEXT_UNAVAILABLE', 'API_FAILED', 'SCHEMA_FAILED',
]
for (const state of requiredStates) {
  if (LATEST_BASE_DATA_PROVIDER_STATES[state] !== state) fail(`provider state missing: ${state}`)
}

const registry = read('src/meta/master-data/foundationEntryUnificationRegistry.js')
const enterprisePage = read('src/meta/pages/EnterpriseMasterDataPage.vue')
const productionPage = read('src/meta/components/ProductionFoundationMaintenance.vue')
const requestClient = read('src/api/request.js')
for (const row of orderProductionBaseDataTemplateAdoption) {
  if (!row.formalModel || !row.api || !row.component || !row.routePath) fail(`${row.moduleId}: incomplete formal mapping`)
  if (!registry.includes(`'${row.entityKey}'`) || !registry.includes(row.formalModel) || !registry.includes(row.routePath)) {
    fail(`${row.moduleId}: registry entity/model/route mapping missing`)
  }
  if (row.legacyFallbackAllowed !== false) fail(`${row.moduleId}: legacy fallback enabled`)
}
for (const token of ['data-provider-state', 'providerStateLabel', 'PceEnterpriseListTable']) {
  if (!enterprisePage.includes(token) || !productionPage.includes(token)) fail(`shared page/provider binding missing: ${token}`)
}
if (!requestClient.includes('isUsableServerJwt') || !requestClient.includes('withCredentials: true')) fail('authenticated server request context is not enforced')
for (const pageSource of [enterprisePage, productionPage]) {
  if (/localStorage\s*\.\s*(?:getItem|setItem|removeItem|clear)\s*\(/.test(pageSource)) {
    fail('formal page reads or writes localStorage authority')
  }
}

const runtimeEvidencePath = path.join(projectRoot, 'docs/governance/WAVE1_PROVIDER_RUNTIME_EVIDENCE.json')
const adopted = orderProductionBaseDataTemplateAdoption.filter(row => row.adoptionStatus === 'ADOPTED')
if (adopted.length) {
  if (!fs.existsSync(runtimeEvidencePath)) fail('ADOPTED pages require runtime evidence')
  const evidence = JSON.parse(fs.readFileSync(runtimeEvidencePath, 'utf8'))
  for (const row of adopted) {
    const item = evidence.modules?.[row.moduleId]
    if (!item?.serverContextResolved || !item?.identityMatch) fail(`${row.moduleId}: context/identity runtime evidence failed`)
    if (item.dbCount !== item.apiTotal || item.apiTotal !== item.uiTotal) fail(`${row.moduleId}: DB/API/UI count mismatch`)
    if (item.dbCount > 0 && item.uiTotal === 0) fail(`${row.moduleId}: DB > 0 but UI = 0`)
    if (!['LOADED_EMPTY', 'LOADED_WITH_DATA'].includes(item.providerState)) fail(`${row.moduleId}: provider state is not successful`)
  }
}

console.log(`PASS latest base-data provider continuity contract: mappings=${orderProductionBaseDataTemplateAdoption.length} adoptedRuntimeChecks=${adopted.length}`)
