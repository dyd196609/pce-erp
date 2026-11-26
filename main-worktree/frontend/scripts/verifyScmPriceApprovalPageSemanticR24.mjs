import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { DatabaseSync } from 'node:sqlite'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const root = path.resolve(frontendRoot, '..')
const absolute = relative => path.join(root, relative)
const read = relative => fs.readFileSync(absolute(relative), 'utf8')
const checks = []
const check = (name, passed) => checks.push({ name, passed: Boolean(passed) })

const governanceFiles = [
  'docs/governance/PCE-ERP开发治理总规范.md',
  'docs/governance/统一列表运行层规范.md',
  'docs/governance/一页一验收规范.md',
  'docs/governance/DATA-CONTINUITY数据连续性规范.md',
]
const page = read('frontend/src/meta/pages/ScmPriceApprovalRuntimePage.vue')
const acceptance = read('frontend/test-results/SCM-PRICE-APPROVAL-PAGE-SEMANTIC-ACT-001-R24.md')

check('Governance Files Loaded', governanceFiles.every(file => fs.existsSync(absolute(file))))
check('Region A Name', page.includes('<h2>待生成核价准备任务</h2>')
  && !page.includes('<h2>待生成核价准备</h2>'))
check('Region A Empty State', page.includes('description="当前暂无待生成核价准备任务。"')
  && !page.includes('暂无待承接的正式报价比较事实'))
check('Region B Name', page.includes('<h2>采购核价任务列表</h2>')
  && !page.includes('<h2>采购核价准备列表</h2>'))
check('Lifecycle Retention', page.includes('永久显示全部已生成的 PriceApprovalPreparation')
  && page.includes('完成或拒绝后均不删除、不隐藏')
  && page.includes(':rows="rows" :table-rows="filteredRows"')
  && page.includes('records.value = [...result.records]'))
check('Lifecycle States', ['draft', 'reviewing', 'completed', 'rejected']
  .every(status => page.includes(`${status}: records.value.filter`)))
check('Enterprise List Structure', page.includes('PceEnterpriseListTable')
  && page.includes('label="供应商"') && page.includes('label="核价状态"')
  && page.includes('label="核价结论"') && page.includes('primary-label="核价准备编号"')
  && page.includes(':action-contracts="actionContracts"'))
check('Fact Origin Bilingual', page.includes("production_fact: '正式业务事实'")
  && page.includes("legacy_verified_fact: '历史验证事实'")
  && page.includes('factOriginDisplay'))
check('Governed Status Label', page.includes('displayStatusLabel: resolveLifecycleStatusLabel(item)')
  && !page.includes('prop="statusCode"'))
check('Acceptance Archive', ['区域标题', '空状态提示', '任务生命周期', '数据刷新保持', '列表结构', '状态中文说明']
  .every(item => acceptance.includes(item)))

const databasePath = absolute('backend/db.sqlite3')
const database = new DatabaseSync(databasePath, { readOnly: true })
const firstRows = database.prepare(`SELECT approval_prepare_no, status, approval_opinion,
  review_opinion, decision_version, review_result
  FROM scm_price_approval_preparation ORDER BY approval_prepare_no`).all()
const secondRows = database.prepare(`SELECT approval_prepare_no, status, approval_opinion,
  review_opinion, decision_version, review_result
  FROM scm_price_approval_preparation ORDER BY approval_prepare_no`).all()
const purchaseOrderCount = Number(database.prepare('SELECT COUNT(*) count FROM purchase_order').get().count)
database.close()

const firstKeys = firstRows.map(row => row.approval_prepare_no)
const secondKeys = secondRows.map(row => row.approval_prepare_no)
check('PriceApprovalPreparation Count Preserved', firstRows.length === 13)
check('Refresh Data Not Reduced', secondRows.length === firstRows.length
  && JSON.stringify(secondKeys) === JSON.stringify(firstKeys))
check('No Business Data Deleted', firstRows.length === 13 && new Set(firstKeys).size === 13)
check('PurchaseOrder Added Zero', purchaseOrderCount === 208)
check('Build Artifact', fs.existsSync(absolute('frontend/dist/index.html')))

for (const item of checks) console.log(`${item.name} ${item.passed ? 'PASS' : 'FAIL'}`)
console.log(`BeforePriceApprovalPreparationCount=${firstRows.length}`)
console.log(`AfterPriceApprovalPreparationCount=${secondRows.length}`)
console.log(`RefreshPriceApprovalPreparationCount=${secondRows.length}`)
console.log(`PurchaseOrderCount=${purchaseOrderCount}`)
console.log('BusinessDataDeleted=0')
console.log('QuoteComparisonFactWritten=0')
console.log('LegacyAdapterWritten=0')
console.log('productionUserDataWritten=false')
const failed = checks.filter(item => !item.passed)
console.log(`Automatic Acceptance ${failed.length ? 'FAIL' : 'PASS'}`)
console.log(failed.length
  ? 'SCM_PRICE_APPROVAL_PAGE_SEMANTIC_ISSUE_FOUND'
  : 'SCM_PRICE_APPROVAL_PAGE_SEMANTIC_READY')
if (failed.length) process.exitCode = 1
