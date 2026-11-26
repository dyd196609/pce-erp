export const PCE_ADVANCED_FILTER_LAYOUT_VERSION = 'PCE-ADVANCED-FILTER-LAYOUT-V1.0'

export const PCE_ADVANCED_FILTER_LAYOUT_METRICS = Object.freeze({
  controlHeight: 36,
  controlMinWidth: 180,
  columnGap: 12,
  labelGap: 6,
  rowGap: 14,
})

const RANGE_FILTER_TYPES = new Set(['number', 'numberRange', 'date', 'daterange'])

export function resolveAdvancedFilterLayoutGroup(field = {}) {
  const filterType = field.filterType || field.type || 'text'
  return RANGE_FILTER_TYPES.has(filterType) ? 'range' : 'query'
}

export function buildAdvancedFilterLayoutRows(schema = []) {
  const rows = { query: [], range: [] }
  schema.forEach((field) => rows[resolveAdvancedFilterLayoutGroup(field)].push(field))
  return rows
}

export function advancedFilterResponsiveColumns(viewportWidth) {
  const width = Number(viewportWidth || 0)
  if (width >= 1440) return 4
  if (width >= 1024) return 3
  if (width >= 768) return 2
  return 1
}
