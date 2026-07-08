const moduleName = 'finance'

export const financeFields = [
  { key: 'accountId', label: '账户ID', sortable: true, filter: true, filterType: 'text' },
  { key: 'accountName', label: '账户名称', filter: true, filterType: 'text' },
  { key: 'debit', label: '借方金额', sortable: true },
  { key: 'credit', label: '贷方金额', sortable: true },
  { key: 'balance', label: '账户余额', sortable: true },
  { key: 'transactionDate', label: '交易日期', sortable: true, filter: true, filterType: 'date' },
  { key: 'currency', label: '币种', filter: true, filterType: 'select' },
  { key: 'costCenter', label: '成本中心', filter: true, filterType: 'select' },
]

let records = [
  {
    id: 601,
    accountId: 'ACC-601',
    accountName: 'Operating Cash',
    debit: 12800,
    credit: 0,
    balance: 12800,
    transactionDate: '2026-06-20',
    currency: 'USD',
    costCenter: 'Manufacturing',
    workflow_state: 'created',
  },
  {
    id: 602,
    accountId: 'ACC-602',
    accountName: 'Accounts Receivable',
    debit: 7600,
    credit: 1200,
    balance: 6400,
    transactionDate: '2026-06-22',
    currency: 'USD',
    costCenter: 'Sales',
    workflow_state: 'reviewed',
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
  const debit = Number(input.debit ?? 0)
  const credit = Number(input.credit ?? 0)
  return {
    id: input.id ?? (Number(String(input.accountId || '').replace(/\D/g, '')) || Date.now()),
    accountId: input.accountId || `ACC-${input.id || Date.now()}`,
    accountName: input.accountName || '-',
    debit,
    credit,
    balance: Number(input.balance ?? debit - credit),
    transactionDate: input.transactionDate || new Date().toISOString().slice(0, 10),
    currency: input.currency || 'USD',
    costCenter: input.costCenter || '-',
    workflow_state: input.workflow_state || 'created',
  }
}

export const financeModel = {
  module: moduleName,
  fields: financeFields,
  list() {
    return response(records.map(normalize))
  },
  detail(id) {
    return response(records.find((record) => String(record.id) === String(id) || record.accountId === id) || null)
  },
  create(payload = {}) {
    const next = normalize({ ...payload, id: payload.id || Date.now() })
    records = [next, ...records]
    return response(next)
  },
  update(id, payload = {}) {
    let updated = null
    records = records.map((record) => {
      if (String(record.id) !== String(id) && record.accountId !== id) return record
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
      workflow_state: payload.data?.workflow_state || (action === 'close' || action === 'SETTLE' ? 'settled' : 'reviewed'),
    })
  },
}
