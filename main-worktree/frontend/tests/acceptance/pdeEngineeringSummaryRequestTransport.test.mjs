import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { createStandardApiError, createStandardApiResponse } from '../../src/meta/product/productDelivery.js'
import { assertPceFactLoadFacts, createReadFailedFactLoad, currentPceServerFactContext, rememberPceServerFactContext } from '../../src/meta/runtime/pceFactLoadContract.js'

const requestSource = fs.readFileSync(new URL('../../src/api/request.js', import.meta.url), 'utf8')
const apiSource = fs.readFileSync(new URL('../../src/api/pde.js', import.meta.url), 'utf8')
const productionBody = requestSource.replace(/import[\s\S]*?from\s+['"][^'"]+['"]\r?\n/g, '')
  .replace(/import\.meta\.env\.VITE_API_BASE_URL/g, "''")
  .replace(/export default function request/, 'function request').replace(/export function /g, 'function ')
function transportHarness() {
  const rawCalls = [], transportCalls = []
  let defaults, requestInterceptor, responseSuccess, responseFailure
  const mode = { status: 200, data: { savedFacts: true }, error: null, authChanged: false }
  const instance = async passed => {
    rawCalls.push(passed)
    const config = requestInterceptor({ ...defaults, ...passed })
    transportCalls.push(config)
    if (mode.error) return responseFailure({ ...mode.error, config })
    return responseSuccess({ status: mode.status, data: mode.data, config })
  }
  instance.interceptors = { request: { use: handler => { requestInterceptor = handler } },
    response: { use: (success, failure) => { responseSuccess = success; responseFailure = failure } } }
  const dependencies = { axios: { create: config => { defaults = config; return instance } },
    createStandardApiError, createStandardApiResponse, assertPceFactLoadFacts, createReadFailedFactLoad,
    currentPceServerFactContext, rememberPceServerFactContext, isUsableServerJwt: token => token === 'SIMULATED_FOR_TEST_TOKEN',
    authenticationContextChanged: () => mode.authChanged, getTabAuthEpoch: () => 9, getTabAuthToken: () => 'SIMULATED_FOR_TEST_TOKEN' }
  const request = new Function(...Object.keys(dependencies), `${productionBody}\nreturn request`)(...Object.values(dependencies))
  const between = (start, end) => apiSource.slice(apiSource.indexOf(start), apiSource.indexOf(end, apiSource.indexOf(start) + start.length))
  const api = new Function('request', `return ({${between('  engineeringDrafts(', '  saveEngineeringDraft(')}${between('  engineeringCalculation(', '  executeEngineeringCalculation(')}})`)(request)
  return { request, api, mode, rawCalls, transportCalls, get defaults() { return defaults } }
}

test('production PDE API → production request exit → instance transport preserves 90/60-second overrides', async () => {
  const h = transportHarness()
  await h.api.engineeringDesignCalculationContext(11)
  await h.api.engineeringDesignCalculationContext(11, { includeWorkloadSummary: true })
  await h.api.engineeringCalculation(4)
  await h.api.engineeringDrafts(3)
  assert.deepEqual(h.transportCalls.map(config => config.timeout), [90000, 90000, 60000, 60000])
  assert.deepEqual(h.transportCalls.map(config => config.url), [
    '/api/pde/a1-engineering/calculations/batch-reuse/', '/api/pde/a1-engineering/calculations/batch-reuse/',
    '/api/pde/a1-engineering/calculations/4/', '/api/pde/a1-engineering/calculations/batch-reuse/',
  ])
  for (const config of h.transportCalls) {
    assert.equal(config.method, 'GET')
    assert.equal(config.meta.module, 'pde')
    assert.equal(config.meta.tabAuthEpoch, 9)
    assert.equal(config.withCredentials, true)
    assert.equal(config.headers.Authorization, 'Bearer SIMULATED_FOR_TEST_TOKEN')
  }
})

