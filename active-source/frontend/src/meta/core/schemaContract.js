import { trace } from './runtimeTracer.js'

export function validateSchema(schema) {
  if (!schema?.api?.module) {
    trace('schema:error', { reason: 'missing api.module' })
    console.warn('[SCHEMA] Missing api.module')
    return null
  }

  if (!schema?.ui?.list?.columns) {
    trace('schema:error', { reason: 'missing ui.list.columns' })
    console.warn('[SCHEMA] Missing ui.list.columns')
    return null
  }

  schema.ui.list.actions = schema.ui.list.actions || []

  trace('schema:validated:ok', schema)

  return schema
}
