import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  CODEX_ACCEPTANCE_STATUS,
  evaluateCodexAcceptanceGate,
} from '../src/meta/governance/codexHumanFeedbackGovernance.js'

const VERSION = 'V1.14.2.8.18.10.3.6A'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')

const governanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '治理符合性检查矩阵.md',
  '问题案例库.md',
  '一页一验收规范.md',
]
const governanceFilesLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const commandStandard = readGovernance('CODEX执行命令规范.md')
const general = readGovernance('PCE-ERP开发治理总规范.md')
const matrix = readGovernance('治理符合性检查矩阵.md')
const cases = readGovernance('问题案例库.md')
const pageAcceptance = readGovernance('一页一验收规范.md')

const autoPassHumanFail = evaluateCodexAcceptanceGate({
  automaticAcceptance: 'PASS',
  humanAcceptance: 'FAIL',
})
const feedbackOpen = evaluateCodexAcceptanceGate({
  automaticAcceptance: 'PASS',
  humanAcceptance: 'PASS',
  humanFeedbackRequired: true,
  humanFeedbackClosed: false,
})
const feedbackClosed = evaluateCodexAcceptanceGate({
  automaticAcceptance: 'PASS',
  humanAcceptance: 'PASS',
  humanFeedbackRequired: true,
  humanFeedbackClosed: true,
})

const commandStandardUpdated = [
  'CODEX-COMMAND-002',
  '人工验收反向校验机制',
  'AUTO_PASS_HUMAN_FAIL',
  '自动验收不能替代人工验收',
  'Automatic Acceptance:',
  'Human Acceptance:',
  'Human Feedback Closed:',
  'Final Status:',
].every(token => commandStandard.includes(token))
const reverseFlowDocumented = [
  '建立诊断版本',
  '定位根因',
  '完善执行规则',
  '建立新规范',
  '更新问题案例库',
  '更新自动验收',
  '人工复验',
].every(token => commandStandard.includes(token))
const command001 = commandStandard.includes('CODEX-COMMAND-001')
const command002 = commandStandardUpdated
  && reverseFlowDocumented
  && autoPassHumanFail.status === CODEX_ACCEPTANCE_STATUS.AUTO_PASS_HUMAN_FAIL
  && !autoPassHumanFail.readyEligible
  && !autoPassHumanFail.publishAllowed
  && feedbackOpen.status === CODEX_ACCEPTANCE_STATUS.HUMAN_FEEDBACK_OPEN
  && !feedbackOpen.readyEligible
  && feedbackClosed.status === CODEX_ACCEPTANCE_STATUS.READY_ELIGIBLE
  && feedbackClosed.readyEligible
const process010 = general.includes('PROCESS-010')
  && cases.includes('PROCESS-010')
  && cases.includes('CODEX-COMMAND-002')
const process009 = matrix.includes('PROCESS-009')
  && pageAcceptance.includes('CODEX-COMMAND-002')
  && pageAcceptance.includes('AUTO_PASS_HUMAN_FAIL')
const case031 = cases.includes('CASE-SCM-031')
  && cases.includes('V1.14.2.8.18.10.3.x')
  && cases.includes('AUTO_PASS_HUMAN_FAIL')
  && cases.includes('verifyCodexHumanFeedbackGovernanceV114281036A.mjs')
const matrixUpdated = matrix.includes('CODEX-COMMAND-002')
  && matrix.includes('自动 PASS、人工 FAIL')
  && matrix.includes('流程正反向检查')

const regressionRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseCodexHumanFeedbackGovernanceV114281036A.test.mjs',
  'tests/acceptance/enterpriseBusinessNameSingleSourceV114281036.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'], {
  cwd: frontendRoot,
  encoding: 'utf8',
  stdio: ['ignore', 'pipe', 'pipe'],
})
for (const run of [regressionRun, buildRun]) {
  if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)
}

const checks = [
  ['Governance Files Loaded', governanceFilesLoaded],
  ['CODEX-COMMAND-001', command001],
  ['CODEX-COMMAND-002', command002],
  ['PROCESS-010', process010],
  ['PROCESS-009', process009],
  ['CASE-SCM-031', case031],
  ['Command Standard Updated', commandStandardUpdated && reverseFlowDocumented],
  ['Governance Matrix Updated', matrixUpdated],
  ['Case Library Updated', case031],
  ['Regression', regressionRun.status === 0],
  ['Build', buildRun.status === 0],
]

console.log(`Version ${VERSION}`)
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length
  ? 'PCE_CODEX_HUMAN_FEEDBACK_GOVERNANCE_ISSUES_FOUND'
  : 'PCE_CODEX_HUMAN_FEEDBACK_GOVERNANCE_READY')
if (failures.length) process.exitCode = 1
