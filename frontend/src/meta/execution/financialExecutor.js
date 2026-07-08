const financialRecords = []

function amountFromContext(context = {}) {
  const record = context.event?.payload?.record || context.record || {}
  const quantity = Number(record.quantity || 0)
  const price = Number(record.price || record.cost || 0)
  return Number(record.amount || record.opportunityValue || quantity * price || 0)
}

export function autoCreatePayable(context = {}) {
  const payable = {
    id: `PAY-${Date.now()}-${financialRecords.length}`,
    type: 'payable',
    sourceEvent: context.event?.type || context.actionPlan?.eventType || 'execution',
    amount: amountFromContext(context),
    currency: context.record?.currency || 'CNY',
    status: 'CREATED',
    createdAt: Date.now(),
  }
  financialRecords.unshift(payable)
  return payable
}

export function autoCreateReceivable(context = {}) {
  const receivable = {
    id: `REC-${Date.now()}-${financialRecords.length}`,
    type: 'receivable',
    sourceEvent: context.event?.type || context.actionPlan?.eventType || 'execution',
    amount: amountFromContext(context),
    currency: context.record?.currency || 'CNY',
    status: 'CREATED',
    createdAt: Date.now(),
  }
  financialRecords.unshift(receivable)
  return receivable
}

export function autoPosting(record = {}) {
  return {
    ...record,
    postingStatus: 'POSTED',
    postedAt: Date.now(),
  }
}

export function autoSettlementSimulation(record = {}) {
  return {
    ...record,
    settlementStatus: Number(record.amount || 0) > 0 ? 'SIMULATED' : 'NO_AMOUNT',
    settledAt: Date.now(),
  }
}

export function runFinancialExecutor(actionPlan = {}, context = {}) {
  const steps = actionPlan.steps || []
  const needsPayable = steps.some((step) => step.module === 'finance' || step.action === 'reviewPayable') ||
    actionPlan.eventType === 'purchase.approved'
  const needsReceivable = actionPlan.eventType === 'crm.dealClosed'
  const created = []

  if (needsPayable) created.push(autoSettlementSimulation(autoPosting(autoCreatePayable({ ...context, actionPlan }))))
  if (needsReceivable) created.push(autoSettlementSimulation(autoPosting(autoCreateReceivable({ ...context, actionPlan }))))

  return {
    records: created,
    financialAutomationScore: created.length ? 100 : 75,
  }
}

export function getFinancialExecutionRecords() {
  return [...financialRecords]
}
