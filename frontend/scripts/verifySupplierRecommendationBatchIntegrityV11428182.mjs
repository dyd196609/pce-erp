import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(root, '..', 'docs', 'governance')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const run = args => spawnSync(process.execPath, args,
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const governanceFiles = ['CODEX执行命令规范.md', 'PCE-ERP开发治理总规范.md',
  '业务增强版本修改边界规范.md', '流程节点真实运行验收规范.md',
  '一页一验收规范.md', '问题案例库.md', '页面Route与业务Context分离规范.md']
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())
  && readGovernance('CODEX执行命令规范.md').includes('人工验收反向校验机制')

const current = run(['--test', 'tests/acceptance/supplierRecommendationBatchIntegrityV11428182.test.mjs'])
const regression = run(['--test',
  'tests/acceptance/supplierRecommendationDecisionItemGrainV11428181.test.mjs',
  'tests/acceptance/supplierRecommendationDataHandoffV1142818.test.mjs',
  'tests/acceptance/supplierRecommendationDecisionWorkbenchV11428169.test.mjs'])
const routeRegression = run(['scripts/verifySupplierRecommendationRouteIdentityV11428171.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, routeRegression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const model = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const provider = read('src/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js')
const pricePage = read('src/meta/components/ScmPriceApprovalPreparationEnterpriseList.vue')
const routeContext = readGovernance('页面Route与业务Context分离规范.md')
const process011 = readGovernance('流程节点真实运行验收规范.md')
const cases = readGovernance('问题案例库.md')
const currentPass = current.status === 0
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Selected Rows Count', currentPass && model.includes('selectedRowsCount: values.length')
    && pricePage.includes('selectedRows.value.map(createHandoffInput)')],
  ['Task Creation Count', currentPass && model.includes('taskCreationCount: taskResult.taskCount')
    && model.includes('const sourceTasks = taskResult.batches.flatMap')],
  ['Batch Source Mapping', currentPass && model.includes('const decisionBatches = freeze([batchStore.saveBatch(batch, bindings)])')
    && model.includes('batchSourceTaskCount: bindings.length')
    && model.includes('sourcePriceApprovalIds: freeze(sourcePriceApprovalIds)')],
  ['Material Aggregation', currentPass
    && model.includes('aggregateInputsBy(inputs, input => text(input.materialCode))')],
  ['DecisionItem Count', currentPass && model.includes('decisionItemCount: decisionBatches.reduce')],
  ['No Data Loss', currentPass && provider.includes('SOURCE_PRICE_APPROVAL_MISMATCH')
    && provider.includes('sourcePriceApprovalIds: frozen(priceApprovalIds)')
    && cases.includes('CASE-SCM-053')],
  ['Supplier Candidate Group', currentPass && model.includes('mergeSupplierCandidates')
    && provider.includes('preparationCandidates')],
  ['PROCESS-011 Data Handoff', currentPass && process011.includes('Data Handoff PASS')
    && provider.includes('DECISION_BATCH_SOURCE_MISMATCH')],
  ['ROUTE-CONTEXT-001', routeRegression.status === 0 && routeContext.includes('ROUTE-CONTEXT-001')],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.18.2')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_BATCH_INTEGRITY_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_BATCH_INTEGRITY_ISSUES_FOUND')
if (!passed) process.exitCode = 1
