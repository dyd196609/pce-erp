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

const scan = read('docs', 'governance', '供应商报价确认闭环扫描报告.md')
const domain = read('docs', 'governance', '供应商价格领域职责分离规范.md')
const backend = read('backend', 'masterdata', 'master_data_statistics_runtime.py')
const views = read('backend', 'masterdata', 'views.py')
const urls = read('backend', 'masterdata', 'urls.py')
const api = read('frontend', 'src', 'api', 'enterpriseMasterData.js')
const provider = read('frontend', 'src', 'meta', 'providers', 'supplierMaterialPriceRuntimeProvider.js')
const assistant = read('frontend', 'src', 'meta', 'pages', 'PurchasePriceReviewAssistantPage.vue')
const effectivePage = read('frontend', 'src', 'meta', 'pages', 'ManufacturingFoundationPage.vue')

check('GOVERNANCE-FILES-LOADED', scan.includes('Price Review Confirmation Scan Report: PASS')
  && domain.includes('V1.14.2.8.4.27.2.44'), '报价确认扫描与价格职责规则已落档')

check('PRICE_CONFIRMATION_CHAIN_001', backend.includes('def confirm_quotation')
  && backend.includes('confirmationResult')
  && backend.includes('ACCEPT_QUOTATION')
  && assistant.includes("confirmDecision('REJECT_QUOTATION')")
  && assistant.includes("confirmDecision('REQUEST_RENEGOTIATION')")
  && assistant.includes('确认采用报价'), '人工接受、拒绝、重新议价三结果存在')

check('SUPPLIER_MATERIAL_PRICE_GENERATION_001', backend.includes('sourceType="SupplierQuotationConfirmed"')
  && backend.includes('sourceReference=quotation.quotation_no')
  && backend.includes('confirmedBy=confirmed_by')
  && backend.includes('confirmedAt=confirmed_at')
  && backend.includes('status="ACTIVE"')
  && urls.includes('confirm-quotation')
  && api.includes('confirmSupplierQuotationPrice')
  && provider.includes('confirmSupplierQuotationPrice'), '复用现有Runtime并保留报价来源与确认事实')

check('AUTHORITATIVE-QUOTATION-001', backend.includes('matched = None')
  && backend.includes('_quotation_runtime_lines()')
  && backend.includes('SupplierQuotation:')
  && !backend.includes('unitPrice=payload'), '供应商、物料、价格、币种由服务端报价事实重读')

check('PRICE_FACT_SEPARATION_001', backend.includes('factOrigin="SESSION_CONFIRMED"')
  && backend.includes('if price.factOrigin == "SESSION_CONFIRMED"')
  && assistant.includes('当前企业有效价格')
  && effectivePage.includes('sessionConfirmedPriceCount'), '会话有效价格与历史事实分离')

check('NO_AUTO_PRICE_GENERATION_001', backend.includes('"autoGenerationEnabled": False')
  && backend.includes('persisted=False')
  && backend.includes('SERVER_MEMORY_ONLY')
  && scan.includes('拒绝报价、要求重新议价均不调用生成接口'), '无自动生成且无数据库业务写入')

check('NO_DUPLICATE_FRAMEWORK_001', !scan.includes('新建报价审批中心')
  && views.includes('SupplierMaterialPriceRuntime.confirm_quotation')
  && provider.includes('loadSupplierMaterialPriceRuntime'), '沿用既有Runtime、Provider和页面')

const protectedHashes = new Map([
  ['backend/db.sqlite3', '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847'],
  ['backend/procurement/scm_runtime_services.py', '097799B4644347AECD3CFC9FC1C761639BDE222732242B6212316A0EE6C57FDB'],
  ['backend/procurement/purchase_order_supplier_fact_runtime.py', '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5'],
  ['frontend/src/meta/runtime/purchaseOrderCreationGateRuntime.js', '49046366EACB77CA925EAEB5B2AFBFF9D71F610E2385CC171639A519ADCC1DDF'],
  ['frontend/src/meta/runtime/supplierRecommendationRuntime.js', '1F30B2B7425C2DFC694D8AE7844DE94F05D03D7AC1E0419F844F7D57A9921809'],
])
const changed = [...protectedHashes].filter(([file, expected]) => hash(file) !== expected).map(([file]) => file)
check('PROTECTED-SCOPE-001', changed.length === 0, changed.length ? changed.join(', ') : '数据库、采购订单、Gate、推荐Runtime未修改')

if (phase === 'final') {
  const evidenceDir = path.join(frontend, 'test-results', 'V1.14.2.8.4.27.2.44')
  const screenshots = [
    'price-review-assistant-confirmed.png',
    'supplier-material-prices-confirmed.png',
    'supplier-price-facts-separated.png',
    'supplier-price-analysis-separated.png',
  ]
  const report = read('docs', 'governance', '供应商报价确认与有效价格真实运行验收报告.md')
  check('REAL_BROWSER_ACCEPTANCE_001', screenshots.every(name => fs.existsSync(path.join(evidenceDir, name)))
    && report.includes('Automatic Acceptance：PASS')
    && report.includes('Browser Human Acceptance：PASS')
    && report.includes('Build：PASS')
    && report.includes('SupplierQuotationConfirmed')
    && report.includes('事实总量保持 405 条'), '四页面浏览器证据与READY三门禁一致')
}

const failed = checks.filter(item => !item.passed)
for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (failed.length) process.exit(1)
console.log(`PASS SUPPLIER_QUOTE_CONFIRMATION_PRICE ${phase}`)
