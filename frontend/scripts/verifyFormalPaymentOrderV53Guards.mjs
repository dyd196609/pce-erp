import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const page = read('frontend/src/meta/pages/FormalPaymentOrderPage.vue')
const runtime = read('frontend/src/meta/runtime/formalPaymentOrderRuntime.js')
const panel = read('frontend/src/meta/components/PceStrictServerFactsPanel.vue')
const api = read('frontend/src/api/formalPaymentOrder.js')
const models = read('backend/formal_payment_order/models.py')
const services = read('backend/formal_payment_order/services.py')
const providers = read('backend/formal_payment_order/providers.py')
const views = read('backend/formal_payment_order/views.py')
const registry = read('frontend/src/meta/process/financeProcessPageRegistry.js')
const filters = read('frontend/src/meta/runtime/pceAdvancedFilterContract.js')
const resultRoot = path.join(root, 'frontend', 'test-results', 'formal-payment-order-v53')

const guards = {
  formal_payment_order_source_must_be_risk_review:
    models.includes('default="paymentRiskReview"')
    && services.includes('SOURCE_DOCUMENT_TYPE = "paymentRiskReview"'),
  formal_payment_order_requires_server_revalidation:
    services.includes('source.status != "passed"')
    && services.includes('source.risk_result != "passed"')
    && services.includes('source.risk_level != "low"')
    && services.includes('ready_for_formal_payment_order'),
  formal_payment_order_fact_model_single_source:
    runtime.includes('createFormalPaymentOrderPageFacts')
    && page.includes('createFormalPaymentOrderPageFacts')
    && !page.includes('localStorage'),
  formal_payment_order_diagnostic_matches_page:
    page.includes('formalPaymentOrderCount: facts.capacity.formalPaymentOrderCount')
    && page.includes('resultCount: facts.resultCount'),
  formal_payment_order_strictFacts_matches_api:
    panel.includes("props.pageCode === 'formal-payment-order'")
    && panel.includes('createFormalPaymentOrderPageFacts')
    && api.includes('/api/finance/formal-payment-orders/'),
  formal_payment_order_no_bank_send:
    views.includes('"bankMessages": 0')
    && !page.includes('<button>发送银行')
    && !page.includes('生成银行报文</el-button>'),
  formal_payment_order_no_payment_execution:
    views.includes('"paymentExecutions": 0')
    && !page.includes('执行付款</el-button>'),
  formal_payment_order_idempotent:
    services.includes('BusinessActionIdempotency')
    && services.includes('"classification": "existing_result"')
    && models.includes('source_risk_review = models.OneToOneField'),
  formal_payment_order_no_ledger_write:
    views.includes('"ledgerEntries": 0')
    && views.includes('"postings": 0'),
  formal_payment_order_server_evidence_only:
    providers.includes('PaymentRiskReviewAuthorityProvider')
    && providers.includes('review.evidence_snapshots')
    && !services.includes('request.data.get("eligible")'),
  formal_payment_order_filter_contract_inherited:
    runtime.includes('createPceAdvancedFilterSchema')
    && runtime.includes('FORMAL_PAYMENT_ORDER_FILTER_SCHEMA')
    && page.includes('PceAdvancedFilterField')
    && !page.includes('const filterSchema = ['),
  formal_payment_order_filter_labels_chinese:
    ['正式付款单编号', '来源风险评审编号', '供应商', '法人', '账簿', '币种', '金额下限', '计划执行日期起']
      .every(label => runtime.includes(label) || filters.includes(label)),
  formal_payment_order_strict_level_five_registered:
    registry.includes("['formal-payment-order'")
    && (
      registry.includes("const STRICT_FLOW_END = 'formal-payment-order'")
      || registry.includes(
        "const STRICT_FLOW_END = 'bank-send-preparation'",
      )
      || registry.includes("const STRICT_FLOW_END = 'bank-send-task'")
    ),
  formal_payment_order_downstream_zero_visible:
    page.includes('data-acceptance-id="formal-payment-order-zero-boundary"')
    && page.includes('下游零对象保护'),
  formal_payment_order_sensitive_diagnostic_absent:
    !page.includes('JWT')
    && !page.includes('Cookie')
    && !page.includes('privateKey')
    && !page.includes('accountNo'),
}
const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: 'V1.14.2.8.4.7.53',
  guardCount: Object.keys(guards).length,
  passedGuardCount: Object.values(guards).filter(Boolean).length,
  failures,
  guards,
}
fs.mkdirSync(resultRoot, { recursive: true })
fs.writeFileSync(path.join(resultRoot, 'static-guards.json'), `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)
