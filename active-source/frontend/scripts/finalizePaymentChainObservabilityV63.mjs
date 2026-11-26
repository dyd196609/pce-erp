import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.7.63'
const checkpointId = 'pce_payment_chain_observability_complete_ready'
const sourceCheckpointId = 'pce_payment_chain_page_acceptance_v2_ready'
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
const resultRoot = path.join(frontend, 'test-results/payment-chain-observability-v63')
const acceptance = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'payment_chain_page_acceptance_v63_report.json'), 'utf8'),
)
const unknownReduction = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'unknown_reduction_report_v63.json'), 'utf8'),
)
const databaseProtection = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'database-protection-report.json'), 'utf8'),
)
const iab = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'iab_visual_review_report.json'), 'utf8'),
)
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target)) throw new Error(`immutable checkpoint already exists: ${target}`)
if (fs.existsSync(archive)) throw new Error(`immutable archive already exists: ${archive}`)
if (
  acceptance.baseAcceptance.fail !== 0
  || acceptance.baseAcceptance.unknown !== 0
  || acceptance.observabilityFail !== 0
  || acceptance.observabilityPass !== 36
) throw new Error('V63 observability acceptance is not complete')
if (unknownReduction.afterUnknown !== 0) throw new Error('UNKNOWN was not cleared')
if (databaseProtection.productionUserDataWritten !== false) {
  throw new Error('database protection failed')
}
if (iab.result !== 'passed') throw new Error('IAB review did not pass')

fs.mkdirSync(target, { recursive: false })
for (const name of ['storage-state.json', 'business-entities.json', 'relationship-graph.json']) {
  fs.copyFileSync(path.join(source, name), path.join(target, name))
}
writeJson(path.join(target, 'application-state.json'), {
  version,
  runtime: 'PCE Payment Chain Observability Complete',
  sourceCheckpointId,
  contractVersion: acceptance.contractVersion,
  validator: acceptance.validator,
  pageCount: acceptance.pageCount,
  baseAcceptance: acceptance.baseAcceptance,
  observabilityChecks: acceptance.observabilityChecks,
  observabilityPass: acceptance.observabilityPass,
  observabilityFail: acceptance.observabilityFail,
  unknownReduction,
  safety: {
    businessLogicChanged: false,
    stateMachineChanged: false,
    permissionModelChanged: false,
    paymentObjectCreated: false,
    businessProgressWriteCount: 0,
    productionUserDataWritten: false,
  },
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
  unknownBefore: unknownReduction.beforeUnknown,
  unknownAfter: unknownReduction.afterUnknown,
  pageCount: acceptance.pageCount,
  observabilityCheckCount: acceptance.observabilityChecks,
  productionUserDataWritten: false,
  integrityFiles: coreFiles,
  integrityHashes: payloadHashes,
})

fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(coreFiles.map(name => [name, sha256(path.join(target, name))]))
const archiveHashes = Object.fromEntries(coreFiles.map(name => [name, sha256(path.join(archive, name))]))
const archiveMatches = coreFiles.every(name => localHashes[name] === archiveHashes[name])
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
  unknown: 0,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
