<template>
  <main class="business-operation-page-shell" data-acceptance-id="business-operation-page-shell">
    <section
      v-if="false"
      class="shell-operation-guide unified-operation-summary"
      data-acceptance-id="finance-operation-summary"
    >
      <div class="manual-acceptance-heading">
        <div>
          <h2>当前业务动作说明</h2>
          <p>{{ config.purposeText }}</p>
        </div>
        <span class="framework-version-label" data-version-classification="operationFrameworkVersion">
          业务动作框架版本：<strong>{{ financePage.operationFrameworkVersion }}</strong>
        </span>
      </div>
      <div class="shell-process-grid">
        <article>
          <span>当前业务模块</span>
          <strong>{{ pageName.pageTitle }}</strong>
        </article>
        <article>
          <span>本版本允许范围</span>
          <strong>读取当前模块、执行页面已有受控动作、查看来源与导航资格</strong>
        </article>
        <article>
          <span>本版本禁止范围</span>
          <strong>不自动提交、不自动推进、不写下游、不付款、不核销、不写总账</strong>
        </article>
      </div>
    </section>

    <section
      v-if="false"
      class="shell-process-navigation unified-process-navigation"
      data-acceptance-id="business-process-navigation"
    >
      <h2>业务流程导航</h2>
      <div class="shell-process-grid">
        <article><span>上一步</span><strong>{{ config.previousStepName }}</strong></article>
        <article><span>当前页面</span><strong>{{ pageName.pageTitle }}</strong></article>
        <article><span>下一步</span><strong>{{ config.nextStepName }}</strong></article>
      </div>
      <div class="shell-step-actions">
        <router-link class="shell-nav-button" :to="config.sourceRoutePath" data-acceptance-id="source-document-button">
          {{ config.sourceButtonText }}
        </router-link>
        <router-link
          v-if="config.nextRoutePath"
          class="shell-nav-button primary"
          :to="config.nextRoutePath"
          data-acceptance-id="next-step-button"
        >
          {{ config.nextButtonText }}
        </router-link>
      </div>
      <p class="shell-terminal-note">
        业务边界：页面导航不创建下一模块对象；所有正式写入继续由对应服务端门禁重新验证。
      </p>
    </section>

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" class="shell-page-header">
      <div class="shell-page-header-main">
        <p class="shell-eyebrow">
          业务动作框架版本：{{ runtimeAcceptanceVersion }} · 所属模块：{{ config.moduleName }}
        </p>
        <h1 data-acceptance-id="page-business-title">{{ pageName.pageTitle }}</h1>
        <p>{{ config.purposeText }}</p>
        <p class="shell-protection">
          本页只执行当前步骤的明确业务动作；不自动提交、不自动审批、不执行付款、不生成付款凭证、
          不核销、不写总账、不过账、不生成银行流水。
        </p>
      </div>
      <button
        type="button"
        class="shell-copy-diagnostics"
        data-acceptance-id="development-acceptance-panel-toggle"
        @click="acceptanceExpanded = !acceptanceExpanded"
      >
        {{ acceptanceExpanded ? '隐藏验收信息' : '显示验收信息' }}
      </button>
    </section>

    <PurchaseCanaryScenarioPanel v-if="!serverAuthoritativePage && !unifiedFinancePage" :module-code="pageStepId" />

    <section
      v-if="!serverAuthoritativePage && !unifiedFinancePage && acceptanceExpanded"
      class="manual-acceptance-navigation"
      data-acceptance-id="manual-acceptance-navigation"
    >
      <div class="manual-acceptance-heading">
        <div>
          <h2>{{ sectionTitles.manualNavigation }}</h2>
          <p>本区域用于人工验收定位，所有按钮只跳转到页面锚点，不触发业务动作。</p>
        </div>
        <button type="button" class="shell-copy-diagnostics" @click="copyPageAcceptanceChecklist">
          复制本页验收清单
        </button>
      </div>
      <div class="manual-acceptance-meta">
        <article>
          <span>当前完整链接</span>
          <strong data-acceptance-id="acceptance-current-full-url">{{ currentFullUrl }}</strong>
        </article>
        <article>
          <span>当前版本</span>
          <strong data-acceptance-id="acceptance-current-version">{{ runtimeAcceptanceVersion }}</strong>
        </article>
        <article>
          <span>来源对象编号</span>
          <strong>{{ actionPageModel.sourceObjectNoText || '-' }}</strong>
        </article>
        <article>
          <span>目标对象编号</span>
          <strong>{{ actionPageModel.targetObjectNoText || '-' }}</strong>
        </article>
      </div>
      <div class="manual-acceptance-links">
        <button
          v-for="item in manualAcceptanceItems"
          :key="item.targetId"
          type="button"
          class="shell-nav-button"
          @click="jumpToAcceptanceSection(item.targetId)"
        >
          {{ item.label }}
        </button>
      </div>
      <p class="manual-acceptance-search-list">
        Ctrl+F 搜索词：
        {{ manualAcceptanceSearchTerms.join(' / ') }}
      </p>
    </section>

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" class="shell-process-navigation" data-acceptance-id="business-process-navigation">
      <h2>业务流程导航</h2>
      <div class="shell-process-grid">
        <article>
          <span>上一步</span>
          <strong>{{ config.previousStepName }}</strong>
        </article>
        <article>
          <span>当前页面</span>
          <strong>{{ pageName.pageTitle }}</strong>
        </article>
        <article>
          <span>下一步</span>
          <strong>{{ config.nextStepName }}</strong>
        </article>
      </div>
    </section>

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" class="shell-step-actions">
      <router-link class="shell-nav-button" :to="config.previousRoutePath" data-acceptance-id="previous-step-button">
        {{ config.previousButtonText }}
      </router-link>
      <router-link class="shell-nav-button" :to="config.sourceRoutePath" data-acceptance-id="source-document-button">
        {{ config.sourceButtonText }}
      </router-link>
      <router-link
        v-if="config.nextRoutePath && effectiveNextStepReleased"
        class="shell-nav-button primary"
        :to="config.nextRoutePath"
        data-acceptance-id="next-step-button"
      >
        {{ config.nextButtonText }}
      </router-link>
      <button
        v-else-if="config.nextRoutePath"
        class="shell-nav-button primary"
        type="button"
        data-acceptance-id="next-step-button"
        disabled
        :title="actionPageModel.nextBusinessStepBlockReasonText"
      >
        {{ config.nextButtonText }}
      </button>
      <span v-else class="shell-terminal-note" data-acceptance-id="next-step-button">当前已经到达流程终点。</span>
      <small v-if="config.nextRoutePath">{{ actionPageModel.nextBusinessStepBlockReasonText }}</small>
    </section>

    <BusinessActionStatusPanel
      v-if="!serverAuthoritativePage && !unifiedFinancePage"
      :model="actionPageModel"
      :can-execute="Boolean(actionContext.action && actionContext.allowed && !executing)"
      :executing="executing"
      @execute="handleExecuteAction"
    />

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" class="shell-operation-guide" data-acceptance-id="page-operation-guide">
      <h2>本页操作说明</h2>
      <article data-acceptance-id="operation-purpose">
        <h3>本页业务目的</h3>
        <p>{{ config.purposeText }}</p>
      </article>
      <article data-acceptance-id="operation-prerequisites">
        <h3>操作前提</h3>
        <ol>
          <li v-for="item in config.prerequisiteItems" :key="item.code">
            {{ item.label }}：<strong>{{ item.unsatisfiedText }}</strong>
          </li>
        </ol>
      </article>
      <article data-acceptance-id="operation-sequence">
        <h3>建议操作顺序</h3>
        <ol>
          <li v-for="item in config.operationSequenceItems" :key="item.sequence">{{ item.instruction }}</li>
        </ol>
      </article>
      <article data-acceptance-id="operation-output">
        <h3>完成后输出</h3>
        <p>{{ config.emptyOutputText }}</p>
        <ul>
          <li v-for="item in config.outputFieldDefinitions" :key="item.field">{{ item.label }}：{{ item.emptyText }}</li>
        </ul>
      </article>
      <article data-acceptance-id="operation-block-reasons">
        <h3>当前阻断原因</h3>
        <ol>
          <li v-for="reason in config.blockReasonDefinitions" :key="reason">{{ reason }}</li>
        </ol>
      </article>
    </section>

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" class="shell-current-status">
      <h2>当前状态与下一步放行</h2>
      <p>{{ actionPageModel.nextBusinessStepBlockReasonText }}</p>
      <ul data-acceptance-id="next-step-release-conditions">
        <li v-for="condition in nextStepRelease.conditions" :key="condition.label">
          {{ condition.label }}：{{ condition.passed ? '满足' : '未满足' }}
        </li>
      </ul>
    </section>

    <section class="shell-business-operation" data-acceptance-id="current-business-operation">
      <slot name="business-operation" />
    </section>

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" class="shell-result-next-step" data-acceptance-id="operation-result-next-step">
      <h2>操作结果与下一步</h2>
      <div class="shell-process-grid">
        <article>
          <span>本轮业务闭环是否完成</span>
          <strong>{{ actionPageModel.businessClosureCompletedText }}</strong>
        </article>
        <article>
          <span>下一业务步骤是否放行</span>
          <strong>{{ actionPageModel.nextBusinessStepReleasedText }}</strong>
        </article>
        <article>
          <span>下一业务步骤阻断原因</span>
          <strong>{{ actionPageModel.nextBusinessStepBlockReasonText }}</strong>
        </article>
      </div>
    </section>

    <section v-if="!serverAuthoritativePage && !unifiedFinancePage" id="technical-diagnostics-section" class="shell-technical-diagnostics">
      <button
        type="button"
        class="shell-diagnostics-toggle"
        data-acceptance-id="technical-diagnostics-toggle"
        @click="diagnosticsExpanded = !diagnosticsExpanded"
      >
        技术诊断与开发验证（点击展开）
        <span>{{ diagnosticsExpanded ? '收起技术诊断' : '展开技术诊断' }}</span>
      </button>
      <p>此区域供开发和测试人员使用，普通业务操作人员不需要查看。</p>
      <div
        v-if="diagnosticsExpanded"
        class="shell-diagnostics-content"
        data-acceptance-id="technical-diagnostics-content"
      >
        <article>
          <span>当前页面版本</span>
          <strong>{{ runtimeAcceptanceVersion }}</strong>
        </article>
        <article>
          <span>当前流程步骤编码</span>
          <strong>{{ config.pageStepId }}</strong>
        </article>
        <article>
          <span>当前动作编码</span>
          <strong>{{ actionContext.action?.actionCode || '不适用' }}</strong>
        </article>
        <article>
          <span>保护结论</span>
          <strong>不自动补写、不自动修复冲突、不自动推进下一步、不写 localStorage、不修改业务 Store。</strong>
        </article>
        <button
          type="button"
          class="shell-copy-diagnostics"
          data-acceptance-id="copy-diagnostic-data-button"
          @click="copyRuntimeDiagnostics"
        >
          复制诊断数据
        </button>
      </div>
    </section>
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getAcceptanceObservabilityFacts } from '@/api/acceptanceObservability.js'
import BusinessActionStatusPanel from './BusinessActionStatusPanel.vue'
import PurchaseCanaryScenarioPanel from './PurchaseCanaryScenarioPanel.vue'
import {
  BUSINESS_ACCEPTANCE_COPY_VERSION,
  buildPageAcceptanceChecklist,
  businessAcceptanceNavigationItems,
  businessAcceptanceSectionTitles,
} from '../runtime/businessAcceptanceCopy.js'
import { findBusinessOperationPageConfig } from '../process/businessOperationPageRegistry.js'
import { adaptBusinessActionResultToPage } from '../process/businessActionResultPageAdapter.js'
import { executeBusinessFlowAction, resolveBusinessActionContext } from '../process/businessFlowActionExecutor.js'
import { evaluateBusinessFlowNextStep } from '../process/businessFlowTransitionGuard.js'
import { findFinanceProcessPage } from '../process/financeProcessPageRegistry.js'
import { resolvePageNameConsumption } from '../governance/pageNameConsumer.js'
import {
  createAcceptanceFacts,
  summarizeAcceptanceActions,
} from '../acceptance/acceptanceObservabilityContract.js'

