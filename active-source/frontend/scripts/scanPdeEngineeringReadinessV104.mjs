import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-engineering-readiness-v104')
const outputPath = path.join(resultRoot, 'pde_engineering_readiness_scan_v104.json')
const checkpointRoot = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints')
const archiveRoot = 'D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow'
const checkpointIds = ['pce_pde_workbench_v103_ready', 'pce_scm_supplier_settlement_final_ready']
const shaFile = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const checkpointHashes = checkpointIds.map(checkpointId => {
  const local = path.join(checkpointRoot, checkpointId)
  const archive = path.join(archiveRoot, checkpointId)
  const root = fs.existsSync(local) ? local : archive
  return {
    checkpointId,
    root,
    manifestHash: shaFile(path.join(root, 'manifest.json')),
    applicationStateHash: shaFile(path.join(root, 'application-state.json')),
    relationshipGraphHash: shaFile(path.join(root, 'relationship-graph.json')),
  }
})
const processState = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const shellSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/PceListPageShell.vue'), 'utf8')
const modelSource = fs.readFileSync(path.join(frontendRoot, '../backend/pde/models.py'), 'utf8')
const report = {
  version: 'V1.14.2.8.4.10.4',
  scanType: 'pre-development',
  generatedAt: new Date().toISOString(),
  pdeProcessVersion: processState?.processVersion,
  pdeNodeCount: processState?.nodes?.length || 0,
  pdePageCount: Object.keys(pdePageDefinitions).length,
  navigationUsesClickableLinks: shellSource.includes('data-pde-navigation-link'),
  readinessModelPresent: modelSource.includes('class ProductEngineeringReadiness'),
  checkpointHashes,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ outputPath, pdePageCount: report.pdePageCount, checkpointCount: checkpointHashes.length }, null, 2))
