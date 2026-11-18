import assert from 'node:assert/strict'

import {
  MATERIAL_RUNTIME_STATUS,
  createMaterialMasterRuntimeEngine,
} from './materialMasterRuntimeEngine.js'

const success = (rows) => ({
  success: true,
  data: {
    success: true,
    data: { factLoadFacts: { factLoadStatus: 'success' }, rows },
  },
  meta: { status: 200 },
})

const enterprise = (principalId = 'user-1') => ({
  authenticated: true,
  mode: 'enterprise',
  tenantId: 'formal',
  principalId,
})

let calls = 0
let engine = createMaterialMasterRuntimeEngine({ fetchFacts: async () => { calls += 1; return success([]) } })

assert.deepEqual(await engine.load({ context: { authenticated: false, mode: 'enterprise' } }), [])
assert.equal(calls, 0, 'unauthenticated startup must not read enterprise facts')
assert.equal(engine.state().status, MATERIAL_RUNTIME_STATUS.AUTH_REQUIRED)

await engine.load({ context: enterprise() })
assert.equal(calls, 1, 'post-login context must load')
assert.equal(engine.state().status, MATERIAL_RUNTIME_STATUS.LOADED)
await engine.load({ context: enterprise() })
assert.equal(calls, 1, 'a valid empty result is cached')
await engine.load({ context: enterprise('user-2') })
assert.equal(calls, 2, 'login identity switch must reload')

engine = createMaterialMasterRuntimeEngine({ fetchFacts: async () => { calls += 1; return success([{ id: 1, code: 'M-1', name: '板材' }]) } })
const beforeDemoCalls = calls
assert.deepEqual(await engine.load({ context: { authenticated: true, mode: 'demo', principalId: 'user-1' } }), [])
assert.equal(calls, beforeDemoCalls, 'demo context must remain isolated from enterprise API')
const enterpriseRows = await engine.load({ context: enterprise() })
assert.equal(enterpriseRows[0].materialCode, 'M-1')
assert.equal(enterpriseRows[0].materialSourceTrace.source, 'MaterialMaster')

for (const [httpStatus, expected] of [
  [401, MATERIAL_RUNTIME_STATUS.AUTH_REQUIRED],
  [403, MATERIAL_RUNTIME_STATUS.PERMISSION_DENIED],
  [500, MATERIAL_RUNTIME_STATUS.SERVER_ERROR],
]) {
  const failed = createMaterialMasterRuntimeEngine({
    fetchFacts: async () => ({ success: false, error: { message: `HTTP ${httpStatus}` }, meta: { status: httpStatus } }),
  })
  await assert.rejects(
    failed.load({ context: enterprise() }),
    (error) => error.code === expected,
  )
}

const network = createMaterialMasterRuntimeEngine({ fetchFacts: async () => { throw new Error('offline') } })
await assert.rejects(network.load({ context: enterprise() }), (error) => error.code === MATERIAL_RUNTIME_STATUS.NETWORK_ERROR)

const malformed = createMaterialMasterRuntimeEngine({ fetchFacts: async () => ({ success: true, data: { rows: {} } }) })
await assert.rejects(malformed.load({ context: enterprise() }), (error) => error.code === MATERIAL_RUNTIME_STATUS.DATA_ERROR)

const formalRows = Array.from({ length: 270 }, (_, index) => ({
  id: index + 1,
  materialCode: `M-${String(index + 1).padStart(3, '0')}`,
  materialName: `正式物料${index + 1}`,
  unit: '件',
}))
engine = createMaterialMasterRuntimeEngine({ fetchFacts: async () => success(formalRows) })
const parsed = await engine.load({ context: enterprise() })
assert.equal(parsed.length, 270)
assert.equal(parsed[269].code, 'M-270')
assert.equal(parsed[269].name, '正式物料270')

let releaseDuplicate
let duplicateCalls = 0
engine = createMaterialMasterRuntimeEngine({
  fetchFacts: () => {
    duplicateCalls += 1
    return new Promise((resolve) => { releaseDuplicate = () => resolve(success(formalRows.slice(0, 1))) })
  },
})
const duplicateA = engine.load({ context: enterprise() })
const duplicateB = engine.load({ context: enterprise() })
assert.equal(duplicateCalls, 0)
await Promise.resolve()
assert.equal(duplicateCalls, 1, 'duplicate preload must share one request')
releaseDuplicate()
assert.deepEqual(await duplicateA, await duplicateB)

const releases = []
engine = createMaterialMasterRuntimeEngine({
  fetchFacts: () => new Promise((resolve) => releases.push(resolve)),
})
const stale = engine.load({ context: enterprise('old-user') })
await Promise.resolve()
const current = engine.load({ context: enterprise('new-user') })
await Promise.resolve()
releases[1](success([{ id: 2, code: 'NEW', name: '新用户物料' }]))
assert.equal((await current)[0].code, 'NEW')
releases[0](success([{ id: 1, code: 'OLD', name: '旧用户物料' }]))
assert.deepEqual(await stale, [], 'stale response must not overwrite the current identity')
assert.equal(engine.models()[0].code, 'NEW')

console.log('materialMasterRuntimeEngine.test: PASS (12 lifecycle/error/race scenarios)')