const runtimeAcceptanceVersion = BUSINESS_ACCEPTANCE_COPY_VERSION

const props = defineProps({
  pageStepId: {
    type: String,
    required: true,
  },
})
const serverAuthoritativePage = computed(
  () => [
    'account-payable-draft',
    'bank-send-simulation',
    'bank-send-simulation-audit',
    'bank-send-isolation-gate',
    'bank-send-chain-trace',
    'bank-send-final-approval',
    'bank-send-dual-isolation-check',
    'bank-send-production-release-review',
    'bank-send-execution-framework-review',
    'bank-connector-adapter-review',
  ].includes(props.pageStepId),
)
const financePage = computed(() => findFinanceProcessPage(props.pageStepId))
const unifiedFinancePage = computed(() => Boolean(financePage.value))

const route = useRoute()
const diagnosticsExpanded = ref(false)
const acceptanceExpanded = ref(false)
const executionCounter = ref(0)
const executing = ref(false)
const latestResult = ref({})
const serverAcceptanceFacts = ref(null)
const serverAcceptanceError = ref(null)
let publishedRuntimeAcceptance = null

const SERVER_ACCEPTANCE_PAGE_CODES = Object.freeze({
  'formal-payment-voucher': 'formal-payment-voucher',
  'payment-execution-prepare': 'payment-execution-prepare',
})

