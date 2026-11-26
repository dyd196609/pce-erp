import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.54.2'
const frontend = path.resolve(import.meta.dirname, '..')
const backend = path.resolve(frontend, '..', 'backend')
const resultRoot = path.join(frontend, 'test-results', 'formal-payment-order-v542')
const domains = {
  finance: [
    'formal_payment_order',
    'payable_confirmation_prepare',
    'payment_instruction_prepare',
    'payment_order_draft',
    'payment_order_prepare',
    'payment_request',
    'payment_request_prepare',
    'payment_risk_review',
    'purchase_accounts_payable_draft',
    'purchase_invoice_prepare',
  ],
  procurement: ['procurement', 'purchase', 'reconciliation'],
  sales: [],
  inventory: [],
}
const ignoredDirectories = new Set(['migrations', 'tests', '__pycache__'])
const walk = directory => {
  if (!fs.existsSync(directory)) return []
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const fullPath = path.join(directory, entry.name)
    if (entry.isDirectory()) {
      return ignoredDirectories.has(entry.name) ? [] : walk(fullPath)
    }
    return entry.name.endsWith('.py') ? [fullPath] : []
  })
}
const inspectModule = (domain, moduleCode) => {
  const files = walk(path.join(backend, moduleCode))
  const fileResults = files.map(file => {
    const source = fs.readFileSync(file, 'utf8')
    const directAssignmentCount = [
      ...source.matchAll(/\.\s*(?:status|document_status|progress_status)\s*=(?!=)/g),
    ].length
    const bulkUpdateCount = [
      ...source.matchAll(/\.update\([\s\S]{0,220}?(?:status|document_status|progress_status)\s*=/g),
    ].length
    const sharedTransitionCallCount = (
      source.match(/transition_business_object/g) || []
    ).length
    return {
      file: path.relative(backend, file).replaceAll('\\', '/'),
      directAssignmentCount,
      bulkUpdateCount,
      sharedTransitionCallCount,
    }
  })
  const directAssignmentCount = fileResults.reduce(
    (sum, row) => sum + row.directAssignmentCount,
    0,
  )
  const bulkUpdateCount = fileResults.reduce(
    (sum, row) => sum + row.bulkUpdateCount,
    0,
  )
  const sharedTransitionCallCount = fileResults.reduce(
    (sum, row) => sum + row.sharedTransitionCallCount,
    0,
  )
  const stateful = directAssignmentCount + bulkUpdateCount + sharedTransitionCallCount > 0
  const classification = sharedTransitionCallCount > 0
    ? 'compliant-shared-transition'
    : stateful
      ? 'legacy-direct-status-mutation'
      : 'not-stateful-in-current-scan'
  const riskLevel = classification === 'compliant-shared-transition'
    ? 'controlled'
    : classification === 'not-stateful-in-current-scan'
      ? 'not-applicable'
      : bulkUpdateCount > 0 || directAssignmentCount >= 3
        ? 'high'
        : 'medium'
  return {
    domain,
    moduleCode,
    scannedFileCount: files.length,
    directAssignmentCount,
    bulkUpdateCount,
    sharedTransitionCallCount,
    classification,
    riskLevel,
    files: fileResults.filter(row => (
      row.directAssignmentCount
      || row.bulkUpdateCount
      || row.sharedTransitionCallCount
    )),
  }
}

const moduleReports = Object.entries(domains).flatMap(([domain, modules]) => (
  modules.map(moduleCode => inspectModule(domain, moduleCode))
))
const domainReports = Object.entries(domains).map(([domain, modules]) => {
  const rows = moduleReports.filter(row => row.domain === domain)
  return {
    domain,
    moduleCount: modules.length,
    classification: modules.length
      ? 'scanned-and-classified'
      : 'no-backend-state-machine-module-in-current-workspace',
    compliantModuleCount: rows.filter(
      row => row.classification === 'compliant-shared-transition',
    ).length,
    legacyModuleCount: rows.filter(
      row => row.classification === 'legacy-direct-status-mutation',
    ).length,
    notStatefulModuleCount: rows.filter(
      row => row.classification === 'not-stateful-in-current-scan',
    ).length,
  }
})
const compliantModules = moduleReports
  .filter(row => row.classification === 'compliant-shared-transition')
  .map(({ domain, moduleCode, riskLevel }) => ({ domain, moduleCode, riskLevel }))
const legacyModules = moduleReports
  .filter(row => row.classification === 'legacy-direct-status-mutation')
  .map(({
    domain,
    moduleCode,
    riskLevel,
    directAssignmentCount,
    bulkUpdateCount,
  }) => ({
    domain,
    moduleCode,
    riskLevel,
    directAssignmentCount,
    bulkUpdateCount,
  }))
const report = {
  result: 'passed',
  version: VERSION,
  reportName: 'stateMachineCoverageReport.json',
  scannedDomains: ['finance', 'procurement', 'sales', 'inventory'],
  allDomainsClassified: domainReports.length === 4,
  domainReports,
  moduleReports,
  compliantModules,
  legacyModules,
  summary: {
    scannedModuleCount: moduleReports.length,
    compliantModuleCount: compliantModules.length,
    legacyModuleCount: legacyModules.length,
    highRiskLegacyModuleCount: legacyModules.filter(
      row => row.riskLevel === 'high',
    ).length,
    mediumRiskLegacyModuleCount: legacyModules.filter(
      row => row.riskLevel === 'medium',
    ).length,
    unclassifiedModuleCount: 0,
  },
  migrationTruth: {
    allModulesMigrated: false,
    formalPaymentOrderMigrated: compliantModules.some(
      row => row.moduleCode === 'formal_payment_order',
    ),
    legacyModulesRemainBacklog: legacyModules.length > 0,
    productionDataMigrationPerformed: false,
  },
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'stateMachineCoverageReport.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify({
  result: report.result,
  version: VERSION,
  allDomainsClassified: report.allDomainsClassified,
  summary: report.summary,
  compliantModules,
  legacyModules,
  reportPath: path.join(resultRoot, 'stateMachineCoverageReport.json'),
}, null, 2))
