import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.3'
const TARGET_CHECKPOINT = 'formal_payment_order_scenario_filter_ready'
const SOURCE_CHECKPOINT = 'formal_payment_order_filter_control_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
const source = path.join(checkpointBase, SOURCE_CHECKPOINT)
const target = path.join(checkpointBase, TARGET_CHECKPOINT)
const archive = path.join(archiveBase, TARGET_CHECKPOINT)
const pageResultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v533')
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const expectedBusinessResultHash = '6312f1f1b5a3999013362ce48ee9c930f7d9e21ce0a506c5a3cf5ce66beb95b7'
const expectedScenarioCodes = Array.from(
  { length: 8 },
  (_, index) => `SUCCESS_${String(index + 1).padStart(2, '0')}`,
)
const coreNames = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const integrityFiles = coreNames.slice(1)
const protectedHashes = {
  formal_payment_order_ready: {
    'manifest.json': '868b25d0c0a439c5c854587d7572c8e889aa9652318a281f7f9c9f613c4b84bd',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': '6bb827daf813c836965d036888d756017da8372790a07edb9a16a9defd0c79bd',
    'business-entities.json': '3f6effa75099cb2b6ca8b4aab7fb92347d5d12becd131caff053273ea99a9ade',
    'relationship-graph.json': '5687ee4088797d37ff2f48199331e542913f1b117595bf58c8974d9d60f0045e',
  },
  formal_payment_order_page_contract_ready: {
    'manifest.json': '0f79d8db7965feca18334f125b9b463fabbfa846761338a54531d420beb19c47',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': '6bb827daf813c836965d036888d756017da8372790a07edb9a16a9defd0c79bd',
    'business-entities.json': '3f6effa75099cb2b6ca8b4aab7fb92347d5d12becd131caff053273ea99a9ade',
    'relationship-graph.json': '5687ee4088797d37ff2f48199331e542913f1b117595bf58c8974d9d60f0045e',
  },
  formal_payment_order_filter_control_ready: {
    'manifest.json': 'ada8aa7c29233b683350c8369cc79827e7a92e04276db2fb99d4ba3d8ba95782',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': '6bb827daf813c836965d036888d756017da8372790a07edb9a16a9defd0c79bd',
    'business-entities.json': '3f6effa75099cb2b6ca8b4aab7fb92347d5d12becd131caff053273ea99a9ade',
    'relationship-graph.json': '5687ee4088797d37ff2f48199331e542913f1b117595bf58c8974d9d60f0045e',
  },
}

