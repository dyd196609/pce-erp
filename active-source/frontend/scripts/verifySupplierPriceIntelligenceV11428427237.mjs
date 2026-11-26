import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const failures = []

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

function requireTokens(relativePath, tokens, rule) {
  const content = read(relativePath)
  for (const token of tokens) {
    if (!content.includes(token)) failures.push(`${rule}: ${relativePath} missing ${token}`)
  }
}

function sha256(relativePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(path.join(root, relativePath))).digest('hex').toUpperCase()
}

requireTokens('backend/masterdata/master_data_statistics_runtime.py', [
  'class SupplierPriceFactRuntime', 'intelligence_analysis', 'lowestPurchasePrice',
  'latestPurchasePrice', 'averagePurchasePrice', 'priceChangeRatio', 'supplierComparisons',
  'PRICE_INCREASE_20', 'PRICE_DECREASE_20', 'PRICE_LOW_DEVIATION_30',
  'PRICE_HIGH_DEVIATION_30', 'PRICE_STALE_180_DAYS', 'READ_ONLY_REFERENCE',
  '"automaticSupplierSelection": False', '"automaticPriceDecision": False',
  '"automaticPurchaseOrderCreation": False',
], 'PRICE-HISTORY-ANALYSIS-001')

requireTokens('backend/masterdata/views.py', [
  '"intelligenceAnalysis": intelligence_analysis', '"intelligenceRuleVersion"',
  '"analysisMode"', '"autoPriceApprovalEnabled": False',
  '"autoSupplierSelectionEnabled": False',
], 'PRICE-INTELLIGENCE-SOURCE-001')

requireTokens('frontend/src/meta/pages/SupplierPriceAnalysisPage.vue', [
  '供应商价格分析', 'SupplierPriceFactRuntime', 'FoundationMetadataList',
  'price-fact-summary', 'price-history-list', 'price-history-trend',
  'supplier-price-comparison', 'price-anomaly-region',
  'PRICE-INTELLIGENCE-SOURCE-001', 'PRICE-HISTORY-ANALYSIS-001',
  'PRICE-COMPARISON-001', 'PRICE-NO-AUTO-DECISION-001',
  'observability?.register?.(observabilityProvider)',
  'observability?.unregister?.(observabilityProvider)',
], 'REAL-BROWSER-EVIDENCE-001')

requireTokens('frontend/src/meta/master-data/masterDataRegistry.js', [
  "collection: 'supplierPriceAnalysisHistory'", "collection: 'supplierPriceComparisons'",
  "filterType: 'remote-select'", "pageKind: 'fact'",
], 'PRICE-COMPARISON-001')

requireTokens('frontend/src/meta/runtime/supplierPriceFactRuntime.js', [
  'normalizeAnalysis', 'READ_ONLY_REFERENCE', 'automaticSupplierSelection',
  'automaticPriceDecision', 'automaticPurchaseOrderCreation',
], 'PRICE-NO-AUTO-DECISION-001')

requireTokens('frontend/src/router/index.js', [
  "path: 'foundation/erp/supplier-price-analysis'", "'foundation-supplier-price-analysis'",
], 'PRICE-INTELLIGENCE-SOURCE-001')

requireTokens('docs/governance/供应商价格事实智能分析能力清单.md', [
  'SupplierPriceIntelligenceCapabilityInventory', '不新建 Metadata、Runtime、Registry、Schema',
], 'PRICE-INTELLIGENCE-SOURCE-001')
requireTokens('docs/governance/供应商价格事实质量报告.md', [
  'SupplierPriceFactQualityReport', '业务写入为 `0`',
], 'PRICE-HISTORY-ANALYSIS-001')
requireTokens('docs/governance/供应商价格事实智能分析验收报告.md', [
  'Automatic Acceptance：PASS', 'Browser Human Acceptance：PASS',
  'Build：PASS', 'Ready Gate：PASS', 'REAL-BROWSER-EVIDENCE-001',
  'SUPPLIER_PRICE_INTELLIGENCE_ANALYSIS_READY',
], 'REAL-BROWSER-EVIDENCE-001')

const evidenceDirectory = path.join(root, 'docs/governance/evidence/V1.14.2.8.4.27.2.37')
const screenshots = fs.readdirSync(evidenceDirectory)
  .filter(file => file.endsWith('.png'))
  .map(file => path.join(evidenceDirectory, file))
if (screenshots.length < 5 || screenshots.some(file => fs.statSync(file).size <= 0)) {
  failures.push('REAL-BROWSER-EVIDENCE-001: screenshot evidence incomplete')
}

const protectedHashes = {
  'backend/db.sqlite3': '634DE03199C0BD5E3140437A7CAC3E2DA1BE327B857C62553E4D4005EE19C847',
  'backend/masterdata/models.py': 'B54F4CC0E9EEFE0F3C4709B645174439845A08006C7FEAD99C68584A8B069959',
  'backend/procurement/models.py': '7E80989AEA1018EF1224E110E4E6C782445E5A891AD3AC00EFE99B8393A6FE98',
  'backend/masterdata/material_master_runtime.py': 'EF81D76449EE14DB02DD4C4A91721C9ABCF8E7167AA45565A820A696BBF8CBF6',
  'backend/masterdata/supplier_master_runtime.py': 'D1C9EB2D4E8A138C861627322FB9B3EB3569D7AA5406D293018A1E9D2F627DC7',
  'backend/masterdata/material_supplier_relation_runtime.py': '5F3DB7BEC0AA9B3114B5EB775D0CC186FADEEB351BA03B462BCFE5FABB07ED0D',
  'backend/procurement/purchase_order_supplier_fact_runtime.py': '05618A86CF6F57F4D1919F65BFACFAFC6DDD1430AE7474C0715C064FE188DAE5',
}
for (const [file, expected] of Object.entries(protectedHashes)) {
  if (sha256(file) !== expected) failures.push(`Forbidden asset changed: ${file}`)
}

if (failures.length) {
  console.error('Supplier Price Intelligence V2.37: FAIL')
  failures.forEach(failure => console.error(`- ${failure}`))
  process.exit(1)
}

console.log('PRICE-INTELLIGENCE-SOURCE-001: PASS')
console.log('PRICE-HISTORY-ANALYSIS-001: PASS')
console.log('PRICE-COMPARISON-001: PASS')
console.log('PRICE-NO-AUTO-DECISION-001: PASS')
console.log('REAL-BROWSER-EVIDENCE-001: PASS')
console.log('Database Changed: NO')
console.log('Business Write Count: 0')
