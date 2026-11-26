import { resolveListWidthPolicy } from './pceTableScrollRuntime.js'

export const PCE_TABLE_COLUMN_RUNTIME_VERSION = 'V1.14.2.8.18.13.4'

const normalizeColumn = column => {
  const field = String(column.field || '').trim()
  const label = String(column.label || '').trim()
  const width = Number(column.width || column.minWidth || 0)
  if (!field || !label || !Number.isFinite(width) || width <= 0) {
    throw new Error('PCE_TABLE_COLUMN_INVALID')
  }
  return Object.freeze({ ...column, field, label, width,
    minWidth: Number(column.minWidth || column.width || width) })
}

export function createPceTableColumnRuntime({ fixedColumns = [], dynamicGroups = [],
  baseReservedWidth = 0, widthPolicy = 'wide' } = {}) {
  const groups = dynamicGroups.map((group, index) => Object.freeze({
    groupKey: String(group.groupKey || `group-${index + 1}`),
    label: String(group.label || `列组${index + 1}`),
    columns: Object.freeze((group.columns || []).map(normalizeColumn)),
  }))
  const columns = Object.freeze([...fixedColumns.map(normalizeColumn),
    ...groups.flatMap(group => group.columns)])
  const calculatedWidth = Number(baseReservedWidth || 0)
    + columns.reduce((sum, column) => sum + column.width, 0)
  const width = resolveListWidthPolicy({ widthPolicy, requestedMinWidth: calculatedWidth })
  return Object.freeze({ runtimeVersion: PCE_TABLE_COLUMN_RUNTIME_VERSION,
    columns, dynamicGroups: Object.freeze(groups), calculatedWidth,
    minWidth: width.resolvedMinWidth, cssMinWidth: width.cssMinWidth,
    dynamicColumnCount: groups.reduce((sum, group) => sum + group.columns.length, 0) })
}

export function createSupplierComparisonColumnGroups(supplierCount = 0) {
  const count = Math.max(3, Number(supplierCount) || 0)
  return Object.freeze(Array.from({ length: count }, (_, index) => Object.freeze({
    groupKey: `supplier-${index + 1}`, label: `供应商${index + 1}`,
    columns: Object.freeze([
      { field: `supplierName${index + 1}`, label: `供应商${index + 1}`, minWidth: 180 },
      { field: `supplierPrice${index + 1}`, label: '报价', width: 120 },
    ]),
  })))
}
