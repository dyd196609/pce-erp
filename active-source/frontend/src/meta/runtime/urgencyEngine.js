const URGENCY_LABELS = {
  normal: '正常',
  urgent: '紧急',
  critical: '特急',
  overdue: '超期',
  completed: '已达成',
  unknown: '未设日期',
}

const URGENCY_SORT_WEIGHT = {
  normal: 1,
  urgent: 2,
  critical: 3,
  overdue: 4,
  completed: 5,
  unknown: 6,
}

const COMPLETED_STATUSES = ['received', 'fullyReceived', 'inventoryPosted', 'closed', 'completed', 'done']

function toDateOnly(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

function diffDays(left, right) {
  return Math.ceil((left.getTime() - right.getTime()) / 86400000)
}

export function calculateDeliveryUrgency(record = {}, baseDate = new Date()) {
  const status = record.orderStatus || record.status || ''
  const actualDate = record.actualDeliveryDate || record.actualArrivalDate || record.actualReceiveDate
  if (actualDate || COMPLETED_STATUSES.includes(status)) return 'completed'

  const planDate = record.expectedDeliveryDate || record.planDeliveryDate || record.plannedArrivalDate || record.expectedReceiveDate
  const planned = toDateOnly(planDate)
  if (!planned) return 'unknown'

  const today = toDateOnly(baseDate) || toDateOnly(new Date())
  const days = diffDays(planned, today)
  if (days < 0) return 'overdue'
  if (days <= 3) return 'critical'
  if (days <= 7) return 'urgent'
  return 'normal'
}

export function getUrgencyLabel(urgency) {
  return URGENCY_LABELS[urgency] || URGENCY_LABELS.unknown
}

export function getUrgencySortWeight(urgency) {
  return URGENCY_SORT_WEIGHT[urgency] || URGENCY_SORT_WEIGHT.unknown
}

export function getUrgencyTagType(urgency) {
  return {
    normal: 'success',
    urgent: 'warning',
    critical: 'danger',
    overdue: 'danger',
    completed: 'info',
    unknown: 'info',
  }[urgency] || 'info'
}

export function getUrgencyStyle(urgency) {
  if (urgency === 'overdue') return { color: '#991b1b', fontWeight: 700 }
  if (urgency === 'critical') return { color: '#dc2626', fontWeight: 600 }
  if (urgency === 'urgent') return { color: '#ea580c', fontWeight: 600 }
  if (urgency === 'normal') return { color: '#15803d' }
  return { color: '#64748b' }
}

export function filterByUrgency(records = [], urgency = '') {
  if (!urgency) return records
  return records.filter((record) => calculateDeliveryUrgency(record) === urgency)
}

