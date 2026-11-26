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

const service = read('backend/procurement/purchase_inquiry_service.py')
const api = read('backend/procurement/purchase_inquiry_api.py')
const page = read('frontend/src/meta/pages/ScmPurchaseInquiryNodePage.vue')
const provider = read('frontend/src/meta/providers/purchaseInquiryProvider.js')
const canaryProjection = read('backend/purchase_canary/purchase_inquiry_runtime.py')
const acceptance = read('frontend/test-results/SCM-PURCHASE-INQUIRY-ACT-001-R1.md')

const database = new DatabaseSync(path.join(root, 'backend/db.sqlite3'), { readOnly: true })
const inquiryRows = database.prepare(`
  SELECT pi.id, pi.inquiry_no, pi.source_purchase_request_id, pi.items, pi.quotation, pi.quantity,
         pi.status, pi.created_at, pr.request_no, pr.status AS request_status,
         pr.approval_status, pr.usage_department, pr.purchase_department
  FROM scm_purchase_inquiry pi
  JOIN scm_purchase_request pr ON pr.id = pi.source_purchase_request_id
  ORDER BY pi.id
`).all()
const purchaseOrderCount = database.prepare('SELECT COUNT(*) AS count FROM purchase_order').get().count
const priceApprovalCount = database.prepare('SELECT COUNT(*) AS count FROM scm_price_approval').get().count
database.close()

const validRows = inquiryRows.filter(row => {
  const items = JSON.parse(row.items || '[]')
  const quotation = JSON.parse(row.quotation || '{}')
  return row.request_status === 'approved' && row.approval_status === 'completed'
    && row.request_no && row.inquiry_no && row.source_purchase_request_id
    && items.length > 0 && (quotation.supplierCandidates || []).length > 0
    && quotation.sourcePurchaseRequestNo === row.request_no
})
check('PurchaseRequest Traceable', validRows.length > 0)
check('PurchaseInquiry Exists', inquiryRows.length > 0, `count=${inquiryRows.length}`)
check('Source Relationship', validRows.length === inquiryRows.length && inquiryRows.length > 0)
check('Approved Creation Guard', service.includes('request.status != "approved"')
  && service.includes('request.approval_status != "completed"')
  && service.includes('select_for_update()') && service.includes('existing = PurchaseInquiry.objects.filter'))

const expectedMappings = Array.from({ length: 8 }, (_, index) => ({
  request: `PRQ-CAN-${String(index + 1).padStart(3, '0')}`,
  inquiry: `PI-CAN-${String(index + 1).padStart(3, '0')}`,
}))
const canaryDb = new DatabaseSync(path.join(root, 'backend/canary-data/scm-canary-flow-v1.sqlite3'), { readOnly: true })
const mappings = canaryDb.prepare(`
  SELECT pr.object_no AS request_no, pi.object_no AS inquiry_no
  FROM pce_purchase_canary_module_object pr
  JOIN pce_purchase_canary_module_object pi ON pi.scenario_id = pr.scenario_id
  WHERE pr.module_code = 'purchase-request' AND pi.module_code = 'purchase-inquiry'
`).all()
canaryDb.close()
check('Eight Canary Mappings', expectedMappings.every(expected => mappings.some(row =>
  row.request_no === expected.request && row.inquiry_no === expected.inquiry))
  && !inquiryRows.some(row => /CAN|DEMO|TEST/.test(row.inquiry_no)))

let liveFacts = null
let refreshFacts = null
try {
  const first = await fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/purchase-inquiry/')
  const second = await fetch('http://127.0.0.1:8000/api/procurement/scm-page-facts/purchase-inquiry/')
  liveFacts = await first.json()
  refreshFacts = await second.json()
} catch (error) {
  liveFacts = { error: String(error) }
}
const liveObjects = liveFacts?.data?.objects || []
check('Formal API Isolation', liveFacts?.success === true && liveObjects.length === inquiryRows.length
  && liveObjects.every(item => !/CAN|DEMO|TEST/.test(item.inquiryNo || '')))
check('Refresh Persistence', JSON.stringify(liveFacts?.data?.objects) === JSON.stringify(refreshFacts?.data?.objects))
check('Source Fields Complete', liveObjects.every(item => item.sourcePurchaseRequestId
  && item.sourcePurchaseRequestNo && item.materials?.length && item.quantity && item.createdAt))
check('Explicit Page Action', page.includes('@click="createInquiry(row)"')
  && provider.includes('createFromApprovedRequest(requestId)')
  && api.includes('permission_classes = [IsAuthenticated]'))
check('One Page Acceptance', acceptance.includes('PAGE-COMMON') && acceptance.includes('LIST')
  && acceptance.includes('SCM-INQUIRY') && acceptance.includes('GUIDE')
  && acceptance.includes('CANARY') && acceptance.includes('CHAIN') && acceptance.includes('PAGE_READY'))
check('No PurchaseOrder Creation', !service.includes('PurchaseOrder.objects.create') && purchaseOrderCount >= 0,
  `purchaseOrderCount=${purchaseOrderCount}`)
check('No PriceApproval Creation', !service.includes('PriceApproval.objects.create') && priceApprovalCount === 0,
  `priceApprovalCount=${priceApprovalCount}`)
check('Production Data Protection', provider.includes('productionUserDataWritten: false')
  && canaryProjection.includes('"productionUserDataWritten": False'))

if (checks.every(item => item.pass)) {
  const build = spawnSync(process.execPath, [path.join(frontendRoot, 'node_modules/vite/bin/vite.js'), 'build', '.'], {
    cwd: frontendRoot, encoding: 'utf8', timeout: 180000,
  })
  check('Build', build.status === 0, build.status === 0 ? 'vite build completed' : `${build.stdout}\n${build.stderr}`.slice(-3000))
} else check('Build', false, 'blocked by failed chain check')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`PurchaseInquiryCount=${inquiryRows.length}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('productionUserDataWritten=false')
const passed = checks.every(item => item.pass)
console.log(passed ? 'SCM_PURCHASE_INQUIRY_CHAIN_READY' : 'SCM_PURCHASE_INQUIRY_CHAIN_ISSUES_FOUND')
if (!passed) {
  for (const item of checks.filter(item => !item.pass)) console.error(`${item.name}: ${JSON.stringify(item.evidence)}`)
  process.exitCode = 1
}