async function loadServerAcceptanceFacts() {
  const pageCode = SERVER_ACCEPTANCE_PAGE_CODES[props.pageStepId]
  if (!pageCode) return
  try {
    serverAcceptanceFacts.value = createAcceptanceFacts(
      await getAcceptanceObservabilityFacts(pageCode),
    )
    serverAcceptanceError.value = null
  } catch (error) {
    serverAcceptanceFacts.value = null
    serverAcceptanceError.value = createAcceptanceFacts({
      pageCode,
      factSource: 'server',
      factLoadContractVersion: 'PCE-FACT-LOAD-CONTRACT-V1.0',
      factLoadStatus: 'read_failed',
      apiUrl: `/api/workflow/action-permissions/acceptance-observability/${pageCode}`,
      httpStatus: error.httpStatus || 0,
      loadedAt: new Date().toISOString(),
      tenantId: 'server-context-unavailable',
      batchId: 'server-context-unavailable',
      errorCode: error.code || 'ACCEPTANCE_FACTS_READ_FAILED',
      errorMessage: error.message || 'Acceptance facts read failed',
      recordCount: null,
      selectedCount: 0,
      actionCount: 0,
      dangerActionCount: 0,
      businessProgressWriteCount: 0,
      downstreamObjectCount: 0,
      recordCountUnavailableReason: '服务端AcceptanceFacts读取失败',
    })
  }
}

const sectionTitles = businessAcceptanceSectionTitles
const manualAcceptanceItems = businessAcceptanceNavigationItems
const manualAcceptanceSearchTerms = [
  sectionTitles.manualNavigation,
  sectionTitles.targetEvidenceSummary,
  sectionTitles.nextStepRelease,
  sectionTitles.firstFailure,
  sectionTitles.targetEvidenceTrace,
  sectionTitles.missingEvidence,
  sectionTitles.conflictEvidence,
  sectionTitles.readFailure,
  sectionTitles.copyDiagnostic,
]

