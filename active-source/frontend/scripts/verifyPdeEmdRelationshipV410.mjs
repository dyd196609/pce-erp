import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { pdeEmdRelationshipRegistry } from '../src/meta/process/pdeEmdRelationshipRegistry.js'
import { evaluatePdeEmdRelationshipRules } from '../src/meta/acceptance/rules/pdeEmdRelationshipRules.js'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-emd-relationship-v410')
const scanPath = path.join(resultRoot, 'pde_emd_relationship_scan_v410.json')
const reportPath = path.join(resultRoot, 'pde_emd_relationship_acceptance_v410.json')
const canaryPath = path.join(resultRoot, 'PDE_EMD_RELATIONSHIP_CANARY_GROUP_V410.json')
const databaseProtectionPath = path.join(resultRoot, 'database-protection-report.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const checkpointRoot = path.join(
  frontendRoot,
  'test-results/purchase-payment-golden-flow/checkpoints',
)
const checkpointId = 'pce_pde_emd_relationship_ready'
const checkpointDir = path.join(checkpointRoot, checkpointId)
const archiveDir = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const apiBase = process.env.PCE_API_BASE_URL || 'http://127.0.0.1:8000'
const shaText = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase()
const shaFile = file => shaText(fs.readFileSync(file))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)

function buildCanary() {
  const products = Array.from({ length: 10 }, (_, index) => ({
    productCode: `PDE-V410-P${String(index + 1).padStart(2, '0')}`,
    emdMaterialCode: `EMD-FG-${String(index + 1).padStart(3, '0')}`,
  }))
  const materialReferences = Array.from({ length: 100 }, (_, index) => ({
    emdMaterialCode: `EMD-MAT-${String(index + 1).padStart(3, '0')}`,
    ownerModule: 'EMD',
  }))
  const boms = Array.from({ length: 20 }, (_, index) => ({
    bomCode: `PDE-V410-BOM-${String(index + 1).padStart(2, '0')}`,
    productCode: products[index % products.length].productCode,
    materialReferences: materialReferences.slice(index * 5, index * 5 + 5),
  }))
  const workCenters = Array.from({ length: 10 }, (_, index) => ({
    emdWorkCenterCode: `EMD-WC-${String(index + 1).padStart(2, '0')}`,
    ownerModule: 'EMD',
  }))
  const routings = products.map((product, index) => ({
    routingCode: `PDE-V410-RT-${String(index + 1).padStart(2, '0')}`,
    productCode: product.productCode,
    emdWorkCenterCode: workCenters[index].emdWorkCenterCode,
  }))
  const engineeringDocuments = Array.from({ length: 30 }, (_, index) => {
    const productIndex = index % products.length
    return {
      documentCode: `PDE-V410-DOC-${String(index + 1).padStart(3, '0')}`,
      documentType: ['工艺文件', '技术资料', '版本记录'][index % 3],
      productCode: products[productIndex].productCode,
      bomCode: boms[productIndex * 2 + (index % 2)].bomCode,
      routingCode: routings[productIndex].routingCode,
    }
  })
  return {
    groupCode: 'PDE_EMD_RELATIONSHIP_CANARY_GROUP_V410',
    productionData: false,
    products,
    boms,
    materialReferences,
    routings,
    workCenters,
    engineeringDocuments,
  }
}

async function apiCheck(resource) {
  try {
    const response = await fetch(`${apiBase}/api/pde/${resource}/`)
    const payload = await response.json()
    const surfaces = ['apiFacts', 'pageFacts', 'diagnosticFacts', 'strictFacts', 'acceptanceFacts']
    const consistent = surfaces.every(name => (
      payload[name]?.factSource === 'server'
      && payload[name]?.recordCount === payload.strictFacts?.recordCount
      && payload[name]?.pageCode === payload.strictFacts?.pageCode
    ))
    return {
      resource,
      httpStatus: response.status,
      recordCount: payload.strictFacts?.recordCount,
      factSource: payload.strictFacts?.factSource,
      passed: response.status === 200 && consistent,
    }
  } catch (error) {
    return { resource, httpStatus: 0, passed: false, error: error.message }
  }
}

