import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.2'
const apiBase = (
  process.env.PCE_V552_API_BASE_URL || 'http://127.0.0.1:8042'
).replace(/\/$/, '')
const resultRoot = path.join(
  process.cwd(),
  'test-results',
  'pce-business-action-permission-v552',
)

const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
async function actorSession(actor) {
  const response = await fetch(
    `${apiBase}/api/workflow/action-permissions/canary-session`
      + `?actor=${encodeURIComponent(actor)}`,
  )
  assert(response.ok, `Actor session failed: ${actor}`)
  const cookie = String(response.headers.get('set-cookie') || '').split(';')[0]
  assert(cookie.startsWith('pce_v552_actor='), `Actor cookie missing: ${actor}`)
  return cookie
}
async function api(cookie, url, options = {}) {
  const response = await fetch(`${apiBase}${url}`, {
    ...options,
    headers: {
      Cookie: cookie,
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
  })
  return {
    status: response.status,
    payload: await response.json(),
  }
}
async function validate(cookie, actionCode, objectIds) {
  return api(cookie, '/api/workflow/action-permissions/validate', {
    method: 'POST',
    body: JSON.stringify({
      moduleCode: 'payment-request',
      actionCode,
      objectIds,
      selectionCount: objectIds.length,
      businessStatus: 'client_value_must_not_be_trusted',
    }),
  })
}

const viewerCookie = await actorSession('v552-viewer')
const operatorCookie = await actorSession('v552-operator')
const batchCookie = await actorSession('v552-batch-operator')
const outscopeCookie = await actorSession('v552-outscope')

const contract = await api(
  viewerCookie,
  '/api/workflow/action-permissions/contract',
)
assert(contract.status === 200, 'Permission contract API failed')
assert(contract.payload.data.moduleCount === 13, 'Module count mismatch')
assert(contract.payload.data.actionCount === 54, 'Policy count mismatch')

const viewerList = await api(
  viewerCookie,
  '/api/finance/payment-requests/',
)
const operatorList = await api(
  operatorCookie,
  '/api/finance/payment-requests/',
)
const batchList = await api(
  batchCookie,
  '/api/finance/payment-requests/',
)
const outscopeList = await api(
  outscopeCookie,
  '/api/finance/payment-requests/',
)
assert(viewerList.payload.data.count === 8, 'Viewer list count mismatch')
assert(operatorList.payload.data.count === 8, 'Operator list count mismatch')
assert(batchList.payload.data.count === 8, 'Batch list count mismatch')
assert(outscopeList.payload.data.count === 0, 'Out-of-scope list was exposed')
const objectIds = batchList.payload.data.results.slice(0, 2).map(row => row.id)
assert(objectIds.length === 2, 'Payment request samples missing')

const viewerDenied = await validate(
  viewerCookie,
  'enter-payment-instruction-prepare',
  [objectIds[0]],
)
const operatorAllowed = await validate(
  operatorCookie,
  'enter-payment-instruction-prepare',
  [objectIds[0]],
)
const operatorBatchDenied = await validate(
  operatorCookie,
  'batch-enter-payment-instruction-prepare',
  objectIds,
)
const batchAllowed = await validate(
  batchCookie,
  'batch-enter-payment-instruction-prepare',
  objectIds,
)
const outscopeDenied = await validate(
  outscopeCookie,
  'enter-payment-instruction-prepare',
  [objectIds[0]],
)

assert(viewerDenied.status === 403, 'Viewer action was not rejected')
assert(operatorAllowed.status === 200, 'Operator single action was rejected')
assert(operatorAllowed.payload.data.granted, 'Operator decision was not granted')
assert(
  operatorAllowed.payload.data.serverFacts.statuses[0] === 'approved',
  'Server state was not re-read',
)
assert(operatorBatchDenied.status === 403, 'Operator batch was not rejected')
assert(batchAllowed.status === 200, 'Batch operator action was rejected')
assert(batchAllowed.payload.data.granted, 'Batch decision was not granted')
assert(outscopeDenied.status === 403, 'Out-of-scope action was not rejected')

const report = {
  result: 'passed',
  version: VERSION,
  contractVersion: contract.payload.contractVersion,
  apiBase,
  currentStateSource: 'server',
  moduleCount: contract.payload.data.moduleCount,
  permissionPolicyCount: contract.payload.data.actionCount,
  roles: {
    viewer: {
      viewCount: viewerList.payload.data.count,
      singleActionStatus: viewerDenied.status,
      singleActionDecision: viewerDenied.payload.data.decisionCode,
    },
    operator: {
      viewCount: operatorList.payload.data.count,
      singleActionStatus: operatorAllowed.status,
      singleActionDecision: operatorAllowed.payload.data.decisionCode,
      batchActionStatus: operatorBatchDenied.status,
      batchActionDecision:
        operatorBatchDenied.payload.data.decisionCode,
    },
    batchOperator: {
      viewCount: batchList.payload.data.count,
      batchActionStatus: batchAllowed.status,
      batchActionDecision: batchAllowed.payload.data.decisionCode,
    },
    outOfScope: {
      viewCount: outscopeList.payload.data.count,
      singleActionStatus: outscopeDenied.status,
      singleActionDecision: outscopeDenied.payload.data.decisionCode,
    },
  },
  serverFacts: {
    objectIds,
    statuses: batchAllowed.payload.data.serverFacts.statuses,
    legalEntityIds:
      batchAllowed.payload.data.serverFacts.legalEntityIds,
    clientStatusTrusted: false,
  },
  frontendVisibilityIsAuthority: false,
  serverValidationRequired: true,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'server-validation-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
