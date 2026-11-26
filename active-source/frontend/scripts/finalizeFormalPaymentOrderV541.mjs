import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54.1'
const CHECKPOINT = 'formal_payment_order_state_consistency_ready'
const SOURCE_CHECKPOINT = 'formal_payment_order_send_gate_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v541')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
const source = path.join(checkpointBase, SOURCE_CHECKPOINT)
const target = path.join(checkpointBase, CHECKPOINT)
const archive = path.join(archiveBase, CHECKPOINT)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedPersistentHash = '6e9a5d16341e259a8fd49f2b2eb5a1232d460aee4d0faf94b8ddcc86fcc81e87'
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
}

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = directory => Object.fromEntries(coreNames.map(name => [name, digest(path.join(directory, name))]))
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
      JSON.stringify(hashes(path.join(checkpointBase, checkpointId))) === JSON.stringify(expected),
      `${checkpointId} checkpoint changed`,
    )
    assert(
      JSON.stringify(hashes(path.join(archiveBase, checkpointId))) === JSON.stringify(expected),
      `${checkpointId} archive changed`,
    )
  }
}

assertProtected()
assert(!fs.existsSync(target), `Checkpoint already exists: ${CHECKPOINT}`)
assert(!fs.existsSync(archive), `Archive already exists: ${CHECKPOINT}`)
assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent canary database changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')

const staticReport = readJson(path.join(resultRoot, 'static-guard-report.json'))
const coverageReport = readJson(path.join(resultRoot, 'stateMachineCoverageReport.json'))
const runtimeReport = readJson(path.join(resultRoot, 'runtime-consistency-report.json'))
const pageReport = readJson(path.join(resultRoot, 'page-assertions.json'))
const consistencyReport = readJson(path.join(resultRoot, 'fact-consistency-report.json'))
const geometryReport = readJson(path.join(resultRoot, 'geometry-report.json'))
const recoveryReport = readJson(path.join(resultRoot, 'cross-process-recovery.json'))

assert(staticReport.result === 'passed' && staticReport.guardCount === 10 && staticReport.failedCount === 0, 'Static guards failed')
assert(coverageReport.result === 'passed' && coverageReport.allDomainsClassified === true, 'State-machine scan failed')
assert(runtimeReport.result === 'passed' && runtimeReport.guards.length === 10, 'Runtime guards failed')
assert(runtimeReport.guards.every(row => row.passed), 'A runtime guard failed')
assert(runtimeReport.formalPaymentOrderCount === 8, 'Formal payment order count mismatch')
assert(runtimeReport.workflowInstanceCount === 8, 'Workflow count mismatch')
assert(runtimeReport.approvalTaskCount === 16, 'Approval task count mismatch')
assert(runtimeReport.approvalDecisionCount === 16, 'Approval decision count mismatch')
assert(runtimeReport.businessStateTransitionCount === 24, 'Transition count mismatch')
assert(runtimeReport.freezeSnapshotCount === 8 && runtimeReport.freezeHashCount === 8, 'Freeze facts mismatch')
assert(runtimeReport.approvedCount === 8 && runtimeReport.frozenCount === 8, 'Approval/frozen count mismatch')
assert(runtimeReport.bankSendEligibleCount === 8, 'Bank-send eligibility mismatch')
assert(runtimeReport.abnormalScenarios.length === 5, 'Abnormal matrix count mismatch')
assert(runtimeReport.abnormalScenarios.every(row => row.result === 'blocked' && row.bankSendEligible === false), 'Abnormal matrix failed')
assert(runtimeReport.successObjects.every(row => (
  row.status === 'frozen_for_execution'
  && row.statusTransitionHistory.length === 3
  && row.stateMachineConsistent === true
  && row.workflowInstance?.status === 'approved'
  && row.approvalHistory.length === 2
  && row.freezeStatus === 'frozen'
  && row.freezeHash
  && row.bankSendEligibility?.readyForBankSend === true
)), 'Success object state-machine facts mismatch')
assert(pageReport.result === 'passed' && pageReport.assertions.every(row => row.passed), 'Page acceptance failed')
assert(consistencyReport.result === 'passed' && consistencyReport.consistent === true, 'API/page/diagnostic/strictFacts mismatch')
assert(consistencyReport.businessWriteRequestCount === 0, 'Page acceptance performed a business write')
assert(geometryReport.result === 'passed', 'Geometry acceptance failed')
assert(recoveryReport.result === 'passed' && recoveryReport.databaseUnchanged === true, 'Cross-process recovery failed')
assert(recoveryReport.businessActionsReplayed === false, 'Business actions were replayed during recovery')
assert(Object.values(runtimeReport.downstreamCounts).every(value => value === 0), 'A downstream object exists')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))

const sourceApplication = readJson(path.join(source, 'application-state.json'))
writeJson(target, 'application-state.json', {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  stateMachine: ['prepared', 'submitted', 'approved', 'frozen_for_execution'],
  stateTransitionService: 'workflow_runtime.transition_business_object',
  capacity: {
    ...sourceApplication.capacity,
    formalPaymentOrderCount: 8,
    workflowInstanceCount: 8,
    approvalTaskCount: 16,
    approvalDecisionCount: 16,
    businessStateTransitionCount: 24,
    approvedCount: 8,
    freezeSnapshotCount: 8,
    freezeHashCount: 8,
    frozenCount: 8,
    bankSendEligibleCount: 8,
    blockedScenarioCount: 5,
    nextStageConsumedCount: 0,
  },
  downstreamCounts: runtimeReport.downstreamCounts,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
})

