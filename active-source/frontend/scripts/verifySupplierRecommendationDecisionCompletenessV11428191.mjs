import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(sourceRoot, 'docs', 'governance')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const runNode = args => spawnSync(process.execPath, args, {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})

const requiredGovernanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '流程节点真实运行验收规范.md',
  '问题案例库.md',
  '一页一验收规范.md',
]
const governanceLoaded = requiredGovernanceFiles.every(name => {
  const target = path.join(governanceRoot, name)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
})

const cases = readGovernance('问题案例库.md')
const acceptance = readGovernance('一页一验收规范.md')
const casePass = [
  'CASE-SCM-056',
  '批量推荐确认前未完成全部物料决策导致按钮不可执行',
  '当前批次仍有未完成物料决策。',
  'Completed Item Count',
  'Pending Item Count',
  'Confirm Action Enabled',
].every(value => cases.includes(value))
const completenessRulePass = [
  'Batch Decision Completeness Check',
  'selectedSupplier',
  'selectionReason',
  'reviewStatus',
  'Completed Item Count',
  'Pending Item Count',
  'Confirm Action Enabled',
  'Pending Item Count = 0',
].every(value => acceptance.includes(value))

const regression = runNode([
  '--test',
  'tests/acceptance/supplierRecommendationHumanDecisionV1142819.test.mjs',
])
const build = runNode([
  path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js'),
  'build',
  '.',
])
for (const result of [regression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['CASE-SCM-056', casePass && completenessRulePass],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)

console.log('Version: V1.14.2.8.18.19.1')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed
  ? 'SCM_SUPPLIER_RECOMMENDATION_DECISION_COMPLETENESS_GOVERNANCE_READY'
  : 'SCM_SUPPLIER_RECOMMENDATION_DECISION_COMPLETENESS_GOVERNANCE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
