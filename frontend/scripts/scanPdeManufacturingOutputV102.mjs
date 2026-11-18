import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import { pdeEmdRelationshipRegistry } from '../src/meta/process/pdeEmdRelationshipRegistry.js'
import { pdeVersionRelationshipRegistry } from '../src/meta/process/pdeVersionRelationshipRegistry.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-manufacturing-output-v102')
const outputPath = path.join(resultRoot, 'pde_manufacturing_output_scan_v102.json')
const sha = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const checkpointRoot = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints')
const archiveRoot = 'D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow'
const checkpointIds = [
  'pce_scm_supplier_settlement_final_ready',
  'pce_pde_version_governance_ready',
  'pce_pde_navigation_governance_v492_ready',
]
const checkpointHashes = checkpointIds.map(checkpointId => {
  const local = path.join(checkpointRoot, checkpointId)
  const archive = path.join(archiveRoot, checkpointId)
  const root = fs.existsSync(local) ? local : archive
  return {
    checkpointId,
    root,
    manifestHash: sha(path.join(root, 'manifest.json')),
    applicationStateHash: sha(path.join(root, 'application-state.json')),
    relationshipGraphHash: sha(path.join(root, 'relationship-graph.json')),
  }
})
const modelSource = fs.readFileSync(path.join(repoRoot, 'backend/pde/models.py'), 'utf8')
const process = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const databasePath = path.join(repoRoot, 'backend/db.sqlite3')
const report = {
  version: 'V1.14.2.8.4.10.2',
  scanType: 'pre-development',
  generatedAt: new Date().toISOString(),
  currentProcess: {
    processCode: process?.processCode,
    processVersion: process?.processVersion,
    nodeCount: process?.nodes?.length || 0,
  },
  existingPdeEmdRelationshipCount: pdeEmdRelationshipRegistry.length,
  existingPdeVersionRelationshipCount: pdeVersionRelationshipRegistry.length,
  manufacturingOutputObjectsPresent: {
    ProductManufacturingOutput: modelSource.includes('class ProductManufacturingOutput'),
    ManufacturingInputReference: modelSource.includes('class ManufacturingInputReference'),
  },
  databaseBefore: { path: databasePath, sha256: sha(databasePath) },
  checkpointHashes,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ outputPath, ...report.currentProcess, checkpointCount: checkpointHashes.length }, null, 2))
