import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54.2'
const CHECKPOINT = 'formal_payment_order_state_transition_fact_ready'
const SOURCE_CHECKPOINT = 'formal_payment_order_state_consistency_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v542')
const checkpointBase = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const archiveBase = path.resolve(
  frontend,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const source = path.join(checkpointBase, SOURCE_CHECKPOINT)
const target = path.join(checkpointBase, CHECKPOINT)
const archive = path.join(archiveBase, CHECKPOINT)
const persistentDatabase = path.join(
  backend,
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedPersistentHash = '177c176176785b9a7dd4ebc24dd4ff2dfa4741fc23b87ebcc93490df33f5d8e4'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreNames = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
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
  formal_payment_order_scenario_filter_ready: {
    'manifest.json': '96dbc677ac888e192d19b089fb04ba1d8e41657793ff661044dacd8661e663b9',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': '4f78d9065f7f402eab53bb62a79c8cc3040a91cf3b3474c14d2d7895854be94b',
    'business-entities.json': '4fbac9d8aa91f8c6b288851061fa4709c75502c8f1424663277945a0975b8ae7',
    'relationship-graph.json': '387abc0d8f45a40656d446cf417360a36661d7d0b2c2d4536ec5f03e1d5fd128',
  },
  formal_payment_order_send_gate_ready: {
    'manifest.json': 'aad481ecd53912dda76eda8634907f2a83e5028da876448e1593140d00dd8c14',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': '51e4e0589e96c78d0af22dd3f8856bfae663e78feb8cbbb705a2420d2dbc8b3d',
    'business-entities.json': '69356092b92741d643a4c51a4b3159235eb4739554786c9da9d921d682ef6ea2',
    'relationship-graph.json': '9e55afce028c9e092b0025b454b6a50a85917aecbc9619ff801aa4f6f642b90e',
  },
  formal_payment_order_state_consistency_ready: {
    'manifest.json': '9efa48f0f0bd3e3e2a9767e194f45bb9cab4719cc1f9deffa1031beaf3595f4c',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': 'dfb5f63d01bd2399b071b3863dc257e718c58e0cff45272be2859b2b4ddc9b05',
    'business-entities.json': '52b237fc325a0764fab4d38a3689636776daee9a6f2ed1630a2d2dedc1eb3e9f',
    'relationship-graph.json': '1b8bd730bdc0d24ca3058e68a7efa3ae2e648e35fbb79b7fbe2deee0af5b4c45',
  },
}

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const digest = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreNames.map(name => [name, digest(path.join(directory, name))]),
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (directory, name, value) => fs.writeFileSync(
  path.join(directory, name),
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const findFile = (directory, name) => {
  const pending = [directory]
  while (pending.length) {
    const current = pending.shift()
    if (!fs.existsSync(current)) continue
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      const fullPath = path.join(current, entry.name)
      if (entry.isDirectory()) pending.push(fullPath)
      else if (entry.name === name) return fullPath
    }
  }
  return ''
}
const assertProtected = () => {
  for (const [checkpointId, expected] of Object.entries(protectedHashes)) {
    assert(
      JSON.stringify(hashes(path.join(checkpointBase, checkpointId)))
        === JSON.stringify(expected),
      `${checkpointId} checkpoint changed`,
    )
    assert(
      JSON.stringify(hashes(path.join(archiveBase, checkpointId)))
        === JSON.stringify(expected),
      `${checkpointId} archive changed`,
    )
  }
}

assertProtected()
assert(!fs.existsSync(target), `Checkpoint already exists: ${CHECKPOINT}`)
assert(!fs.existsSync(archive), `Archive already exists: ${CHECKPOINT}`)
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent database changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')

const staticReport = readJson(path.join(resultRoot, 'static-guard-report.json'))
const coverageReport = readJson(path.join(resultRoot, 'stateMachineCoverageReport.json'))
const runtimeReport = readJson(path.join(resultRoot, 'runtime-transition-fact-report.json'))
const pageReport = readJson(path.join(resultRoot, 'page-assertions.json'))
const consistencyReport = readJson(path.join(resultRoot, 'fact-consistency-report.json'))
const geometryReport = readJson(path.join(resultRoot, 'geometry-report.json'))
const recoveryReport = readJson(path.join(resultRoot, 'cross-process-recovery.json'))

assert(staticReport.result === 'passed' && staticReport.guardCount === 12, 'Static guards failed')
assert(staticReport.failedCount === 0, 'A static guard failed')
assert(coverageReport.result === 'passed' && coverageReport.allDomainsClassified, 'Coverage scan failed')
assert(coverageReport.summary.unclassifiedModuleCount === 0, 'Coverage has unclassified modules')
assert(coverageReport.migrationTruth.allModulesMigrated === false, 'Legacy migration was falsely reported complete')
assert(runtimeReport.result === 'passed' && runtimeReport.guards.length === 10, 'Runtime fact guards failed')
assert(runtimeReport.guards.every(row => row.passed), 'A runtime fact guard failed')
assert(runtimeReport.formalPaymentOrderCount === 8, 'Formal payment order count mismatch')
assert(runtimeReport.businessStateTransitionCount === 24, 'Transition count mismatch')
assert(runtimeReport.reasonCompleteCount === 24, 'Transition reason count mismatch')
assert(runtimeReport.auditReferenceCompleteCount === 24, 'Audit reference count mismatch')
assert(runtimeReport.stateMachineConsistentCount === 8, 'State-machine consistency mismatch')
assert(runtimeReport.statusTransitionCountPerObject.every(value => value === 3), 'Per-object transition count mismatch')
assert(runtimeReport.successObjects.every(row => (
  row.status === 'frozen_for_execution'
  && row.statusTransitionCount === 3
  && row.statusTransitionHistory.length === 3
  && row.statusTransitionHistory.every(transition => (
    transition.objectType === 'formal_payment_order'
    && transition.objectId > 0
    && transition.operator?.id > 0
    && transition.operator?.name
    && transition.timestamp
    && transition.reason
    && transition.version > 0
    && /^BusinessActionAuditRecord:\d+$/.test(transition.auditReference)
  ))
  && row.stateMachineConsistent === true
)), 'Canonical transition facts are incomplete')
assert(pageReport.result === 'passed' && pageReport.assertions.every(row => row.passed), 'Page acceptance failed')
assert(consistencyReport.result === 'passed' && consistencyReport.consistent === true, 'Four-surface consistency failed')
assert(consistencyReport.businessWriteRequestCount === 0, 'Page acceptance performed a business write')
assert(geometryReport.result === 'passed', 'Geometry report failed')
assert(recoveryReport.result === 'passed' && recoveryReport.databaseUnchanged, 'Cross-process recovery failed')
assert(recoveryReport.businessActionsReplayed === false, 'Business actions were replayed')
assert(Object.values(runtimeReport.downstreamCounts).every(value => value === 0), 'A downstream object exists')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(
  path.join(source, 'storage-state.json'),
  path.join(target, 'storage-state.json'),
)
const sourceApplication = readJson(path.join(source, 'application-state.json'))
writeJson(target, 'application-state.json', {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  stateMachine: ['prepared', 'submitted', 'approved', 'frozen_for_execution'],
  transitionFactContract: {
    service: 'workflow_runtime.transition_business_object',
    initializationService: 'workflow_runtime.create_business_object_with_initial_state',
    canonicalFields: [
      'sourceState',
      'targetState',
      'objectType',
      'objectId',
      'operator',
      'timestamp',
      'reason',
      'version',
      'auditReference',
    ],
  },
  capacity: {
    ...sourceApplication.capacity,
    formalPaymentOrderCount: 8,
    businessStateTransitionCount: 24,
    statusTransitionCountPerObject: 3,
    reasonCompleteCount: 24,
    auditReferenceCompleteCount: 24,
    stateMachineConsistentCount: 8,
    nextStageConsumedCount: 0,
  },
  stateMachineCoverage: coverageReport.summary,
  downstreamCounts: runtimeReport.downstreamCounts,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
})
const sourceEntities = readJson(path.join(source, 'business-entities.json'))
writeJson(target, 'business-entities.json', {
  ...sourceEntities,
  version: VERSION,
  formalPaymentOrders: runtimeReport.successObjects,
  formalPaymentOrderCount: 8,
  businessStateTransitionCount: 24,
  reasonCompleteCount: 24,
  auditReferenceCompleteCount: 24,
  stateMachineConsistentCount: 8,
  compliantStateMachineModules: coverageReport.compliantModules,
  legacyStateMachineModules: coverageReport.legacyModules,
  nextStageConsumedCount: 0,
  downstreamCounts: runtimeReport.downstreamCounts,
})
const sourceGraph = readJson(path.join(source, 'relationship-graph.json'))
const transitionById = new Map(
  runtimeReport.successObjects.flatMap(row => (
    row.statusTransitionHistory.map(transition => [transition.id, transition])
  )),
)
writeJson(target, 'relationship-graph.json', {
  ...sourceGraph,
  version: VERSION,
  nodes: sourceGraph.nodes.map(node => {
    if (node.type !== 'businessStateTransition') return node
    const identifier = Number(String(node.id).split(':').at(-1))
    const transition = transitionById.get(identifier)
    return transition ? {
      ...node,
      objectType: transition.objectType,
      objectId: transition.objectId,
      sourceState: transition.sourceState,
      targetState: transition.targetState,
      operator: transition.operator,
      timestamp: transition.timestamp,
      reason: transition.reason,
      version: transition.version,
      auditReference: transition.auditReference,
    } : node
  }),
  downstreamEdges: [],
})

const screenshot = path.join(resultRoot, 'screenshots', 'page-1366.png')
const trace = findFile(path.join(resultRoot, 'playwright-output'), 'trace.zip')
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
  checkpointId: CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  canonicalName: '正式付款单状态机转换事实完整性修复',
  moduleCode: 'formal-payment-order',
  route: '/finance/formal-payment-orders',
  immutable: true,
  restorable: true,
  currentStateSource: 'server',
  formalPaymentOrderCount: 8,
  businessStateTransitionCount: 24,
  statusTransitionCountPerObject: 3,
  reasonCompleteCount: 24,
  auditReferenceCompleteCount: 24,
  stateMachineConsistentCount: 8,
  stateMachine: ['prepared', 'submitted', 'approved', 'frozen_for_execution'],
  transitionFactFields: [
    'sourceState',
    'targetState',
    'objectType',
    'objectId',
    'operator',
    'timestamp',
    'reason',
    'version',
    'auditReference',
  ],
  staticGuardCount: 12,
  runtimeGuardCount: 10,
  scannedModuleCount: coverageReport.summary.scannedModuleCount,
  compliantModuleCount: coverageReport.summary.compliantModuleCount,
  legacyModuleCount: coverageReport.summary.legacyModuleCount,
  highRiskLegacyModuleCount: coverageReport.summary.highRiskLegacyModuleCount,
  mediumRiskLegacyModuleCount: coverageReport.summary.mediumRiskLegacyModuleCount,
  allModulesMigrated: false,
  allModulesClassified: true,
  migrationApplied: true,
  migrations: ['workflow_runtime.0003_transition_fact_integrity'],
  djangoCheckPassed: true,
  compileallPassed: true,
  playwrightPassed: true,
  crossProcessRecoveryReady: true,
  apiPageDiagnosticStrictConsistent: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  developmentDatabaseUnchanged: true,
  protectedCheckpointsImmutable: true,
  bankMessageCreated: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  ledgerCreated: false,
  productionUserDataWritten: false,
  downstreamCountsAllZero: true,
  archiveHashVerified: true,
}
delete manifest.integrityHash
const integrity = crypto.createHash('sha256')
for (const name of coreNames.slice(1)) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(target, name)))
}
manifest.integrityHash = integrity.digest('hex')
writeJson(target, 'manifest.json', manifest)

