export const LIST_FILTER_RUNTIME_VERSION = 'V1.14.2.8.18.14'
export const LIST_FILTER_TYPES = Object.freeze(['text', 'select', 'date', 'number'])
const COMPATIBLE_TYPES = Object.freeze([...LIST_FILTER_TYPES, 'remote-select', 'number-range', 'daterange', 'numberRange', 'boolean'])

const normalizeOption = option => Object.freeze(typeof option === 'object'
  ? { value: option.value, label: String(option.label ?? option.value ?? '') }
  : { value: option, label: String(option) })

export function normalizeListFilterField(input = {}) {
  const field = String(input.field || input.key || '').trim()
  const label = String(input.label || '').trim()
  const declaredFilterType = input.filterType || input.type || 'text'
  const filterType = declaredFilterType === 'number-range'
    ? 'numberRange'
    : declaredFilterType === 'searchable_select' ? 'select' : declaredFilterType
  const type = input.type || (filterType === 'daterange' ? 'dateRange' : filterType)
  if (!field || !label) throw new Error('LIST_FILTER_FIELD_AND_LABEL_REQUIRED')
  if (!COMPATIBLE_TYPES.includes(filterType)) throw new Error(`LIST_FILTER_TYPE_INVALID:${field}`)
  const options = Object.freeze((input.options || []).map(normalizeOption))
  const optionsSource = input.optionsSource || input.optionsProvider
    || (options.length ? 'static' : filterType === 'select' ? 'current_result' : 'none')
  if (['select', 'remote-select'].includes(filterType) && !options.length && !optionsSource) {
    throw new Error(`LIST_FILTER_OPTIONS_SOURCE_REQUIRED:${field}`)
  }
  return Object.freeze({ ...input, field, key: field, label, type, filterType,
    options, optionsSource, optionsProvider: input.optionsProvider || optionsSource,
    sourceKey: input.sourceKey || field })
}

export function normalizeListFilterSchema(schema = []) {
  if (!Array.isArray(schema) || !schema.length) throw new Error('LIST_FILTER_SCHEMA_REQUIRED')
  return Object.freeze(schema.map(normalizeListFilterField))
}

export function resolveListFilterOptions(field = {}, rows = []) {
  const normalized = normalizeListFilterField(field)
  if (!['select', 'remote-select'].includes(normalized.filterType)) return Object.freeze([])
  let options = normalized.options
  const source = normalized.optionsSource
  if (!options.length && typeof source === 'function') options = source({ field: normalized, rows }) || []
  if (!options.length && source && typeof source === 'object') {
    options = typeof source.loadOptions === 'function' ? source.loadOptions(normalized) : source.options || []
  }
  if (!options.length && ['current_result', 'currentResultDistinctValues'].includes(source)) {
    options = [...new Set(rows.flatMap(row => {
      const value = row?.[normalized.sourceKey]
      return Array.isArray(value) ? value : [value]
    }).filter(value => value !== '' && value != null))]
  }
  return Object.freeze(options.map(normalizeOption))
}

export async function resolveRemoteListFilterOptions(field = {}, query = '', rows = []) {
  const normalized = normalizeListFilterField(field)
  if (normalized.filterType !== 'remote-select') return resolveListFilterOptions(normalized, rows)
  const source = normalized.optionsProvider || normalized.optionsSource
  let options = normalized.options
  if (typeof source === 'function') options = await source({ query, field: normalized, rows })
  else if (source && typeof source === 'object') {
    if (typeof source.searchOptions === 'function') options = await source.searchOptions({ query, field: normalized, rows })
    else if (typeof source.loadOptions === 'function') options = await source.loadOptions({ query, field: normalized, rows })
  }
  return Object.freeze((options || []).map(normalizeOption))
}
