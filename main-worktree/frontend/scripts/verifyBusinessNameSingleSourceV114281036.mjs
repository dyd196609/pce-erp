import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { validateBusinessNameSingleSourceGovernance } from '../src/meta/governance/businessNameSingleSourceGovernance.js'

const VERSION = 'V1.14.2.8.18.10.3.6'
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
const secondSourceReport = readWorkspace('docs/governance/Second Name Source Report.md')
const acceptance = readWorkspace('docs/acceptance/PAGE-BUSINESS-NAME-SINGLE-SOURCE-V114281036.md')

const router = readFrontend('src/router/index.js')
const cockpit = readFrontend('src/meta/shell/ProfitCockpit.vue')
const wms = readFrontend('src/meta/pages/WmsPage.vue')
const titleManager = readFrontend('src/meta/runtime/pageTitleManager.js')
const businessModules = readFrontend('src/meta/runtime/pceBusinessModuleRegistry.js')
const shell = readFrontend('src/meta/components/PceListPageShell.vue')
const validation = validateBusinessNameSingleSourceGovernance()

const routerFindings = []
if (/meta\s*:\s*\{[^}]*\btitle\s*:/s.test(router)) routerFindings.push('router:meta.title')
if (/meta\s*:\s*\{[^}]*\bpageName\s*:/s.test(router)) routerFindings.push('router:meta.pageName')
if (/route\.meta\??\.title/.test(router) || /route\.meta\??\.title/.test(cockpit)) routerFindings.push('consumer:route.meta.title')

const fallbackFindings = []
if (/resolvePceCanonicalNameByRoute|findBusinessProcessStepByRoutePath|routeTitleMap/.test(titleManager)) fallbackFindings.push('pageTitleManager:fallback')
if (/resolvePceCanonicalNameByRoute|currentList\.value\?\.title/.test(wms)) fallbackFindings.push('WmsPage:fallback')
const inventoryDefinition = businessModules.match(/moduleId:\s*'inventory-balances'[\s\S]*?route:\s*'\/wms\/inventory-balances'/)?.[0] || ''
if (!inventoryDefinition || /canonicalName\s*:/.test(inventoryDefinition)) fallbackFindings.push('pceBusinessModuleRegistry:inventory-canonicalName')

const routerNameSource = routerFindings.length === 0
const shellNameSource = shell.includes('resolvePageNameConsumption')
  && shell.includes('data-name-source="BusinessNameRegistry"')
  && !shell.includes('fallbackTitle')
const contentHeaderName = validation.shell.rows.every(row => row.contentHeaderName === row.registryName
  && row.contentHeaderNameSource === 'BusinessNameRegistry')
const browserTitle = validation.shell.rows.every(row => row.browserTitle === row.registryName
  && row.browserTitleNameSource === 'BusinessNameRegistry')
  && titleManager.includes('resolveBusinessName({ route: path })')
const runtimeAssertion = validation.result === 'PASS'

const jsonReport = {
  version: VERSION,
  result: routerFindings.length === 0 && fallbackFindings.length === 0 && runtimeAssertion ? 'PASS' : 'FAIL',
  uniqueSource: 'BusinessNameRegistry',
  sourceChain: ['BusinessNameRegistry', 'Process Center', 'Node Identity', 'Router', 'Page Shell', 'Content Header', 'Browser Title'],
  routerFindings,
  fallbackFindings,
  runtimeRows: validation.shell.rows,
}
fs.writeFileSync(path.join(frontendRoot, 'second_name_source_report_v114281036.json'), `${JSON.stringify(jsonReport, null, 2)}\n`)

const testRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterpriseBusinessNameSingleSourceV114281036.test.mjs',
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

const rulesDocumented = code => nameStandard.includes(code) && matrix.includes(code)
const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['CODEX-COMMAND-001', commandStandard.includes('CODEX-COMMAND-001')],
  ['NAME-GOV-001', rulesDocumented('NAME-GOV-001') && validation.registry.result === 'PASS'],
  ['NAME-GOV-002', rulesDocumented('NAME-GOV-002') && validation.registry.result === 'PASS'],
  ['NAME-GOV-003', rulesDocumented('NAME-GOV-003') && validation.consumption.result === 'PASS'],
  ['NAME-GOV-004', rulesDocumented('NAME-GOV-004') && validation.shell.result === 'PASS'],
  ['NAME-GOV-005', rulesDocumented('NAME-GOV-005') && routerNameSource],
  ['NAME-GOV-006', rulesDocumented('NAME-GOV-006') && fallbackFindings.length === 0],
  ['CASE-WMS-001', cases.includes('CASE-WMS-001') && cases.includes(VERSION) && cases.includes('关闭')],
  ['Second Name Source Scan', routerFindings.length === 0 && fallbackFindings.length === 0 && secondSourceReport.includes('PASS')],
  ['Router Name Source', routerNameSource],
  ['Shell Name Source', shellNameSource],
  ['Content Header Name', contentHeaderName],
  ['Browser Title', browserTitle],
  ['Runtime Name Assertion', runtimeAssertion],
  ['PROCESS-009', acceptance.includes('PROCESS-009') && acceptance.includes('PASS')],
  ['Regression', testRun.status === 0],
  ['Build', buildRun.status === 0],
]

console.log(`Version ${VERSION}`)
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}`))
}
console.log(failures.length ? 'PCE_BUSINESS_NAME_SINGLE_SOURCE_ISSUES_FOUND' : 'PCE_BUSINESS_NAME_SINGLE_SOURCE_READY')
if (failures.length) process.exitCode = 1
