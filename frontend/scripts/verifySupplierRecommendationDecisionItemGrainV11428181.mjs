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
  '一页一验收规范.md', '问题案例库.md']
const governanceLoaded = governanceFiles.every(name => fs.existsSync(path.join(governanceRoot, name))
  && readGovernance(name).trim())

const current = run(['--test', 'tests/acceptance/supplierRecommendationDecisionItemGrainV11428181.test.mjs'])
const regression = run(['scripts/verifySupplierRecommendationDataHandoffV1142818.mjs'])
const build = run([path.join(root, 'node_modules', 'vite', 'bin', 'vite.js'), 'build', '.'])
for (const result of [current, regression, build]) if (result.status !== 0) {
  process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const model = read('src/meta/process/scm/supplierRecommendation/supplierRecommendationDecisionBatchV11428169.js')
const provider = read('src/meta/providers/supplierRecommendationDataHandoffProviderV1142818.js')
const page = read('src/meta/pages/ScmSupplierRecommendationDecisionWorkbenchPage.vue')
const process011 = readGovernance('流程节点真实运行验收规范.md')
const cases = readGovernance('问题案例库.md')
const currentPass = current.status === 0
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Source Rows', currentPass && model.includes('sourceRowCount: values.length')],
  ['Material Count', currentPass && model.includes('materialCount: new Set(values.map')],
  ['DecisionItem Grain', currentPass
    && model.includes('aggregateInputsBy(inputs, input => text(input.materialCode))')
    && model.includes('decisionItemCount: decisionBatches.reduce')],
  ['Supplier Candidate Group', currentPass && model.includes('mergeSupplierCandidates')
    && page.includes('item.supplierCandidates')],
  ['No Data Loss', currentPass && model.includes('quoteComparisonIds')
    && model.includes('priceEvidence') && !model.includes('.slice(0, 13)')],
  ['PROCESS-011 Data Handoff', currentPass && process011.includes('Data Handoff PASS')
    && provider.includes('itemBindings.length') && provider.includes('itemPreparations')
    && cases.includes('CASE-SCM-051')],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)
console.log('Version: V1.14.2.8.18.18.1')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ITEM_GRAIN_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_DECISION_ITEM_GRAIN_ISSUES_FOUND')
if (!passed) process.exitCode = 1
