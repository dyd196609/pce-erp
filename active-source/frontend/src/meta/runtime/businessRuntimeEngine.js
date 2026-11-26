import { executeTransaction } from './transactionEngine.js'
import { postJournalEntry, syncFinanceModule } from './financialPostingEngine.js'
import { deductStock, syncWarehouse } from './inventoryStateEngine.js'
import { emitBusinessEvent, propagateCrossModuleActions, getEnterpriseEventStreamSnapshot } from './enterpriseEventStream.js'
import { syncExecutionWithDB, syncWorkflowWithDB } from '../data/syncEngine.js'
import { writeDatabase } from '../data/databaseLayer.js'

const businessExecutions = []

export function resolveWorkflow(event = {}) {
  const payload = event.payload || {}
  const record = payload.record || payload
  const module = event.module || payload.module || 'purchase'
  const action = event.action || payload.action || 'execute'

  if (module === 'purchase' || event.type === 'purchase.approved') {
    return {
      module: 'purchase',
      action,
      steps: [
        { module: 'purchase', action: 'approve', record: { ...record, approvalStatus: 'Approved', workflow_state: 'approved' } },
        { module: 'finance', action: 'post', record },
        { module: 'inventory', action: 'updateStock', record },
        { module: 'scm', action: 'syncDelivery', record: { ...record, supplyStatus: 'Stable', workflow_state: 'in_transit' } },
      ],
    }
  }

  return {
    module,
    action,
    steps: [
      { module, action, record: { ...record, workflow_state: record.workflow_state || 'committed' } },
    ],
  }
}

export function applyStateChanges(result = {}, context = {}) {
  if (result.status !== 'COMMITTED') return []

  return result.stateUpdates.map((update) => {
    if (update.module === 'finance') {
      const posting = postJournalEntry(update.record, { ...context, transactionId: result.id })
      return { ...update, posting }
    }

    if (update.module === 'inventory') {
      const inventory = syncWarehouse(deductStock(update.record, { ...context, transactionId: result.id }), {
        ...context,
        transactionId: result.id,
      })
      return { ...update, inventory }
    }

    if (update.module === 'scm') {
      const scm = writeDatabase('scm', {
        ...update.record,
        supplyStatus: update.record.supplyStatus || 'Stable',
        workflow_state: update.record.workflow_state || 'in_transit',
        sourceTransactionId: result.id,
      }, context)
      return { ...update, scm }
    }

    return update
  })
}

export function triggerCrossModuleSync(result = {}, context = {}) {
  const propagated = propagateCrossModuleActions({
    ...result,
    correlationId: result.id,
  })
  const workflowSync = syncWorkflowWithDB(result.module, result, context)
  const executionSync = syncExecutionWithDB(result.module, result, context)

  return {
    propagated,
    workflowSync,
    executionSync,
    eventStream: getEnterpriseEventStreamSnapshot(),
  }
}

export function runBusinessTransaction(event = {}, context = {}) {
  const workflow = resolveWorkflow(event)
  const transaction = executeTransaction(workflow, context)
  const stateUpdates = applyStateChanges(transaction, context)
  const sync = triggerCrossModuleSync({ ...transaction, stateUpdates }, context)
  const success = transaction.status === 'COMMITTED'

  const execution = {
    success,
    workflow,
    transaction,
    stateUpdates,
    sync,
    timestamp: Date.now(),
  }

  businessExecutions.unshift(execution)
  if (businessExecutions.length > 100) businessExecutions.length = 100
  emitBusinessEvent({
    type: success ? 'business.runtimeExecuted' : 'business.runtimeFailed',
    module: workflow.module,
    payload: { transactionId: transaction.id, success },
    correlationId: transaction.id,
  })

  return execution
}

export function getBusinessRuntimeSnapshot() {
  const total = businessExecutions.length
  const success = businessExecutions.filter((item) => item.success).length

  return {
    productionRuntime: 'ACTIVE',
    businessExecutionMode: 'ON',
    executions: [...businessExecutions],
    businessExecutionRate: total ? Math.round((success / total) * 100) : 100,
  }
}
