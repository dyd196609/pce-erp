import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const exists = relative => fs.existsSync(path.join(root, relative))
const checks = []
const check = (name, pass, evidence = '') => checks.push({ name, pass: Boolean(pass), evidence })

const governanceFiles = [
  'PCE-ERP开发治理总规范.md',
  'PCE-ERP统一页面验收标准V1.1.md',
  '一页一验收规范.md',
  '金丝雀测试管理规范.md',
  '问题案例库.md',
  'DATA-CONTINUITY数据连续性规范.md',
]
check('Governance Files Loaded', governanceFiles.every(name => exists(`docs/governance/${name}`)))

const provider = read('frontend/src/meta/providers/quoteComparisonSimpleProviderV11428121.js')
const model = read('frontend/src/meta/process/scm/quoteComparison/quoteComparisonSimpleModelV11428121.js')
const store = read('frontend/src/meta/runtime/supplierQuoteRuntimeStoreV114289.js')
const page = read('frontend/src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue')
const router = read('frontend/src/router/index.js')
const canaryRuntime = read('backend/purchase_canary/quote_comparison_runtime.py')
const canaryViews = read('backend/purchase_canary/views.py')
const scan = read('docs/acceptance/scm_quote_comparison_current_state_v11428423.md')
const acceptance = read('frontend/test-results/SCM-QUOTE-COMPARISON-ACT-001.md')
const governance = read('docs/governance/DATA-CONTINUITY数据连续性规范.md')
const cases = read('docs/governance/问题案例库.md')

check('QuoteComparison Exists', model.includes("objectType: 'QuoteComparison'")
  && model.includes('quoteComparisonId') && page.includes('data-business-object="QuoteComparison"'))
check('SupplierQuotation Source', provider.includes("sourceProvider = supplierQuoteProvider")
  && model.includes('quotationNo') && page.includes('sourceQuotationNos'))
check('Formal Provider Unchanged', provider.includes("if (!canary.isCanaryMode) return Object.freeze({ ...this.load()")
  && provider.includes('const source = sourceProvider.load(query)')
  && store.includes("pce.scm.supplier-quote.runtime.v114289")
  && model.includes('`${record.inquiryNo}::${record.materialCode}`'))
check('Real Object Count Preserved 13', scan.includes('count=13') && scan.includes('13 -> 13 -> 13')
  && governance.includes('DATA-CONTINUITY-002') && governance.includes('count=13')
  && governance.includes('Before Count') && governance.includes('Refresh Count'))
check('Refresh Persistence Contract', provider.includes('this.load()') && !provider.includes('localStorage.clear')
  && !model.includes('.slice(0,') && !model.includes('QC-DEMO'))

const expectedMappings = Array.from({ length: 8 }, (_, index) => ({
  quotation: `SQ-CAN-${String(index + 1).padStart(3, '0')}`,
  comparison: `QC-CAN-${String(index + 1).padStart(3, '0')}`,
}))
const canaryDb = new DatabaseSync(path.join(root, 'backend/canary-data/scm-canary-flow-v1.sqlite3'), { readOnly: true })
const inquiryObjects = canaryDb.prepare(`
  SELECT object_no FROM pce_purchase_canary_module_object
  WHERE module_code = 'purchase-inquiry' ORDER BY object_no
`).all()
canaryDb.close()
check('Eight Canary Mappings', expectedMappings.every(({ quotation, comparison }) =>
  inquiryObjects.some(row => Number(row.object_no.slice(-3)) === Number(quotation.slice(-3)))
    && Number(quotation.slice(-3)) === Number(comparison.slice(-3)))
  && canaryRuntime.includes('comparison_no = f"QC-CAN-{sequence:03d}"')
  && canaryRuntime.includes('load_supplier_quotation_canary_runtime'))
check('Production Canary Isolation', provider.includes('productionProviderCallCount: 1')
  && provider.includes('productionProviderCallCount: 0')
  && provider.includes('getQuoteComparisonCanaryRuntime')
  && router.includes("wrapPceListPage('quote-comparison-workbench'")
  && router.includes('{ pageOwnsCanary: true }')
  && canaryRuntime.includes('"productionUserDataWritten": False'))
check('Canary Runtime API', canaryViews.includes('class QuoteComparisonCanaryRuntimeView')
  && canaryRuntime.includes('"records": [row]') && !canaryRuntime.includes('QC-DEMO'))
check('Page Guide', page.includes('data-acceptance-region="page-operation-guide"')
  && ['查看报价来源', '确认供应商报价', '比较价格', '确认比较结果', '进入核价准备']
    .every(text => page.includes(text)))
check('Business Chain Fields', ['sourceInquiryNo', 'sourceQuotationNos', 'materialCode', 'materialName',
  'quantity', 'supplierQuotes', 'lowestQuote', 'comparisonStatusLabel'].every(text => page.includes(text) || model.includes(text)))
check('One Page Acceptance', ['PAGE-COMMON', 'LIST', 'GUIDE', 'CHAIN', 'CANARY', 'DATA-CONTINUITY',
  'SCM-QUOTE-COMPARISON', 'PASS', 'FAIL', 'N/A', 'UNKNOWN'].every(text => acceptance.includes(text)))
check('Governance Case', governance.includes('DATA-CONTINUITY-002') && cases.includes('CASE-SCM-063'))

const db = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const priceApprovalCount = db.prepare('SELECT COUNT(*) AS count FROM scm_price_approval').get().count
const purchaseOrderCount = db.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count
db.close()
check('No Downstream Creation', priceApprovalCount === 0
  && !canaryRuntime.includes('PriceApproval.objects.create')
  && !canaryRuntime.includes('PurchaseOrder.objects.create'),
`priceApprovalCount=${priceApprovalCount},purchaseOrderCount=${purchaseOrderCount}`)
check('Production User Data Written', provider.includes('productionUserDataWritten: false')
  && canaryRuntime.includes('"businessWriteCount": 0'))

const regression = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142810.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonRuntimeV1142812.test.mjs',
  'tests/acceptance/enterpriseQuoteComparisonScrollVisualV11428134.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', timeout: 120000 })
check('Regression', regression.status === 0, `${regression.stdout}\n${regression.stderr}`.slice(-3000))

if (checks.every(item => item.pass)) {
  const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
    cwd: frontendRoot, encoding: 'utf8', timeout: 180000,
  })
  check('Build', build.status === 0, `${build.stdout}\n${build.stderr}`.slice(-3000))
} else check('Build', false, 'blocked by failed continuity check')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`PriceApprovalCount=${priceApprovalCount}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('productionUserDataWritten=false')
const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_QUOTE_COMPARISON_CHAIN_READY' : 'SCM_QUOTE_COMPARISON_CHAIN_ISSUES_FOUND')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}
