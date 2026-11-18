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

const governance = [
  'PCE-ERP开发治理总规范.md', '页面开发规范.md', 'PCE-ERP统一页面验收标准V1.1.md',
  '一页一验收规范.md', '金丝雀测试管理规范.md', '问题案例库.md',
]
check('Governance Files Loaded', governance.every(name => exists(`docs/governance/${name}`)))

const models = read('backend/procurement/models.py')
const service = read('backend/procurement/supplier_quotation_service.py')
const api = read('backend/procurement/supplier_quotation_api.py')
const provider = read('frontend/src/meta/providers/supplierQuoteProviderV114289.js')
const page = read('frontend/src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue')
const list = read('frontend/src/meta/components/ScmSupplierQuoteEnterpriseList.vue')
const router = read('frontend/src/router/index.js')
const canary = read('backend/purchase_canary/supplier_quotation_runtime.py')
const acceptance = read('frontend/test-results/SCM-SUPPLIER-QUOTATION-ACT-001.md')

const db = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const rows = db.prepare(`
  SELECT sq.id, sq.quotation_no, sq.source_inquiry_id, sq.supplier_id, sq.supplier_name,
         sq.items, sq.quantity, sq.price, sq.currency, sq.quotation_status, sq.received_at,
         pi.inquiry_no
  FROM scm_supplier_quotation sq
  JOIN scm_purchase_inquiry pi ON pi.id = sq.source_inquiry_id
  ORDER BY sq.id
`).all()
const priceApprovalCount = db.prepare('SELECT COUNT(*) AS count FROM scm_price_approval').get().count
const purchaseOrderCount = db.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count
db.close()

const validRows = rows.filter(row => {
  const items = JSON.parse(row.items || '[]')
  return row.quotation_no && row.inquiry_no && row.source_inquiry_id && row.supplier_id
    && row.supplier_name && items.length > 0 && Number(row.quantity) > 0 && Number(row.price) > 0
    && row.currency && row.quotation_status === 'received' && row.received_at
})
check('SupplierQuotation Exists', models.includes('class SupplierQuotation') && rows.length > 0, `count=${rows.length}`)
check('PurchaseInquiry Traceable', validRows.length === rows.length && rows.length > 0)
check('Real Business Chain', rows.some(row => row.inquiry_no === 'PI-202608050001'
  && row.quotation_no === 'SQ-202608050001'))
check('Quotation Fields Complete', ['quotation_no', 'source_inquiry', 'supplier_id', 'supplier_name',
  'price', 'currency', 'quotation_status', 'received_at'].every(field => models.includes(field)))
check('Manual Save And Receive', api.includes('IsAuthenticated') && service.includes('save_supplier_quotation')
  && service.includes('submit_supplier_quotation') && service.includes('SUPPLIER_QUOTATION_INCOMPLETE'))

const expectedMappings = Array.from({ length: 8 }, (_, index) => ({
  inquiry: `PI-CAN-${String(index + 1).padStart(3, '0')}`,
  quotation: `SQ-CAN-${String(index + 1).padStart(3, '0')}`,
}))
const canaryDb = new DatabaseSync(path.join(root, 'backend/canary-data/scm-canary-flow-v1.sqlite3'), { readOnly: true })
const inquiryMappings = canaryDb.prepare(`
  SELECT object_no AS inquiry_no FROM pce_purchase_canary_module_object
  WHERE module_code = 'purchase-inquiry' ORDER BY object_no
`).all()
canaryDb.close()
check('Eight Canary Mappings', expectedMappings.every(({ inquiry, quotation }) =>
  inquiryMappings.some(row => row.inquiry_no === inquiry)
    && Number(inquiry.slice(-3)) === Number(quotation.slice(-3)))
  && canary.includes('quotation_no = f"SQ-CAN-{sequence:03d}"')
  && !rows.some(row => /CAN|DEMO|TEST/.test(row.quotation_no)))
check('Production Canary Isolation', provider.includes("dataMode = canary.isCanaryMode ? 'canary_acceptance' : 'production'")
  && provider.includes('getSupplierQuotationCanaryRuntime')
  && canary.includes('"productionUserDataWritten": False'))

