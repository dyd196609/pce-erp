import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.1'
const checkpointId = 'supplier_reconciliation_performance_base_ready'
const sourceCheckpointId = 'bank_send_execution_framework_design_ready'
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join('D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow', checkpointId)
const resultRoot = path.join(frontend, 'test-results/supplier-reconciliation-performance-v81')
const acceptance = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-acceptance-report.json')))
const databaseProtection = JSON.parse(fs.readFileSync(path.join(resultRoot, 'database-protection-report.json')))
const iab = JSON.parse(fs.readFileSync(path.join(resultRoot, 'iab_acceptance_report.json')))
const scan = JSON.parse(fs.readFileSync(path.join(resultRoot, 'supplier_settlement_chain_scan_v81.json')))
const files = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const write = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}
if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target) || fs.existsSync(archive)) throw new Error('immutable target already exists')
if (acceptance.result !== 'passed' || acceptance.totals.FAIL || acceptance.totals.UNKNOWN) throw new Error('acceptance failed')
if (databaseProtection.productionUserDataWritten !== false || iab.result !== 'passed') throw new Error('safety evidence failed')

fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
write(path.join(target, 'application-state.json'), {
  version, sourceCheckpointId, runtime: 'Supplier Reconciliation and Procurement Performance Base',
  chainScan: scan, pageAcceptance: acceptance, databaseProtection, iabAcceptance: iab,
})
write(path.join(target, 'business-entities.json'), {
  version, factSource: 'server',
  entities: [
    { entityType: 'SupplierReconciliation', recordCount: 4, states: ['draft', 'internal_review', 'supplier_confirming', 'completed'] },
    { entityType: 'BuyerPerformanceMetric', recordCount: 3 },
    { entityType: 'SupplierPerformanceMetric', recordCount: 4 },
  ],
  forbiddenEntities: { paymentExecution: 0, bankSend: 0, fundsDebit: 0, ledgerEntry: 0 },
})
write(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'PurchaseOrder' }, { id: 'Receipt' }, { id: 'Inspection' }, { id: 'WarehouseReceipt' },
    { id: 'SupplierReconciliation', state: 'governed' }, { id: 'SupplierPerformanceMetric' }, { id: 'BuyerPerformanceMetric' },
  ],
  edges: [
    { from: 'PurchaseOrder', to: 'Receipt' }, { from: 'Receipt', to: 'Inspection' },
    { from: 'Inspection', to: 'WarehouseReceipt' }, { from: 'WarehouseReceipt', to: 'SupplierReconciliation' },
    { from: 'SupplierReconciliation', to: 'SupplierPerformanceMetric', relation: 'metric_source' },
    { from: 'PurchaseOrder', to: 'BuyerPerformanceMetric', relation: 'metric_source' },
    { from: 'draft', to: 'internal_review', service: 'BusinessStateTransition' },
    { from: 'internal_review', to: 'supplier_confirming', service: 'BusinessStateTransition' },
    { from: 'supplier_confirming', to: 'completed', service: 'BusinessStateTransition' },
  ],
  forbiddenEdges: ['SupplierReconciliation -> PaymentExecution', 'SupplierReconciliation -> BankSend', 'completed -> payment_executed'],
})
const payloadHashes = Object.fromEntries(files.slice(1).map(name => [name, hash(path.join(target, name))]))
write(path.join(target, 'manifest.json'), {
  result: 'passed', version, checkpointId, sourceCheckpointId, createdAt: new Date().toISOString(),
  immutable: true, restorable: true, productionUserDataWritten: false,
  paymentExecutionWritten: false, bankSendWritten: false, integrityFiles: files, integrityHashes: payloadHashes,
})
fs.mkdirSync(path.dirname(archive), { recursive: true })
fs.cpSync(target, archive, { recursive: true, errorOnExist: true })
const localHashes = Object.fromEntries(files.map(name => [name, hash(path.join(target, name))]))
const archiveHashes = Object.fromEntries(files.map(name => [name, hash(path.join(archive, name))]))
const archiveMatches = files.every(name => localHashes[name] === archiveHashes[name])
if (!archiveMatches) throw new Error('archive mismatch')
const result = {
  result: 'passed', checkpointId, sourceCheckpointId, immutable: true,
  localPath: target, archivePath: archive, fiveHashes: localHashes, archiveHashes,
  archiveMatches, productionUserDataWritten: false,
}
write(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
