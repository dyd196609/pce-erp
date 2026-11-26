import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceNames = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '治理符合性检查矩阵.md', '问题案例库.md']
const governanceLoaded = governanceNames.every(name => {
  const target = path.join(governanceRoot, name)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim()
}) && fs.readFileSync(path.join(governanceRoot, 'CODEX执行命令规范.md'), 'utf8')
  .includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationEntryConsistencyV11428163.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationRuntimePathV11428162.test.mjs',
  'tests/acceptance/supplierRecommendationRealHandoffV11428161.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionRuntimeV1142816.test.mjs',
  'tests/acceptance/businessEnhancementBoundaryGovernanceV11428152.test.mjs',
  'tests/acceptance/v11428151RegressionRecovery.test.mjs'])
const vite = path.join(root, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])
for (const result of [current, regression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const runtimeContext = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js')
const domain = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDomainModelV1142811.js')
const evidenceDomain = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionDomainV1142816.js')
const handoff = read('src/meta/process/scm/priceApproval/priceApprovalSupplierRecommendationHandoffV11428161.js')
const provider = read('src/meta/providers/supplierRecommendationDecisionProviderV1142816.js')
const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
const gate = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationPurchaseOrderGateHandoffV1142816.js')
const router = read('src/router/index.js')
const process011 = fs.readFileSync(path.join(governanceRoot, '流程节点真实运行验收规范.md'), 'utf8')
const currentPass = current.status === 0
const boundary = ['src/meta/components/PceListPageShell.vue', 'src/meta/components/PceEnterpriseListTable.vue',
  'src/router/index.js'].every(file => !read(file).includes('V11428163'))
const fields = ['priceApprovalNo', 'priceApprovalId', 'quoteComparisonId', 'materialCode', 'materialName',
  'supplierCandidates', 'priceEvidence', 'historicalPriceEvidence']
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['BUSINESS-ENHANCEMENT-BOUNDARY', boundary],
  ['Object Exists', currentPass && runtimeContext.includes('SupplierRecommendationRuntimeContext')
    && domain.includes('SupplierRecommendationDecision') && evidenceDomain.includes('SupplierRecommendationEvidence')],
  ['Page Exists', page.includes('data-page-code="supplier-recommendation"')
    && router.includes("path: 'scm/supplier-recommendations'")],
  ['Data Handoff', currentPass && fields.every(field => handoff.includes(field))],
  ['Human Action Loop', currentPass && page.includes('CONFIRM_RECOMMENDATION_DECISION')],
  ['Entry Consistency', currentPass && runtimeContext.includes('resolveSupplierRecommendationEntryV11428163')],
  ['PriceApproval Context', currentPass && fields.every(field => runtimeContext.includes(field))],
  ['Route Context', currentPass && ['priceApprovalId:row.priceApprovalId',
    'quoteComparisonId:row.quoteComparisonId', 'materialCode:row.materialCode'].every(value => pricePage.includes(value))],
  ['Page Data Same Instance', currentPass && page.includes('item.entryKey === entryResolution.value.entryKey')],
  ['No Demo Data', currentPass && provider.includes(': Object.freeze([])') && !runtimeContext.includes('PI-TEST-SR')],
  ['Material Match', currentPass],
  ['Supplier Match', currentPass],
  ['Manual Decision', currentPass && domain.includes("decisionStatus: 'confirmed'")],
  ['Gate Handoff', currentPass && gate.includes('purchaseOrderCreated: false')],
  ['PROCESS-011', currentPass && ['Object Exists PASS', 'Page Exists PASS', 'Data Handoff PASS',
    'Human Action Loop PASS', 'Entry Consistency PASS'].every(value => process011.includes(value))],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.3')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_ENTRY_CONSISTENCY_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_ENTRY_CONSISTENCY_ISSUES_FOUND')
if (!passed) process.exitCode = 1
