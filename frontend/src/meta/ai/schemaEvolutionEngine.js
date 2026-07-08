function getSchemaVersion(schema = {}) {
  return Number(schema.version || schema.meta?.schemaVersion || 1)
}

function getActionKey(action = {}) {
  return action.key || action.action || action.event || action.workflowAction
}

export function optimizeSchema(feedback = {}) {
  const schema = feedback.schema || {}
  const currentVersion = getSchemaVersion(schema)
  const columns = schema?.ui?.list?.columns || []
  const actions = schema?.ui?.list?.actions || []
  const hasUsageData = (feedback.totals?.clicks || 0) > 0
  const unusedFields = columns
    .filter((column) => column.type !== 'index')
    .filter((column) => hasUsageData && (feedback.fieldUsageRate?.[column.key] || 0) === 0)
    .map((column) => column.key)
  const promotedActions = actions
    .filter((action) => (feedback.buttonUsageRate?.[getActionKey(action)] || 0) >= 0.25)
    .map(getActionKey)
  const hiddenActions = actions
    .filter((action) => hasUsageData && (feedback.buttonUsageRate?.[getActionKey(action)] || 0) === 0)
    .map(getActionKey)
  const nextColumns = columns.filter((column) => !unusedFields.includes(column.key))
  const nextActions = actions.map((action) => {
    const key = getActionKey(action)
    return {
      ...action,
      priority: promotedActions.includes(key) ? 'HIGH' : action.priority,
      evolutionHidden: hiddenActions.includes(key),
    }
  })

  return {
    fromVersion: currentVersion,
    toVersion: currentVersion + 1,
    removedFields: unusedFields,
    promotedActions,
    hiddenActions,
    schema: {
      ...schema,
      version: currentVersion + 1,
      meta: {
        ...(schema.meta || {}),
        schemaVersion: currentVersion + 1,
        evolutionMode: 'AUTO',
      },
      ui: {
        ...(schema.ui || {}),
        list: {
          ...(schema?.ui?.list || {}),
          columns: nextColumns,
          actions: nextActions,
        },
      },
    },
  }
}
