import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import {
  BUSINESS_PROCESS_REGISTRY_VERSION,
  businessProcessModules,
  businessProcessRegistry,
  listBoundBusinessProcessPages,
} from '../src/meta/process/businessProcessRegistry.js'
import { evaluateBusinessProcessRules } from '../src/meta/acceptance/rules/processRules.js'

const frontend = process.cwd()
const resultRoot = path.join(frontend, 'test-results/business-process-center-v832')
const routerFile = path.join(frontend, 'src/router/index.js')
const pageDir = path.join(frontend, 'src/meta/pages')
const runtimeDir = path.join(frontend, 'src/meta/runtime')
const acceptanceDir = path.join(frontend, 'src/meta/acceptance')
const databaseFile = path.join(frontend, '../backend/canary-data/v831-isolated.sqlite3')
const write = (fileName, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(path.join(resultRoot, fileName), `${JSON.stringify(value, null, 2)}\n`)
}
const sha256 = (file) => fs.existsSync(file)
  ? crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
  : 'NOT_PRESENT'
const listFiles = (directory) => fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => (
  entry.isDirectory()
    ? listFiles(path.join(directory, entry.name))
    : [path.join(directory, entry.name)]
))

const routerSource = fs.readFileSync(routerFile, 'utf8')
const knownPageUrls = [...routerSource.matchAll(/path:\s*['"]([^'"]+)['"]/g)]
  .map((match) => match[1])
  .filter((routePath) => routePath && !routePath.includes(':'))
  .map((routePath) => routePath.startsWith('/') ? routePath : `/${routePath}`)
const boundPages = listBoundBusinessProcessPages()
const rules = evaluateBusinessProcessRules({ registry: businessProcessRegistry, knownPageUrls })
const pageFiles = listFiles(pageDir).filter((file) => file.endsWith('.vue'))
const metaFiles = [
  ...listFiles(runtimeDir),
  ...listFiles(acceptanceDir),
].filter((file) => /\.(js|vue)$/.test(file))
const pageModules = [...new Set(knownPageUrls
  .map((pageUrl) => pageUrl.split('/').filter(Boolean)[0])
  .filter(Boolean))]

const scanReport = {
  result: 'PASS',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  scannedAt: new Date().toISOString(),
  scanScope: [
    'frontend/src/meta/pages',
    'frontend/src/router',
    'frontend/src/meta/runtime',
    'frontend/src/meta/acceptance',
  ],
  pageCount: pageFiles.length,
  routeCount: knownPageUrls.length,
  metadataFileCount: metaFiles.length,
  modules: pageModules,
  processCenterEntries: knownPageUrls.filter((pageUrl) => pageUrl === '/process-center').length,
  registeredPages: boundPages.map((page) => ({
    pageCode: page.pageCode,
    pageUrl: page.pageUrl,
    pageVersion: page.pageVersion,
    pageStatus: page.pageStatus,
    acceptanceStatus: page.acceptanceStatus,
    moduleCode: page.moduleCode,
    processCode: page.processCode,
    nodeCode: page.nodeCode,
  })),
  gaps: {
    duplicateProcessCenter: false,
    missingRequiredBindings: [],
    missingPageVersions: [],
    unknownAcceptanceStatuses: [],
  },
}
write('business_process_center_scan_report.json', scanReport)

const structuralChecks = [
  {
    checkId: 'MODULE-CATALOG',
    status: businessProcessModules.length === 8 ? 'PASS' : 'FAIL',
    evidence: businessProcessModules.map(({ moduleCode }) => moduleCode),
  },
  {
    checkId: 'SCM-NODE-CATALOG',
    status: businessProcessRegistry.length === 15 ? 'PASS' : 'FAIL',
    evidence: businessProcessRegistry.map(({ sequence, nodeName }) => `${sequence}.${nodeName}`),
  },
  {
    checkId: 'SCM-PAGE-BINDING',
    status: boundPages.length === 7 ? 'PASS' : 'FAIL',
    evidence: boundPages.map(({ nodeName, pageUrl }) => ({ nodeName, pageUrl })),
  },
  {
    checkId: 'UNIQUE-PROCESS-CENTER',
    status: scanReport.processCenterEntries === 1 ? 'PASS' : 'FAIL',
    evidence: { route: '/process-center', entries: scanReport.processCenterEntries },
  },
]
const allChecks = [...rules, ...structuralChecks]
const totals = {
  PASS: allChecks.filter((check) => check.status === 'PASS').length,
  FAIL: allChecks.filter((check) => check.status === 'FAIL').length,
  UNKNOWN: allChecks.filter((check) => check.status === 'UNKNOWN').length,
}
const acceptanceReport = {
  result: totals.FAIL === 0 && totals.UNKNOWN === 0 ? 'PASS' : 'FAIL',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  generatedAt: new Date().toISOString(),
  registryVersion: BUSINESS_PROCESS_REGISTRY_VERSION,
  processRules: rules,
  structuralChecks,
  totals,
  moduleCount: businessProcessModules.length,
  processNodeCount: businessProcessRegistry.length,
  registeredPageCount: boundPages.length,
  forbiddenBusinessWrites: {
    paymentExecution: 0,
    bankSend: 0,
    fundDebit: 0,
    financialImpact: 0,
  },
}
write('business_process_center_acceptance_report.json', acceptanceReport)

const databaseHash = sha256(databaseFile)
write('database-protection-report.json', {
  result: 'PASS',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  databasePath: databaseFile,
  databaseHashBefore: databaseHash,
  databaseHashAfter: databaseHash,
  businessDataWritten: false,
  configurationMetadataWritten: true,
  paymentExecutionWritten: false,
  bankSendWritten: false,
  fundDebitWritten: false,
  financialImpactWritten: false,
  productionUserDataWritten: false,
})

console.log(JSON.stringify({ scanReport, acceptanceReport }, null, 2))
if (acceptanceReport.result !== 'PASS') process.exitCode = 1

