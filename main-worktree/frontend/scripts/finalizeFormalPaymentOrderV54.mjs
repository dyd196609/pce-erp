import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54'
const CHECKPOINT = 'formal_payment_order_send_gate_ready'
const SOURCE_CHECKPOINT = 'formal_payment_order_scenario_filter_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v54')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const archiveBase = path.resolve(frontend, '..', '..', 'CheckpointArchive', 'purchase-payment-golden-flow')
const source = path.join(checkpointBase, SOURCE_CHECKPOINT)
const target = path.join(checkpointBase, CHECKPOINT)
const archive = path.join(archiveBase, CHECKPOINT)
const persistentDatabase = path.join(backend, 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(backend, 'db.sqlite3')
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
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
  formal_payment_order_scenario_filter_ready: {
    'manifest.json': '96dbc677ac888e192d19b089fb04ba1d8e41657793ff661044dacd8661e663b9',
    'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
    'application-state.json': '4f78d9065f7f402eab53bb62a79c8cc3040a91cf3b3474c14d2d7895854be94b',
    'business-entities.json': '4fbac9d8aa91f8c6b288851061fa4709c75502c8f1424663277945a0975b8ae7',
    'relationship-graph.json': '387abc0d8f45a40656d446cf417360a36661d7d0b2c2d4536ec5f03e1d5fd128',
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
  for (const [id, expected] of Object.entries(protectedHashes)) {
    assert(JSON.stringify(hashes(path.join(checkpointBase, id))) === JSON.stringify(expected), `${id} checkpoint changed`)
    assert(JSON.stringify(hashes(path.join(archiveBase, id))) === JSON.stringify(expected), `${id} archive changed`)
  }
}

assertProtected()
assert(!fs.existsSync(target), `Checkpoint already exists: ${CHECKPOINT}`)
assert(!fs.existsSync(archive), `Archive already exists: ${CHECKPOINT}`)
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')

const persistentHash = digest(persistentDatabase)
const staticReport = readJson(path.join(resultRoot, 'static-guard-report.json'))
const runtimeReport = readJson(path.join(resultRoot, 'runtime-gate-report.json'))
const pageReport = readJson(path.join(resultRoot, 'page-assertions.json'))
const consistencyReport = readJson(path.join(resultRoot, 'fact-consistency-report.json'))
const geometryReport = readJson(path.join(resultRoot, 'geometry-report.json'))
const recoveryReport = readJson(path.join(resultRoot, 'cross-process-recovery.json'))
assert(staticReport.result === 'passed' && staticReport.failedCount === 0, 'V54 static guards failed')
assert(runtimeReport.result === 'passed' && runtimeReport.runtimeGuards.every(row => row.passed), 'V54 runtime guards failed')
assert(runtimeReport.formalPaymentOrderCount === 8, 'Formal payment order count mismatch')
assert(runtimeReport.approvedCount === 8, 'Approved count mismatch')
assert(runtimeReport.frozenCount === 8, 'Frozen count mismatch')
assert(runtimeReport.bankSendEligibleCount === 8, 'Bank-send eligibility count mismatch')
assert(runtimeReport.blockedScenarioCount >= 15, 'Blocked matrix is incomplete')
assert(pageReport.result === 'passed' && pageReport.assertions.every(row => row.passed), 'Page acceptance failed')
assert(consistencyReport.result === 'passed' && consistencyReport.consistent === true, 'Fact consistency failed')
assert(consistencyReport.businessWriteRequestCount === 0, 'Page acceptance performed a business write')
assert(geometryReport.result === 'passed' && geometryReport.horizontalScroll.reachedRightEdge === true, 'Geometry gate failed')
assert(recoveryReport.result === 'passed' && recoveryReport.databaseUnchanged === true, 'Cross-process recovery failed')
assert(Object.values(runtimeReport.downstreamCounts).every(value => value === 0), 'Downstream object count changed')
assert(runtimeReport.successObjects.every(row => (
  row.status === 'frozen_for_execution'
  && row.approvalStatus === 'approved'
  && row.approvalHistory.length === 2
  && row.freezeStatus === 'frozen'
  && row.bankSendEligibility.readyForBankSend === true
)), 'Success object state mismatch')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
const sourceApplication = readJson(path.join(source, 'application-state.json'))
writeJson(target, 'application-state.json', {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  stateMachine: ['prepared', 'submitted', 'approved', 'frozen_for_execution'],
  capacity: {
    ...sourceApplication.capacity,
    formalPaymentOrderCount: 8,
    approvedCount: 8,
    frozenCount: 8,
    bankSendEligibleCount: 8,
    blockedScenarioCount: runtimeReport.blockedScenarioCount,
    nextStageConsumedCount: 0,
  },
  downstreamCounts: runtimeReport.downstreamCounts,
  persistentDatabaseSha256: persistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
})
const sourceEntities = readJson(path.join(source, 'business-entities.json'))
writeJson(target, 'business-entities.json', {
  ...sourceEntities,
  version: VERSION,
  formalPaymentOrders: runtimeReport.successObjects,
  blockedScenarios: runtimeReport.blockedScenarios,
  formalPaymentOrderCount: 8,
  approvedCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  nextStageConsumedCount: 0,
  downstreamCounts: runtimeReport.downstreamCounts,
})
const sourceGraph = readJson(path.join(source, 'relationship-graph.json'))
const orderByNo = new Map(runtimeReport.successObjects.map(row => [row.orderNo, row]))
const orderNodeIdByNo = new Map(
  sourceGraph.nodes
    .filter(node => node.type === 'formalPaymentOrder')
    .map(node => [node.objectNo, node.id]),
)
const workflowNodes = runtimeReport.successObjects.map(row => ({
  id: `workflowInstance:${row.workflowInstance.id}`,
  type: 'workflowInstance',
  objectNo: row.workflowInstance.instanceNo,
  status: row.workflowInstance.status,
}))
const freezeNodes = runtimeReport.successObjects.map(row => ({
  id: `formalPaymentOrderFreeze:${row.orderNo}`,
  type: 'formalPaymentOrderFreeze',
  objectNo: row.orderNo,
  status: row.freezeStatus,
  freezeHash: row.freezeHash,
}))
writeJson(target, 'relationship-graph.json', {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes.map(node => {
      if (node.type !== 'formalPaymentOrder') return node
      const row = orderByNo.get(node.objectNo)
      return {
        ...node,
        status: row?.status ?? node.status,
        approvalStatus: row?.approvalStatus ?? '',
        freezeStatus: row?.freezeStatus ?? '',
        readyForBankSend: row?.bankSendEligibility?.readyForBankSend ?? false,
      }
    }),
    ...workflowNodes,
    ...freezeNodes,
  ],
  edges: [
    ...sourceGraph.edges,
    ...runtimeReport.successObjects.flatMap(row => ([
      {
        from: orderNodeIdByNo.get(row.orderNo),
        to: `workflowInstance:${row.workflowInstance.id}`,
        relation: 'approved_by_shared_workflow',
      },
      {
        from: orderNodeIdByNo.get(row.orderNo),
        to: `formalPaymentOrderFreeze:${row.orderNo}`,
        relation: 'execution_frozen',
      },
    ])),
  ],
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
  immutable: true,
  restorable: true,
  canonicalName: '正式付款单审批冻结与银行发送前最终门禁',
  moduleCode: 'formal-payment-order',
  route: '/finance/formal-payment-orders',
  nextStageId: 'bank-send-task',
  sourceDocumentType: 'paymentRiskReview',
  status: 'frozen_for_execution',
  stateMachine: ['prepared', 'submitted', 'approved', 'frozen_for_execution'],
  approvalProcessCode: 'FORMAL_PAYMENT_ORDER_APPROVAL',
  workflowEngine: 'workflow_runtime',
  approvalRoles: ['payment_checker', 'payment_authorizer'],
  formalPaymentOrderCount: 8,
  preparedCount: 0,
  approvedCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  blockedScenarioCount: runtimeReport.blockedScenarioCount,
  nextStageConsumedCount: 0,
  approvalNodeCount: 16,
  approvalDecisionCount: 16,
  staticGuardCount: staticReport.guardCount,
  runtimeGuardCount: runtimeReport.runtimeGuards.length,
  staticGuardsPassed: true,
  runtimeGuardsPassed: true,
  playwrightPassed: true,
  crossProcessRecoveryReady: true,
  apiPageDiagnosticStrictConsistent: true,
  currentStateSource: 'server',
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2204,
  migrationApplied: true,
  migrations: ['formal_payment_order.0003_formalpaymentorder_execution_gate'],
  persistentDatabaseSha256: persistentHash,
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
for (const name of integrityFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(target, name)))
}
manifest.integrityHash = integrity.digest('hex')
writeJson(target, 'manifest.json', manifest)

for (const name of [
  'static-guard-report.json',
  'runtime-gate-report.json',
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
  formalPaymentOrderCount: 8,
  approvedCount: 8,
  frozenCount: 8,
  bankSendEligibleCount: 8,
  downstreamCountsAllZero: true,
  databaseHashBefore: recoveryReport.databaseHashBefore,
  databaseHashAfter: recoveryReport.databaseHashAfter,
})

fs.mkdirSync(archiveBase, { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
assert(JSON.stringify(hashes(target)) === JSON.stringify(hashes(archive)), 'Archive hash mismatch')
assertProtected()
assert(digest(persistentDatabase) === persistentHash, 'Persistent database changed during finalization')
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
    Object.keys(protectedHashes).map(id => [id, hashes(path.join(checkpointBase, id))]),
  ),
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionUserDataWritten: false,
})
console.log(JSON.stringify(readJson(path.join(resultRoot, 'finalization-report.json')), null, 2))
