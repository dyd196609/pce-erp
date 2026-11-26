import { getUrgencySortWeight } from './urgencyEngine.js'

const STATUS_ORDER = [
  'draft',
  'pending',
  'prepared',
  'submitted',
  'inspecting',
  'reviewed',
  'rechecked',
  'approved',
  'issued',
  'checking',
  'checked',
  'receiving',
  'received',
  'inspectionPrepared',
  'inspected',
  'inboundPrepared',
  'inventoryPosted',
  'invoicePending',
  'payableReady',
  'closed',
  'cancelled',
]

function dateValue(value) {
  if (!value) return Number.POSITIVE_INFINITY
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? Number.POSITIVE_INFINITY : time
}

function statusWeight(value) {
  const index = STATUS_ORDER.indexOf(String(value || ''))
  return index === -1 ? STATUS_ORDER.length : index
}

export function normalizeSortValue(value, fieldType = 'string') {
  if (fieldType === 'number' || fieldType === 'amount' || fieldType === 'quantity') {
    const number = Number(value)
    return Number.isFinite(number) ? number : 0
  }
  if (fieldType === 'date') return dateValue(value)
  if (fieldType === 'status') return statusWeight(value)
  if (fieldType === 'urgency') return getUrgencySortWeight(value)
  return String(value ?? '').trim()
}

function inferFieldType(key = '', column = {}) {
  if (column.sortType) return column.sortType
  if (column.fieldType) return column.fieldType
  if (column.filterType === 'number' || column.type === 'number') return 'number'
  if (column.filterType === 'date' || column.type === 'date') return 'date'
  if (key === 'status' || key.endsWith('Status')) return 'status'
  if (key === 'deliveryUrgency' || key === 'urgencyLevel') return 'urgency'
  if (key.toLowerCase().includes('date') || key.endsWith('At')) return 'date'
  if (['quantity', 'qty', 'amount', 'price', 'totalAmount', 'planAmount', 'actualAmount', 'lineCount', 'totalQuantity', 'receivableQty', 'availableQuantity', 'lockedQuantity'].some((item) => key.includes(item))) return 'number'
  return 'string'
}

export function sortRecords(records = [], sortState = {}, columns = []) {
  if (!sortState?.key) return records
  const column = columns.find((item) => item.key === sortState.key) || {}
  const fieldType = inferFieldType(sortState.key, column)
  const direction = sortState.direction === 'desc' ? -1 : 1
  return [...records].sort((a, b) => {
    const left = normalizeSortValue(a?.[sortState.key], fieldType)
    const right = normalizeSortValue(b?.[sortState.key], fieldType)
    if (typeof left === 'number' && typeof right === 'number') return (left - right) * direction
    return String(left).localeCompare(String(right), 'zh-Hans-CN') * direction
  })
}

export function clearSortState() {
  return { key: '', direction: 'asc' }
}

export function getDefaultSort(moduleName = '', pageType = '') {
  if (pageType.includes('transaction')) return { key: 'transactionDate', direction: 'desc' }
  if (moduleName === 'scm' && pageType === 'order') return { key: 'deliveryUrgency', direction: 'desc' }
  return clearSortState()
}
