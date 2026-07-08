const moduleName = 'inventory'

export const inventoryFields = [
  { key: 'skuId', label: 'SKU ID', sortable: true, filter: true, filterType: 'text' },
  { key: 'stockQuantity', label: '库存数量', sortable: true },
  { key: 'warehouseLocation', label: '仓库位置', filter: true, filterType: 'select' },
  { key: 'reorderLevel', label: '补货水位', sortable: true },
  { key: 'batchNumber', label: '批次号', filter: true, filterType: 'text' },
  { key: 'expiryDate', label: '有效期', sortable: true, filter: true, filterType: 'date' },
]

let records = [
  {
    id: 501,
    skuId: 'SKU-501',
    stockQuantity: 320,
    warehouseLocation: 'Main-A1',
    reorderLevel: 120,
    batchNumber: 'BATCH-202606-A',
    expiryDate: '2027-06-30',
    workflow_state: 'order',
  },
  {
    id: 502,
    skuId: 'SKU-502',
    stockQuantity: 86,
    warehouseLocation: 'Line-B2',
    reorderLevel: 100,
    batchNumber: 'BATCH-202606-B',
    expiryDate: '2027-03-31',
    workflow_state: 'in_stock',
  },
]

function response(data, success = true) {
  return {
    success,
    data,
    meta: {
      module: moduleName,
      timestamp: Date.now(),
    },
  }
}

function normalize(input = {}) {
  return {
    id: input.id ?? (Number(String(input.skuId || '').replace(/\D/g, '')) || Date.now()),
    skuId: input.skuId || `SKU-${input.id || Date.now()}`,
    stockQuantity: Number(input.stockQuantity ?? 0),
    warehouseLocation: input.warehouseLocation || '-',
    reorderLevel: Number(input.reorderLevel ?? 0),
    batchNumber: input.batchNumber || '-',
    expiryDate: input.expiryDate || new Date().toISOString().slice(0, 10),
    workflow_state: input.workflow_state || 'order',
  }
}

export const inventoryModel = {
  module: moduleName,
  fields: inventoryFields,
  list() {
    return response(records.map(normalize))
  },
  detail(id) {
    return response(records.find((record) => String(record.id) === String(id) || record.skuId === id) || null)
  },
  create(payload = {}) {
    const next = normalize({ ...payload, id: payload.id || Date.now() })
    records = [next, ...records]
    return response(next)
  },
  update(id, payload = {}) {
    let updated = null
    records = records.map((record) => {
      if (String(record.id) !== String(id) && record.skuId !== id) return record
      updated = normalize({ ...record, ...payload, id: record.id })
      return updated
    })
    return response(updated)
  },
  execute(action, payload = {}) {
    if (action === 'create') return this.create(payload.data || payload)
    if (action === 'update') return this.update(payload.id || payload.data?.id, payload.data || payload)
    return this.update(payload.id || payload.data?.id, {
      ...(payload.data || {}),
      workflow_state: payload.data?.workflow_state || (action === 'close' || action === 'DELIVER' ? 'delivered' : 'in_stock'),
    })
  },
}