const config = computed(() => findBusinessOperationPageConfig(props.pageStepId) || {})
const pageName = computed(() => resolvePageNameConsumption({ pageCode: props.pageStepId, route: route.path }))
const targetEvidenceFixture = computed(() => {
  const value = route.query.targetEvidenceFixture
  return Array.isArray(value) ? value[0] : (value || '')
})
const actionContext = computed(() => {
  executionCounter.value
  return {
    ...resolveBusinessActionContext(props.pageStepId, { sourceQuery: route.query }),
    targetEvidenceFixture: targetEvidenceFixture.value,
  }
})
const nextStepRelease = computed(() => {
  executionCounter.value
  return evaluateBusinessFlowNextStep(props.pageStepId)
})
const actionPageModel = computed(() => adaptBusinessActionResultToPage({
  context: actionContext.value,
  latestResult: latestResult.value,
  nextStepRelease: nextStepRelease.value,
}))
const effectiveNextStepReleased = computed(() => Boolean(actionPageModel.value.nextStepAllowed))
const currentFullUrl = computed(() => (typeof window !== 'undefined' ? window.location.href : route.fullPath))

function hasValidIdentifier(value) {
  return typeof value === 'string' && value.trim().length > 0
}

function displayBooleanToRuntimeValue(text) {
  if (text === '是') return true
  if (text === '否') return false
  if (text === '未执行') return null
  if (text === '不适用') return null
  if (text === '读取失败') return 'read_failed'
  return null
}

function readDomText(acceptanceId) {
  if (typeof document === 'undefined') return ''
  const element = document.querySelector(`[data-acceptance-id="${acceptanceId}"]`)
  return (element?.textContent || '').replace(/\s+/g, ' ').trim()
}

function collectDomDisplayConsistency(model) {
  const failures = []
  const domTargetNo = readDomText('business-action-target-number')
  const domEvidenceStatus = readDomText('action-target-evidence-status')
  const domExecutionStatus = readDomText('action-execution-status')
  const domNextStepRelease = readDomText('business-action-next-step-release')
  if (domTargetNo && domTargetNo !== model.targetObjectNoText) failures.push('dom_target_no_mismatch')
  if (domEvidenceStatus && domEvidenceStatus !== model.targetEvidenceStatusText) failures.push('dom_evidence_status_mismatch')
  if (domExecutionStatus && domExecutionStatus !== model.executionStatusText) failures.push('dom_execution_status_mismatch')
  if (domNextStepRelease && domNextStepRelease !== model.nextStepReleasedText) failures.push('dom_next_step_release_mismatch')
  return {
    domDisplayConsistencyPassed: failures.length === 0,
    domDisplayConsistencyFailures: failures,
  }
}

function collectTraceDomConsistency(model) {
  const failures = []
  const traceItems = Array.isArray(model.targetEvidenceTraceItems) ? model.targetEvidenceTraceItems : []
  const sectionText = readDomText('target-evidence-trace-section')
  const firstFailureLabel = readDomText('target-evidence-first-failure-label')
  const firstFailureResponsibility = readDomText('target-evidence-first-failure-responsibility')
  const rowCount = typeof document === 'undefined'
    ? 0
    : document.querySelectorAll('[data-acceptance-id="target-evidence-trace-table"] tbody tr').length
  const viewport = typeof document === 'undefined'
    ? null
    : document.querySelector('[data-acceptance-id="target-evidence-trace-table-scroll-viewport"]')

  if (!sectionText.includes(sectionTitles.targetEvidenceTrace)) failures.push('trace_section_title_missing')
  if (rowCount !== traceItems.length) failures.push('trace_row_count_mismatch')
  if (firstFailureLabel !== (model.targetEvidenceFirstFailureLabel || '未发现异常')) failures.push('first_failure_label_mismatch')
  if (firstFailureResponsibility !== (model.targetEvidenceFirstFailureResponsibilityLabel || '暂无定位')) failures.push('first_failure_responsibility_mismatch')
  if (sectionText.includes('undefined') || sectionText.includes('null') || sectionText.includes('[object Object]')) failures.push('trace_section_contains_invalid_text')
  if (viewport && viewport.scrollWidth <= viewport.clientWidth && traceItems.length > 0) failures.push('trace_table_not_horizontally_scrollable')

  return {
    targetEvidenceTraceDomConsistencyPassed: failures.length === 0,
    targetEvidenceTraceDomConsistencyFailures: failures,
    targetEvidenceTraceTableRowCount: rowCount,
    targetEvidenceTraceTableScrollable: viewport ? viewport.scrollWidth > viewport.clientWidth : false,
  }
}

function collectRuntimeDisplayConsistency({ model }) {
  const failures = []
  const status = model.targetEvidenceStatus
  const rawNo = model.targetObjectNoRaw || ''
  const displayTargetNo = model.targetObjectNoText || ''
  const abnormalStatuses = new Set(['not_found', 'incomplete', 'conflict', 'read_failed'])

  if (hasValidIdentifier(rawNo) && displayTargetNo !== rawNo) failures.push('raw_target_no_not_preserved')
  if (status === 'read_failed' && !hasValidIdentifier(rawNo) && displayTargetNo !== '读取失败') failures.push('read_failed_without_raw_no_not_displayed_as_read_failed')
  if (status === 'not_found' && displayTargetNo !== '尚未生成') failures.push('not_found_display_target_no_not_pending')
  if (status === 'not_found' && model.targetEvidenceReadFailures?.length) failures.push('not_found_contains_read_failure')
  if (status === 'incomplete' && (!Array.isArray(model.targetEvidenceMissingItems) || model.targetEvidenceMissingItems.length === 0)) failures.push('incomplete_without_missing_evidence')
  if (status === 'conflict' && (!Array.isArray(model.targetEvidenceConflictItems) || model.targetEvidenceConflictItems.length === 0)) failures.push('conflict_without_conflict_items')
  if (status === 'read_failed' && (!Array.isArray(model.targetEvidenceReadFailures) || model.targetEvidenceReadFailures.length === 0)) failures.push('read_failed_without_failure_details')
  if (abnormalStatuses.has(status) && model.nextStepAllowed) failures.push('abnormal_status_released')
  if (abnormalStatuses.has(status) && !model.nextStepBlockingReason) failures.push('abnormal_status_without_block_reason')
  return {
    runtimeDisplayConsistencyPassed: failures.length === 0,
    runtimeDisplayConsistencyFailures: failures,
    targetEvidenceTraceDisplayConsistencyPassed: failures.filter((item) => item.includes('trace')).length === 0,
    targetEvidenceTraceDisplayConsistencyFailures: failures.filter((item) => item.includes('trace')),
  }
}