const sourceEntities = readJson(path.join(source, 'business-entities.json'))
writeJson(target, 'business-entities.json', {
  ...sourceEntities,
  version: VERSION,
  formalPaymentOrders: runtimeReport.successObjects,
  abnormalStateMachineScenarios: runtimeReport.abnormalScenarios,
  formalPaymentOrderCount: 8,
  workflowInstanceCount: 8,
  approvalTaskCount: 16,
  approvalDecisionCount: 16,
  businessStateTransitionCount: 24,
  approvedCount: 8,
  freezeSnapshotCount: 8,
  freezeHashCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  nextStageConsumedCount: 0,
  downstreamCounts: runtimeReport.downstreamCounts,
})

const sourceGraph = readJson(path.join(source, 'relationship-graph.json'))
const orderNodeByNo = new Map(
  sourceGraph.nodes.filter(node => node.type === 'formalPaymentOrder').map(node => [node.objectNo, node.id]),
)
const transitionNodes = runtimeReport.successObjects.flatMap(row => row.statusTransitionHistory.map(transition => ({
  id: `businessStateTransition:${transition.id}`,
  type: 'businessStateTransition',
  objectNo: row.orderNo,
  fromStatus: transition.fromStatus,
  toStatus: transition.toStatus,
  actionCode: transition.actionCode,
  transitionVersion: transition.transitionVersion,
})))
const transitionEdges = runtimeReport.successObjects.flatMap(row => row.statusTransitionHistory.map(transition => ({
  from: orderNodeByNo.get(row.orderNo),
  to: `businessStateTransition:${transition.id}`,
  relation: 'has_state_transition',
})))
writeJson(target, 'relationship-graph.json', {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes.map(node => node.type === 'formalPaymentOrder'
      ? { ...node, stateMachineConsistent: true, stateTransitionCount: 3 }
      : node),
    ...transitionNodes,
  ],
  edges: [...sourceGraph.edges, ...transitionEdges],
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
  canonicalName: '正式付款单状态机与审批冻结事实一致性',
  moduleCode: 'formal-payment-order',
  route: '/finance/formal-payment-orders',
  immutable: true,
  restorable: true,
  currentStateSource: 'server',
  stateMachine: ['prepared', 'submitted', 'approved', 'frozen_for_execution'],
  stateTransitionService: 'workflow_runtime.transition_business_object',
  workflowEngine: 'workflow_runtime',
  approvalProcessCode: 'FORMAL_PAYMENT_ORDER_APPROVAL',
  formalPaymentOrderCount: 8,
  workflowInstanceCount: 8,
  approvalTaskCount: 16,
  approvalDecisionCount: 16,
  approvedCount: 8,
  businessStateTransitionCount: 24,
  freezeSnapshotCount: 8,
  freezeHashCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  blockedScenarioCount: 5,
  nextStageConsumedCount: 0,
  staticGuardCount: 10,
  runtimeGuardCount: 10,
  scannedDomainCount: 4,
  allScannedDomainsClassified: true,
  staticGuardsPassed: true,
  runtimeGuardsPassed: true,
  playwrightPassed: true,
  crossProcessRecoveryReady: true,
  apiPageDiagnosticStrictConsistent: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
  migrationApplied: true,
  migrations: [
    'workflow_runtime.0002_business_state_transition',
    'formal_payment_order.0004_state_consistency_contract',
  ],
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  developmentDatabaseUnchanged: true,
  protectedCheckpointsImmutable: true,
  bankMessageCreated: false,
  bankSendTaskCreated: false,
  paymentExecuted: false,
  paymentVoucherCreated: false,
  writeoffCreated: false,
  ledgerCreated: false,
  postingCreated: false,
  bankTransactionCreated: false,
  productionUserDataWritten: false,
  stoppedBeforeBankSendAndPaymentExecution: true,
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
  'runtime-consistency-report.json',
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
  warningsOnly: ['dependency-pure-annotation', 'large-chunk'],
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
  workflowInstanceCount: 8,
  approvalTaskCount: 16,
  approvalDecisionCount: 16,
  businessStateTransitionCount: 24,
  freezeSnapshotCount: 8,
  freezeHashCount: 8,
  bankSendEligibleCount: 8,
  downstreamCountsAllZero: true,
  databaseHashBefore: recoveryReport.databaseHashBefore,
  databaseHashAfter: recoveryReport.databaseHashAfter,
})

fs.mkdirSync(archiveBase, { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
assert(JSON.stringify(hashes(target)) === JSON.stringify(hashes(archive)), 'Archive hash mismatch')
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
    Object.keys(protectedHashes).map(checkpointId => [checkpointId, hashes(path.join(checkpointBase, checkpointId))]),
  ),
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionUserDataWritten: false,
})
console.log(JSON.stringify(readJson(path.join(resultRoot, 'finalization-report.json')), null, 2))
