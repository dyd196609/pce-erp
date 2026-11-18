import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const acceptanceRoot = path.join(workspaceRoot, 'docs', 'acceptance', 'scm-purchase-golden-path-v114288')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')

const governanceFiles = [
  'PCE-ERP开发治理总规范.md',
  '节点开发模板.md',
  '页面开发模板.md',
  'Approval审批治理规范.md',
  '一页一验收规范.md',
  '问题案例库.md',
]
const governanceLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const requestPage = readFrontend('src/meta/pages/ScmPurchaseRequestPage.vue')
const requestRegion = readFrontend('src/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue')
const inquiryPage = readFrontend('src/meta/pages/ScmPurchaseInquiryWorkbenchPage.vue')
const editPage = readFrontend('src/meta/pages/ScmPurchaseInquiryEditPage.vue')
const supplierSelector = readFrontend('src/meta/components/SupplierCandidateSelector.vue')
const scmPage = readFrontend('src/meta/pages/ScmPage.vue')
const priceApprovalList = readFrontend('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const router = readFrontend('src/router/index.js')
const identityRegistry = readFrontend('src/meta/schema/scm/scmPageIdentityRegistry.js')
const approvalPage = readFrontend('src/meta/pages/ApprovalFlowConfigPage.vue')
const approvalRuntime = readFrontend('src/meta/workflow/approvalRuntime.js')
const stateMapping = readFrontend('src/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js')
const displayMapping = readFrontend('src/meta/process/scm/purchaseInquiry/businessStatusDisplayMapping.js')
const caseLibrary = readWorkspace('docs/governance/问题案例库.md')
const purchaseRequestBackend = readWorkspace('backend/procurement/purchase_request_api.py')
const purchaseRequestBackendTests = readWorkspace('backend/procurement/tests_v417.py')
const materialMigration = readWorkspace('backend/masterdata/migrations/0001_initial.py')
const employeeMigration = readWorkspace('backend/pfm/migrations/0001_initial.py')

const nodeTests = spawnSync(process.execPath, ['--test',
  'tests/acceptance/processRuntimeFrameworkV114288.test.mjs',
  'tests/acceptance/purchaseRequestProcessRuntimeV1142889.test.mjs',
  'tests/acceptance/enterpriseScmPurchaseRequestInquiryPreparationHandoffV11428183.test.mjs',
  'tests/acceptance/enterpriseInquiryPreparationProviderRuntimeV1142831.test.mjs',
  'tests/acceptance/enterpriseScmInquiryBusinessClosureV114287A.test.mjs',
  'tests/acceptance/enterpriseScmPurchaseInquiryHandoffV11428818.test.mjs',
  'tests/acceptance/enterpriseScmPurchaseGoldenPathStabilizationV1142881.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const backendCreateContract = purchaseRequestBackend.includes('return [permissions.IsAuthenticated()]')
  && purchaseRequestBackendTests.includes('test_v11428818_authenticated_create_returns_complete_purchase_request_and_is_listed')
const databaseMigrationIntegrity = materialMigration.includes("'db_table': 'material_category'")
  && materialMigration.includes("'managed': True")
  && employeeMigration.includes('name="Employee"')
  && employeeMigration.includes('"db_table": "employee"')

const page001 = requestPage.includes("pageCode:'purchase-request'")
  && requestPage.includes('approvalStatusLabel')
  && requestPage.includes('businessLifecycleStatusLabel')
  && requestPage.includes('新增采购申请')
  && requestPage.includes('提交审批')
  && requestRegion.includes('保存采购申请')
  && requestRegion.includes('PURCHASE_REQUEST_CREATE_RESPONSE_INCOMPLETE')
  && nodeTests.status === 0 && backendCreateContract && databaseMigrationIntegrity

const approvalLevels = ['1关', '2关', '3关'].every(value => approvalPage.includes(value))
const approvalPageIdentity = router.includes("pageCode: 'approval-flow-config'")
  && router.includes("businessObject: 'ApprovalConfiguration'")
  && identityRegistry.includes("pageCode: 'approval-flow-config'")
  && identityRegistry.includes("pageName: '审批规则配置'")
  && identityRegistry.includes("route: '/admin/approval-flow-config'")
const approvalLifecycle = ['createApprovalContract', 'createApprovalInstance', 'executeApprovalAction',
  'writeApprovalResultToBusinessObject', 'approvalWritebackKeys']
  .every(value => approvalRuntime.includes(value)) && nodeTests.status === 0
const page002 = approvalLevels && approvalPageIdentity && approvalLifecycle

const page003 = inquiryPage.includes('data-acceptance-id="pending-inquiry-preparations"')
  && ['询价准备编号', '来源申请号', '物料数量', '供应商候选数量', 'statusLabel']
    .every(value => inquiryPage.includes(value))
  && nodeTests.status === 0

const stateAndActionMapping = stateMapping.includes("processStatusLabel: '已进入供应商报价准备'")
  && stateMapping.includes("nextAction: '进入供应商报价准备'")
  && inquiryPage.includes('currentInquiryDisplay?.processStatusLabel')
  && inquiryPage.includes('currentInquiryDisplay?.nextAction')
  && !inquiryPage.includes("processStatusLabel || '询价编辑中'")
const page004 = inquiryPage.includes('label="业务状态"')
  && inquiryPage.includes('label="流程状态"')
  && stateAndActionMapping && nodeTests.status === 0

const materialDecision = editPage.includes('data-material-supplier-decision')
  && ['物料编码', '物料名称', '规格', '数量', '需求日期'].every(value => editPage.includes(value))
  && supplierSelector.includes('data-candidate-action="add"')
  && supplierSelector.includes('data-candidate-action="remove"')
  && supplierSelector.includes('data-candidate-action="replace"')
const businessLanguageDisplay = displayMapping.includes("active: '有效'")
  && displayMapping.includes("unclassified: '未分类'")
  && displayMapping.includes("supplier_master: '供应商主数据'")
  && supplierSelector.includes('businessDisplay(candidate).supplierStatusLabel')
  && supplierSelector.includes('businessDisplay(candidate).supplierCategoryLabel')
  && supplierSelector.includes('businessDisplay(candidate).sourceLabel')
  && !supplierSelector.includes('{{ candidate.supplierStatus }}')
  && !supplierSelector.includes('{{ candidate.supplierCategory }}')
  && !supplierSelector.includes('{{ candidate.source }}')
  && !editPage.includes('{{ pageState.runtimeState }}')
const page005 = materialDecision && editPage.includes('PREPARE_SUPPLIER_QUOTE')
  && businessLanguageDisplay && nodeTests.status === 0

const priceRegionStart = scmPage.indexOf('data-acceptance-id="price-approval-current-quote-preparation"')
const priceRegionEnd = scmPage.indexOf('<section v-else-if="activeConfig', priceRegionStart)
const priceRegion = scmPage.slice(priceRegionStart, priceRegionEnd)
const priceApprovalTemplate = priceApprovalList.slice(0, priceApprovalList.indexOf('<script setup>'))
const page006 = priceRegionStart >= 0
  && priceRegion.includes('<ScmPriceApprovalPreparationEnterpriseList')
  && ['PceEnterpriseListTable', 'inquiryNo', 'sourceRequestNo', 'supplierCode',
    'preparationStatusLabel', 'material-price-reference-region', 'data-read-only="true"']
    .every(value => priceApprovalTemplate.includes(value))
  && scmPage.includes("price_approval_preparation_ready: '已进入采购核价准备'")
  && !['自动批准报价', '自动拒绝报价', '自动推荐供应商', '自动生成采购订单']
    .some(value => priceApprovalTemplate.includes(value))
  && nodeTests.status === 0

const pageRecords = [1, 2, 3, 4, 5, 6].every(number =>
  fs.readdirSync(acceptanceRoot).some(name => name.startsWith(`PAGE-00${number}-`)))
const fixedCases = ['CASE-SCM-010', 'CASE-SCM-011', 'CASE-SCM-012', 'CASE-SCM-013', 'CASE-SCM-014']
const process010 = fixedCases.every(caseId => caseLibrary.includes(caseId))
  && caseLibrary.includes('修复版本：`V1.14.2.8.18.8.1`')

const process006A = [page001, page002, page003, page004, page005, page006].every(Boolean)
const process006B = page003 && page006 && nodeTests.status === 0
const process006C = nodeTests.status === 0
const process006D = process006A && nodeTests.status === 0
const process008 = nodeTests.status === 0 && backendCreateContract && databaseMigrationIntegrity
const process009 = pageRecords && process006A
const governanceFramework = governanceLoaded
const goldenPath = process006A && process006B && process006C && process006D
  && process008 && process009 && process010

const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = spawnSync(process.execPath, [vite, 'build', '.'],
  { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

if (nodeTests.status !== 0) process.stderr.write(`${nodeTests.stdout || ''}${nodeTests.stderr || ''}`)
if (build.status !== 0) process.stderr.write(`${build.stdout || ''}${build.stderr || ''}`)

const regression = nodeTests.status === 0 && backendCreateContract && databaseMigrationIntegrity
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Database Migration Integrity', databaseMigrationIntegrity],
  ['Approval Page Identity', approvalPageIdentity],
  ['Approval Lifecycle', approvalLifecycle],
  ['State And Action Mapping', stateAndActionMapping],
  ['Business Language Display', businessLanguageDisplay],
  ['Governance Framework', governanceFramework],
  ['PAGE-001', page001], ['PAGE-002', page002], ['PAGE-003', page003],
  ['PAGE-004', page004], ['PAGE-005', page005], ['PAGE-006', page006],
  ['PROCESS-006-A', process006A], ['PROCESS-006-B', process006B],
  ['PROCESS-006-C', process006C], ['PROCESS-006-D', process006D],
  ['PROCESS-008', process008], ['PROCESS-009', process009], ['PROCESS-010', process010],
  ['Golden Path', goldenPath], ['Regression', regression], ['Build', build.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)

const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('未通过项清单：')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length === 0
  ? 'SCM_PURCHASE_GOLDEN_PATH_STABILIZED'
  : 'SCM_PURCHASE_GOLDEN_PATH_ISSUES_FOUND')
if (failures.length) process.exitCode = 1
