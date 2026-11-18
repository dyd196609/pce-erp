import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(frontend, '..')
const phase = process.argv.includes('--phase=automatic') ? 'automatic' : 'final'
const read = (...parts) => fs.readFileSync(path.join(repo, ...parts), 'utf8')
const exists = (...parts) => fs.existsSync(path.join(repo, ...parts))
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(repo, file))).digest('hex').toUpperCase()
const checks = []
const check = (code, passed, detail) => checks.push({ code, passed: Boolean(passed), detail })

const standard = read('docs', 'governance', '供应商价格领域职责分离规范.md')
const scan = read('docs', 'governance', 'SupplierMaterialPrice来源扫描报告.md')
const migration = read('docs', 'governance', '价格数据迁移评估.md')
const backendRuntime = read('backend', 'masterdata', 'master_data_statistics_runtime.py')
const views = read('backend', 'masterdata', 'views.py')
const urls = read('backend', 'masterdata', 'urls.py')
const api = read('frontend', 'src', 'api', 'enterpriseMasterData.js')
const clientRuntime = read('frontend', 'src', 'meta', 'runtime', 'supplierMaterialPriceRuntime.js')
const provider = read('frontend', 'src', 'meta', 'providers', 'supplierMaterialPriceRuntimeProvider.js')
const registry = read('frontend', 'src', 'meta', 'master-data', 'masterDataRegistry.js')
const foundationPage = read('frontend', 'src', 'meta', 'pages', 'ManufacturingFoundationPage.vue')
const factPage = read('frontend', 'src', 'meta', 'pages', 'SupplierPriceFactPage.vue')
const assistantPage = read('frontend', 'src', 'meta', 'pages', 'PurchasePriceReviewAssistantPage.vue')
const legacyStore = read('frontend', 'src', 'meta', 'manufacturing', 'manufacturingFoundationStore.js')

check('GOVERNANCE-FILES-LOADED', standard.includes('V1.14.2.8.4.27.2.42')
  && scan.includes('SupplierMaterialPrice Source Scan Report')
  && migration.includes('Price Data Migration Assessment'), '治理规范、来源扫描和迁移评估已读取并落档')

check('PRICE_SOURCE_RUNTIME-001', backendRuntime.includes('class SupplierMaterialPriceRuntime')
  && backendRuntime.includes('APPROVAL_WORKFLOW_MANAGED')
  && views.includes('class SupplierMaterialPriceFactsView')
  && urls.includes('supplier-material-prices/runtime/facts')
  && api.includes('supplierMaterialPrices()')
  && provider.includes('loadSupplierMaterialPriceRuntime')
  && foundationPage.includes("return supplierMaterialPriceRuntime.value?.rows || []")
  && foundationPage.includes("if (isSupplierMaterialPriceRuntimePage.value) return 'SupplierMaterialPriceRuntime'"),
  '页面通过Provider读取既有服务端SupplierMaterialPriceRuntime')

const requiredFields = [
  'supplierId', 'supplierCode', 'materialId', 'materialCode', 'minOrderQty',
  'unitPrice', 'taxRate', 'currency', 'deliveryPeriod', 'effectiveDate',
  'expiryDate', 'status', 'sourceType', 'sourceReference', 'approvalStatus',
]
check('SUPPLIER_MATERIAL_PRICE_GOVERNANCE-001', requiredFields.every(field => (
  backendRuntime.includes(`${field}:`) && clientRuntime.includes(`'${field}'`)
)) && [
  'supplierDisplay', 'materialDisplay', 'minOrderQty', 'unitPrice', 'taxRate',
  'currency', 'deliveryPeriod', 'effectiveDate', 'expiryDate', 'statusLabel',
  'sourceType', 'sourceReference', 'approvalStatusLabel',
].every(field => registry.includes(`field('${field}'`))
  && clientRuntime.includes('SupplierMaterialPrice governed contract unavailable')
  && foundationPage.includes('编辑价格（进入核价流程）'), '完整契约、受控维护入口和运行校验已建立')

check('PRICE_REFERENCE_CHAIN-001', [
  'SupplierPriceFactRuntime', 'PurchasePriceReviewAssistant', 'PurchaseOrderPriceSourceReference',
].every(term => backendRuntime.includes(term) && clientRuntime.includes(term))
  && foundationPage.includes('supplierMaterialPriceReferenceChain')
  && factPage.includes('supplier-price-fact-intelligence-reference')
  && ['历史价格分析', '价格趋势分析', '价格异常检测', '核价智能辅助'].every(term => factPage.includes(term))
  && assistantPage.includes('price-intelligence-input-chain'), '价格事实、分析、核价和订单来源引用关系透明')

check('PRICE-DATA-MIGRATION-ASSESSMENT-001', ['smp-001', 'smp-002', 'smp-003'].every(id => legacyStore.includes(id))
  && migration.includes('ISOLATED')
  && backendRuntime.includes('return []')
  && backendRuntime.includes('ISOLATED_INCOMPLETE')
  && clientRuntime.includes('isolatedLegacyCount: 3'), '3条早期测试数据和不完整审批候选保持隔离')

check('NO_DUPLICATE_PRICE_MODEL-001', scan.includes('原位扩展既有`SupplierMaterialPriceRuntime`')
  && !exists('frontend', 'src', 'runtime')
  && !exists('frontend', 'src', 'schema')
  && !exists('backend', 'runtime')
  && !exists('backend', 'services'), '未创建第二套价格、Runtime、Metadata或页面框架')

const protectedHashes = new Map([
  ['backend/db.sqlite3', '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847'],
  ['backend/procurement/scm_runtime_services.py', '097799B4644347AECD3CFC9FC1C761639BDE222732242B6212316A0EE6C57FDB'],
  ['backend/procurement/purchase_order_supplier_fact_runtime.py', '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5'],
  ['frontend/src/meta/runtime/purchaseOrderCreationGateRuntime.js', '49046366EACB77CA925EAEB5B2AFBFF9D71F610E2385CC171639A519ADCC1DDF'],
  ['frontend/src/meta/runtime/supplierRecommendationRuntime.js', '1F30B2B7425C2DFC694D8AE7844DE94F05D03D7AC1E0419F844F7D57A9921809'],
])
const protectedChanges = [...protectedHashes].filter(([file, expected]) => hash(file) !== expected).map(([file]) => file)
check('PROTECTED-SCOPE-001', protectedChanges.length === 0,
  protectedChanges.length ? protectedChanges.join(', ') : '数据库、PurchaseOrder、Gate和推荐Runtime未修改')

if (phase === 'final') {
  const evidenceDir = path.join(frontend, 'test-results', 'V1.14.2.8.4.27.2.42')
  const requiredScreenshots = [
    'supplier-material-prices-01.png',
    'supplier-price-facts-01.png',
    'supplier-price-analysis-01.png',
    'price-review-assistant-01.png',
  ]
  const report = read('docs', 'governance', '价格领域运行透明化真实运行验收报告.md')
  check('REAL_BROWSER_ACCEPTANCE-001', requiredScreenshots.every(name => fs.existsSync(path.join(evidenceDir, name)))
    && report.includes('Browser Human Acceptance：PASS')
    && report.includes('Automatic Acceptance：PASS')
    && report.includes('Build：PASS'), '四个指定页面具有真实浏览器证据且三门禁一致')
}

const failed = checks.filter(item => !item.passed)
for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (failed.length) process.exit(1)
console.log(`PASS PRICE_DOMAIN_RUNTIME_TRANSPARENT ${phase}`)
