import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const VERSION = 'V1.14.2.8.4.7.55.1.1'
const root = process.cwd()
const apiBase = (
  process.env.PCE_V5511_API_BASE_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '')
const resultRoot = path.join(
  root,
  'test-results',
  'pce-business-action-real-data-v5511',
)
const writeJson = (name, value) => {
  fs.mkdirSync(resultRoot, { recursive: true })
  fs.writeFileSync(
    path.join(resultRoot, name),
    `${JSON.stringify(value, null, 2)}\n`,
    'utf8',
  )
}
const assert = (condition, message) => {
  if (!condition) throw new Error(message)
}
const get = async route => {
  const response = await fetch(`${apiBase}${route}`)
  const payload = await response.json()
  assert(response.ok, `${route} returned HTTP ${response.status}`)
  return payload
}

const preparePayload = await get(
  '/api/finance/payment-request-prepares/',
)
const requestPayload = await get('/api/finance/payment-requests/')
const prepareData = preparePayload.data
const requestData = requestPayload.data
const prepareRows = prepareData.results || []
const requestRows = requestData.results || []
const eligibilityRows = []
for (const row of requestRows.slice(0, 2)) {
  const payload = await get(
    `/api/finance/payment-requests/${encodeURIComponent(row.id)}`
      + '/payment-instruction-prepare-eligibility',
  )
  eligibilityRows.push({
    id: row.id,
    requestNo: row.requestNo,
    status: row.status,
    ...payload.data,
  })
}

const guards = {
  payment_request_prepare_uses_server_read_model:
    preparePayload.currentStateSource === 'server',
  payment_request_prepare_count_is_eight:
    prepareData.count === 8 && prepareRows.length === 8,
  payment_request_prepare_all_prepared:
    prepareRows.every(row => row.status === 'prepared'),
  payment_request_prepare_source_is_payable_confirmation_prepare:
    preparePayload.sourceDocumentType === 'payableConfirmationPrepare'
      && prepareRows.every(
        row => row.sourceDocumentType === 'payableConfirmationPrepare',
      ),
  payment_request_uses_server_read_model:
    requestPayload.currentStateSource === 'server',
  payment_request_count_is_eight:
    requestData.count === 8 && requestRows.length === 8,
  payment_request_all_approved:
    requestRows.every(row => row.status === 'approved'),
  payment_request_source_is_payment_request_prepare:
    requestPayload.sourceDocumentType === 'paymentRequestPrepare'
      && requestRows.every(
        row => row.sourceDocumentType === 'paymentRequestPrepare',
      ),
  single_source_server_eligibility_ready:
    eligibilityRows.length >= 1
      && eligibilityRows[0].serverDerived === true
      && eligibilityRows[0].eligible === true
      && eligibilityRows[0].nextStepReadiness
        === 'ready_for_payment_instruction_prepare',
  batch_sources_server_eligibility_ready:
    eligibilityRows.length === 2
      && eligibilityRows.every(
        row => row.serverDerived === true
          && row.eligible === true
          && row.nextStepReadiness
            === 'ready_for_payment_instruction_prepare',
      ),
  navigation_context_has_no_downstream_creation:
    Number(requestData.downstreamCounts?.paymentInstructionPrepares || 0)
      === 0,
}
const failedGuards = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const report = {
  result: failedGuards.length === 0 ? 'passed' : 'failed',
  version: VERSION,
  canonicalName: 'PCE业务动作真实数据验收补全',
  apiBase,
  currentStateSource: 'server',
  guardCount: Object.keys(guards).length,
  passedGuardCount: Object.values(guards).filter(Boolean).length,
  failedGuardCount: failedGuards.length,
  failedGuards,
  guards,
  paymentRequestPrepare: {
    sourceDocumentType: preparePayload.sourceDocumentType,
    formalObjectCount: prepareRows.length,
    statuses: [...new Set(prepareRows.map(row => row.status))],
    objectNos: prepareRows.map(row => row.prepareNo),
  },
  paymentRequest: {
    sourceDocumentType: requestPayload.sourceDocumentType,
    formalObjectCount: requestRows.length,
    statuses: [...new Set(requestRows.map(row => row.status))],
    objectNos: requestRows.map(row => row.requestNo),
    eligibilityRows,
  },
  actionContextDownstreamCounts: requestData.downstreamCounts,
  apiMethodCounts: { GET: 4, POST: 0, PUT: 0, PATCH: 0, DELETE: 0 },
  businessWriteRequestCount: 0,
  paymentInstructionPrepareCreated: false,
  productionUserDataWritten: false,
}

writeJson('api-real-data-report.json', report)
assert(
  report.result === 'passed',
  `V55.1.1 API guards failed: ${failedGuards.join(', ')}`,
)
console.log(JSON.stringify(report, null, 2))
