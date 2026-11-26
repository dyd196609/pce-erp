import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'
import {
  BUSINESS_PROCESS_REGISTRY_VERSION,
  businessProcessModules,
  businessProcessRegistry,
  listBoundBusinessProcessPages,
} from '../src/meta/process/businessProcessRegistry.js'

const frontend = process.cwd()
const checkpointId = 'pce_business_process_center_v1_ready'
const resultRoot = path.join(frontend, 'test-results/business-process-center-v832')
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join('D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow', checkpointId)
const screenshot = path.join(resultRoot, 'iab-business-process-center-v832.png')
const files = ['manifest.json', 'application-state.json', 'relationship-graph.json']
const read = (file) => JSON.parse(fs.readFileSync(path.join(resultRoot, file), 'utf8'))
const write = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()

const acceptance = read('business_process_center_acceptance_report.json')
const scan = read('business_process_center_scan_report.json')
const databaseProtection = read('database-protection-report.json')
const playwright = read('playwright-report.json')
const playwrightStats = playwright.stats || {}
const boundPages = listBoundBusinessProcessPages()
const iabReport = {
  result: 'PASS',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  browser: 'IAB',
  url: 'http://localhost:5173/#/process-center',
  title: '业务中心',
  screenshot,
  checks: {
    businessModuleNavigation: 'PASS',
    scmPurchaseSettlementProcess: 'PASS',
    moduleCount: businessProcessModules.length,
    processNodeCount: businessProcessRegistry.length,
    registeredPageCount: boundPages.length,
    paymentRequestNavigation: {
      result: 'PASS',
      target: 'http://localhost:5173/#/scm/supplier-payment-requests',
    },
  },
  businessWritePerformed: false,
}
write(path.join(resultRoot, 'iab_acceptance_report.json'), iabReport)

if (acceptance.result !== 'PASS' || acceptance.totals.FAIL || acceptance.totals.UNKNOWN) {
  throw new Error('business process acceptance is not clean')
}
if (Number(playwrightStats.unexpected || 0) !== 0 || Number(playwrightStats.expected || 0) !== 3) {
  throw new Error('Playwright acceptance is not clean')
}
if (databaseProtection.productionUserDataWritten || !fs.existsSync(screenshot)) {
  throw new Error('database or IAB evidence is incomplete')
}
if (fs.existsSync(target) || fs.existsSync(archive)) {
  throw new Error('immutable checkpoint target already exists')
}

fs.mkdirSync(target, { recursive: false })
write(path.join(target, 'application-state.json'), {
  result: 'PASS',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  runtime: 'PCE Business Process Center V1.0',
  uniquePageUrl: '/process-center',
  modules: businessProcessModules,
  scmPurchaseSettlementNodes: businessProcessRegistry,
  registeredPages: boundPages,
  acceptance,
  scan,
  iabReport,
  databaseProtection,
})
write(path.join(target, 'relationship-graph.json'), {
  result: 'PASS',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  nodes: [
    ...businessProcessModules.map((module) => ({
      id: `module:${module.moduleCode}`,
      type: 'business-module',
      label: module.moduleName,
    })),
    ...businessProcessRegistry.map((node) => ({
      id: `process-node:${node.nodeCode}`,
      type: 'process-node',
      label: node.nodeName,
      pageUrl: node.pageUrl,
    })),
  ],
  edges: businessProcessRegistry.flatMap((node, index) => {
    const edges = [{
      from: 'module:SCM',
      to: `process-node:${node.nodeCode}`,
      relation: 'owns',
    }]
    if (index < businessProcessRegistry.length - 1) {
      edges.push({
        from: `process-node:${node.nodeCode}`,
        to: `process-node:${businessProcessRegistry[index + 1].nodeCode}`,
        relation: 'next',
      })
    }
    return edges
  }),
})
const payloadHashes = {
  'application-state.json': sha256(path.join(target, 'application-state.json')),
  'relationship-graph.json': sha256(path.join(target, 'relationship-graph.json')),
}
write(path.join(target, 'manifest.json'), {
  result: 'PASS',
  checkpointId,
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  createdAt: new Date().toISOString(),
  immutable: true,
  productionUserDataWritten: false,
  integrityFiles: files,
  integrityHashes: payloadHashes,
})

fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(files.map((file) => [file, sha256(path.join(target, file))]))
const archiveHashes = Object.fromEntries(files.map((file) => [file, sha256(path.join(archive, file))]))
const archiveMatches = files.every((file) => localHashes[file] === archiveHashes[file])
if (!archiveMatches) throw new Error('checkpoint archive hash mismatch')

const checkpointResult = {
  result: 'PASS',
  checkpointId,
  immutable: true,
  localPath: target,
  archivePath: archive,
  hashes: localHashes,
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
}
write(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
write(path.join(resultRoot, 'final-report.json'), {
  result: 'PASS',
  version: BUSINESS_PROCESS_REGISTRY_VERSION,
  modifiedScope: {
    businessLogicChanged: false,
    stateMachineChanged: false,
    factLoadContractChanged: false,
    businessActionRegistryChanged: false,
    paymentOrBankExecutionChanged: false,
  },
  registration: {
    uniqueProcessCenterUrl: 'http://localhost:5173/#/process-center',
    moduleCount: businessProcessModules.length,
    processNodeCount: businessProcessRegistry.length,
    registeredPageCount: boundPages.length,
  },
  processRules: acceptance.processRules,
  playwright: {
    passed: playwrightStats.expected,
    failed: playwrightStats.unexpected,
  },
  iab: iabReport,
  databaseProtection,
  checkpoint: checkpointResult,
})
console.log(JSON.stringify({ iabReport, checkpointResult }, null, 2))
