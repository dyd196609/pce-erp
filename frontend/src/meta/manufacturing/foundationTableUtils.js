import { sortRecords } from '../runtime/tableSortEngine.js'

export function normalizeText(value) {
  return String(value ?? '').trim().toLowerCase()
}

export function getColumnFilterType(column = {}) {
  if (column.filterType) return column.filterType
  if (column.type === 'number') return 'number'
  if (column.type === 'date') return 'date'
  if (column.type === 'checkbox' || column.type === 'select' || column.options?.length) return 'enum'
  if (['status', 'industryType', 'materialType', 'productCategory', 'equipmentType'].includes(column.key)) return 'enum'
  return 'text'
}

export function applyKeywordFilter(list = [], keyword = '', columns = []) {
  const text = normalizeText(keyword)
  if (!text) return list
  return list.filter((row) => columns.some((column) => normalizeText(row[column.key]).includes(text)))
}

export function applyColumnFilters(list = [], filters = {}, columns = []) {
  return list.filter((row) => columns.every((column) => {
    const filter = filters[column.key] || {}
    const type = getColumnFilterType(column)
    const value = row[column.key]
    if (type === 'number') {
      const min = filter.min === '' || filter.min == null ? null : Number(filter.min)
      const max = filter.max === '' || filter.max == null ? null : Number(filter.max)
      const number = Number(value ?? 0)
      if (min != null && number < min) return false
      if (max != null && number > max) return false
      return true
    }
    if (type === 'date') {
      const start = filter.start ? new Date(filter.start) : null
      const end = filter.end ? new Date(filter.end) : null
      if (!start && !end) return true
      const date = value ? new Date(value) : null
      if (!date || Number.isNaN(date.getTime())) return false
      if (start && date < start) return false
      if (end && date > end) return false
      return true
    }
    if (type === 'enum') {
      const values = Array.isArray(filter.values) ? filter.values.filter(Boolean) : []
      if (!values.length) return true
      return values.map(String).includes(String(value))
    }
    const text = normalizeText(filter.text)
    return !text || normalizeText(value).includes(text)
  }))
}

export function applySorting(list = [], sortState = {}, columns = []) {
  return sortRecords(list, sortState, columns)
}

export function applyPagination(list = [], page = 1, pageSize = 20) {
  const start = (Number(page || 1) - 1) * Number(pageSize || 20)
  return list.slice(start, start + Number(pageSize || 20))
}

export function resetTableState() {
  return {
    keyword: '',
    filters: {},
    sortState: { key: '', direction: 'asc' },
    page: 1,
    pageSize: 20,
  }
}

export function buildFilterOptions(list = [], column = {}) {
  const values = new Set()
  list.forEach((row) => {
    const value = row[column.key]
    if (value !== '' && value != null) values.add(String(value))
  })
  return Array.from(values)
    .sort((a, b) => a.localeCompare(b, 'zh-Hans-CN'))
    .map((value) => ({ value, label: value }))
}

export function exportRowsToCsv(rows = [], columns = [], filename = 'export.csv') {
  const header = columns.map((column) => column.label).join(',')
  const body = rows.map((row) => columns.map((column) => {
    const raw = row[column.key]
    const value = Array.isArray(raw) ? raw.join('、') : raw ?? ''
    return `"${String(value).replaceAll('"', '""')}"`
  }).join(','))
  const blob = new Blob([`\uFEFF${[header, ...body].join('\n')}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}
