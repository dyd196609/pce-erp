export const SCM_PAGE_PERFORMANCE_DIAGNOSTIC_VERSION = 'V1.14.2.8.4.14'

export const SCM_PAGE_PERFORMANCE_BUDGET = Object.freeze({
  normalPageMs: 1000,
  complexPageMs: 3000,
  complexPageCodes: Object.freeze(['purchase-receive-preview', 'incoming-inspection', 'inventory-balances']),
})

const records = new Map()
const now = () => globalThis.performance?.now?.() ?? Date.now()
const rounded = (value) => Math.max(0, Number(Number(value || 0).toFixed(2)))

export function beginScmPagePerformanceDiagnostic(route, pageCode) {
  const token = `${pageCode}:${Date.now()}:${Math.random().toString(16).slice(2)}`
  records.set(token, {
    token,
    route,
    pageCode,
    startedAt: now(),
    routerDurationMs: 0,
    schemaLoadDurationMs: 0,
    apiDurationMs: null,
    renderDurationMs: null,
    fullScmScanPerformed: false,
    fullSupplyChainCalculationPerformed: false,
  })
  return token
}

export function markScmPagePerformance(token, phase, startedAt) {
  const record = records.get(token)
  if (!record) return null
  const duration = rounded(now() - Number(startedAt || record.startedAt))
  if (phase === 'router') record.routerDurationMs = duration
  if (phase === 'schema') record.schemaLoadDurationMs = duration
  if (phase === 'api') record.apiDurationMs = duration
  if (phase === 'render') record.renderDurationMs = duration
  return { ...record }
}

export function finishScmPagePerformanceDiagnostic(token) {
  const record = records.get(token)
  if (!record) return null
  if (record.renderDurationMs == null) record.renderDurationMs = rounded(now() - record.startedAt)
  record.totalDurationMs = rounded(now() - record.startedAt)
  record.routeLoadTime = record.routerDurationMs
  record.schemaLoadTime = record.schemaLoadDurationMs
  record.apiTime = record.apiDurationMs
  record.renderTime = record.renderDurationMs
  record.totalTime = record.totalDurationMs
  const complex = SCM_PAGE_PERFORMANCE_BUDGET.complexPageCodes.includes(record.pageCode)
  record.pageComplexity = complex ? 'complex' : 'normal'
  record.budgetMs = complex ? SCM_PAGE_PERFORMANCE_BUDGET.complexPageMs : SCM_PAGE_PERFORMANCE_BUDGET.normalPageMs
  record.result = record.totalDurationMs <= record.budgetMs ? 'PASS' : 'FAIL'
  if (typeof window !== 'undefined') {
    window.__PCE_SCM_PAGE_PERFORMANCE__ = { ...record }
  }
  if (typeof document !== 'undefined') {
    const root = document.documentElement
    root.dataset.scmRouteLoadTime = String(record.routeLoadTime)
    root.dataset.scmSchemaLoadTime = String(record.schemaLoadTime)
    root.dataset.scmApiTime = String(record.apiTime)
    root.dataset.scmRenderTime = String(record.renderTime)
    root.dataset.scmTotalTime = String(record.totalTime)
    root.dataset.scmPerformanceResult = record.result
  }
  return { ...record }
}

export function listScmPagePerformanceDiagnostics() {
  return [...records.values()].map((record) => ({ ...record }))
}
