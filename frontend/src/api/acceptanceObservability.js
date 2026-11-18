import request from './request.js'

export async function getAcceptanceObservabilityFacts(pageCode) {
  const response = await request({
    method: 'GET',
    url: `/api/workflow/action-permissions/acceptance-observability/${encodeURIComponent(pageCode)}`,
    meta: { module: 'acceptance-observability' },
  })
  const payload = response?.data ?? response ?? {}
  if (response?.success === false || payload?.result !== 'passed') {
    const error = new Error(
      response?.error?.message
      || payload?.error?.message
      || 'Acceptance facts read failed',
    )
    error.code = response?.error?.code || payload?.error?.code || 'ACCEPTANCE_FACTS_READ_FAILED'
    error.httpStatus = response?.factLoadFacts?.httpStatus || 0
    throw error
  }
  return payload.acceptanceFacts
}
