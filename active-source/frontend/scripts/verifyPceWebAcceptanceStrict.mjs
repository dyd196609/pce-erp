import crypto from 'node:crypto'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { listPageAcceptanceContracts } from '../src/meta/runtime/pcePageAcceptanceRegistry.js'

const VERSION = 'V1.14.2.8.4.7.50.3'
const CONTRACT_VERSION = 'PCE-WEB-ACCEPTANCE-V1.1'
const frontend = path.resolve(import.meta.dirname, '..')
const source = path.resolve(frontend, '..')
const root = path.join(frontend, 'test-results', 'pce-web-acceptance-v11-strict-golden-flow')
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const core = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const read = file => fs.readFileSync(file, 'utf8')
const expected = [
  ['payable-prepare', 'FIN_PAYABLE_PREPARE', '采购应付预备', '/finance/payable-prepares', 'V1.14.2.8.4.7.32'],
  ['payable-check', 'FIN_PAYABLE_CHECK', '采购应付核对', '/finance/payable-checks', 'V1.14.2.8.4.7'],
  ['supplier-settlement', 'SCM_SUPPLIER_SETTLEMENT', '供应商结算', '/scm/supplier-settlements', 'V1.14.2.8.4.7'],
  ['purchase-reconciliation', 'SCM_PURCHASE_RECONCILIATION', '采购对账', '/scm/purchase-reconciliations', 'V1.14.2.8.4.7.42'],
  ['invoice-prepare', 'FIN_INVOICE_PREPARE', '采购发票准备', '/finance/purchase-invoice-prepares', 'V1.14.2.8.4.7.43.1'],
  ['account-payable-draft', 'FIN_AP_DRAFT', '采购应付账款草稿', '/finance/ap-drafts', 'V1.14.2.8.4.7.45.3'],
  ['account-payable-confirm', 'FIN_AP_CONFIRM', '应付确认准备', '/finance/account-payable-confirms', 'V1.14.2.8.4.7.46'],
  ['payment-application', 'FIN_PAYMENT_APPLICATION', '付款申请准备', '/finance/payment-applications', 'V1.14.2.8.4.7.47.2'],
  ['payment-request', 'FIN_PAYMENT_REQUEST', '付款申请', '/finance/payment-requests', 'V1.14.2.8.4.7.48'],
  ['payment-instruction-prepare', 'FIN_PAYMENT_INSTRUCTION_PREPARE', '付款指令准备', '/finance/payment-order-prepares', 'V1.14.2.8.4.7.49.1'],
  ['payment-order-prepare', 'FIN_PAYMENT_ORDER_PREPARE', '正式付款单预备', '/finance/payment-prepares', 'V1.14.2.8.4.7.50.1'],
]
const contracts = new Map(listPageAcceptanceContracts().map(item => [item.pageCode, item]))
const router = read(path.join(frontend, 'src', 'router', 'index.js'))
const shell = read(path.join(frontend, 'src', 'meta', 'components', 'PceListPageShell.vue'))
const operationShell = read(path.join(frontend, 'src', 'meta', 'components', 'BusinessOperationPageShell.vue'))
const failures = []
const results = expected.map(([pageCode, moduleCode, canonicalName, route, businessVersion], index) => {
  const contract = contracts.get(pageCode)
  const checks = {
    registered: Boolean(contract),
    moduleCode: contract?.moduleCode === moduleCode,
    canonicalName: contract?.canonicalName === canonicalName,
    route: contract?.route === route,
    businessVersion: contract?.businessVersion === businessVersion,
    migrationVersion: contract?.acceptanceMigrationVersion === VERSION,
    contractVersion: contract?.contractVersion === CONTRACT_VERSION,
    strict: contract?.enforcementMode === 'strict',
    level5: contract?.acceptanceLevel === 5,
    pageType: contract?.pageType === 'list',
    planNotApplicable: contract?.planRules?.notApplicable === true && Boolean(contract?.planRules?.reason),
    fourLevelInheritance: contract?.inheritanceContract?.fourLevelInheritanceRequired === true,
    processPrevious: index === 0 || contract?.process?.previousModuleCode === expected[index - 1][0],
    processCurrent: contract?.process?.currentModuleCode === pageCode,
    processNext: contract?.process?.nextModuleCode === (expected[index + 1]?.[0] || 'payment-order-draft'),
    routerIdentity: router.includes(`'${route.slice(1)}'`) && router.includes(contract?.routeName || '__missing__'),
  }
  const blockers = Object.entries(checks).filter(([, passed]) => !passed).map(([name]) => name)
  if (blockers.length) failures.push({ pageCode, blockers })
  return { pageCode, moduleCode, canonicalName, route, businessVersion, checks, blockers, result: blockers.length ? 'failed' : 'passed' }
})

