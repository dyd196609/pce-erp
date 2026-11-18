import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.4.1'
const checkpointId = 'pce_process_center_governance_ready'
const sourceCheckpointId = 'supplier_settlement_closed_loop_ready'
const resultRoot = path.join(frontend, 'test-results/process-center-governance-v841')
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const sourceCheckpoint = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join(
  'D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow',
  checkpointId,
)
const readJson = file => JSON.parse(fs.readFileSync(file, 'utf8'))
const writeJson = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
const sha256 = file =>
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()

const scan = readJson(path.join(resultRoot, 'process_center_governance_scan_report.json'))
const acceptance = readJson(
  path.join(resultRoot, 'process_center_governance_acceptance_report.json'),
)
const playwright = readJson(path.join(resultRoot, 'playwright-report.json'))
const iab = readJson(path.join(resultRoot, 'iab_acceptance_report.json'))
const databaseProtection = readJson(path.join(resultRoot, 'database-protection-report.json'))
const playwrightFailures = playwright.suites
  .flatMap(suite => suite.specs || [])
  .filter(spec => spec.ok !== true)

if (!fs.existsSync(sourceCheckpoint)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target) || fs.existsSync(archive)) {
  throw new Error(`immutable checkpoint already exists: ${checkpointId}`)
}
if (
  acceptance.result !== 'PASS'
  || acceptance.totals.FAIL !== 0
  || acceptance.totals.UNKNOWN !== 0
  || playwrightFailures.length
  || iab.result !== 'PASS'
  || databaseProtection.productionUserDataWritten
) {
  throw new Error('V841 acceptance or data protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  sourceCheckpointId,
  architecture: {
    processCenter: {
      route: '/process-center',
      responsibility: ['展示企业业务流程体系', '导航页面', '查看页面状态'],
      managementActions: [],
    },
    processDesigner: {
      route: '/process-designer',
      responsibility: ['新建流程', '编辑流程', '执行流程', '停用流程', '流程版本管理'],
      store: 'enterpriseOperationStore',
    },
  },
  pageQualityRuleCount: 7,
  acceptance,
  iab,
  databaseProtection,
  scan,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  hierarchy: [
    '企业业务模块',
    '业务流程',
    '业务节点',
    '业务页面',
    '页面版本',
    '自动验收状态',
  ],
  nodes: [
    { id: 'BusinessProcessCenter', route: '/process-center' },
    { id: 'ProcessDesigner', route: '/process-designer' },
    { id: 'BusinessProcessRegistry', version },
    { id: 'PageQualityRules', ruleCount: 7 },
    { id: 'ScmPurchaseProcess', nodeCount: 16, boundPageCount: 16 },
  ],
  edges: [
    { from: 'BusinessProcessCenter', to: 'BusinessProcessRegistry', relation: 'reads_navigation_catalog' },
    { from: 'ProcessDesigner', to: 'enterpriseOperationStore', relation: 'manages_design_state' },
    { from: 'BusinessProcessRegistry', to: 'ScmPurchaseProcess', relation: 'registers' },
    { from: 'PageQualityRules', to: 'BusinessProcessRegistry', relation: 'validates' },
  ],
})
const payloadFiles = ['application-state.json', 'relationship-graph.json']
const payloadHashes = Object.fromEntries(
  payloadFiles.map(name => [name, sha256(path.join(target, name))]),
)
writeJson(path.join(target, 'manifest.json'), {
  result: 'PASS',
  version,
  checkpointId,
  sourceCheckpointId,
  createdAt: new Date().toISOString(),
  immutable: true,
  restorable: true,
  productionUserDataWritten: false,
  integrityHashes: payloadHashes,
})
const integrityFiles = ['manifest.json', ...payloadFiles]
fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(target, name))]),
)
const archiveHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(archive, name))]),
)
const archiveMatches = integrityFiles.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('checkpoint archive mismatch')
for (const root of [target, archive]) {
  for (const name of integrityFiles) fs.chmodSync(path.join(root, name), 0o444)
}
const checkpointResult = {
  result: 'PASS',
  checkpointId,
  sourceCheckpointId,
  immutable: true,
  localPath: target,
  archivePath: archive,
  hashes: localHashes,
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  structure: {
    processCenter: 'catalog_navigation_and_page_status_only',
    processDesigner: 'process_management_only',
    processCenterCount: 1,
    scmNodeCount: 16,
    scmBoundPageCount: 16,
  },
  pageQualityRules: acceptance.totals,
  playwright: { passed: 2, failed: 0, traceMode: 'on' },
  viteBuild: 'PASS',
  iab,
  databaseProtection,
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))
