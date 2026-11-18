import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceNames = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md', '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceNames.every(name => fs.existsSync(path.join(governanceRoot, name))
  && fs.readFileSync(path.join(governanceRoot, name), 'utf8').trim())
  && fs.readFileSync(path.join(governanceRoot, 'CODEX执行命令规范.md'), 'utf8')
    .includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationBatchAndActionV11428164.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationEntryConsistencyV11428163.test.mjs',
  'tests/acceptance/supplierRecommendationRuntimePathV11428162.test.mjs',
  'tests/acceptance/supplierRecommendationRealHandoffV11428161.test.mjs',
  'tests/acceptance/businessEnhancementBoundaryGovernanceV11428152.test.mjs',
  'tests/acceptance/v11428151RegressionRecovery.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const pass = current.status === 0
const batch = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationBatchContextV11428164.js')
const runtime = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationRuntimeContextV11428163.js')
const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
const decision = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionDomainV1142816.js')
const gate = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationPurchaseOrderGateHandoffV1142816.js')
const process011 = fs.readFileSync(path.join(governanceRoot, '流程节点真实运行验收规范.md'), 'utf8')
const boundary = ['src/meta/components/PceListPageShell.vue', 'src/meta/components/PceEnterpriseListTable.vue',
  'src/router/index.js'].every(file => !read(file).includes('V11428164'))
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Single Entry', pass && pricePage.includes('runtimeContextId:result.handoff.runtimeContext.runtimeContextNo')],
  ['Batch Entry', pass && batch.includes('SupplierRecommendationBatchContext')
    && batch.includes('SUPPLIER_RECOMMENDATION_BATCH_INQUIRY_MIXED')],
  ['Process Center Context', pass && page.includes('runtimeContextId') && page.includes('router.replace')],
  ['Context Restore', pass && runtime.includes('resolveSupplierRecommendationRuntimeContextIdV11428164')],
  ['Candidate Action', pass && page.includes('recommendation-candidates')],
  ['Evidence Display', pass && page.includes('recommendation-evidence')
    && page.includes('historical-price-reference')],
  ['Manual Confirm', pass && page.includes('CONFIRM_RECOMMENDATION_DECISION')],
  ['Decision Created', pass && decision.includes("decisionStatus: 'confirmed'")],
  ['Gate Handoff', pass && gate.includes('purchaseOrderCreated: false')],
  ['PROCESS-011', pass && ['Object Exists PASS', 'Page Exists PASS', 'Data Handoff PASS',
    'Human Action Loop PASS', 'Entry Consistency PASS'].every(value => process011.includes(value))],
  ['Regression', regression.status === 0 && boundary],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.4')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_BATCH_ACTION_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_BATCH_ACTION_ISSUES_FOUND')
if (!passed) process.exitCode = 1
