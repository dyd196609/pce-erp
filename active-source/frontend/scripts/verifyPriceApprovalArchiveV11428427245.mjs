import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const repo = path.resolve(frontend, '..')
const phase = process.argv.includes('--phase=final') ? 'final' : 'automatic'
const read = (...parts) => fs.readFileSync(path.join(repo, ...parts), 'utf8')
const checks = []
const check = (code, passed, detail) => checks.push({ code, passed: Boolean(passed), detail })

const governanceFiles = [
  'PCE-ERP智能化开发总纲.md',
  'PCE智能化开发增量接入规范.md',
  '供应商价格领域职责分离规范.md',
  '价格事实治理规范.md',
  '供应商报价确认闭环扫描报告.md',
]
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(repo, 'docs', 'governance', name)))
const backend = read('backend', 'masterdata', 'master_data_statistics_runtime.py')
const views = read('backend', 'masterdata', 'views.py')
const urls = read('backend', 'masterdata', 'urls.py')
const api = read('frontend', 'src', 'api', 'enterpriseMasterData.js')
const provider = read('frontend', 'src', 'meta', 'providers', 'supplierMaterialPriceRuntimeProvider.js')
const runtime = read('frontend', 'src', 'meta', 'runtime', 'supplierMaterialPriceRuntime.js')
const page = read('frontend', 'src', 'meta', 'pages', 'PurchasePriceReviewAssistantPage.vue')

check('PRICE_APPROVAL_RESULT_SCAN_001', governanceLoaded
  && backend.includes('def record_approval_result')
  && backend.includes('"objectType": "PriceApprovalResult"')
  && backend.includes('"ACCEPT": "接受报价"')
  && backend.includes('"REJECT": "拒绝报价"')
  && backend.includes('"RENEGOTIATE": "重新议价"')
  && page.includes('已完成人工确认的核价结果'), '核价结果扫描、三种人工结果与既有页面接入')

const officialFields = [
  'priceNo', 'supplierId', 'materialId', 'unitPrice', 'currency', 'taxRate',
  'minPurchaseQty', 'deliveryPeriod', 'effectiveDate', 'expiryDate', 'sourceType',
  'sourceId', 'confirmedBy', 'confirmedAt', 'status',
]
check('EFFECTIVE_PRICE_ARCHIVE_001', backend.includes('def _archive_approval_result')
  && officialFields.every(field => backend.includes(field))
  && backend.includes('sourceType="SupplierQuotationConfirmed"')
  && backend.includes('status="ACTIVE"')
  && backend.includes('PRICE_APPROVAL_RESULT_SOURCE_CHANGED')
  && runtime.includes("'priceId', 'priceNo'")
  && provider.includes('batchArchiveSupplierMaterialPrices'), '完整字段、权威报价重读与正式ACTIVE会话归档')

check('BATCH_PRICE_CONFIRMATION_001', backend.includes('def batch_archive')
  && backend.includes('for result_id in ordered_ids:')
  && backend.includes('except ValueError as exc:')
  && backend.includes('"successCount"')
  && backend.includes('"failureCount"')
  && views.includes('SupplierMaterialPriceBatchArchiveView')
  && urls.includes('batch-archive')
  && api.includes('batchArchiveSupplierMaterialPrices')
  && page.includes('批量生成有效价格'), '人工多选、逐条校验、失败隔离与批次汇总')

check('PRICE_FACT_ISOLATION_001', backend.includes('if price.factOrigin == "SESSION_CONFIRMED"')
  && backend.includes('persisted=False')
  && backend.includes('"sessionPersistence": "SERVER_MEMORY_ONLY"')
  && backend.includes('"businessProgressWriteCount": 0')
  && !urls.includes('purchase-order')
  && !urls.includes('gate'), '历史事实排除会话归档，采购订单与Gate未接入')

if (phase === 'final') {
  const evidenceDir = path.join(frontend, 'test-results', 'V1.14.2.8.4.27.2.45')
  const screenshots = [
    'price-review-assistant-batch-confirmed.png',
    'supplier-material-prices-archived.png',
    'supplier-price-facts-unchanged.png',
    'supplier-price-analysis-normal.png',
  ]
  const reportPath = path.join(repo, 'docs', 'governance', '核价结果批量确认与有效价格正式归档验收报告.md')
  const report = fs.existsSync(reportPath) ? fs.readFileSync(reportPath, 'utf8') : ''
  check('REAL_BROWSER_ACCEPTANCE_001', screenshots.every(name => fs.existsSync(path.join(evidenceDir, name)))
    && report.includes('Browser Human Acceptance: PASS')
    && report.includes('Real Browser Evidence: PASS')
    && report.includes('Business Write Count: 0'), '四页面真实浏览器截图与零业务写入报告')
} else {
  check('REAL_BROWSER_ACCEPTANCE_001', page.includes('data-acceptance-id="batch-price-confirmation"')
    && page.includes('data-acceptance-id="effective-price-count"'), '真实浏览器验收锚点已就绪（final阶段校验截图）')
}

for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (checks.some(item => !item.passed)) process.exit(1)
console.log(`PASS V1.14.2.8.4.27.2.45 ${phase}`)
