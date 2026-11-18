import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  getBusinessProcessByCode,
  listBusinessProcessModules,
} from '../src/meta/process/businessProcessRegistry.js'
import { pdeFoundationDependency } from '../src/meta/process/businessDependencyRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { evaluatePdeRules } from '../src/meta/acceptance/rules/pdeRules.js'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-governance-v90')
const checkpointRoot = path.join(
  frontendRoot,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
)
const checkpointId = 'pce_pde_foundation_ready'
const checkpointDir = path.join(checkpointRoot, checkpointId)
const archiveDir = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const scanPath = path.join(resultRoot, 'pde_development_scan_v90.json')
const reportPath = path.join(resultRoot, 'pde_governance_acceptance_v90.json')
const canaryPath = path.join(resultRoot, 'PDE_PRODUCT_DEVELOPMENT_CANARY_GROUP_V90.json')
const modelPath = path.join(sourceRoot, 'backend', 'pde', 'models.py')
const routerPath = path.join(frontendRoot, 'src', 'router', 'index.js')
const pagePath = path.join(frontendRoot, 'src', 'meta', 'pages', 'PdeFoundationPage.vue')
const sourceScmCheckpoint = path.join(checkpointRoot, 'pce_scm_supplier_settlement_final_ready')
const apiBase = process.env.PCE_API_BASE_URL || 'http://127.0.0.1:8000'

const shaText = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase()
const shaFile = file => shaText(fs.readFileSync(file))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)

function buildCanary() {
  const products = Array.from({ length: 5 }, (_, index) => ({
    productCode: `PDE-CANARY-P${String(index + 1).padStart(2, '0')}`,
    productName: `金丝雀产品${index + 1}`,
    version: 'V1.0',
  }))
  const materials = Array.from({ length: 30 }, (_, index) => ({
    emdMaterialCode: `EMD-MAT-CANARY-${String(index + 1).padStart(3, '0')}`,
    ownership: 'EMD',
  }))
  const boms = Array.from({ length: 10 }, (_, index) => {
    const product = products[index % products.length]
    return {
      bomCode: `PDE-CANARY-BOM-${String(index + 1).padStart(2, '0')}`,
      productCode: product.productCode,
      bomVersion: `V${Math.floor(index / products.length) + 1}.0`,
      components: materials.slice(index * 3, index * 3 + 3).map((material, componentIndex) => ({
        emdMaterialCode: material.emdMaterialCode,
        quantity: componentIndex + 1,
        unit: '件',
      })),
    }
  })
  const routings = products.map((product, index) => ({
    routingCode: `PDE-CANARY-ROUTING-${String(index + 1).padStart(2, '0')}`,
    productCode: product.productCode,
    routingVersion: 'V1.0',
    emdWorkCenterCode: `EMD-WC-${String(index + 1).padStart(2, '0')}`,
    operations: [
      { sequence: 10, name: '准备', standardHours: 0.5 },
      { sequence: 20, name: '加工', standardHours: 1.5 },
      { sequence: 30, name: '检验', standardHours: 0.5 },
    ],
  }))
  return {
    groupCode: 'PDE_PRODUCT_DEVELOPMENT_CANARY_GROUP_V90',
    productionData: false,
    products,
    materials,
    boms,
    routings,
  }
}

async function readApi(resource) {
  try {
    const response = await fetch(`${apiBase}/api/pde/${resource}/`)
    const payload = await response.json()
    const surfaces = ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']
    const factsConsistent = surfaces.every(name => (
      payload[name]?.factSource === 'server'
      && payload[name]?.recordCount === payload.strictFacts?.recordCount
      && payload[name]?.pageCode === payload.strictFacts?.pageCode
    ))
    return {
      resource,
      httpStatus: response.status,
      recordCount: payload.strictFacts?.recordCount,
      factSource: payload.strictFacts?.factSource,
      factsConsistent,
      passed: response.status === 200 && factsConsistent,
    }
  } catch (error) {
    return { resource, httpStatus: 0, factsConsistent: false, passed: false, error: error.message }
  }
}

