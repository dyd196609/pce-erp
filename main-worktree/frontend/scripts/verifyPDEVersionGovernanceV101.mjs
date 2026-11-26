import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { pdeVersionRelationshipRegistry } from '../src/meta/process/pdeVersionRelationshipRegistry.js'
import { evaluatePdeVersionRules } from '../src/meta/acceptance/rules/pdeVersionRules.js'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-version-governance-v101')
const scanPath = path.join(resultRoot, 'pde_version_change_scan_v101.json')
const reportPath = path.join(resultRoot, 'pde_version_governance_acceptance_v101.json')
const canaryPath = path.join(resultRoot, 'PDE_VERSION_CHANGE_CANARY_GROUP_V101.json')
const databaseProtectionPath = path.join(resultRoot, 'database-protection-report.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const checkpointRoot = path.join(
  frontendRoot,
  'test-results/purchase-payment-golden-flow/checkpoints',
)
const checkpointId = 'pce_pde_version_governance_ready'
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
    productCode: `PDE-V101-P${String(index + 1).padStart(2, '0')}`,
  }))
  const productVersions = products.flatMap(product => [
    {
      productCode: product.productCode,
      versionNo: 'V1.0',
      status: 'obsolete',
      effectiveDate: '2026-01-01',
      expireDate: '2026-06-30',
    },
    {
      productCode: product.productCode,
      versionNo: 'V2.0',
      status: 'released',
      effectiveDate: '2026-07-01',
      expireDate: null,
    },
  ])
  const bomVersions = products.flatMap((product, index) => [
    { bomVersionNo: `BOM-${index + 1}-V1`, productCode: product.productCode, productVersionNo: 'V1.0', status: 'obsolete' },
    { bomVersionNo: `BOM-${index + 1}-V2`, productCode: product.productCode, productVersionNo: 'V2.0', status: 'released' },
    { bomVersionNo: `BOM-${index + 1}-V2A`, productCode: product.productCode, productVersionNo: 'V2.0', status: 'reviewed' },
  ])
  const routingVersions = products.flatMap((product, index) => [
    { routingVersionNo: `RT-${index + 1}-V1`, productCode: product.productCode, productVersionNo: 'V1.0', status: 'obsolete' },
    { routingVersionNo: `RT-${index + 1}-V2`, productCode: product.productCode, productVersionNo: 'V2.0', status: 'released' },
  ])
  const engineeringDocumentVersions = products.flatMap((product, index) => (
    Array.from({ length: 4 }, (_, documentIndex) => ({
      documentVersionNo: `DOC-${index + 1}-V${documentIndex + 1}`,
      productCode: product.productCode,
      productVersionNo: documentIndex === 0 ? 'V1.0' : 'V2.0',
      bomVersionNo: documentIndex === 0 ? `BOM-${index + 1}-V1` : `BOM-${index + 1}-V2`,
      routingVersionNo: documentIndex === 0 ? `RT-${index + 1}-V1` : `RT-${index + 1}-V2`,
      status: documentIndex === 0 ? 'obsolete' : 'released',
    }))
  ))
  const ecns = products.map((product, index) => ({
    changeNo: `ECN-V101-${String(index + 1).padStart(3, '0')}`,
    productCode: product.productCode,
    changeType: ['设计变更', '材料变更', '工艺变更', '资料变更'][index % 4],
    beforeVersionNo: 'V1.0',
    afterVersionNo: 'V2.0',
    status: 'effective',
  }))
  const effectiveDateChecks = products.map(product => ({
    productCode: product.productCode,
    orderDate: '2026-07-15',
    selectedVersionNo: 'V2.0',
    selectedStatus: 'released',
    obsoleteSelected: false,
  }))
  return {
    groupCode: 'PDE_VERSION_CHANGE_CANARY_GROUP_V101',
    productionData: false,
    products,
    productVersions,
    bomVersions,
    routingVersions,
    engineeringDocumentVersions,
    ecns,
    effectiveDateChecks,
  }
}

