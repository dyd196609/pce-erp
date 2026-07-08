export function normalizeSchema(schema = {}) {
  const api = schema.api && typeof schema.api === 'object' ? schema.api : {}
  const ui = schema.ui && typeof schema.ui === 'object' ? schema.ui : {}
  const list = ui.list && typeof ui.list === 'object' ? ui.list : {}

  const normalized = {
    name: schema.name,
    meta: schema.meta && typeof schema.meta === 'object' ? schema.meta : {},
    api: {
      module: api.module,
    },
    ui: {
      list: {
        columns: list.columns,
        actions: Array.isArray(list.actions) ? list.actions : undefined,
      },
      detail: ui.detail && typeof ui.detail === 'object' ? ui.detail : {},
      form: ui.form && typeof ui.form === 'object' ? ui.form : {},
    },
    workflow: schema.workflow && typeof schema.workflow === 'object' ? schema.workflow : {},
    crud: schema.crud && typeof schema.crud === 'object' ? schema.crud : { actions: [] },
  }

  const status = assertV3Schema(normalized)
  if (!status.valid) {
    throw new Error(`Invalid V3 schema: ${status.errors.join('; ')}`)
  }

  return normalized
}

export function assertV3Schema(schema) {
  const errors = []

  if (typeof schema?.api?.module !== 'string' || schema.api.module.length === 0) {
    errors.push('schema.api.module is required')
  }

  if (!Array.isArray(schema?.ui?.list?.columns)) {
    errors.push('schema.ui.list.columns must be an array')
  }

  if (schema?.ui?.list?.columns?.length === 0) {
    errors.push('schema.ui.list.columns must not be empty')
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}
