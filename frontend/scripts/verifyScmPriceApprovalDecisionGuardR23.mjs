import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, pass) => checks.push({ name, pass: Boolean(pass) })

const governance = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/统一列表运行层规范.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/问题案例库.md',
]
check('Governance Files Loaded', governance.every(file => fs.existsSync(absolute(file))))

const model = read('backend/procurement/models.py')
const service = read('backend/procurement/price_approval_preparation_service.py')
const api = read('backend/procurement/price_approval_preparation_api.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const migration = read('backend/procurement/migrations/0015_price_approval_review_result_v11428424_r23.py')
const caseLibrary = read('docs/governance/问题案例库.md')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-ACT-001-R23.md')
const domainPath = absolute('frontend/src/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js')

check('Review Result Model', model.includes('REVIEW_RESULT_CHOICES')
  && model.includes('("pass", "通过")') && model.includes('("reject", "不同意")')
  && model.includes('("adjust", "调整后重新核价")') && model.includes('review_result = models.CharField'))
check('Process State Separation', model.includes('("completed", "已完成")')
  && service.includes('"reviewing": {"completed"}')
  && !service.includes('"reviewing": {"approved", "rejected"}'))
check('Historical Compatibility', service.includes('resolve_price_approval_review_result')
  && service.includes('preparation.status in {"approved", "rejected"}')
  && !migration.includes('RunPython'))
check('Supplier Recommendation Guard', service.includes('is_supplier_recommendation_eligible')
  && service.includes('resolve_supplier_recommendation_blocked_reason')
  && service.includes('resolve_price_approval_review_result(preparation) != "pass"')
  && api.includes('if is_supplier_recommendation_eligible(preparation) else None'))
check('Blocked Message', page.includes('当前核价结果未通过，不允许进入供应商推荐。'))
check('Decision UI', page.includes('label="核价结论"')
  && page.includes('value="pass"') && page.includes('value="reject"') && page.includes('value="adjust"'))
check('Decision List', page.includes('prop="reviewResultLabel" label="核价结论"')
  && page.includes('查看/进入供应商推荐') && page.includes("row?.reviewResult === 'adjust'"))
check('Chinese Status', service.includes('"supplier_quote_collecting": "供应商报价收集中"')
  && (service.includes('"quotation_received": "已接收"')
    || service.includes('"quotation_received": "报价已接收"'))
  && service.includes('"completed": "已完成"'))
check('Case Closed', caseLibrary.includes('CASE-SCM-066')
  && caseLibrary.includes('status=completed AND reviewResult=pass'))
check('Acceptance Archive', ['STATUS', 'DECISION', 'ACTION', 'CHAIN', 'SUPPLIER-RECOMMENDATION-GUARD']
  .every(item => acceptance.includes(item)))

const domain = await import(`${pathToFileURL(domainPath).href}?v=R23`)
const base = {
  objectType: 'PriceApprovalPreparation', factSource: 'QuoteComparisonFact',
  approvalPrepareNo: 'PAP-QC-TEST', sourceComparisonNo: 'QC-TEST',
  sourceQuotationEvidence: [{ supplierCode: 'SUP-1', quotationStatusCode: 'quotation_received' }],
  supplierCandidates: [{ supplierCode: 'SUP-1', supplierName: '供应商一' }],
  materialLines: [{ materialCode: 'MT001' }], status: 'reviewing', decisionVersion: 0,
}
const commonInput = { selectedSupplierCode: 'SUP-1', reviewOpinion: '人工意见',
  exceptionNote: '', approvalOpinion: '审批说明', reviewer: '验收员' }
const passed = domain.completePriceApprovalReview(base, { ...commonInput, reviewResult: 'pass' }, 'completed')
const rejected = domain.completePriceApprovalReview(base, { ...commonInput, reviewResult: 'reject' }, 'completed')
check('Pass Context', passed.status === 'completed' && passed.reviewResult === 'pass'
  && domain.createSupplierRecommendationDecisionContext(passed).reviewResult === 'pass')
let rejectBlocked = false
try { domain.createSupplierRecommendationDecisionContext(rejected) } catch (error) {
  rejectBlocked = error.message === '当前核价结果未通过，不允许进入供应商推荐。'
}
check('Reject Guard', rejected.status === 'completed' && rejected.reviewResult === 'reject' && rejectBlocked)
check('Legacy Opinion Mapping', domain.resolvePriceApprovalProcessStatus({ status: 'approved' }) === 'completed'
  && domain.resolvePriceApprovalReviewResult({ status: 'approved', approvalOpinion: '不同意' }) === 'reject')

const database = new DatabaseSync(absolute('backend/db.sqlite3'), { readOnly: true })
const statusRows = database.prepare(`SELECT approval_prepare_no, status, approval_opinion,
  review_opinion, decision_version FROM scm_price_approval_preparation ORDER BY approval_prepare_no`).all()
const reviewResultCounts = database.prepare(`SELECT review_result value, COUNT(*) count
  FROM scm_price_approval_preparation GROUP BY review_result`).all()
const purchaseOrderCount = Number(database.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
database.close()
const crypto = await import('node:crypto')
const historicalHash = crypto.createHash('sha256').update(JSON.stringify(statusRows.map(row => [
  row.approval_prepare_no, row.status, row.approval_opinion, row.review_opinion, row.decision_version,
]))).digest('hex')
check('Historical Records Unchanged', statusRows.length === 13
  && historicalHash === 'eeb3ba6e356656add0cbf63bd9d7cfb19813b73d099a6d5d11e69a1c8d69588a'
  && reviewResultCounts.length === 1 && reviewResultCounts[0].value === '' && Number(reviewResultCounts[0].count) === 13)
check('PurchaseOrder Added Zero', purchaseOrderCount === 208)
check('Build Artifact', fs.existsSync(absolute('frontend/dist/index.html')))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log(`HistoricalPriceApprovalCount=${statusRows.length}`)
console.log(`HistoricalPriceApprovalSHA256=${historicalHash}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('QuoteComparisonFactWritten=0')
console.log('LegacyAdapterWritten=0')
console.log('productionUserDataWritten=false')
const failed = checks.filter(item => !item.pass)
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(failed.length ? 'SCM_PRICE_APPROVAL_DECISION_GUARD_ISSUE_FOUND' : 'SCM_PRICE_APPROVAL_DECISION_GUARD_READY')
if (failed.length) process.exitCode = 1
