import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { listPceBusinessModules } from '../src/meta/runtime/pceBusinessModuleRegistry.js'
import { validateBusinessNameRegistry } from '../src/meta/governance/businessNameRegistry.js'
import { scanBusinessNameCoverage } from '../src/meta/governance/businessNameCoverageScanner.js'
import { createPageNameConsumerReport, validatePageNameConsumptionGovernance } from '../src/meta/governance/pageNameConsumptionGovernance.js'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const workspaceRoot = path.resolve(frontendRoot, '..')
const readFrontend = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const readWorkspace = relative => fs.readFileSync(path.join(workspaceRoot, relative), 'utf8')
const governanceFiles = ['CODEX执行命令规范.md','PCE-ERP开发治理总规范.md','页面开发模板.md','节点开发模板.md',
  '一页一验收规范.md','问题案例库.md','治理符合性检查矩阵.md','业务名称治理规范.md']
const governanceLoaded = governanceFiles.every(file => readWorkspace(`docs/governance/${file}`).trim())
const commandStandard = readWorkspace('docs/governance/CODEX执行命令规范.md')
const nameStandard = readWorkspace('docs/governance/业务名称治理规范.md')
const matrix = readWorkspace('docs/governance/治理符合性检查矩阵.md')
const cases = readWorkspace('docs/governance/问题案例库.md')
const consumerReportDoc = readWorkspace('docs/governance/Page Name Consumer Report.md')
const registry = validateBusinessNameRegistry()
const coverage = scanBusinessNameCoverage()
const consumption = validatePageNameConsumptionGovernance()
const rows = createPageNameConsumerReport()

const registeredComponents = [...new Set(listPceBusinessModules().map(page => page.pageComponent).filter(Boolean))]
const hardcodedFindings = []
for (const componentFile of registeredComponents) {
  const source = readFrontend(componentFile)
  if (/<h1(?:\s[^>]*)?>\s*[^<{\n][^<\n]*<\/h1>/.test(source)) hardcodedFindings.push({ componentFile, type: 'fixed_h1' })
  if (/data-acceptance-id=["']page-internal-subject-title["'][^>]*>\s*[^<{\n][^<\n]*/.test(source)) hardcodedFindings.push({ componentFile, type: 'fixed_internal_title' })
}
const directTitleWrites = []
const pending = [path.join(frontendRoot, 'src')]
while (pending.length) {
  const current = pending.pop()
  for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
    const target = path.join(current, entry.name)
    if (entry.isDirectory()) pending.push(target)
    else if (/\.(vue|js|ts)$/.test(entry.name) && /document\.title\s*=/.test(fs.readFileSync(target, 'utf8'))) directTitleWrites.push(path.relative(frontendRoot, target))
  }
}
const shell = readFrontend('src/meta/components/PceListPageShell.vue')
const headerConsumer = shell.includes('PceBusinessNameConsumer') && shell.includes('resolvePageNameConsumption')
  && rows.every(row => /(resolvePageNameConsumption|resolveBusinessName|PceBusinessNameConsumer)/.test(readFrontend(row.componentFile)))
const browserTitle = shell.includes('applyConsumedBrowserTitle') && !shell.includes('| PCE-ERP')
  && rows.every(row => row.browserTitle === row.registryName)
const internalTitle = rows.every(row => row.internalTitle === row.registryName)
  && !hardcodedFindings.some(item => item.type === 'fixed_internal_title')
const hardcodedNameScan = hardcodedFindings.length === 0 && directTitleWrites.length === 0

fs.writeFileSync(path.join(frontendRoot, 'page_name_consumer_report_v114281034.json'), `${JSON.stringify({
  version: 'V1.14.2.8.18.10.3.4', ruleCode: 'NAME-GOV-003', result: consumption.result,
  registeredComponentCount: registeredComponents.length, hardcodedFindings, directTitleWrites, rows,
}, null, 2)}\n`)

const acceptanceFiles = ['PURCHASE-REQUEST','INQUIRY-PREPARATION','PURCHASE-INQUIRY','SUPPLIER-QUOTE','QUOTE-COMPARISON',
  'WMS-INBOUND','QMS-INSPECTION','PURCHASE-APPROVAL','FIN-PAYABLE-PREPARE']
const process009 = acceptanceFiles.every(name => {
  const content = readWorkspace(`docs/acceptance/PAGE-NAME-CONSUMPTION-${name}.md`)
  return content.includes('URL：') && content.includes('页面名称：') && content.includes('名称来源：`BusinessNameRegistry`')
    && content.includes('检查项：') && content.includes('页面证据：') && content.includes('结果：PASS')
})
const testRun = spawnSync(process.execPath, ['--test',
  'tests/acceptance/enterprisePageNameConsumptionGovernanceV114281034.test.mjs',
  'tests/acceptance/enterpriseBusinessNameConsistencyGovernanceV114281033.test.mjs',
  'tests/acceptance/enterpriseBusinessNameApprovalBindingV114281032.test.mjs',
], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore','pipe','pipe'] })
const vite = path.join(frontendRoot, 'node_modules', 'vite', 'bin', 'vite.js')
const buildRun = spawnSync(process.execPath, [vite, 'build', '.'], { cwd: frontendRoot, encoding: 'utf8', stdio: ['ignore','pipe','pipe'] })
for (const run of [testRun, buildRun]) if (run.status !== 0) process.stderr.write(`${run.stdout || ''}${run.stderr || ''}`)

const checks = [
  ['Governance Files Loaded', governanceLoaded],
  ['CODEX-COMMAND-001', commandStandard.includes('CODEX-COMMAND-001') && commandStandard.includes('失败阻断规范')],
  ['NAME-GOV-001', registry.result === 'PASS' && nameStandard.includes('NAME-GOV-001')],
  ['NAME-GOV-002', coverage.result === 'PASS' && nameStandard.includes('NAME-GOV-002')],
  ['NAME-GOV-003', consumption.result === 'PASS' && nameStandard.includes('NAME-GOV-003') && matrix.includes('NAME-GOV-003')],
  ['CASE-SCM-028', cases.includes('CASE-SCM-028') && cases.includes('NAME-GOV-002')],
  ['CASE-SCM-029', cases.includes('CASE-SCM-029') && cases.includes('PceBusinessNameConsumer')],
  ['BusinessNameRegistry', registry.result === 'PASS'],
  ['Header Consumer', headerConsumer],
  ['Browser Title', browserTitle],
  ['Internal Title', internalTitle],
  ['Hardcoded Name Scan', hardcodedNameScan && consumerReportDoc.includes('固定业务 `<h1>`')],
  ['PROCESS-009', process009],
  ['Regression', testRun.status === 0],
  ['Build', buildRun.status === 0],
]
for (const [label, passed] of checks) console.log(`${label} ${passed ? 'PASS' : 'FAIL'}`)
const failures = checks.filter(([, passed]) => !passed).map(([label]) => label)
if (failures.length) {
  console.log('Issues:')
  failures.forEach((label, index) => console.log(`${index + 1}. ${label}: 页面名称消费证据或构建失败，请修复后重跑。`))
}
console.log(failures.length ? 'PCE_PAGE_NAME_CONSUMPTION_GOVERNANCE_ISSUES_FOUND' : 'PCE_PAGE_NAME_CONSUMPTION_GOVERNANCE_READY')
if (failures.length) process.exitCode = 1
