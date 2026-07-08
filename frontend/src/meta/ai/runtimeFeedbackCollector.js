const feedbackEvents = []

function normalizeModule(module) {
  return module || 'unknown'
}

function pushFeedback(event) {
  feedbackEvents.push({
    timestamp: Date.now(),
    ...event,
  })
}

function countBy(items, getKey) {
  return items.reduce((map, item) => {
    const key = getKey(item)
    map[key] = (map[key] || 0) + 1
    return map
  }, {})
}

function rate(part, total) {
  return total === 0 ? 0 : part / total
}

export function recordClick(payload = {}) {
  pushFeedback({
    type: 'CLICK',
    module: normalizeModule(payload.module),
    action: payload.action || payload.target || 'unknown',
    field: payload.field,
  })
}

export function recordModuleAccess(module, route) {
  pushFeedback({
    type: 'MODULE_ACCESS',
    module: normalizeModule(module),
    route,
  })
}

export function recordWorkflowCompletion(payload = {}) {
  pushFeedback({
    type: 'WORKFLOW',
    module: normalizeModule(payload.module),
    action: payload.action,
    from: payload.from,
    to: payload.to,
    completed: payload.completed !== false,
  })
}

export function recordRuntimeError(payload = {}) {
  pushFeedback({
    type: 'ERROR',
    module: normalizeModule(payload.module),
    message: payload.message || 'runtime error',
  })
}

export function recordBlocking(payload = {}) {
  pushFeedback({
    type: 'BLOCKING',
    module: normalizeModule(payload.module),
    controlMode: payload.controlMode || 'BLOCKED',
    reason: payload.reason,
  })
}

export function getRuntimeFeedbackEvents() {
  return feedbackEvents
}

export function clearRuntimeFeedback() {
  feedbackEvents.length = 0
}

export function collectRuntimeFeedback(context = {}) {
  const module = normalizeModule(context.module || context.schema?.api?.module || context.schema?.name)
  const scopedEvents = feedbackEvents.filter((event) => module === 'unknown' || event.module === module || event.module === 'unknown')
  const clickEvents = scopedEvents.filter((event) => event.type === 'CLICK')
  const workflowEvents = scopedEvents.filter((event) => event.type === 'WORKFLOW')
  const accessEvents = scopedEvents.filter((event) => event.type === 'MODULE_ACCESS')
  const errorEvents = scopedEvents.filter((event) => event.type === 'ERROR')
  const blockingEvents = scopedEvents.filter((event) => event.type === 'BLOCKING')
  const completedWorkflows = workflowEvents.filter((event) => event.completed)
  const schema = context.schema || {}
  const actions = schema?.ui?.list?.actions || []
  const columns = schema?.ui?.list?.columns || []
  const actionUsage = countBy(clickEvents, (event) => event.action)
  const fieldUsage = countBy(clickEvents.filter((event) => event.field), (event) => event.field)

  return {
    module,
    schema,
    events: scopedEvents,
    clickHeatmap: actionUsage,
    workflowCompletionRate: rate(completedWorkflows.length, workflowEvents.length),
    buttonUsageRate: actions.reduce((map, action) => {
      const key = action.key || action.action || action.event || action.workflowAction
      map[key] = rate(actionUsage[key] || 0, Math.max(clickEvents.length, 1))
      return map
    }, {}),
    moduleAccessFrequency: countBy(accessEvents, (event) => event.route || event.module),
    fieldUsageRate: columns.reduce((map, column) => {
      const key = column.key || column.prop || column.field
      map[key] = rate(fieldUsage[key] || 0, Math.max(clickEvents.length, 1))
      return map
    }, {}),
    errorRate: rate(errorEvents.length, Math.max(scopedEvents.length, 1)),
    blockingRate: rate(blockingEvents.length, Math.max(scopedEvents.length, 1)),
    totals: {
      clicks: clickEvents.length,
      workflow: workflowEvents.length,
      access: accessEvents.length,
      errors: errorEvents.length,
      blocking: blockingEvents.length,
    },
  }
}
