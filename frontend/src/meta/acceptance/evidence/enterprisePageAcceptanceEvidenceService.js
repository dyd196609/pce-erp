import { archiveEnterprisePageEvidence, collectEnterprisePageEvidence, createEvidenceCollectionPlan, evaluateCollectedEvidence } from './enterprisePageEvidenceEngine.js'

const runs = new Map()
const envelope = (success, data = null, error = null) => Object.freeze({ success, data, error, meta: Object.freeze({ timestamp: new Date().toISOString(), serviceVersion: 'V1.14.2.8.4.21' }) })

export function createRun(input) {
  try {
    const plan = createEvidenceCollectionPlan(input)
    runs.set(plan.acceptanceRunId, { plan, runtimeContext: input.runtimeContext || {}, collection: null, evaluated: null, archive: null })
    return envelope(true, { acceptanceRunId: plan.acceptanceRunId, plan })
  } catch (error) { return envelope(false, null, { code: 'CREATE_RUN_FAILED', message: error.message }) }
}

export async function collect(acceptanceRunId, runtimeContext) {
  const state = runs.get(acceptanceRunId)
  if (!state) return envelope(false, null, { code: 'RUN_NOT_FOUND', message: acceptanceRunId })
  state.collection = await collectEnterprisePageEvidence(state.plan, runtimeContext || state.runtimeContext)
  return envelope(true, state.collection)
}

export function getEvidence(acceptanceRunId) {
  const state = runs.get(acceptanceRunId)
  return state ? envelope(true, state.collection?.evidence || []) : envelope(false, null, { code: 'RUN_NOT_FOUND', message: acceptanceRunId })
}

export function evaluate(acceptanceRunId) {
  const state = runs.get(acceptanceRunId)
  if (!state?.collection) return envelope(false, null, { code: 'EVIDENCE_NOT_COLLECTED', message: acceptanceRunId })
  state.evaluated = evaluateCollectedEvidence(state.collection)
  return envelope(true, state.evaluated)
}

export async function archive(acceptanceRunId, options) {
  const state = runs.get(acceptanceRunId)
  if (!state?.evaluated) return envelope(false, null, { code: 'RUN_NOT_EVALUATED', message: acceptanceRunId })
  state.archive = await archiveEnterprisePageEvidence(state.evaluated, options)
  return envelope(true, state.archive)
}

export function getReport(acceptanceRunId) {
  const state = runs.get(acceptanceRunId)
  return state ? envelope(true, { plan: state.plan, evaluated: state.evaluated, archive: state.archive }) : envelope(false, null, { code: 'RUN_NOT_FOUND', message: acceptanceRunId })
}

export { envelope as createEvidenceServiceEnvelope }