fs.mkdirSync(resultRoot, { recursive: true })
const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const databaseProtection = JSON.parse(fs.readFileSync(databaseProtectionPath, 'utf8'))
const canary = buildCanary()
writeJson(canaryPath, canary)
const baselineChecks = Object.entries(scan.checkpointHashes).map(([checkpointIdValue, hashes]) => {
  const root = path.join(checkpointRoot, checkpointIdValue)
  const current = Object.fromEntries(Object.keys(hashes).map(name => [name, shaFile(path.join(root, name))]))
  return {
    checkpointId: checkpointIdValue,
    unchanged: Object.keys(hashes).every(name => hashes[name] === current[name]),
    expected: hashes,
    current,
  }
})
const frozenBaselinesUnchanged = baselineChecks.every(check => check.unchanged)
const pdeModelSource = fs.readFileSync(path.join(sourceRoot, 'backend/pde/models.py'), 'utf8')
const rules = evaluatePdeEmdRelationshipRules({
  relationships: pdeEmdRelationshipRegistry,
  pdeModelSource,
  canary,
  frozenBaselinesUnchanged,
})
const apiChecks = await Promise.all(
  ['product-requirements', 'product-definitions', 'product-boms', 'routings', 'engineering-documents']
    .map(apiCheck),
)
const processDefinition = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const engineeringNode = processDefinition.nodes.find(node => node.nodeCode === 'engineering-data-release')
const canaryValidation = {
  productCount: canary.products.length,
  bomCount: canary.boms.length,
  materialReferenceCount: canary.materialReferences.length,
  routingCount: canary.routings.length,
  workCenterCount: canary.workCenters.length,
  engineeringDocumentCount: canary.engineeringDocuments.length,
  allProductsConnected: canary.products.every(product => (
    canary.boms.some(bom => bom.productCode === product.productCode)
    && canary.routings.some(routing => routing.productCode === product.productCode)
  )),
  allBomMaterialsFromEmd: canary.boms.every(bom => (
    bom.materialReferences.length === 5
    && bom.materialReferences.every(reference => reference.ownerModule === 'EMD')
  )),
  allDocumentsConnected: canary.engineeringDocuments.every(document => (
    canary.products.some(product => product.productCode === document.productCode)
    && canary.boms.some(bom => bom.bomCode === document.bomCode)
    && canary.routings.some(routing => routing.routingCode === document.routingCode)
  )),
}
let playwright = { exists: false, passed: false, testCount: 0, failed: 0 }
if (fs.existsSync(playwrightPath)) {
  const payload = JSON.parse(fs.readFileSync(playwrightPath, 'utf8'))
  playwright = {
    exists: true,
    testCount: Number(payload.stats?.expected || 0),
    failed: Number(payload.stats?.unexpected || 0),
    passed: Number(payload.stats?.expected || 0) >= 4 && Number(payload.stats?.unexpected || 0) === 0,
  }
}
const totals = {
  total: rules.length,
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const relationshipSummary = {
  relationshipCount: pdeEmdRelationshipRegistry.length,
  emdReferenceCount: pdeEmdRelationshipRegistry.filter(item => item.targetModule === 'EMD').length,
  pdeAssociationCount: pdeEmdRelationshipRegistry.filter(item => item.targetModule === 'PDE').length,
  activeCount: pdeEmdRelationshipRegistry.filter(item => item.status === 'active').length,
}
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && apiChecks.every(check => check.passed)
  && Object.values(canaryValidation).slice(6).every(Boolean)
  && engineeringNode?.pageUrl === '/pde/engineering-documents'
  && Object.keys(pdePageDefinitions).length === 5
  && playwright.passed
  && databaseProtection.productionUserDataWritten === false
  && databaseProtection.protectedTablesUnchanged === true
  && frozenBaselinesUnchanged
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-EMD-RELATIONSHIP-ACCEPTANCE-V410',
  version: 'V1.14.2.8.4.10',
  generatedAt: new Date().toISOString(),
  result,
  pdeObjectCount: 5,
  emdObjectCount: scan.emdObjectCount,
  pageCount: Object.keys(pdePageDefinitions).length,
  relationshipSummary,
  relationships: pdeEmdRelationshipRegistry,
  rules,
  totals,
  apiChecks,
  processBinding: {
    nodeCode: engineeringNode?.nodeCode,
    nodeName: engineeringNode?.nodeName,
    pageUrl: engineeringNode?.pageUrl,
  },
  canaryValidation,
  playwright,
  databaseProtection,
  baselineChecks,
  complexPlmFeatures: [],
}
writeJson(reportPath, report)

if (result === 'PASS') {
  if (fs.existsSync(checkpointDir) || fs.existsSync(archiveDir)) {
    throw new Error(`Immutable checkpoint already exists: ${checkpointId}`)
  }
  fs.mkdirSync(checkpointDir, { recursive: true })
  const files = {
    'application-state.json': {
      checkpointId,
      version: 'V1.14.2.8.4.10',
      immutable: true,
      result,
      pdeObjectCount: report.pdeObjectCount,
      emdObjectCount: report.emdObjectCount,
      pageCount: report.pageCount,
      relationshipSummary,
      rules: totals,
      canaryValidation,
      playwright,
      databaseProtection,
    },
    'relationship-graph.json': {
      registryVersion: 'V1.14.2.8.4.10',
      relationships: pdeEmdRelationshipRegistry,
      manufacturingBridge: ['CRM订单', 'PDE产品', 'BOM', 'EMD物料', 'Routing', 'EMD工作中心', 'MRP/SCM/MES'],
      protectedBaseline: 'pce_scm_supplier_settlement_final_ready',
    },
    'relationship-registry.json': pdeEmdRelationshipRegistry,
    'canary-dataset.json': canary,
    'database-protection-report.json': databaseProtection,
    'acceptance-report.json': report,
    'development-scan.json': scan,
    'playwright-report.json': JSON.parse(fs.readFileSync(playwrightPath, 'utf8')),
  }
  for (const [name, payload] of Object.entries(files)) writeJson(path.join(checkpointDir, name), payload)
  const integrityHashes = Object.fromEntries(
    Object.keys(files).map(name => [name, shaFile(path.join(checkpointDir, name))]),
  )
  const manifest = {
    checkpointId,
    type: 'immutable PDE-EMD relationship checkpoint',
    immutable: true,
    version: 'V1.14.2.8.4.10',
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
  result,
  pdeObjectCount: report.pdeObjectCount,
  emdObjectCount: report.emdObjectCount,
  relationshipSummary,
  totals,
  apiChecks,
  canaryValidation,
  playwright,
  databaseProtection: {
    productionUserDataWritten: databaseProtection.productionUserDataWritten,
    protectedTableCount: databaseProtection.protectedTableCount,
    protectedTablesUnchanged: databaseProtection.protectedTablesUnchanged,
  },
  reportPath,
  checkpointId: result === 'PASS' ? checkpointId : null,
}, null, 2)}\n`)
if (result !== 'PASS') process.exitCode = 1
