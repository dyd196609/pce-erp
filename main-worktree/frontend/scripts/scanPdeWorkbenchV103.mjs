import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-workbench-v103')
const outputPath = path.join(resultRoot, 'pde_workbench_scan_v103.json')
const checkpointRoot = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints')
const archiveRoot = 'D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow'
const checkpointIds = ['pce_pde_mfg_output_ready', 'pce_scm_supplier_settlement_final_ready']
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
const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/pdePageDefinitions.js'), 'utf8')
const report = {
  version: 'V1.14.2.8.4.10.3',
  scanType: 'pre-development',
  generatedAt: new Date().toISOString(),
  process: {
    processCode: processState?.processCode,
    processVersion: processState?.processVersion,
    nodeCount: processState?.nodes?.length || 0,
    firstNodeName: processState?.nodes?.[0]?.nodeName || '',
  },
  existingPdePageCount: (pageSource.match(/pageCode:/g) || []).length,
  workbenchRoutePresent: routerSource.includes("path: 'pde/workbench'"),
  checkpointHashes,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ outputPath, ...report.process, checkpointCount: checkpointHashes.length }, null, 2))
