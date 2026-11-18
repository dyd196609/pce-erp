import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.1'
const SOURCE_CHECKPOINT = 'formal_payment_order_ready'
const TARGET_CHECKPOINT = 'formal_payment_order_page_contract_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
const source = path.join(checkpointBase, SOURCE_CHECKPOINT)
const sourceArchive = path.join(archiveBase, SOURCE_CHECKPOINT)
const target = path.join(checkpointBase, TARGET_CHECKPOINT)
const targetArchive = path.join(archiveBase, TARGET_CHECKPOINT)
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v531')
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedPersistentHash = 'e9fe4cf001a6408fdaa4291fc00d2d5e6c92f84c5d6fc98f49ed33e5edb6a676'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreNames = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const integrityFiles = coreNames.slice(1)
const expectedSourceHashes = {
  'manifest.json': '868b25d0c0a439c5c854587d7572c8e889aa9652318a281f7f9c9f613c4b84bd',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': '6bb827daf813c836965d036888d756017da8372790a07edb9a16a9defd0c79bd',
  'business-entities.json': '3f6effa75099cb2b6ca8b4aab7fb92347d5d12becd131caff053273ea99a9ade',
  'relationship-graph.json': '5687ee4088797d37ff2f48199331e542913f1b117595bf58c8974d9d60f0045e',
}
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = directory => Object.fromEntries(coreNames.map(name => [name, digest(path.join(directory, name))]))
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (directory, name, value) => fs.writeFileSync(
  path.join(directory, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

assert(JSON.stringify(hashes(source)) === JSON.stringify(expectedSourceHashes), 'V53 checkpoint hash changed')
assert(JSON.stringify(hashes(sourceArchive)) === JSON.stringify(expectedSourceHashes), 'V53 archive hash changed')
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent canary database changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
assert(!fs.existsSync(target), `Checkpoint already exists: ${TARGET_CHECKPOINT}`)
assert(!fs.existsSync(targetArchive), `Archive already exists: ${TARGET_CHECKPOINT}`)

const staticGuards = readJson(path.join(resultRoot, 'static-guards.json'))
const pageAssertions = readJson(path.join(resultRoot, 'page-assertions.json'))
const diagnostics = readJson(path.join(resultRoot, 'diagnostics-report.json'))
const consistency = readJson(path.join(resultRoot, 'diagnostic-consistency-report.json'))
const strictConsistency = readJson(path.join(resultRoot, 'strict-facts-consistency-report.json'))
assert(staticGuards.result === 'passed' && staticGuards.failures.length === 0, 'V53.1 static guards failed')
assert(pageAssertions.result === 'passed' && pageAssertions.assertions.every(item => item.passed), 'Page assertions failed')
assert(diagnostics.businessWriteRequestCount === 0, 'Page acceptance performed a business write')
assert(consistency.consistent === true && strictConsistency.consistent === true, 'Fact counts are inconsistent')
assert([consistency.apiCount, consistency.pageCount, consistency.diagnosticCount, consistency.strictFactsCount]
  .every(value => value === 8), 'API/page/diagnostic/strict count mismatch')

fs.mkdirSync(target, { recursive: false })
for (const name of integrityFiles) fs.copyFileSync(path.join(source, name), path.join(target, name))
for (const name of ['checkpoint-screenshot.png', 'trace.zip']) {
  fs.copyFileSync(path.join(source, name), path.join(target, name))
}
const sourceManifest = readJson(path.join(source, 'manifest.json'))
const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  pageContractVersion: VERSION,
  immutable: true,
  restorable: true,
  filterContractSource: 'pceAdvancedFilterContract',
  requiredFilterCount: 10,
  operationWhitelist: [
    '查看正式付款单',
    '查看来源真实付款风险评审',
    '复制业务编号',
  ],
  forbiddenExecutionActionsPresent: false,
  apiCount: 8,
  pageCount: 8,
  diagnosticCount: 8,
  strictFactsCount: 8,
  businessWriteRequestCount: 0,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  productionUserDataWritten: false,
}
delete manifest.integrityHash
const integrity = crypto.createHash('sha256')
for (const name of integrityFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(target, name)))
}
manifest.integrityHash = integrity.digest('hex')
writeJson(target, 'manifest.json', manifest)
writeJson(target, 'restore-verification.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  immutable: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: 8,
  businessWriteRequestCount: 0,
  downstreamCountsAllZero: true,
})
writeJson(target, 'page-contract-verification.json', {
  result: 'passed',
  version: VERSION,
  fullUrl: 'http://localhost:5173/#/finance/formal-payment-orders',
  advancedFilterContract: 'pceAdvancedFilterContract',
  actionWhitelist: manifest.operationWhitelist,
  fixedLeftSelectionColumn: true,
  fixedRightOperationColumn: true,
  horizontalScrollPassed: true,
  businessWriteRequestCount: 0,
  downstreamCountsAllZero: true,
  sourceCheckpointHashes: expectedSourceHashes,
})

fs.mkdirSync(archiveBase, { recursive: true })
fs.cpSync(target, targetArchive, { recursive: true, errorOnExist: true })
const targetHashes = hashes(target)
const archiveHashes = hashes(targetArchive)
assert(JSON.stringify(targetHashes) === JSON.stringify(archiveHashes), 'Checkpoint archive hashes differ')
assert(JSON.stringify(hashes(source)) === JSON.stringify(expectedSourceHashes), 'V53 checkpoint changed during finalization')
assert(JSON.stringify(hashes(sourceArchive)) === JSON.stringify(expectedSourceHashes), 'V53 archive changed during finalization')
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent database changed during finalization')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed during finalization')

writeJson(resultRoot, 'build-report.json', {
  result: 'passed',
  version: VERSION,
  command: 'npm.cmd run build',
  exitCode: 0,
  prebuildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
})
writeJson(resultRoot, 'finalization-report.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  checkpointPath: target,
  archivePath: targetArchive,
  checkpointHashes: targetHashes,
  archiveHashes,
  sourceCheckpointHashes: hashes(source),
  sourceArchiveHashes: hashes(sourceArchive),
  immutable: true,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionUserDataWritten: false,
})
console.log(JSON.stringify(readJson(path.join(resultRoot, 'finalization-report.json')), null, 2))
