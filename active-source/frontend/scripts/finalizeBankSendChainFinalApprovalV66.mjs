import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.7.66'
const checkpointId = 'bank_send_final_approval_isolation_ready'
const sourceCheckpointId = 'bank_send_simulation_isolation_gate_ready'
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
  'test-results/bank-send-chain-final-approval-v66',
)
const acceptance = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'v66_acceptance_report.json'), 'utf8'),
)
const databaseProtection = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'database_protection_report.json'), 'utf8'),
)
const iab = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'iab_acceptance_report.json'), 'utf8'),
)
const scan = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'bank_send_chain_trace_scan_v66.json'), 'utf8'),
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

if (!fs.existsSync(source)) {
  throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
}
if (fs.existsSync(target)) {
  throw new Error(`immutable checkpoint already exists: ${target}`)
}
if (fs.existsSync(archive)) {
  throw new Error(`immutable archive already exists: ${archive}`)
}
if (acceptance.result !== 'passed' || acceptance.summary.failed !== 0) {
  throw new Error('V66 acceptance is not complete')
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
  runtime: 'Bank Send Full Chain Trace and Final Approval Isolation',
  sourceCheckpointId,
  architectureScan: scan,
  finalApproval: acceptance.finalApproval,
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
      entityType: 'BankSendChainTrace',
      recordCount: acceptance.chainTrace.traceCount,
      completeTraceCount: acceptance.chainTrace.completeTraceCount,
      nodeCount: acceptance.chainTrace.nodeCount,
      missingNodeCount: acceptance.chainTrace.missingNodeCount,
    },
    {
      entityType: 'BankSendFinalApproval',
      recordCount: 1,
      status: 'final_locked',
      statusLabel: '最终审批已锁定',
      dualPersonApprovalCount:
        acceptance.finalApproval.dualPersonApprovalCount,
      firstApprover: acceptance.finalApproval.firstApprover,
      firstRole: acceptance.finalApproval.firstRole,
      secondApprover: acceptance.finalApproval.secondApprover,
      secondRole: acceptance.finalApproval.secondRole,
      bankSent: false,
    },
  ],
  forbiddenEntities: {
    approvedToSend: 0,
    bankMessageSent: 0,
    paymentExecution: 0,
    fundsDebit: 0,
    bankTransaction: 0,
    paymentVoucher: 0,
    ledgerEntry: 0,
  },
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: acceptance.chainTrace.expectedNodes.map((id, index) => ({
    id,
    order: index + 1,
    source: 'server',
  })).concat([
    {
      id: 'BankSendFinalApproval',
      terminalState: 'final_locked',
      bankSent: false,
    },
    { id: 'ProductionBankSend', state: 'blocked' },
  ]),
  edges: [
    ...acceptance.chainTrace.expectedNodes.slice(0, -1).map((from, index) => ({
      from,
      to: acceptance.chainTrace.expectedNodes[index + 1],
      relation: 'server_trace',
    })),
    {
      from: 'BankSendFinalApproval:pending',
      to: 'BankSendFinalApproval:first_approved',
      service: 'BusinessStateTransition',
    },
    {
      from: 'BankSendFinalApproval:first_approved',
      to: 'BankSendFinalApproval:second_approved',
      service: 'BusinessStateTransition',
    },
    {
      from: 'BankSendFinalApproval:second_approved',
      to: 'BankSendFinalApproval:final_locked',
      service: 'BusinessStateTransition',
    },
  ],
  forbiddenEdges: [
    'pending -> second_approved',
    'pending -> final_locked',
    'final_locked -> approved_to_send',
    'final_locked -> sent',
    'BankSendFinalApproval -> ProductionBankSend',
  ],
  finalChecks: Array.from(
    { length: 8 },
    (_, index) => `FINAL-00${index + 1}`,
  ),
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
  bankSent: false,
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
  bankSent: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
