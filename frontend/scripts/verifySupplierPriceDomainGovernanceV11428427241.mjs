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

const canonicalIntegration = read('docs', 'governance', 'PCE智能化增量接入规范.md')
const compatibilityIntegration = read('docs', 'governance', 'PCE智能化开发增量接入规范.md')
const standard = read('docs', 'governance', '供应商价格领域职责分离规范.md')
const scan = read('docs', 'governance', '价格领域扫描报告.md')
const registry = read('frontend', 'src', 'meta', 'master-data', 'masterDataRegistry.js')
const foundationPage = read('frontend', 'src', 'meta', 'pages', 'ManufacturingFoundationPage.vue')
const factPage = read('frontend', 'src', 'meta', 'pages', 'SupplierPriceFactPage.vue')
const assistantPage = read('frontend', 'src', 'meta', 'pages', 'PurchasePriceReviewAssistantPage.vue')
const factRuntime = read('backend', 'masterdata', 'master_data_statistics_runtime.py')

check('GOVERNANCE-FILES-LOADED', canonicalIntegration.includes('PCE-INTELLIGENCE-INTEGRATION-001')
  && compatibilityIntegration.includes('唯一正文') && standard.includes('PRICE-DOMAIN-SEPARATION-001'), '治理正文与兼容入口有效')

check('PRICE-DOMAIN-SEPARATION-001', ['MaterialSupplierRelation', 'SupplierMaterialPrice', 'SupplierPriceFact']
  .every(term => standard.includes(term))
  && standard.includes('哪些供应商可以供应该物料')
  && standard.includes('当前企业认可的供应价格')
  && standard.includes('过去实际价格'), '三个价格领域对象职责独立')

check('PRICE-SOURCE-TRACE-001', standard.includes('sourceReference')
  && factRuntime.includes('sourceReference=')
  && factRuntime.includes('def _supplier_material_price_facts')
  && factRuntime.includes('return []')
  && scan.includes('NOT_GOVERNED'), '正式来源可追溯，缺失来源不补造')

check('SUPPLIER-MATERIAL-PRICE-POSITION-001', registry.includes("metadataVersion: 'V1.14.2.8.4.27.2.41'")
  && ['effectiveDate', 'expiryDate', 'paymentTerms'].every(term => registry.includes(`field('${term}'`))
  && foundationPage.includes('data-price-domain-object')
  && foundationPage.includes('NOT_APPROVED_EXECUTION_SOURCE'), '有效价格Metadata和页面边界已原位补充')

check('PRICE-FACT-READONLY-001', factPage.includes('data-price-maintenance-enabled="false"')
  && factPage.includes('data-pce-action-policy="view"')
  && registry.includes("pageKind: 'fact'")
  && registry.includes('MASTER_DATA_PAGE_ACTION_POLICIES.fact'), '价格事实保持只读')

check('PRICE-INTELLIGENCE-CHAIN-001', ['MaterialSupplierRelation', 'SupplierMaterialPrice', 'SupplierPriceFact', 'SupplierQuotation']
  .every(term => assistantPage.includes(`objectCode: '${term}'`))
  && assistantPage.includes('price-intelligence-input-chain')
  && assistantPage.includes('未接入正式服务端事实，不参与本次核价')
  && assistantPage.includes('automaticPurchaseOrderCreation === false'), '四类输入显式展示且仅供参考')

const forbiddenRoots = [
  ['frontend', 'src', 'runtime'], ['frontend', 'src', 'schema'],
  ['backend', 'runtime'], ['backend', 'services'],
]
check('NO-DUPLICATE-PRICE-MODEL-001', forbiddenRoots.every(parts => !exists(...parts))
  && scan.includes('新价格体系/Runtime/Metadata：`NO`'), '未创建平行价格或智能框架')

const protectedHashes = new Map([
  ['backend/db.sqlite3', '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847'],
  ['backend/procurement/scm_runtime_services.py', '097799B4644347AECD3CFC9FC1C761639BDE222732242B6212316A0EE6C57FDB'],
  ['backend/procurement/purchase_order_supplier_fact_runtime.py', '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5'],
  ['frontend/src/meta/runtime/purchaseOrderCreationGateRuntime.js', '49046366EACB77CA925EAEB5B2AFBFF9D71F610E2385CC171639A519ADCC1DDF'],
  ['frontend/src/meta/runtime/supplierRecommendationRuntime.js', '1F30B2B7425C2DFC694D8AE7844DE94F05D03D7AC1E0419F844F7D57A9921809'],
  ['backend/masterdata/master_data_statistics_runtime.py', '5BB3C7E2B18AA89D104D24CA67903D6642ED4A22B5373AE05DCD2674F58D9D4A'],
  ['backend/masterdata/material_supplier_relation_runtime.py', '5F3DB7BEC0AA9B3114B5EB775D0CC186FADEEB351BA03B462BCFE5FABB07ED0D'],
])
const changed = [...protectedHashes].filter(([file, expected]) => hash(file) !== expected).map(([file]) => file)
check('BUSINESS-REGRESSION-001', changed.length === 0, changed.length ? changed.join(', ') : '数据库、订单、Gate、推荐和服务端Runtime未修改')

if (phase === 'final') {
  const evidenceDir = path.join(frontend, 'test-results', 'V1.14.2.8.4.27.2.41')
  const screenshots = exists('frontend', 'test-results', 'V1.14.2.8.4.27.2.41')
    ? fs.readdirSync(evidenceDir).filter(name => name.endsWith('.png')) : []
  const report = read('docs', 'governance', '供应商价格领域真实运行验收报告.md')
  check('REAL-BROWSER-EVIDENCE-001', screenshots.length >= 4
    && report.includes('Browser Human Acceptance: PASS')
    && report.includes('Business Write Count：0'), `${screenshots.length} screenshots`)
}

const failed = checks.filter(item => !item.passed)
for (const item of checks) console.log(`${item.passed ? 'PASS' : 'FAIL'} ${item.code} ${item.detail}`)
if (failed.length) process.exit(1)
console.log(`PASS SUPPLIER_PRICE_DOMAIN_GOVERNANCE ${phase}`)
