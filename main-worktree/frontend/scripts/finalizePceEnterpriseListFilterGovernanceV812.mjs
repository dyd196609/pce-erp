import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.1.2'
const checkpointId = 'pce_enterprise_list_filter_governance_v11_ready'
const sourceCheckpointId = 'supplier_settlement_page_governance_ready'
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join('D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow', checkpointId)
const resultRoot = path.join(frontend, 'test-results/pce-enterprise-list-filter-governance-v812')
const acceptance = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-acceptance-report.json')))
const filterAcceptance = JSON.parse(fs.readFileSync(path.join(resultRoot, 'pce_list_filter_acceptance_report.json')))
const databaseProtection = JSON.parse(fs.readFileSync(path.join(resultRoot, 'database-protection-report.json')))
const iab = JSON.parse(fs.readFileSync(path.join(resultRoot, 'iab_acceptance_report.json')))
const files = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const write = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target) || fs.existsSync(archive)) throw new Error('immutable target already exists')
if (acceptance.result !== 'PASS' || acceptance.totals.FAIL || acceptance.totals.UNKNOWN) throw new Error('page acceptance failed')
if (filterAcceptance.result !== 'PASS' || databaseProtection.businessDataModified
  || databaseProtection.productionUserDataWritten || iab.result !== 'PASS') throw new Error('acceptance safety evidence failed')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
write(path.join(target, 'application-state.json'), {
  version,
  sourceCheckpointId,
  runtime: 'PCE Enterprise List Advanced Filter Governance V1.1',
  contracts: ['PCE-ENTERPRISE-LIST-CONTRACT-V1.1', 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0'],
  acceptance,
  filterAcceptance,
  iab,
  databaseProtection,
})
write(path.join(target, 'business-entities.json'), {
  version,
  businessDataModified: false,
  governedPages: ['supplier-reconciliation', 'supplier-performance', 'buyer-performance'],
  filterTypes: ['text', 'select', 'date', 'daterange', 'number', 'numberRange', 'boolean'],
  forbiddenWrites: { payment: 0, bankSend: 0, financialImpact: 0 },
})
write(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1' },
    { id: 'PceEnterpriseAdvancedFilter' },
    { id: 'filterSchema' },
    { id: 'page-acceptance-report' },
  ],
  edges: [
    { from: 'filterSchema', to: 'PceEnterpriseAdvancedFilter', relation: 'drives_control_type' },
    { from: 'PceEnterpriseAdvancedFilter', to: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', relation: 'implements' },
    { from: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1', to: 'page-acceptance-report', relation: 'verified_by' },
  ],
})
const payloadHashes = Object.fromEntries(files.slice(1).map(name => [name, sha256(path.join(target, name))]))
write(path.join(target, 'manifest.json'), {
  result: 'PASS', version, checkpointId, sourceCheckpointId, createdAt: new Date().toISOString(),
  immutable: true, restorable: true, productionUserDataWritten: false, businessDataModified: false,
  integrityFiles: files, integrityHashes: payloadHashes,
})
fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(files.map(name => [name, sha256(path.join(target, name))]))
const archiveHashes = Object.fromEntries(files.map(name => [name, sha256(path.join(archive, name))]))
const archiveMatches = files.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('archive mismatch')
const result = {
  result: 'PASS', checkpointId, sourceCheckpointId, immutable: true,
  localPath: target, archivePath: archive, fiveHashes: localHashes, archiveHashes,
  archiveMatches, businessDataModified: false, productionUserDataWritten: false,
}
write(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
