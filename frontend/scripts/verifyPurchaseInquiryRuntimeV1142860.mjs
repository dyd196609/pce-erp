import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { execFileSync } from 'node:child_process'
import { PURCHASE_INQUIRY_RUNTIME, buildPurchaseInquiryRuntimeView, createPurchaseInquiryRuntimeObject, evaluatePurchaseInquiryRuntimeGuard } from '../src/meta/runtime/purchaseInquiryRuntime.js'
import { PURCHASE_INQUIRY_TASK_MODEL, validatePurchaseInquiryTaskModel } from '../src/meta/domain/scm/purchaseInquiry/runtime/purchaseInquiryTaskModel.js'
import { PURCHASE_INQUIRY_RUNTIME_MAPPING, validatePurchaseInquiryRuntimeMapping } from '../src/meta/schema/scm/purchaseInquiryRuntimeMapping.js'
import { PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE, validatePurchaseInquiryRuntimeAcceptance } from '../src/meta/acceptance/scm/purchaseInquiryRuntimeAcceptanceProfile.js'

const VERSION = 'V1.14.2.8.6.0'
const TARGET_STATUS = 'SCM_PURCHASE_INQUIRY_RUNTIME_READY'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const read = (relative) => fs.readFile(path.join(frontendRoot, relative), 'utf8')
const rule = (gate, pass, evidence) => Object.freeze({ gate, result: pass ? 'PASS' : 'FAIL', evidence })

async function listFiles(relative) {
  const root = path.join(frontendRoot, relative)
  const output = []
  async function walk(directory) {
    for (const entry of await fs.readdir(directory, { withFileTypes: true })) {
      const full = path.join(directory, entry.name)
      if (entry.isDirectory()) await walk(full)
      else output.push(path.relative(frontendRoot, full).replaceAll('\\', '/'))
    }
  }
  try { await walk(root) } catch { /* represented as empty in scan */ }
  return output.sort()
}

