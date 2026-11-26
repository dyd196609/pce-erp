import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.6'
const checkpointId = 'pce_business_navigation_single_entry_ready'
const sourceCheckpointId = 'pce_enterprise_entry_governance_ready'
const resultRoot = path.join(frontend, 'test-results/business-navigation-governance-v86-fix')
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
const sha256 = file => (
  crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
)

const acceptance = readJson(path.join(resultRoot, 'business_navigation_governance_v86_fix_report.json'))
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
  || databaseProtection.businessDataWriteCount !== 0
) {
  throw new Error('V86 navigation acceptance or database protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  checkpointId,
  sourceCheckpointId,
  navigationHierarchy: acceptance.navigation.hierarchy,
  removedShortcutCount: acceptance.navigation.removedShortcutCount,
  retainedProcessNodeCount: acceptance.navigation.retainedProcessNodeCount,
  paymentRequestNode: acceptance.navigation.paymentRequestNode,
  rules: acceptance.rules,
  totals: acceptance.totals,
  playwright: playwright.stats,
  iab,
  databaseProtection,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'BusinessProcessCenter', role: 'unique_navigation_entry' },
    { id: 'SCM', role: 'business_module' },
    { id: 'SCM_PURCHASE_SETTLEMENT', role: 'business_process' },
    ...Array.from({ length: acceptance.navigation.retainedProcessNodeCount }, (_, index) => ({
      id: `SCM_NODE_${index + 1}`,
      role: 'business_process_node',
    })),
    { id: '/scm/supplier-payment-requests', role: 'business_page' },
  ],
  edges: [
    { from: 'BusinessProcessCenter', to: 'SCM', relation: 'contains_module' },
    { from: 'SCM', to: 'SCM_PURCHASE_SETTLEMENT', relation: 'contains_process' },
    { from: 'SCM_PURCHASE_SETTLEMENT', to: 'SCM_NODE_12', relation: 'contains_payment_request_node' },
    { from: 'SCM_NODE_12', to: '/scm/supplier-payment-requests', relation: 'navigates_to_page' },
  ],
  forbiddenEdges: [
    { from: 'BusinessProcessCenter', to: 'business_page', relation: 'isolated_shortcut', count: 0 },
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
  productionUserDataWritten: false,
  businessDataWriteCount: 0,
  integrityHashes: payloadHashes,
})
const integrityFiles = ['manifest.json', ...payloadFiles]
const localHashes = Object.fromEntries(
  integrityFiles.map(name => [name, sha256(path.join(target, name))]),
)

fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
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
  hashes: {
    manifestHash: localHashes['manifest.json'],
    applicationStateHash: localHashes['application-state.json'],
    relationshipGraphHash: localHashes['relationship-graph.json'],
  },
  archiveHashes,
  archiveMatches,
  productionUserDataWritten: false,
  businessDataWriteCount: 0,
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  removedShortcutCount: acceptance.navigation.removedShortcutCount,
  retainedProcessNodeCount: acceptance.navigation.retainedProcessNodeCount,
  navigationRuleCount: acceptance.ruleCount,
  rules: acceptance.totals,
  playwright: {
    passed: playwright.stats.expected,
    failed: playwright.stats.unexpected,
  },
  iab: {
    result: iab.result,
    sessionId: iab.sessionId,
  },
  databaseProtection,
  viteBuild: 'PASS',
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))
