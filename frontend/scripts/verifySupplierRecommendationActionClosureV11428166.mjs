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
const governanceLoaded = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md', '一页一验收规范.md', '问题案例库.md']
  .every(name => fs.existsSync(path.join(governanceRoot, name))
    && fs.readFileSync(path.join(governanceRoot, name), 'utf8').trim())

const current = run(['--test', 'tests/acceptance/supplierRecommendationActionClosureV11428166.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationBatchSplitV11428165.test.mjs',
  'tests/acceptance/supplierRecommendationBatchAndActionV11428164.test.mjs',
  'tests/acceptance/supplierRecommendationEntryConsistencyV11428163.test.mjs',
  'tests/acceptance/supplierRecommendationRuntimePathV11428162.test.mjs',
  'tests/acceptance/supplierRecommendationRealHandoffV11428161.test.mjs',
  'tests/acceptance/v11428151RegressionRecovery.test.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const pass = current.status === 0
const page = read('src/meta/pages/ScmSupplierRecommendationPage.vue')
const selection = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationCurrentSelectionV11428166.js')
const context = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationProcessCenterContextV11428166.js')
const scmRegistry = read('src/meta/process/scmPurchaseProcessCenterRegistryV11428101.js')
const processRegistry = read('src/meta/process/businessProcessRegistry.js')
const gate = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationPurchaseOrderGateHandoffV1142816.js')
const process011 = fs.readFileSync(path.join(governanceRoot, '流程节点真实运行验收规范.md'), 'utf8')
const publicBoundary = ['src/meta/components/PceListPageShell.vue',
  'src/meta/components/PceEnterpriseListTable.vue', 'src/meta/components/ProcessNodeNavigation.vue']
  .every(file => !read(file).includes('V11428166'))
const checks = [
  ['Candidate Action', governanceLoaded && pass && page.includes('SELECT_RECOMMENDATION_SUPPLIER')
    && selection.includes('SupplierRecommendationCurrentSelection')],
  ['Decision Action', pass && page.includes('currentRecommendation')
    && page.includes('CONFIRM_RECOMMENDATION_DECISION')],
  ['QuoteComparison Display', pass && page.includes('单物料供应商报价比较')
    && page.includes('供应商报价')],
  ['Material Supplier Separation', pass && page.includes('single-material-summary')],
  ['Process Center Context', pass && scmRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428166')
    && processRegistry.includes('resolveScmPurchaseProcessNodePageUrlV11428166')],
  ['Runtime Restore', pass && context.includes('runtimeContextId=')
    && context.includes('real_price_approval_handoff') && page.includes('markActive')],
  ['Manual Confirm', pass && page.includes('推荐理由') && page.includes('确认人')
    && page.includes('确认时间')],
  ['Gate Handoff', pass && gate.includes('purchaseOrderCreated: false')],
  ['PROCESS-011', pass && ['Object Exists PASS', 'Page Exists PASS', 'Data Handoff PASS',
    'Human Action Loop PASS', 'Entry Consistency PASS'].every(value => process011.includes(value))],
  ['Regression', regression.status === 0 && publicBoundary],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.16.6')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_ACTION_CLOSURE_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_ACTION_CLOSURE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
