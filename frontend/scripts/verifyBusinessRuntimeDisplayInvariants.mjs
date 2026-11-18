import fs from 'node:fs'
import path from 'node:path'

const root = process.cwd()
const shellText = fs.readFileSync(path.join(root, 'src/meta/components/BusinessOperationPageShell.vue'), 'utf8')
const panelText = fs.readFileSync(path.join(root, 'src/meta/components/BusinessActionStatusPanel.vue'), 'utf8')
const adapterText = fs.readFileSync(path.join(root, 'src/meta/process/businessActionResultPageAdapter.js'), 'utf8')
const guardText = fs.readFileSync(path.join(root, 'src/meta/process/businessFlowTransitionGuard.js'), 'utf8')
const classifierText = fs.readFileSync(path.join(root, 'src/meta/process/businessTargetEvidenceClassifier.js'), 'utf8')
const acceptanceCopyText = fs.readFileSync(path.join(root, 'src/meta/runtime/businessAcceptanceCopy.js'), 'utf8')
const testText = fs.readFileSync(path.join(root, 'tests/business-flow/purchasePayableRuntimeAcceptance.spec.js'), 'utf8')
const psText = fs.readFileSync(path.join(root, 'scripts/Test-PcePurchasePaymentFlow.ps1'), 'utf8')
const paymentExecutionText = fs.readFileSync(path.join(root, 'src/meta/pages/PaymentExecutionPreparePage.vue'), 'utf8')
const paymentVoucherPreviewText = fs.readFileSync(path.join(root, 'src/meta/pages/PaymentVoucherPreparePreviewPage.vue'), 'utf8')
const businessScrollContainerText = fs.readFileSync(path.join(root, 'src/meta/components/BusinessTableScrollContainer.vue'), 'utf8')

