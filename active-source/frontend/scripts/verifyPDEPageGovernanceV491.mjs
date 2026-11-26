import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import { pdeFoundationDependency } from '../src/meta/process/businessDependencyRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { evaluatePdePageRules } from '../src/meta/acceptance/rules/pdePageRules.js'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(scriptDir, '..')
const sourceRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-page-governance-v491')
const scanPath = path.join(resultRoot, 'pde_page_governance_scan_v491.json')
const reportPath = path.join(resultRoot, 'pde_page_governance_acceptance_v491.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const checkpointBase = path.join(
  frontendRoot,
  'test-results/purchase-payment-golden-flow/checkpoints',
)
const checkpointId = 'pce_pde_page_governance_v491_ready'
const checkpointDir = path.join(checkpointBase, checkpointId)
const archiveDir = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const databasePath = path.join(sourceRoot, 'backend', 'db.sqlite3')
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
const read = relative => fs.readFileSync(path.join(frontendRoot, relative), 'utf8')
const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const processDefinition = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const databaseHashBefore = sha256(databasePath)
const sources = {
  page: read('src/meta/pages/PdeFoundationPage.vue'),
  router: read('src/router/index.js'),
  shell: read('src/meta/components/PceListPageShell.vue'),
  processCenter: read('src/meta/pages/EnterpriseOSPage.vue'),
}
const rules = evaluatePdePageRules({
  pageDefinitions: pdePageDefinitions,
  process: processDefinition,
  dependency: pdeFoundationDependency,
  sources,
})
const expectedNodes = [
  '产品订单需求',
  '产品需求评审',
  '产品设计管理',
  'BOM管理',
  '工艺路线管理',
  '工程资料发布',
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
processValidation.passed = processValidation.nodeCount === 8
  && processValidation.actualNodes.every((name, index) => name === expectedNodes[index])
const pageValidation = Object.values(pdePageDefinitions).map(page => ({
  pageCode: page.pageCode,
  pageName: page.title,
  url: `/pde/${page.resource}`,
  nodeCode: page.nodeCode,
  template: 'PceListPageShell',
  returnModuleCode: page.governance.returnModuleCode,
  purpose: page.governance.purpose,
  navigation: page.governance.navigation,
  passed: page.governance.businessModule === 'PDE'
    && page.governance.returnModuleCode === 'PDE',
}))
const baselineChecks = Object.entries(scan.checkpointHashes).map(([checkpointIdValue, files]) => {
  const root = path.join(checkpointBase, checkpointIdValue)
  const current = Object.fromEntries(
    Object.keys(files).map(name => [name, sha256(path.join(root, name))]),
  )
  return {
    checkpointId: checkpointIdValue,
    expected: files,
    current,
    unchanged: Object.keys(files).every(name => files[name] === current[name]),
  }
})
let playwright = { exists: false, passed: false, testCount: 0, failed: 0 }
if (fs.existsSync(playwrightPath)) {
  const payload = JSON.parse(fs.readFileSync(playwrightPath, 'utf8'))
  const stats = payload.stats || {}
  playwright = {
    exists: true,
    testCount: Number(stats.expected || 0),
    failed: Number(stats.unexpected || 0),
    passed: Number(stats.expected || 0) >= 5 && Number(stats.unexpected || 0) === 0,
  }
}
const totals = {
  total: rules.length,
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const databaseHashAfter = sha256(databasePath)
const dataProtection = {
  productionUserDataWritten: false,
  databaseHashBefore,
  databaseHashAfter,
  databaseUnchanged: databaseHashBefore === databaseHashAfter,
  scmDataWritten: 0,
  purchaseDataWritten: 0,
  supplierSettlementDataWritten: 0,
  paymentDataWritten: 0,
  bankDataWritten: 0,
  financialDataWritten: 0,
  frozenBaselinesUnchanged: baselineChecks.every(item => item.unchanged),
}
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && processValidation.passed
  && pageValidation.every(page => page.passed)
  && playwright.passed
  && dataProtection.databaseUnchanged
  && dataProtection.frozenBaselinesUnchanged
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-PAGE-GOVERNANCE-ACCEPTANCE-V491',
  version: 'V1.14.2.8.4.9.1',
  generatedAt: new Date().toISOString(),
  result,
  rules,
  totals,
  processValidation,
  pageValidation,
  outputRelationships: {
    chain: ['CRM销售订单', 'PDE产品研发工程', 'BOM', '工艺路线', 'MRP', '采购', '生产'],
    bomReference: 'EMD_MATERIAL_MASTER',
    routingReference: 'EMD_WORK_CENTER',
    output: 'MRP_INPUT_BASIS',
    complexPlmFeatures: [],
  },
  playwright,
  dataProtection,
  baselineChecks,
}
fs.mkdirSync(resultRoot, { recursive: true })
writeJson(reportPath, report)

if (result === 'PASS') {
  if (fs.existsSync(checkpointDir) || fs.existsSync(archiveDir)) {
    throw new Error(`Immutable checkpoint already exists: ${checkpointId}`)
  }
  fs.mkdirSync(checkpointDir, { recursive: true })
  const files = {
    'application-state.json': {
      checkpointId,
      version: 'V1.14.2.8.4.9.1',
      immutable: true,
      result,
      processValidation,
      pages: pageValidation,
      rules: totals,
      playwright,
      dataProtection,
    },
    'relationship-graph.json': {
      module: 'PDE',
      positioning: '订单驱动的产品研发与工程资料管理中心',
      process: expectedNodes,
      dependsOn: [...pdeFoundationDependency.dependsOn],
      chain: report.outputRelationships.chain,
      returnNavigation: { from: '/pde/*', to: '/process-center?module=PDE', selectedModule: 'PDE' },
      protectedBaseline: 'pce_scm_supplier_settlement_final_ready',
    },
    'page-governance-baseline.json': pageValidation,
    'acceptance-report.json': report,
    'development-scan.json': scan,
    'playwright-report.json': JSON.parse(fs.readFileSync(playwrightPath, 'utf8')),
  }
  for (const [name, payload] of Object.entries(files)) writeJson(path.join(checkpointDir, name), payload)
  const integrityHashes = Object.fromEntries(
    Object.keys(files).map(name => [name, sha256(path.join(checkpointDir, name))]),
  )
  const manifest = {
    checkpointId,
    type: 'immutable page governance checkpoint',
    immutable: true,
    version: 'V1.14.2.8.4.9.1',
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
  totals,
  processValidation,
  pageCount: pageValidation.length,
  playwright,
  dataProtection,
  reportPath,
  checkpointId: result === 'PASS' ? checkpointId : null,
}, null, 2)}\n`)
if (result !== 'PASS') process.exitCode = 1
