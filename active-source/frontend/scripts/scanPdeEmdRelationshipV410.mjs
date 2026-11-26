import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { listMasterDataDefinitions } from '../src/meta/master-data/masterDataRegistry.js'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-emd-relationship-v410')
const checkpointRoot = path.join(
  frontendRoot,
  'test-results/purchase-payment-golden-flow/checkpoints',
)
const pdeModelsPath = path.join(sourceRoot, 'backend', 'pde', 'models.py')
const emdModelsPath = path.join(sourceRoot, 'backend', 'masterdata', 'models.py')
const pdeModels = fs.readFileSync(pdeModelsPath, 'utf8')
const emdModels = fs.readFileSync(emdModelsPath, 'utf8')
const classNames = source => [...source.matchAll(/^class\s+(\w+)\(models\.Model\):/gm)].map(match => match[1])
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const checkpointIds = [
  'pce_scm_supplier_settlement_final_ready',
  'pce_pde_page_governance_v491_ready',
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
const pdeObjects = classNames(pdeModels)
const emdBackendObjects = classNames(emdModels)
const emdGovernedObjects = listMasterDataDefinitions().map(item => ({
  entityCode: item.entityCode,
  masterDataCode: item.masterDataCode,
  title: item.title,
}))
const existingRelationships = [
  {
    sourceObject: 'ProductBOM',
    targetObject: 'MaterialMaster',
    field: 'emd_material_code',
    present: /class ProductBOM[\s\S]*emd_material_code/.test(pdeModels),
  },
  {
    sourceObject: 'Routing',
    targetObject: 'WorkCenterMaster',
    field: 'emd_work_center_code',
    present: /class Routing[\s\S]*emd_work_center_code/.test(pdeModels),
  },
]
const report = {
  reportCode: 'PDE-EMD-RELATIONSHIP-SCAN-V410',
  version: 'V1.14.2.8.4.10',
  generatedAt: new Date().toISOString(),
  scope: [
    'frontend/src/meta/master-data',
    'frontend/src/meta/process',
    'frontend/src/meta/pages',
    'backend/pde',
    'backend/masterdata',
  ],
  pdeObjectCount: pdeObjects.length,
  pdeObjects,
  emdObjectCount: emdGovernedObjects.length,
  emdGovernedObjects,
  emdBackendModelCount: emdBackendObjects.length,
  emdBackendObjects,
  existingRelationships,
  missingRelationships: [
    'ProductDefinition -> EMD MaterialMaster',
    'EngineeringDocument -> ProductDefinition',
    'EngineeringDocument -> ProductBOM',
    'EngineeringDocument -> Routing',
    'MassProductionIntroduction -> ProductionResource',
  ],
  duplicateDataRisks: [
    {
      risk: 'ProductDefinition尚未声明EMD物料引用',
      status: 'OPEN',
    },
    {
      risk: 'PDE关系尚无集中注册表',
      status: 'OPEN',
    },
    {
      risk: 'PDE不得创建Material模型或分配第二套物料编码',
      status: /class\s+Material\s*\(/.test(pdeModels) ? 'FAIL' : 'CONTROLLED',
    },
  ],
  databaseHash: sha256(path.join(sourceRoot, 'backend', 'db.sqlite3')),
  checkpointHashes,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
const outputPath = path.join(resultRoot, 'pde_emd_relationship_scan_v410.json')
fs.writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`)
process.stdout.write(`${outputPath}\n`)