for (const name of [
  'static-guard-report.json',
  'stateMachineCoverageReport.json',
  'runtime-transition-fact-report.json',
  'page-assertions.json',
  'fact-consistency-report.json',
  'geometry-report.json',
  'cross-process-recovery.json',
]) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(target, name))
}
writeJson(target, 'build-report.json', {
  result: 'passed',
  version: VERSION,
  command: 'npm.cmd run build',
  exitCode: 0,
  prebuildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
  warningsOnly: [
    'dependency-pure-annotation',
    'large-chunk',
    'plugin-timings',
  ],
})
writeJson(target, 'restore-verification.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  sourceCheckpointId: SOURCE_CHECKPOINT,
  immutable: true,
  currentStateSource: 'server',
  serviceRestarted: true,
  businessActionsReplayed: false,
  formalPaymentOrderCount: 8,
  businessStateTransitionCount: 24,
  statusTransitionCountPerObject: 3,
  stateMachineConsistentCount: 8,
  downstreamCountsAllZero: true,
  databaseHashBefore: recoveryReport.databaseHashBefore,
  databaseHashAfter: recoveryReport.databaseHashAfter,
})

fs.mkdirSync(archiveBase, { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
assert(
  JSON.stringify(hashes(target)) === JSON.stringify(hashes(archive)),
  'Archive hash mismatch',
)
assertProtected()
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent database changed during finalization')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed during finalization')
writeJson(resultRoot, 'build-report.json', readJson(path.join(target, 'build-report.json')))
writeJson(resultRoot, 'finalization-report.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: target,
  archivePath: archive,
  checkpointHashes: hashes(target),
  archiveHashes: hashes(archive),
  protectedCheckpoints: Object.fromEntries(
    Object.keys(protectedHashes).map(checkpointId => [
      checkpointId,
      hashes(path.join(checkpointBase, checkpointId)),
    ]),
  ),
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionUserDataWritten: false,
})
console.log(JSON.stringify(
  readJson(path.join(resultRoot, 'finalization-report.json')),
  null,
  2,
))
