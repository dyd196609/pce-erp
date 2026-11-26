import {
  createPceAdvancedFilterSchema,
  resolvePceFilterOptions,
} from './pceAdvancedFilterContract.js'

export const STANDARD_LIST_CONTRACT_VERSION = 'V1.14.2.8.4.7.52.1'

const EMPTY = Object.freeze([])

function normalizeText(value) {
  return String(value ?? '').trim().toLowerCase()
}

function decimalParts(value) {
  const match = String(value ?? '').trim().match(/^(-?)(\d+)(?:\.(\d{0,2}))?$/)
  if (!match) return null
  const minor = BigInt(match[2]) * 100n + BigInt((match[3] || '').padEnd(2, '0'))
  return match[1] ? -minor : minor
}

export function compareDecimalStrings(left, right) {
  const a = decimalParts(left)
  const b = decimalParts(right)
  if (a === null || b === null) return String(left ?? '').localeCompare(String(right ?? ''))
  return a === b ? 0 : a < b ? -1 : 1
}

export function createStandardListContract(config) {
  const filterSchema = createPceAdvancedFilterSchema(config.filterSchema || EMPTY)
  const contract = {
    contractVersion: STANDARD_LIST_CONTRACT_VERSION,
    tableId: config.tableId,
    stateId: config.stateId,
    filterSchema,
    columnSchema: Object.freeze(config.columnSchema || EMPTY),
    defaultSort: Object.freeze(config.defaultSort || { prop: '', order: '' }),
    stickyColumns: Object.freeze(config.stickyColumns || {
      left: ['selection', 'sequence'],
      right: ['operation'],
    }),
    horizontalScrollOwner: config.horizontalScrollOwner || 'element-plus-native',
    rowSelection: true,
    resultCount: true,
    selectedCount: true,
    effectiveFilterCount: true,
    exportColumns: Object.freeze(config.exportColumns || EMPTY),
    operationColumn: Object.freeze(config.operationColumn || { label: '操作', width: 104 }),
    emptyState: config.emptyState || '暂无符合条件的记录',
    searchPlaceholder: config.searchPlaceholder || '输入编号、供应商或关键词',
  }
  return Object.freeze(contract)
}

export function createFilterState(contract) {
  return Object.fromEntries(contract.filterSchema.map(field => [field.key, field.defaultValue ?? '']))
}

export function countEffectiveFilters(quickSearch, filters, contract) {
  return Number(Boolean(normalizeText(quickSearch)))
    + contract.filterSchema.filter(field => normalizeText(filters[field.key])).length
}

function matchesField(row, field, rawValue) {
  if (rawValue === '' || rawValue === null || rawValue === undefined) return true
  const actual = row[field.sourceKey || field.key]
  if (field.queryType === 'decimal-min') return compareDecimalStrings(actual, rawValue) >= 0
  if (field.queryType === 'decimal-max') return compareDecimalStrings(actual, rawValue) <= 0
  if (field.queryType === 'date-min') return String(actual || '') >= String(rawValue)
  if (field.queryType === 'date-max') return String(actual || '') <= String(rawValue)
  if (field.queryType === 'boolean') return String(Boolean(actual)) === String(rawValue)
  if (field.match === 'contains') return normalizeText(actual).includes(normalizeText(rawValue))
  return normalizeText(actual) === normalizeText(rawValue)
}

export function resolveStandardFilterOptions(field, rows = []) {
  return resolvePceFilterOptions(field, rows)
}

export function applyStandardListQuery(rows, {
  quickSearch,
  filters,
  contract,
  sort,
}) {
  const query = normalizeText(quickSearch)
  const filtered = rows.filter((row) => {
    if (query && !normalizeText(JSON.stringify(row)).includes(query)) return false
    return contract.filterSchema.every(field => matchesField(row, field, filters[field.key]))
  })
  const activeSort = sort?.prop ? sort : contract.defaultSort
  if (!activeSort?.prop || !activeSort?.order) return filtered
  const factor = activeSort.order === 'descending' ? -1 : 1
  return [...filtered].sort((left, right) => {
    const a = left[activeSort.prop]
    const b = right[activeSort.prop]
    const compared = activeSort.kind === 'decimal'
      ? compareDecimalStrings(a, b)
      : String(a ?? '').localeCompare(String(b ?? ''), 'zh-CN', { numeric: true })
    return compared * factor
  })
}

export function safeExportRows(rows, contract) {
  return rows.map(row => Object.fromEntries(
    contract.exportColumns.map(column => [column.key, row[column.key] ?? '']),
  ))
}
