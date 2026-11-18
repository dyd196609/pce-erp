import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const outputDir = path.join(frontendRoot, 'test-results', 'pde-governance-v90')
const checkpointRoot = path.join(
  frontendRoot,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  'pce_scm_supplier_settlement_final_ready',
)

const scanRoots = [
  'frontend/src/meta/process',
  'frontend/src/meta/pages',
  'frontend/src/meta/master-data',
  'frontend/src/meta/acceptance',
  'backend',
]

function listFiles(root) {
  if (!fs.existsSync(root)) return []
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const absolute = path.join(root, entry.name)
    if (entry.isDirectory()) {
      if (['node_modules', 'venv', '__pycache__', '.pytest_cache'].includes(entry.name)) return []
      return listFiles(absolute)
    }
    return [absolute]
  })
}

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex').toUpperCase()
}

function read(relativePath) {
  return fs.readFileSync(path.join(sourceRoot, relativePath), 'utf8')
}

const processSource = read('frontend/src/meta/process/businessProcessRegistry.js')
const dependencySource = read('frontend/src/meta/process/businessDependencyRegistry.js')
const routerSource = read('frontend/src/router/index.js')
const allFiles = scanRoots.flatMap(root => listFiles(path.join(sourceRoot, root)))
const textFiles = allFiles.filter(file => /\.(js|mjs|vue|py|json)$/i.test(file))
const pageFiles = textFiles.filter(file => file.includes(`${path.sep}meta${path.sep}pages${path.sep}`))
const pdeFiles = textFiles.filter((file) => {
  const relative = path.relative(sourceRoot, file)
  return /pde|product.?requirement|product.?definition|product.?bom/i.test(relative)
    || /PDE_PRODUCT_ENGINEERING/.test(fs.readFileSync(file, 'utf8'))
})
const pdeRouteMatches = [...routerSource.matchAll(/path:\s*['"]([^'"]*\/pde\/[^'"]*)['"]/g)]
const pdeNodeBlock = processSource.match(/const pdeNodeDefinitions = \[([\s\S]*?)\n\]/)?.[1] ?? ''
const pdeNodeCount = [...pdeNodeBlock.matchAll(/\[['"]/g)].length

const checkpointFiles = fs.existsSync(checkpointRoot)
  ? listFiles(checkpointRoot)
      .sort()
      .map(file => ({
        path: path.relative(checkpointRoot, file).replaceAll('\\', '/'),
        sha256: sha256(file),
      }))
  : []

const report = {
  reportCode: 'PDE-DEVELOPMENT-SCAN-V90',
  version: 'V1.14.2.8.4.9',
  generatedAt: new Date().toISOString(),
  scanRoots,
  summary: {
    scannedFileCount: textFiles.length,
    metaPageFileCount: pageFiles.length,
    pdeRelatedFileCount: pdeFiles.length,
    pdeRegistered: /moduleCode:\s*['"]PDE['"]/.test(processSource),
    pdeStatus: /moduleCode:\s*['"]PDE['"][\s\S]{0,240}?status:\s*['"]planned['"]/.test(processSource)
      ? 'planned'
      : 'unknown',
    pdeProcessNodeCount: pdeNodeCount,
    pdeRouteCount: pdeRouteMatches.length,
    pdeBackendAppPresent: fs.existsSync(path.join(sourceRoot, 'backend', 'pde')),
    scmFinalCheckpointPresent: fs.existsSync(checkpointRoot),
  },
  pdeExistingRegistration: {
    processCode: /PDE_PRODUCT_ENGINEERING/.test(processSource)
      ? 'PDE_PRODUCT_ENGINEERING'
      : null,
    nodeCount: pdeNodeCount,
    routes: pdeRouteMatches.map(match => match[1]),
    files: pdeFiles.map(file => path.relative(sourceRoot, file).replaceAll('\\', '/')).sort(),
  },
  masterDataRelationships: {
    emdMaterialMasterPresent: /material-data|EMD_MATERIAL_MASTER/.test(
      `${processSource}\n${dependencySource}`,
    ),
    emdOrganizationPresent: /organization-data|EMD_ORGANIZATION/.test(
      `${processSource}\n${dependencySource}`,
    ),
    pdeExplicitEmdDependencyPresent:
      /moduleCode:\s*['"]PDE['"][\s\S]{0,800}?EMD_MATERIAL_MASTER/.test(dependencySource),
  },
  scmDependency: {
    checkpoint: 'pce_scm_supplier_settlement_final_ready',
    declared: /baselineCheckpoint:\s*['"]pce_scm_supplier_settlement_final_ready['"]/.test(
      dependencySource,
    ),
    downstreamPdeProtected:
      /moduleCode:\s*['"]PDE['"][^\n]*mayModifyProcessNodes:\s*false/.test(dependencySource),
    frozenFiles: checkpointFiles,
  },
  dataProtection: {
    productionUserDataWritten: false,
    scanIsReadOnly: true,
  },
}

fs.mkdirSync(outputDir, { recursive: true })
const outputPath = path.join(outputDir, 'pde_development_scan_v90.json')
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${outputPath}\n`)
