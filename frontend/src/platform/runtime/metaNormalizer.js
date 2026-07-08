export function normalizeRuntime(input = {}) {
  const meta = input.meta || {}

  return {
    fields: normalizeFields(meta),
    actions: normalizeActions(meta),
    table: meta.table || {},
    workflow: input.workflow || {},
    formRules: input.formRules || {},
  }
}

/**
 * =========================
 * 字段标准化
 * =========================
 */
function normalizeFields(meta) {
  const fields = meta.fields || meta.form || meta.table?.columns || []

  return Array.isArray(fields) ? fields : []
}

/**
 * =========================
 * actions标准化
 * =========================
 */
function normalizeActions(meta) {
  const actions = meta.actions || []
  return Array.isArray(actions) ? actions : []
}