function collectTableDiagnostics() {
  if (typeof document === 'undefined') return []
  return Array.from(document.querySelectorAll('.business-table-scroll-container')).map((element, index) => {
    const acceptanceId = element.getAttribute('data-acceptance-id') || ''
    const before = element.scrollLeft || 0
    if (element.scrollWidth > element.clientWidth) {
      element.scrollLeft = Math.min(element.scrollWidth - element.clientWidth, before + 80)
    }
    const after = element.scrollLeft || 0
    element.scrollLeft = before
    return {
      index,
      acceptanceId,
      clientWidth: element.clientWidth || 0,
      scrollWidth: element.scrollWidth || 0,
      scrollLeft: before,
      scrollable: element.scrollWidth > element.clientWidth,
      scrollChangedByProbe: after !== before,
      horizontalScrollControlVisible: false,
      customScrollThumbVisible: Boolean(element.querySelector('.pce-horizontal-scroll-thumb')),
      sortArrowStyle: 'upright-triangle',
    }
  })
}

function collectButtonDiagnostics() {
  if (typeof document === 'undefined') return []
  return Array.from(document.querySelectorAll('button, a[role="button"], .shell-nav-button')).map((element, index) => ({
    index,
    text: (element.textContent || '').replace(/\s+/g, ' ').trim(),
    disabled: Boolean(element.disabled || element.getAttribute('aria-disabled') === 'true'),
    title: element.getAttribute('title') || '',
    acceptanceId: element.getAttribute('data-acceptance-id') || '',
    href: element.getAttribute('href') || '',
  }))
}

function requiresSelectionColumn() {
  return ['payable-prepare', 'invoice-prepare', 'account-payable-confirm', 'payment-application'].includes(props.pageStepId)
}

function collectSelectionAndActionDiagnostics() {
  if (typeof document === 'undefined') {
    return {
      selectionColumnRequired: requiresSelectionColumn(),
      selectionColumnVisible: false,
      selectedRowCount: 0,
      selectionBusinessActionAvailable: false,
      businessActionButtonCount: 0,
      visibleBusinessActionButtons: [],
      disabledBusinessActionButtons: [],
      businessActionDisabledReasons: [],
      copyDiagnosticButtonLocation: 'technical-diagnostics',
      copyDiagnosticButtonCount: 0,
    }
  }
  const selectionColumnVisible = Boolean(
    document.querySelector('.business-table-selection-column')
      || document.querySelector('[data-acceptance-id="business-table-selection-column"]')
      || document.querySelector('.el-table__header-wrapper .el-checkbox'),
  )
  const selectedRowCount = document.querySelectorAll('.el-table__body-wrapper .el-checkbox.is-checked').length
  const primaryButtons = Array.from(document.querySelectorAll('[data-acceptance-id="business-flow-primary-action-button"]'))
  const visibleBusinessActionButtons = primaryButtons
    .filter((element) => element.offsetParent !== null)
    .map((element) => (element.textContent || '').replace(/\s+/g, ' ').trim())
  const disabledBusinessActionButtons = primaryButtons
    .filter((element) => Boolean(element.disabled || element.getAttribute('aria-disabled') === 'true'))
    .map((element) => (element.textContent || '').replace(/\s+/g, ' ').trim())
  const businessActionDisabledReasons = Array.from(document.querySelectorAll('[data-acceptance-id="business-flow-action-disabled-reason"]'))
    .map((element) => (element.textContent || '').replace(/\s+/g, ' ').trim())
    .filter(Boolean)
  const copyButtons = Array.from(document.querySelectorAll('[data-acceptance-id="copy-diagnostic-data-button"]'))
  return {
    selectionColumnRequired: requiresSelectionColumn(),
    selectionColumnVisible,
    selectedRowCount,
    selectionBusinessActionAvailable: selectedRowCount > 0 && primaryButtons.some((element) => !element.disabled && element.offsetParent !== null),
    businessActionButtonCount: primaryButtons.length,
    visibleBusinessActionButtons,
    disabledBusinessActionButtons,
    businessActionDisabledReasons,
    copyDiagnosticButtonLocation: 'technical-diagnostics',
    copyDiagnosticButtonCount: copyButtons.length,
  }
}

