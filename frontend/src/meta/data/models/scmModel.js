const moduleName = 'scm'

export const scmFields = [
  { key: 'supplierId', label: '供应商ID', sortable: true, filter: true, filterType: 'text' },
  { key: 'materialId', label: '物料ID', sortable: true, filter: true, filterType: 'text' },
  { key: 'supplyStatus', label: '供应状态', filter: true, filterType: 'select' },
  { key: 'leadTime', label: '交付周期', sortable: true },
  { key: 'cost', label: '供应成本', sortable: true },
  { key: 'deliverySchedule', label: '交付计划', sortable: true, filter: true, filterType: 'date' },
]

let records = [
  {
    id: 801,
    supplierId: 'SUP-801',
    materialId: 'MAT-501',
    supplyStatus: 'Stable',
    leadTime: 7,
    cost: 18.5,
    deliverySchedule: '2026-07-03',
    workflow_state: 'order',
  },
  {
    id: 802,
    supplierId: 'SUP-802',
    materialId: 'MAT-502',
    supplyStatus: 'Watch',
    leadTime: 14,
    cost: 42,
    deliverySchedule: '2026-07-10',
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
    id: input.id ?? (Number(String(input.supplierId || '').replace(/\D/g, '')) || Date.now()),
    supplierId: input.supplierId || `SUP-${input.id || Date.now()}`,
    materialId: input.materialId || '-',
    supplyStatus: input.supplyStatus || 'Stable',
    leadTime: Number(input.leadTime ?? 0),
    cost: Number(input.cost ?? 0),
    deliverySchedule: input.deliverySchedule || new Date().toISOString().slice(0, 10),
    workflow_state: input.workflow_state || 'order',
  }
}

export const scmModel = {
  module: moduleName,
  fields: scmFields,
  list() {
    return response(records.map(normalize))
  },
  detail(id) {
    return response(records.find((record) => String(record.id) === String(id) || record.supplierId === id) || null)
  },
  create(payload = {}) {
    const next = normalize({ ...payload, id: payload.id || Date.now() })
    records = [next, ...records]
    return response(next)
  },
  update(id, payload = {}) {
    let updated = null
    records = records.map((record) => {
      if (String(record.id) !== String(id) && record.supplierId !== id) return record
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
      supplyStatus: action === 'close' || action === 'DELIVER' ? 'Delivered' : 'Stable',
      workflow_state: payload.data?.workflow_state || (action === 'close' || action === 'DELIVER' ? 'delivered' : 'in_stock'),
    })
  },
}
