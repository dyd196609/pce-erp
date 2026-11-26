import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.2'
const CHECKPOINT_ID = 'pce_business_action_permission_ready'
const SOURCE_CHECKPOINT_ID = 'pce_business_action_real_data_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-permission-v552',
)
const checkpointRoot = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const checkpoint = path.join(checkpointRoot, CHECKPOINT_ID)
const sourceCheckpoint = path.join(checkpointRoot, SOURCE_CHECKPOINT_ID)
const archiveRoot = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
)
const archive = path.join(archiveRoot, CHECKPOINT_ID)
const sourceArchive = path.join(archiveRoot, SOURCE_CHECKPOINT_ID)
const persistentDatabase = path.join(
  workspace,
  'backend',
  'canary-data',
  'purchase-flow-demo.sqlite3',
)
const developmentDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const expectedPersistentDatabaseHash =
  '6320461a88b739933828a0909baa02155fdeb93e17e386c5deb977d9c1e0548d'
const expectedDevelopmentDatabaseHash =
  'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const coreFiles = [
  'manifest.json',
  'storage-state.json',
  'application-state.json',
  'business-entities.json',
  'relationship-graph.json',
]
const protectedHashes = {
  'manifest.json':
    '96787ce3b7908be931c029d9b0dd6eff106834b893f6e94afaa51dbbe07439e5',
  'storage-state.json':
    '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json':
    '015fd2fab1f8052fcf9a08a7ff33d0929a306d2a4b4bc3ea580e74278b50d39f',
  'business-entities.json':
    '490404d0e0337c83e83a0317cdabc3dce1ec63caa183940083d9458ab1328aae',
  'relationship-graph.json':
    'fd631a7ded3e1e5aa8cfd0a68754322d3e1a6978543a3e149d68f237494059a1',
}

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)

const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
const sourceHashes = hashes(sourceCheckpoint)
const sourceArchiveHashes = hashes(sourceArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive hashes differ',
)
assert(
  coreFiles.every(file => sourceHashes[file] === protectedHashes[file]),
  'Protected source checkpoint changed',
)
assert(
  coreFiles.every(file => sourceArchiveHashes[file] === protectedHashes[file]),
  'Protected source archive changed',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent canary database changed',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed',
)

const manifest = readJson(path.join(checkpoint, 'manifest.json'))
const summary = readJson(path.join(
  checkpoint,
  'reports',
  'permission-acceptance-summary.json',
))
assert(manifest.result === 'passed', 'Checkpoint result did not pass')
assert(manifest.version === VERSION, 'Checkpoint version mismatch')
assert(manifest.checkpointId === CHECKPOINT_ID, 'Checkpoint id mismatch')
assert(manifest.immutable === true, 'Checkpoint is not immutable')
assert(manifest.registeredPageCount === 12, 'Page count mismatch')
assert(manifest.registeredActionCount === 34, 'Action count mismatch')
assert(manifest.permissionPolicyCount === 46, 'Policy count mismatch')
assert(manifest.actionPermissionDeclared === true, 'Permission declaration failed')
assert(
  manifest.actionServerValidationRequired === true,
  'Server validation not required',
)
assert(
  manifest.frontendVisibilityNotAuthority === true,
  'Frontend visibility treated as authority',
)
assert(manifest.playwrightPassed === true, 'Playwright did not pass')
assert(manifest.buildPassed === true, 'Build did not pass')
assert(manifest.businessWriteRequestCount === 0, 'Business write detected')
assert(manifest.productionUserDataWritten === false, 'Production data written')
assert(summary.result === 'passed', 'Permission summary did not pass')
assert(summary.roleAcceptancePassed === true, 'Role acceptance failed')
assert(
  summary.organizationScopeAcceptancePassed === true,
  'Organization scope acceptance failed',
)

const recovery = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  immutable: true,
  crossProcessRestorePassed: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointHashes: sourceHashes,
  protectedArchiveHashes: sourceArchiveHashes,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  currentStateSource: 'server',
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
writeJson(path.join(resultRoot, 'cross-process-recovery-report.json'), recovery)
console.log(JSON.stringify(recovery, null, 2))