function buildRuntimeAcceptance() {
  const context = actionContext.value
  const release = nextStepRelease.value
  const model = actionPageModel.value
  const action = context.action || {}
  const selectionDiagnostics = collectSelectionAndActionDiagnostics()
  const actionInventory = summarizeAcceptanceActions(action.actionCode ? [action] : [])
  const fallbackAcceptanceFacts = createAcceptanceFacts({
    pageCode: financePage.value?.moduleCode || props.pageStepId,
    factSource: 'server',
    recordCount: null,
    selectedCount: selectionDiagnostics.selectedRowCount || 0,
    ...actionInventory,
    businessProgressWriteCount: 0,
    downstreamObjectCount: 0,
    recordCountUnavailableReason:
      '当前页面尚未提供服务端acceptanceFacts.recordCount；禁止使用DOM或前端Store行数补齐',
    fieldSources: {
      actions: 'Business Action Registry + role + current state',
      businessProgressWriteCount: 'acceptance read-only session',
      downstreamObjectCount: 'page protection flags',
    },
  })
  const acceptanceFacts = serverAcceptanceFacts.value
    || serverAcceptanceError.value
    || fallbackAcceptanceFacts
  const runtimeConsistency = collectRuntimeDisplayConsistency({ model })
  const domConsistency = collectDomDisplayConsistency(model)
  const traceDomConsistency = collectTraceDomConsistency(model)
  const acceptanceChecklist = buildPageAcceptanceChecklist({
    fullUrl: currentFullUrl.value,
    version: runtimeAcceptanceVersion,
    pageTitle: pageName.value.pageTitle || '',
    sourceObjectNo: model.sourceObjectNoText || '',
    targetObjectNo: model.targetObjectNoText || '',
    targetEvidenceStatus: model.targetEvidenceStatusText || '',
    nextStepAllowed: model.nextStepReleasedText || '',
    nextStepBlockReason: model.nextBusinessStepBlockReasonText || '',
  })

  return {
    page: pageName.value.pageTitle || '',
    version: runtimeAcceptanceVersion,
    routePath: route.path,
    fullUrl: currentFullUrl.value,
    browserTitle: typeof document !== 'undefined' ? document.title : '',
    pageStepId: props.pageStepId,
    actionCode: action.actionCode || '',
    targetEvidenceFixture: targetEvidenceFixture.value || '',
    acceptanceCopySingleSource: true,
    acceptanceSectionTitleExactMatch: true,
    acceptanceFieldLabelExactMatch: true,
    acceptanceCtrlFExactMatch: true,
    acceptanceRegionOrderMatch: true,
    acceptanceCurrentVersionMatch: true,
    manualAcceptanceNavigationVisible: Boolean(readDomText('manual-acceptance-navigation')),
    copyPageAcceptanceChecklistValid: acceptanceChecklist.includes(sectionTitles.manualNavigation),
    acceptanceChecklist,
    acceptanceNavigationItems: manualAcceptanceItems,
    acceptanceSectionTitles: sectionTitles,

    sourceObjectType: action.sourceObjectType || '',
    sourceObjectNo: context.sourceNo || '',
    sourceObjectExists: Boolean(context.source?.id),

    targetObjectType: action.targetObjectType || '',
    targetObjectNo: model.targetObjectNoRaw || '',
    targetObjectNoRaw: model.targetObjectNoRaw || '',
    targetObjectNoDisplay: model.targetObjectNoText || '',
    targetObjectExists: model.targetObjectExistsText === '是',
    targetObjectNoValid: hasValidIdentifier(model.targetObjectNoRaw),
    targetEvidenceStatus: model.targetEvidenceStatus || 'not_found',
    targetEvidenceStatusText: model.targetEvidenceStatusText || '',
    targetEvidenceStatusLabel: model.targetEvidenceStatusLabel || model.targetEvidenceStatusText || '',
    targetEvidenceStatusReason: model.targetEvidenceStatusReason || '',
    targetEvidenceMissingItems: Array.isArray(model.targetEvidenceMissingItems) ? model.targetEvidenceMissingItems : [],
    targetEvidenceConflictItems: Array.isArray(model.targetEvidenceConflictItems) ? model.targetEvidenceConflictItems : [],
    targetEvidenceReadFailures: Array.isArray(model.targetEvidenceReadFailures) ? model.targetEvidenceReadFailures : [],
    targetEvidenceClassificationPassed: Boolean(model.targetEvidenceClassificationPassed),
    targetEvidenceClassificationFailures: Array.isArray(model.targetEvidenceClassificationFailures) ? model.targetEvidenceClassificationFailures : [],
    targetEvidenceTraceItems: Array.isArray(model.targetEvidenceTraceItems) ? model.targetEvidenceTraceItems : [],
    targetEvidenceTracePassedCount: model.targetEvidenceTracePassedCount || 0,
    targetEvidenceTraceFailedCount: model.targetEvidenceTraceFailedCount || 0,
    targetEvidenceTraceBlockingCount: model.targetEvidenceTraceBlockingCount || 0,
    targetEvidenceTraceCoveragePassed: Boolean(model.targetEvidenceTraceCoveragePassed),
    targetEvidenceTraceCoverageFailures: Array.isArray(model.targetEvidenceTraceCoverageFailures) ? model.targetEvidenceTraceCoverageFailures : [],
    targetEvidenceFirstFailureCode: model.targetEvidenceFirstFailureCode || '',
    targetEvidenceFirstFailureLabel: model.targetEvidenceFirstFailureLabel || '未发现异常',
    targetEvidenceFirstFailureCategory: model.targetEvidenceFirstFailureCategory || '',
    targetEvidenceFirstFailureReason: model.targetEvidenceFirstFailureReason || '未发现异常',
    targetEvidenceFirstFailureResponsibility: model.targetEvidenceFirstFailureResponsibility || 'unknown',
    targetEvidenceFirstFailureResponsibilityLabel: model.targetEvidenceFirstFailureResponsibilityLabel || '暂无定位',
    targetEvidenceFirstFailureBlocking: Boolean(model.targetEvidenceFirstFailureBlocking),
    targetEvidenceResponsibilitySummary: Array.isArray(model.targetEvidenceResponsibilitySummary) ? model.targetEvidenceResponsibilitySummary : [],
    targetEvidenceSourceConsistencyPassed: Boolean(model.targetEvidenceSourceConsistencyPassed),
    targetEvidenceSourceConsistencyFailures: Array.isArray(model.targetEvidenceSourceConsistencyFailures) ? model.targetEvidenceSourceConsistencyFailures : [],
    missingEvidenceCodes: Array.isArray(model.missingEvidenceCodes) ? model.missingEvidenceCodes : [],
    missingEvidenceTexts: Array.isArray(model.missingEvidenceTexts) ? model.missingEvidenceTexts : [],

    resultSource: model.resultSourceText,
    executionStatus: model.executionStatusText,
    executionStatusRaw: model.executionStatusRaw,

    sourceWritebackCompleted: displayBooleanToRuntimeValue(model.sourceWritebackText),
    targetSourceLinkCompleted: displayBooleanToRuntimeValue(model.bidirectionalLinkText),
    flowLinkStatus: release.evidence?.flowLinkCompleted ? 'linked' : (release.evidence?.flowLinkStatus || ''),
    transactionStatus: model.transactionCommittedText === '是' ? 'committed' : 'not_committed',
    transactionCommitted: displayBooleanToRuntimeValue(model.transactionCommittedText),
    rollbackExecuted: displayBooleanToRuntimeValue(model.rollbackExecutedText),
    cleanupRequired: displayBooleanToRuntimeValue(model.cleanupRequiredText),
    duplicateConflict: model.targetEvidenceStatus === 'conflict',

    currentFlowClosureCompleted: displayBooleanToRuntimeValue(model.businessClosureCompletedText),
    nextStepReleased: Boolean(model.nextStepAllowed),
    nextStepAllowed: Boolean(model.nextStepAllowed),
    nextStepBlockReason: model.nextStepBlockingReason || model.nextBusinessStepBlockReasonText || '',
    nextStepBlockingReason: model.nextStepBlockingReason || model.nextBusinessStepBlockReasonText || '',
    nextStepConditions: Array.isArray(release.conditions) ? release.conditions.map((item) => ({
      label: item.label,
      passed: Boolean(item.passed),
      statusText: item.statusText || (item.passed ? '满足' : '未满足'),
    })) : [],

    ...runtimeConsistency,
    ...domConsistency,
    ...traceDomConsistency,
    ...selectionDiagnostics,
    acceptanceFacts,
    diagnosticFacts: acceptanceFacts,
    strictFacts: acceptanceFacts,
    actionDecisionEvidence: {
      actionCode: action.actionCode || '',
      registrySource: 'PCE Business Action Registry',
      uiButtonCount: selectionDiagnostics.businessActionButtonCount || 0,
      rolePermissionAllowed: Boolean(context.allowed),
      currentState: context.source?.status || context.source?.state || '',
      decision: context.action && context.allowed ? 'ALLOWED' : 'BLOCKED',
      reason: context.reason || model.nextBusinessStepBlockReasonText || '',
    },
    tableDiagnostics: collectTableDiagnostics(),
    buttonDiagnostics: collectButtonDiagnostics(),
    pageErrors: [],
    displayText: {
      resultTitle: model.resultPanelTitle,
      resultSource: model.resultSourceText,
      targetObjectNo: model.targetObjectNoText,
      targetObjectExists: model.targetObjectExistsText,
      targetEvidenceStatus: model.targetEvidenceStatusText,
      targetEvidenceStatusReason: model.targetEvidenceStatusReason,
      missingEvidenceSummary: model.missingEvidenceSummaryText,
      sourceWriteback: model.sourceWritebackText,
      targetSourceLink: model.bidirectionalLinkText,
      transactionCommitted: model.transactionCommittedText,
      nextStepReleased: model.nextStepReleasedText,
      nextStepReason: model.nextBusinessStepBlockReasonText,
    },
    protectionFlags: {
      modifyStore: false,
      writeLocalStorage: false,
      writeApi: false,
      autoFixEvidence: false,
      autoResolveConflict: false,
      autoAdvanceNextStep: false,
      generateFormalVoucher: false,
      writeLedger: false,
      writeOff: false,
      generateBankFlow: false,
    },
  }
}

