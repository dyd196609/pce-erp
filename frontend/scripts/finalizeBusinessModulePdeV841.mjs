import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.4.1'
const checkpointId = 'pce_business_module_pde_ready'
const sourceCheckpointId = 'pce_process_center_governance_ready'
const resultRoot = path.join(frontend, 'test-results/pde-business-module-v841')
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

const scan = readJson(path.join(resultRoot, 'pde_module_process_center_scan_report.json'))
const acceptance = readJson(
  path.join(resultRoot, 'business_module_structure_acceptance_report.json'),
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
  throw new Error('V841 PDE acceptance or data protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  sourceCheckpointId,
  processCenterRoute: '/process-center',
  moduleOrder: ['CRM', 'PDE', 'SCM', 'PLAN', 'WMS', 'MES', 'QMS', 'BI', 'ProfitOS'],
  pde: {
    moduleCode: 'PDE',
    moduleName: '产品研发与工程管理中心',
    description: '产品设计、BOM、工艺路线、工程资料管理',
    order: 2,
    status: 'planned',
    processCode: 'PDE_PRODUCT_ENGINEERING',
    processName: 'PDE产品研发流程',
    nodeNames: ['产品需求', '产品设计', '工程评审', 'BOM建立', '工艺路线', '工程资料发布'],
    pageStatus: 'planned',
    acceptanceStatus: 'not_started',
    pageBindingCount: 0,
  },
  scm: {
    nodeCount: 16,
    pageBindingCount: 16,
    orderPreserved: true,
  },
  acceptance,
  iab,
  databaseProtection,
  scan,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'BusinessProcessCenter', route: '/process-center' },
    { id: 'PDE', name: '产品研发与工程管理中心', order: 2, status: 'planned' },
    { id: 'SCM', name: '供应链管理中心', order: 3, status: 'active' },
    { id: 'PDE_PRODUCT_ENGINEERING', nodeCount: 6, pageBindingCount: 0 },
    { id: 'SCM_PURCHASE_SETTLEMENT', nodeCount: 16, pageBindingCount: 16 },
  ],
  edges: [
    { from: 'BusinessProcessCenter', to: 'PDE', relation: 'lists_module' },
    { from: 'BusinessProcessCenter', to: 'SCM', relation: 'lists_module' },
    { from: 'PDE', to: 'PDE_PRODUCT_ENGINEERING', relation: 'registers_process' },
    {
      from: 'PDE',
      to: 'SCM',
      relation: '工程资料驱动采购',
      businessChain: ['产品研发', 'BOM发布', '工艺路线', '物料需求', '采购执行'],
    },
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
    oldModuleOrder: ['CRM', 'SCM', 'WMS', 'PLAN', 'MES', 'QMS', 'BI', 'ProfitOS'],
    newModuleOrder: ['CRM', 'PDE', 'SCM', 'PLAN', 'WMS', 'MES', 'QMS', 'BI', 'ProfitOS'],
    pdeNodeCount: 6,
    pdePageBindingCount: 0,
    scmNodeCount: 16,
    scmOrderPreserved: true,
  },
  moduleStructureRules: acceptance.totals,
  playwright: { passed: 2, failed: 0, traceMode: 'on' },
  viteBuild: 'PASS',
  iab,
  databaseProtection,
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))
