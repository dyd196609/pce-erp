import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateBusinessNameRegistry } from '../src/meta/governance/businessNameRegistry.js'
import { scanBusinessNameCoverage } from '../src/meta/governance/businessNameCoverageScanner.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')
const governanceFiles = [
  'CODEX执行命令规范.md',
  'PCE-ERP开发治理总规范.md',
  '页面开发模板.md',
  '节点开发模板.md',
  '一页一验收规范.md',
  '问题案例库.md',
  '治理符合性检查矩阵.md',
  '业务名称治理规范.md',
]
const governanceLoaded = governanceFiles.every(file => readWorkspace(`docs/governance/${file}`).trim())
const commandStandard = readWorkspace('docs/governance/CODEX执行命令规范.md')
const nameStandard = readWorkspace('docs/governance/业务名称治理规范.md')
const matrix = readWorkspace('docs/governance/治理符合性检查矩阵.md')
const cases = readWorkspace('docs/governance/问题案例库.md')
const sourceReport = readWorkspace('docs/governance/Business Name Source Report.md')
const registryValidation = validateBusinessNameRegistry()
const scan = scanBusinessNameCoverage()

fs.writeFileSync(path.join(frontendRoot, 'business_name_source_report_v114281033.json'), `${JSON.stringify({
  version: 'V1.14.2.8.18.10.3.3',
  ruleCode: scan.ruleCode,
  result: scan.result,
  registeredPageCount: scan.registeredPageCount,
  discoveredPageCount: scan.discoveredPageCount,
  sourceRecordCount: scan.sourceRecordCount,
  modules: scan.modules,
  rows: scan.rows,
}, null, 2)}\n`)

const acceptanceRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseBusinessNameConsistencyGovernanceV114281033.test.mjs',
  'tests/acceptance/enterpriseBusinessNameApprovalBindingV114281032.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore','pipe','pipe'] })
const regression = acceptanceRun.status === 0
const acceptanceFiles = [
  'PAGE-PDE-MANUFACTURING-OUTPUT-NAME.md',
  'PAGE-WMS-INBOUND-NAME.md',
  'PAGE-QMS-INCOMING-INSPECTION-NAME.md',
  'PAGE-FIN-PAYABLE-PREPARE-NAME.md',
  'PAGE-SCM-PURCHASE-INQUIRY-NAME.md',
]
const process009 = acceptanceFiles.every(file => {
  const content = readWorkspace(`docs/acceptance/${file}`)
  return content.includes('URL：') && content.includes('页面名称：') && content.includes('名称来源：`BusinessNameRegistry`')
    && content.includes('Registry 字段：') && content.includes('页面证据：') && content.includes('结果：PASS')
})
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore','pipe','pipe'] })
for (const run of [acceptanceRun, buildRun]) {
  if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)
}

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['CODEX-COMMAND-001', commandStandard.includes('CODEX-COMMAND-001') && commandStandard.includes('失败阻断规范')],
  ['NAME-GOV-001', registryValidation.result === 'PASS' && nameStandard.includes('NAME-GOV-001')],
  ['NAME-GOV-002', scan.result === 'PASS' && nameStandard.includes('NAME-GOV-002') && matrix.includes('NAME-GOV-002')],
  ['CASE-SCM-023', cases.includes('CASE-SCM-023') && cases.includes('NAME-GOV-002 可执行全局门禁')],
  ['CASE-SCM-026', cases.includes('CASE-SCM-026') && cases.includes('统一消费 BusinessNameRegistry')],
  ['CASE-SCM-028', cases.includes('CASE-SCM-028') && cases.includes('84 个唯一业务路由')],
  ['BusinessNameRegistry', registryValidation.result === 'PASS' && registryValidation.recordCount === 84],
  ['Process Name Consistency', scan.rows.filter(row => row.source === 'ProcessRegistry').every(row => row.result === 'PASS')],
  ['Page Name Consistency', scan.rows.filter(row => row.source.includes('PageIdentityRegistry')).every(row => row.result === 'PASS')],
  ['Browser Title Consistency', scan.rows.every(row => row.browserTitle === row.pageTitle)],
  ['Business Object Name Consistency', registryValidation.aligned && sourceReport.includes('业务对象')],
  ['PROCESS-009', process009],
  ['Regression', regression],
  ['Build', buildRun.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}: 名称来源、覆盖证据或构建失败；请修复后重跑本脚本。`))
}
console.log(failures.length ? 'PCE_GLOBAL_BUSINESS_NAME_GOVERNANCE_ISSUES_FOUND' : 'PCE_GLOBAL_BUSINESS_NAME_GOVERNANCE_READY')
if (failures.length) process.exitCode = 1
