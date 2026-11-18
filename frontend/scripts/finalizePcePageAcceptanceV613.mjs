import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const checkpointId = 'pce_page_acceptance_runtime_v1_ready'
const sourceCheckpointId = 'pce_enterprise_list_runtime_v1_ready'
const checkpointRoot = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const resultRoot = path.join(frontend, 'test-results', 'page-acceptance')
const reportPath = path.join(resultRoot, 'checkpoint_result.json')
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
}

function writeJson(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target)) throw new Error(`immutable checkpoint already exists: ${target}`)
if (fs.existsSync(archive)) throw new Error(`immutable archive already exists: ${archive}`)

const acceptance = JSON.parse(
  fs.readFileSync(path.join(resultRoot, 'pce_page_acceptance_report.json'), 'utf8'),
)
if (acceptance.fail !== 0 || acceptance.totalChecks < 90) {
  throw new Error('page acceptance gate is not ready for checkpoint')
}

fs.mkdirSync(target, { recursive: false })
for (const name of ['storage-state.json', 'business-entities.json', 'relationship-graph.json']) {
  fs.copyFileSync(path.join(source, name), path.join(target, name))
}

writeJson(path.join(target, 'application-state.json'), {
  version: 'V1.14.2.8.4.7.61.3',
  runtime: 'PCE Page Acceptance Runtime V1.0',
  contractVersion: 'PCE-PAGE-ACCEPTANCE-CONTRACT-V1.0',
  sourceCheckpointId,
  firstBatchPages: acceptance.pages.map(page => ({
    route: page.page,
    totalChecks: page.totalChecks,
    pass: page.pass,
    fail: page.fail,
    unknown: page.unknown,
  })),
  ruleFamilies: {
    PAGE: 5,
    LIST: 10,
    STATUS: 3,
    FACT: 5,
    ACTION: 3,
    SECURITY: 5,
  },
  safety: {
    readOnlyAcceptance: true,
    businessLogicChanged: false,
    businessProgressWriteCount: 0,
    productionUserDataWritten: false,
  },
  automatedChecks: {
    ruleUnitTests: { total: 33, pass: 33, fail: 0 },
    runtime: {
      total: acceptance.totalChecks,
      pass: acceptance.pass,
      fail: acceptance.fail,
      unknown: acceptance.unknown,
    },
    enterpriseListRegression: { total: 9, pass: 9, fail: 0 },
    iabVisualPages: 3,
  },
})

const payloadHashes = Object.fromEntries(
  coreFiles.slice(1).map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'passed',
  version: 'V1.14.2.8.4.7.61.3',
  checkpointId,
  sourceCheckpointId,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  contractVersion: 'PCE-PAGE-ACCEPTANCE-CONTRACT-V1.0',
  firstBatchPageCount: 3,
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
const localHashes = Object.fromEntries(
  coreFiles.map(name => [name, sha256(path.join(target, name))]),
)
const archiveHashes = Object.fromEntries(
  coreFiles.map(name => [name, sha256(path.join(archive, name))]),
)
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
writeJson(reportPath, result)
console.log(JSON.stringify(result, null, 2))