test('deferred context, absent timeout and explicit undefined preserve the unchanged 15-second default', async () => {
  const h = transportHarness()
  await h.api.engineeringDesignCalculationContext(11, { includeWorkloadSummary: false })
  await h.request({ url: '/api/pde/unchanged-read/', meta: { module: 'pde' } })
  await h.request({ url: '/api/pde/unchanged-read/', timeout: undefined })
  assert.deepEqual(h.transportCalls.map(config => config.timeout), [15000, 15000, 15000])
  assert.ok(h.rawCalls.every(config => !Object.hasOwn(config, 'timeout')))
  assert.deepEqual(h.transportCalls[0].params, { action: 'designCalculationContext', sourceRecordId: 11, includeWorkloadSummary: false })
  assert.equal(h.defaults.timeout, 15000)
})

test('the exit still forwards only its original whitelist plus optional timeout; auth, headers and response envelope remain', async () => {
  const h = transportHarness()
  const headers = { Authorization: 'Bearer SIMULATED_EXPLICIT_AUTH', 'X-Read-Trace': 'SIMULATED_FOR_TEST' }
  const params = { scope: 4 }, data = { readonly: true }, meta = { module: 'pde', trace: 'SIMULATED_FOR_TEST' }
  const result = await h.request({ method: 'GET', url: '/api/pde/read/', params, data, headers,
    meta, responseType: 'json', withCredentials: false, timeout: 60000, unapprovedConfig: 'discarded' })
  const call = h.transportCalls[0]
  assert.equal(call.params, params)
  assert.equal(call.data, data)
  assert.equal(call.headers, headers)
  assert.equal(call.headers.Authorization, 'Bearer SIMULATED_EXPLICIT_AUTH')
  assert.equal(call.meta.trace, meta.trace)
  assert.equal(call.meta.tabAuthEpoch, 9)
  assert.equal(call.responseType, 'json')
  assert.equal(call.withCredentials, false)
  assert.equal(Object.hasOwn(call, 'unapprovedConfig'), false)
  assert.equal(result.success, true)
  assert.deepEqual(result.data, { savedFacts: true })
  assert.equal(result.meta.module, 'pde')
  assert.equal(result.meta.status, 200)
})

test('HTTP permission rejection retains the complete server failure contract and never becomes a zero result', async () => {
  const h = transportHarness()
  const failure = createReadFailedFactLoad({ apiUrl: '/api/pde/read/', httpStatus: 403, errorCode: 'PERMISSION_DENIED',
    errorMessage: '计划查看权限受限', tenantId: 'SIM-TENANT', batchId: 'SIM-BATCH' })
  h.mode.status = 403
  h.mode.data = { factLoadFacts: failure, details: { boundary: 'preserved' } }
  const result = await h.request({ url: '/api/pde/read/', timeout: 90000, meta: { module: 'pde' } })
  assert.equal(result.success, false)
  assert.equal(result.data, null)
  assert.equal(result.factLoadStatus, 'read_failed')
  assert.equal(result.error.code, 'PERMISSION_DENIED')
  assert.equal(result.error.message, '计划查看权限受限')
  assert.deepEqual(result.error.details, { boundary: 'preserved' })
  assert.equal(result.meta.status, 403)
  assert.equal(assertPceFactLoadFacts(result.factLoadFacts).tenantId, 'SIM-TENANT')
  assert.equal(h.transportCalls[0].timeout, 90000)
})

test('network timeout and stale authentication responses preserve existing error semantics', async () => {
  const h = transportHarness()
  h.mode.error = { code: 'ECONNABORTED', message: 'SIMULATED_FOR_TEST timeout' }
  const network = await h.request({ url: '/api/pde/read/', timeout: 60000, meta: { module: 'pde' } })
  assert.equal(network.success, false)
  assert.equal(network.data, null)
  assert.equal(network.factLoadStatus, 'read_failed')
  assert.equal(network.error.code, 'ECONNABORTED')
  assert.equal(network.factLoadFacts.apiUrl, '/api/pde/read/')
  assert.equal(network.factLoadFacts.httpStatus, 0)
  assert.doesNotThrow(() => assertPceFactLoadFacts(network.factLoadFacts))
  h.mode.error = null
  h.mode.authChanged = true
  const changed = await h.request({ url: '/api/pde/read/', timeout: 90000, meta: { module: 'pde' } })
  assert.equal(changed.success, false)
  assert.equal(changed.data, null)
  assert.equal(changed.error.code, 'AUTHENTICATION_CONTEXT_CHANGED')
  assert.equal(changed.meta.source, 'tab-auth-context')
})
