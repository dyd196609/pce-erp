export const BUSINESS_FLOW_TRANSACTION_COORDINATOR_VERSION = 'V1.14.2'

function clone(value) {
  return JSON.parse(JSON.stringify(value ?? null))
}

export async function runBusinessFlowTransaction({ participants = [], operation }) {
  const snapshots = participants.map((participant) => ({
    name: participant.name,
    getState: participant.getState,
    saveState: participant.saveState,
    snapshot: clone(participant.getState()),
  }))

  try {
    const result = await operation()
    return {
      ...result,
      transactionCommitted: true,
      rollbackStatus: result?.rollbackStatus || 'not_required',
      cleanupRequired: result?.cleanupRequired ?? false,
    }
  } catch (error) {
    const rollbackErrors = []
    snapshots.reverse().forEach((item) => {
      try {
        item.saveState(item.snapshot)
      } catch (rollbackError) {
        rollbackErrors.push({ store: item.name, message: rollbackError?.message || String(rollbackError) })
      }
    })
    return {
      success: false,
      executionStatus: 'failed_rolled_back',
      transactionCommitted: false,
      rollbackStatus: rollbackErrors.length ? 'rollback_failed' : 'rolled_back',
      rollbackErrors,
      cleanupRequired: rollbackErrors.length > 0,
      failedStep: error?.failedStep || 'operation',
      errorCode: error?.errorCode || 'transaction_failed',
      error: error?.message || String(error),
    }
  }
}