for (const [name, condition] of Object.entries({
  commonShell: shell.includes('data-pce-shell-type="PceListPageShell"'),
  moduleMainProcess: shell.includes('data-acceptance-id="module-main-process"'),
  processNavigation: shell.includes('data-acceptance-id="business-process-navigation"'),
  pageActionBar: shell.includes('data-acceptance-id="page-observability-action-bar"'),
  strictServerFacts: shell.includes('PceStrictServerFactsPanel'),
  noMountedDuplicateUnifiedNavigation: operationShell.includes('v-if="false"'),
})) if (!condition) failures.push({ pageCode: 'global', blockers: [name] })

const persistent = path.join(source, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const development = path.join(source, 'backend', 'db.sqlite3')
const databaseHashes = { persistent: sha(persistent), development: sha(development) }
if (databaseHashes.persistent !== 'f59513f0c7fb48c7a6ed7fc553f785e39ff89981e251469431d4c88bec38cc27') failures.push({ pageCode: 'database', blockers: ['persistent_hash'] })
if (databaseHashes.development !== 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0') failures.push({ pageCode: 'database', blockers: ['development_hash'] })

const protectedCheckpoints = {}
for (const entry of fs.readdirSync(checkpointRoot, { withFileTypes: true })) {
  if (!entry.isDirectory() || entry.name === '.staging') continue
  const directory = path.join(checkpointRoot, entry.name)
  const manifestFile = path.join(directory, 'manifest.json')
  if (!fs.existsSync(manifestFile)) continue
  const manifest = JSON.parse(read(manifestFile))
  if (manifest.immutable !== true || !core.every(name => fs.existsSync(path.join(directory, name)))) continue
  protectedCheckpoints[entry.name] = Object.fromEntries(core.map(name => [name, sha(path.join(directory, name))]))
}

fs.mkdirSync(root, { recursive: true })
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  acceptanceMigrationVersion: VERSION,
  contractVersion: CONTRACT_VERSION,
  strictProfile: 'purchase-payment-golden-flow',
  strictPageCount: expected.length,
  strictPagesPassed: results.filter(item => item.result === 'passed').length,
  strictPagesFailed: results.filter(item => item.result !== 'passed').length,
  strictBlockerCount: failures.reduce((sum, item) => sum + item.blockers.length, 0),
  acceptanceLevel: 5,
  allStrictPagesLevel5: results.every(item => item.checks.level5),
  databaseHashesBefore: databaseHashes,
  protectedImmutableCheckpointCount: Object.keys(protectedCheckpoints).length,
  results,
  failures,
}
fs.writeFileSync(path.join(root, 'strict-migration-report.json'), `${JSON.stringify(report, null, 2)}\n`)
fs.writeFileSync(path.join(root, 'protected-checkpoints-before.json'), `${JSON.stringify({
  result: 'passed', version: VERSION, coreFiles: core, checkpoints: protectedCheckpoints,
}, null, 2)}\n`)
console.log(JSON.stringify({
  result: report.result,
  strictPageCount: report.strictPageCount,
  strictPagesPassed: report.strictPagesPassed,
  strictBlockerCount: report.strictBlockerCount,
  protectedImmutableCheckpointCount: report.protectedImmutableCheckpointCount,
  databaseHashes,
}, null, 2))
if (failures.length) process.exit(1)
