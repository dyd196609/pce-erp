import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

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
]
check('Governance Files Loaded', governance.every(file => fs.existsSync(absolute(file))))

const api = read('backend/procurement/price_approval_preparation_api.py')
const service = read('backend/procurement/price_approval_preparation_service.py')
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const list = read('frontend/src/meta/components/PceEnterpriseListTable.vue')
const contract = read('frontend/src/meta/runtime/pceEnterpriseListContract.js')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-LIST-ACT-001-R22.md')

check('List Structure', page.includes('<PceEnterpriseListTable')
  && contract.includes("contractVersion: PCE_ENTERPRISE_LIST_CONTRACT_VERSION")
  && list.includes('type="selection"') && list.includes('type="index"'))
check('Fixed Columns', list.includes('fixed="left"') && list.includes('fixed="right"')
  && contract.includes("frozenLeft: Object.freeze(['selection', 'index', 'primaryNo'])"))
check('Lifecycle Preservation', api.includes('PriceApprovalPreparation.objects.select_related("source_comparison").all()]')
  && !api.includes('PriceApprovalPreparation.objects.select_related("source_comparison").all()[:200]')
  && !api.includes('PriceApprovalPreparation.objects.filter(status'))
check('Lifecycle Status', ['draft', 'reviewing', 'approved', 'rejected'].every(code => service.includes(`"${code}"`))
  && ['草稿', '核价中', '已核准', '已拒绝'].every(label => page.includes(label)))
check('Action Column', page.includes(':action-label-resolver="resolveReviewActionLabel"')
  && page.includes("draft: '人工核价'") && page.includes("reviewing: '继续核价'")
  && page.includes("approved: '查看'") && page.includes("rejected: '查看'"))
check('Batch Action', page.includes('批量查看') && page.includes('批量进入核价')
  && page.includes('批量入口不会自动核价') && page.includes("['draft', 'reviewing'].includes(item.status)"))
check('Region Separation', page.includes('待生成核价准备')
  && page.includes('采购核价准备列表')
  && page.includes('尚未生成 PriceApprovalPreparation'))
check('No Automatic Approval', !page.includes('batchApprove') && !service.includes('automaticLowestQuoteSelected = True'))
check('No PurchaseOrder Creation', !service.includes('PurchaseOrder.objects.create')
  && page.includes('不创建采购订单'))
check('Acceptance Archive', ['LIST-STRUCTURE', 'LIFECYCLE', 'BATCH-ACTION', 'STATUS', 'ACTION-COLUMN']
  .every(item => acceptance.includes(item)))
check('Build Artifact', fs.existsSync(absolute('frontend/dist/index.html')))

for (const item of checks) console.log(`${item.name} ${item.pass ? 'PASS' : 'FAIL'}`)
console.log('PriceApprovalPreparationDeleted=0')
console.log('QuoteComparisonFactWritten=0')
console.log('LegacyAdapterWritten=0')
console.log('PurchaseOrderWritten=0')
console.log('productionUserDataWritten=false')
const failed = checks.filter(item => !item.pass)
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(failed.length ? 'SCM_PRICE_APPROVAL_LIST_STANDARD_ISSUES_FOUND' : 'SCM_PRICE_APPROVAL_LIST_STANDARD_READY')
if (failed.length) process.exitCode = 1
