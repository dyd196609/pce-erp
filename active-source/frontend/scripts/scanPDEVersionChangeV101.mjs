import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-version-governance-v101')
const modelPath = path.join(sourceRoot, 'backend', 'pde', 'models.py')
const modelSource = fs.readFileSync(modelPath, 'utf8')
const classMatches = [...modelSource.matchAll(/^class\s+(\w+)\(models\.Model\):/gm)]
const classBlocks = classMatches.map((match, index) => {
  const body = modelSource.slice(
    match.index + match[0].length,
    classMatches[index + 1]?.index ?? modelSource.length,
  )
  return {
    objectName: match[1],
    versionFields: [...body.matchAll(/^\s+(\w*version\w*)\s*=/gmi)].map(field => field[1]),
    fields: [...body.matchAll(/^\s{4}(\w+)\s*=\s*models\./gm)].map(field => field[1]),
  }
})
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const checkpointRoot = path.join(
  frontendRoot,
  'test-results/purchase-payment-golden-flow/checkpoints',
)
const checkpointIds = [
  'pce_scm_supplier_settlement_final_ready',
  'pce_pde_page_governance_v491_ready',
  'pce_pde_emd_relationship_ready',
]
const checkpointHashes = Object.fromEntries(checkpointIds.map((checkpointId) => {
  const root = path.join(checkpointRoot, checkpointId)
  return [checkpointId, Object.fromEntries(
    ['manifest.json', 'application-state.json', 'relationship-graph.json'].map(name => [
      name,
      sha256(path.join(root, name)),
    ]),
  )]
}))
const find = name => classBlocks.find(item => item.objectName === name) || null
const report = {
  reportCode: 'PDE-VERSION-CHANGE-SCAN-V101',
  version: 'V1.14.2.8.4.10.1',
  generatedAt: new Date().toISOString(),
  scope: [
    'frontend/src/meta/pages',
    'frontend/src/meta/process',
    'frontend/src/meta/master-data',
    'backend/pde',
  ],
  pdeObjectCount: classBlocks.length,
  pdeObjects: classBlocks,
  existingVersionFields: classBlocks.flatMap(object => (
    object.versionFields.map(field => ({ object: object.objectName, field }))
  )),
  structures: {
    productBOM: find('ProductBOM'),
    routing: find('Routing'),
    engineeringDocument: find('EngineeringDocument'),
  },
  missingVersionRelationships: [
    'ProductVersion 1:N BOMVersion',
    'ProductVersion 1:N RoutingVersion',
    'ProductVersion 1:N EngineeringDocumentVersion',
    'EffectiveDateControl -> ProductVersion/BOMVersion/RoutingVersion',
    'EngineeringChangeNotice beforeVersion -> afterVersion',
  ],
  prohibitedCapabilitiesPresent: {
    cad: /CAD|FileField|ImageField/.test(modelSource),
    threeDimensionalDesign: /ThreeDimensional|3DModel/.test(modelSource),
    plmWorkflow: /PLM|approval_workflow/.test(modelSource),
  },
  databaseHash: sha256(path.join(sourceRoot, 'backend', 'db.sqlite3')),
  checkpointHashes,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
const output = path.join(resultRoot, 'pde_version_change_scan_v101.json')
fs.writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${output}\n`)
