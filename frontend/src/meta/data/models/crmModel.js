const moduleName = 'crm'

export const crmFields = [
  { key: 'customerId', label: '客户ID', sortable: true, filter: true, filterType: 'text' },
  { key: 'customerName', label: '客户名称', filter: true, filterType: 'text' },
  { key: 'contactInfo', label: '联系方式', filter: true, filterType: 'text' },
  { key: 'leadStage', label: '线索阶段', filter: true, filterType: 'select' },
  { key: 'opportunityValue', label: '商机金额', sortable: true },
  { key: 'salesOwner', label: '销售负责人', filter: true, filterType: 'select' },
  { key: 'lifecycleStatus', label: '生命周期状态', filter: true, filterType: 'select' },
]

let records = [
  {
    id: 701,
    customerId: 'CUS-701',
    customerName: 'North Star Manufacturing',
    contactInfo: 'ops@northstar.example',
    leadStage: 'Qualified',
    opportunityValue: 46000,
    salesOwner: 'Sales A',
    lifecycleStatus: 'Active',
    workflow_state: 'lead',
  },
  {
    id: 702,
    customerId: 'CUS-702',
    customerName: 'East Works',
    contactInfo: 'procurement@eastworks.example',
    leadStage: 'Proposal',
    opportunityValue: 32000,
    salesOwner: 'Sales B',
    lifecycleStatus: 'Expansion',
    workflow_state: 'opportunity',
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
    id: input.id ?? (Number(String(input.customerId || '').replace(/\D/g, '')) || Date.now()),
    customerId: input.customerId || `CUS-${input.id || Date.now()}`,
    customerName: input.customerName || '-',
    contactInfo: input.contactInfo || '-',
    leadStage: input.leadStage || 'New',
    opportunityValue: Number(input.opportunityValue ?? 0),
    salesOwner: input.salesOwner || '-',
    lifecycleStatus: input.lifecycleStatus || 'Prospect',
    workflow_state: input.workflow_state || 'lead',
  }
}

export const crmModel = {
  module: moduleName,
  fields: crmFields,
  list() {
    return response(records.map(normalize))
  },
  detail(id) {
    return response(records.find((record) => String(record.id) === String(id) || record.customerId === id) || null)
  },
  create(payload = {}) {
    const next = normalize({ ...payload, id: payload.id || Date.now() })
    records = [next, ...records]
    return response(next)
  },
  update(id, payload = {}) {
    let updated = null
    records = records.map((record) => {
      if (String(record.id) !== String(id) && record.customerId !== id) return record
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
      lifecycleStatus: action === 'close' || action === 'CLOSE_DEAL' ? 'Closed' : 'Active',
      workflow_state: payload.data?.workflow_state || (action === 'close' || action === 'CLOSE_DEAL' ? 'deal' : 'opportunity'),
    })
  },
}
