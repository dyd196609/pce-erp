import { chromium } from 'playwright'
import { createHash } from 'node:crypto'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'

const frontendRoot = process.cwd()
const projectRoot = path.resolve(frontendRoot, '..')
const databasePath = process.env.PCE_WAVE1_DATABASE_PATH || path.join(projectRoot, 'backend', 'db.sqlite3')
const outputPath = path.join(projectRoot, 'docs', 'governance', 'WAVE1_PROVIDER_UI_RUNTIME.json')
const baseURL = process.env.PCE_WAVE1_BASE_URL || 'http://127.0.0.1:5174'
const backendOrigin = process.env.PCE_WAVE1_BACKEND_ORIGIN || 'http://127.0.0.1:8000'
const hashFile = async file => createHash('sha256').update(await readFile(file)).digest('hex')

const pages = [
  ['customer', '/master-data/customers', '/api/masterdata/enterprise/customers/facts/', 'rows', '[data-acceptance-id="master-data-customers-page"]'],
  ['supplier', '/master-data/suppliers', '/api/masterdata/enterprise/suppliers/facts/', 'rows', '[data-acceptance-id="master-data-suppliers-page"]'],
  ['material', '/foundation/master-data/materials', '/api/pde/a1-foundation/materials/', 'materials'],
  ['product-category', '/foundation/master-data/product-categories', '/api/pde/a1-foundation/product-categories/', 'product-categories'],
  ['manufacturing-process-type', '/foundation/master-data/manufacturing-process-types', '/api/pde/a1-foundation/manufacturing-process-types/', 'manufacturing-process-types'],
  ['product-definition', '/foundation/master-data/products', '/api/pde/a1-foundation/products/', 'products'],
  ['product-version', '/foundation/master-data/product-versions', '/api/pde/a1-foundation/product-versions/', 'product-versions'],
  ['bom', '/foundation/master-data/boms', '/api/pde/a1-foundation/boms/', 'boms'],
  ['bom-version', '/foundation/master-data/bom-versions', '/api/pde/a1-foundation/bom-versions/', 'bom-versions'],
  ['bom-item', '/foundation/master-data/bom-items', '/api/pde/a1-foundation/bom-items/', 'bom-items'],
  ['bom-substitute', '/foundation/master-data/bom-substitutes', '/api/pde/a1-foundation/bom-substitutes/', 'bom-substitutes'],
  ['routing', '/foundation/master-data/routings', '/api/pde/a1-foundation/routings/', 'routings'],
  ['routing-version', '/foundation/master-data/routing-versions', '/api/pde/a1-foundation/routing-versions/', 'routing-versions'],
  ['routing-step', '/foundation/master-data/routing-steps', '/api/pde/a1-foundation/routing-steps/', 'routing-steps'],
  ['engineering-document', '/foundation/master-data/engineering-documents', '/api/pde/a1-foundation/engineering-documents/', 'engineering-documents'],
  ['engineering-document-version', '/foundation/master-data/engineering-document-versions', '/api/pde/a1-foundation/engineering-document-versions/', 'engineering-document-versions'],
  ['manufacturing-output', '/foundation/master-data/manufacturing-outputs', '/api/pde/a1-foundation/manufacturing-outputs/', 'manufacturing-outputs'],
  ['engineering-source-record', '/foundation/master-data/engineering-source-records', '/api/pde/a1-foundation/engineering-source-records/', 'engineering-source-records'],
  ['workshop', '/foundation/master-data/workshops', '/api/pde/a1-foundation/workshops/', 'workshops'],
  ['work-center', '/foundation/master-data/work-centers', '/api/pde/a1-foundation/work-centers/', 'work-centers'],
  ['operation', '/foundation/master-data/operations', '/api/pde/a1-foundation/operations/', 'operations'],
  ['equipment', '/foundation/master-data/equipment', '/api/pde/a1-foundation/equipment/', 'equipment'],
  ['capacity', '/foundation/master-data/standard-capacities', '/api/pde/a1-foundation/standard-capacities/', 'standard-capacities'],
]

