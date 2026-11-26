import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { listPdeProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const outputDir = path.join(frontendRoot, 'test-results', 'pde-navigation-governance-v492')
const outputPath = path.join(outputDir, 'pde_navigation_governance_scan_v492.json')
function sha256(filePath) {
  return fs.existsSync(filePath)
    ? crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex').toUpperCase()
    : ''
}

const actualRouterSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const shellSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/PceListPageShell.vue'), 'utf8')
const centerSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/EnterpriseOSPage.vue'), 'utf8')
const definitions = Object.values(pdePageDefinitions)
const nodes = listPdeProcessNodes().map(node => {
  const page = definitions.find(item => item.pageCode === node.pageCode)
  return {
    sequence: node.sequence,
    nodeCode: node.nodeCode,
    nodeName: node.nodeName,
    moduleCode: node.moduleCode,
    pageCode: node.pageCode,
    pageUrl: node.pageUrl,
    pageVersion: node.pageVersion,
    pageDefinitionExists: Boolean(page),
    routeExists: Boolean(node.pageUrl && actualRouterSource.includes(`path: '${node.pageUrl.replace(/^\//, '')}'`)),
    returnModuleCode: page?.governance?.returnModuleCode || '',
  }
})

const checkpointRoots = [
  path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints'),
  'D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow',
]
const protectedCheckpoints = ['pce_scm_supplier_settlement_final_ready', 'pce_pde_version_governance_ready']
const checkpointHashes = protectedCheckpoints.map(checkpointId => {
  const root = checkpointRoots.map(candidate => path.join(candidate, checkpointId)).find(candidate => fs.existsSync(candidate)) || ''
  return {
    checkpointId,
    root,
    manifestHash: root ? sha256(path.join(root, 'manifest.json')) : '',
    applicationStateHash: root ? sha256(path.join(root, 'application-state.json')) : '',
    relationshipGraphHash: root ? sha256(path.join(root, 'relationship-graph.json')) : '',
  }
})

const report = {
  version: 'V1.14.2.8.4.9.2',
  scanType: 'pre-development',
  generatedAt: new Date().toISOString(),
  sourceScopes: [
    'frontend/src/meta/process',
    'frontend/src/meta/pages',
    'frontend/src/router',
    'frontend/src/meta/runtime',
  ],
  pdeNodeCount: nodes.length,
  nodes,
  summary: {
    boundNodeCount: nodes.filter(node => node.pageCode && node.pageUrl && node.pageVersion).length,
    missingPageBindingCount: nodes.filter(node => !node.pageCode || !node.pageUrl || !node.pageVersion).length,
    existingRouteCount: nodes.filter(node => node.routeExists).length,
    pdeReturnContextCount: nodes.filter(node => node.returnModuleCode === 'PDE').length,
    shellUsesReturnModuleCode: shellSource.includes('returnModuleCode'),
    shellUsesBusinessModuleFallback: /returnModuleCode\s*\|\|\s*governedPage\.value\?\.businessModule/.test(shellSource),
    processCenterReadsModuleQuery: centerSource.includes('route.query.module'),
    processCenterSynchronizesModuleQuery: centerSource.includes('selectProcessModule'),
  },
  databaseBefore: {
    path: path.join(repoRoot, 'backend', 'db.sqlite3'),
    sha256: sha256(path.join(repoRoot, 'backend', 'db.sqlite3')),
  },
  checkpointHashes,
  productionUserDataWritten: false,
}

fs.mkdirSync(outputDir, { recursive: true })
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify({ outputPath, ...report.summary }, null, 2))