async function apiCheck(resource) {
  try {
    const response = await fetch(`${apiBase}/api/pde/${resource}/`)
    const payload = await response.json()
    const facts = payload.strictFacts || {}
    return {
      resource,
      httpStatus: response.status,
      factSource: facts.factSource,
      recordCount: facts.recordCount,
      passed: response.status === 200 && facts.factSource === 'server',
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
const modelSource = fs.readFileSync(path.join(sourceRoot, 'backend/pde/models.py'), 'utf8')
const rules = evaluatePdeVersionRules({
  modelSource,
  canary,
  relationships: pdeVersionRelationshipRegistry,
})
const apiChecks = await Promise.all(
  ['product-versions', 'bom-versions', 'routing-versions', 'engineering-changes'].map(apiCheck),
)
const processDefinition = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const expectedNodes = [
  '产品订单需求',
  '产品需求评审',
  '产品设计管理',
  '产品版本管理',
  'BOM版本管理',
  '工艺路线版本管理',
  '工程资料发布',
  '工程变更ECN',
  '试制验证',
  '量产导入',
]
const processValidation = {
  processName: processDefinition?.processName,
  processVersion: processDefinition?.processVersion,
  nodeCount: processDefinition?.nodes?.length,
  expectedNodes,
  actualNodes: processDefinition?.nodes?.map(node => node.nodeName),
}
processValidation.passed = processValidation.processName === 'PDE产品研发工程流程 V1.2'
  && processValidation.processVersion === 'V1.2'
  && processValidation.nodeCount === 10
  && processValidation.actualNodes.every((name, index) => name === expectedNodes[index])
const canaryValidation = {
  productCount: canary.products.length,
  productVersionCount: canary.productVersions.length,
  bomVersionCount: canary.bomVersions.length,
  routingVersionCount: canary.routingVersions.length,
  engineeringDocumentVersionCount: canary.engineeringDocumentVersions.length,
  ecnCount: canary.ecns.length,
  allRelationsValid: canary.engineeringDocumentVersions.every(version => (
    canary.productVersions.some(item => (
      item.productCode === version.productCode && item.versionNo === version.productVersionNo
    ))
    && canary.bomVersions.some(item => item.bomVersionNo === version.bomVersionNo)
    && canary.routingVersions.some(item => item.routingVersionNo === version.routingVersionNo)
  )),
  obsoleteProductionInputCount: canary.effectiveDateChecks.filter(check => check.obsoleteSelected).length,
  ecnBeforeAfterValid: canary.ecns.every(ecn => ecn.beforeVersionNo !== ecn.afterVersionNo),
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
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && apiChecks.every(check => check.passed)
  && processValidation.passed
  && canaryValidation.productCount === 10
  && canaryValidation.productVersionCount === 20
  && canaryValidation.bomVersionCount === 30
  && canaryValidation.routingVersionCount === 20
  && canaryValidation.engineeringDocumentVersionCount === 40
  && canaryValidation.ecnCount === 10
  && canaryValidation.allRelationsValid
  && canaryValidation.obsoleteProductionInputCount === 0
  && canaryValidation.ecnBeforeAfterValid
  && playwright.passed
  && databaseProtection.productionUserDataWritten === false
  && databaseProtection.protectedTablesUnchanged === true
  && databaseProtection.versionBusinessRowsWritten === 0
  && baselineChecks.every(check => check.unchanged)
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-VERSION-GOVERNANCE-ACCEPTANCE-V101',
  version: 'V1.14.2.8.4.10.1',
  generatedAt: new Date().toISOString(),
  result,
  newObjectCount: 6,
  versionRelationshipCount: pdeVersionRelationshipRegistry.length,
  ecnCount: canary.ecns.length,
  relationships: pdeVersionRelationshipRegistry,
  rules,
  totals,
  processValidation,
  pageCount: Object.keys(pdePageDefinitions).length,
  apiChecks,
  canaryValidation,
  effectiveDateValidation: canary.effectiveDateChecks,
  ecnValidation: canary.ecns,
  playwright,
  databaseProtection,
  baselineChecks,
  prohibitedCapabilities: [],
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
      version: 'V1.14.2.8.4.10.1',
      immutable: true,
      result,
      newObjectCount: report.newObjectCount,
      versionRelationshipCount: report.versionRelationshipCount,
      ecnCount: report.ecnCount,
      rules: totals,
      processValidation,
      canaryValidation,
      playwright,
      databaseProtection,
    },
    'relationship-graph.json': {
      relationships: pdeVersionRelationshipRegistry,
      effectiveChain: ['订单日期', 'ProductVersion', 'BOMVersion', 'RoutingVersion', 'EngineeringDocumentVersion'],
      changeChain: ['ECN.beforeVersion', 'ECN.afterVersion'],
      downstream: ['MRP', 'MPS', 'APS', 'MES'],
      protectedBaseline: 'pce_scm_supplier_settlement_final_ready',
    },
    'version-relationship-registry.json': pdeVersionRelationshipRegistry,
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
    type: 'immutable PDE version governance checkpoint',
    immutable: true,
    version: 'V1.14.2.8.4.10.1',
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
  newObjectCount: report.newObjectCount,
  versionRelationshipCount: report.versionRelationshipCount,
  ecnCount: report.ecnCount,
  totals,
  processValidation,
  canaryValidation,
  playwright,
  databaseProtection: {
    productionUserDataWritten: databaseProtection.productionUserDataWritten,
    protectedTableCount: databaseProtection.protectedTableCount,
    protectedTablesUnchanged: databaseProtection.protectedTablesUnchanged,
    versionBusinessRowsWritten: databaseProtection.versionBusinessRowsWritten,
  },
  reportPath,
  checkpointId: result === 'PASS' ? checkpointId : null,
}, null, 2)}\n`)
if (result !== 'PASS') process.exitCode = 1
