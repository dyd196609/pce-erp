import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import {
  GOVERNANCE_FIRST_STATUS,
  evaluateGovernanceFirstGate,
} from '../src/meta/governance/governanceFirstDevelopment.js'

const VERSION = 'V1.14.2.8.18.10.3.6B'
const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const governanceRoot = path.join(workspaceRoot, 'docs', 'governance')
const governanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '治理符合性检查矩阵.md',
  '问题案例库.md',
  '一页一验收规范.md',
]
const readGovernance = name => fs.readFileSync(path.join(governanceRoot, name), 'utf8')
const governanceFilesLoaded = governanceFiles.every(name => {
  const file = path.join(governanceRoot, name)
  return fs.existsSync(file) && fs.readFileSync(file, 'utf8').trim().length > 0
})

const command = readGovernance(governanceFiles[0])
const general = readGovernance(governanceFiles[1])
const matrix = readGovernance(governanceFiles[2])
const cases = readGovernance(governanceFiles[3])

const unassessed = evaluateGovernanceFirstGate()
const updateOpen = evaluateGovernanceFirstGate({
  existingStandardAssessed: true,
  standardUpdateRequired: true,
  caseUpdateRequired: true,
  matrixUpdateRequired: true,
})
const completed = evaluateGovernanceFirstGate({
  existingStandardAssessed: true,
  standardUpdateRequired: true,
  standardUpdated: true,
  caseUpdateRequired: true,
  caseLibraryUpdated: true,
  matrixUpdateRequired: true,
  matrixUpdated: true,
})

const governanceFirstCheck = unassessed.status === GOVERNANCE_FIRST_STATUS.BLOCKED
  && !unassessed.developmentAllowed
  && updateOpen.status === GOVERNANCE_FIRST_STATUS.BLOCKED
  && !updateOpen.developmentAllowed
  && completed.status === GOVERNANCE_FIRST_STATUS.READY
  && completed.developmentAllowed
const command003 = [
  'CODEX-COMMAND-003',
  '规范先行检查机制（Governance First Check）',
  '是否已有规范覆盖？',
  '是否需要补充规范？',
  '是否需要更新案例库？',
  '是否需要更新验收矩阵？',
  '不得进入开发阶段',
].every(token => command.includes(token)) && matrix.includes('CODEX-COMMAND-003')
const gov001 = general.includes('GOV-001')
  && general.includes('先规范 → 后设计 → 再开发 → 最后验收')
  && matrix.includes('GOV-001')
const requiredFlow = [
  '需求/问题',
  '治理评估',
  '规范检查',
  '规范更新',
  'CODEX任务生成',
  '开发实施',
  '自动验收',
  '人工验收',
  '案例闭环',
].every(token => command.includes(token) && general.includes(token))
const governanceFilesUpdated = command.includes(VERSION)
  && general.includes(VERSION)
  && command003
  && gov001
  && requiredFlow
const governanceMatrixUpdated = matrix.includes(VERSION)
  && matrix.includes('开发前规范更新门禁')
  && matrix.includes('规范先行开发原则')
const caseLibraryUpdated = [
  'CASE-SCM-032',
  '开发动作先于规范归档导致治理遗漏',
  'GOV-001',
  'CODEX-COMMAND-003',
  'PROCESS-010',
  'verifyGovernanceFirstDevelopmentV114281036B.mjs',
].every(token => cases.includes(token))

const regressionRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseGovernanceFirstDevelopmentV114281036B.test.mjs',
  'tests/acceptance/enterpriseCodexHumanFeedbackGovernanceV114281036A.test.mjs',
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
  ['Governance First Check', governanceFirstCheck && requiredFlow],
  ['CODEX-COMMAND-003', command003],
  ['GOV-001', gov001],
  ['Governance Files Updated', governanceFilesUpdated],
  ['Governance Matrix Updated', governanceMatrixUpdated],
  ['Case Library Updated', caseLibraryUpdated],
  ['Regression', regressionRun.status === 0],
  ['Build', buildRun.status === 0],
]

console.log(`Version: ${VERSION}`)
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length
  ? 'PCE_GOVERNANCE_FIRST_DEVELOPMENT_ISSUES_FOUND'
  : 'PCE_GOVERNANCE_FIRST_DEVELOPMENT_READY')
if (failures.length) process.exitCode = 1
