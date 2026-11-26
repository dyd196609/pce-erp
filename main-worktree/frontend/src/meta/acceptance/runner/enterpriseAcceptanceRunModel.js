export const ENTERPRISE_ACCEPTANCE_RUN_MODEL_VERSION = 'V1.14.2.8.4.22'
export const ENTERPRISE_ACCEPTANCE_RUN_STATUSES = Object.freeze(['CREATED','RUNNING','COMPLETED','FAILED','ARCHIVED'])

const transitions = Object.freeze({ CREATED:['RUNNING','FAILED'], RUNNING:['COMPLETED','FAILED'], COMPLETED:['ARCHIVED','FAILED'], FAILED:[], ARCHIVED:[] })

export function createEnterpriseAcceptanceRunModel(input = {}) {
  const now = new Date().toISOString()
  return {
    runId: String(input.runId || `PAGE-ACCEPTANCE-${Date.now()}`),
    pageCode: '', pageUrl: String(input.pageUrl || ''), templateCode: '', mode: input.mode || 'production',
    status: 'CREATED', startedAt: now, completedAt: '', collectorCount: 0, evidenceCount: 0, result: 'UNKNOWN',
    readonly: input.readonly === true, scenarioCode: String(input.scenarioCode || ''), canaryBatchId: String(input.canaryBatchId || ''),
    moduleCode: String(input.moduleCode || ''), page: null, template: null, plan: null, collection: null, evaluation: null,
    report: null, archiveResult: null, error: null,
  }
}

export function transitionEnterpriseAcceptanceRun(run, nextStatus) {
  if (!ENTERPRISE_ACCEPTANCE_RUN_STATUSES.includes(nextStatus) || !transitions[run.status]?.includes(nextStatus)) throw new Error(`INVALID_RUN_TRANSITION:${run.status}->${nextStatus}`)
  run.status = nextStatus
  if (['COMPLETED','FAILED','ARCHIVED'].includes(nextStatus)) run.completedAt = new Date().toISOString()
  return run
}
