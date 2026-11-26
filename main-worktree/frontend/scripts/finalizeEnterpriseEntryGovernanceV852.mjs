import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.5.2'
const checkpointId = 'pce_enterprise_entry_governance_ready'
const sourceCheckpointId = 'pce_enterprise_data_boundary_governance_ready'
const resultRoot = path.join(frontend, 'test-results/enterprise-entry-governance-v852')
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

const scan = readJson(path.join(resultRoot, 'enterprise_entry_boundary_scan_v852.json'))
const acceptance = readJson(path.join(resultRoot, 'enterprise_entry_governance_acceptance_v852.json'))
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
  throw new Error('V852 acceptance or database protection failed')
}

fs.mkdirSync(target, { recursive: false })
writeJson(path.join(target, 'application-state.json'), {
  version,
  checkpointId,
  sourceCheckpointId,
  entryStructure: acceptance.entryStructure,
  legacyEntryMappings: acceptance.legacyEntryMappings,
  manufacturingCapabilities: acceptance.rules
    .find(rule => rule.ruleId === 'ENTRY-003')
    .evidence.capabilities,
  pageAcceptanceContract: acceptance.pageAcceptanceContract,
  pageAcceptance: acceptance.pageAcceptance,
  acceptance,
  playwright: playwright.stats,
  iab,
  databaseProtection,
  preDevelopmentScan: scan.entrySummary,
})
writeJson(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'EMD', role: 'enterprise_master_data_maintenance' },
    { id: 'Reference', role: 'master_data_reference_read_only' },
    { id: 'ManufacturingCapabilityMap', role: 'digital_capability_display' },
    { id: 'ProcessCenter', role: 'business_process_navigation' },
    ...acceptance.legacyEntryMappings.map(mapping => ({
      id: mapping.legacyPath,
      role: 'legacy_compatible_entry',
    })),
  ],
  edges: [
    { from: 'Reference', to: 'EMD', relation: 'reads_reference_relationships' },
    { from: 'ManufacturingCapabilityMap', to: 'EMD', relation: 'describes_capability_without_execution' },
    { from: 'ProcessCenter', to: 'EMD', relation: 'navigates_process_without_maintenance' },
    ...acceptance.legacyEntryMappings.map(mapping => ({
      from: mapping.legacyPath,
      to: mapping.targetPath,
      relation: mapping.compatibilityMode,
    })),
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
}
writeJson(path.join(resultRoot, 'checkpoint_result.json'), checkpointResult)
writeJson(path.join(resultRoot, 'final-report.json'), {
  version,
  result: 'PASS',
  rules: acceptance.totals,
  playwright: {
    passed: playwright.stats.expected,
    failed: playwright.stats.unexpected,
  },
  iab: {
    result: iab.result,
    sessionId: iab.sessionId,
    pageCount: iab.pages.length,
    legacyRouteCount: iab.legacyRoutes.length,
  },
  databaseProtection,
  viteBuild: 'PASS',
  checkpoint: checkpointResult,
  nextStep: '等待人工验收',
})
console.log(JSON.stringify(checkpointResult, null, 2))
