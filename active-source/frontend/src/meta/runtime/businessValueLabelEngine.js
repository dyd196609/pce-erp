const qualityStatusDictionary = {
  qualified: '合格',
  concession: '让步接收',
  pending: '待检',
  rejected: '不合格',
  unqualified: '不合格',
  returnPending: '退货待处理',
  scrapped: '已报废',
  reworkPending: '返工待处理',
  unknown: '未知',
}

const inventoryStatusDictionary = {
  normal: '正常',
  lowStock: '低库存',
  overStock: '超库存',
  locked: '已锁定',
  zero: '零库存',
  disabled: '已停用',
}

const transactionTypeDictionary = {
  purchaseInspectionIn: '采购检验合格入库',
  concessionIn: '让步接收入库',
  purchaseReceivePrepare: '采购收货预备',
  incomingInspection: '来料检验',
  qualifiedInboundPrepare: '检验合格入库预备',
  inventoryPosting: '库存入库',
  adjustment: '库存调整',
  adjust: '库存调整',
  transfer: '库存调拨',
  lock: '库存锁定',
  unlock: '库存解锁',
  manualInit: '手工初始化',
  opening: '手工初始化',
  manualIn: '手工入库',
  manualOut: '手工出库',
  other: '其他',
}

function normalizeText(value) {
  return String(value ?? '').trim().toLowerCase()
}

export function labelFromDictionary(value, dictionary = {}) {
  return dictionary[value] || value || '-'
}

export function getQualityStatusLabel(value) {
  return labelFromDictionary(value, qualityStatusDictionary)
}

export function getInventoryStatusLabel(value) {
  return labelFromDictionary(value, inventoryStatusDictionary)
}

export function getTransactionTypeLabel(value) {
  return labelFromDictionary(value, transactionTypeDictionary)
}

export function getQualityStatusValue(input) {
  return findDictionaryValue(input, qualityStatusDictionary)
}

export function getInventoryStatusValue(input) {
  return findDictionaryValue(input, inventoryStatusDictionary)
}

export function getTransactionTypeValue(input) {
  return findDictionaryValue(input, transactionTypeDictionary)
}

export function findDictionaryValue(input, dictionary = {}) {
  const text = normalizeText(input)
  if (!text) return ''
  const match = Object.entries(dictionary).find(([value, label]) => (
    normalizeText(value) === text || normalizeText(label) === text
  ))
  return match?.[0] || ''
}

export function matchBusinessLabelOrValue(rawValue, userInput, dictionary = {}) {
  const text = normalizeText(userInput)
  if (!text) return true
  const value = normalizeText(rawValue)
  const label = normalizeText(dictionary[rawValue])
  return value.includes(text) || label.includes(text)
}

export function getBusinessFilterLabel(key, value) {
  if (key === 'qualityStatus') return getQualityStatusLabel(value)
  if (key === 'transactionType') return getTransactionTypeLabel(value)
  if (key === 'status') return getInventoryStatusLabel(value)
  return value ?? '-'
}

export function formatBusinessDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value || '-')
  return date.toISOString().slice(0, 10)
}

export function formatBusinessDateTime(value) {
  if (!value) return '-'
  const raw = String(value)
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return `${raw} 00:00:00`
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value || '-')
  const pad = (number) => String(number).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
