import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  executeOrganizationWriteRequest,
  resetOrganizationRequestIdentitiesForTests,
} from '../../src/api/organizationRequestIdentity.js'


const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const apiSource = fs.readFileSync(path.join(root, 'src/api/accessControl.js'), 'utf8')
const helperSource = fs.readFileSync(
  path.join(root, 'src/api/organizationRequestIdentity.js'), 'utf8',
)
const dialogSource = fs.readFileSync(
  path.join(root, 'src/meta/components/OrganizationOperatingAdminDialog.vue'), 'utf8',
)
const modelViewSource = fs.readFileSync(
  path.join(root, 'src/meta/components/EnterpriseOrganizationModelView.vue'), 'utf8',
)

resetOrganizationRequestIdentitiesForTests()

const action = 'SAVE_RESPONSIBILITY'
const payload = {
  code: 'GENERIC_TEST_RESPONSIBILITY',
  name: '通用隔离测试责任',
  status: 'DRAFT',
  reason: '前端请求身份隔离测试',
}

const firstKeys = []
await executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    firstKeys.push(key)
    return { success: true }
  },
})
assert.equal(firstKeys.length, 1)
assert.ok(firstKeys[0])

let unknownKey = ''
await assert.rejects(() => executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    unknownKey = key
    throw new Error('simulated network timeout before response')
  },
}))
let recoveryKey = ''
await executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    recoveryKey = key
    return { success: true, data: { idempotentReplay: true } }
  },
})
assert.equal(recoveryKey, unknownKey, 'unknown-result retry must reuse the same key')

resetOrganizationRequestIdentitiesForTests()
const concurrentKeys = []
let release
const blocked = new Promise((resolve) => { release = resolve })
const firstConcurrent = executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    concurrentKeys.push(key)
    await blocked
    return { success: true }
  },
})
const secondConcurrent = executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    concurrentKeys.push(key)
    return { success: true, data: { idempotentReplay: true } }
  },
})
release()
await Promise.all([firstConcurrent, secondConcurrent])
assert.equal(concurrentKeys.length, 2)
assert.equal(concurrentKeys[0], concurrentKeys[1], 'same in-flight command uses one key')

resetOrganizationRequestIdentitiesForTests()
let conflictKey = ''
const conflict = Object.assign(new Error('payload conflict'), {
  response: { status: 409, data: { error: { code: 'IDEMPOTENCY_PAYLOAD_CONFLICT' } } },
})
await assert.rejects(() => executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    conflictKey = key
    throw conflict
  },
}), (error) => error.response.status === 409)
let nextBusinessKey = ''
await executeOrganizationWriteRequest({
  action,
  payload,
  send: async (key) => {
    nextBusinessKey = key
    return { success: true }
  },
})
assert.notEqual(nextBusinessKey, conflictKey, 'definitive 409 ends the prior operation')

let nonTargetKey = 'not-called'
await executeOrganizationWriteRequest({
  action: 'SAVE_POSITION',
  payload,
  send: async (key) => {
    nonTargetKey = key
    return { success: true }
  },
})
assert.equal(nonTargetKey, null, 'unrelated organization actions preserve their contract')

assert.match(apiSource, /'Idempotency-Key': requestIdentity/)
assert.match(apiSource, /executeOrganizationWriteRequest/)
assert.doesNotMatch(apiSource, /WriteRequestId|AuditId|ExternalIdentityId/)
assert.doesNotMatch(helperSource, /ENTERPRISE_WORKFLOW_CATALOG_MAINTAINER|Position ID 38|SO202609180003|CALC-3/)
assert.match(dialogSource, /请求冲突（\$\{responseError\.code\}）：/)
assert.match(modelViewSource, /请求冲突（\$\{responseError\.code\}）：/)

console.log(JSON.stringify({
  suite: 'organizationOperatingRequestIdentity',
  status: 'PASS',
  checks: 9,
  idempotencyHeader: true,
  unknownResultRetryReusesKey: true,
  concurrentDuplicateUsesOneKey: true,
  conflictIsVisible: true,
  productionSampleHardcoding: false,
}, null, 2))
