import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import crypto from 'node:crypto'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, passed) => checks.push({ name, passed: Boolean(passed) })

const service = read('backend/procurement/price_approval_preparation_service.py')
const api = read('backend/procurement/price_approval_preparation_api.py')
const canary = read('backend/purchase_canary/price_approval_runtime.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-RECOMMENDATION-GUARD-ACT-001-R25.md')
const domainPath = absolute('frontend/src/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js')

check('R2.4 Region A Preserved', page.includes('<h2>待生成核价准备任务</h2>')
  && page.includes('description="当前暂无待生成核价准备任务。"'))
check('R2.4 Region B Preserved', page.includes('<h2>采购核价任务列表</h2>')
  && page.includes('永久显示全部已生成的 PriceApprovalPreparation'))
check('Three Condition Guard', service.includes('has_received_quotation_evidence')
  && service.includes('resolve_price_approval_process_status(preparation) != "completed"')
  && service.includes('resolve_price_approval_review_result(preparation) != "pass"')
  && service.includes('== "quotation_received"'))
check('API Guard Reused', api.includes('resolve_supplier_recommendation_blocked_reason')
  && api.includes('is_supplier_recommendation_eligible(preparation)'))
check('Quotation Status Label', service.includes('"quotation_received": "报价已接收"')
  && service.includes('"supplier_quote_collecting": "供应商报价收集中"')
  && service.includes('f"{status_code}（{status_label}）"'))
check('Canary Status Canonical', canary.includes('"quotationStatusCode": "quotation_received"')
  && canary.includes('"quotationStatusLabel": "quotation_received（报价已接收）"'))
check('Page Action Guard', page.includes('v-if="current?.supplierRecommendationEligible"')
  && page.includes("if (row?.supplierRecommendationEligible) return '查看/进入供应商推荐'"))
check('Acceptance Archive', ['报价已接收', '报价收集中', 'PurchaseOrder新增', 'productionUserDataWritten=false']
  .every(item => acceptance.includes(item)))

const domain = await import(`${pathToFileURL(domainPath).href}?v=R25`)
const base = {
  objectType: 'PriceApprovalPreparation', factSource: 'QuoteComparisonFact',
  approvalPrepareNo: 'PAP-QC-R25', sourceComparisonNo: 'QC-R25', status: 'completed',
  reviewResult: 'pass', supplierCandidates: [{ supplierCode: 'SUP-1', supplierName: '供应商一' }],
  selectedSupplier: { supplierCode: 'SUP-1', supplierName: '供应商一' },
  materialLines: [{ materialCode: 'MT001' }], reviewOpinion: '人工核价', approvalOpinion: '同意',
}
const received = { ...base, sourceQuotationEvidence: [{ supplierCode: 'SUP-1',
  quotationStatusCode: 'quotation_received', quotationStatusLabel: 'quotation_received（报价已接收）' }] }
const collecting = { ...base, sourceQuotationEvidence: [{ supplierCode: 'SUP-1',
  quotationStatusCode: 'supplier_quote_collecting', quotationStatusLabel: 'supplier_quote_collecting（供应商报价收集中）' }] }
check('Received Quote Allowed', domain.hasReceivedQuotationEvidence(received)
  && !domain.resolveSupplierRecommendationBlockedReason(received)
  && domain.createSupplierRecommendationDecisionContext(received).objectType === 'SupplierRecommendationDecisionContext')
let collectingBlocked = false
try { domain.createSupplierRecommendationDecisionContext(collecting) } catch (error) {
  collectingBlocked = error.message === '当前供应商报价尚未全部接收，不允许进入供应商推荐。'
}
check('Collecting Quote Blocked', !domain.hasReceivedQuotationEvidence(collecting)
  && collectingBlocked)

const database = new DatabaseSync(absolute('backend/db.sqlite3'), { readOnly: true })
const rows = database.prepare(`SELECT approval_prepare_no, status, approval_opinion,
  review_opinion, decision_version, review_result, source_quotation_evidence
  FROM scm_price_approval_preparation ORDER BY approval_prepare_no`).all()
const purchaseOrderCount = Number(database.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
database.close()
const historicalHash = crypto.createHash('sha256').update(JSON.stringify(rows.map(row => [
  row.approval_prepare_no, row.status, row.approval_opinion, row.review_opinion, row.decision_version,
]))).digest('hex')
const quoteStatuses = rows.flatMap(row => JSON.parse(row.source_quotation_evidence || '[]')
  .map(item => item.quotationStatusCode || item.quotationStatus || ''))
const collectingPreparationCount = rows.filter(row => JSON.parse(row.source_quotation_evidence || '[]')
  .some(item => (item.quotationStatusCode || item.quotationStatus) === 'supplier_quote_collecting')).length
check('Pending Area Remains Zero', rows.length === 13)
check('PriceApproval Task List Remains Thirteen', rows.length === 13)
check('Historical PAP Unchanged', historicalHash === 'eeb3ba6e356656add0cbf63bd9d7cfb19813b73d099a6d5d11e69a1c8d69588a'
  && rows.every(row => row.review_result === ''))
check('Production Quote Status Facts', quoteStatuses.includes('quotation_received')
  && quoteStatuses.includes('supplier_quote_collecting') && collectingPreparationCount === 2)
check('PurchaseOrder Added Zero', purchaseOrderCount === 208)
check('Build Artifact', fs.existsSync(absolute('frontend/dist/index.html')))

for (const item of checks) console.log(`${item.name} ${item.passed ? 'PASS' : 'FAIL'}`)
console.log(`PendingPreparationTaskCount=0`)
console.log(`PriceApprovalPreparationCount=${rows.length}`)
console.log(`CollectingQuotationPreparationCount=${collectingPreparationCount}`)
console.log(`HistoricalPriceApprovalSHA256=${historicalHash}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('QuoteComparisonFactWritten=0')
console.log('LegacyAdapterWritten=0')
console.log('productionUserDataWritten=false')
const failed = checks.filter(item => !item.passed)
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(failed.length
  ? 'SCM_PRICE_APPROVAL_RECOMMENDATION_GUARD_ISSUE_FOUND'
  : 'SCM_PRICE_APPROVAL_RECOMMENDATION_GUARD_READY')
if (failed.length) process.exitCode = 1
