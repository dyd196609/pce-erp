import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateBusinessNameRegistry } from '../src/meta/governance/businessNameRegistry.js'
import { scanBusinessNameCoverage } from '../src/meta/governance/businessNameCoverageScanner.js'
import { validatePageNameConsumptionGovernance } from '../src/meta/governance/pageNameConsumptionGovernance.js'
import { createPageShellNameSourceReport, validatePageShellNameGovernance } from '../src/meta/governance/pageShellNameGovernance.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
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
const shellReportDoc = readWorkspace('docs/governance/Page Shell Name Source Report.md')

const registry = validateBusinessNameRegistry()
const coverage = scanBusinessNameCoverage()
const consumption = validatePageNameConsumptionGovernance()
const shellGovernance = validatePageShellNameGovernance()
const rows = createPageShellNameSourceReport()

const shell = readFrontend('src/meta/components/PceListPageShell.vue')
const router = readFrontend('src/router/index.js')
const shellHeaderConsumer = shell.includes('data-name-source="BusinessNameRegistry"')
  && shell.includes('PceBusinessNameConsumer')
  && shell.includes('resolvePageNameConsumption')
  && shell.includes('nameConsumption.moduleCode')
  && shell.includes('nameConsumption.businessObject')
const contentHeaderConsumer = consumption.result === 'PASS'
  && rows.every(row => row.contentHeaderName === row.registryName)
const browserTitle = rows.every(row => row.browserTitle === row.registryName)
  && shell.includes('applyConsumedBrowserTitle(nameConsumption.value)')
const forbiddenShellTokens = [
  'fallbackTitle',
  'resolvePceCanonicalName',
  'governedPage.value?.pageName',
  'governedPage.pageName',
  'config.pageTitle',
]
const hardcodedShellFindings = forbiddenShellTokens.filter(token => shell.includes(token))
if (/fallbackTitle\s*:/.test(router)) hardcodedShellFindings.push('router:fallbackTitle')
const shellFiles = [
  'src/meta/components/PceListPageShell.vue',
  'src/meta/components/PceDetailPageShell.vue',
  'src/meta/components/PceFormPageShell.vue',
  'src/meta/components/PceProcessPageShell.vue',
  'src/meta/components/BusinessOperationPageShell.vue',
]
for (const file of shellFiles) {
  const source = readFrontend(file)
  if (/(?:headerTitle|moduleTitle|displayTitle)\s*[:=]\s*['"][^'"]+['"]/.test(source)) hardcodedShellFindings.push(`${file}:local-title`)
  if (/<h1(?:\s[^>]*)?>\s*[^<{\n][^<\n]*<\/h1>/.test(source)) hardcodedShellFindings.push(`${file}:fixed-h1`)
}

fs.writeFileSync(path.join(frontendRoot, 'page_shell_name_source_report_v114281035.json'), `${JSON.stringify({
  version: 'V1.14.2.8.18.10.3.5',
  ruleCode: 'NAME-GOV-004',
  result: shellGovernance.result,
  sourceChain: ['PCE Enterprise Page V2', 'PceListPageShell', 'resolvePageNameConsumption', 'BusinessNameRegistry'],
  hardcodedShellFindings,
  rows,
}, null, 2)}\n`)

const acceptanceFiles = [
  'PURCHASE-REQUEST', 'INQUIRY-PREPARATION', 'PURCHASE-INQUIRY', 'SUPPLIER-QUOTE', 'QUOTE-COMPARISON',
  'WMS-INBOUND', 'QMS-INSPECTION', 'PURCHASE-APPROVAL', 'FIN-PAYABLE-PREPARE',
]
const process009 = acceptanceFiles.every(name => {
  const content = readWorkspace(`docs/acceptance/PAGE-SHELL-NAME-${name}.md`)
  return content.includes('URL：')
    && content.includes('页面名称：')
    && content.includes('名称来源：`BusinessNameRegistry`')
    && content.includes('NAME-GOV-004')
    && content.includes('结果：PASS')
})

const testRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterprisePageShellNameGovernanceV114281035.test.mjs',
  'tests/acceptance/enterprisePageNameConsumptionGovernanceV114281034.test.mjs',
  'tests/acceptance/enterpriseBusinessNameConsistencyGovernanceV114281033.test.mjs',
  'tests/acceptance/enterpriseBusinessNameApprovalBindingV114281032.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] })
for (const run of [testRun, buildRun]) {
  if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)
}

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['CODEX-COMMAND-001', commandStandard.includes('CODEX-COMMAND-001') && commandStandard.includes('失败阻断规范')],
  ['NAME-GOV-001', registry.result === 'PASS' && nameStandard.includes('NAME-GOV-001')],
  ['NAME-GOV-002', coverage.result === 'PASS' && nameStandard.includes('NAME-GOV-002')],
  ['NAME-GOV-003', consumption.result === 'PASS' && nameStandard.includes('NAME-GOV-003')],
  ['NAME-GOV-004', shellGovernance.result === 'PASS' && nameStandard.includes('NAME-GOV-004') && matrix.includes('NAME-GOV-004')],
  ['CASE-SCM-028', cases.includes('CASE-SCM-028') && cases.includes('NAME-GOV-002')],
  ['CASE-SCM-029', cases.includes('CASE-SCM-029') && cases.includes('PceBusinessNameConsumer')],
  ['CASE-SCM-030', cases.includes('CASE-SCM-030') && cases.includes('NAME-GOV-004')],
  ['BusinessNameRegistry', registry.result === 'PASS'],
  ['Shell Header Consumer', shellHeaderConsumer],
  ['Content Header Consumer', contentHeaderConsumer],
  ['Browser Title', browserTitle],
  ['Hardcoded Shell Name Scan', hardcodedShellFindings.length === 0 && shellReportDoc.includes('fallbackTitle/headerTitle/moduleTitle/displayTitle')],
  ['PROCESS-009', process009],
  ['Regression', testRun.status === 0],
  ['Build', buildRun.status === 0],
]

for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}: 页面壳名称来源、验收证据或构建未通过。`))
}
console.log(failures.length ? 'PCE_PAGE_SHELL_NAME_GOVERNANCE_ISSUES_FOUND' : 'PCE_PAGE_SHELL_NAME_GOVERNANCE_READY')
if (failures.length) process.exitCode = 1
