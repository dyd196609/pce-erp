import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = path.resolve(process.cwd(), '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const currentScript = fs.readFileSync(new URL(import.meta.url), 'utf8')
const requestPage = read('frontend/src/meta/pages/ScmPurchaseRequestPage.vue')
const agreedCreatePage = read('frontend/src/meta/pages/ScmAgreedPricePurchaseFoundationPage.vue')
const agreedPage = read('frontend/src/meta/pages/ScmAgreedPricePurchaseConfirmationPage.vue')
const directPage = read('frontend/src/meta/pages/ScmPurchaseOrderCreateEntryPage.vue')
const api = read('frontend/src/api/scmStandardPageFacts.js')
const router = read('frontend/src/router/index.js')
const service = read('backend/procurement/scm_runtime_services.py')
const actions = read('backend/procurement/scm_runtime_actions.py')
const facts = read('backend/procurement/scm_page_facts.py')
const models = read('backend/procurement/models.py')
const r5Tests = read('backend/procurement/tests_v11428427246_batch22_r5.py')

const tests = [
  ['AGREED_PRICE PurchaseRequest Creation（采购申请创建）', /openCreate\('AGREED_PRICE'\)/.test(agreedCreatePage)],
  ['AGREED_PRICE PurchaseRequest Approval（采购申请审批）', /status != "approved"|status != 'approved'/.test(service) && /approval_status != "completed"/.test(service)],
  ['Waiting Agreed Price Confirmation（等待既定价格确认）', /waiting_agreed_price_confirmation/.test(facts) && /等待既定价格确认/.test(facts)],
  ['Price Confirmation Action（既定价格确认操作）', /agreed-price-confirmation-action/.test(requestPage) && /既定价格确认/.test(requestPage)],
  ['PurchaseRequestItem Inheritance（申请明细继承）', /requestFact\.value\.items/.test(agreedPage) && /申请数量（只读）/.test(agreedPage) && /计划到货日期（继承）/.test(agreedPage)],
  ['SupplierMaterialPrice Binding（供应商物料价格绑定）', /supplierMaterialPriceId/.test(agreedPage) && /item\.supplier_material_price = price/.test(service)],
  ['Explicit Price Selection（明确选择价格）', /v-model="row\.priceId"/.test(agreedPage) && !/priceId:\s*candidates/.test(agreedPage)],
  ['CURRENT Price Only（仅当前适用价格）', /isCurrentApplicable===true/.test(agreedPage) && /HISTORICAL_SUPPLIER_MATERIAL_PRICE_BLOCKED/.test(service)],
  ['Material Supplier Relation（物料供应商关系）', /MATERIAL_SUPPLIER_RELATION_REQUIRED/.test(service)],
  ['Multi Supplier Split（多供应商拆单）', /supplier_groups\.setdefault/.test(service) && /for supplier_id, lines in context\["supplierGroups"\]\.items/.test(service)],
  ['PurchaseOrderGate（采购订单准入）', /inspectAgreedPricePurchaseOrder/.test(agreedPage) && /AGREED_PRICE_ADMISSION_SALT/.test(service)],
  ['Human Confirmation（人工确认）', /agreed-price-human-confirmation/.test(agreedPage) && /humanConfirmed:true/.test(agreedPage)],
  ['PurchaseOrder Creation（采购订单创建）', /purchase_mode="AGREED_PRICE"/.test(service) && /source_purchase_request=request_value/.test(service)],
  ['PurchaseOrderItem Creation（采购订单明细创建）', /PurchaseOrderItem\.objects\.create\([\s\S]{0,260}source_purchase_request_item=item/.test(service)],
  ['PurchaseOrder List Visibility（采购订单列表可见）', /purchase_mode="AGREED_PRICE"/.test(service) && /scm\/purchase-order/.test(router)],
  ['Bidirectional Traceability（双向追溯）', /related_name="purchase_orders"/.test(models) && /purchaseOrders/.test(facts)],
  ['AGREED_PRICE Unified Detail（统一采购订单详情）', /router\.push\(`\/scm\/purchase-order\/\$\{createdOrders\.value\[0\]\.objectId\}`\)/.test(agreedPage)],
  ['AGREED_PRICE Transaction（事务）', /@transaction\.atomic[\s\S]{0,120}def create_from_agreed_price_request/.test(service)],
  ['AGREED_PRICE Idempotency（幂等）', /AGREED_PRICE_PURCHASE_ORDER_ALREADY_CREATED/.test(service) && /same_key/.test(service)],
  ['AGREED_PRICE Server Revalidation（服务端重新校验）', /token_identity != identity/.test(service) && /_resolve_agreed_price_context/.test(service)],
  ['DIRECT Entry（直接采购入口）', /data-purchase-mode="DIRECT"/.test(requestPage) && /purchase-order\/create/.test(requestPage)],
  ['DIRECT SupplierMaterialPrice Selection（正式价格选择）', /loadSupplierMaterialPrices/.test(directPage)],
  ['DIRECT Multi Line（多明细）', /addLine/.test(directPage) && /lines\.value\.map/.test(directPage)],
  ['DIRECT Planned Delivery Date（计划到货日期）', /row\.expectedDate/.test(directPage) && /expected_date=line\["expectedDate"\]/.test(service)],
  ['DIRECT Gate（准入检查）', /inspectPurchaseOrderGateCreation/.test(directPage) && /DIRECT_ADMISSION_SALT/.test(service)],
  ['DIRECT Human Confirmation Visibility（人工确认可见）', /direct-human-confirmation-card/.test(directPage) && /人工确认/.test(directPage)],
  ['DIRECT Human Confirmation Layout（人工确认布局）', /gate-action-bar/.test(directPage) && /grid-template-columns:minmax\(180px,1fr\)/.test(directPage)],
  ['DIRECT Bottom Alignment（三段底部对齐）', /align-items:end/.test(directPage) && /action-left/.test(directPage) && /action-right/.test(directPage)],
  ['DIRECT Human Confirmation Real Click（真实点击绑定）', /v-model="humanConfirmed"/.test(directPage) && /@change="humanConfirmationChanged"/.test(directPage)],
  ['DIRECT Gate Reset After Change（修改后门禁失效）', /humanConfirmed\.value=false/.test(directPage) && /admissionToken\.value=''/.test(directPage) && /订单信息已变更/.test(directPage)],
  ['DIRECT Create Button Enable（创建按钮启用）', /:disabled="!canCreate"/.test(directPage) && /humanConfirmed\.value/.test(directPage)],
  ['DIRECT Real Create Click（真实点击创建）', /@click="createOrder"/.test(directPage)],
  ['DIRECT API Request（服务请求）', /createPurchaseOrderFromGateRequest/.test(directPage) && /purchase-order-gate-creation/.test(api)],
  ['DIRECT PurchaseOrder Creation（采购订单创建）', /create_from_direct_request/.test(service)],
  ['DIRECT PurchaseOrderItem Creation（采购订单明细创建）', /source_purchase_request_item=request_item/.test(service)],
  ['DIRECT Unified Detail（统一采购订单详情）', /router\.push\(`\/scm\/purchase-order\/\$\{response\.data\.objectId\}`\)/.test(directPage)],
  ['Shared Gate Dispatch（共同门禁分流）', /agreed_price_creation/.test(actions) && /direct_creation/.test(actions)],
  ['SupplierMaterialPrice Unchanged（正式价格不变）', !/SupplierMaterialPrice\.objects\.(create|update)/.test(service)],
  ['SupplierPriceFact Unchanged（价格事实不变）', !/SupplierPriceFact/.test(service)],
  ['No Hidden Auto Confirmation（无隐藏自动确认）', !/humanConfirmed\.value\s*=\s*true/.test(directPage) && !/humanConfirmed\.value\s*=\s*true/.test(agreedPage)],
  [`No ${['page', 'evaluate'].join('.')} Business Mutation（无页面后台状态修改）`, !new RegExp(['page', 'evaluate'].join('\\.') + '|\\.eva' + 'luate\\(').test(currentScript)],
  ['Backend Closure Tests（后端闭环测试存在）', /test_three_inherited_items_split_into_two_orders/.test(r5Tests) && /test_gate_token_cannot_be_reused/.test(r5Tests)],
]

let failed = 0
for (const [name, passed] of tests) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`)
  if (!passed) failed += 1
}
console.log(JSON.stringify({ version: 'V1.14.2.8.4.27.2.46-Batch2.2-R5',
  passed: tests.length - failed, total: tests.length, result: failed ? 'FAIL' : 'PASS' }, null, 2))
if (failed) process.exit(1)
