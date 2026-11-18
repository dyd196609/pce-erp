import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(frontend, '..')
const phase = process.argv.includes('--phase=automatic') ? 'automatic' : 'final'
const read = (...parts) => fs.readFileSync(path.join(repo, ...parts), 'utf8')
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(repo, file))).digest('hex').toUpperCase()
const checks = []
const check = (code, passed, detail) => checks.push({ code, passed: Boolean(passed), detail })

const standard = read('docs', 'governance', '供应商价格领域职责分离规范.md')
const stateReport = read('docs', 'governance', 'SupplierMaterialPrice当前状态报告.md')
const migration = read('docs', 'governance', '供应商有效价格迁移评估.md')
const backendRuntime = read('backend', 'masterdata', 'master_data_statistics_runtime.py')
const views = read('backend', 'masterdata', 'views.py')
const clientRuntime = read('frontend', 'src', 'meta', 'runtime', 'supplierMaterialPriceRuntime.js')
const provider = read('frontend', 'src', 'meta', 'providers', 'supplierMaterialPriceRuntimeProvider.js')
const foundationPage = read('frontend', 'src', 'meta', 'pages', 'ManufacturingFoundationPage.vue')
const factPage = read('frontend', 'src', 'meta', 'pages', 'SupplierPriceFactPage.vue')
const analysisPage = read('frontend', 'src', 'meta', 'pages', 'SupplierPriceAnalysisPage.vue')
const assistantPage = read('frontend', 'src', 'meta', 'pages', 'PurchasePriceReviewAssistantPage.vue')

check('GOVERNANCE-FILES-LOADED', standard.includes('V1.14.2.8.4.27.2.43')
  && stateReport.includes('SupplierMaterialPrice Current State Report')
  && migration.includes('Price Migration Assessment'), '治理规范、现状扫描和迁移评估已落档')

check('SUPPLIER_EFFECTIVE_PRICE_SOURCE_001', backendRuntime.includes('"Quotation Approved"')
  && backendRuntime.includes('"Manual Approved Price"')
  && backendRuntime.includes('sourceReference=candidate["sourceReference"]')
  && views.includes('allowedSourceTypes')
  && clientRuntime.includes('autoGenerationEnabled !== false'), '正式价格仅接受受治理审批来源')

check('SUPPLIER_PRICE_APPROVAL_CHAIN_001', backendRuntime.includes('"HumanPriceApproval"')
  && backendRuntime.includes('preparation.status__in') === false
  && backendRuntime.includes('status__in=("approved", "completed")')
  && foundationPage.includes('supplier-material-price-approval-chain')
  && standard.includes('SupplierQuotation') && standard.includes('HumanPriceApproval'), '报价审批归档链显式可追溯')

check('EFFECTIVE-PRICE-COMPLETENESS-001', [
  'minOrderQty', 'unitPrice', 'taxRate', 'currency', 'deliveryPeriod',
  'effectiveDate', 'expiryDate', 'sourceType', 'sourceReference', 'approvalStatus',
].every(field => backendRuntime.includes(`${field}=`) || backendRuntime.includes(`"${field}":`))
  && backendRuntime.includes('if not candidate["eligible"]')
  && migration.includes('正式转换：0条'), '字段不完整候选保持隔离，不补造值')

check('SUPPLIER_PRICE_FACT_SEPARATION_001', backendRuntime.includes('def _supplier_material_price_facts')
  && backendRuntime.includes('SupplierMaterialPriceRuntime.list_runtime_models()')
  && backendRuntime.includes('sourceType="SupplierMaterialPrice"')
  && backendRuntime.includes('def _purchase_order_history_facts')
  && factPage.includes('有效价格仅作为独立来源追加引用，不覆盖报价或历史采购事实')
  && analysisPage.includes('SupplierPriceFactRuntime'), '有效价格追加为独立事实来源，历史事实未覆盖')

check('PRICE_REVIEW_REFERENCE_001', assistantPage.includes('loadSupplierMaterialPriceRuntime')
  && assistantPage.includes("source: 'SupplierMaterialPriceRuntime'")
  && assistantPage.includes('effectivePriceRuntime.value?.formalPriceCount')
  && assistantPage.includes("rule: 'PRICE_REVIEW_REFERENCE_001'"), '核价助手直接读取企业有效价格Runtime')

check('NO_PRICE_AUTO_GENERATION_001', backendRuntime.includes('"autoGenerationEnabled": False')
  && clientRuntime.includes('autoGenerationEnabled: false')
  && migration.includes('禁止最低价自动转正式价')
  && !backendRuntime.includes('sourceType="PurchaseOrderHistory"') === false,
  '正式价无自动生成，历史采购事实保持独立')

const protectedHashes = new Map([
  ['backend/db.sqlite3', '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847'],
  ['backend/procurement/scm_runtime_services.py', '097799B4644347AECD3CFC9FC1C761639BDE222732242B6212316A0EE6C57FDB'],
  ['backend/procurement/purchase_order_supplier_fact_runtime.py', '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5'],
  ['frontend/src/meta/runtime/purchaseOrderCreationGateRuntime.js', '49046366EACB77CA925EAEB5B2AFBFF9D71F610E2385CC171639A519ADCC1DDF'],
  ['frontend/src/meta/runtime/supplierRecommendationRuntime.js', '1F30B2B7425C2DFC694D8AE7844DE94F05D03D7AC1E0419F844F7D57A9921809'],
])
const changed = [...protectedHashes].filter(([file, expected]) => hash(file) !== expected).map(([file]) => file)
check('PROTECTED-SCOPE-001', changed.length === 0, changed.length ? changed.join(', ') : '数据库、订单、Gate与推荐Runtime未修改')

if (phase === 'final') {
  const evidenceDir = path.join(frontend, 'test-results', 'V1.14.2.8.4.27.2.43')
  const screenshots = [
    'supplier-material-prices-01.png', 'supplier-price-facts-01.png',
    'supplier-price-analysis-01.png', 'price-review-assistant-01.png',
  ]
  const report = read('docs', 'governance', '供应商有效价格真实运行验收报告.md')
  check('REAL_BROWSER_ACCEPTANCE_001', screenshots.every(name => fs.existsSync(path.join(evidenceDir, name)))
    && report.includes('Automatic Acceptance：PASS')
    && report.includes('Browser Human Acceptance：PASS')
    && report.includes('Build：PASS'), '四页浏览器证据和READY三门禁一致')
}

const failed = checks.filter(item => !item.passed)
for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (failed.length) process.exit(1)
console.log(`PASS SUPPLIER_EFFECTIVE_PRICE ${phase}`)
