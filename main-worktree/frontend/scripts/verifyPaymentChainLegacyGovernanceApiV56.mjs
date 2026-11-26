import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.56'
const API_ROOT = (
  process.env.PCE_V56_API_ROOT
  || 'http://127.0.0.1:8044'
).replace(/\/$/, '')
const resultRoot = path.resolve(
  'test-results',
  'payment-chain-legacy-governance-v56',
)
const modules = [
  {
    module: 'payment_request_prepare',
    registryModule: 'payment-request-prepare',
    endpoint: 'payment-request-prepares',
    expectedStatus: 'prepared',
    expectedTransitionCount: 1,
  },
  {
    module: 'payment_request',
    registryModule: 'payment-request',
    endpoint: 'payment-requests',
    expectedStatus: 'approved',
    expectedTransitionCount: 2,
  },
  {
    module: 'payment_instruction_prepare',
    registryModule: 'payment-instruction-prepare',
    endpoint: 'payment-instruction-prepares',
    expectedStatus: 'validated',
    expectedTransitionCount: 1,
  },
  {
    module: 'payment_order_prepare',
    registryModule: 'payment-order-prepare',
    endpoint: 'payment-order-prepares',
    expectedStatus: 'submitted',
    expectedTransitionCount: 1,
  },
]
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}
const factsOf = row => ({
  statusTransitionHistory: row.statusTransitionHistory,
  statusTransitionCount: row.statusTransitionCount,
  stateMachineConsistent: row.stateMachineConsistent,
})
const getJson = async (url, cookie = '') => {
  const response = await fetch(url, {
    headers: cookie ? { cookie } : {},
  })
  const payload = await response.json()
  assert(response.ok, `GET ${url} returned ${response.status}`)
  return { response, payload }
}

const session = await fetch(
  `${API_ROOT}/api/workflow/action-permissions/canary-session`
  + '?actor=v552-batch-operator',
)
assert(session.ok, `Actor session returned ${session.status}`)
const cookie = session.headers.get('set-cookie')?.split(';')[0] || ''
assert(cookie.includes('pce_v552_actor='), 'Actor cookie was not issued')

const moduleReports = []
for (const module of modules) {
  const { payload } = await getJson(
    `${API_ROOT}/api/finance/${module.endpoint}/`,
    cookie,
  )
  assert(
    payload.currentStateSource === 'server',
    `${module.module}: API state source is not server`,
  )
  const rows = payload.data?.results || []
  assert(rows.length >= 8, `${module.module}: expected at least 8 rows`)
  const first = rows[0]
  const facts = factsOf(first)
  assert(
    Array.isArray(facts.statusTransitionHistory),
    `${module.module}: transition history missing`,
  )
  assert(
    facts.statusTransitionCount
      === facts.statusTransitionHistory.length,
    `${module.module}: transition count mismatch`,
  )
  assert(
    facts.statusTransitionCount === module.expectedTransitionCount,
    `${module.module}: unexpected transition count`,
  )
  assert(
    facts.stateMachineConsistent === true,
    `${module.module}: inconsistent state machine`,
  )
  assert(
    first.status === module.expectedStatus,
    `${module.module}: unexpected status ${first.status}`,
  )
  const legalEntityId =
    first.legalEntityId || first.legal_entity_id || ''
  const permissionUrl = new URL(
    `${API_ROOT}/api/workflow/action-permissions/`,
  )
  permissionUrl.searchParams.set('moduleCode', module.registryModule)
  permissionUrl.searchParams.set('objectIds', String(first.id))
  permissionUrl.searchParams.set('selectionCount', '1')
  permissionUrl.searchParams.set('legalEntityId', legalEntityId)
  const permission = await getJson(permissionUrl.toString(), cookie)
  assert(
    permission.payload.result === 'passed',
    `${module.module}: action permission lookup failed`,
  )
  assert(
    permission.payload.currentStateSource === 'server',
    `${module.module}: action permission source is not server authority`,
  )
  const decisions = permission.payload.data?.decisions || []
  assert(
    decisions.length >= 2,
    `${module.module}: registry actions were not resolved`,
  )
  moduleReports.push({
    module: module.module,
    registryModule: module.registryModule,
    objectCount: rows.length,
    status: first.status,
    facts,
    currentStateSource: payload.currentStateSource,
    actionPermissionSource: permission.payload.currentStateSource,
    registeredActionCount: decisions.length,
    grantedActionCount: decisions.filter(row => row.granted).length,
    apiPageDiagnosticStrictFactsRuntimeReady: true,
  })
}

const report = {
  result: 'passed',
  version: VERSION,
  apiRoot: API_ROOT,
  currentStateSource: 'server',
  priorityModuleCount: modules.length,
  passedPriorityModuleCount: moduleReports.length,
  statusTransitionCountMatchesHistory: true,
  actionRegistryResolvedByServer: true,
  moduleReports,
  businessWriteRequestCount: 0,
  bankSendTaskCreated: false,
  paymentExecutionCreated: false,
  paymentVoucherCreated: false,
  ledgerEntryCreated: false,
  productionUserDataWritten: false,
}
writeJson('api-runtime-report.json', report)
console.log(JSON.stringify(report, null, 2))
