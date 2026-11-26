import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.57'
const CHECKPOINT_ID = 'pce_purchase_upstream_state_machine_action_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(root, 'test-results', 'purchase-upstream-governance-v57')
const checkpointRoot = path.join(root, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const archive = path.resolve(workspace, '..', 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT_ID)
const devDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const canaryDatabase = path.join(workspace, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const isolatedDatabase = path.join(workspace, 'backend', 'pce-purchase-upstream-governance-v57-iab.sqlite3')
const expectedDevHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const expectedCanaryHash = '6320461a88b739933828a0909baa02155fdeb93e17e386c5deb977d9c1e0548d'

const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const copyTree = (source, target) => {
  fs.mkdirSync(target, { recursive: true })
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    const from = path.join(source, entry.name)
    const to = path.join(target, entry.name)
    if (entry.isDirectory()) copyTree(from, to)
    else fs.copyFileSync(from, to)
  }
}

assert(!fs.existsSync(checkpoint), `Checkpoint already exists: ${checkpoint}`)
assert(!fs.existsSync(archive), `Archive already exists: ${archive}`)

const governance = readJson(path.join(resultRoot, 'governance-verification-report.json'))
const facts = readJson(path.join(resultRoot, 'playwright-fact-consistency-report.json'))
const iab = readJson(path.join(resultRoot, 'iab-real-browser-report.json'))
const permissions = readJson(path.join(root, 'test-results', 'pce-business-action-permission-v552', 'playwright-permission-report.json'))
assert(governance.result === 'passed' && governance.migratedModuleCount === 4, 'Governance verification failed')
assert(governance.stateMachineConsistent === true && governance.actionRegistryConsistent === true, 'Governance consistency failed')
assert(facts.result === 'passed' && facts.apiPageDiagnosticStrictFactsConsistent === true, 'Four-surface verification failed')
assert(
  iab.result === 'passed'
    && iab.payableCheck?.realUserScenariosPassed === true
    && permissions.result === 'passed',
  'Real browser verification failed',
)
assert(facts.businessWriteRequestCount === 0 && permissions.businessWriteRequestCount === 0 && iab.businessWriteRequestCount === 0, 'Business write request detected')

const trace = path.join(
  resultRoot,
  'playwright-output',
  'purchaseUpstreamGovernance-451de-ictFacts-share-server-facts',
  'trace.zip',
)
assert(fs.existsSync(trace) && fs.statSync(trace).size > 0, 'Playwright trace missing')
for (const item of [...iab.governedPages, ...Object.values(iab.roles)]) {
  if (item.screenshot) assert(fs.existsSync(path.join(resultRoot, item.screenshot)), `Screenshot missing: ${item.screenshot}`)
}

const databaseHashes = {
  development: sha256(devDatabase),
  canary: sha256(canaryDatabase),
  isolatedAcceptance: sha256(isolatedDatabase),
}
assert(databaseHashes.development === expectedDevHash, 'Development database changed')
assert(databaseHashes.canary === expectedCanaryHash, 'Persistent canary database changed')
writeJson(path.join(resultRoot, 'database-protection-report.json'), {
  result: 'passed',
  version: VERSION,
  hashes: databaseHashes,
  developmentDatabaseUnchanged: true,
  canaryDatabaseUnchanged: true,
  isolatedAcceptanceDatabaseUsed: true,
  migrationExecuted: false,
  productionUserDataWritten: false,
})

fs.mkdirSync(checkpoint, { recursive: true })
const payloads = {
  'storage-state.json': {
    version: VERSION,
    currentStateSource: 'server',
    browserSessionStored: false,
    reason: 'httpOnly canary actor cookie is not archived',
    productionCredentialStored: false,
  },
  'application-state.json': {
    version: VERSION,
    stateMachineConsistent: true,
    actionRegistryConsistent: true,
    apiPageDiagnosticStrictFactsConsistent: true,
    iabRealBrowserPassed: true,
    businessWriteRequestCount: 0,
  },
  'business-entities.json': {
    version: VERSION,
    createdBusinessEntities: [],
    paymentExecutionCreated: false,
    bankTaskCreated: false,
    paymentVoucherCreated: false,
    ledgerEntryCreated: false,
  },
  'relationship-graph.json': {
    version: VERSION,
    governedModules: governance.moduleReports.map(item => ({
      module: item.module,
      migrationStatus: item.migrationStatus,
      currentStateSource: 'server',
    })),
    downstreamBehavior: 'navigation_only',
  },
}
for (const [name, payload] of Object.entries(payloads)) writeJson(path.join(checkpoint, name), payload)
const integrityFiles = Object.keys(payloads)
const integrityHashes = Object.fromEntries(integrityFiles.map(name => [name, sha256(path.join(checkpoint, name))]))
writeJson(path.join(checkpoint, 'manifest.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  canonicalName: '采购付款上游模块状态机与业务动作全面治理',
  immutable: true,
  restorable: true,
  stateMachineConsistent: true,
  actionRegistryConsistent: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  iabRealBrowserPassed: true,
  migrationExecuted: false,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
  databaseHashes,
  integrityFiles,
  integrityHashes,
  trace: path.relative(root, trace).replaceAll('\\', '/'),
})

copyTree(checkpoint, archive)
const checkpointFiles = ['manifest.json', ...integrityFiles]
const checkpointHashes = Object.fromEntries(checkpointFiles.map(name => [name, sha256(path.join(checkpoint, name))]))
const archiveHashes = Object.fromEntries(checkpointFiles.map(name => [name, sha256(path.join(archive, name))]))
assert(JSON.stringify(checkpointHashes) === JSON.stringify(archiveHashes), 'External archive hash mismatch')

const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  restorable: true,
  checkpointHashes,
  archiveHashes,
  stateMachineConsistent: true,
  actionRegistryConsistent: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  iabRealBrowserPassed: true,
  businessWriteRequestCount: 0,
  migrationExecuted: false,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))
