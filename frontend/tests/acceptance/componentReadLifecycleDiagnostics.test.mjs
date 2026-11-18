import assert from 'node:assert/strict'
import test from 'node:test'
import { createComponentReadLifecycle } from '../../src/meta/runtime/componentReadLifecycle.js'

// Synthetic transport observations only: no HTTP, browser or database.
test('equivalent query ordering yields transport phases without matching another generation or an earlier read', async () => {
  let now = 50, records = []
  const current = { name: 'http://localhost/api/route/?generation=4&productionPlanId=1', startTime: 60,
    fetchStart: 62, domainLookupStart: 63, domainLookupEnd: 65, connectStart: 65, connectEnd: 69,
    requestStart: 70, responseStart: 110, responseEnd: 125, duration: 65,
    encodedBodySize: 64, decodedBodySize: 128, transferSize: 300,
    serverTiming: [{ name: 'native', duration: 35, description: 'must not be copied' },
      { name: 'sql', duration: 12 }, { name: 'render', duration: 2 }, { name: 'responseBytes', duration: 64 },
      { name: 'queryCount', duration: 15 }, { name: 'unapproved', duration: 8 }, { name: 'sql', duration: NaN }] }
  const lifecycle = createComponentReadLifecycle({ clock: () => now, resources: () => [
    { ...current, startTime: 40, requestStart: 400 }, current,
    { ...current, name: 'http://localhost/api/route/?generation=5&productionPlanId=1', requestStart: 500 },
  ], changed: rows => { records = rows } })
  const value = { data: { factSource: 'server' } }
  const result = await lifecycle.run({ purpose: 'route', url: '/api/route/?productionPlanId=1&generation=4',
    read: async () => { now = 130; return value } })
  assert.equal(result, value, 'Diagnostics never replace the original result')
  assert.equal(records[0].receiveAndParseMs, 80)
  assert.equal(records[0].fetchStart, 62)
  assert.equal(records[0].domainLookupStart, 63)
  assert.equal(records[0].domainLookupEnd, 65)
  assert.equal(records[0].connectStart, 65)
  assert.equal(records[0].connectEnd, 69)
  assert.equal(records[0].requestStart, 70)
  assert.equal(records[0].networkWaitMs, 8)
  assert.equal(records[0].ttfbMs, 40)
  assert.equal(records[0].transferMs, 15)
  assert.equal(records[0].encodedBodySize, 64)
  assert.equal(records[0].decodedBodySize, 128)
  assert.equal(records[0].transferSize, 300)
  assert.deepEqual(records[0].serverTiming, [{ name: 'native', duration: 35 }, { name: 'sql', duration: 12 },
    { name: 'render', duration: 2 }, { name: 'responseBytes', duration: 64 }, { name: 'queryCount', duration: 15 }])
  await lifecycle.run({ purpose: 'route', url: '/api/route/?productionPlanId=1&generation=6', read: async () => value })
  for (const key of ['fetchStart', 'requestStart', 'networkWaitMs', 'ttfbMs', 'transferMs', 'encodedBodySize', 'serverTiming']) {
    assert.equal(records[1][key], null, `${key} cannot come from another generation`)
  }
})

test('missing resource and failed reads keep transport phases unknown and never supply success facts', async () => {
  let now = 10, records = []
  const lifecycle = createComponentReadLifecycle({ clock: () => now, resources: () => [], changed: rows => { records = rows } })
  const failure = new Error('synthetic timeout')
  await assert.rejects(lifecycle.run({ purpose: 'route', url: '/api/route/', read: async () => { now = 25; throw failure } }), failure)
  assert.equal(records[0].outcome, 'failed')
  assert.equal(records[0].receiveAndParseMs, 15)
  for (const key of ['fetchStart', 'requestStart', 'domainLookupStart', 'domainLookupEnd', 'connectStart', 'connectEnd',
    'networkWaitMs', 'ttfbMs', 'transferMs', 'serverTiming', 'serverReadDiagnostics']) assert.equal(records[0][key], null)
  assert.equal(records[0].diagnosticOnly, true)
  assert.equal('passed' in records[0], false)
})