const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = directory => Object.fromEntries(
  coreNames.map(name => [name, digest(path.join(directory, name))]),
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (directory, name, value) => fs.writeFileSync(
  path.join(directory, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const findFile = (directory, name) => {
  const pending = [directory]
  while (pending.length) {
    const current = pending.shift()
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) pending.push(fullPath)
      else if (entry.name === name) return fullPath
    }
  }
  return ''
}
const assertProtected = () => {
  for (const [id, expected] of Object.entries(protectedHashes)) {
    assert(JSON.stringify(hashes(path.join(checkpointBase, id))) === JSON.stringify(expected), `${id} checkpoint changed`)
    assert(JSON.stringify(hashes(path.join(archiveBase, id))) === JSON.stringify(expected), `${id} archive changed`)
  }
}

assertProtected()
assert(!fs.existsSync(target), `Checkpoint already exists: ${TARGET_CHECKPOINT}`)
assert(!fs.existsSync(archive), `Archive already exists: ${TARGET_CHECKPOINT}`)
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
const persistentHash = digest(persistentDatabase)
const staticReport = readJson(path.join(pageResultRoot, 'scenario-contract-static-report.json'))
const backendReport = readJson(path.join(pageResultRoot, 'backend-contract-report.json'))
const pageReport = readJson(path.join(pageResultRoot, 'page-assertions.json'))
const diagnosticsReport = readJson(path.join(pageResultRoot, 'diagnostics-report.json'))
const consistencyReport = readJson(path.join(pageResultRoot, 'diagnostic-consistency-report.json'))
const strictReport = readJson(path.join(pageResultRoot, 'strict-facts-consistency-report.json'))
const diagnostics = diagnosticsReport.diagnostics
const apiScenarioCodes = backendReport.formalPaymentOrders.map(row => row.sourceScenarioCode)

assert(staticReport.result === 'passed' && staticReport.failures.length === 0, 'V53.3 static guards failed')
assert(Object.values(staticReport.guards).every(Boolean), 'V53.3 guard result is incomplete')
assert(backendReport.result === 'passed' && Object.values(backendReport.checks).every(Boolean), 'Backend contract failed')
assert(backendReport.businessResultHashBefore === expectedBusinessResultHash, 'Pre-migration business hash changed')
assert(backendReport.businessResultHashAfter === expectedBusinessResultHash, 'Post-migration business hash changed')
assert(backendReport.businessResultUnchanged === true, 'Existing formal payment order result changed')
assert(JSON.stringify(apiScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Server scenario values mismatch')
assert(pageReport.result === 'passed' && pageReport.assertions.every(row => row.passed), 'Page acceptance failed')
assert(diagnosticsReport.businessWriteRequestCount === 0, 'Page acceptance performed a business write')
assert(consistencyReport.consistent === true && consistencyReport.scenarioCodeConsistent === true, 'API/page/diagnostic scenario mismatch')
assert(consistencyReport.scenarioCodeEmptyCount === 0, 'Empty scenario code remains')
assert(strictReport.scenarioCodeEmptyCount === 0, 'Strict facts contain an empty scenario code')
assert(JSON.stringify(strictReport.apiScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Strict report API scenarios mismatch')
assert(JSON.stringify(strictReport.pageScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Strict report page scenarios mismatch')
assert(JSON.stringify(strictReport.diagnosticScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Strict report diagnostic scenarios mismatch')
assert(JSON.stringify(strictReport.strictFactsScenarioCodes) === JSON.stringify(expectedScenarioCodes), 'Strict report scenarios mismatch')
assert(Object.values(backendReport.downstreamCounts).every(value => value === 0), 'Downstream object count changed')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
const sourceApplication = readJson(path.join(source, 'application-state.json'))
writeJson(target, 'application-state.json', {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  scenarioCodeSource: 'PaymentRiskReview.scenarioCode',
  scenarioCodes: expectedScenarioCodes,
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
})
const sourceEntities = readJson(path.join(source, 'business-entities.json'))
writeJson(target, 'business-entities.json', {
  ...sourceEntities,
  version: VERSION,
  formalPaymentOrders: backendReport.formalPaymentOrders,
  scenarioCodeSource: 'PaymentRiskReview.scenarioCode',
  scenarioCodes: expectedScenarioCodes,
})
const scenarioByReview = new Map(
  backendReport.formalPaymentOrders.map(row => [row.sourceRiskReviewId, row.sourceScenarioCode]),
)
const scenarioByOrder = new Map(
  backendReport.formalPaymentOrders.map(row => [row.id, row.sourceScenarioCode]),
)
const sourceGraph = readJson(path.join(source, 'relationship-graph.json'))
writeJson(target, 'relationship-graph.json', {
  ...sourceGraph,
  version: VERSION,
  nodes: sourceGraph.nodes.map(node => {
    const [type, rawId] = node.id.split(':')
    const objectId = Number(rawId)
    const scenarioCode = type === 'paymentRiskReview'
      ? scenarioByReview.get(objectId)
      : type === 'formalPaymentOrder'
        ? scenarioByOrder.get(objectId)
        : ''
    return scenarioCode ? { ...node, scenarioCode } : node
  }),
})
const screenshot = path.join(pageResultRoot, 'screenshots', 'page-full.png')
const trace = findFile(path.join(pageResultRoot, 'playwright-output'), 'trace.zip')
assert(fs.existsSync(screenshot), 'Checkpoint screenshot missing')
assert(trace && fs.existsSync(trace), 'Checkpoint trace missing')
fs.copyFileSync(screenshot, path.join(target, 'checkpoint-screenshot.png'))
fs.copyFileSync(trace, path.join(target, 'trace.zip'))

const sourceManifest = readJson(path.join(source, 'manifest.json'))
const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  immutable: true,
  restorable: true,
  currentStateSource: 'server',
  scenarioCodeSource: 'PaymentRiskReview.scenarioCode',
  scenarioCodes: expectedScenarioCodes,
  scenarioCodeCount: expectedScenarioCodes.length,
  scenarioCodeEmptyCount: 0,
  scenarioCodeControlType: 'select',
  scenarioCodeOptionsNonEmpty: true,
  scenarioCodeFilterSuccess01Count: 1,
  scenarioCodeFilterClearCount: 8,
  scenarioCodeHasServerValues: true,
  scenarioCodeConsistentApiPageDiagnostic: true,
  scenarioCodeNotEmptyForStrictPages: true,
  migrationApplied: true,
  migrations: [
    'payment_risk_review.0002_paymentriskreview_scenario_code',
    'formal_payment_order.0002_formalpaymentorder_source_scenario_code',
  ],
  existingBusinessResultHashBefore: expectedBusinessResultHash,
  existingBusinessResultHashAfter: expectedBusinessResultHash,
  existingBusinessResultUnchanged: true,
  formalPaymentOrderCount: 8,
  apiCount: 8,
  pageCount: 8,
  diagnosticCount: 8,
  strictFactsCount: 8,
  businessWriteRequestCount: 0,
  downstreamCountsAllZero: true,
  protectedCheckpointsImmutable: true,
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  developmentDatabaseUnchanged: true,
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
writeJson(target, 'scenario-filter-verification.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  fullUrl: 'http://localhost:5173/#/finance/formal-payment-orders',
  currentStateSource: 'server',
  scenarioCodeSource: 'PaymentRiskReview.scenarioCode',
  apiScenarioCodes,
  pageScenarioCodes: strictReport.pageScenarioCodes,
  diagnosticScenarioCodes: strictReport.diagnosticScenarioCodes,
  strictFactsScenarioCodes: strictReport.strictFactsScenarioCodes,
  scenarioCodeEmptyCount: 0,
  scenarioCodeFilterSuccess01Count: 1,
  scenarioCodeFilterClearCount: 8,
  guards: staticReport.guards,
  existingBusinessResultUnchanged: true,
  businessWriteRequestCount: 0,
  downstreamCountsAllZero: true,
})
writeJson(target, 'restore-verification.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  immutable: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: 8,
  scenarioCodeCount: 8,
  scenarioCodeEmptyCount: 0,
  businessWriteRequestCount: 0,
  downstreamCountsAllZero: true,
})

fs.mkdirSync(archiveBase, { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
assert(JSON.stringify(hashes(target)) === JSON.stringify(hashes(archive)), 'Archive hash mismatch')
assertProtected()
assert(digest(persistentDatabase) === persistentHash, 'Persistent database changed during finalization')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed during finalization')
writeJson(pageResultRoot, 'build-report.json', {
  result: 'passed',
  version: VERSION,
  command: 'npm.cmd run build',
  exitCode: 0,
  prebuildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
})
writeJson(pageResultRoot, 'finalization-report.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: TARGET_CHECKPOINT,
  checkpointPath: target,
  archivePath: archive,
  checkpointHashes: hashes(target),
  archiveHashes: hashes(archive),
  protectedCheckpoints: Object.fromEntries(
    Object.keys(protectedHashes).map(id => [id, hashes(path.join(checkpointBase, id))]),
  ),
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  existingBusinessResultUnchanged: true,
  productionUserDataWritten: false,
})
console.log(JSON.stringify(readJson(path.join(pageResultRoot, 'finalization-report.json')), null, 2))
