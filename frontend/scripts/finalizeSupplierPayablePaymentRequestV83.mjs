import crypto from 'node:crypto'
import fs from 'node:fs'
import path from 'node:path'

const frontend = process.cwd()
const version = 'V1.14.2.8.4.8.3'
const checkpointId = 'supplier_payable_payment_request_business_ready'
const sourceCheckpointId = 'supplier_reconciliation_difference_collaboration_ready'
const checkpointRoot = path.join(frontend, 'test-results/purchase-payment-golden-flow/checkpoints')
const source = path.join(checkpointRoot, sourceCheckpointId)
const target = path.join(checkpointRoot, checkpointId)
const archive = path.join('D:\\Dev-PCE\\CheckpointArchive\\purchase-payment-golden-flow', checkpointId)
const resultRoot = path.join(frontend, 'test-results/supplier-payable-payment-request-v83')
const acceptance = JSON.parse(fs.readFileSync(path.join(resultRoot, 'page-acceptance-report.json')))
const databaseProtection = JSON.parse(fs.readFileSync(path.join(resultRoot, 'database-protection-report.json')))
const iab = JSON.parse(fs.readFileSync(path.join(resultRoot, 'iab_acceptance_report.json')))
const scan = JSON.parse(fs.readFileSync(path.join(resultRoot, 'supplier_payable_confirmation_scan_v83.json')))
const files = ['manifest.json', 'storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']
const sha256 = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toUpperCase()
const write = (file, value) => {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`)
}

if (!fs.existsSync(source)) throw new Error(`source checkpoint missing: ${sourceCheckpointId}`)
if (fs.existsSync(target) || fs.existsSync(archive)) throw new Error('immutable target already exists')
if (acceptance.result !== 'PASS' || acceptance.totals.FAIL || acceptance.totals.UNKNOWN) throw new Error('acceptance failed')
if (iab.result !== 'PASS' || databaseProtection.productionUserDataWritten) throw new Error('safety evidence failed')
fs.mkdirSync(target, { recursive: false })
fs.copyFileSync(path.join(source, 'storage-state.json'), path.join(target, 'storage-state.json'))
write(path.join(target, 'application-state.json'), {
  version, sourceCheckpointId,
  runtime: 'Supplier Payable Confirmation and Payment Request',
  contracts: [
    'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
    'PCE-FACT-LOAD-CONTRACT-V1.0',
    'PCE-ACCEPTANCE-OBSERVABILITY-CONTRACT-V1.0',
    'PCE-PAGE-ACCEPTANCE-CONTRACT-V2.0',
  ],
  acceptance, iab, databaseProtection, scan,
})
write(path.join(target, 'business-entities.json'), {
  version,
  entities: {
    SupplierPayableConfirmation: 4,
    SupplierPaymentRequest: 3,
    BuyerPerformanceMetric: 3,
  },
  stateMachines: {
    payableConfirmation: ['draft', 'internal_review', 'confirmed', 'ready_for_payment_request'],
    paymentRequest: ['draft', 'submitted', 'approved', 'payment_pending'],
  },
  forbiddenWrites: { paymentExecution: 0, bankSend: 0, fundsDebit: 0, bankTransaction: 0, ledger: 0 },
})
write(path.join(target, 'relationship-graph.json'), {
  version,
  nodes: [
    { id: 'SupplierReconciliation' },
    { id: 'SupplierReconciliationDifference' },
    { id: 'SupplierReconciliationConfirmation' },
    { id: 'SupplierPayableConfirmation' },
    { id: 'SupplierPaymentRequest' },
    { id: 'BusinessStateTransition' },
  ],
  edges: [
    { from: 'SupplierReconciliation', to: 'SupplierPayableConfirmation', relation: 'confirms_payable' },
    { from: 'SupplierReconciliationDifference', to: 'SupplierPayableConfirmation', relation: 'deduction_source' },
    { from: 'SupplierReconciliationConfirmation', to: 'SupplierPayableConfirmation', relation: 'supplier_evidence' },
    { from: 'SupplierPayableConfirmation', to: 'SupplierPaymentRequest', relation: 'creates_request' },
    { from: 'BusinessStateTransition', to: 'SupplierPayableConfirmation', relation: 'governs_state' },
    { from: 'BusinessStateTransition', to: 'SupplierPaymentRequest', relation: 'governs_state' },
  ],
})
const payloadHashes = Object.fromEntries(files.slice(1).map(name => [name, sha256(path.join(target, name))]))
write(path.join(target, 'manifest.json'), {
  result: 'PASS', version, checkpointId, sourceCheckpointId, createdAt: new Date().toISOString(),
  immutable: true, restorable: true, productionUserDataWritten: false,
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
  archiveMatches, productionUserDataWritten: false,
}
write(path.join(resultRoot, 'checkpoint_result.json'), result)
console.log(JSON.stringify(result, null, 2))
