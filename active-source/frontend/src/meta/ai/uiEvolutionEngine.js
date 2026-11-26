function getActionKey(action = {}) {
  return action.key || action.action || action.event || action.workflowAction
}

function sortByUsage(items, usage, getKey) {
  return [...items].sort((a, b) => (usage[getKey(b)] || 0) - (usage[getKey(a)] || 0))
}

export function optimizeUI(feedback = {}) {
  const schema = feedback.schema || {}
  const actions = schema?.ui?.list?.actions || []
  const columns = schema?.ui?.list?.columns || []
  const reorderedActions = sortByUsage(actions, feedback.buttonUsageRate || {}, getActionKey)
  const reorderedColumns = sortByUsage(columns, feedback.fieldUsageRate || {}, (column) => column.key || column.prop || column.field)
  const hiddenComponents = reorderedActions
    .filter((action) => (feedback.buttonUsageRate?.[getActionKey(action)] || 0) === 0)
    .map(getActionKey)

  return {
    cockpitLayout: ['profit-kpi', 'system-health', 'review-control', 'workflow-status'],
    reorderedActions: reorderedActions.map(getActionKey),
    reorderedColumns: reorderedColumns.map((column) => column.key || column.prop || column.field),
    hiddenComponents,
    ui: {
      list: {
        columns: reorderedColumns,
        actions: reorderedActions,
      },
    },
  }
}
