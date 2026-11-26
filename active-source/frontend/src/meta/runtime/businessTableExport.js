export const BUSINESS_TABLE_EXPORT_VERSION = 'V1.14.2.8.4.6'

export const BUSINESS_TABLE_EXPORT_SCOPES = Object.freeze({
  selected: 'selected',
  currentResult: 'current_result',
})

function csvEscape(value) {
  return `"${String(value ?? '').replaceAll('"', '""')}"`
}

export function buildBusinessTableExport({ scope, selectedRows = [], sortedRows = [], columns = [], canonicalName = '' } = {}) {
  if (!Object.values(BUSINESS_TABLE_EXPORT_SCOPES).includes(scope)) {
    throw new Error('导出范围必须明确为 selected 或 current_result。')
  }
  if (!canonicalName || !columns.length) {
    throw new Error('导出必须提供中文标准模块名称和业务字段。')
  }

  const rows = scope === BUSINESS_TABLE_EXPORT_SCOPES.selected ? selectedRows : sortedRows
  const headers = columns.map((column) => column.label)
  const csv = [headers.map(csvEscape).join(',')]
    .concat(rows.map((row) => columns.map((column) => csvEscape(
      typeof column.value === 'function' ? column.value(row) : row[column.key],
    )).join(',')))
    .join('\n')

  return {
    scope,
    canonicalName,
    sheetNames: [canonicalName],
    rowCount: rows.length,
    rows: [...rows],
    csv: `\ufeff${csv}`,
  }
}

export function downloadBusinessTableCsv(options = {}) {
  const result = buildBusinessTableExport(options)
  const date = new Date().toISOString().slice(0, 10).replaceAll('-', '')
  const scopeSuffix = result.scope === BUSINESS_TABLE_EXPORT_SCOPES.selected ? '已选记录' : '当前结果'
  const blob = new Blob([result.csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `${result.canonicalName}-${scopeSuffix}-${date}.csv`
  link.click()
  URL.revokeObjectURL(link.href)
  return result
}
