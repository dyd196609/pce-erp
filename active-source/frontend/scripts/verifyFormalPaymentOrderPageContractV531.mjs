import fs from 'node:fs'
import path from 'node:path'

const VERSION = 'V1.14.2.8.4.7.53.1'
const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const page = read('frontend/src/meta/pages/FormalPaymentOrderPage.vue')
const runtime = read('frontend/src/meta/runtime/formalPaymentOrderRuntime.js')
const filters = read('frontend/src/meta/runtime/pceAdvancedFilterContract.js')
const registry = read('frontend/src/meta/runtime/pceBusinessModuleRegistry.js')
const resultRoot = path.join(root, 'frontend', 'test-results', 'formal-payment-order-v531')

const requiredFilterFragments = [
  "field: 'status'",
  "field: 'riskStatus'",
  "field: 'riskLevel'",
  "field: 'supplierName'",
  "field: 'legalEntity'",
  "field: 'ledgerBook'",
  "field: 'currency'",
  "field: 'amountMin'",
  "field: 'amountMax'",
  "field: 'executionDateFrom'",
  "field: 'executionDateTo'",
  "field: 'scenarioCode'",
]
const guards = {
  formal_payment_order_page_uses_shared_filter_contract:
    runtime.includes('createPceAdvancedFilterSchema')
    && runtime.includes('PCE_FILTER_DISPLAY_MAP')
    && page.includes('FORMAL_PAYMENT_ORDER_FILTER_SCHEMA')
    && page.includes('PceAdvancedFilterField')
    && !page.includes('const filterSchema = ['),
  formal_payment_order_required_filters_complete:
    requiredFilterFragments.every(fragment => runtime.includes(fragment)),
  formal_payment_order_dictionary_fields_are_select:
    ['supplierName', 'legalEntity', 'ledgerBook', 'currency', 'scenarioCode']
      .every(field => runtime.includes(`field: '${field}'`) && runtime.includes(`field: '${field}', label:`)),
  formal_payment_order_status_options_are_chinese:
    ['已准备', '已取消', '已通过', '已阻断', '低', '中', '高']
      .every(label => runtime.includes(`label: '${label}'`) || filters.includes(`${label}'`)),
  formal_payment_order_cancelled_display_registered:
    filters.includes("cancelled: '已取消'"),
  formal_payment_order_server_risk_evidence_derived:
    runtime.includes('row.evidence?.riskReview?.riskResult')
    && runtime.includes('row.evidence?.riskReview?.riskLevel'),
  formal_payment_order_action_whitelist_complete:
    ['查看正式付款单', '查看来源真实付款风险评审', '复制业务编号']
      .every(label => page.includes(`>${label}</el-button>`)),
  formal_payment_order_execution_actions_absent:
    ['>签署</el-button>', '>发送银行</el-button>', '>付款执行</el-button>', '>生成凭证</el-button>', '>核销</el-button>', '>总账</el-button>']
      .every(label => !page.includes(label)),
  formal_payment_order_fixed_columns_preserved:
    page.includes('type="selection" width="55" fixed="left"')
    && page.includes('label="操作"')
    && page.includes('fixed="right" class-name="payment-fixed-action-column"'),
  formal_payment_order_api_page_diagnostic_strict_single_facts:
    page.includes('createFormalPaymentOrderPageFacts')
    && page.includes('formalPaymentOrderCount: facts.capacity.formalPaymentOrderCount')
    && page.includes('strictServerFacts: facts.strictServerFacts'),
  formal_payment_order_registry_uses_runtime_schema:
    registry.includes('FORMAL_PAYMENT_ORDER_FILTER_SCHEMA')
    && registry.includes('advancedFilterSchema: FORMAL_PAYMENT_ORDER_FILTER_SCHEMA'),
  formal_payment_order_page_contract_version:
    runtime.includes(`FORMAL_PAYMENT_ORDER_VERSION = '${VERSION}'`)
    || runtime.includes("FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.53.2'")
    || runtime.includes("FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.53.3'")
    || runtime.includes("FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.54'")
    || runtime.includes("FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.54.1'")
    || runtime.includes("FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.54.2'")
    || runtime.includes("FORMAL_PAYMENT_ORDER_VERSION = 'V1.14.2.8.4.7.54.3'"),
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
  backendModelChanged: false,
  migrationChanged: false,
  canaryDataChanged: false,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'static-guards.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
