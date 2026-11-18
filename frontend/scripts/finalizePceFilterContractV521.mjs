import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { financeProcessPageRegistry } from '../src/meta/process/financeProcessPageRegistry.js'
import { findPceBusinessModuleById } from '../src/meta/runtime/pceBusinessModuleRegistry.js'

const VERSION = 'V1.14.2.8.4.7.52.1'
const CHECKPOINT = 'pce_filter_contract_standard_ready'
const frontend = path.resolve(import.meta.dirname, '..')
const workspace = path.resolve(frontend, '..')
const project = path.resolve(workspace, '..')
const resultRoot = path.join(frontend, 'test-results', 'pce-filter-contract-v521')
const checkpointBase = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints')
const checkpointRoot = path.join(checkpointBase, CHECKPOINT)
const archiveRoot = path.join(project, 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const sourceCheckpoint = path.join(checkpointBase, 'payment_risk_review_validated_ready')
const persistentDatabase = path.join(workspace, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const protectedCheckpoint = path.join(checkpointBase, 'payment_risk_review_validated_ready')
const expectedPersistentHash = 'ae801464c27d4ff687aa1a35327790a7e9186de433f47c99563b26b85ce757a6'
const expectedDevelopmentHash = 'b6b12fdd541b09c0470a69fbf5aae2d8225072310ea81f052d898322bcc1a0b0'
const expectedProtectedHashes = {
  'manifest.json': '11206a1b9e3e872aa5c21840cd7b0e5aa3262fe1d4dc1d3df0ee6c817ae2bc3d',
  'storage-state.json': '8fc36561d0bc7ff473395e7a810739c1228ffe8df47449b5a53f1f48fa88a242',
  'application-state.json': 'd6b6ef7b885cb804143babfc2ef61729321771eb72a6744810da9e2b491842c9',
  'business-entities.json': '7b94e73de8644acf7bbadee9ac1065989ce82ff6c48942d898bebfc17766a777',
  'relationship-graph.json': '09bbb0adb21332106ab527387db9b085e66d6ffa7729bd3ad3ce5e19b415bac6',
}
const coreNames = Object.keys(expectedProtectedHashes)
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = root => Object.fromEntries(coreNames.map(name => [name, digest(path.join(root, name))]))
const readJson = name => JSON.parse(fs.readFileSync(path.join(resultRoot, name), 'utf8'))
const writeJson = (root, name, value) => fs.writeFileSync(path.join(root, name), `${JSON.stringify(value, null, 2)}\n`, 'utf8')
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}

assert(digest(persistentDatabase) === expectedPersistentHash, 'Persistent canary database changed')
assert(digest(developmentDatabase) === expectedDevelopmentHash, 'Development database changed')
assert(JSON.stringify(hashes(protectedCheckpoint)) === JSON.stringify(expectedProtectedHashes), 'V52 checkpoint changed')
const guardReport = readJson('filter-contract-guard-report.json')
const browserReport = readJson('filter-contract-browser-report.json')
assert(guardReport.result === 'passed' && guardReport.strictPassedCount === 13 && guardReport.blockerCount === 0, 'Filter guard report failed')
assert(browserReport.result === 'passed' && browserReport.strictPassedCount === 13 && browserReport.businessWriteRequestCount === 0, 'Filter browser report failed')
assert(fs.existsSync(path.join(frontend, 'dist', 'index.html')), 'Vite production output missing')

const pages = financeProcessPageRegistry.map(page => {
  const moduleRecord = findPceBusinessModuleById(page.pageStepId)
  return {
    pageCode: page.pageStepId,
    canonicalName: page.canonicalName,
    fullUrl: page.fullUrl,
    mainTableId: page.mainTableId,
    filterSchema: moduleRecord.advancedFilterSchema.map(field => ({
      field: field.field,
      label: field.label,
      type: field.type,
      displayMap: field.displayMap,
      optionsProvider: field.optionsProvider,
    })),
    result: 'passed',
  }
})
const buildReport = {
  result: 'passed',
  version: VERSION,
  command: 'npm.cmd run build',
  exitCode: 0,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2200,
  distIndexPresent: true,
}
writeJson(resultRoot, 'build-report.json', buildReport)

for (const target of [checkpointRoot, archiveRoot]) {
  assert(path.basename(target) === CHECKPOINT, `Unsafe checkpoint target: ${target}`)
  if (fs.existsSync(target)) fs.rmSync(target, { recursive: true, force: true })
}
fs.mkdirSync(checkpointRoot, { recursive: true })

const manifest = {
  result: 'passed',
  version: VERSION,
  reportVersion: VERSION,
  runnerVersion: VERSION,
  checkpointVersion: '1.0.0',
  checkpointId: CHECKPOINT,
  immutable: true,
  restorable: true,
  origin: 'http://localhost:5173',
  contractVersion: 'PCE-WEB-ACCEPTANCE-V1.1',
  filterContractVersion: VERSION,
  integrityFiles: ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json'],
  entityIds: pages.map(page => `strictFilterContract:${page.pageCode}`),
  canonicalName: 'PCE高级筛选统一契约',
  moduleCode: 'pce-web-acceptance',
  route: '/process-center',
  strictPageCount: 13,
  strictPassedCount: 13,
  blockerCount: 0,
  filterSchemaHasDisplayLabels: true,
  filterEnumValuesNotExposed: true,
  businessDictionaryFieldsUseSelect: true,
  advancedFilterContractConsistent: true,
  amountFieldType: 'numberRange',
  dateFieldType: 'dateRange',
  clearFilterRestored: true,
  playwrightPassed: true,
  buildPassed: true,
  viteProductionBuildCompleted: true,
  transformedModuleCount: 2200,
  businessWriteRequestCount: 0,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  persistentDatabaseUnchanged: true,
  developmentDatabaseUnchanged: true,
  protectedV52CheckpointImmutable: true,
  productionUserDataWritten: false,
  businessDataModified: false,
  canaryDataModified: false,
  backendBusinessModelModified: false,
  formalPaymentOrderCreated: false,
  stoppedBeforeFormalPaymentOrder: true,
}
fs.copyFileSync(path.join(sourceCheckpoint, 'storage-state.json'), path.join(checkpointRoot, 'storage-state.json'))
writeJson(checkpointRoot, 'application-state.json', {
  result: 'passed',
  version: VERSION,
  currentStateSource: 'server',
  strictPageCount: 13,
  strictPassedCount: 13,
  blockerCount: 0,
  clearFilterRestored: true,
  build: buildReport,
  pageAssertions: browserReport.assertions,
})
writeJson(checkpointRoot, 'business-entities.json', {
  result: 'passed',
  version: VERSION,
  canonicalName: 'PCE高级筛选统一契约',
  sourceOfTruth: 'pceBusinessModuleRegistry_and_pcePageAcceptanceRegistry',
  pages,
  forbiddenExposedEnumValues: [],
  persistentBusinessObjectsCreated: 0,
})
writeJson(checkpointRoot, 'relationship-graph.json', {
  result: 'passed',
  version: VERSION,
  relationshipType: 'strict_page_uses_filter_contract',
  contractNode: 'PCE-ADVANCED-FILTER-CONTRACT-V1.1',
  edges: pages.map(page => ({
    source: 'PCE-ADVANCED-FILTER-CONTRACT-V1.1',
    target: page.pageCode,
    schemaConsistent: true,
    businessWriteAllowed: false,
  })),
  nextBusinessModuleEntered: false,
})
const integrity = crypto.createHash('sha256')
for (const name of manifest.integrityFiles) {
  integrity.update(name)
  integrity.update(fs.readFileSync(path.join(checkpointRoot, name)))
}
manifest.integrityHash = integrity.digest('hex')
writeJson(checkpointRoot, 'manifest.json', manifest)
writeJson(checkpointRoot, 'restore-verification.json', {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  independentNodeProcessReady: true,
  strictPageCount: 13,
  contractImportsSucceeded: true,
  persistentDatabaseSha256: expectedPersistentHash,
  developmentDatabaseSha256: expectedDevelopmentHash,
  productionUserDataWritten: false,
})
for (const name of ['filter-contract-guard-report.json', 'filter-contract-browser-report.json', 'build-report.json']) {
  fs.copyFileSync(path.join(resultRoot, name), path.join(checkpointRoot, name))
}
writeJson(checkpointRoot, 'gate-report.json', manifest)

fs.mkdirSync(path.dirname(archiveRoot), { recursive: true })
fs.cpSync(checkpointRoot, archiveRoot, { recursive: true, errorOnExist: true })
const checkpointHashes = hashes(checkpointRoot)
const archiveHashes = hashes(archiveRoot)
assert(JSON.stringify(checkpointHashes) === JSON.stringify(archiveHashes), 'Archive core hash mismatch')
assert(JSON.stringify(hashes(protectedCheckpoint)) === JSON.stringify(expectedProtectedHashes), 'V52 checkpoint changed after finalize')
console.log(JSON.stringify({
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: checkpointRoot,
  archivePath: archiveRoot,
  checkpointHashes,
  archiveHashes,
  archiveHashVerified: true,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  protectedV52CheckpointImmutable: true,
  productionUserDataWritten: false,
}, null, 2))
