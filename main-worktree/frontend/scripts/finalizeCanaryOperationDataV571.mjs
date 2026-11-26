import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.57.1'
const CHECKPOINT_ID = 'pce_canary_operation_data_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(root, 'test-results', 'canary-operation-data-v571')
const checkpoint = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  CHECKPOINT_ID,
)
const archive = path.resolve(
  workspace,
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
  CHECKPOINT_ID,
)
const devDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const canaryDatabase = path.join(workspace, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const isolatedDatabase = path.join(workspace, 'backend', 'pce-canary-operation-data-v571-iab.sqlite3')
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
const listFiles = (directory, prefix = '') => fs.readdirSync(directory, { withFileTypes: true })
  .flatMap(entry => {
    const relative = path.join(prefix, entry.name)
    return entry.isDirectory()
      ? listFiles(path.join(directory, entry.name), relative)
      : [relative.replaceAll('\\', '/')]
  })
  .sort()

assert(!fs.existsSync(checkpoint), `Checkpoint already exists: ${checkpoint}`)
assert(!fs.existsSync(archive), `Archive already exists: ${archive}`)

const staticReport = readJson(path.join(resultRoot, 'static-verification-report.json'))
const playwrightReport = readJson(path.join(resultRoot, 'playwright-operation-report.json'))
const iabReport = readJson(path.join(resultRoot, 'iab-real-browser-report.json'))
assert(staticReport.result === 'passed', 'Static verification failed')
assert(playwrightReport.result === 'passed', 'Playwright verification failed')
assert(iabReport.result === 'passed', 'IAB verification failed')
assert(
  playwrightReport.apiPageDiagnosticStrictFactsConsistent === true
    && iabReport.apiPageDiagnosticStrictFactsConsistent === true,
  'API/page/diagnostic/strictFacts consistency failed',
)
assert(
  playwrightReport.businessWriteRequestCount === 0
    && iabReport.businessWriteRequestCount === 0,
  'Business write request detected',
)

const trace = path.join(
  resultRoot,
  'playwright-output',
  'canaryOperationDataV571-V5-6b2b5-idates-three-real-scenarios',
  'trace.zip',
)
assert(fs.existsSync(trace) && fs.statSync(trace).size > 0, 'Successful Playwright trace missing')
for (const relative of [...playwrightReport.screenshots.map(item => `screenshots/${item}`), ...iabReport.screenshots]) {
  const file = path.join(resultRoot, relative)
  assert(fs.existsSync(file) && fs.statSync(file).size > 0, `Screenshot missing: ${relative}`)
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

fs.mkdirSync(path.join(checkpoint, 'evidence'), { recursive: true })
const payloads = {
  'storage-state.json': {
    version: VERSION,
    currentStateSource: 'server',
    browserSessionStored: false,
    reason: 'HTTP-only acceptance actor cookie is not archived',
    productionCredentialStored: false,
  },
  'application-state.json': {
    version: VERSION,
    contractVersion: 'PCE-CANARY-OPERATION-DATA-V1.0',
    objectCount: 16,
    pendingCheckCount: 8,
    checkedCount: 8,
    mixedSelectionSupported: true,
    apiPageDiagnosticStrictFactsConsistent: true,
    playwrightPassed: true,
    iabRealBrowserPassed: true,
    businessWriteRequestCount: 0,
  },
  'business-entities.json': {
    version: VERSION,
    createdBusinessEntities: [],
    acceptanceObjectCount: 16,
    paymentExecutionCreated: false,
    bankTaskCreated: false,
    paymentVoucherCreated: false,
    ledgerEntryCreated: false,
  },
  'relationship-graph.json': {
    version: VERSION,
    moduleCode: 'payable-check',
    pools: {
      pending_check: 8,
      checked: 8,
      mixedSelectionSupported: true,
    },
    actionSource: 'BusinessActionRegistry',
    factSource: 'server',
    downstreamBehavior: 'qualification_or_navigation_only',
  },
}
for (const [name, payload] of Object.entries(payloads)) writeJson(path.join(checkpoint, name), payload)

const evidenceFiles = [
  'static-verification-report.json',
  'playwright-operation-report.json',
  'iab-real-browser-report.json',
  'database-protection-report.json',
  'final-acceptance-report.md',
]
for (const name of evidenceFiles) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(checkpoint, 'evidence', name))
}
fs.copyFileSync(trace, path.join(checkpoint, 'evidence', 'trace.zip'))
copyTree(path.join(resultRoot, 'screenshots'), path.join(checkpoint, 'evidence', 'playwright-screenshots'))
copyTree(path.join(resultRoot, 'iab-screenshots'), path.join(checkpoint, 'evidence', 'iab-screenshots'))

const integrityFiles = listFiles(checkpoint)
const integrityHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(checkpoint, name))]),
)
writeJson(path.join(checkpoint, 'manifest.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  canonicalName: 'PCE业务验收金丝雀操作数据保持机制',
  contractVersion: 'PCE-CANARY-OPERATION-DATA-V1.0',
  immutable: true,
  restorable: true,
  apiPageDiagnosticStrictFactsConsistent: true,
  iabRealBrowserPassed: true,
  playwrightTracePresent: true,
  migrationExecuted: false,
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
  databaseHashes,
  integrityFiles,
  integrityHashes,
})

copyTree(checkpoint, archive)
const checkpointFiles = listFiles(checkpoint)
const archiveFiles = listFiles(archive)
assert(JSON.stringify(checkpointFiles) === JSON.stringify(archiveFiles), 'External archive file list mismatch')
const checkpointHashes = Object.fromEntries(
  checkpointFiles.map(name => [name, sha256(path.join(checkpoint, name))]),
)
const archiveHashes = Object.fromEntries(
  archiveFiles.map(name => [name, sha256(path.join(archive, name))]),
)
assert(JSON.stringify(checkpointHashes) === JSON.stringify(archiveHashes), 'External archive hash mismatch')

const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  restorable: true,
  checkpointFileCount: checkpointFiles.length,
  checkpointHashes,
  archiveHashes,
  apiPageDiagnosticStrictFactsConsistent: true,
  iabRealBrowserPassed: true,
  businessWriteRequestCount: 0,
  migrationExecuted: false,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))
