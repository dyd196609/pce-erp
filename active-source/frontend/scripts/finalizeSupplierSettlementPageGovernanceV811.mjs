import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.1.1'
const checkpointId = 'supplier_settlement_page_governance_ready'
const sourceCheckpointId = 'supplier_reconciliation_performance_base_ready'
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join('D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow', checkpointId)
const resultRoot = path.join(frontend, 'test-results/supplier-settlement-page-governance-v811')
const acceptance = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-acceptance-report.json')))
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
if (acceptance.result !== 'passed' || acceptance.totals.FAIL || acceptance.totals.UNKNOWN) throw new Error('page acceptance failed')
if (databaseProtection.businessDataModified || databaseProtection.productionUserDataWritten || iab.result !== 'passed') throw new Error('safety evidence failed')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
write(path.join(target, 'application-state.json'), {
  version, sourceCheckpointId, runtime: 'Supplier Settlement Enterprise Page Governance',
  frameworkVersion: 'PCE Enterprise Page V2',
  contracts: [
    'PCE-FACT-LOAD-CONTRACT-V1.0', 'PCE-BUSINESS-ACTION-CONTRACT-V1.0',
    'PCE-ENTERPRISE-LIST-CONTRACT-V1.0', 'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0',
  ],
  pageAcceptance: acceptance, iabAcceptance: iab, databaseProtection,
})
write(path.join(target, 'business-entities.json'), {
  version, businessDataModified: false,
  governedPages: [
    { pageCode: 'supplier-reconciliation', pageName: '供应商对账', moduleCode: 'SCM_SUPPLIER_RECONCILIATION' },
    { pageCode: 'supplier-performance', pageName: '供应商绩效', moduleCode: 'SCM_SUPPLIER_PERFORMANCE' },
    { pageCode: 'buyer-performance', pageName: '采购员绩效', moduleCode: 'SCM_BUYER_PERFORMANCE' },
  ],
  forbiddenWrites: { paymentExecution: 0, bankSend: 0, fundsDebit: 0, financialImpact: 0 },
})
write(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'PceListPageShell', role: 'enterprise_page_governance_owner' },
    { id: 'supplier-reconciliation', title: '供应商对账 | PCE-ERP' },
    { id: 'supplier-performance', title: '供应商绩效 | PCE-ERP' },
    { id: 'buyer-performance', title: '采购员绩效 | PCE-ERP' },
    { id: 'PceBusinessModuleRegistry' }, { id: 'PceBusinessActionRegistry' }, { id: 'PcePageAcceptanceRegistry' },
  ],
  edges: [
    { from: 'PceListPageShell', to: 'supplier-reconciliation', relation: 'governs' },
    { from: 'PceListPageShell', to: 'supplier-performance', relation: 'governs' },
    { from: 'PceListPageShell', to: 'buyer-performance', relation: 'governs' },
    { from: 'PceBusinessModuleRegistry', to: 'PceListPageShell', relation: 'canonical_identity' },
    { from: 'PceBusinessActionRegistry', to: 'PceListPageShell', relation: 'readonly_actions' },
    { from: 'PcePageAcceptanceRegistry', to: 'PceListPageShell', relation: 'acceptance_contract' },
  ],
})
const payloadHashes = Object.fromEntries(files.slice(1).map(name => [name, sha256(path.join(target, name))]))
write(path.join(target, 'manifest.json'), {
  result: 'passed', version, checkpointId, sourceCheckpointId, createdAt: new Date().toISOString(),
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
  result: 'passed', checkpointId, sourceCheckpointId, immutable: true,
  localPath: target, archivePath: archive, fiveHashes: localHashes, archiveHashes,
  archiveMatches, businessDataModified: false, productionUserDataWritten: false,
}
write(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
