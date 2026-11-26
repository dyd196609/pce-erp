const defaultStateActionMap = {
  DRAFT: 'prepare_documents',
  SUBMITTED: 'notify_reviewer',
  APPROVED: 'release_purchase_or_work_order',
  RECEIVED: 'confirm_delivery',
  STOCKED: 'update_inventory',
  CLOSED: 'archive_case',
}

export function mapWorkflowStatesToRealActions(workflow = {}, record = {}) {
  const states = workflow.states || ['DRAFT', 'SUBMITTED', 'APPROVED', 'CLOSED']
  const currentState = record.workflow_state || record.state || states[0]

  return states.map((state) => ({
    state,
    realAction: defaultStateActionMap[state] || `execute_${String(state).toLowerCase()}`,
    active: state === currentState,
  }))
}

export function mapExecutionPriority(context = {}) {
  const record = context.record || {}
  const amount = Number(record.amount || record.revenue || 0)
  const urgency = record.urgency || context.feedback?.urgency

  return {
    priority: urgency === 'high' || amount > 100000 ? 'HIGH' : amount > 20000 ? 'MEDIUM' : 'NORMAL',
    reason: urgency === 'high' ? 'BUSINESS_URGENCY' : amount > 20000 ? 'FINANCIAL_IMPACT' : 'STANDARD_FLOW',
  }
}

export function translateOperationalImpact(context = {}) {
  const priority = mapExecutionPriority(context)

  return {
    laborImpact: priority.priority === 'HIGH' ? 'REALLOCATE_TEAM_CAPACITY' : 'NORMAL_STAFFING',
    cashImpact: priority.priority === 'HIGH' ? 'ACCELERATE_CASH_REVIEW' : 'STANDARD_CASH_REVIEW',
    supplyImpact: priority.priority === 'HIGH' ? 'RESERVE_SUPPLY_CAPACITY' : 'NORMAL_SUPPLY_FLOW',
  }
}

export function mapWorkflowToReality(context = {}) {
  return {
    mode: 'V28_WORKFLOW_REALITY_MAPPING',
    actions: mapWorkflowStatesToRealActions(context.workflow, context.record),
    priority: mapExecutionPriority(context),
    operationalImpact: translateOperationalImpact(context),
  }
}
