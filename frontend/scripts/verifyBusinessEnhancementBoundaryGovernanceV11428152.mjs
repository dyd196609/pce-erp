import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const run = args => spawnSync(process.execPath, args, {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
const read = file => fs.readFileSync(path.join(governanceRoot, file), 'utf8')

const governanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '统一列表运行层规范.md',
  '页面开发模板.md',
  '一页一验收规范.md',
  '治理符合性检查矩阵.md',
  '问题案例库.md',
]
const governanceLoaded = governanceFiles.every(file => {
  const target = path.join(governanceRoot, file)
  return fs.existsSync(target) && fs.readFileSync(target, 'utf8').trim().length > 0
}) && read('CODEX执行命令规范.md').includes('人工验收反向校验机制')

const boundary = read('业务增强版本修改边界规范.md')
const development = read('PCE-ERP开发治理总规范.md')
const command = read('CODEX执行命令规范.md')
const cases = read('问题案例库.md')
const matrix = read('治理符合性检查矩阵.md')

const boundaryRuleDocument = [
  '业务增强版本定义', '业务模型', 'Provider', '页面业务区域',
  'List Runtime', 'Page Shell', 'Process Center', '公共组件',
  '治理评估', '影响范围报告', '公共页面自动回归', '真实页面人工验收',
].every(value => boundary.includes(value))
const developmentUpdated = development.includes('业务增强版本修改边界')
  && ['GOV-001', 'PROCESS-008', 'PROCESS-010'].every(value => development.includes(value))
const commandUpdated = command.includes('CODEX-COMMAND-004')
  && ['业务增强版本', '平台能力版本', '公共组件版本',
    'List Runtime', 'Page Shell', 'Process Center', '公共组件']
    .every(value => command.includes(value))
const caseUpdated = cases.includes('CASE-GOV-001')
  && cases.includes('业务增强误修改公共层导致系统回归')
  && cases.includes('V1.14.2.8.18.15')
  && matrix.includes('BUSINESS-ENHANCEMENT-BOUNDARY-001')

const boundaryTests = run(['--test',
  'tests/acceptance/businessEnhancementBoundaryGovernanceV11428152.test.mjs',
  'tests/acceptance/enterpriseGovernanceFirstDevelopmentV114281036B.test.mjs',
  'tests/acceptance/enterpriseCodexHumanFeedbackGovernanceV114281036A.test.mjs',
])
const priorRegression = run(['scripts/verifyV11428151RegressionRecovery.mjs'])
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const build = run([vite, 'build', '.'])

for (const result of [boundaryTests, priorRegression, build]) {
  if (result.status !== 0) process.stderr.write(`${result.stdout || ''}${result.stderr || ''}`)
}

const regression = boundaryTests.status === 0 && priorRegression.status === 0
  && priorRegression.stdout.includes('SCM_PRICE_CONTEXT_REGRESSION_FIXED')
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['Boundary Rule Document', boundaryRuleDocument && boundaryTests.status === 0],
  ['Development Governance Updated', developmentUpdated],
  ['CODEX Command Rule Updated', commandUpdated],
  ['Problem Case Updated', caseUpdated],
  ['Regression', regression],
  ['Build', build.status === 0],
]
const automaticAcceptance = checks.every(([, passed]) => passed)

console.log('Version: V1.14.2.8.18.15.2')
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
console.log(`Automatic Acceptance ${automaticAcceptance ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(automaticAcceptance
  ? 'BUSINESS_ENHANCEMENT_BOUNDARY_GOVERNANCE_READY'
  : 'BUSINESS_ENHANCEMENT_BOUNDARY_GOVERNANCE_ISSUES_FOUND')
if (!automaticAcceptance) process.exitCode = 1
