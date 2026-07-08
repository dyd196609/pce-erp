import { writeDatabase } from '../data/databaseLayer.js'
import { emitBusinessEvent } from './enterpriseEventStream.js'

const transactions = []

function transactionId() {
  return `TX-${Date.now()}-${transactions.length}`
}

export function createTransaction(workflow = {}, context = {}) {
  return {
    id: workflow.transactionId || transactionId(),
    module: workflow.module || context.module || 'enterprise',
    action: workflow.action || context.action || 'execute',
    steps: workflow.steps || [],
    context,
    status: 'CREATED',
    createdAt: Date.now(),
  }
}

export function updateState(transaction, step) {
  const record = {
    ...(step.record || {}),
    id: step.id || step.record?.id || `${step.module}-${transaction.id}`,
    workflow_state: step.workflow_state || step.state || 'committed',
    runtimeTransactionId: transaction.id,
    runtimeAction: transaction.action,
    updatedAt: Date.now(),
  }

  return {
    module: step.module || transaction.module,
    action: step.action || 'update',
    record,
  }
}

export function commitChanges(transaction) {
  const stateUpdates = transaction.steps.map((step) => {
    const update = updateState(transaction, step)
    const data = writeDatabase(update.module, update.record, transaction.context)
    return {
      ...update,
      data,
      status: 'COMMITTED',
    }
  })

  const committed = {
    ...transaction,
    status: 'COMMITTED',
    stateUpdates,
    committedAt: Date.now(),
  }
  transactions.unshift(committed)
  if (transactions.length > 100) transactions.length = 100
  emitBusinessEvent({
    type: 'transaction.committed',
    module: transaction.module,
    payload: { transactionId: transaction.id, updates: stateUpdates.length },
    correlationId: transaction.id,
  })

  return committed
}

export function rollbackTransaction(transaction, error) {
  const rolledBack = {
    ...transaction,
    status: 'ROLLED_BACK',
    error: error?.message || String(error || 'TRANSACTION_FAILED'),
    rolledBackAt: Date.now(),
  }
  transactions.unshift(rolledBack)
  if (transactions.length > 100) transactions.length = 100
  emitBusinessEvent({
    type: 'transaction.rolledBack',
    module: transaction.module,
    payload: { transactionId: transaction.id, error: rolledBack.error },
    correlationId: transaction.id,
  })
  return rolledBack
}

export function executeTransaction(workflow = {}, context = {}) {
  const transaction = createTransaction(workflow, context)

  try {
    if (!transaction.steps.length) {
      throw new Error('EMPTY_TRANSACTION_STEPS')
    }

    return commitChanges(transaction)
  } catch (error) {
    return rollbackTransaction(transaction, error)
  }
}

export function getTransactionRuntimeSnapshot() {
  const committed = transactions.filter((item) => item.status === 'COMMITTED').length
  const total = transactions.length

  return {
    transactionLayer: 'ENABLED',
    transactions: [...transactions],
    successIndex: total ? Math.round((committed / total) * 100) : 100,
  }
}
