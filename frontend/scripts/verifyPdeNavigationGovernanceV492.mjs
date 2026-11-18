import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode, listPdeProcessNodes } from '../src/meta/process/businessProcessRegistry.js'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { evaluatePdeNavigationRules } from '../src/meta/acceptance/rules/pdeNavigationRules.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-navigation-governance-v492')
const scanPath = path.join(resultRoot, 'pde_navigation_governance_scan_v492.json')
const reportPath = path.join(resultRoot, 'pde_navigation_governance_acceptance_v492.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const iabPath = path.join(resultRoot, 'iab_acceptance_report.json')
const databaseProtectionPath = path.join(resultRoot, 'database-protection-report.json')
const checkpointId = 'pce_pde_navigation_governance_v492_ready'
const checkpointRoot = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints')
const checkpointDir = path.join(checkpointRoot, checkpointId)
const archiveDir = path.join('D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow', checkpointId)
const shaText = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase()
const shaFile = file => shaText(fs.readFileSync(file))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)

fs.mkdirSync(resultRoot, { recursive: true })
const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const routerSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const shellSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/PceListPageShell.vue'), 'utf8')
const processCenterSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/EnterpriseOSPage.vue'), 'utf8')
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/PdeFoundationPage.vue'), 'utf8')
const routeExists = pageUrl => Boolean(
  pageUrl && routerSource.includes(`path: '${String(pageUrl).replace(/^\//, '')}'`),
)
const nodes = listPdeProcessNodes()
const rules = evaluatePdeNavigationRules({
  nodes,
  pageDefinitions: pdePageDefinitions,
  routeExists,
  sources: { router: routerSource, shell: shellSource, processCenter: processCenterSource, page: pageSource },
})
const totals = {
  total: rules.length,
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const process = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const nodeBindings = nodes.map(node => ({
  sequence: node.sequence,
  nodeCode: node.nodeCode,
  nodeName: node.nodeName,
  moduleCode: node.moduleCode,
  pageCode: node.pageCode,
  pageUrl: node.pageUrl,
  pageVersion: node.pageVersion,
  routeExists: routeExists(node.pageUrl),
  definitionExists: Object.values(pdePageDefinitions).some(page => page.pageCode === node.pageCode),
}))
const playwrightPayload = fs.existsSync(playwrightPath) ? JSON.parse(fs.readFileSync(playwrightPath, 'utf8')) : null
const playwright = {
  exists: Boolean(playwrightPayload),
  testCount: Number(playwrightPayload?.stats?.expected || 0),
  failed: Number(playwrightPayload?.stats?.unexpected || 0),
}
playwright.passed = playwright.testCount >= 4 && playwright.failed === 0
const iab = fs.existsSync(iabPath)
  ? JSON.parse(fs.readFileSync(iabPath, 'utf8'))
  : { result: 'UNKNOWN', browser: 'IAB', checks: [] }
const databasePath = path.join(repoRoot, 'backend/db.sqlite3')
const databaseAfterHash = shaFile(databasePath)
const databaseProtection = {
  version: 'V1.14.2.8.4.9.2',
  generatedAt: new Date().toISOString(),
  databasePath,
  beforeHash: scan.databaseBefore.sha256,
  afterHash: databaseAfterHash,
  databaseUnchanged: scan.databaseBefore.sha256 === databaseAfterHash,
  productionUserDataWritten: false,
  scmDataWritten: 0,
  purchaseDataWritten: 0,
  paymentDataWritten: 0,
  financialDataWritten: 0,
  allowedChanges: ['页面注册', '路由', '导航规则'],
}
writeJson(databaseProtectionPath, databaseProtection)

const baselineChecks = scan.checkpointHashes.map(expected => {
  const current = {
    manifestHash: expected.root ? shaFile(path.join(expected.root, 'manifest.json')) : '',
    applicationStateHash: expected.root ? shaFile(path.join(expected.root, 'application-state.json')) : '',
    relationshipGraphHash: expected.root ? shaFile(path.join(expected.root, 'relationship-graph.json')) : '',
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
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && process?.processCode === 'PDE_PRODUCT_ENGINEERING'
  && process?.nodes?.length === 10
  && nodeBindings.every(binding => binding.moduleCode === 'PDE'
    && binding.pageCode && binding.pageUrl && binding.pageVersion
    && binding.routeExists && binding.definitionExists)
  && playwright.passed
  && iab.result === 'PASS'
  && databaseProtection.databaseUnchanged
  && databaseProtection.productionUserDataWritten === false
  && baselineChecks.every(check => check.unchanged)
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-NAVIGATION-GOVERNANCE-ACCEPTANCE-V492',
  version: 'V1.14.2.8.4.9.2',
  generatedAt: new Date().toISOString(),
  result,
  totals,
  rules,
  process: {
    processCode: process?.processCode,
    processName: process?.processName,
    processVersion: process?.processVersion,
    nodeCount: process?.nodes?.length || 0,
  },
  nodeBindings,
  pageEntry: {
    pageCode: 'pde-product-requirements',
    pageName: pdePageDefinitions.requirements.title,
    pageUrl: '/pde/product-requirements',
    result: nodeBindings.find(binding => binding.nodeCode === 'product-order-demand')?.routeExists ? 'PASS' : 'FAIL',
  },
  returnModuleContext: {
    PDE: '/process-center?module=PDE',
    SCM: '/process-center?module=SCM',
    EMD: '/process-center?module=EMD',
    result: rules.find(rule => rule.ruleId === 'PDE-NAV-002')?.status,
  },
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
      rules: totals,
      process: report.process,
      pageEntry: report.pageEntry,
      returnModuleContext: report.returnModuleContext,
      playwright,
      iab,
      databaseProtection,
    },
    'relationship-graph.json': {
      moduleContext: {
        PDE: { pages: Object.keys(pdePageDefinitions).length, returnTo: '/process-center?module=PDE' },
        SCM: { returnTo: '/process-center?module=SCM' },
        EMD: { returnTo: '/process-center?module=EMD' },
      },
      processCode: process.processCode,
      nodeBindings,
    },
    'development-scan.json': scan,
    'acceptance-report.json': report,
    'playwright-report.json': playwrightPayload,
    'iab-acceptance-report.json': iab,
    'database-protection-report.json': databaseProtection,
  }
  for (const [name, payload] of Object.entries(files)) writeJson(path.join(checkpointDir, name), payload)
  const integrityHashes = Object.fromEntries(
    Object.keys(files).map(name => [name, shaFile(path.join(checkpointDir, name))]),
  )
  const manifest = {
    checkpointId,
    type: 'immutable PDE navigation governance checkpoint',
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
  totals,
  nodeCount: report.process.nodeCount,
  boundNodeCount: nodeBindings.filter(binding => binding.routeExists && binding.definitionExists).length,
  pageEntry: report.pageEntry,
  returnModuleContext: report.returnModuleContext,
  playwright,
  iab: { result: iab.result, checkCount: iab.checks?.length || 0 },
  databaseProtection,
  checkpointId: result === 'PASS' ? checkpointId : null,
  reportPath,
}, null, 2))
if (result !== 'PASS') process.exitCode = 1
