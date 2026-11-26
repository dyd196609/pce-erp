import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { pdeManufacturingOutputRegistry, manufacturingInputReferences } from '../src/meta/process/pdeManufacturingOutputRegistry.js'
import { evaluatePdeManufacturingOutputRules } from '../src/meta/acceptance/rules/pdeManufacturingOutputRules.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-manufacturing-output-v102')
const scanPath = path.join(resultRoot, 'pde_manufacturing_output_scan_v102.json')
const databaseProtectionPath = path.join(resultRoot, 'database-protection-report.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const iabPath = path.join(resultRoot, 'iab_acceptance_report.json')
const canaryPath = path.join(resultRoot, 'PDE_MFG_OUTPUT_CANARY_GROUP_V102.json')
const reportPath = path.join(resultRoot, 'pde_manufacturing_output_acceptance_report.json')
const checkpointId = 'pce_pde_mfg_output_ready'
const checkpointRoot = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints')
const checkpointDir = path.join(checkpointRoot, checkpointId)
const archiveDir = path.join('D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow', checkpointId)
const apiBase = process.env.PCE_API_BASE_URL || 'http://127.0.0.1:8000'
const shaText = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase()
const shaFile = file => shaText(fs.readFileSync(file))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)

function buildCanary() {
  const products = Array.from({ length: 10 }, (_, index) => ({
    productId: `PDE-MFG-P${String(index + 1).padStart(2, '0')}`,
  }))
  const productVersions = products.flatMap(product => [
    { versionId: `${product.productId}-V1`, productId: product.productId, status: 'obsolete' },
    { versionId: `${product.productId}-V2`, productId: product.productId, status: 'released' },
  ])
  const materials = Array.from({ length: 100 }, (_, index) => ({
    materialCode: `EMD-MAT-${String(index + 1).padStart(3, '0')}`,
    ownerModule: 'EMD',
    unit: '件',
  }))
  const boms = products.flatMap((product, productIndex) => [
    { bomId: `${product.productId}-BOM-V1`, productId: product.productId, productVersionId: `${product.productId}-V1`, status: 'obsolete', materialCodes: materials.slice(productIndex * 10, productIndex * 10 + 10).map(item => item.materialCode) },
    { bomId: `${product.productId}-BOM-V2`, productId: product.productId, productVersionId: `${product.productId}-V2`, status: 'released', materialCodes: materials.slice(productIndex * 10, productIndex * 10 + 10).map(item => item.materialCode) },
    { bomId: `${product.productId}-BOM-V2A`, productId: product.productId, productVersionId: `${product.productId}-V2`, status: 'reviewed', materialCodes: materials.slice(productIndex * 10, productIndex * 10 + 10).map(item => item.materialCode) },
  ])
  const routings = products.flatMap(product => [
    { routingId: `${product.productId}-RT-V1`, productId: product.productId, productVersionId: `${product.productId}-V1`, status: 'obsolete', workCenterSource: 'EMD' },
    { routingId: `${product.productId}-RT-V2`, productId: product.productId, productVersionId: `${product.productId}-V2`, status: 'released', workCenterSource: 'EMD' },
  ])
  const engineeringDocuments = products.flatMap(product => Array.from({ length: 4 }, (_, index) => ({
    documentId: `${product.productId}-DOC-${index + 1}`,
    productId: product.productId,
    productVersionId: `${product.productId}-V2`,
    status: 'released',
  })))
  const manufacturingOutputs = products.map(product => ({
    outputId: `${product.productId}-OUTPUT`,
    productId: product.productId,
    productVersionId: `${product.productId}-V2`,
    bomId: `${product.productId}-BOM-V2`,
    routingId: `${product.productId}-RT-V2`,
    engineeringStatus: 'ready',
    releaseStatus: 'released_to_manufacturing',
    obsoleteVersionSelected: false,
    targetInputs: ['MRP', 'SCM'],
  }))
  return {
    groupCode: 'PDE_MFG_OUTPUT_CANARY_GROUP_V102',
    productionData: false,
    products,
    productVersions,
    boms,
    materials,
    routings,
    engineeringDocuments,
    manufacturingOutputs,
  }
}

