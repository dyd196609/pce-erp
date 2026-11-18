import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.3'
const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const riskModel = read('backend/payment_risk_review/models.py')
const riskService = read('backend/payment_risk_review/services.py')
const riskView = read('backend/payment_risk_review/views.py')
const riskRuntime = read('frontend/src/meta/runtime/paymentRiskReviewRuntime.js')
const orderModel = read('backend/formal_payment_order/models.py')
const orderProvider = read('backend/formal_payment_order/providers.py')
const orderService = read('backend/formal_payment_order/services.py')
const orderView = read('backend/formal_payment_order/views.py')
const orderRuntime = read('frontend/src/meta/runtime/formalPaymentOrderRuntime.js')
const orderPage = read('frontend/src/meta/pages/FormalPaymentOrderPage.vue')
const pageTest = read('frontend/tests/ui-baseline/formalPaymentOrderV53.spec.js')
const resultRoot = path.join(root, 'frontend', 'test-results', 'formal-payment-order-v533')

const guards = {
  scenario_code_has_server_values:
    riskModel.includes('scenario_code = models.CharField(max_length=80, editable=False)')
    && orderModel.includes('source_scenario_code = models.CharField(max_length=80, editable=False)')
    && orderProvider.includes('"scenarioCode": review.scenario_code')
    && orderService.includes('"sourceScenarioCode": order.source_scenario_code')
    && orderView.includes('"scenarioCode": source.scenario_code'),
  scenario_code_consistent_api_page_diagnostic:
    orderRuntime.includes("scenarioCode: row.sourceScenarioCode || ''")
    && orderRuntime.includes('scenarioCode: row.scenarioCode,')
    && orderPage.includes('scenarioCode: current.value?.scenarioCode')
    && orderPage.includes('scenarioCodes: facts.rows.map(row => row.scenarioCode)')
    && pageTest.includes('E-FPO-DIAG-SCENARIO-001')
    && pageTest.includes('E-FPO-STRICT-SCENARIO-001'),
  scenario_code_not_empty_for_strict_pages:
    riskModel.includes('name="prr_scenario_code_not_empty"')
    && orderModel.includes('name="fpo_source_scenario_not_empty"')
    && pageTest.includes("row.sourceScenarioCode")
    && pageTest.includes('E-FPO-STRICT-SCENARIO-002')
    && !riskRuntime.includes('`SUCCESS_${String(index + 1)'),
  scenario_code_not_client_submitted:
    orderService.includes('source_scenario_code=current.scenario_code')
    && riskService.includes('"scenario_code": normalized_scenario_code')
    && !riskView.includes('request.data.get("scenarioCode")')
    && !orderView.includes('request.data.get("sourceScenarioCode")'),
  scenario_filter_options_use_server_rows:
    orderRuntime.includes("{ field: 'scenarioCode', label: '场景编码', type: 'select' }")
    && orderPage.includes(':rows="rows"')
    && pageTest.includes('E-FPO-SCENARIO-OPTION-001')
    && pageTest.includes('E-FPO-SCENARIO-FILTER-001'),
}
const failures = Object.entries(guards)
  .filter(([, passed]) => !passed)
  .map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: VERSION,
  guardCount: Object.keys(guards).length,
  passedGuardCount: Object.values(guards).filter(Boolean).length,
  failures,
  guards,
  expectedScenarioCodes: Array.from(
    { length: 8 },
    (_, index) => `SUCCESS_${String(index + 1).padStart(2, '0')}`,
  ),
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(
  path.join(resultRoot, 'scenario-contract-static-report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
  'utf8',
)
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
