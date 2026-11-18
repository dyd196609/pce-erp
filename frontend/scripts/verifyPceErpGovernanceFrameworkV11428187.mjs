import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(scriptDir, '..')
const governanceRoot = resolve(frontendRoot, '..', 'docs', 'governance')

const requiredFiles = [
  'PCE-ERP开发治理总规范.md',
  '节点开发模板.md',
  '页面开发模板.md',
  'Action动作规范.md',
  'State状态规范.md',
  'Handoff交接规范.md',
  'Approval审批治理规范.md',
  'Provider数据规范.md',
  '一页一验收规范.md',
  'GoldenPath黄金路径规范.md',
  '回归测试规范.md',
  '问题案例库.md'
]

const readGovernance = (name) => readFileSync(join(governanceRoot, name), 'utf8')
const requireTerms = (content, terms, label) => {
  for (const term of terms) {
    assert.ok(content.includes(term), `${label} missing required term: ${term}`)
  }
}

for (const name of requiredFiles) {
  assert.ok(existsSync(join(governanceRoot, name)), `missing governance file: ${name}`)
}

const total = readGovernance('PCE-ERP开发治理总规范.md')
const nodeTemplate = readGovernance('节点开发模板.md')
const pageTemplate = readGovernance('页面开发模板.md')
const approvalTemplate = readGovernance('Approval审批治理规范.md')
const pageAcceptance = readGovernance('一页一验收规范.md')
const goldenPath = readGovernance('GoldenPath黄金路径规范.md')
const regression = readGovernance('回归测试规范.md')
const caseLibrary = readGovernance('问题案例库.md')

requireTerms(nodeTemplate, [
  'Node Contract',
  'Domain Model',
  'State Contract',
  'Action Contract',
  'Approval Contract',
  'Handoff Contract',
  'Provider Contract',
  'Page Contract',
  'Acceptance Profile',
  'Golden Path'
], 'Node Template')

requireTerms(pageTemplate, [
  'pageCode',
  'pageName',
  'route',
  'moduleCode',
  '数据来源',
  '当前状态',
  '下一动作',
  'Action Contract',
  '执行结果',
  '页面名称未登记'
], 'Page Template')

requireTerms(approvalTemplate, [
  '审批关卡',
  '审批级别',
  '审批状态',
  '审批实例',
  '审批结果回写',
  '1 关',
  '2 关',
  '3 关',
  '禁止页面自建'
], 'Approval Template')

requireTerms(pageAcceptance, [
  'Page Acceptance Template',
  'URL',
  '页面名称',
  '区域定位',
  '数据字段',
  '按钮',
  '流程下一步',
  '异常处理',
  '刷新恢复',
  '人工验收结果',
  'PROCESS-009'
], 'One Page Acceptance')

for (let index = 1; index <= 9; index += 1) {
  requireTerms(caseLibrary, [`CASE-SCM-${String(index).padStart(3, '0')}`], 'Case Library')
}
requireTerms(caseLibrary, ['案例编号', '发现版本', '问题描述', '根因', '解决方案', '纳入规则'], 'Case Library')

requireTerms(total, ['PROCESS-006', 'PROCESS-008', 'PROCESS-009', 'PROCESS-010'], 'Unified PROCESS Governance')
requireTerms(goldenPath, ['PROCESS-006-A', 'PROCESS-006-B', 'PROCESS-006-C', 'PROCESS-006-D', 'PROCESS-008'], 'Golden Path')
requireTerms(regression, ['PROCESS-008', 'Contract', 'Page', 'Handoff', 'Golden Path', 'Build'], 'Regression')

console.log('Governance Files PASS')
console.log('Node Template PASS')
console.log('Page Template PASS')
console.log('Approval Template PASS')
console.log('One Page Acceptance PASS')
console.log('Case Library PASS')

const regressionResult = spawnSync(
  process.execPath,
  [
    '--test',
    'tests/acceptance/processRuntimeFrameworkV114288.test.mjs',
    'tests/acceptance/enterpriseScmPurchaseRegressionBaselineV11428182.test.mjs'
  ],
  { cwd: frontendRoot, encoding: 'utf8', stdio: 'pipe' }
)
if (regressionResult.status !== 0) {
  process.stderr.write(regressionResult.stdout ?? '')
  process.stderr.write(regressionResult.stderr ?? '')
  throw new Error('governance regression suite failed')
}
console.log('Regression PASS')

const viteBin = join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
assert.ok(existsSync(viteBin), 'vite is not installed; cannot verify build')
const buildResult = spawnSync(process.execPath, [viteBin, 'build', '.'], {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: 'pipe'
})
if (buildResult.status !== 0) {
  process.stderr.write(buildResult.stdout ?? '')
  process.stderr.write(buildResult.stderr ?? '')
  throw new Error('frontend build failed')
}
console.log('Build PASS')
console.log('PCE_ERP_GOVERNANCE_FRAMEWORK_READY')

