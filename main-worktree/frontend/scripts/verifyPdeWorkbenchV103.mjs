import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { getBusinessProcessByCode } from '../src/meta/process/businessProcessRegistry.js'
import {
  pdeWorkbenchEntries,
  pdeWorkbenchGovernance,
  pdeWorkbenchRelationship,
} from '../src/meta/process/pdeWorkbenchRegistry.js'
import { evaluatePdeWorkbenchRules } from '../src/meta/acceptance/rules/pdeWorkbenchRules.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-workbench-v103')
const scanPath = path.join(resultRoot, 'pde_workbench_scan_v103.json')
const databasePath = path.join(resultRoot, 'database-protection-report.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const iabPath = path.join(resultRoot, 'iab_acceptance_report.json')
const screenshotPath = path.join(resultRoot, 'iab-pde-workbench-v103.png')
const reportPath = path.join(resultRoot, 'pde_workbench_acceptance_v103.json')
const checkpointId = 'pce_pde_workbench_v103_ready'
const checkpointDir = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints', checkpointId)
const archiveDir = path.join('D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow', checkpointId)
const shaText = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase()
const shaFile = file => shaText(fs.readFileSync(file))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)

const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const databaseProtection = JSON.parse(fs.readFileSync(databasePath, 'utf8'))
const playwrightPayload = JSON.parse(fs.readFileSync(playwrightPath, 'utf8'))
const iab = JSON.parse(fs.readFileSync(iabPath, 'utf8'))
const routeSource = fs.readFileSync(path.join(frontendRoot, 'src/router/index.js'), 'utf8')
const pageSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/PdeWorkbenchPage.vue'), 'utf8')
const processCenterSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/pages/EnterpriseOSPage.vue'), 'utf8')
const rules = evaluatePdeWorkbenchRules({
  entries: pdeWorkbenchEntries,
  relationship: pdeWorkbenchRelationship,
  governance: pdeWorkbenchGovernance,
  routeSource,
  pageSource,
  processCenterSource,
})
const totals = {
  total: rules.length,
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const baselineChecks = scan.checkpointHashes.map(expected => {
  const current = {
    manifestHash: shaFile(path.join(expected.root, 'manifest.json')),
    applicationStateHash: shaFile(path.join(expected.root, 'application-state.json')),
    relationshipGraphHash: shaFile(path.join(expected.root, 'relationship-graph.json')),
  }
  return {
    checkpointId: expected.checkpointId,
    unchanged: Object.keys(current).every(key => current[key] === expected[key]),
    expected,
    current,
  }
})
const pdeProcess = getBusinessProcessByCode('PDE_PRODUCT_ENGINEERING')
const processValidation = {
  processVersion: pdeProcess?.processVersion,
  nodeCount: pdeProcess?.nodes?.length || 0,
  firstNodeName: pdeProcess?.nodes?.[0]?.nodeName,
  workbenchPrimaryEntryOnly: processCenterSource.includes('data-acceptance-id="pde-workbench-primary-entry"')
    && processCenterSource.includes('data-entry-mode="workbench-context-only"'),
}
processValidation.passed = processValidation.processVersion === 'V1.3'
  && processValidation.nodeCount === 12
  && processValidation.firstNodeName === '客户订单需求输入'
  && processValidation.workbenchPrimaryEntryOnly
const playwright = {
  testCount: Number(playwrightPayload?.stats?.expected || 0),
  failed: Number(playwrightPayload?.stats?.unexpected || 0),
}
playwright.passed = playwright.testCount >= 5 && playwright.failed === 0
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && processValidation.passed
  && playwright.passed
  && iab.result === 'PASS'
  && fs.existsSync(screenshotPath)
  && databaseProtection.productionUserDataWritten === false
  && databaseProtection.protectedTablesUnchanged === true
  && databaseProtection.schemaChanges === 0
  && baselineChecks.every(check => check.unchanged)
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-WORKBENCH-ACCEPTANCE-V103',
  version: 'V1.14.2.8.4.10.3',
  generatedAt: new Date().toISOString(),
  result,
  workbenchUrl: '/pde/workbench',
  processCenterUrl: '/process-center?module=PDE',
  existingPdePagesPreserved: true,
  workbenchEntryCount: pdeWorkbenchEntries.length,
  rules,
  totals,
  processValidation,
  relationship: pdeWorkbenchRelationship,
  playwright,
  iab,
  iabScreenshot: screenshotPath,
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
      workbenchEntryCount: report.workbenchEntryCount,
      rules: totals,
      processValidation,
      productionUserDataWritten: false,
    },
    'relationship-graph.json': {
      chain: pdeWorkbenchRelationship.chain,
      bomMaterialOwner: 'EMD',
      routingWorkCenterOwner: 'EMD',
      purchaseOrderGeneration: false,
    },
    'workbench-registry.json': { entries: pdeWorkbenchEntries, governance: pdeWorkbenchGovernance },
    'development-scan.json': scan,
    'acceptance-report.json': report,
    'database-protection-report.json': databaseProtection,
    'playwright-report.json': playwrightPayload,
    'iab-acceptance-report.json': iab,
  }
  for (const [name, payload] of Object.entries(files)) writeJson(path.join(checkpointDir, name), payload)
  fs.copyFileSync(screenshotPath, path.join(checkpointDir, path.basename(screenshotPath)))
  const checkpointFiles = [...Object.keys(files), path.basename(screenshotPath)]
  const integrityHashes = Object.fromEntries(
    checkpointFiles.map(name => [name, shaFile(path.join(checkpointDir, name))]),
  )
  writeJson(path.join(checkpointDir, 'manifest.json'), {
    checkpointId,
    type: 'immutable PDE product engineering workbench checkpoint',
    immutable: true,
    version: report.version,
    result,
    createdAt: new Date().toISOString(),
    integrityHashes,
    manifestHashAlgorithm: 'SHA-256',
    applicationStateHash: integrityHashes['application-state.json'],
    relationshipGraphHash: integrityHashes['relationship-graph.json'],
  })
  fs.mkdirSync(path.dirname(archiveDir), { recursive: true })
  fs.cpSync(checkpointDir, archiveDir, { recursive: true, errorOnExist: true })
}

console.log(JSON.stringify({
  result,
  workbenchEntryCount: report.workbenchEntryCount,
  totals,
  processValidation,
  playwright,
  iab: iab.result,
  databaseProtection: {
    productionUserDataWritten: databaseProtection.productionUserDataWritten,
    protectedTableCount: databaseProtection.protectedTableCount,
    protectedTablesUnchanged: databaseProtection.protectedTablesUnchanged,
  },
  checkpointId: result === 'PASS' ? checkpointId : null,
  reportPath,
}, null, 2))
if (result !== 'PASS') process.exitCode = 1
