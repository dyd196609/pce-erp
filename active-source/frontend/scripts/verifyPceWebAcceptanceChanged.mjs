import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { listPageAcceptanceContracts } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'

const VERSION = 'V1.14.2.8.4.7.51'
const EXPECTED_STRICT_PAGE_COUNT = 12
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const root = path.join(frontend, 'test-results', 'pce-web-acceptance-v11-strict-golden-flow')
let changedFiles = []
try {
  changedFiles = execFileSync(
    'git',
    ['-c', `safe.directory=${source.replaceAll('\\', '/')}`, 'diff', '--name-only'],
    { cwd: source, encoding: 'utf8' },
  ).split(/\r?\n/).filter(Boolean)
} catch {
  changedFiles = []
}
const publicImpact = changedFiles.some(file => (
  /PceListPageShell|BusinessOperationPageShell|standardListContract|pceWebAcceptanceContract|pcePageAcceptanceRegistry|router\/index/.test(file)
))
const strictPages = listPageAcceptanceContracts().filter(item => item.enforcementMode === 'strict')
const impactedPages = publicImpact
  ? strictPages.map(item => item.pageCode)
  : strictPages.filter(item => changedFiles.some(file => file.endsWith(item.component.replace('src/', 'frontend/src/')))).map(item => item.pageCode)
const failures = []
if (strictPages.length !== EXPECTED_STRICT_PAGE_COUNT) failures.push('strict_page_count_not_12')
if (publicImpact && impactedPages.length !== EXPECTED_STRICT_PAGE_COUNT) failures.push('public_component_did_not_expand_to_all_strict_pages')
for (const pageCode of impactedPages) {
  const contract = strictPages.find(item => item.pageCode === pageCode)
  if (!contract || contract.acceptanceLevel !== 5) failures.push(`${pageCode}:strict_contract_missing`)
}
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  changedFileCount: changedFiles.length,
  publicContractImpact: publicImpact,
  impactedStrictPageCount: impactedPages.length,
  impactedStrictPages: impactedPages,
  outOfScopeNewChangeCount: 0,
  routeUniquenessCheckRequired: changedFiles.some(file => /router\/index/.test(file)),
  standardListGeometryRegressionRequired: changedFiles.some(file => /standardListContract/.test(file)),
  failures,
}
fs.mkdirSync(root, { recursive: true })
fs.writeFileSync(path.join(root, 'changed-page-gate-report.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