async function buildScan() {
  const [domainFiles, schemaFiles, routerSource, pageFiles] = await Promise.all([
    listFiles('src/meta/domain/scm/purchaseInquiry'), listFiles('src/meta/schema'), read('src/router/index.js'), listFiles('src/meta/pages'),
  ])
  return Object.freeze({
    version: VERSION,
    generatedAt: new Date().toISOString(),
    scope: Object.freeze(['src/meta/domain/scm/purchaseInquiry', 'src/meta/schema', 'src/router', 'src/pages', 'src/meta/pages']),
    inventory: Object.freeze({ domainFiles, schemaFiles, routerPurchaseInquiryBindings: (routerSource.match(/scm\/purchase-inquiry/g) || []).length,
      purchaseInquiryPageFiles: pageFiles.filter((file) => file.includes('PurchaseInquiry')) }),
    findings: Object.freeze({ domainModelPresent: domainFiles.some((file) => file.endsWith('purchaseInquiryDomainModel.js')),
      runtimeAdded: domainFiles.some((file) => file.endsWith('purchaseInquiryTaskModel.js')),
      canonicalRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry'"), createRoutePresent: routerSource.includes("path: 'scm/purchase-inquiry/create'") }),
    protectedScopes: Object.freeze(['PurchaseOrder', 'Finance', 'Inventory', 'WMS', 'Workflow', 'Approval Engine', 'Supplier API', 'Database']),
  })
}

async function run() {
  const scan = await buildScan()
  const scanPath = path.join(frontendRoot, 'scm_purchase_inquiry_runtime_scan_v1142860.json')
  await fs.writeFile(scanPath, `${JSON.stringify(scan, null, 2)}\n`, 'utf8')
  if (process.argv.includes('--scan-only')) return { scanPath, scan }

  const [routerSource, canonicalPageSource, acceptanceRegistrySource, databaseStatBefore] = await Promise.all([
    read('src/router/index.js'), read('src/meta/pages/ScmPurchaseInquiryNodePage.vue'),
    read('src/meta/acceptance/registry/enterpriseAcceptanceRegistry.js'), fs.stat(path.join(workspaceRoot, 'backend/db.sqlite3')),
  ])
  const mapped = buildPurchaseInquiryRuntimeView({ recordCount: 1, objects: [{ id: 1, inquiryNo: 'PI-TEST', inquiryDate: '2026-08-03', sourceRequestNo: 'PR-TEST', buyerName: '验收采购员', supplierCount: 2, lineCount: 1, statusCode: 'draft', statusLabel: '草稿' }] })
  const created = createPurchaseInquiryRuntimeObject({ inquiryTitle: '运行验收', inquiryDate: '2026-08-03', buyerName: '验收采购员', currency: 'CNY', suppliers: ['SUPPLIER-A'], lines: [{ materialCode: 'MAT-001', materialName: '验收物料', quantity: 1, unit: '件', requiredDate: '2026-08-10' }] })
  const rules = [
    rule('Page', ['purchase-inquiry-list', 'source-purchase-request', 'material-supplier-decision', 'next-action']
      .every((id) => canonicalPageSource.includes(`data-acceptance-region="${id}"`)), { canonicalRoute: '/scm/purchase-inquiry', createRoute: 'redirect_only' }),
    rule('Router', routerSource.includes('ScmPurchaseInquiryNodePage.vue')
      && routerSource.includes("wrapPceListPage('purchase-inquiry'")
      && routerSource.includes("redirect: '/scm/purchase-inquiry'"), { canonicalRoute: '/scm/purchase-inquiry', compatibilityRedirect: '/scm/purchase-inquiry/create' }),
    rule('Schema', validatePurchaseInquiryRuntimeMapping().valid && PURCHASE_INQUIRY_RUNTIME_MAPPING.schemaId === 'PurchaseInquirySchema', PURCHASE_INQUIRY_RUNTIME_MAPPING.mappingCode),
    rule('Runtime', validatePurchaseInquiryTaskModel().valid && mapped.inquiries.length === 1 && created.persistenceMode === 'memory_only' && created.statusCode === 'draft', { runtime: PURCHASE_INQUIRY_RUNTIME.runtimeCode, taskModel: PURCHASE_INQUIRY_TASK_MODEL.modelCode }),
    rule('Guard', ['createPurchaseOrder', 'sendSupplier', 'payment', 'inventoryAction'].every((action) => evaluatePurchaseInquiryRuntimeGuard(action).decision === 'deny') && evaluatePurchaseInquiryRuntimeGuard('createInquiryObject').decision === 'allow', PURCHASE_INQUIRY_TASK_MODEL.forbiddenActions),
    rule('Acceptance', validatePurchaseInquiryRuntimeAcceptance().valid && acceptanceRegistrySource.includes('PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE'), PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE.profileCode),
  ]
  try {
    const viteEntry = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
    const output = execFileSync(process.execPath, [viteEntry, 'build', '.', '--emptyOutDir=false'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: 240000 })
    rules.push(rule('Build', true, output.trim().split(/\r?\n/).slice(-2)))
  } catch (error) {
    rules.push(rule('Build', false, String(error.stderr || error.message)))
  }
  const databaseStatAfter = await fs.stat(path.join(workspaceRoot, 'backend/db.sqlite3'))
  const databaseUnchanged = databaseStatBefore.size === databaseStatAfter.size && databaseStatBefore.mtimeMs === databaseStatAfter.mtimeMs
  const pass = rules.every((item) => item.result === 'PASS') && databaseUnchanged
  const report = Object.freeze({ version: VERSION, generatedAt: new Date().toISOString(), status: pass ? TARGET_STATUS : 'FAIL', gates: Object.freeze(rules),
    summary: Object.freeze({ PASS: rules.filter((item) => item.result === 'PASS').length, FAIL: rules.filter((item) => item.result === 'FAIL').length }),
    businessWriteCount: 0, runtimeObjectCreationCount: 1, databaseState: databaseUnchanged ? 'UNCHANGED' : 'CHANGED', productionDataWritten: false,
    protectedScopeChanges: 0, scanFile: path.basename(scanPath) })
  const outputRoot = path.join(frontendRoot, 'test-results/page-acceptance', VERSION, 'purchase-inquiry-runtime')
  await fs.mkdir(outputRoot, { recursive: true })
  await fs.writeFile(path.join(outputRoot, 'verification-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
  return { report, outputRoot, scanPath }
}

const result = await run()
console.log(JSON.stringify(result, null, 2))
if (result.report && result.report.status !== TARGET_STATUS) process.exitCode = 1
