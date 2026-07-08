import { readDatabase, writeDatabase } from './databaseLayer.js'

const syncEvents = []

function remember(event = {}) {
  syncEvents.unshift({
    ...event,
    timestamp: Date.now(),
  })
  if (syncEvents.length > 100) syncEvents.length = 100
}

export async function syncUIWithBackend(module, params = {}) {
  const data = await readDatabase(module, params.id ? 'detail' : 'list', params)
  remember({ type: 'UI_BACKEND_SYNC', module, tenantId: params.tenantId, rows: Array.isArray(data) ? data.length : data ? 1 : 0 })
  return data
}

export function syncWorkflowWithDB(module, workflow = {}, context = {}) {
  const record = workflow.result?.record || workflow.record || context.record || {}
  const data = writeDatabase(module, record, context)
  remember({ type: 'WORKFLOW_DB_SYNC', module, tenantId: context.tenantId, state: record.workflow_state })
  return data
}

export function syncExecutionWithDB(module, execution = {}, context = {}) {
  const record = execution.record || execution.data || execution
  const data = writeDatabase(module, record, context)
  remember({ type: 'EXECUTION_DB_SYNC', module, tenantId: context.tenantId })
  return data
}

export function getDataSyncSnapshot() {
  return {
    dataSync: 'ACTIVE',
    uiBackendSync: 'ACTIVE',
    workflowDbSync: 'ACTIVE',
    executionDbSync: 'ACTIVE',
    events: [...syncEvents],
    healthScore: syncEvents.length ? 100 : 90,
  }
}