const requiredSourceSnippets = [
  { code: 'version_acceptance_copy', text: "BUSINESS_ACCEPTANCE_COPY_VERSION = 'V1.14.2.7.2.1'", source: acceptanceCopyText },
  { code: 'version_shell', text: 'BUSINESS_ACCEPTANCE_COPY_VERSION', source: shellText },
  { code: 'version_adapter', text: "BUSINESS_ACTION_RESULT_PAGE_ADAPTER_VERSION = 'V1.14.2.7.1'", source: adapterText },
  { code: 'version_guard', text: "BUSINESS_FLOW_TRANSITION_GUARD_VERSION = 'V1.14.2.7.1'", source: guardText },
  { code: 'version_classifier', text: "BUSINESS_TARGET_EVIDENCE_CLASSIFIER_VERSION = 'V1.14.2.7.1'", source: classifierText },
  { code: 'manual_acceptance_navigation', text: 'manual-acceptance-navigation', source: shellText },
  { code: 'copy_page_acceptance_checklist', text: 'copyPageAcceptanceChecklist', source: shellText },
  { code: 'panel_target_evidence_section', text: 'data-acceptance-id="target-evidence-status-section"', source: panelText },
  { code: 'panel_target_exists', text: 'data-acceptance-id="action-target-exists"', source: panelText },
  { code: 'panel_target_evidence_status', text: 'data-acceptance-id="action-target-evidence-status"', source: panelText },
  { code: 'panel_missing_evidence', text: 'data-acceptance-id="action-missing-evidence-list"', source: panelText },
  { code: 'panel_conflict_evidence', text: 'data-acceptance-id="action-conflict-evidence-list"', source: panelText },
  { code: 'panel_read_failure', text: 'data-acceptance-id="action-read-failure-list"', source: panelText },
  { code: 'panel_target_evidence_trace_section', text: 'data-acceptance-id="target-evidence-trace-section"', source: panelText },
  { code: 'panel_target_evidence_trace_table', text: 'data-acceptance-id="target-evidence-trace-table"', source: panelText },
  { code: 'panel_target_evidence_trace_scroll', text: 'acceptance-id="target-evidence-trace-table-scroll"', source: panelText },
  { code: 'panel_target_evidence_first_failure', text: 'data-acceptance-id="target-evidence-first-failure-label"', source: panelText },
  { code: 'panel_target_evidence_responsibility', text: 'data-acceptance-id="target-evidence-first-failure-responsibility"', source: panelText },
  { code: 'adapter_read_failed_status', text: "executionStatus: 'target_evidence_read_failed'", source: adapterText },
  { code: 'adapter_conflict_status', text: "executionStatus: 'existing_target_conflict'", source: adapterText },
  { code: 'adapter_target_no_display', text: 'targetObjectNoDisplay', source: adapterText },
  { code: 'adapter_target_evidence_trace_items', text: 'targetEvidenceTraceItems', source: adapterText },
  { code: 'adapter_target_evidence_first_failure', text: 'targetEvidenceFirstFailureCode', source: adapterText },
  { code: 'classifier_priority_read_failed', text: "'read_failed',", source: classifierText },
  { code: 'classifier_priority_conflict', text: "'conflict',", source: classifierText },
  { code: 'classifier_missing_items', text: 'targetEvidenceMissingItems', source: classifierText },
  { code: 'classifier_conflict_items', text: 'targetEvidenceConflictItems', source: classifierText },
  { code: 'classifier_read_failures', text: 'targetEvidenceReadFailures', source: classifierText },
  { code: 'classifier_trace_items', text: 'targetEvidenceTraceItems', source: classifierText },
  { code: 'classifier_trace_coverage', text: 'targetEvidenceTraceCoveragePassed', source: classifierText },
  { code: 'classifier_responsibility_summary', text: 'targetEvidenceResponsibilitySummary', source: classifierText },
  { code: 'classifier_source_consistency', text: 'targetEvidenceSourceConsistencyPassed', source: classifierText },
  { code: 'runtime_dom_consistency', text: 'domDisplayConsistencyPassed', source: shellText },
  { code: 'runtime_trace_dom_consistency', text: 'targetEvidenceTraceDomConsistencyPassed', source: shellText },
  { code: 'runtime_trace_display_consistency', text: 'targetEvidenceTraceDisplayConsistencyPassed', source: shellText },
  { code: 'runtime_classification_fields', text: 'targetEvidenceClassificationPassed', source: shellText },
  { code: 'test_fixture_conflict', text: "status: 'conflict'", source: testText },
  { code: 'test_fixture_read_failed', text: "status: 'read_failed'", source: testText },
  { code: 'test_trace_section', text: 'target-evidence-trace-section', source: testText },
  { code: 'powershell_trace_matrix_step', text: 'target-evidence-trace-matrix', source: psText },
  { code: 'powershell_version', text: "$Version = 'V1.14.2.8'", source: psText },
]

const checks = requiredSourceSnippets.map((item) => ({
  code: item.code,
  passed: item.source.includes(item.text),
}))

