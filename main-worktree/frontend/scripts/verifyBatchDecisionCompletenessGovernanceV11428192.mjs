import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const governanceRoot = path.resolve(frontendRoot, '..', 'docs', 'governance')
const read = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const runNode = args => spawnSync(process.execPath, args, {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})

const requiredFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '流程节点真实运行验收规范.md',
  '一页一验收规范.md',
  '问题案例库.md',
  '页面开发模板.md',
]
const governanceLoaded = requiredFiles.every(name => {
  const target = path.join(governanceRoot, name)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
})

const codex = read('CODEX执行命令规范.md')
const general = read('PCE-ERP开发治理总规范.md')
const process011 = read('流程节点真实运行验收规范.md')
const acceptance = read('一页一验收规范.md')
const cases = read('问题案例库.md')
const pageTemplate = read('页面开发模板.md')
const countLabels = ['Total Item Count', 'Completed Item Count', 'Pending Item Count']

const governanceRule = [
  'BATCH-COMPLETENESS-001',
  'Batch Decision Completeness Check',
  'SCM 采购推荐',
  '付款审批',
  '生产派工',
  '质量放行',
  '库存处理',
  'Pending Item Count > 0',
  'Action Disabled',
  ...countLabels,
].every(value => general.includes(value)) && codex.includes('BATCH-COMPLETENESS-001')

const templateUpdate = [
  'BATCH-COMPLETENESS-001',
  'Action Disabled',
  ...countLabels,
].every(value => pageTemplate.includes(value) && acceptance.includes(value))

const processUpdate = [
  'Batch Completeness',
  'Total Item Count = Completed Item Count + Pending Item Count',
  'Action Disabled',
  'NOT_APPLICABLE',
  ...countLabels,
].every(value => process011.includes(value))

const caseUpdate = [
  'CASE-SCM-056',
  '所有批量业务完整性检查模板',
  'BATCH-COMPLETENESS-001',
  'Action Disabled',
  ...countLabels,
].every(value => cases.includes(value))

const regression = runNode(['scripts/verifySupplierRecommendationDecisionCompletenessV11428191.mjs'])
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
  ['Governance Rule', governanceRule],
  ['Template Update', templateUpdate],
  ['PROCESS-011 Update', processUpdate],
  ['CASE Update', caseUpdate],
  ['Regression', regression.status === 0],
  ['Build', build.status === 0],
]
const passed = checks.every(([, value]) => value)

console.log('Version: V1.14.2.8.18.19.2')
for (const [label, value] of checks) console.log(`${label} ${value ? 'PASS' : 'FAIL'}`)
console.log(passed ? 'BATCH_COMPLETENESS_GOVERNANCE_READY'
  : 'BATCH_COMPLETENESS_GOVERNANCE_ISSUES_FOUND')
if (!passed) process.exitCode = 1
