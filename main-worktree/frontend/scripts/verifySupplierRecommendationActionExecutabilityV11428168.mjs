import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(root, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })

const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationActionExecutabilityV11428168.test.mjs'])
const taskRegression = run(['--test', 'tests/acceptance/supplierRecommendationTaskRuntimeV11428167.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationActionClosureV11428166.test.mjs',
  'tests/acceptance/supplierRecommendationBatchSplitV11428165.test.mjs',
  'tests/acceptance/supplierRecommendationBatchAndActionV11428164.test.mjs',
  'tests/acceptance/supplierRecommendationEntryConsistencyV11428163.test.mjs',
  'tests/acceptance/supplierRecommendationRuntimePathV11428162.test.mjs',
  'tests/acceptance/supplierRecommendationRealHandoffV11428161.test.mjs',
  'tests/acceptance/v11428151RegressionRecovery.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, taskRegression, regression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const actionRuntime = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationActionExecutabilityV11428168.js')
const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
const taskRuntime = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskRuntimeV11428167.js')
const taskProcess = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationTaskProcessCenterContextV11428167.js')
const process011 = readGovernance('流程节点真实运行验收规范.md')
const caseLibrary = readGovernance('问题案例库.md')
const currentPass = current.status === 0
const protectedBoundary = ['src/meta/components/PceListPageShell.vue',
  'src/meta/components/PceEnterpriseListTable.vue', 'src/meta/components/ProcessNodeNavigation.vue']
  .every(file => !read(file).includes('V11428168'))
const stateSequence = ['created', 'evaluating', 'decision_prepared', 'manual_review', 'confirmed', 'handoff_ready']
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Task Entry Regression', taskRegression.status === 0 && taskRuntime.includes('V1.14.2.8.18.16.7')
    && taskProcess.includes('?taskId=') && !page.includes('route.query.runtimeContextId')],
  ['Action Exists', currentPass && ['START_RECOMMENDATION_EVALUATION', 'PREPARE_RECOMMENDATION_DECISION',
    'START_MANUAL_REVIEW', 'SELECT_RECOMMENDATION_SUPPLIER', 'CONFIRM_RECOMMENDATION_DECISION',
    'PREPARE_PURCHASE_ORDER_GATE_HANDOFF'].every(action => actionRuntime.includes(action) && page.includes(action))],
  ['Action Executable', currentPass && actionRuntime.includes('permissionAllowed')
    && actionRuntime.includes('stateAllowed') && actionRuntime.includes('dataComplete')
    && page.includes('executeAllowed') && page.includes('selectCandidateByCode')],
  ['State Guard', currentPass && stateSequence.every(state => actionRuntime.includes(state))
    && actionRuntime.includes('ACTION_STATE_NOT_ALLOWED')],
  ['Data Completeness', currentPass && actionRuntime.includes('ACTION_DATA_INCOMPLETE')
    && actionRuntime.includes('runtimeContext?.materialCode')],
  ['Manual Confirm', currentPass && page.includes("actionExecutable('CONFIRM_RECOMMENDATION_DECISION')")],
  ['Decision Transition', currentPass && actionRuntime.includes('validateSupplierRecommendationActionResultV11428168')
    && actionRuntime.includes("resultState: 'confirmed'")],
  ['Gate Handoff', currentPass && actionRuntime.includes("resultState: 'handoff_ready'")
    && page.includes('executePreparePurchaseOrderGateHandoff')],
  ['PROCESS-011', currentPass && ['Object Exists PASS', 'Page Exists PASS', 'Data Handoff PASS',
    'Human Action Loop PASS', 'Entry Consistency PASS', 'Action Executability PASS']
    .every(value => process011.includes(value)) && caseLibrary.includes('CASE-SCM-047')],
  ['Regression', regression.status === 0 && protectedBoundary],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.8')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_ACTION_EXECUTION_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_ACTION_EXECUTION_ISSUES_FOUND')
if (!passed) process.exitCode = 1
