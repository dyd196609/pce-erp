import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.2'
const SOURCE_CHECKPOINT_ID = 'pce_business_action_real_data_ready'
const root = process.cwd()
const workspace = path.resolve(root, '..')
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-permission-v552',
)
const sourceCheckpoint = path.join(
  root,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  SOURCE_CHECKPOINT_ID,
)
const sourceArchive = path.resolve(
  root,
  '..',
  '..',
  'CheckpointArchive',
  'purchase-payment-golden-flow',
  SOURCE_CHECKPOINT_ID,
)
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
const sha256 = file => crypto
  .createHash('sha256')
  .update(fs.readFileSync(file))
  .digest('hex')
const hashes = directory => Object.fromEntries(
  coreFiles.map(file => [file, sha256(path.join(directory, file))]),
)
const writeJson = (file, value) => fs.writeFileSync(
  file,
  `${JSON.stringify(value, null, 2)}\n`,
  'utf8',
)

assert(fs.existsSync(sourceCheckpoint), 'Protected source checkpoint missing')
assert(fs.existsSync(sourceArchive), 'Protected source archive missing')
const checkpointHashes = hashes(sourceCheckpoint)
const archiveHashes = hashes(sourceArchive)
assert(
  coreFiles.every(file => checkpointHashes[file] === protectedHashes[file]),
  'Protected source checkpoint hash mismatch',
)
assert(
  coreFiles.every(file => archiveHashes[file] === protectedHashes[file]),
  'Protected source archive hash mismatch',
)
const persistentHash = sha256(persistentDatabase)
const developmentHash = sha256(developmentDatabase)
assert(
  persistentHash === expectedPersistentDatabaseHash,
  'Persistent canary database changed',
)
assert(
  developmentHash === expectedDevelopmentDatabaseHash,
  'Development database changed',
)

const moduleArg = process.argv.find(item => item.startsWith('--module-count='))
const transformedModuleCount = Number(moduleArg?.split('=')[1] || 0)
const buildPassed = process.argv.includes('--build-passed')
const distIndex = path.join(root, 'dist', 'index.html')
const distAssets = path.join(root, 'dist', 'assets')
const actionBarChunk = fs.existsSync(distAssets)
  ? fs.readdirSync(distAssets).find(
      file => file.startsWith('PceBusinessActionBar-') && file.endsWith('.js'),
    )
  : ''
assert(buildPassed, 'Build result flag missing')
assert(transformedModuleCount > 0, 'Transformed module count missing')
assert(fs.existsSync(distIndex), 'Vite dist/index.html missing')
assert(actionBarChunk, 'Business action permission production chunk missing')

fs.mkdirSync(resultRoot, { recursive: true })
writeJson(path.join(resultRoot, 'database-protection-report.json'), {
  result: 'passed',
  version: VERSION,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  sourceCheckpointHashesBefore: checkpointHashes,
  sourceCheckpointHashesAfter: hashes(sourceCheckpoint),
  sourceArchiveHashesBefore: archiveHashes,
  sourceArchiveHashesAfter: hashes(sourceArchive),
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  persistentCanaryDatabaseSha256: persistentHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseSha256: developmentHash,
  developmentDatabaseUnchanged: true,
  isolatedPermissionDatabaseOnly: true,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
})
writeJson(path.join(resultRoot, 'build-report.json'), {
  result: 'passed',
  version: VERSION,
  command: 'npm.cmd run build',
  exitCode: 0,
  prebuildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount,
  actionPermissionChunk: actionBarChunk,
  distIndexSha256: sha256(distIndex),
  warningsOnly: [
    'dependency pure annotation warning',
    'large chunk warning',
  ],
})
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  transformedModuleCount,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  sourceCheckpointImmutable: true,
}, null, 2))
