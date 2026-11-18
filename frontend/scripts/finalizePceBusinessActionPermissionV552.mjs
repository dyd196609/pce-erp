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
const reportFiles = [
  'permission-coverage-report.json',
  'action-permission-matrix.json',
  'server-validation-report.json',
  'playwright-permission-report.json',
  'database-protection-report.json',
  'build-report.json',
]
const screenshotFiles = [
  '01-viewer-single-action-denied.png',
  '02-operator-single-action-granted.png',
  '03-batch-operator-action-granted.png',
  '04-out-of-scope-view-empty.png',
]

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
const listFiles = directory => fs.existsSync(directory)
  ? fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => (
      entry.isDirectory()
        ? listFiles(path.join(directory, entry.name))
        : [path.join(directory, entry.name)]
    ))
  : []

assert(!fs.existsSync(checkpoint), `Target checkpoint already exists: ${checkpoint}`)
assert(!fs.existsSync(archive), `Target archive already exists: ${archive}`)
assert(fs.existsSync(sourceCheckpoint), 'Protected source checkpoint missing')
assert(fs.existsSync(sourceArchive), 'Protected source archive missing')
const sourceHashesBefore = hashes(sourceCheckpoint)
const sourceArchiveHashesBefore = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesBefore[file] === protectedHashes[file]),
  'Protected source checkpoint hash mismatch',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesBefore[file] === protectedHashes[file],
  ),
  'Protected source archive hash mismatch',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent canary database changed',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed',
)

const reports = Object.fromEntries(reportFiles.map(file => {
  const reportPath = path.join(resultRoot, file)
  assert(fs.existsSync(reportPath), `Required report missing: ${file}`)
  const report = readJson(reportPath)
  assert(report.result === 'passed', `Required report failed: ${file}`)
  return [file, report]
}))
const coverage = reports['permission-coverage-report.json']
const matrix = reports['action-permission-matrix.json']
const server = reports['server-validation-report.json']
const playwright = reports['playwright-permission-report.json']
const database = reports['database-protection-report.json']
const build = reports['build-report.json']
assert(coverage.blockerCount === 0, 'Permission static blocker found')
assert(coverage.moduleCount === 12, 'Permission module count mismatch')
assert(coverage.registryActionCount === 34, 'Registry action count mismatch')
assert(matrix.actionCount === 34, 'Permission action matrix mismatch')
assert(server.currentStateSource === 'server', 'API state is not server sourced')
assert(server.roles.viewer.singleActionStatus === 403, 'Viewer was not denied')
assert(server.roles.operator.singleActionStatus === 200, 'Operator was denied')
assert(server.roles.operator.batchActionStatus === 403, 'Operator batch was allowed')
assert(server.roles.batchOperator.batchActionStatus === 200, 'Batch role denied')
assert(server.roles.outOfScope.viewCount === 0, 'Out-of-scope data was exposed')
assert(playwright.currentStateSource === 'server', 'Browser facts not server sourced')
assert(playwright.roles.viewer.directApiStatus === 403, 'Browser viewer not denied')
assert(playwright.roles.operator.singleActionEnabled, 'Browser single action denied')
assert(playwright.roles.batchOperator.batchActionEnabled, 'Browser batch denied')
assert(playwright.roles.outOfScope.viewCount === 0, 'Browser scope exposure')
assert(playwright.businessWriteRequestCount === 0, 'Browser business write detected')
assert(database.persistentDatabaseUnchanged, 'Persistent database changed')
assert(database.developmentDatabaseUnchanged, 'Development database changed')
assert(build.exitCode === 0, 'Build failed')
assert(build.viteProductionBuildCompleted, 'Vite production build incomplete')

const screenshots = Object.fromEntries(screenshotFiles.map(file => {
  const screenshot = path.join(resultRoot, 'screenshots', file)
  assert(fs.existsSync(screenshot), `Required screenshot missing: ${file}`)
  return [file, sha256(screenshot)]
}))
const traceFiles = listFiles(path.join(resultRoot, 'playwright-output'))
  .filter(file => path.basename(file) === 'trace.zip')
assert(traceFiles.length > 0, 'Playwright trace missing')
const traceFile = traceFiles[0]

