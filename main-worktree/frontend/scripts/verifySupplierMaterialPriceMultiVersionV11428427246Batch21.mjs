const API = process.env.PCE_API_BASE || 'http://127.0.0.1:8000'
const TARGET = Object.freeze({
  supplierCode: 'SUP001',
  materialCode: 'MT005',
  historicalPriceNo: 'SMP-PAP-REAL-SQ-202608040011-L1',
  currentPriceNo: 'SMP-PAP-QC-PI-202608040009-MT005',
  purchaseOrderNo: 'PO202608140001',
})

async function read(path) {
  const response = await fetch(`${API}${path}`, { headers: { Accept: 'application/json' } })
  const payload = await response.json()
  if (!response.ok) throw new Error(`${path} HTTP ${response.status}: ${JSON.stringify(payload)}`)
  return payload
}

const pricePath = `/api/masterdata/prices/supplier-material-prices/runtime/facts/?supplierCode=${TARGET.supplierCode}&materialCode=${TARGET.materialCode}`
const first = await read(pricePath)
const second = await read(pricePath)
const purchaseOrders = await read('/api/procurement/scm-page-facts/purchase-order/')
const rows = first.rows || []
const byNo = new Map(rows.map(row => [row.priceNo, row]))
const historical = byNo.get(TARGET.historicalPriceNo)
const current = byNo.get(TARGET.currentPriceNo)
const orderObjects = purchaseOrders?.data?.objects || purchaseOrders?.objects || []
const order = orderObjects.find(item => item.objectNo === TARGET.purchaseOrderNo)
const orderLine = order?.items?.find(item => item.materialCode === TARGET.materialCode)

const gates = [
  ['SUPPLIER-MATERIAL-PRICE-MULTI-VERSION-001', rows.length === 2 && historical && current],
  ['SUPPLIER-MATERIAL-PRICE-UNIQUE-ID-001', new Set(rows.map(row => row.priceNo)).size === rows.length],
  ['SUPPLIER-MATERIAL-PRICE-HISTORY-PRESERVE-001', historical?.versionStatus === 'HISTORICAL'
    && current?.versionStatus === 'CURRENT' && historical?.nextPriceNo === current?.priceNo],
  ['SUPPLIER-MATERIAL-PRICE-SOURCE-TRACE-001', historical?.sourceReference === 'SupplierQuotation:SQ-202608040011:line:1'
    && current?.sourceReference === 'QC-PI-202608040009-MT005'
    && historical?.priceApprovalResultId === 'PAR-PAP-REAL-SQ-202608040011-L1'
    && current?.priceApprovalResultId === 'PAR-PAP-QC-PI-202608040009-MT005'],
  ['SUPPLIER-MATERIAL-PRICE-STATUS-001', historical?.overlapClassification === 'B_HISTORICAL_VERSION_RELATION'
    && current?.overlapClassification === 'B_HISTORICAL_VERSION_RELATION'
    && historical?.scopeStatus === 'DEFAULT_SCOPE_NO_DIMENSIONS'],
  ['PURCHASE-ORDER-SMP-IDENTITY-001', orderLine?.supplierMaterialPriceNo === TARGET.historicalPriceNo
    && String(orderLine?.supplierMaterialPriceId) === '6'],
  ['PURCHASE-ORDER-PRICE-SNAPSHOT-001', Number(orderLine?.unitPrice) === 132
    && Number(orderLine?.unitPriceSnapshot ?? orderLine?.unitPrice) === 132
    && Number(orderLine?.taxRate) === 13 && orderLine?.currency === 'CNY'],
  ['PRICE-EDIT-PERSISTENCE-001', historical?.taxRate === '13'
    && historical?.taxModificationReason === 'V46-Batch2.1自动验收恢复原税率'],
  ['PRICE-EDIT-AUDIT-001', historical?.modificationAuditCount >= 3
    && historical?.oldTaxRate === '9' && historical?.taxModifiedBy && historical?.taxModifiedAt],
  ['PRICE-INTERNAL-REFRESH-001', second.factLoadFacts?.loadedAt !== first.factLoadFacts?.loadedAt
    && second.rows?.find(row => row.priceNo === TARGET.historicalPriceNo)?.taxRate === historical?.taxRate],
]

let failed = 0
for (const [name, passed] of gates) {
  console.log(`${passed ? 'PASS' : 'FAIL'} ${name}`)
  if (!passed) failed += 1
}
console.log(JSON.stringify({
  target: TARGET,
  priceRows: rows.map(row => ({ id: row.sourceId, priceNo: row.priceNo, unitPrice: row.unitPrice,
    versionStatus: row.versionStatus, sourceReference: row.sourceReference,
    confirmedAt: row.confirmedAt, createdAt: row.createdAt })),
  purchaseOrder: order ? { id: order.objectId, objectNo: order.objectNo,
    supplierMaterialPriceNo: orderLine?.supplierMaterialPriceNo,
    unitPrice: orderLine?.unitPrice, taxRate: orderLine?.taxRate, currency: orderLine?.currency } : null,
  passed: gates.length - failed,
  total: gates.length,
}, null, 2))
if (failed) process.exit(1)

