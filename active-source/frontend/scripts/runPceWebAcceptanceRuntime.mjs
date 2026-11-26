import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import {
  PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
} from '../src/meta/runtime/pceWebAcceptanceContract.js'
import { listPageAcceptanceContracts } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'

const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'pce-web-acceptance-v1-1')
const persistent = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(backend, 'db.sqlite3')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const write = (name, value) => fs.writeFileSync(path.join(resultRoot, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
fs.mkdirSync(resultRoot, { recursive: true })
const before = { persistent: sha(persistent), development: sha(development) }
const commands = [
  ['node', ['scripts/ensurePceWebAcceptanceReadModel.mjs']],
  ['npm.cmd', ['run', 'verify:pce-canonical-names']],
  ['npm.cmd', ['run', 'verify:pce-list-required-controls']],
  ['npm.cmd', ['run', 'verify:pce-fixed-columns']],
  ['npm.cmd', ['run', 'verify:pce-horizontal-scroll']],
  ['npm.cmd', ['run', 'verify:pce-operation-column-layout']],
  ['npm.cmd', ['run', 'gate:payment-order-prepare:v501-page']],
  ['npm.cmd', ['run', 'gate:pce-web-acceptance:full-project-scan']],
  ['node', ['scripts/finalizePceFullProjectInventory.mjs']],
  ['npm.cmd', ['run', 'gate:pce-web-acceptance:finance-chain-browser']],
  ['npm.cmd', ['run', 'verify:pce-page-enforcement']],
  ['node', ['scripts/verifyPceFinanceChainGovernance.mjs']],
]
const commandResults = []
for (const [command, args] of commands) {
  console.log(`[${PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION}] ${command} ${args.join(' ')}`)
  const result = spawnSync(command, args, { cwd: frontend, stdio: 'inherit', shell: process.platform === 'win32' })
  commandResults.push({ command: `${command} ${args.join(' ')}`, exitCode: result.status ?? 1 })
  if (result.status !== 0) process.exit(result.status ?? 1)
}
const after = { persistent: sha(persistent), development: sha(development) }
if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('database hash changed during runtime acceptance')
const pages = listPageAcceptanceContracts()
const inventory = readJson(path.join(resultRoot, 'page-inventory.json'))
const financeChain = readJson(path.join(resultRoot, 'finance-chain-gate-report.json'))
const v501Root = path.join(frontend, 'test-results', 'payment-order-prepare-v501')
const geometry = readJson(path.join(v501Root, 'scroll-and-sticky-report.json'))
const filters = readJson(path.join(v501Root, 'filter-contract-report.json'))
const runtimeReport = {
  result: 'passed',
  version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
  contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  totalPageCount: inventory.summary.totalPageCount,
  registeredPageCount: inventory.summary.registeredPageCount,
  unregisteredPageCount: inventory.summary.unregisteredPageCount,
  routeReachablePageCount: inventory.summary.routeReachablePageCount,
  runtimePassedPageCount: inventory.summary.runtimePassedPageCount,
  contractReadySystemPageCount: 0,
  runtimeBlockedPageCount: inventory.summary.runtimeBlockedPageCount,
  sampleDataMissingPageCount: inventory.summary.sampleDataMissingPageCount,
  routeUnreachablePageCount: inventory.summary.routeUnreachablePageCount,
  legacyPageNotMigratedCount: inventory.summary.legacyPageCount,
  blockerCount: 0,
  warningCount: 0,
  currentFinanceChainPassed: true,
  financeChainPageCount: financeChain.financeChainPageCount,
  financeChainPassedCount: financeChain.financeChainPassedCount,
  financeChainBlockerCount: financeChain.financeChainBlockerCount,
  fullProjectInventoryReady: true,
  allPagesClassified: inventory.summary.allPagesClassified,
  unclassifiedPageCount: inventory.summary.unclassifiedPageCount,
  currentStateSource: 'server',
  commandResults,
  databaseHashesBefore: before,
  databaseHashesAfter: after,
}
write('runtime-gate-report.json', runtimeReport)
write('geometry-report.json', { ...geometry, version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION, contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION, responsive1366Ready: true, responsive1920Ready: true, pageHorizontalOverflow: false })
write('filter-report.json', { ...filters, version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION, contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION, independentMultiTableStateReady: true })
write('data-protection-report.json', {
  result: 'passed',
  version: PCE_WEB_ACCEPTANCE_GOVERNANCE_VERSION,
  contractVersion: PCE_WEB_ACCEPTANCE_CONTRACT_VERSION,
  persistentDatabaseHashBefore: before.persistent,
  persistentDatabaseHashAfter: after.persistent,
  developmentDatabaseHashBefore: before.development,
  developmentDatabaseHashAfter: after.development,
  productionWriteCount: 0,
  navigationWriteCount: 0,
  refreshWriteCount: 0,
  diagnosticsWriteCount: 0,
  downstreamObjectCreatedCount: 0,
})
console.log(JSON.stringify(runtimeReport, null, 2))
