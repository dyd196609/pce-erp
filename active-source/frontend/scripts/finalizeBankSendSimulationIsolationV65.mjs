import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.7.65'
const checkpointId = 'bank_send_simulation_isolation_gate_ready'
const sourceCheckpointId = 'bank_send_execution_simulation_ready'
const checkpointRoot = path.join(
  frontend,
  'test-results/purchase-payment-golden-flow/checkpoints',
)
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const resultRoot = path.join(
  frontend,
  'test-results/bank-send-simulation-isolation-v65',
)
const acceptance = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'v65_acceptance_report.json'), 'utf8'),
)
const databaseProtection = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'database_protection_report.json'), 'utf8'),
)
const iab = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'iab_acceptance_report.json'), 'utf8'),
)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
  .toUpperCase()
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target)) throw new Error(`immutable checkpoint already exists: ${target}`)
if (fs.existsSync(archive)) throw new Error(`immutable archive already exists: ${archive}`)
if (acceptance.result !== 'passed' || acceptance.summary.failed !== 0) {
  throw new Error('V65 acceptance is not complete')
}
if (databaseProtection.productionUserDataWritten !== false) {
  throw new Error('database protection failed')
}
if (iab.result !== 'passed') throw new Error('IAB acceptance did not pass')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(
  path.join(source, 'storage-state.json'),
  path.join(target, 'storage-state.json'),
)
writeJson(path.join(target, 'application-state.json'), {
  version,
  runtime: 'Bank Send Simulation Audit and Production Isolation Gate',
  sourceCheckpointId,
  stateMachine: acceptance.stateMachine,
  fiveSurfaceFacts: acceptance.fiveSurfaceFacts,
  protection: acceptance.protection,
  databaseProtection,
  iabAcceptance: iab,
})
writeJson(path.join(target, 'business-entities.json'), {
  version,
  currentStateSource: 'server',
  entities: [
    {
      entityType: 'BankSendSimulationAudit',
      recordCount: 9,
      simulationCount: 2,
      auditTypes: [
        'simulation_created',
        'simulation_validated',
        'simulation_started',
        'simulation_completed',
        'simulation_failed',
        'simulation_recovered',
      ],
    },
    {
      entityType: 'BankSendProductionIsolationGate',
      recordCount: 1,
      status: 'isolated',
      statusLabel: '隔离有效',
      productionConnectionEnabled: false,
      productionSecretAvailable: false,
      productionSendAllowed: false,
      paymentExecutionAllowed: false,
    },
  ],
  forbiddenEntities: {
    bankMessageSent: 0,
    paymentExecution: 0,
    bankTransaction: 0,
    paymentVoucher: 0,
    ledgerEntry: 0,
  },
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'BankSendExecutionSimulation', terminalStates: ['simulation_success', 'simulation_failed'] },
    { id: 'BankSendSimulationAudit', role: 'independent_audit_record' },
    { id: 'BankSendProductionIsolationGate', terminalState: 'isolated' },
    { id: 'ProductionBankSend', state: 'blocked' },
  ],
  edges: [
    { from: 'BankSendExecutionSimulation', to: 'BankSendSimulationAudit', writeIntent: 'simulation_audit_write' },
    { from: 'BankSendProductionIsolationGate:created', to: 'BankSendProductionIsolationGate:checked', service: 'BusinessStateTransition' },
    { from: 'BankSendProductionIsolationGate:checked', to: 'BankSendProductionIsolationGate:isolated', service: 'BusinessStateTransition' },
  ],
  forbiddenEdges: [
    'BankSendExecutionSimulation -> ProductionBankSend',
    'isolated -> approved_for_send',
    'isolated -> sent',
  ],
  isolationRules: [
    'ISOLATION-001',
    'ISOLATION-002',
    'ISOLATION-003',
    'ISOLATION-004',
    'ISOLATION-005',
    'ISOLATION-006',
  ],
})
const payloadHashes = Object.fromEntries(
  coreFiles.slice(1).map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'passed',
  version,
  checkpointId,
  sourceCheckpointId,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  productionUserDataWritten: false,
  integrityFiles: coreFiles,
  integrityHashes: payloadHashes,
})
fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(
  coreFiles.map(name => [name, sha256(path.join(target, name))]),
)
const archiveHashes = Object.fromEntries(
  coreFiles.map(name => [name, sha256(path.join(archive, name))]),
)
const archiveMatches = coreFiles.every(
  name => localHashes[name] === archiveHashes[name],
)
if (!archiveMatches) throw new Error('checkpoint archive hash mismatch')
const result = {
  result: 'passed',
  checkpointId,
  sourceCheckpointId,
  immutable: true,
  localPath: target,
  archivePath: archive,
  fiveHashes: localHashes,
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