const semanticChecks = [
  {
    code: 'priority_read_failed_before_conflict',
    passed: classifierText.indexOf("'read_failed'") >= 0
      && classifierText.indexOf("'conflict'") > classifierText.indexOf("'read_failed'"),
  },
  {
    code: 'not_found_read_failed_separated',
    passed: classifierText.includes("targetEvidenceStatus === 'not_found'")
      && classifierText.includes("targetEvidenceStatus === 'read_failed'"),
  },
  {
    code: 'incomplete_conflict_separated',
    passed: classifierText.includes("targetEvidenceStatus === 'incomplete'")
      && classifierText.includes("targetEvidenceStatus === 'conflict'"),
  },
  {
    code: 'abnormal_status_not_released',
    passed: classifierText.includes("new Set(['not_found', 'incomplete', 'conflict', 'read_failed'])"),
  },
  {
    code: 'trace_table_single_native_horizontal_scroll',
    passed: panelText.includes('target-evidence-trace-table-scroll')
      && panelText.includes('BusinessTableScrollContainer')
      && panelText.includes('min-width="1900px"'),
  },
  {
    code: 'no_custom_blue_scrollbar_on_business_tables',
    passed: businessScrollContainerText.includes('overflow-x: auto')
      && !businessScrollContainerText.includes('PceHorizontalScrollArea'),
  },
  {
    code: 'payment_execution_index_column_present',
    passed: paymentExecutionText.includes('type="index" label="序号"')
      && paymentExecutionText.includes('payment-fixed-index-column'),
  },
  {
    code: 'payment_execution_no_column_fixed_left',
    passed: paymentExecutionText.includes('label="付款执行准备编号"')
      && paymentExecutionText.includes('payment-fixed-no-column')
      && paymentExecutionText.includes('fixed="left"'),
  },
  {
    code: 'payment_execution_action_column_fixed_right',
    passed: paymentExecutionText.includes('label="操作" fixed="right"')
      && paymentExecutionText.includes('payment-fixed-action-column')
      && paymentExecutionText.includes('查看付款凭证准备预览'),
  },
  {
    code: 'target_summary_chinese_display_only',
    passed: paymentVoucherPreviewText.includes('尚未创建')
      && paymentVoucherPreviewText.includes('目标证据分类器只读判断')
      && !paymentVoucherPreviewText.includes('<small>{{ targetEvidenceStatusCode }}</small>')
      && !paymentVoucherPreviewText.includes('<small>{{ targetEvidenceProcessingStatus }}</small>')
      && !paymentVoucherPreviewText.includes('<strong>businessTargetEvidenceClassifier.js</strong>'),
  },
  {
    code: 'target_evidence_trace_suggestion_column_present',
    passed: paymentVoucherPreviewText.includes('建议检查方向')
      && paymentVoucherPreviewText.includes('target-evidence-trace-suggestion-header')
      && paymentVoucherPreviewText.includes('target-evidence-trace-suggestion-cell')
      && paymentVoucherPreviewText.includes('targetEvidenceSuggestionDirection'),
  },
  {
    code: 'runtime_test_fixed_column_coordinates',
    passed: testText.includes('assertPaymentExecutionFixedColumns')
      && testText.includes('boundingBox()')
      && testText.includes('序号列滚动前、中、右 x 坐标必须稳定'),
  },
  {
    code: 'runtime_test_summary_chinese_cleanup',
    passed: testText.includes('assertPaymentVoucherPreviewChineseSummary')
      && testText.includes('目标证据摘要 DOM 文本不得隐藏技术词'),
  },
  {
    code: 'runtime_test_suggestion_column',
    passed: testText.includes('assertTargetEvidenceSuggestionColumn')
      && testText.includes('建议检查方向必须位于是否阻断之后'),
  },
  {
    code: 'trace_diagnostic_copy_fields',
    passed: shellText.includes('targetEvidenceTraceItems')
      && shellText.includes('targetEvidenceTraceCoveragePassed')
      && shellText.includes('targetEvidenceFirstFailureCode')
      && shellText.includes('targetEvidenceResponsibilitySummary'),
  },
  {
    code: 'trace_consistency_in_powershell',
    passed: psText.includes('target-evidence-trace-display-consistency')
      && psText.includes('target-evidence-trace-dom-consistency')
      && psText.includes('target-evidence-trace-copy-diagnostic'),
  },
]

const allChecks = [...checks, ...semanticChecks]
const failed = allChecks.filter((item) => !item.passed)

console.log(JSON.stringify({
  page: 'verifyBusinessRuntimeDisplayInvariants',
  version: 'V1.14.2.8',
  checks: allChecks,
  invariants: [
    '五种目标证据状态必须由统一分类器生成',
    'read_failed 与 not_found 不得混用',
    'conflict 与 incomplete 不得混用',
    '原始目标编号存在时显示模型必须保留原始编号',
    '冲突清单、读取失败明细和缺失证据必须可诊断',
    '目标证据来源链必须在页面主区域可见并使用单一原生横向滚动容器',
    '第一异常点、建议责任分类和来源链诊断必须与页面显示一致',
    '运行时数据、显示模型和 DOM 必须一致',
    '异常状态不得放行下一步',
  ],
  failedCount: failed.length,
  overall: failed.length ? 'failed' : 'passed',
}, null, 2))

if (failed.length) process.exit(1)

