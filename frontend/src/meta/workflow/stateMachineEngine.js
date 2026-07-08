export const businessWorkflowDefinitions = {
  purchaseOrder: {
    module: 'purchaseOrder',
    stateField: 'workflow_state',
    states: ['draft', 'submitted', 'approved', 'received', 'closed'],
    transitions: [
      { action: 'SUBMIT', from: 'draft', to: 'submitted' },
      { action: 'APPROVE', from: 'submitted', to: 'approved' },
      { action: 'RECEIVE', from: 'approved', to: 'received' },
      { action: 'CLOSE', from: 'received', to: 'closed' },
      { action: 'close', from: 'received', to: 'closed' },
    ],
  },
  finance: {
    module: 'finance',
    stateField: 'workflow_state',
    states: ['created', 'reviewed', 'posted', 'settled'],
    transitions: [
      { action: 'REVIEW', from: 'created', to: 'reviewed' },
      { action: 'POST', from: 'reviewed', to: 'posted' },
      { action: 'SETTLE', from: 'posted', to: 'settled' },
      { action: 'close', from: 'posted', to: 'settled' },
    ],
  },
  crm: {
    module: 'crm',
    stateField: 'workflow_state',
    states: ['lead', 'opportunity', 'quotation', 'deal'],
    transitions: [
      { action: 'QUALIFY', from: 'lead', to: 'opportunity' },
      { action: 'QUOTE', from: 'opportunity', to: 'quotation' },
      { action: 'CLOSE_DEAL', from: 'quotation', to: 'deal' },
      { action: 'close', from: 'quotation', to: 'deal' },
    ],
  },
  scm: {
    module: 'scm',
    stateField: 'workflow_state',
    states: ['order', 'in_stock', 'in_transit', 'delivered'],
    transitions: [
      { action: 'STOCK', from: 'order', to: 'in_stock' },
      { action: 'SHIP', from: 'in_stock', to: 'in_transit' },
      { action: 'DELIVER', from: 'in_transit', to: 'delivered' },
      { action: 'close', from: 'in_transit', to: 'delivered' },
    ],
  },
  inventory: {
    module: 'inventory',
    stateField: 'workflow_state',
    states: ['order', 'in_stock', 'in_transit', 'delivered'],
    transitions: [
      { action: 'STOCK', from: 'order', to: 'in_stock' },
      { action: 'SHIP', from: 'in_stock', to: 'in_transit' },
      { action: 'DELIVER', from: 'in_transit', to: 'delivered' },
      { action: 'close', from: 'in_transit', to: 'delivered' },
    ],
  },
}

export function getWorkflowDefinition(module) {
  return businessWorkflowDefinitions[module] || businessWorkflowDefinitions.purchaseOrder
}

export function normalizeState(state, definition) {
  const source = String(state || definition.states[0] || '').trim()
  const lower = source.toLowerCase()
  return definition.states.includes(lower) ? lower : definition.states[0]
}

export function evaluateState(module, context = {}) {
  const definition = getWorkflowDefinition(module)
  const stateField = definition.stateField || 'workflow_state'
  return normalizeState(context.record?.[stateField] || context[stateField], definition)
}

export function getNextSteps(module, context = {}) {
  const definition = getWorkflowDefinition(module)
  const currentState = evaluateState(module, context)
  return definition.transitions.filter((transition) => transition.from === currentState)
}

export function validateTransition(module, action, context = {}) {
  const currentState = evaluateState(module, context)
  const transition = getNextSteps(module, context).find((item) => item.action === action)

  return {
    allowed: !!transition,
    from: currentState,
    to: transition?.to || currentState,
    transition: transition || null,
    reason: transition ? null : 'INVALID_STATE_TRANSITION',
  }
}

export function progressState(module, action, context = {}) {
  const validation = validateTransition(module, action, context)
  if (!validation.allowed) return validation

  return {
    ...validation,
    stateField: getWorkflowDefinition(module).stateField || 'workflow_state',
  }
}
