import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..', '..')
const read = relative => fs.readFileSync(path.join(root, relative), 'utf8')
const page = read('frontend/src/meta/pages/PaymentExecutionRiskReviewPage.vue')
const runtime = read('frontend/src/meta/runtime/paymentRiskReviewRuntime.js')
const panel = read('frontend/src/meta/components/PceStrictServerFactsPanel.vue')
const api = read('frontend/src/api/paymentRiskReview.js')
const models = read('backend/payment_risk_review/models.py')
const services = read('backend/payment_risk_review/services.py')
const providers = read('backend/payment_risk_review/providers.py')
const views = read('backend/payment_risk_review/views.py')
const registry = read('frontend/src/meta/process/financeProcessPageRegistry.js')
const guards = {
  risk_review_source_must_be_payment_order_draft:
    models.includes('default="paymentOrderDraft"')
    && services.includes('SOURCE_DOCUMENT_TYPE = "paymentOrderDraft"'),
  risk_review_fact_model_single_source:
    runtime.includes('createPaymentRiskReviewPageFacts')
    && page.includes('createPaymentRiskReviewPageFacts')
    && !page.includes('paymentExecutionRiskReviewStore'),
  risk_review_page_matches_api:
    api.includes('/api/finance/payment-risk-reviews/')
    && page.includes('paymentRiskReviewApi.list()'),
  risk_review_diagnostic_matches_page:
    page.includes('riskReviewCount: facts.capacity.riskReviewCount')
    && page.includes('resultCount: facts.resultCount'),
  risk_review_strictFacts_matches_moduleFacts:
    panel.includes("props.pageCode === 'payment-risk-review'")
    && panel.includes('createPaymentRiskReviewPageFacts')
    && runtime.includes('resultCount: rows.length'),
  risk_review_rules_server_executed:
    services.includes('RULES = (')
    && services.includes('PaymentOrderDraftRiskEvidenceProvider')
    && services.includes('RiskReviewExecution.objects.create'),
  risk_review_blocked_has_reason:
    models.includes('blocking_reasons = models.JSONField')
    && views.includes('"blockedScenarios": scenarios'),
  risk_review_success_requires_all_rules_pass:
    services.includes('current.status = "blocked" if failures else "passed"')
    && services.includes('passed_count=len(results) - len(failures)'),
  risk_review_cannot_create_payment_order:
    services.includes('"formalPaymentOrderCreated": False')
    && page.includes('不创建正式付款单'),
  risk_review_no_downstream_write:
    views.includes('"formalPaymentOrders": 0')
    && views.includes('"paymentExecutions": 0')
    && !page.includes('生成正式付款单'),
  risk_review_business_labels_are_chinese:
    ['评审状态', '风险等级', '风险结果', '是否允许进入下一模块', '阻断原因', '下一步骤放行状态']
      .every(label => page.includes(label)),
  risk_review_forbidden_technical_labels_absent:
    !['<Fact label="status"', '<Fact label="riskLevel"', '<Fact label="riskResult"', '<Fact label="eligible"', '<Fact label="blockingReasons"', '<Fact label="nextStepReadiness"']
      .some(label => page.includes(label)),
  risk_review_server_evidence_only:
    providers.includes('read_order_authorities')
    && !services.includes('request.data.get("riskResult")'),
  risk_review_strict_level_five_registered:
    registry.includes("['payment-risk-review'")
    && registry.includes("const STRICT_FLOW_END = 'payment-risk-review'"),
  risk_review_no_legacy_local_storage:
    !page.includes('localStorage')
    && !page.includes('STORAGE_KEY'),
}
const failures = Object.entries(guards).filter(([, passed]) => !passed).map(([name]) => name)
const report = {
  result: failures.length ? 'failed' : 'passed',
  version: 'V1.14.2.8.4.7.52',
  guardCount: Object.keys(guards).length,
  passedGuardCount: Object.values(guards).filter(Boolean).length,
  failures,
  guards,
}
console.log(JSON.stringify(report, null, 2))
if (failures.length) process.exit(1)

