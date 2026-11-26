import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import process from 'node:process'
import {
  createPurchasePriceDecisionContext,
  confirmPurchasePriceDecisionContext,
} from '../src/meta/process/scm/priceApproval/priceReferenceContext.js'

const frontendRoot = process.cwd()
const root = path.resolve(frontendRoot, '..')
const failures = []
const read = file => fs.readFileSync(path.join(root, file), 'utf8')

function requireTokens(file, tokens, rule) {
  const content = read(file)
  for (const token of tokens) if (!content.includes(token)) failures.push(`${rule}: ${file} missing ${token}`)
}

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex').toUpperCase()
}

requireTokens('backend/masterdata/master_data_statistics_runtime.py', [
  'class PriceReviewRuleRuntime', 'PurchasePriceReviewContext', 'PurchasePriceDecisionContext',
  'QUOTE_ABOVE_LATEST_20', 'QUOTE_BELOW_LOWEST_30', 'QUOTE_PEER_AVERAGE_DEVIATION_20',
  'HISTORY_REFERENCE_INSUFFICIENT', 'SUPPLIER_COMPARISON_INSUFFICIENT',
  'ASSISTIVE_PROMPT_ONLY', '"automaticPriceDecision": False',
  '"automaticSupplierSelection": False', '"automaticPriceModification": False',
  '"automaticPurchaseOrderCreation": False', '"businessProgressWriteCount": 0',
], 'PRICE-REVIEW-CONTEXT-001')

requireTokens('backend/masterdata/views.py', [
  '"purchasePriceReviewContexts"', '"purchasePriceReviewContextCount"',
  '"priceReviewRuleRuntimeCode": "PriceReviewRuleRuntime"',
], 'PRICE-HISTORY-REFERENCE-001')

requireTokens('frontend/src/meta/pages/PurchasePriceReviewAssistantPage.vue', [
  '供应商核价智能辅助', 'current-quotation-information', 'historical-price-reference',
  'price-review-supplier-comparison', 'price-review-rule-prompts', 'manual-price-decision',
  '核价意见', '确认人', '确认结果', '人工确认（仅测试会话）',
  'FoundationMetadataList', 'observability?.register?.(observabilityProvider)',
  'observability?.unregister?.(observabilityProvider)',
  'PRICE-REVIEW-CONTEXT-001', 'PRICE-HISTORY-REFERENCE-001', 'PRICE-RULE-ASSIST-001',
  'PRICE-NO-AUTO-DECISION-001', 'NO-AUTO-PRICE-DECISION-001', 'DECISION-AUDIT-001',
], 'PRICE-RULE-ASSIST-001')

requireTokens('frontend/src/router/index.js', [
  "path: 'scm/price-review-assistant'", "'price-review-assistant'",
], 'PRICE-REVIEW-CONTEXT-001')

const reviewContext = Object.freeze({
  objectType: 'PurchasePriceReviewContext', reviewContextId: 'PPRC-TEST',
  source: 'SupplierPriceFactRuntime', currentQuotationFact: { priceFactId: 'SPF-TEST' },
})
const pending = createPurchasePriceDecisionContext(reviewContext)
const confirmed = confirmPurchasePriceDecisionContext(pending, {
  reviewOpinion: '测试人工核价意见', confirmedBy: '测试核价员', confirmationResult: 'PASS',
}, () => '2026-08-11T00:00:00.000Z')
if (!confirmed.manualDecisionRecorded || confirmed.persisted !== false
  || confirmed.auditMode !== 'memory_session_only' || confirmed.businessProgressWriteCount !== 0
  || confirmed.confirmedAt !== '2026-08-11T00:00:00.000Z') {
  failures.push('DECISION-AUDIT-001: session audit contract invalid')
}

requireTokens('docs/governance/供应商核价智能辅助能力清单.md', [
  'SupplierPricingDecisionCapabilityInventory', '不建设第二套智能框架',
], 'PRICE-REVIEW-CONTEXT-001')
requireTokens('docs/governance/供应商核价智能辅助与人工决策闭环设计报告.md', [
  'PurchasePriceReviewContext', 'PriceReviewRuleRuntime', 'memory_session_only',
  '自动选择最低价：关闭', '自动创建采购订单：关闭',
], 'PRICE-NO-AUTO-DECISION-001')

const acceptanceReport = 'docs/governance/供应商核价智能辅助验收报告.md'
if (fs.existsSync(path.join(root, acceptanceReport))) {
  requireTokens(acceptanceReport, [
    'Automatic Acceptance：PASS', 'Browser Human Acceptance：PASS', 'Build：PASS',
    'Ready Gate：PASS', 'REAL-BROWSER-EVIDENCE-001', 'PURCHASE_PRICE_REVIEW_ASSISTANT_READY',
  ], 'REAL-BROWSER-EVIDENCE-001')
  const evidenceDirectory = path.join(root, 'frontend/test-results/V1.14.2.8.4.27.2.38')
  const screenshots = fs.existsSync(evidenceDirectory)
    ? fs.readdirSync(evidenceDirectory).filter(file => file.endsWith('.png')).map(file => path.join(evidenceDirectory, file)) : []
  if (screenshots.length < 3 || screenshots.some(file => fs.statSync(file).size <= 0)) {
    failures.push('REAL-BROWSER-EVIDENCE-001: screenshot evidence incomplete')
  }
} else failures.push('REAL-BROWSER-EVIDENCE-001: acceptance report missing')

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
  console.error('Purchase Price Review Assistant V2.38: FAIL')
  failures.forEach(item => console.error(`- ${item}`))
  process.exit(1)
}

console.log('PRICE-REVIEW-CONTEXT-001: PASS')
console.log('PRICE-HISTORY-REFERENCE-001: PASS')
console.log('PRICE-RULE-ASSIST-001: PASS')
console.log('PRICE-NO-AUTO-DECISION-001: PASS')
console.log('NO-AUTO-PRICE-DECISION-001: PASS')
console.log('DECISION-AUDIT-001: PASS')
console.log('REAL-BROWSER-EVIDENCE-001: PASS')
console.log('Database Changed: NO')
console.log('Business Write Count: 0')
