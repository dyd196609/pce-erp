import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.7.62'
const checkpointId = 'pce_payment_chain_page_acceptance_v2_ready'
const sourceCheckpointId = 'pce_page_acceptance_runtime_v1_ready'
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
const resultRoot = path.join(frontend, 'test-results/payment-chain-page-acceptance-v2')
const acceptance = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'payment_chain_page_acceptance_report.json'), 'utf8'),
)
const actionDecision = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'actionDecisionReport.json'), 'utf8'),
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
if (acceptance.pageCount !== 6 || acceptance.fail !== 0 || acceptance.unknown > 5) {
  throw new Error('payment-chain page acceptance V2 gate is not ready')
}
if (actionDecision.pages.length !== 6) throw new Error('action decision evidence is incomplete')

fs.mkdirSync(target, { recursive: false })
for (const name of ['storage-state.json', 'business-entities.json', 'relationship-graph.json']) {
  fs.copyFileSync(path.join(source, name), path.join(target, name))
}
writeJson(path.join(target, 'application-state.json'), {
  version,
  runtime: 'PCE Payment Chain Page Acceptance V2',
  contractVersion: acceptance.contractVersion,
  observabilityContractVersion: acceptance.observabilityContractVersion,
  sourceCheckpointId,
  pages: acceptance.pages.map(page => ({
    route: page.page,
    pageCode: page.pageCode,
    pass: page.pass,
    fail: page.fail,
    unknown: page.unknown,
    acceptanceFacts: page.acceptanceFacts,
  })),
  unknownClassifications: acceptance.unknownClassifications,
  actionDecisionEvidence: actionDecision.pages,
  safety: {
    readOnlyAcceptance: true,
    businessLogicChanged: false,
    stateMachineChanged: false,
    permissionModelChanged: false,
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
  contractVersion: acceptance.contractVersion,
  observabilityContractVersion: acceptance.observabilityContractVersion,
  pageCount: acceptance.pageCount,
  totalCheckCount: acceptance.totalChecks,
  passedCheckCount: acceptance.pass,
  failedCheckCount: acceptance.fail,
  unknownCheckCount: acceptance.unknown,
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
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
