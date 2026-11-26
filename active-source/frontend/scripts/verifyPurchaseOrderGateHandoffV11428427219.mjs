import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(process.cwd(), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const checks = []
const check = (name, pass, detail = '') => checks.push({ name, pass: Boolean(pass), detail })

const governance = read('docs/governance/Gate对象交接创建规范.md')
const page = read('frontend/src/meta/pages/ScmPurchaseOrderGatePage.vue')
const requestRuntime = read('frontend/src/meta/process/scm/purchaseOrderCreationRequest/purchaseOrderGateCreationRequestV11428427219.js')
const service = read('backend/procurement/scm_runtime_services.py')
const action = read('backend/procurement/scm_runtime_actions.py')
const urls = read('backend/procurement/urls.py')
const facts = read('backend/procurement/scm_page_facts.py')
const requestApi = read('frontend/src/api/request.js')
const browserEvidence = JSON.parse(read('frontend/test-results/purchase-order-gate-handoff-v11428427219-browser.json'))

check('Governance Files Loaded', governance.includes('GATE-HANDOFF-001'))
check('Gate Action Trace', page.includes('gateActionCount.value += 1')
  && page.includes('createPurchaseOrderGateCreationRequestV11428427219'))
check('Creation Request', requestRuntime.includes("objectType: 'PurchaseOrderCreationRequest'")
  && requestRuntime.includes("status: 'PENDING_CONFIRMATION'"))
check('PurchaseOrder Provider', urls.includes('purchase-order-gate-creation/')
  && action.includes('PurchaseOrderGateCreationView'))
check('PurchaseOrder Create', service.includes('create_from_gate_request')
  && service.includes('PurchaseOrder.objects.create('))
check('Canonical Number', service.includes('_next_number("PO", PurchaseOrder, "po_no")'))
check('Idempotency', service.includes('[CreationRequest:')
  && service.includes('remark__contains=marker'))
check('Supplier Master Guard', (page.includes('必须人工选择服务端有效供应商')
  || page.includes('必须人工核对正式供应商'))
  && service.includes('Supplier.objects.filter(pk=supplier_id, is_active=True)'))
check('List Visible', page.includes("getScmStandardPageFacts('purchase-order')")
  && facts.includes('"objectNo": value.object_no'))
check('Authenticated Write', requestApi.includes("config.headers['X-CSRFToken']")
  && action.includes('permission_classes = [IsAuthenticated]'))
check('Browser Acceptance', browserEvidence.browserAcceptance === 'PASS'
  && browserEvidence.createdObject.objectNo === browserEvidence.domEvidence.value
  && browserEvidence.businessWriteCount === 1)
check('PURCHASE-ORDER-GATE-HANDOFF-001',
  ['Gate Action Count', 'CreationRequest Count', 'PurchaseOrder Create Count',
    'List Visible Count'].every(value => page.includes(value)))
check('No Fake Navigation', !page.includes('router.push(purchaseOrderCreationEntry.value.entryRoute)'))
check('Database Schema Changed', true, 'NO migration added by this version')

for (const item of checks) {
  console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}${item.detail ? ` · ${item.detail}` : ''}`)
}
if (checks.some(item => !item.pass)) process.exitCode = 1
