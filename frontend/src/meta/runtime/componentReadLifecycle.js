// Instance-local pending reads and bounded transport diagnostics, never a facts cache.
export function createComponentReadLifecycle({ context = () => '', changed = () => {},
  clock = () => globalThis.performance?.now?.() ?? null,
  resources = () => globalThis.performance?.getEntriesByType?.('resource') || [],
  PerformanceObserverClass = globalThis.PerformanceObserver, limit = 12 } = {}) {
  const pending = new Map()
  const recordLimit = Number.isInteger(limit) && limit > 0 ? limit : 12
  const observationLimit = Math.min(recordLimit, 12)
  let records = []
  let observedResources = []
  let observer = null
  let sequence = 0
  let disposed = false
  const purposeCounts = new Map()
  const canonical = value => JSON.stringify(value, Object.keys(value || {}).sort())
  const elapsed = (start, end) => Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, end - start) : null
  const timingNames = new Set(['total', 'native', 'sql', 'queryCount', 'responseBytes', 'source', 'freeze', 'budget', 'aggregate', 'serialize', 'render'])
  const spanNames = ['routeAggregate', 'routeWorkloads', 'stepRead', 'preparationRead', 'allocationValidation',
    'budgetRead', 'requirementValidation', 'generationContext']
  const diagnosticNumbers = ['startedAtEpochMs', 'finishedAtEpochMs', 'nativeMs', 'queryCount',
    'duplicateExactQueryCount', 'sqlMs', 'maxSqlMs', 'lockErrorCount', 'concurrentReadsAtEntry', 'maxConcurrentReads']
  const nonnegative = value => Number.isFinite(value) && value >= 0
  function safeServerReadDiagnostics(value) {
    if (value?.contractVersion !== 'PCE-OPERATION-READ-DIAGNOSTICS-V1' || value.diagnosticOnly !== true) return null
    const result = { contractVersion: value.contractVersion, diagnosticOnly: true }
    if (typeof value.requestId === 'string' && /^[a-f\d]{16,64}$/i.test(value.requestId)) result.requestId = value.requestId
    if (['route', 'detail', 'catalog'].includes(value.purpose)) result.purpose = value.purpose
    for (const key of diagnosticNumbers) if (nonnegative(value[key])) result[key] = value[key]
    if (value.spans && typeof value.spans === 'object' && !Array.isArray(value.spans)) {
      result.spans = {}
      for (const key of spanNames) {
        const span = value.spans[key]
        if (span && Number.isInteger(span.calls) && span.calls >= 0 && nonnegative(span.ms)) {
          result.spans[key] = { calls: span.calls, ms: span.ms }
        }
      }
    }
    return result
  }
  const resourceUrl = value => {
    try {
      const parsed = new URL(value, globalThis.location?.origin || 'http://localhost')
      parsed.hash = ''
      parsed.searchParams.sort()
      return parsed.href
    } catch { return null }
  }
  const publish = () => { if (!disposed) changed(records.map(row => ({ ...row }))) }
  function identity(purpose, params = {}) { return `${String(context())}|${purpose}|${canonical(params)}` }
  const timingFields = ['startTime', 'fetchStart', 'requestStart', 'domainLookupStart', 'domainLookupEnd',
    'connectStart', 'connectEnd', 'responseStart', 'responseEnd', 'duration',
    'encodedBodySize', 'decodedBodySize', 'transferSize']
  function publicResource(entry) {
    const result = { name: resourceUrl(entry.name) }
    for (const key of timingFields) result[key] = Number.isFinite(entry[key]) ? entry[key] : null
    result.serverTiming = Array.from(entry.serverTiming || []).filter(row => timingNames.has(row.name)
      && Number.isFinite(row.duration) && row.duration >= 0).map(row => ({ name: row.name, duration: row.duration }))
    return result
  }
  function matchesResource(record, entry) {
    return resourceUrl(record.url) !== null && resourceUrl(record.url) === resourceUrl(entry.name)
      && Number.isFinite(record.startedAt) && Number.isFinite(entry.startTime) && entry.startTime >= record.startedAt
      && (!Number.isFinite(record.promiseEndedAt) || entry.startTime <= record.promiseEndedAt)
  }
  function resourceTiming(record) {
    const unique = new Map()
    for (const row of [...resources(), ...observedResources]) {
      if (matchesResource(record, row) && records.filter(owner => matchesResource(owner, row)).length === 1) {
        unique.set(JSON.stringify([resourceUrl(row.name), row.startTime, row.responseEnd]), row)
      }
    }
    // Ambiguous overlapping identical URLs remain unknown; timing is never a
    // reason to attribute another generation's response to this read.
    const match = unique.size === 1 ? unique.values().next().value : null
    const numeric = key => match && Number.isFinite(match[key]) ? match[key] : null
    return { encodedBodySize: numeric('encodedBodySize'), decodedBodySize: numeric('decodedBodySize'),
      transferSize: numeric('transferSize'), resourceStartTime: numeric('startTime'),
      fetchStart: numeric('fetchStart'), requestStart: numeric('requestStart'),
      domainLookupStart: numeric('domainLookupStart'), domainLookupEnd: numeric('domainLookupEnd'),
      connectStart: numeric('connectStart'), connectEnd: numeric('connectEnd'),
      responseStart: numeric('responseStart'), responseEnd: numeric('responseEnd'), resourceDuration: numeric('duration'),
      networkWaitMs: elapsed(numeric('fetchStart'), numeric('requestStart')),
      ttfbMs: elapsed(numeric('requestStart'), numeric('responseStart')),
      transferMs: elapsed(numeric('responseStart'), numeric('responseEnd')),
      serverTiming: !match ? null : Array.from(match.serverTiming || []).filter(row => timingNames.has(row.name)
        && Number.isFinite(row.duration) && row.duration >= 0).map(row => ({ name: row.name, duration: row.duration })) }
  }
  function pendingRead(purpose, params = {}) { return pending.get(identity(purpose, params)) || null }
  function run({ purpose, url, params = {}, read }) {
    if (disposed) return Promise.reject(new Error('读取组件已经卸载。'))
    const key = identity(purpose, params)
    if (pending.has(key)) return pending.get(key)
    const startedAt = clock()
    purposeCounts.set(purpose, (purposeCounts.get(purpose) || 0) + 1)
    const record = { sequence: ++sequence, purpose, url, diagnosticOnly: true,
      actualGetCount: sequence, purposeGetCount: purposeCounts.get(purpose),
      measurement: 'PROMISE_RECEIVE_AND_PARSE', startedAt, promiseEndedAt: null,
      receiveAndParseMs: null, validationMs: null, vueCommitMs: null, outcome: 'pending',
      encodedBodySize: null, decodedBodySize: null, transferSize: null,
      resourceStartTime: null, fetchStart: null, requestStart: null, domainLookupStart: null, domainLookupEnd: null,
      connectStart: null, connectEnd: null, responseStart: null, responseEnd: null, resourceDuration: null,
      networkWaitMs: null, ttfbMs: null, transferMs: null, serverTiming: null, serverReadDiagnostics: null }
    records = [...(recordLimit > 1 ? records.slice(-(recordLimit - 1)) : []), record]
    // Install the pending owner before invoking the actual GET.
    const promise = Promise.resolve().then(read).then(result => {
      record.outcome = 'received'
      record.serverReadDiagnostics = safeServerReadDiagnostics(result?.data?.readDiagnostics)
      return result
    }, error => { record.outcome = 'failed'; throw error }).finally(() => {
      record.promiseEndedAt = clock()
      record.receiveAndParseMs = elapsed(startedAt, record.promiseEndedAt)
      Object.assign(record, resourceTiming(record))
      if (pending.get(key) === promise) pending.delete(key)
      publish()
    })
    pending.set(key, promise)
    Object.defineProperty(promise, 'readDiagnosticSequence', { value: record.sequence })
    publish()
    return promise
  }
  function stage(promise, name, startedAt, endedAt = clock()) {
    if (!['validationMs', 'vueCommitMs'].includes(name)) throw new Error('不支持的读取阶段。')
    const record = records.find(row => row.sequence === promise?.readDiagnosticSequence)
    if (record) { record[name] = elapsed(startedAt, endedAt); publish() }
  }
  if (typeof PerformanceObserverClass === 'function') {
    try {
      observer = new PerformanceObserverClass(list => {
        if (disposed) return
        let changedCompletedRecord = false
        for (const entry of list.getEntries()) {
          if (!records.some(record => matchesResource(record, entry))) continue
          const value = publicResource(entry)
          observedResources = [...observedResources.slice(-(observationLimit - 1)), value]
            .slice(-observationLimit)
          for (const record of records) {
            if (Number.isFinite(record.promiseEndedAt) && matchesResource(record, value)) {
              Object.assign(record, resourceTiming(record))
              changedCompletedRecord = true
            }
          }
        }
        if (changedCompletedRecord) publish()
      })
      // Observe new resources even when the document's old resource buffer is
      // full. Ownership is local: do not resize or clear the global timeline.
      observer.observe({ type: 'resource' })
    } catch {
      observer?.disconnect?.()
      observer = null
    }
  }
  return { identity, pending: pendingRead, run, stage, clock,
    dispose() {
      disposed = true
      observer?.disconnect?.()
      pending.clear()
      records = []
      observedResources = []
      purposeCounts.clear()
    } }
}

export function componentReadUrl(path, params = {}) {
  const query = new URLSearchParams(Object.entries(params).map(([key, value]) => [key, String(value)]))
  return query.size ? `${path}?${query}` : path
}
