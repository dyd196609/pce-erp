export const BATCH_FILTER_RUNTIME_VERSION = 'V1.14.2.8.18.14'

export function createBatchFilterRuntime({ schema = [] } = {}) {
  const fields = Object.freeze(schema.filter(field => field.batchFilter !== false)
    .map(field => Object.freeze({ field: field.field, label: field.label, sourceKey: field.sourceKey || field.field })))
  return Object.freeze({ runtimeVersion: BATCH_FILTER_RUNTIME_VERSION, fields,
    createFilter(selectedRows = [], fieldName = '') {
      const field = fields.find(item => item.field === fieldName)
      if (!field) throw new Error('BATCH_FILTER_FIELD_NOT_AVAILABLE')
      const values = [...new Set(selectedRows.flatMap(row => {
        const value = row?.[field.sourceKey]
        return Array.isArray(value) ? value : [value]
      }).filter(value => value !== '' && value != null))]
      if (!values.length) throw new Error('BATCH_FILTER_SELECTION_EMPTY')
      return Object.freeze({ field: field.field, values: Object.freeze(values) })
    },
  })
}