async function apiCheck() {
  try {
    const response = await fetch(`${apiBase}/api/pde/manufacturing-outputs/`)
    const payload = await response.json()
    return {
      url: '/api/pde/manufacturing-outputs/',
      httpStatus: response.status,
      factSource: payload.strictFacts?.factSource,
      pageCode: payload.strictFacts?.pageCode,
      passed: response.status === 200
        && payload.strictFacts?.factSource === 'server'
        && payload.strictFacts?.pageCode === 'pde-manufacturing-outputs',
    }
  } catch (error) {
    return { url: '/api/pde/manufacturing-outputs/', httpStatus: 0, passed: false, error: error.message }
  }
}

fs.mkdirSync(resultRoot, { recursive: true })
const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const databaseProtection = JSON.parse(fs.readFileSync(databaseProtectionPath, 'utf8'))
const canary = buildCanary()
writeJson(canaryPath, canary)
const baselineChecks = scan.checkpointHashes.map(expected => {
  const current = {
    manifestHash: shaFile(path.join(expected.root, 'manifest.json')),
    applicationStateHash: shaFile(path.join(expected.root, 'application-state.json')),
    relationshipGraphHash: shaFile(path.join(expected.root, 'relationship-graph.json')),
  }
  return {
    checkpointId: expected.checkpointId,
    unchanged: expected.manifestHash === current.manifestHash
      && expected.applicationStateHash === current.applicationStateHash
      && expected.relationshipGraphHash === current.relationshipGraphHash,
    expected,
    current,
  }
})
const scmBaseline = baselineChecks.find(check => check.checkpointId === 'pce_scm_supplier_settlement_final_ready')
const modelSource = fs.readFileSync(path.join(repoRoot, 'backend/pde/models.py'), 'utf8')
const rules = evaluatePdeManufacturingOutputRules({
  canary,
  relationships: pdeManufacturingOutputRegistry,
  modelSource,
  scmBaseline,
})
const totals = {
  total: rules.length,
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const pdeProcess = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const processValidation = {
  processCode: pdeProcess?.processCode,
  processName: pdeProcess?.processName,
  processVersion: pdeProcess?.processVersion,
  nodeCount: pdeProcess?.nodes?.length || 0,
  manufacturingOutputNode: pdeProcess?.nodes?.find(node => node.nodeCode === 'manufacturing-output-confirmation'),
  mrpInputNode: pdeProcess?.nodes?.find(node => node.nodeCode === 'mrp-input-preparation'),
}
processValidation.passed = processValidation.processVersion === 'V1.3'
  && processValidation.nodeCount === 12
  && processValidation.manufacturingOutputNode?.pageUrl === '/pde/manufacturing-outputs'
  && processValidation.mrpInputNode?.pageUrl === '/pde/manufacturing-outputs'
const page = pdePageDefinitions.manufacturingOutputs
const pageValidation = {
  pageCode: page?.pageCode,
  pageName: page?.title,
  shell: page?.governance?.frameworkVersion,
  returnModuleCode: page?.governance?.returnModuleCode,
  relationshipSectionTitle: page?.relationshipSectionTitle,
  passed: page?.pageCode === 'pde-manufacturing-outputs'
    && page?.title === 'PDE制造输出确认'
    && page?.governance?.returnModuleCode === 'PDE'
    && page?.relationshipSectionTitle === '制造输入关系',
}
const api = await apiCheck()
const playwrightPayload = fs.existsSync(playwrightPath) ? JSON.parse(fs.readFileSync(playwrightPath, 'utf8')) : null
const playwright = {
  exists: Boolean(playwrightPayload),
  testCount: Number(playwrightPayload?.stats?.expected || 0),
  failed: Number(playwrightPayload?.stats?.unexpected || 0),
}
playwright.passed = playwright.testCount >= 4 && playwright.failed === 0
const iab = fs.existsSync(iabPath)
  ? JSON.parse(fs.readFileSync(iabPath, 'utf8'))
  : { result: 'UNKNOWN', checks: [] }
const canaryValidation = {
  productCount: canary.products.length,
  productVersionCount: canary.productVersions.length,
  bomCount: canary.boms.length,
  materialCount: canary.materials.length,
  routingCount: canary.routings.length,
  engineeringDocumentCount: canary.engineeringDocuments.length,
  manufacturingOutputCount: canary.manufacturingOutputs.length,
  allRelationsValid: canary.manufacturingOutputs.every(output => (
    canary.products.some(product => product.productId === output.productId)
      && canary.productVersions.some(version => version.versionId === output.productVersionId)
      && canary.boms.some(bom => bom.bomId === output.bomId)
      && canary.routings.some(routing => routing.routingId === output.routingId)
      && output.targetInputs.includes('MRP')
  )),
}
const exactCanaryCounts = canaryValidation.productCount === 10
  && canaryValidation.productVersionCount === 20
  && canaryValidation.bomCount === 30
  && canaryValidation.materialCount === 100
  && canaryValidation.routingCount === 20
  && canaryValidation.engineeringDocumentCount === 40
  && canaryValidation.manufacturingOutputCount === 10
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && processValidation.passed
  && pageValidation.passed
  && api.passed
  && playwright.passed
  && iab.result === 'PASS'
  && exactCanaryCounts
  && canaryValidation.allRelationsValid
  && databaseProtection.productionUserDataWritten === false
  && databaseProtection.protectedTablesUnchanged === true
  && databaseProtection.manufacturingOutputBusinessRowsWritten === 0
  && baselineChecks.every(check => check.unchanged)
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-MANUFACTURING-OUTPUT-ACCEPTANCE-V102',
  version: 'V1.14.2.8.4.10.2',
  generatedAt: new Date().toISOString(),
  result,
  outputObjectCount: 2,
  emdReferenceCount: pdeManufacturingOutputRegistry.filter(item => item.targetModule === 'EMD').length,
  mrpRelationshipCount: pdeManufacturingOutputRegistry.filter(item => item.targetModule === 'MRP').length,
  scmRelationshipCount: pdeManufacturingOutputRegistry.filter(item => item.targetModule === 'SCM').length,
  rules,
  totals,
  processValidation,
  pageValidation,
  api,
  relationships: pdeManufacturingOutputRegistry,
  manufacturingInputReferences,
  canaryValidation,
  playwright,
  iab,
  databaseProtection,
  baselineChecks,
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
      immutable: true,
      version: report.version,
      result,
      outputObjectCount: report.outputObjectCount,
      rules: totals,
      processValidation,
      pageValidation,
      canaryValidation,
      playwright,
      iab,
      databaseProtection,
    },
    'relationship-graph.json': {
      chain: ['PDE产品', 'ProductVersion', 'BOMVersion', 'EMD物料', 'RoutingVersion', 'EMD工作中心', 'ProductManufacturingOutput', 'MRP/SCM输入'],
      relationships: pdeManufacturingOutputRegistry,
      manufacturingInputReferences,
      prohibitedOutputs: ['PurchaseRequest', 'PurchaseOrder', 'Payment', 'FinancialEntry'],
    },
    'manufacturing-output-registry.json': pdeManufacturingOutputRegistry,
    'canary-dataset.json': canary,
    'development-scan.json': scan,
    'acceptance-report.json': report,
    'database-protection-report.json': databaseProtection,
    'playwright-report.json': playwrightPayload,
    'iab-acceptance-report.json': iab,
  }
  for (const [name, payload] of Object.entries(files)) writeJson(path.join(checkpointDir, name), payload)
  const integrityHashes = Object.fromEntries(
    Object.keys(files).map(name => [name, shaFile(path.join(checkpointDir, name))]),
  )
  const manifest = {
    checkpointId,
    type: 'immutable PDE manufacturing output governance checkpoint',
    immutable: true,
    version: report.version,
    result,
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

console.log(JSON.stringify({
  result,
  outputObjectCount: report.outputObjectCount,
  emdReferenceCount: report.emdReferenceCount,
  mrpRelationshipCount: report.mrpRelationshipCount,
  scmRelationshipCount: report.scmRelationshipCount,
  totals,
  processValidation,
  pageValidation,
  api,
  canaryValidation,
  playwright,
  iab: { result: iab.result, checkCount: iab.checks?.length || 0 },
  databaseProtection: {
    productionUserDataWritten: databaseProtection.productionUserDataWritten,
    protectedTableCount: databaseProtection.protectedTableCount,
    protectedTablesUnchanged: databaseProtection.protectedTablesUnchanged,
    manufacturingOutputBusinessRowsWritten: databaseProtection.manufacturingOutputBusinessRowsWritten,
  },
  checkpointId: result === 'PASS' ? checkpointId : null,
  reportPath,
}, null, 2))
if (result !== 'PASS') process.exitCode = 1
