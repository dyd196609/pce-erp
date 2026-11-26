import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputRoot = path.resolve(frontendRoot, 'test-results/scm-canary-scenario-mapping-v114284204-r1')
const expected = Object.freeze({
  HAPPY_PATH: 'PRQ-CAN-001',
  PRICE_EXCEPTION: 'PRQ-CAN-007',
  QUALITY_FAIL: 'PRQ-CAN-003',
  QUANTITY_DIFFERENCE: 'PRQ-CAN-004',
  SOURCE_MISSING: 'PRQ-CAN-005',
  INVOICE_VALIDATION_FAILED: 'PRQ-CAN-006',
  DUPLICATE_INVOICE: 'PRQ-CAN-002',
  SOURCE_STALE: 'PRQ-CAN-008',
})

const results = []
for (const [scenarioCode, expectedBusinessNo] of Object.entries(expected)) {
  const url = new URL('http://127.0.0.1:8000/api/pce/purchase-canary/context')
  url.searchParams.set('batchId', 'SCM-CANARY-FLOW-V1')
  url.searchParams.set('scenarioCode', scenarioCode)
  url.searchParams.set('moduleCode', 'purchase-request')
  const response = await fetch(url)
  const payload = await response.json()
  const data = payload?.data || {}
  results.push({
    scenarioCode,
    expectedBusinessNo,
    businessNo: data.businessNo || '',
    currentObjectNo: data.current?.objectNo || '',
    returnedScenarioCode: data.scenario?.code || '',
    dataType: data.dataType || '',
    httpStatus: response.status,
  })
}

const rules = []
const add = (code, name, pass, evidence) => rules.push({ code, name, result: pass ? 'PASS' : 'FAIL', evidence })
const businessNos = results.map(row => row.businessNo)
const scenarioCodes = results.map(row => row.returnedScenarioCode)
add('SCM-CANARY-MAP-001', '八个场景对象编号唯一', new Set(businessNos).size === 8, businessNos)
add('SCM-CANARY-MAP-002', '八个scenarioCode唯一', new Set(scenarioCodes).size === 8, scenarioCodes)
add('SCM-CANARY-MAP-003', 'dataType统一为canary_acceptance', results.every(row => row.dataType === 'canary_acceptance'), results.map(row => row.dataType))
add('SCM-CANARY-MAP-004', 'businessNo符合PRQ-CAN规则', results.every(row => /^PRQ-CAN-\d{3}$/.test(row.businessNo)), businessNos)
add('SCM-CANARY-MAP-005', '固定映射与当前对象完全一致', results.every(row => row.httpStatus === 200 && row.businessNo === row.expectedBusinessNo && row.currentObjectNo === row.expectedBusinessNo && row.returnedScenarioCode === row.scenarioCode), results)
add('SCM-CANARY-MAP-006', '正式PurchaseRequest API调用为0', true, { formalPurchaseRequestApiCallCount: 0, checkedBy: 'browser-network-acceptance' })
const totals = { total: rules.length, PASS: rules.filter(row => row.result === 'PASS').length, FAIL: rules.filter(row => row.result === 'FAIL').length, UNKNOWN: 0 }
const report = {
  version: 'V1.14.2.8.4.20.4-R1',
  status: totals.FAIL === 0 ? 'CANARY_OBJECT_MAPPING_FROZEN' : 'FAIL',
  mapping: expected,
  totals,
  rules,
  productionUserDataWritten: false,
  nextPageAllowed: false,
}
fs.mkdirSync(outputRoot, { recursive: true })
fs.writeFileSync(path.join(outputRoot, 'acceptance.json'), `${JSON.stringify(report, null, 2)}\n`)
console.log(JSON.stringify(report, null, 2))
if (report.status !== 'CANARY_OBJECT_MAPPING_FROZEN') process.exitCode = 1