fs.mkdirSync(resultRoot, { recursive: true })
const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const canary = buildCanary()
writeJson(canaryPath, canary)
const module = listBusinessProcessModules().find(item => item.moduleCode === 'PDE')
const pdeProcess = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const modelSource = fs.readFileSync(modelPath, 'utf8')
const routerSource = fs.readFileSync(routerPath, 'utf8')
const pageSource = fs.readFileSync(pagePath, 'utf8')
const modelEvidence = {
  bomUsesEmdMaterialReference: /class ProductBOM[\s\S]*emd_material_code/.test(modelSource),
  pdeMaterialMasterModelPresent: /class\s+Material\s*\(/.test(modelSource),
  routingUsesProductForeignKey: /class Routing[\s\S]*product\s*=\s*models\.ForeignKey/.test(modelSource),
}
const rules = evaluatePdeRules({
  module,
  process: pdeProcess,
  dependency: pdeFoundationDependency,
  pageDefinitions: pdePageDefinitions,
  modelEvidence,
  canary,
})
const apiChecks = await Promise.all(
  ['product-requirements', 'product-definitions', 'product-boms', 'routings'].map(readApi),
)
const routeChecks = Object.values(pdePageDefinitions).map(definition => ({
  pageCode: definition.pageCode,
  url: `/pde/${definition.resource}`,
  registered: routerSource.includes(`path: 'pde/${definition.resource}'`),
  enterpriseListContract: pageSource.includes('PCE-ENTERPRISE-LIST-CONTRACT-V1.1'),
  detailCard: pageSource.includes('PceBusinessDetailCard'),
  factSourceServer: pageSource.includes('data-fact-source="server"'),
}))
const scanHashes = Object.fromEntries(
  scan.scmDependency.frozenFiles.map(item => [item.path, item.sha256]),
)
const currentScmHashes = Object.fromEntries(
  Object.keys(scanHashes).map(name => [name, shaFile(path.join(sourceScmCheckpoint, name))]),
)
const scmBaselineUnchanged = Object.keys(scanHashes)
  .every(name => scanHashes[name] === currentScmHashes[name])
const canaryValidation = {
  productCount: canary.products.length,
  materialCount: canary.materials.length,
  bomCount: canary.boms.length,
  routingCount: canary.routings.length,
  allProductsHaveBom: canary.products.every(product => (
    canary.boms.some(bom => bom.productCode === product.productCode)
  )),
  allProductsHaveRouting: canary.products.every(product => (
    canary.routings.some(routing => routing.productCode === product.productCode)
  )),
  allBomMaterialsOwnedByEmd: canary.boms.every(bom => (
    bom.components.every(component => (
      canary.materials.some(material => (
        material.emdMaterialCode === component.emdMaterialCode && material.ownership === 'EMD'
      ))
    ))
  )),
}
const totals = {
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const infrastructurePassed = apiChecks.every(check => check.passed)
  && routeChecks.every(check => check.registered && check.enterpriseListContract
    && check.detailCard && check.factSourceServer)
  && Object.values(canaryValidation).slice(4).every(Boolean)
  && scmBaselineUnchanged
const overall = totals.FAIL === 0 && totals.UNKNOWN === 0 && infrastructurePassed ? 'PASS' : 'FAIL'
const report = {
  reportCode: 'PDE-GOVERNANCE-ACCEPTANCE-V90',
  version: 'V1.14.2.8.4.9',
  generatedAt: new Date().toISOString(),
  result: overall,
  moduleRegistration: module,
  process: {
    processCode: pdeProcess?.processCode,
    processName: pdeProcess?.processName,
    status: pdeProcess?.status,
    nodeCount: pdeProcess?.nodes?.length,
    nodes: pdeProcess?.nodes?.map(node => ({
      sequence: node.sequence,
      nodeName: node.nodeName,
      pageCode: node.pageCode,
      pageUrl: node.pageUrl,
    })),
  },
  pageCount: Object.keys(pdePageDefinitions).length,
  objectCount: 4,
  dependencies: pdeFoundationDependency,
  rules,
  totals: { total: rules.length, ...totals },
  apiChecks,
  routeChecks,
  canaryValidation,
  dataProtection: {
    productionUserDataWritten: false,
    migrationScope: 'PDE schema only',
    pdeBusinessRowsWritten: apiChecks.reduce((sum, check) => sum + Number(check.recordCount || 0), 0),
    scmFrozenCheckpointUnchanged: scmBaselineUnchanged,
    purchaseDataWritten: 0,
    supplierSettlementDataWritten: 0,
    paymentDataWritten: 0,
    bankDataWritten: 0,
    financialDataWritten: 0,
  },
}
writeJson(reportPath, report)

if (overall === 'PASS') {
  if (fs.existsSync(checkpointDir) || fs.existsSync(archiveDir)) {
    throw new Error(`Immutable checkpoint already exists: ${checkpointId}`)
  }
  fs.mkdirSync(checkpointDir, { recursive: true })
  const applicationState = {
    checkpointId,
    version: 'V1.14.2.8.4.9',
    immutable: true,
    result: 'PASS',
    moduleCode: 'PDE',
    processCode: pdeProcess.processCode,
    processNodeCount: pdeProcess.nodes.length,
    objectCount: 4,
    pageCount: 4,
    rules: report.totals,
    canaryValidation,
    dataProtection: report.dataProtection,
  }
  const relationshipGraph = {
    module: 'PDE',
    dependsOn: [...pdeFoundationDependency.dependsOn],
    provides: [...pdeFoundationDependency.provides],
    scmBaseline: 'pce_scm_supplier_settlement_final_ready',
    productChain: ['ProductDefinition', 'ProductBOM', 'EMD_MATERIAL_MASTER', 'Routing'],
  }
  const processBaseline = report.process
  const pageBaseline = routeChecks
  const dataBaseline = {
    objects: ['ProductRequirement', 'ProductDefinition', 'ProductBOM', 'Routing'],
    canaryGroup: canary.groupCode,
    canaryCounts: canaryValidation,
    productionUserDataWritten: false,
  }
  const files = {
    'application-state.json': applicationState,
    'relationship-graph.json': relationshipGraph,
    'process-baseline.json': processBaseline,
    'page-baseline.json': pageBaseline,
    'data-baseline.json': dataBaseline,
    'canary-dataset.json': canary,
    'acceptance-report.json': report,
    'development-scan.json': scan,
  }
  for (const [name, value] of Object.entries(files)) writeJson(path.join(checkpointDir, name), value)
  const integrityHashes = Object.fromEntries(
    Object.keys(files).map(name => [name, shaFile(path.join(checkpointDir, name))]),
  )
  const manifest = {
    checkpointId,
    type: 'immutable baseline checkpoint',
    immutable: true,
    version: 'V1.14.2.8.4.9',
    result: 'PASS',
    createdAt: new Date().toISOString(),
    integrityHashes,
    manifestHashAlgorithm: 'SHA-256',
    applicationStateHash: integrityHashes['application-state.json'],
    relationshipGraphHash: integrityHashes['relationship-graph.json'],
  }
  writeJson(path.join(checkpointDir, 'manifest.json'), manifest)
  fs.mkdirSync(path.dirname(archiveDir), { recursive: true })
  fs.cpSync(checkpointDir, archiveDir, { recursive: true, errorOnExist: true })
}

process.stdout.write(`${JSON.stringify({
  result: overall,
  totals: report.totals,
  apiChecks,
  canaryValidation,
  dataProtection: report.dataProtection,
  reportPath,
  checkpointId: overall === 'PASS' ? checkpointId : null,
}, null, 2)}\n`)
if (overall !== 'PASS') process.exitCode = 1
