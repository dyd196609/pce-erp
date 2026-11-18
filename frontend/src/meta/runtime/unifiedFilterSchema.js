import { normalizeListFilterSchema } from './listFilterRuntime.js'

export const UNIFIED_FILTER_SCHEMA_VERSION = 'V1.14.2.8.18.14'
export const UNIFIED_FILTER_TYPES = Object.freeze(['text', 'select', 'remote-select', 'date', 'number-range'])

function canonicalType(type = '') {
  if (type === 'number-range') return 'numberRange'
  return type
}

export function createUnifiedFilterSchema({ filterFields = [], optionsProvider = null } = {}) {
  if (!Array.isArray(filterFields) || !filterFields.length) throw new Error('UNIFIED_FILTER_FIELDS_REQUIRED')
  if (!optionsProvider) throw new Error('UNIFIED_FILTER_OPTIONS_PROVIDER_REQUIRED')
  const fields = filterFields.map(field => {
    const declaredType = field.type || field.filterType || 'text'
    if (!UNIFIED_FILTER_TYPES.includes(declaredType)) throw new Error(`UNIFIED_FILTER_TYPE_INVALID:${field.field}`)
    const needsOptions = ['select', 'remote-select'].includes(declaredType)
    const provider = field.optionsProvider || (needsOptions ? optionsProvider : 'none')
    return { ...field, declaredType, type: canonicalType(declaredType),
      optionsSource: field.optionsSource || provider,
      optionsProvider: provider }
  })
  return normalizeListFilterSchema(fields)
}