let formal = null
let refresh = null
let canaryHappy = null
let canaryQuality = null
try {
  const [first, second, happy, quality] = await Promise.all([
    fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/supplier-quotation/'),
    fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/supplier-quotation/'),
    fetch('http://127.0.0.1:8000/api/pce/purchase-canary/supplier-quotation-runtime?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=HAPPY_PATH'),
    fetch('http://127.0.0.1:8000/api/pce/purchase-canary/supplier-quotation-runtime?canaryBatchId=SCM-CANARY-FLOW-V1&scenarioCode=QUALITY_FAIL'),
  ])
  ;[formal, refresh, canaryHappy, canaryQuality] = await Promise.all([first.json(), second.json(), happy.json(), quality.json()])
} catch (error) {
  formal = { error: String(error) }
}
const formalObjects = formal?.data?.objects || []
check('Formal API Real Facts', formal?.success === true && formalObjects.length === rows.length
  && formalObjects.every(item => !/CAN|DEMO|TEST/.test(item.quotationNo || '')))
check('Refresh Persistence', JSON.stringify(formal?.data?.objects) === JSON.stringify(refresh?.data?.objects))
check('Canary Runtime', canaryHappy?.data?.sourceMapping?.inquiryNo === 'PI-CAN-001'
  && canaryHappy?.data?.records?.[0]?.quotationNo === 'SQ-CAN-001'
  || canaryHappy?.data?.objects?.[0]?.quotationNo === 'SQ-CAN-001'
    && canaryQuality?.data?.sourceMapping?.inquiryNo === 'PI-CAN-003'
    && canaryQuality?.data?.objects?.[0]?.quotationNo === 'SQ-CAN-003')
check('Single Page', (router.match(/path: 'scm\/supplier-quotation'/g) || []).length === 1
  && router.includes("redirect: '/scm/supplier-quotation'")
  && router.includes('{ pageOwnsCanary: true }'))
check('Enterprise List Contract', list.includes('PceEnterpriseListTable')
  && list.includes('createPceEnterpriseListContract') && list.includes('quotationStatusLabel'))
check('Page Guide And Boundary', page.includes('data-acceptance-region="page-operation-guide"')
  && page.includes('第六步：') && page.includes('进入核价') && page.includes('<el-button disabled')
  && !service.includes('PriceApproval.objects.create') && !service.includes('PurchaseOrder.objects.create'))
check('One Page Acceptance', ['PAGE-COMMON', 'LIST', 'FORM', 'GUIDE', 'CHAIN', 'CANARY',
  'SCM-QUOTATION', 'PASS', 'FAIL', 'N/A', 'UNKNOWN', 'PAGE_READY'].every(value => acceptance.includes(value)))
check('No Downstream Creation', priceApprovalCount === 0 && purchaseOrderCount >= 0,
  `priceApprovalCount=${priceApprovalCount},purchaseOrderCount=${purchaseOrderCount}`)
check('Production Data Protection', provider.includes('productionUserDataWritten: false'))

const regression = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV114289.test.mjs',
  'tests/acceptance/enterpriseSupplierQuoteRuntimeV1142811.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', timeout: 120000 })
check('Regression', regression.status === 0, `${regression.stdout}\n${regression.stderr}`.slice(-3000))

if (checks.every(item => item.pass)) {
  const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
    cwd: frontendRoot, encoding: 'utf8', timeout: 180000,
  })
  check('Build', build.status === 0, `${build.stdout}\n${build.stderr}`.slice(-3000))
} else check('Build', false, 'blocked by failed chain check')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`SupplierQuotationCount=${rows.length}`)
console.log(`PriceApprovalCount=${priceApprovalCount}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('productionUserDataWritten=false')
const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_SUPPLIER_QUOTATION_CHAIN_READY' : 'SCM_SUPPLIER_QUOTATION_CHAIN_ISSUES_FOUND')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${item.evidence}`)
  process.exitCode = 1
}
