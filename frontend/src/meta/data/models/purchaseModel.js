const moduleName = 'purchaseOrder'

export const purchaseFields = [
  { key: 'purchaseOrderId', label: '采购订单ID', sortable: true, filter: true, filterType: 'text' },
  { key: 'supplierId', label: '供应商ID', filter: true, filterType: 'select' },
  { key: 'materialList', label: '物料清单', filter: true, filterType: 'text' },
  { key: 'quantity', label: '采购数量', sortable: true },
  { key: 'price', label: '采购单价', sortable: true },
  { key: 'approvalStatus', label: '审批状态', filter: true, filterType: 'select' },
  { key: 'deliveryStatus', label: '交付状态', filter: true, filterType: 'select' },
]

let records = [
  {
    id: 412,
    purchaseOrderId: 'PO-2026-0412',
    supplierId: 'SUP-801',
    materialList: 'MAT-501 Bearing; MAT-502 Motor',
    quantity: 120,
    price: 18.5,
    approvalStatus: 'Draft',
    deliveryStatus: 'Scheduled',
    workflow_state: 'draft',
  },
  {
    id: 413,
    purchaseOrderId: 'PO-2026-0413',
    supplierId: 'SUP-802',
    materialList: 'MAT-502 Motor',
    quantity: 60,
    price: 42,
    approvalStatus: 'Submitted',
    deliveryStatus: 'Pending',
    workflow_state: 'submitted',
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
  const quantity = Number(input.quantity ?? 0)
  const price = Number(input.price ?? 0)
  return {
    id: input.id ?? (Number(String(input.purchaseOrderId || '').replace(/\D/g, '')) || Date.now()),
    purchaseOrderId: input.purchaseOrderId || `PO-${input.id || Date.now()}`,
    supplierId: input.supplierId || '-',
    materialList: Array.isArray(input.materialList) ? input.materialList.join('; ') : input.materialList || '-',
    quantity,
    price,
    approvalStatus: input.approvalStatus || 'Draft',
    deliveryStatus: input.deliveryStatus || 'Pending',
    workflow_state: input.workflow_state || 'draft',
  }
}

export const purchaseModel = {
  module: moduleName,
  aliases: ['purchase', 'purchaseOrderDetail'],
  fields: purchaseFields,
  list() {
    return response(records.map(normalize))
  },
  detail(id) {
    return response(records.find((record) => String(record.id) === String(id) || record.purchaseOrderId === id) || null)
  },
  create(payload = {}) {
    const next = normalize({ ...payload, id: payload.id || Date.now() })
    records = [next, ...records]
    return response(next)
  },
  update(id, payload = {}) {
    let updated = null
    records = records.map((record) => {
      if (String(record.id) !== String(id) && record.purchaseOrderId !== id) return record
      updated = normalize({ ...record, ...payload, id: record.id })
      return updated
    })
    return response(updated)
  },
  execute(action, payload = {}) {
    if (action === 'create') return this.create(payload.data || payload)
    if (action === 'update') return this.update(payload.id || payload.data?.id, payload.data || payload)

    const nextState = {
      SUBMIT: { workflow_state: 'submitted', approvalStatus: 'Submitted' },
      APPROVE: { workflow_state: 'approved', approvalStatus: 'Approved' },
      RECEIVE: { workflow_state: 'received', deliveryStatus: 'Received' },
      CLOSE: { workflow_state: 'closed', deliveryStatus: 'Closed' },
      close: { workflow_state: 'closed', deliveryStatus: 'Closed' },
    }[action] || { workflow_state: payload.data?.workflow_state || 'draft' }

    return this.update(payload.id || payload.data?.id, {
      ...(payload.data || {}),
      ...nextState,
    })
  },
}
