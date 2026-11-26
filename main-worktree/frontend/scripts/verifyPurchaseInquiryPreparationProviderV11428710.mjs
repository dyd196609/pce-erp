import fs from 'node:fs/promises'
import path from 'node:path'
import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createInquiryPreparationProvider, mapInquiryPreparationWorkbenchRow } from '../src/meta/providers/inquiryPreparationProvider.js'
import { validatePurchaseInquiryPreparationProviderAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryPreparationProviderAcceptanceProfile.js'
import { PURCHASE_INQUIRY_RUNTIME } from '../src/meta/runtime/purchaseInquiryRuntime.js'

const VERSION = 'V1.14.2.8.7.10'
const TARGET = 'SCM_PURCHASE_INQUIRY_PREPARATION_PROVIDER_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = relative => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const hash = async file => crypto.createHash('sha256').update(await fs.readFile(file)).digest('hex')
const gate = (name, pass, evidence) => ({ gate: name, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const files = []
  async function walk(directory) { for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name); if (entry.isDirectory()) await walk(full)
    else files.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
  } }
  try { await walk(path.join(frontendRoot, relative)) } catch { /* optional provider scope */ }
  return files.sort()
}

const fixture = Object.freeze({ inquiryPreparationNo: 'IPR-PR202608020008', sourceRequestNo: 'PR202608020008',
  sourceRequestDate: '2026-08-02', requester: '周丽', requestDepartment: '采购部', purchaseDepartment: '计划物控部', status: 'prepared',
  inquiryLines: Object.freeze([
    { lineNo: 1, materialCode: 'MT068', materialName: '扩展坞', quantity: 14, unit: '个', requiredDate: '2026-08-09' },
    { lineNo: 2, materialCode: 'MT026', materialName: '胶水', quantity: 500, unit: '瓶', requiredDate: '2026-08-10' },
  ]), supplierCandidates: Object.freeze([{ supplierId: 'SUP001', supplierCode: 'SUP001', supplierName: '华为技术有限公司' }]) })

async function createScan() {
  const [domainFiles, pageFiles, runtimeFiles, providerFiles, acceptanceFiles] = await Promise.all([
    listFiles('src/meta/domain/scm/inquiryPreparation'), listFiles('src/meta/pages'), listFiles('src/meta/runtime'),
    listFiles('src/meta/providers'), listFiles('src/meta/acceptance'),
  ])
  return { version: VERSION, generatedAt: new Date().toISOString(),
    scanned: ['InquiryPreparationObject', 'PurchaseInquirySchema', 'ScmPurchaseInquiryWorkbenchPage', 'Provider'],
    inventory: { domainFiles, pageFiles, runtimeFiles, providerFiles, acceptanceFiles },
    finding: { purchaseInquiryRecordCountMayBeZero: true, preparationPreviouslyReadDirectlyByPage: true,
      inquiryPreparationProviderPreviouslyExisted: false, requiredFactOwner: 'inquiry-preparation' },
    implementation: { providerCode: 'SCM_INQUIRY_PREPARATION_PROVIDER', formalInquiryProviderUnchanged: true,
      preparationAndInquiryFactsSeparated: true }, protectedScopes: ['Approval Engine', 'Purchase Order', 'Finance', 'Inventory'] }
}

async function run() {
  const scan = await createScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_preparation_provider_scan_v11428710.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }
  const databasePath = path.join(workspaceRoot, 'backend', 'db.sqlite3')
  const before = await hash(databasePath)
  const [page, router, providerSource, registry] = await Promise.all([
    read('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue'), read('src/router/index.js'),
    read('src/meta/providers/inquiryPreparationProvider.js'), read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'),
  ])
  const provider = createInquiryPreparationProvider({ reader: () => [fixture] })
  const facts = provider.load({ sourceRequestNo: 'PR202608020008' })
  const row = mapInquiryPreparationWorkbenchRow(fixture)
  const protections = facts.protections
  const gates = [
    gate('Provider', facts.providerCode === 'SCM_INQUIRY_PREPARATION_PROVIDER' && facts.recordCount === 1
      && facts.selected?.sourceRequestNo === 'PR202608020008' && providerSource.includes("factOwner: 'inquiry-preparation'"), facts),
    gate('Schema', row.inquiryPreparationNo === 'IPR-PR202608020008' && row.requestDepartment === '采购部'
      && row.purchaseDepartment === '计划物控部' && row.materialLineCount === 2 && row.materialQuantity === 514
      && row.requiredDate === '2026-08-09' && row.supplierCandidateCount === 1 && row.statusLabel === '询价准备完成', row),
    gate('Page', page.includes('询价准备工作台') && page.includes('data-provider-code="SCM_INQUIRY_PREPARATION_PROVIDER"')
      && page.includes('询价准备编号') && page.includes('来源申请号') && page.includes('物料数量')
      && page.includes('供应商候选数量') && page.includes('inquiryPreparationProvider.load'), '/scm/purchase-inquiry'),
    gate('Router', router.includes("path: 'scm/purchase-inquiry'") && router.includes('ScmPurchaseInquiryWorkbenchPage.vue'), '/scm/purchase-inquiry'),
    gate('Acceptance', validatePurchaseInquiryPreparationProviderAcceptance().valid
      && registry.includes('PURCHASE_INQUIRY_PREPARATION_PROVIDER_ACCEPTANCE_PROFILE')
      && PURCHASE_INQUIRY_RUNTIME.version === VERSION && PURCHASE_INQUIRY_RUNTIME.inquiryPreparationProviderCode === facts.providerCode, TARGET),
  ]
  try { execFileSync(process.execPath, [path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.', '--emptyOutDir=false'],
    { cwd: frontendRoot, stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 }); gates.push(gate('Build', true, 'vite build')) }
  catch (error) { gates.push(gate('Build', false, String(error.stderr || error.message))) }
  const after = await hash(databasePath)
  const database = before === after ? 'UNCHANGED' : 'CHANGED'
  const protectedState = { inquiryCreated: protections.inquiryCreated, quotationCreated: protections.quotationCreated,
    supplierSent: protections.supplierSent, priceApprovalCreated: protections.priceApprovalCreated,
    purchaseOrderCreated: protections.purchaseOrderCreated, productionDataWritten: protections.productionDataWritten, database }
  const passed = gates.every(item => item.result === 'PASS') && Object.entries(protectedState)
    .every(([key, value]) => key === 'database' ? value === 'UNCHANGED' : value === false)
  const report = { version: VERSION, status: passed ? TARGET : 'FAIL', gates,
    testObject: { sourceRequestNo: row.sourceRequestNo, materials: row.inquiryLines.map(item => ({ name: item.materialName, quantity: item.quantity })),
      supplierCandidateCount: row.supplierCandidateCount, status: row.statusLabel }, ...protectedState,
    databaseHashBefore: before, databaseHashAfter: after }
  const outputRoot = path.join(frontendRoot, 'test-results', 'page-acceptance', VERSION, 'purchase-inquiry-preparation-provider')
  await fs.mkdir(outputRoot, { recursive: true }); await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`)
  return { scanPath, outputRoot, report }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET) process.exitCode = 1
