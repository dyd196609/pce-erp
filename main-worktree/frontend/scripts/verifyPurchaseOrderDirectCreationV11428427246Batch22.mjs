import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(process.cwd(), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const API = process.env.PCE_API_BASE || 'http://127.0.0.1:8000'
const TARGET_ORDER = process.env.BATCH22_ACCEPTANCE_PO_NO || 'PO202608140002'
const TARGET_PRICE = 'SMP-PAP-QC-PI-202608040009-MT005'
const HISTORICAL_PRICE = 'SMP-PAP-REAL-SQ-202608040011-L1'

async function json(pathname) {
  const response = await fetch(`${API}${pathname}`, { headers: { Accept: 'application/json' } })
  const payload = await response.json()
  if (!response.ok) throw new Error(`${pathname} HTTP ${response.status}: ${JSON.stringify(payload)}`)
  return payload
}

const page = read('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
const api = read('frontend/src/api/scmStandardPageFacts.js')
const actions = read('backend/procurement/scm_runtime_actions.py')
const service = read('backend/procurement/scm_runtime_services.py')
const facts = read('backend/procurement/scm_page_facts.py')
const tests = read('backend/procurement/tests_v11428427246_batch22.py')
const ordersPayload = await json('/api/procurement/scm-page-facts/purchase-order/')
const pricesPayload = await json('/api/masterdata/prices/supplier-material-prices/runtime/facts/?supplierCode=SUP001&materialCode=MT005')
const orders = ordersPayload?.data?.objects || ordersPayload?.objects || []
const order = orders.find(item => item.objectNo === TARGET_ORDER)
const item = order?.items?.[0]
const prices = pricesPayload?.rows || []
const current = prices.find(item => item.priceNo === TARGET_PRICE)
const historical = prices.find(item => item.priceNo === HISTORICAL_PRICE)

const gates = [
  ['PURCHASE-ORDER-DIRECT-CREATION-PAGE-001', /新建采购订单/.test(page)
    && /purchaseMode: ''/.test(page) && /supplierId: null/.test(page)
    && /materialId: null/.test(page) && /quantity: null/.test(page)],
  ['PURCHASE-ORDER-SUPPLIER-MASTER-001', /getActivePurchaseOrderSuppliers/.test(page)
    && /\/api\/procurement\/suppliers\//.test(api)],
  ['PURCHASE-ORDER-MATERIAL-MASTER-001', /getActivePurchaseOrderMaterials/.test(page)
    && /\/api\/masterdata\/materials\//.test(api)],
  ['MATERIAL-SUPPLIER-RELATION-001', /loadMaterialSupplierRelationRuntime/.test(page)
    && /MaterialSupplierRelationRuntime\.list_runtime_models/.test(service)],
  ['PURCHASE-ORDER-PRICE-BATCH-VISIBLE-001', prices.length === 2
    && current?.versionStatus === 'CURRENT' && historical?.versionStatus === 'HISTORICAL'],
  ['PURCHASE-ORDER-HISTORICAL-PRICE-BLOCK-001', /HISTORICAL_SUPPLIER_MATERIAL_PRICE_BLOCKED/.test(service)
    && /!row\.isCurrentApplicable/.test(page)],
  ['PURCHASE-ORDER-NO-PRICE-BLOCK-001', /当前供应商与物料没有可用于采购订单的正式价格/.test(page)
    && /test_missing_price_is_blocked/.test(tests)],
  ['PURCHASE-ORDER-GATE-001', /signing\.dumps/.test(service) && /signing\.loads/.test(service)
    && /previewOnly/.test(actions) && /humanConfirmed/.test(service)],
  ['PURCHASE-ORDER-IDEMPOTENCY-001', service.includes('source_reference=identity["idempotencyKey"]')
    && /test_same_idempotency_key_returns_existing_order/.test(tests)],
  ['PURCHASE-ORDER-PRICE-SNAPSHOT-001', item?.supplierMaterialPriceNo === TARGET_PRICE
    && String(item?.supplierMaterialPriceId) === '13' && Number(item?.unitPrice) === 120
    && Number(item?.taxRate) === 13 && item?.currency === 'CNY'],
  ['PURCHASE-ORDER-NO-IMPLICIT-CREATION-001', /onMounted\(async \(\) =>/.test(page)
    && !/onMounted[\s\S]{0,500}createOrder\(/.test(page)
    && /test_page_prepare_get_and_preview_do_not_create_order/.test(tests)],
  ['PURCHASE-ORDER-BATCH-BOUNDARY-001', /Batch3 建设，当前不可选择/.test(page)
    && /Batch4 建设，当前不可选择/.test(page)
    && order?.sourceType === 'MANUAL_STANDARD_PURCHASE_ORDER_CREATION'
    && item?.sourcePurchaseRequestNo === ''
    && /is_manual_creation/.test(facts)],
]

let failed = 0
for (const [name, passed] of gates) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`)
  if (!passed) failed += 1
}
console.log(JSON.stringify({
  targetOrder: TARGET_ORDER,
  targetOrderId: order?.objectId || null,
  supplierCode: order?.supplierCode || null,
  materialCode: item?.materialCode || null,
  quantity: item?.quantity || null,
  supplierMaterialPriceId: item?.supplierMaterialPriceId || null,
  supplierMaterialPriceNo: item?.supplierMaterialPriceNo || null,
  unitPrice: item?.unitPrice || null,
  taxRate: item?.taxRate || null,
  currency: item?.currency || null,
  passed: gates.length - failed,
  total: gates.length,
  result: failed ? 'FAIL' : 'PASS',
}, null, 2))
if (failed) process.exit(1)