test('server read measurements copy only the diagnostic contract and approved numeric fields', async () => {
  let records = []
  const lifecycle = createComponentReadLifecycle({ resources: () => [], changed: rows => { records = rows } })
  const diagnostics = { contractVersion: 'PCE-OPERATION-READ-DIAGNOSTICS-V1', diagnosticOnly: true,
    requestId: '0123456789abcdef0123456789abcdef', purpose: 'route', startedAtEpochMs: 1000, finishedAtEpochMs: 1090,
    nativeMs: 90, queryCount: 12, duplicateExactQueryCount: 2, sqlMs: 20, maxSqlMs: 4,
    lockErrorCount: 0, concurrentReadsAtEntry: 1, maxConcurrentReads: 2,
    spans: { routeAggregate: { calls: 1, ms: 80, sql: 'must not be copied' },
      allocationValidation: { calls: 10, ms: 30 }, unrelated: { calls: 1, ms: 6 } },
    sql: 'must not be copied', token: 'must not be copied', passed: true, businessWriteCount: 9 }
  const value = { data: { readDiagnostics: diagnostics, factSource: 'server', passed: false } }
  assert.equal(await lifecycle.run({ purpose: 'route', url: '/api/route/', read: async () => value }), value)
  const recorded = records[0].serverReadDiagnostics
  assert.deepEqual(recorded, { contractVersion: diagnostics.contractVersion, diagnosticOnly: true,
    requestId: diagnostics.requestId, purpose: 'route', startedAtEpochMs: 1000, finishedAtEpochMs: 1090,
    nativeMs: 90, queryCount: 12, duplicateExactQueryCount: 2, sqlMs: 20, maxSqlMs: 4,
    lockErrorCount: 0, concurrentReadsAtEntry: 1, maxConcurrentReads: 2,
    spans: { routeAggregate: { calls: 1, ms: 80 }, allocationValidation: { calls: 10, ms: 30 } } })
  diagnostics.spans.routeAggregate.ms = 999
  assert.equal(recorded.spans.routeAggregate.ms, 80, 'Stored measurements do not alias response objects')
  assert.equal(value.data.passed, false, 'Measured diagnostics do not alter fact acceptance')
  await lifecycle.run({ purpose: 'route', url: '/api/route/', read: async () => ({ data: { readDiagnostics: {
    ...diagnostics, purpose: 'unapproved', queryCount: '12', nativeMs: Infinity,
    requestId: 'not a random hexadecimal request identity', spans: { stepRead: { calls: 1.2, ms: 3 } },
  } } }) })
  assert.equal('purpose' in records[1].serverReadDiagnostics, false)
  assert.equal('requestId' in records[1].serverReadDiagnostics, false)
  assert.equal('queryCount' in records[1].serverReadDiagnostics, false)
  assert.equal('nativeMs' in records[1].serverReadDiagnostics, false)
  assert.deepEqual(records[1].serverReadDiagnostics.spans, {})
  await lifecycle.run({ purpose: 'route', url: '/api/route/', read: async () => ({ data: { readDiagnostics: {
    ...diagnostics, contractVersion: 'WRONG',
  } } }) })
  assert.equal(records[2].serverReadDiagnostics, null)
})

function observerProbe() {
  const instances = []
  class FakePerformanceObserver {
    constructor(callback) { this.callback = callback; this.disconnectCount = 0; instances.push(this) }
    observe(options) { this.options = options }
    disconnect() { this.disconnectCount++ }
    emit(entries) { this.callback({ getEntries: () => entries }) }
  }
  return { instances, FakePerformanceObserver }
}
function observedResource(url, startTime = 12) {
  return { name: `http://localhost${url}`, startTime, fetchStart: startTime + 1, requestStart: startTime + 3,
    responseStart: startTime + 10, responseEnd: startTime + 12, duration: 12,
    encodedBodySize: 64, decodedBodySize: 128, transferSize: 300,
    serverTiming: [{ name: 'native', duration: 6, description: 'must not be retained' }],
    headers: { authorization: 'must not be retained' } }
}

test('instance observer supplies late current resource measurements without the document resource buffer', async () => {
  const probe = observerProbe(), notifications = []
  let now = 10, calls = 0
  const lifecycle = createComponentReadLifecycle({ clock: () => now, resources: () => [],
    PerformanceObserverClass: probe.FakePerformanceObserver, changed: rows => notifications.push(rows) })
  const value = { data: { factSource: 'server', passed: false } }
  assert.equal(await lifecycle.run({ purpose: 'route', url: '/api/route/?generation=1',
    read: async () => { calls++; now = 30; return value } }), value)
  assert.deepEqual(probe.instances[0].options, { type: 'resource' }, 'Do not replay or resize a global buffer')
  assert.equal(notifications.at(-1)[0].ttfbMs, null)
  const before = notifications.length
  probe.instances[0].emit([observedResource('/api/route/?generation=1')])
  const record = notifications.at(-1)[0]
  assert.equal(notifications.length, before + 1)
  assert.equal(record.requestStart, 15)
  assert.equal(record.networkWaitMs, 2)
  assert.equal(record.ttfbMs, 7)
  assert.equal(record.transferMs, 2)
  assert.equal(record.receiveAndParseMs, 20, 'Late measurements do not move Promise completion')
  assert.equal(record.outcome, 'received')
  assert.deepEqual(record.serverTiming, [{ name: 'native', duration: 6 }])
  assert.equal(value.data.passed, false)
  assert.equal(calls, 1, 'An observation never starts another GET')
  assert.doesNotMatch(JSON.stringify(record), /authorization|must not be retained/)
  lifecycle.dispose()
})