const sourceManifest = readJson(path.join(sourceCheckpoint, 'manifest.json'))
const sourceApplication = readJson(
  path.join(sourceCheckpoint, 'application-state.json'),
)
const sourceEntities = readJson(
  path.join(sourceCheckpoint, 'business-entities.json'),
)
const sourceGraph = readJson(
  path.join(sourceCheckpoint, 'relationship-graph.json'),
)
const manifest = {
  ...sourceManifest,
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: VERSION,
  checkpointId: CHECKPOINT_ID,
  sourceCheckpointId: SOURCE_CHECKPOINT_ID,
  canonicalName: 'PCE业务动作权限统一治理',
  permissionContractVersion: 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
  registeredPageCount: 12,
  registeredActionCount: 34,
  permissionPolicyCount: 46,
  actionPermissionDeclared: true,
  actionServerValidationRequired: true,
  frontendVisibilityNotAuthority: true,
  roleAcceptancePassed: true,
  organizationScopeAcceptancePassed: true,
  directForbiddenApiStatus: 403,
  currentStateSource: 'server',
  playwrightPassed: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: build.transformedModuleCount,
  sourceCheckpointImmutable: true,
  sourceArchiveImmutable: true,
  persistentDatabaseSha256: expectedPersistentDatabaseHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseSha256: expectedDevelopmentDatabaseHash,
  developmentDatabaseUnchanged: true,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerCreated: false,
  productionUserDataWritten: false,
  immutable: true,
  restorable: true,
  archiveHashVerified: true,
}
const application = {
  ...sourceApplication,
  version: VERSION,
  currentStateSource: 'server',
  businessActionPermission: {
    result: 'passed',
    contractVersion: 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
    moduleCount: 12,
    registryActionCount: 34,
    permissionPolicyCount: 46,
    frontendVisibilityIsAuthority: false,
    serverValidationRequired: true,
    roleAcceptancePassed: true,
    organizationScopeAcceptancePassed: true,
  },
}
const entities = {
  ...sourceEntities,
  version: VERSION,
  businessActionPermission: {
    roleCodes: [
      'pce_business_viewer',
      'pce_business_operator',
      'pce_business_batch_operator',
      'pce_business_admin',
    ],
    authorityObjects: [
      'UserOrganizationRoleAuthority',
      'Role',
      'Permission',
      'RolePermission',
    ],
    organizationScope: 'legal_entity',
    serverValidator: 'workflow_runtime.ActionPermissionValidator',
  },
}
const nodeId = 'business-action-permission-v552'
const graph = {
  ...sourceGraph,
  version: VERSION,
  nodes: [
    ...sourceGraph.nodes,
    {
      id: nodeId,
      type: 'businessActionPermissionAcceptance',
      result: 'passed',
      currentStateSource: 'server',
      contractVersion: 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
    },
  ],
  edges: [
    ...sourceGraph.edges,
    {
      from: `checkpoint:${SOURCE_CHECKPOINT_ID}`,
      to: nodeId,
      type: 'permissionGovernedByServer',
    },
    {
      from: nodeId,
      to: 'module:payment-instruction-prepare',
      type: 'authorizedNavigationOnlyNoDownstreamWrite',
    },
  ],
}

fs.mkdirSync(checkpoint, { recursive: false })
fs.copyFileSync(
  path.join(sourceCheckpoint, 'storage-state.json'),
  path.join(checkpoint, 'storage-state.json'),
)
writeJson(path.join(checkpoint, 'manifest.json'), manifest)
writeJson(path.join(checkpoint, 'application-state.json'), application)
writeJson(path.join(checkpoint, 'business-entities.json'), entities)
writeJson(path.join(checkpoint, 'relationship-graph.json'), graph)

const checkpointReports = path.join(checkpoint, 'reports')
const screenshotEvidence = path.join(checkpoint, 'evidence', 'screenshots')
const playwrightEvidence = path.join(checkpoint, 'evidence', 'playwright')
fs.mkdirSync(checkpointReports, { recursive: true })
fs.mkdirSync(screenshotEvidence, { recursive: true })
fs.mkdirSync(playwrightEvidence, { recursive: true })
for (const file of reportFiles) {
  fs.copyFileSync(path.join(resultRoot, file), path.join(checkpointReports, file))
}
for (const file of screenshotFiles) {
  fs.copyFileSync(
    path.join(resultRoot, 'screenshots', file),
    path.join(screenshotEvidence, file),
  )
}
fs.copyFileSync(traceFile, path.join(playwrightEvidence, 'trace.zip'))
writeJson(path.join(checkpointReports, 'permission-acceptance-summary.json'), {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  contractVersion: 'PCE-BUSINESS-ACTION-PERMISSION-V1.0',
  moduleCount: 12,
  actionCount: 34,
  policyCount: 46,
  roleAcceptancePassed: true,
  organizationScopeAcceptancePassed: true,
  frontendVisibilityIsAuthority: false,
  serverValidationRequired: true,
  currentStateSource: 'server',
  screenshotHashes: screenshots,
  traceSha256: sha256(traceFile),
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
})

fs.mkdirSync(archiveRoot, { recursive: true })
fs.cpSync(checkpoint, archive, { recursive: true })
const checkpointHashes = hashes(checkpoint)
const archiveHashes = hashes(archive)
assert(
  coreFiles.every(file => checkpointHashes[file] === archiveHashes[file]),
  'Checkpoint/archive hashes differ',
)
const sourceHashesAfter = hashes(sourceCheckpoint)
const sourceArchiveHashesAfter = hashes(sourceArchive)
assert(
  coreFiles.every(file => sourceHashesAfter[file] === protectedHashes[file]),
  'Protected source checkpoint changed during finalization',
)
assert(
  coreFiles.every(
    file => sourceArchiveHashesAfter[file] === protectedHashes[file],
  ),
  'Protected source archive changed during finalization',
)
assert(
  sha256(persistentDatabase) === expectedPersistentDatabaseHash,
  'Persistent database changed during finalization',
)
assert(
  sha256(developmentDatabase) === expectedDevelopmentDatabaseHash,
  'Development database changed during finalization',
)

const finalization = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT_ID,
  checkpointPath: checkpoint,
  archivePath: archive,
  immutable: true,
  crossProcessRestoreReady: true,
  checkpointHashes,
  archiveHashes,
  protectedCheckpointHashesBefore: sourceHashesBefore,
  protectedCheckpointHashesAfter: sourceHashesAfter,
  protectedArchiveHashesBefore: sourceArchiveHashesBefore,
  protectedArchiveHashesAfter: sourceArchiveHashesAfter,
  persistentDatabaseSha256: sha256(persistentDatabase),
  developmentDatabaseSha256: sha256(developmentDatabase),
  businessWriteRequestCount: 0,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'finalization-report.json'), finalization)
console.log(JSON.stringify(finalization, null, 2))
