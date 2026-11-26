function queryText(value) {
  return String(Array.isArray(value) ? value[0] : value || '').trim()
}

export function resolveEnterpriseListCanaryQuery(query = {}) {
  const canaryBatchId = queryText(query.canaryBatchId)
  const scenarioCode = queryText(query.scenarioCode)
  return Object.freeze({
    isCanaryMode: Boolean(canaryBatchId && scenarioCode),
    canaryBatchId,
    scenarioCode,
  })
}