test('observer entries received while pending remain diagnostic-only and are collected at ordinary completion', async () => {
  const probe = observerProbe()
  let now = 10, records = [], release
  const lifecycle = createComponentReadLifecycle({ clock: () => now, resources: () => [],
    PerformanceObserverClass: probe.FakePerformanceObserver, changed: rows => { records = rows } })
  const value = { data: { factSource: 'server' } }
  const pending = lifecycle.run({ purpose: 'route', url: '/api/route/',
    read: () => new Promise(resolve => { release = resolve }) })
  await Promise.resolve()
  probe.instances[0].emit([observedResource('/api/route/')])
  assert.equal(records[0].outcome, 'pending')
  assert.equal(records[0].requestStart, null)
  assert.equal(records[0].promiseEndedAt, null)
  now = 30
  release(value)
  assert.equal(await pending, value)
  assert.equal(records[0].requestStart, 15)
  assert.equal(records[0].outcome, 'received')
  lifecycle.dispose()
})

test('late observer entries respect URL parameters and read intervals; overlapping identical reads remain unknown', async () => {
  const probe = observerProbe()
  let now = 10, records = []
  const lifecycle = createComponentReadLifecycle({ clock: () => now, resources: () => [],
    PerformanceObserverClass: probe.FakePerformanceObserver, changed: rows => { records = rows } })
  const read = async () => { now += 20; return { data: {} } }
  await lifecycle.run({ purpose: 'route', url: '/api/route/?generation=1', read })
  probe.instances[0].emit([observedResource('/api/route/?generation=2'), observedResource('/api/route/?generation=1', 5)])
  assert.equal(records[0].requestStart, null, 'Different generation and earlier resources cannot fill this record')
  now = 40
  await lifecycle.run({ purpose: 'route', url: '/api/route/?generation=1', read })
  probe.instances[0].emit([observedResource('/api/route/?generation=1', 45)])
  assert.equal(records[0].requestStart, null, 'The new read starts after the old Promise ended')
  assert.equal(records[1].requestStart, 48)
  probe.instances[0].emit([observedResource('/api/route/?generation=1', 15)])
  assert.equal(records[0].requestStart, 18)
  assert.equal(records[1].requestStart, 48, 'A late old entry cannot overwrite a new read')
  lifecycle.dispose()

  const overlappingProbe = observerProbe(), gates = []
  now = 100
  const overlapping = createComponentReadLifecycle({ clock: () => now, resources: () => [],
    PerformanceObserverClass: overlappingProbe.FakePerformanceObserver, changed: rows => { records = rows } })
  const first = overlapping.run({ purpose: 'route', params: { generation: 1 }, url: '/api/route/',
    read: () => new Promise(resolve => gates.push(resolve)) })
  now = 101
  const second = overlapping.run({ purpose: 'route', params: { generation: 2 }, url: '/api/route/',
    read: () => new Promise(resolve => gates.push(resolve)) })
  await Promise.resolve()
  now = 130
  gates.forEach(resolve => resolve({ data: {} }))
  await Promise.all([first, second])
  overlappingProbe.instances[0].emit([observedResource('/api/route/', 105)])
  assert.deepEqual(records.map(row => row.requestStart), [null, null], 'Ambiguous transport ownership stays unknown')
  overlapping.dispose()
})

test('observer ownership is per instance, bounded, and disposal disconnects without publishing queued entries', async () => {
  const probe = observerProbe(), changesA = [], changesB = []
  let now = 10
  const options = { clock: () => now, resources: () => [], PerformanceObserverClass: probe.FakePerformanceObserver }
  const first = createComponentReadLifecycle({ ...options, changed: rows => changesA.push(rows) })
  const second = createComponentReadLifecycle({ ...options, changed: rows => changesB.push(rows) })
  const read = async () => { now += 20; return { data: {} } }
  await first.run({ purpose: 'route', url: '/api/first/', read })
  now = 10
  await second.run({ purpose: 'route', url: '/api/second/', read })
  first.dispose()
  const count = changesA.length
  probe.instances[0].emit([observedResource('/api/first/')])
  probe.instances[1].emit([observedResource('/api/second/')])
  assert.equal(changesA.length, count)
  assert.equal(probe.instances[0].disconnectCount, 1)
  assert.equal(probe.instances[1].disconnectCount, 0)
  assert.equal(changesB.at(-1)[0].requestStart, 15)
  for (let generation = 1; generation <= 13; generation++) {
    now += 10
    await second.run({ purpose: 'route', url: `/api/second/?generation=${generation}`, read })
    probe.instances[1].emit([observedResource(`/api/second/?generation=${generation}`, now - 15)])
  }
  assert.equal(changesB.at(-1).length, 12)
  assert.equal(changesB.at(-1).at(-1).purposeGetCount, 14)
  second.dispose()
  assert.equal(probe.instances[1].disconnectCount, 1)
})
