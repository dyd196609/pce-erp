import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.7.67'
const checkpointId = 'bank_send_production_release_isolation_ready'
const sourceCheckpointId = 'bank_send_final_approval_isolation_ready'
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const resultRoot = path.join(frontend, 'test-results/bank-send-production-release-v67')
const acceptance = JSON.parse(fs.readFileSync(path.join(resultRoot, 'v67_acceptance_report.json')))
const databaseProtection = JSON.parse(fs.readFileSync(path.join(resultRoot, 'database_protection_report.json')))
const iab = JSON.parse(fs.readFileSync(path.join(resultRoot, 'iab_acceptance_report.json')))
const scan = JSON.parse(fs.readFileSync(path.join(resultRoot, 'bank_send_production_release_scan_v67.json')))
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto.createHash('sha256')
  .update(fs.readFileSync(file)).digest('hex').toUpperCase()
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target)) throw new Error(`immutable checkpoint exists: ${target}`)
if (fs.existsSync(archive)) throw new Error(`immutable archive exists: ${archive}`)
if (acceptance.result !== 'passed' || acceptance.summary.failed !== 0) {
  throw new Error('V67 acceptance failed')
}
if (databaseProtection.productionUserDataWritten !== false || iab.result !== 'passed') {
  throw new Error('V67 safety evidence failed')
}

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
writeJson(path.join(target, 'application-state.json'), {
  version,
  runtime: 'Bank Send Production Dual Isolation and Manual Release Review',
  sourceCheckpointId,
  architectureScan: scan,
  dualIsolation: acceptance.dualIsolation,
  manualReleaseReview: acceptance.manualReleaseReview,
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
      entityType: 'BankSendDualIsolationCheck',
      recordCount: 1,
      result: 'passed',
      categories: ['environment_check', 'credential_check', 'permission_check', 'interface_check'],
    },
    {
      entityType: 'BankSendProductionReleaseReview',
      recordCount: 1,
      status: 'locked',
      statusLabel: '生产评审已锁定',
      reviewerCount: acceptance.manualReleaseReview.decisions.length,
      productionReviewMeansSent: false,
    },
  ],
  forbiddenEntities: {
    sendAllowed: 0,
    bankMessageSent: 0,
    paymentExecution: 0,
    fundsDebit: 0,
    bankTransaction: 0,
    ledgerEntry: 0,
  },
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'BankSendFinalApproval', state: 'final_locked' },
    { id: 'BankSendDualIsolationCheck', state: 'passed' },
    { id: 'BankSendProductionReleaseReview', state: 'locked' },
    { id: 'ProductionBankSend', state: 'blocked' },
  ],
  edges: [
    { from: 'BankSendFinalApproval', to: 'BankSendDualIsolationCheck', relation: 'isolation_proof' },
    { from: 'BankSendDualIsolationCheck', to: 'BankSendProductionReleaseReview', relation: 'manual_review_source' },
    { from: 'draft', to: 'reviewing', service: 'BusinessStateTransition' },
    { from: 'reviewing', to: 'review_passed', service: 'BusinessStateTransition' },
    { from: 'review_passed', to: 'locked', service: 'BusinessStateTransition' },
  ],
  forbiddenEdges: [
    'final_locked -> sent',
    'locked -> send_allowed',
    'locked -> sent',
    'BankSendProductionReleaseReview -> ProductionBankSend',
  ],
  releaseChecks: Array.from({ length: 10 }, (_, i) => `RELEASE-${String(i + 1).padStart(3, '0')}`),
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
const localHashes = Object.fromEntries(coreFiles.map(name => [name, sha256(path.join(target, name))]))
const archiveHashes = Object.fromEntries(coreFiles.map(name => [name, sha256(path.join(archive, name))]))
const archiveMatches = coreFiles.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('archive hash mismatch')
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