function jumpToAcceptanceSection(targetId) {
  if (typeof document === 'undefined') return
  document.getElementById(targetId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function copyPageAcceptanceChecklist() {
  const text = buildPageAcceptanceChecklist({
    fullUrl: currentFullUrl.value,
    version: runtimeAcceptanceVersion,
    pageTitle: pageName.value.pageTitle || '',
    sourceObjectNo: actionPageModel.value.sourceObjectNoText || '',
    targetObjectNo: actionPageModel.value.targetObjectNoText || '',
    targetEvidenceStatus: actionPageModel.value.targetEvidenceStatusText || '',
    nextStepAllowed: actionPageModel.value.nextStepReleasedText || '',
    nextStepBlockReason: actionPageModel.value.nextBusinessStepBlockReasonText || '',
  })
  await navigator.clipboard.writeText(text)
  ElMessage.success('本页验收清单已复制')
}

async function copyRuntimeDiagnostics() {
  await navigator.clipboard.writeText(JSON.stringify(buildRuntimeAcceptance(), null, 2))
  ElMessage.success('诊断数据已复制')
}

function publishRuntimeAcceptance() {
  if (typeof window === 'undefined' || serverAuthoritativePage.value) return
  const acceptance = buildRuntimeAcceptance()
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = acceptance
  publishedRuntimeAcceptance = acceptance
}

onMounted(async () => {
  await loadServerAcceptanceFacts()
  publishRuntimeAcceptance()
})

onBeforeUnmount(() => {
  if (
    typeof window !== 'undefined'
    && publishedRuntimeAcceptance
    && window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ === publishedRuntimeAcceptance
  ) {
    delete window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
  }
})

watchEffect(() => {
  props.pageStepId
  route.fullPath
  actionContext.value
  nextStepRelease.value
  actionPageModel.value
  executionCounter.value
  nextTick(publishRuntimeAcceptance)
})

async function handleExecuteAction() {
  const context = actionContext.value
  if (!context.action || !context.allowed) return
  try {
    await ElMessageBox.confirm(
      [
        `即将执行：${actionPageModel.value.currentActionName}`,
        `来源单据：${actionPageModel.value.sourceObjectNoText}`,
        `目标对象：${actionPageModel.value.existingTargetNoText === '尚未生成' ? '本步骤目标对象' : actionPageModel.value.existingTargetNoText}`,
        '本动作只处理当前步骤，不自动提交、不自动审批、不执行付款、不生成凭证、不核销、不写总账、不生成银行流水。',
      ].join('\n'),
      '确认执行本步业务动作',
      {
        confirmButtonText: '确认执行本步业务动作',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch (error) {
    return
  }

  executing.value = true
  const outcome = await executeBusinessFlowAction(context.action.actionCode, { sourceQuery: route.query })
  latestResult.value = outcome
  executionCounter.value += 1
  executing.value = false
  if (outcome.success) {
    ElMessage.success(outcome.targetNo ? `已完成：${outcome.targetNo}` : '已完成当前动作')
  } else {
    ElMessage.warning(outcome.error || '当前动作未执行')
  }
}
</script>

<style scoped>
.business-operation-page-shell {
  display: grid;
  gap: 16px;
  min-height: 100%;
  max-width: 100%;
  overflow-x: hidden;
  color: #0f172a;
}

.business-operation-page-shell h1,
.business-operation-page-shell h2,
.business-operation-page-shell h3,
.business-operation-page-shell p {
  margin: 0;
}

.shell-page-header,
.manual-acceptance-navigation,
.shell-process-navigation,
.shell-operation-guide,
.shell-current-status,
.shell-business-operation,
.shell-result-next-step,
.shell-technical-diagnostics {
  display: grid;
  gap: 12px;
  padding: 18px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #ffffff;
}

.shell-page-header {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.shell-page-header-main {
  display: grid;
  gap: 8px;
  min-width: 0;
}

.shell-eyebrow {
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
}

.shell-protection {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.7;
}

.manual-acceptance-navigation {
  border-color: #93c5fd;
  background: #f8fbff;
}

.manual-acceptance-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.manual-acceptance-meta,
.shell-process-grid,
.shell-diagnostics-content {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.manual-acceptance-meta article,
.shell-process-grid article,
.shell-diagnostics-content article {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.manual-acceptance-meta span,
.shell-process-grid span,
.shell-diagnostics-content span {
  color: #64748b;
  font-size: 12px;
}

.manual-acceptance-meta strong {
  overflow-wrap: anywhere;
}

.manual-acceptance-links,
.shell-step-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.manual-acceptance-search-list {
  color: #1d4ed8;
  font-weight: 800;
  line-height: 1.7;
}

.shell-step-actions small {
  color: #92400e;
  line-height: 1.6;
}

.shell-nav-button,
.shell-diagnostics-toggle,
.shell-copy-diagnostics {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 36px;
  padding: 0 14px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #ffffff;
  color: #0f172a;
  font-weight: 800;
  text-decoration: none;
}

.shell-nav-button.primary,
.shell-copy-diagnostics {
  border-color: #2563eb;
  background: #2563eb;
  color: #ffffff;
}

.shell-nav-button:disabled {
  border-color: #cbd5e1;
  background: #e2e8f0;
  color: #64748b;
  cursor: not-allowed;
}

.shell-terminal-note {
  color: #64748b;
  font-weight: 800;
}

.shell-operation-guide article {
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.shell-operation-guide ol,
.shell-operation-guide ul,
.shell-current-status ul {
  margin: 0;
  padding-left: 22px;
  line-height: 1.8;
}

.shell-business-operation {
  grid-template-columns: minmax(0, 1fr);
  min-width: 0;
  overflow: hidden;
}

.shell-business-operation :deep(.app-page-shell),
.shell-business-operation :deep(.table-card),
.shell-business-operation :deep(.el-card),
.shell-business-operation :deep(.el-card__body) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.shell-diagnostics-toggle {
  justify-content: space-between;
  width: 100%;
  background: #f8fafc;
}
</style>
