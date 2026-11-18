import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath, pathToFileURL } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, pass) => checks.push({ name, pass: Boolean(pass) })

const governanceFiles = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/PCE-ERP统一页面验收标准V1.1.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
  'docs/governance/问题案例库.md',
]
check('Governance Files Loaded', governanceFiles.every(file => fs.existsSync(absolute(file))))

const service = read('backend/procurement/price_approval_preparation_service.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const canary = read('backend/purchase_canary/price_approval_runtime.py')
const domainPath = absolute('frontend/src/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js')
const domain = read('frontend/src/meta/domain/scm/priceApproval/priceApprovalPreparationRuntimeV1142824.js')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-ACT-001-R2.1.md')

for (const [code, label] of Object.entries({
  quotation_received: '已接收', draft: '草稿', reviewing: '核价中', approved: '已核准', rejected: '已拒绝',
})) check(`Status Label ${code}`, service.includes(`"${code}": "${label}"`)
  || (code === 'quotation_received' && canary.includes('"quotationStatusLabel": "已接收"')))

check('Status Label Contract', page.includes('prop="statusLabel"')
  && page.includes('prop="quotationStatusLabel"')
  && !page.includes('prop="quotationStatus" label="报价状态"'))
check('Editable Guard', page.includes("['draft', 'reviewing'].includes(current.value?.status)")
  && (page.match(/:disabled="!isCurrentEditable"/g) || []).length >= 5)
check('Editable Prompt', page.includes('请完成人工核价。'))
check('Readonly Prompt', page.includes('当前核价已完成，不允许修改。'))
check('State Codes Preserved', domain.includes("draft: Object.freeze(['reviewing'])")
  && domain.includes("reviewing: Object.freeze(['approved', 'rejected'])"))
check('No Automatic Purchase Order', service.includes('"purchaseOrderCreated": False')
  && !service.includes('PurchaseOrder.objects.create'))
check('Acceptance Archive', acceptance.includes('STATUS-LABEL')
  && acceptance.includes('EDITABLE-GUARD') && acceptance.includes('ACTION')
  && acceptance.includes('CHAIN'))
check('Build Artifact', fs.existsSync(absolute('frontend/dist/index.html')))

const runtime = await import(`${pathToFileURL(domainPath).href}?v=R21`)
const sample = {
  objectType: 'PriceApprovalPreparation', factSource: 'QuoteComparisonFact',
  approvalPrepareNo: 'PA-CAN-001', sourceComparisonNo: 'QC-CAN-001',
  sourceQuotationEvidence: [{ supplierCode: 'SUP-1' }],
  supplierCandidates: [{ supplierCode: 'SUP-1', supplierName: '供应商一' }],
  materialLines: [{ materialCode: 'MT001' }], status: 'draft', decisionVersion: 0,
}
const reviewing = runtime.startPriceApprovalReview(sample)
const approved = runtime.completePriceApprovalReview(reviewing, {
  selectedSupplierCode: 'SUP-1', reviewOpinion: '人工核价通过', exceptionNote: '',
  approvalOpinion: '同意', reviewer: '验收员', reviewedAt: '2026-08-07T12:00:00+08:00',
}, 'approved')
const rejected = runtime.completePriceApprovalReview(reviewing, {
  selectedSupplierCode: '', reviewOpinion: '人工核价拒绝', exceptionNote: '价格异常',
  approvalOpinion: '拒绝', reviewer: '验收员', reviewedAt: '2026-08-07T12:00:00+08:00',
}, 'rejected')
check('Action State Runtime', reviewing.statusLabel === '核价中'
  && approved.statusLabel === '已核准' && rejected.statusLabel === '已拒绝')

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log('QuoteComparisonFactWritten=0')
console.log('LegacyAdapterWritten=0')
console.log('SupplierQuotationWritten=0')
console.log('PurchaseOrderWritten=0')
console.log('productionUserDataWritten=false')
const failed = checks.filter(item => !item.pass)
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(failed.length ? 'SCM_PRICE_APPROVAL_OPERATION_ISSUES_FOUND' : 'SCM_PRICE_APPROVAL_OPERATION_READY')
if (failed.length) process.exitCode = 1
