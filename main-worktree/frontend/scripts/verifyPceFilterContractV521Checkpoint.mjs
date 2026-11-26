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
const checkpointRoot = path.join(frontend, 'test-results', 'purchase-payment-golden-flow', 'checkpoints', CHECKPOINT)
const archiveRoot = path.join(project, 'CheckpointArchive', 'purchase-payment-golden-flow', CHECKPOINT)
const persistentDatabase = path.join(workspace, 'backend', 'canary-data', 'purchase-flow-demo.sqlite3')
const developmentDatabase = path.join(workspace, 'backend', 'db.sqlite3')
const coreNames = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const hashes = root => Object.fromEntries(coreNames.map(name => [name, digest(path.join(root, name))]))
const read = (root, name) => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'))
const before = hashes(checkpointRoot)
const manifest = read(checkpointRoot, 'manifest.json')
const entities = read(checkpointRoot, 'business-entities.json')
const graph = read(checkpointRoot, 'relationship-graph.json')
if (manifest.version !== VERSION || manifest.result !== 'passed' || manifest.strictPassedCount !== 13) throw new Error('Checkpoint manifest failed')
if (entities.pages.length !== 13 || graph.edges.length !== 13) throw new Error('Checkpoint page evidence incomplete')
if (financeProcessPageRegistry.length !== 13) throw new Error('Strict page registry count changed')
for (const page of financeProcessPageRegistry) {
  const schema = findPceBusinessModuleById(page.pageStepId)?.advancedFilterSchema || []
  if (!schema.length || !schema.every(field => field.field && field.label && field.type && field.displayMap && field.optionsProvider)) {
    throw new Error(`${page.pageStepId}: filter schema restore failed`)
  }
}
const archiveHashes = hashes(archiveRoot)
const after = hashes(checkpointRoot)
if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error('Checkpoint core changed during restore')
if (JSON.stringify(after) !== JSON.stringify(archiveHashes)) throw new Error('Archive core hash mismatch')
const report = {
  result: 'passed',
  version: VERSION,
  checkpointId: CHECKPOINT,
  checkpointPath: checkpointRoot,
  archivePath: archiveRoot,
  checkpointHashesBefore: before,
  checkpointHashesAfter: after,
  archiveHashes,
  immutable: true,
  strictPageCount: 13,
  strictPassedCount: 13,
  persistentDatabaseSha256: digest(persistentDatabase),
  developmentDatabaseSha256: digest(developmentDatabase),
  productionUserDataWritten: false,
}
fs.writeFileSync(path.join(frontend, 'test-results', 'pce-filter-contract-v521', 'checkpoint-restore-report.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