const databaseHashBeforeAuthentication = await hashFile(databasePath)
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
const context = await browser.newContext({ baseURL, viewport: { width: 1600, height: 1000 } })
const page = await context.newPage()
const login = await page.request.post('/api/auth/login/', {
  data: { username: process.env.PCE_TEST_USERNAME || 'admin', password: process.env.PCE_TEST_PASSWORD || 'admin123' },
})
if (login.status() !== 200) throw new Error(`WAVE1_RUNTIME_AUTH_FAILED:${login.status()}`)
const auth = await login.json()
await page.goto('/#/foundation/master-data/materials', { waitUntil: 'domcontentloaded' })
await page.waitForURL(url => url.hash.startsWith('#/login') && url.hash.includes('formal-server-context-required'))
const unauthenticatedRouteGuard = true
await page.addInitScript(token => localStorage.setItem('token', token), auth.token)
await page.evaluate(token => localStorage.setItem('token', token), auth.token)
const databaseHashBefore = await hashFile(databasePath)
const businessWrites = []
page.on('request', request => {
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method()) && !request.url().endsWith('/api/auth/login/')) {
    businessWrites.push(`${request.method()} ${request.url()}`)
  }
})
const modules = {}
for (const [moduleId, routePath, apiPath, entityKey, enterpriseSelector] of pages) {
  const apiResponse = await page.request.get(apiPath, { headers: { Authorization: `Bearer ${auth.token}` } })
  if (apiResponse.status() !== 200) throw new Error(`${moduleId}:API_STATUS_${apiResponse.status()}`)
  const apiBody = await apiResponse.json()
  const apiRows = entityKey === 'rows' ? apiBody.rows : apiBody.facts?.[entityKey]
  const apiTotal = entityKey === 'rows' ? apiBody.recordCount : apiBody.recordCounts?.[entityKey]
  await page.goto(`/#${routePath}`, { waitUntil: 'domcontentloaded' })
  const rootSelector = enterpriseSelector || `[data-provider-state][data-module-key="${moduleId}"]`
  const root = page.locator(rootSelector)
  await root.waitFor({ state: 'visible' })
  await page.waitForFunction(selector => {
    const value = document.querySelector(selector)?.getAttribute('data-provider-state')
    return value === 'LOADED_EMPTY' || value === 'LOADED_WITH_DATA'
  }, rootSelector)
  const providerState = await root.getAttribute('data-provider-state')
  const templateVersion = await root.getAttribute('data-latest-base-data-template')
  const uiText = await page.locator('[data-acceptance-id="pagination-total"]').innerText()
  const uiTotal = Number(uiText.match(/\d+/)?.[0] || -1)
  const sample = (apiRows || [])[0] || null
  const sampleIdentity = sample && [sample.customerCode, sample.supplierCode, sample.code, sample.product_code, sample.bom_code, sample.routing_code, sample.document_no, sample.source_no, sample.name]
    .find(value => value !== undefined && value !== null && String(value).trim())
  const bodyText = sampleIdentity ? await page.locator('body').innerText() : ''
  const identityMatch = !sampleIdentity || bodyText.includes(String(sampleIdentity))
  const renderedModuleId = await root.getAttribute('data-module-key')
  const renderedApiPath = await root.getAttribute('data-api-url')
  modules[moduleId] = {
    routePath, apiPath, apiStatus: apiResponse.status(), apiTotal, uiTotal,
    providerState, templateVersion, renderedModuleId, renderedApiPath,
    serverContextResolved: Boolean(apiBody.factLoadFacts?.tenantId && apiBody.factLoadFacts?.batchId),
    sampleIdentity: sampleIdentity || null, identityMatch,
  }
  console.log(`${moduleId}: api=${apiTotal} ui=${uiTotal} state=${providerState} identity=${identityMatch} rendered=${renderedModuleId} adapter=${renderedApiPath}`)
  if (apiTotal !== uiTotal) throw new Error(`${moduleId}:API_UI_MISMATCH:${apiTotal}/${uiTotal}`)
  if (apiTotal > 0 && providerState !== 'LOADED_WITH_DATA') throw new Error(`${moduleId}:EXPECTED_LOADED_WITH_DATA`)
  if (apiTotal === 0 && providerState !== 'LOADED_EMPTY') throw new Error(`${moduleId}:EXPECTED_LOADED_EMPTY`)
  if (!identityMatch) throw new Error(`${moduleId}:BUSINESS_IDENTITY_MISMATCH`)
  if (templateVersion !== 'PCE-LATEST-BASE-DATA-TEMPLATE-V1.0') throw new Error(`${moduleId}:TEMPLATE_MISMATCH`)
}

await context.close()
await browser.close()
const databaseHashAfter = await hashFile(databasePath)
if (businessWrites.length) throw new Error(`BUSINESS_WRITES_OBSERVED:${businessWrites.join(',')}`)
if (databaseHashBefore !== databaseHashAfter) throw new Error('DATABASE_HASH_CHANGED')
await mkdir(path.dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify({
  generatedAt: new Date().toISOString(), baseURL, backendOrigin,
  authenticationScope: 'authenticated project test runner; credentials omitted',
  unauthenticatedRouteGuard,
  databaseHashBeforeAuthentication, databaseHashBefore, databaseHashAfter,
  authenticationMetadataWriteExcluded: databaseHashBeforeAuthentication !== databaseHashBefore,
  businessWriteCount: businessWrites.length, modules,
}, null, 2)}\n`)
console.log(`PASS Wave1 provider runtime: modules=${Object.keys(modules).length} businessWrites=0 dbHashUnchanged=true`)
