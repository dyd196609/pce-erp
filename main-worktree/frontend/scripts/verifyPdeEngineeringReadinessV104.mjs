import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { pdePageDefinitions } from '../src/meta/pages/pdePageDefinitions.js'
import { pdeWorkbenchGovernance } from '../src/meta/process/pdeWorkbenchRegistry.js'
import { evaluatePdeEngineeringReadinessRules } from '../src/meta/acceptance/rules/pdeEngineeringReadinessRules.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const resultRoot = path.join(frontendRoot, 'test-results', 'pde-engineering-readiness-v104')
const scanPath = path.join(resultRoot, 'pde_engineering_readiness_scan_v104.json')
const databasePath = path.join(resultRoot, 'database-protection-report.json')
const playwrightPath = path.join(resultRoot, 'playwright-report.json')
const iabPath = path.join(resultRoot, 'iab_acceptance_report.json')
const reportPath = path.join(resultRoot, 'pde_engineering_readiness_acceptance_v104.json')
const checkpointId = 'pce_pde_engineering_readiness_v104_ready'
const checkpointDir = path.join(frontendRoot, 'test-results/purchase-payment-golden-flow/checkpoints', checkpointId)
const archiveDir = path.join('D:/Dev-PCE/CheckpointArchive/purchase-payment-golden-flow', checkpointId)
const apiBase = process.env.PCE_API_BASE_URL || 'http://127.0.0.1:8000'
const shaText = value => crypto.createHash('sha256').update(value).digest('hex').toUpperCase()
const shaFile = file => shaText(fs.readFileSync(file))
const writeJson = (file, value) => fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)

async function checkApi() {
  try {
    const response = await fetch(`${apiBase}/api/pde/engineering-readiness/`)
    const payload = await response.json()
    return {
      url: '/api/pde/engineering-readiness/',
      httpStatus: response.status,
      pageVersion: payload.strictFacts?.pageVersion,
      pageCode: payload.strictFacts?.pageCode,
      factSource: payload.strictFacts?.factSource,
      recordCount: payload.strictFacts?.recordCount,
      productionUserDataWritten: payload.strictFacts?.productionUserDataWritten,
      passed: response.status === 200
        && payload.strictFacts?.pageVersion === 'V1.14.2.8.4.10.4'
        && payload.strictFacts?.pageCode === 'pde-engineering-readiness'
        && payload.strictFacts?.factSource === 'server'
        && payload.strictFacts?.productionUserDataWritten === false,
    }
  } catch (error) {
    return { url: '/api/pde/engineering-readiness/', httpStatus: 0, passed: false, error: error.message }
  }
}

const scan = JSON.parse(fs.readFileSync(scanPath, 'utf8'))
const databaseProtection = JSON.parse(fs.readFileSync(databasePath, 'utf8'))
const playwrightPayload = JSON.parse(fs.readFileSync(playwrightPath, 'utf8'))
const iab = JSON.parse(fs.readFileSync(iabPath, 'utf8'))
const modelSource = fs.readFileSync(path.join(repoRoot, 'backend/pde/models.py'), 'utf8')
const shellSource = fs.readFileSync(path.join(frontendRoot, 'src/meta/components/PceListPageShell.vue'), 'utf8')
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
const rules = evaluatePdeEngineeringReadinessRules({
  modelSource,
  readinessPage: pdePageDefinitions.engineeringReadiness,
  pdePages: Object.values(pdePageDefinitions),
  workbenchGovernance: pdeWorkbenchGovernance,
  shellSource,
  baselineChecks,
})
const totals = {
  total: rules.length,
  PASS: rules.filter(rule => rule.status === 'PASS').length,
  FAIL: rules.filter(rule => rule.status === 'FAIL').length,
  UNKNOWN: rules.filter(rule => rule.status === 'UNKNOWN').length,
}
const api = await checkApi()
const playwright = {
  testCount: Number(playwrightPayload?.stats?.expected || 0),
  failed: Number(playwrightPayload?.stats?.unexpected || 0),
}
playwright.passed = playwright.testCount >= 5 && playwright.failed === 0
const navigation = {
  governedPageCount: Object.keys(pdePageDefinitions).length + 1,
  clickablePositionsPerPage: 3,
  crmOrderUrl: pdeWorkbenchGovernance.navigation.previous.pageUrl,
  pdeProcessUrl: pdeWorkbenchGovernance.navigation.next.pageUrl,
}
const result = totals.FAIL === 0
  && totals.UNKNOWN === 0
  && api.passed
  && playwright.passed
  && iab.result === 'PASS'
  && databaseProtection.productionUserDataWritten === false
  && databaseProtection.protectedTablesUnchanged === true
  && databaseProtection.readinessBusinessRowsWritten === 0
  && baselineChecks.every(check => check.unchanged)
    ? 'PASS'
    : 'FAIL'
const report = {
  reportCode: 'PDE-ENGINEERING-READINESS-ACCEPTANCE-V104',
  version: 'V1.14.2.8.4.10.4',
  generatedAt: new Date().toISOString(),
  result,
  newObject: 'ProductEngineeringReadiness',
  newPage: '/pde/engineering-readiness',
  rules,
  totals,
  navigation,
  api,
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
      newObject: report.newObject,
      newPage: report.newPage,
      rules: totals,
      navigation,
      api,
      productionUserDataWritten: false,
    },
    'relationship-graph.json': {
      chain: ['CRM客户订单', 'PDE工程准备', 'BOM', '工艺路线', '工程资料', '制造输出', 'MRP输入准备'],
      navigation,
      prohibitedEffects: ['PurchaseOrder', 'Payment', 'BankSend', 'FinancialEntry'],
    },
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
  writeJson(path.join(checkpointDir, 'manifest.json'), {
    checkpointId,
    type: 'immutable PDE engineering readiness governance checkpoint',
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
  totals,
  navigation,
  api,
  playwright,
  iab: iab.result,
  databaseProtection: {
    productionUserDataWritten: databaseProtection.productionUserDataWritten,
    protectedTableCount: databaseProtection.protectedTableCount,
    protectedTablesUnchanged: databaseProtection.protectedTablesUnchanged,
    readinessBusinessRowsWritten: databaseProtection.readinessBusinessRowsWritten,
  },
  checkpointId: result === 'PASS' ? checkpointId : null,
  reportPath,
}, null, 2))
if (result !== 'PASS') process.exitCode = 1
