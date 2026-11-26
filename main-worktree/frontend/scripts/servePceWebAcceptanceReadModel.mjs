import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'

const HOST = '127.0.0.1'
const PORT = 8000
const VERSION = 'V1.14.2.8.4.7.50.2'
const frontend = path.resolve(import.meta.dirname, '..')
const checkpoint = path.join(
  frontend,
  'test-results',
  'purchase-payment-golden-flow',
  'checkpoints',
  'payment_order_prepare_standard_list_ready',
  'business-entities.json',
)
const state = JSON.parse(fs.readFileSync(checkpoint, 'utf8'))
const rows = state.objects.map((row, index) => ({
  ...row,
  canaryLineageId: `PCE-WEB-ACCEPTANCE-${index + 1}`,
  scenarioCode: `PASS-THROUGH-${String(index + 1).padStart(2, '0')}`,
  scenarioClass: 'pass_through',
  scenarioRole: `persistent_canary_${index + 1}`,
  downstreamEligible: Boolean(row.eligibility?.eligible),
  reservedForNextModule: false,
  nextStageConsumed: false,
  upstreamObjectNos: [row.sourcePaymentInstructionPrepareNo].filter(Boolean),
}))
const downstreamCounts = state.downstreamCounts
const capacity = {
  canaryBatchId: 'PURCHASE-FLOW-DEMO-V1',
  paymentInstructionPrepareSourceCount: rows.length,
  paymentInstructionPrepareConsumedCount: rows.length,
  passThroughLineageCount: rows.length,
  blockedScenarioCount: state.counts?.blockedScenarios || 0,
  formalPaymentOrderPrepareCount: rows.length,
  preparedPaymentOrderPrepareCount: rows.filter(row => row.status === 'prepared').length,
  downstreamEligibleSourceCount: rows.filter(row => row.eligibility?.eligible).length,
  nextStageConsumedCount: 0,
  unconsumedAvailableCount: rows.filter(row => row.eligibility?.eligible).length,
  nextModuleCode: 'payment_order_draft',
  nextCanonicalName: '正式付款单草稿',
  nextRoute: '/finance/payment-order-drafts',
  passed: rows.length >= 8,
}
const listPayload = {
  result: 'passed',
  version: VERSION,
  canonicalName: '正式付款单预备',
  sourceDocumentType: 'paymentInstructionPrepare',
  currentStateSource: 'server',
  acceptanceReadModel: 'immutable_server_checkpoint',
  data: {
    count: rows.length,
    results: rows,
    tenantId: 'tenant-canary-demo',
    canaryBatchId: capacity.canaryBatchId,
    capacity,
    scenarioOverview: rows.map(row => ({
      scenarioCode: row.scenarioCode,
      scenarioClass: row.scenarioClass,
      scenarioRole: row.scenarioRole,
      currentObjectNo: row.prepareNo,
      currentStatus: row.status,
      formalObjectCount: 1,
      nextStepAllowed: Boolean(row.eligibility?.eligible),
    })),
    downstreamCounts,
    productionTenantFormalObjectCount: 0,
    productionRolloutEnabled: false,
  },
}

const json = (response, status, payload) => {
  response.writeHead(status, {
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
  })
  response.end(JSON.stringify(payload))
}

const server = http.createServer((request, response) => {
  if (request.method === 'OPTIONS') return json(response, 204, {})
  const url = new URL(request.url, `http://${HOST}:${PORT}`)
  if (request.method !== 'GET') {
    return json(response, 405, { result: 'blocked', error: { code: 'READ_ONLY_ACCEPTANCE_SERVICE' } })
  }
  if (url.pathname === '/api/finance/payment-order-prepares/') {
    return json(response, 200, listPayload)
  }
  const detail = url.pathname.match(/^\/api\/finance\/payment-order-prepares\/(\d+)\/?$/)
  if (detail) {
    const row = rows.find(item => String(item.id) === detail[1])
    if (!row) return json(response, 404, { result: 'blocked', error: { code: 'POP_NOT_FOUND' } })
    return json(response, 200, {
      result: 'passed',
      version: VERSION,
      canonicalName: '正式付款单预备',
      sourceDocumentType: 'paymentInstructionPrepare',
      currentStateSource: 'server',
      acceptanceReadModel: 'immutable_server_checkpoint',
      data: row,
      downstreamCounts,
    })
  }
  if (url.pathname === '/health/pce-web-acceptance') {
    return json(response, 200, {
      result: 'passed',
      version: VERSION,
      mode: 'read_only',
      source: checkpoint,
      rowCount: rows.length,
    })
  }
  return json(response, 404, { result: 'blocked', error: { code: 'NOT_FOUND' } })
})

server.listen(PORT, HOST, () => {
  console.log(`[${VERSION}] read-only acceptance server listening at http://${HOST}:${PORT}`)
})
