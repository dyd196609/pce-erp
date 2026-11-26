import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const directory = path.resolve(process.argv[2] || '')
const runId = process.env.PCE_GOLDEN_RUN_ID || ''
const read = (name) => JSON.parse(fs.readFileSync(path.join(directory, name), 'utf8'))
const assert = (condition, message) => { if (!condition) throw new Error(message) }
const metadata = read('staging-metadata.json')
const entities = read('business-entities.json')
const graph = read('relationship-graph.json')
assert(metadata.checkpointId === 'supplier_settlement_ready', 'staged checkpoint id mismatch')
assert(metadata.runId === runId, 'staged run id mismatch')
assert(metadata.nextStageId === 'purchase-reconciliation', 'next stage mismatch')
assert(/^PC\d+$/.test(entities.payableCheckNo), 'payable check mismatch')
assert(entities.supplierSettlementId && entities.supplierSettlementNo, 'supplier settlement identity missing')
assert(entities.supplierSettlementStatus === 'reconciling', 'supplier settlement status mismatch')
assert(entities.settlementQuantity === 1 && entities.settlementAmount === 66, 'settlement quantity or amount mismatch')
assert(entities.purchaseReconciliationGenerated === false && entities.paymentGenerated === false, 'downstream object unexpectedly generated')
assert(graph.downstreamRelations.some((item) => item.relation === 'payableCheck -> supplierSettlement' && item.matched), 'settlement relationship mismatch')
const hashes = {}
for (const name of ['storage-state.json', 'application-state.json', 'business-entities.json', 'relationship-graph.json']) hashes[name] = crypto.createHash('sha256').update(fs.readFileSync(path.join(directory, name))).digest('hex')
console.log(JSON.stringify({ result: 'passed', directory, hashes, userBusinessDataModified: false }, null, 2))
