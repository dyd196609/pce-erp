<template>
  <main
    class="pce-list-page-shell"
    data-acceptance-id="pce-list-page-shell"
    data-pce-shell-type="PceListPageShell"
    data-pce-page-container-rule="LIST-RUNTIME-001"
    :data-enforcement-mode="acceptanceContract?.enforcementMode || 'audit'"
    :data-acceptance-level="acceptanceContract?.acceptanceLevel || 0"
    :data-contract-version="acceptanceContract?.contractVersion || ''"
  >
    <header
      v-if="!props.compactEmployeeView"
      class="pce-list-page-header"
      data-acceptance-id="page-identity-region"
    >
      <div class="pce-version-classification">
        <span data-version-classification="runtimeBusinessVersion">当前版本：<strong>{{ governedPage?.version || financePage?.runtimeBusinessVersion || '未分类' }}</strong></span>
        <span data-version-classification="pageFrameworkVersion">页面框架版本：<strong>{{ governedPage?.frameworkVersion || version }}</strong></span>
      </div>
      <div class="pce-page-identity-fields" data-name-source="BusinessNameRegistry">
        <span>业务模块：<strong>{{ nameConsumption.moduleDisplayName || nameConsumption.moduleCode || '未登记' }}</strong></span>
        <span>页面名称：<strong>{{ nameConsumption.pageName }}</strong></span>
        <span>页面编码：<strong>{{ nameConsumption.pageCode || '未登记' }}</strong></span>
        <span>业务对象：<strong>{{ nameConsumption.businessObject || '未登记' }}</strong></span>
      </div>
      <nav class="pce-list-page-breadcrumb" data-acceptance-id="page-breadcrumb-current-title" aria-label="页面位置">
        <span>业务流程中心</span>
        <span>/</span>
        <strong>{{ pageTitle }}</strong>
      </nav>
      <h1 data-acceptance-id="page-business-title">
        <PceBusinessNameConsumer
          data-acceptance-id="page-internal-subject-title"
          :page-code="governedPage?.pageCode || props.moduleId"
          :route-path="route.path"
        />
      </h1>
      <p class="pce-list-page-protection">
        模块边界：本公共结构壳统一页面宽度、边距、列表工具栏、固定列和横向滚动边界；
        业务名称、业务版本与流程语义均由 registry 提供，公共壳不执行正式业务动作。
      </p>
    </header>
    <section
      v-if="!props.compactEmployeeView && (financePage || governedPage)"
      class="pce-common-region"
      data-acceptance-id="finance-operation-summary"
    >
      <h2>当前业务动作说明</h2>
      <p>页面作用：{{ governedPage?.purpose || operationConfig?.purposeText }}</p>
      <p><strong>允许：</strong>{{ governedPage ? governedPage.allowed.join('　') : '读取服务端事实、执行页面已有受控动作、查看来源与导航资格。' }}</p>
      <p><strong>禁止：</strong>{{ governedPage ? governedPage.forbidden.join('　') : '导航时创建下游对象、自动推进状态、付款、核销、写总账或银行流水。' }}</p>
    </section>
    <section
      v-if="!props.compactEmployeeView && (financePage || governedPage)"
      class="pce-common-region"
      data-acceptance-id="module-main-process"
      aria-label="模块主流程"
    >
      <h2>模块主流程</h2>
      <ol class="pce-main-process-steps">
        <li
          v-for="(step, index) in governedPage?.flowSteps || strictProcessSteps"
          :key="step.pageStepId || step"
          :aria-current="(step.pageStepId || step) === (governedPage?.currentFlowStep || financePage?.pageStepId) ? 'step' : undefined"
          :data-step-state="governedPage ? ((step.pageStepId || step) === governedPage.currentFlowStep ? 'current' : 'context') : processStepState(index)"
        >
          <span>{{ index + 1 }}</span>
          <strong>{{ step.canonicalName || step }}</strong>
          <small>{{ governedPage ? ((step.pageStepId || step) === governedPage.currentFlowStep ? '当前节点' : '业务节点') : processStepStateText(index) }}</small>
        </li>
      </ol>
      <div class="pce-process-facts">
        <span>当前输入模块：<strong>{{ previousNavigation.label }}</strong></span>
        <span>当前步骤：<strong>{{ pageTitle }}</strong></span>
        <span>当前输出模块：<strong>{{ nextNavigation.label }}</strong></span>
      </div>
    </section>
    <section
      v-if="!props.compactEmployeeView && (financePage || governedPage)"
      class="pce-common-region"
      data-acceptance-id="business-process-navigation"
    >
      <h2>业务流程导航</h2>
      <div class="pce-process-facts">
        <span>
          上一步：
          <router-link
            v-if="previousNavigation.pageUrl"
            :to="previousNavigation.pageUrl"
            :data-page-code="previousNavigation.pageCode"
            data-pde-navigation-link="previous"
          >{{ previousNavigation.label }}</router-link>
          <strong v-else>{{ previousNavigation.label }}</strong>
        </span>
        <span>
          当前页面：
          <router-link
            v-if="currentNavigation.pageUrl"
            :to="currentNavigation.pageUrl"
            :data-page-code="currentNavigation.pageCode"
            data-pde-navigation-link="current"
          >{{ currentNavigation.label }}</router-link>
          <strong v-else>{{ currentNavigation.label }}</strong>
        </span>
        <span>
          下一步：
          <router-link
            v-if="nextNavigation.pageUrl"
            :to="nextNavigation.pageUrl"
            :data-page-code="nextNavigation.pageCode"
            data-pde-navigation-link="next"
          >{{ nextNavigation.label }}</router-link>
          <strong v-else>{{ nextNavigation.label }}</strong>
        </span>
      </div>
      <div class="pce-navigation-actions">
        <router-link
          v-if="operationConfig?.sourceRoutePath"
          :to="operationConfig.sourceRoutePath"
          data-acceptance-id="source-document-button"
        >
          {{ operationConfig.sourceButtonText }}
        </router-link>
        <router-link
          v-if="operationConfig?.nextRoutePath"
          :to="operationConfig.nextRoutePath"
          data-acceptance-id="next-step-button"
        >
          {{ operationConfig.nextButtonText }}
        </router-link>
      </div>
      <p>页面导航只形成查看或导航资格，不创建下一模块对象。</p>
    </section>
    <div
      v-if="observabilityEnabled && (!props.compactEmployeeView || props.showCompactPageActions)"
      class="pce-page-action-bar"
      data-acceptance-id="page-observability-action-bar"
      data-action-location="page_action_bar"
    >
      <button type="button" data-acceptance-id="page-refresh-button"
        :data-refresh-status="pageRefreshStatus" :aria-busy="pageRefreshStatus === 'refreshing'"
        :disabled="pageRefreshStatus === 'refreshing'" @click="refreshCurrentPage">
        {{ pageRefreshButtonLabel }}
      </button>
      <span v-if="pageLastRefreshTime" class="pce-page-refresh-time"
        data-acceptance-id="page-last-refresh-time">最近刷新时间：{{ pageLastRefreshTime }}</span>
      <button type="button" data-acceptance-id="copy-diagnostic-data-button" @click="copyCurrentDiagnostics">复制诊断数据</button>
      <button type="button" data-acceptance-id="return-process-center-button" @click="returnToProcessCenter">返回业务流程中心</button>
    </div>
    <section v-if="props.compactEmployeeView && props.separateCompactNavigation && (financePage || governedPage)"
      class="pce-compact-flow-navigation" data-ui-revision="THREE-PAGE-NAV-R2" data-acceptance-id="compact-flow-navigation">
      <h2>业务流程导航</h2>
        <nav class="pce-process-facts" aria-label="业务流程导航">
          <span>
            上一步：
            <router-link v-if="previousNavigation.pageUrl" :to="previousNavigation.pageUrl">{{ previousNavigation.label }}</router-link>
            <strong v-else>{{ previousNavigation.label }}</strong>
          </span>
          <span>当前页面：<strong>{{ currentNavigation.label }}</strong></span>
          <span>
            下一步：
            <router-link v-if="nextNavigation.pageUrl" :to="nextNavigation.pageUrl">{{ nextNavigation.label }}</router-link>
            <strong v-else>{{ nextNavigation.label }}</strong>
          </span>
        </nav>
    </section>
    <details
      v-if="props.compactEmployeeView && (financePage || governedPage)"
      class="pce-compact-page-guide"
      data-acceptance-id="compact-page-guide"
    >
      <summary>{{ props.separateCompactNavigation ? '页面说明（点击展开／收起）' : '页面说明与业务流程' }}</summary>
      <div class="pce-compact-page-guide__body">
        <p><strong>{{ pageTitle }}</strong>：{{ governedPage?.purpose || operationConfig?.purposeText }}</p>
        <p>公共页面壳仅提供名称、流程与导航治理，不执行正式业务动作。</p>
        <nav v-if="!props.separateCompactNavigation" class="pce-process-facts" aria-label="业务流程导航">
          <span>
            上一步：
            <router-link v-if="previousNavigation.pageUrl" :to="previousNavigation.pageUrl">{{ previousNavigation.label }}</router-link>
            <strong v-else>{{ previousNavigation.label }}</strong>
          </span>
          <span>当前页面：<strong>{{ currentNavigation.label }}</strong></span>
          <span>
            下一步：
            <router-link v-if="nextNavigation.pageUrl" :to="nextNavigation.pageUrl">{{ nextNavigation.label }}</router-link>
            <strong v-else>{{ nextNavigation.label }}</strong>
          </span>
        </nav>
      </div>
    </details>
    <PceStrictServerFactsPanel
      v-if="acceptanceContract?.enforcementMode === 'strict' && !pageOwnsStrictServerFacts"
      :page-code="acceptanceContract.pageCode"
      :canonical-name="pageTitle"
      @loaded="recordStrictServerFacts"
      @load-error="recordStrictServerFacts"
    />
    <ScmStandardPageContext
      v-if="scmStandardGovernance && !(enterpriseCanaryMode && props.pageOwnsCanary)"
      :key="scmStandardGovernance.pageCode"
      :contract="scmStandardGovernance"
    />
    <PurchaseCanaryScenarioPanel
      v-if="route.query.canaryBatchId && canaryModuleCode && !props.pageOwnsCanary"
      :module-code="canaryModuleCode"
    />
    <PceEnterpriseListCanaryView
      v-if="enterpriseCanaryMode && !props.pageOwnsCanary && canaryModuleCode !== 'purchase-request'"
      :page-code="canaryModuleCode"
      :page-title="pageTitle"
    />
    <section v-else class="pce-list-page-content" data-pce-list-container-runtime="LIST-RUNTIME-002">
      <slot />
    </section>
  </main>
</template>

<script setup>
import { computed, defineAsyncComponent, provide, reactive, watchEffect } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { designNavigationTarget } from '../runtime/productDesignNavigation.js'
import { applyConsumedBrowserTitle, resolvePageNameConsumption } from '../governance/pageNameConsumer.js'
import { PCE_PAGE_CONTRACT_ENGINE_VERSION } from '../runtime/pcePageContractEngine.js'
import {
  findFinanceProcessPage,
  listFinanceStrictProcessSteps,
} from '../process/financeProcessPageRegistry.js'
import { findBusinessOperationPageConfig } from '../process/businessOperationPageRegistry.js'
import { findPageAcceptanceContract } from '../runtime/pcePageAcceptanceRegistry.js'
import PceBusinessNameConsumer from './PceBusinessNameConsumer.vue'
import { resolveEnterpriseListCanaryQuery } from '../runtime/enterpriseListCanaryMode.js'
import { resolveScmStandardPageContract } from '../schema/scm/scmStandardPageContract.js'
import { resolveScmProcessNavigation } from '../process/scmProcessNavigationContract.js'
import {
  PAGE_OBSERVABILITY_ACTIONS_KEY,
  assertSafeDiagnosticPayload,
  createEmptyPageObservabilityActions,
} from '../runtime/pageObservabilityActions.js'
import { assertPceFactLoadFacts } from '../runtime/pceFactLoadContract.js'
import {
  PCE_ENTERPRISE_LIST_SHELL_DEFAULTS,
  PCE_ENTERPRISE_LIST_SHELL_KEY,
} from '../runtime/pceEnterpriseListContract.js'

const PceStrictServerFactsPanel = defineAsyncComponent(() => import('./PceStrictServerFactsPanel.vue'))
const ScmStandardPageContext = defineAsyncComponent(() => import('./ScmStandardPageContext.vue'))
const PurchaseCanaryScenarioPanel = defineAsyncComponent(() => import('./PurchaseCanaryScenarioPanel.vue'))
const PceEnterpriseListCanaryView = defineAsyncComponent(() => import('./PceEnterpriseListCanaryView.vue'))

const props = defineProps({
  moduleId: { type: String, default: '' },
  governance: { type: Object, default: null },
  pageOwnsCanary: { type: Boolean, default: false },
  pageRefreshHandler: { type: Function, default: null },
  pageRefreshStatus: { type: String, default: 'idle' },
  pageLastRefreshTime: { type: String, default: '' },
  compactEmployeeView: { type: Boolean, default: false },
  separateCompactNavigation: { type: Boolean, default: false },
  showCompactPageActions: { type: Boolean, default: false },
})

const route = useRoute()
const router = useRouter()
const version = PCE_PAGE_CONTRACT_ENGINE_VERSION
const scmStandardGovernance = computed(() => resolveScmStandardPageContract(props.moduleId || route.path))
const scmProcessNavigation = computed(() => resolveScmProcessNavigation(props.moduleId || route.path))
const governedPage = computed(() => props.governance || scmStandardGovernance.value || null)
const canaryModuleCode = computed(() => (
  resolveScmProcessNavigation(route.path)?.pageCode
  || governedPage.value?.currentFlowStep
  || governedPage.value?.pageCode
  || ''
))
const enterpriseCanaryMode = computed(() => (
  route.path.startsWith('/scm/')
  && Boolean(canaryModuleCode.value)
  && resolveEnterpriseListCanaryQuery(route.query).isCanaryMode
))
const financePage = computed(() => findFinanceProcessPage(props.moduleId || route.path))
const operationConfig = computed(() => findBusinessOperationPageConfig(props.moduleId || financePage.value?.pageStepId) || {})
const acceptanceContract = computed(() => findPageAcceptanceContract(route.path))
const pageOwnsStrictServerFacts = computed(
  () => props.moduleId.startsWith('master-data-') || [
    'bank-send-simulation',
    'bank-send-simulation-audit',
    'bank-send-isolation-gate',
    'bank-send-chain-trace',
    'bank-send-final-approval',
    'bank-send-dual-isolation-check',
    'bank-send-production-release-review',
    'bank-send-execution-framework-review',
    'bank-connector-adapter-review',
    'supplier-reconciliation',
    'supplier-performance',
    'buyer-performance',
    'purchase-request',
    'purchase-inquiry',
    'price-approval',
    'purchase-order',
    'purchase-receive-preview',
    'incoming-inspection',
    'inventory-balances',
  ].includes(props.moduleId),
)
const strictProcessSteps = listFinanceStrictProcessSteps()
const currentProcessIndex = computed(() => strictProcessSteps.findIndex(step => step.pageStepId === financePage.value?.pageStepId))
const nameConsumption = computed(() => resolvePageNameConsumption({
  pageCode: governedPage.value?.pageCode || props.moduleId,
  nodeCode: governedPage.value?.currentFlowStep || props.moduleId,
  route: route.path,
}))
const pageTitle = computed(() => nameConsumption.value.pageTitle)
const normalizeNavigation = (value, fallback = {}) => {
  if (value && typeof value === 'object') {
    return {
      label: String(value.label || fallback.label || ''),
      pageCode: String(value.pageCode || fallback.pageCode || ''),
      pageUrl: String(value.pageUrl || fallback.pageUrl || ''),
    }
  }
  return {
    label: String(value || fallback.label || ''),
    pageCode: String(fallback.pageCode || ''),
    pageUrl: String(fallback.pageUrl || ''),
  }
}
const previousNavigation = computed(() => designNavigationTarget(props.moduleId, route.query, normalizeNavigation(
  scmProcessNavigation.value?.previousPage || governedPage.value?.navigation?.previous,
  { label: operationConfig.value?.previousStepName || (scmProcessNavigation.value ? '无' : '') },
)))
const currentNavigation = computed(() => designNavigationTarget(props.moduleId, route.query, normalizeNavigation(
  scmProcessNavigation.value?.currentPage || governedPage.value?.navigation?.current,
  {
    label: pageTitle.value,
    pageCode: governedPage.value?.pageCode || '',
    pageUrl: governedPage.value ? route.fullPath : '',
  },
)))
const nextNavigation = computed(() => designNavigationTarget(props.moduleId, route.query, normalizeNavigation(
  scmProcessNavigation.value?.nextPage || governedPage.value?.navigation?.next,
  { label: operationConfig.value?.nextStepName || (scmProcessNavigation.value ? '无' : '') },
)))
const observability = reactive(createEmptyPageObservabilityActions())
let observabilityOwner = null
const strictServerFacts = reactive({})
const observabilityEnabled = computed(() => Boolean(governedPage.value || financePage.value?.observabilityActions))
const pageRefreshButtonLabel = computed(() => ({
  refreshing: '刷新中...', success: '刷新成功', error: '刷新失败',
}[props.pageRefreshStatus] || '刷新'))

provide(PCE_ENTERPRISE_LIST_SHELL_KEY, PCE_ENTERPRISE_LIST_SHELL_DEFAULTS)

watchEffect(() => {
  if (!props.compactEmployeeView) applyConsumedBrowserTitle(nameConsumption.value)
})

function recordStrictServerFacts(value) {
  Object.keys(strictServerFacts).forEach(key => {
    delete strictServerFacts[key]
  })
  Object.assign(strictServerFacts, value || {})
}

function processStepState(index) {
  if (index < currentProcessIndex.value) return 'completed'
  if (index === currentProcessIndex.value) return 'current'
  return 'not-entered'
}

function processStepStateText(index) {
  return {
    completed: '已完成步骤',
    current: '当前步骤',
    'not-entered': '未进入步骤',
  }[processStepState(index)]
}

provide(PAGE_OBSERVABILITY_ACTIONS_KEY, {
  register(provider) {
    const expectedOwner = financePage.value?.moduleCode || ''
    if (
      ['FIN_BANK_SEND_TASK', 'FIN_BANK_SEND_EXECUTION_GATE', 'FIN_BANK_SEND_REQUEST'].includes(expectedOwner)
      && provider?.factOwner !== expectedOwner
    ) {
      throw new Error('page_fact_owner_unique: owner mismatch')
    }
    observabilityOwner = provider || null
    observability.ready = Boolean(provider?.refresh && provider?.buildDiagnostics)
    observability.refresh = provider?.refresh || null
    observability.buildDiagnostics = provider?.buildDiagnostics || null
  },
  unregister(provider) {
    if (provider && provider !== observabilityOwner) return
    observabilityOwner = null
    Object.assign(observability, createEmptyPageObservabilityActions())
  },
})

async function refreshCurrentPage() {
  if (props.pageRefreshHandler) {
    await props.pageRefreshHandler()
    return
  }
  if (observability.refresh) {
    await observability.refresh()
    return
  }
  window.location.reload()
}

async function copyCurrentDiagnostics() {
  try {
    const payload = observability.buildDiagnostics
      ? await observability.buildDiagnostics()
      : window.__PCE_BUSINESS_PAGE_ACCEPTANCE__
    if (!payload) throw new Error('diagnostic_payload_unavailable')
    const expectedFactOwner = financePage.value?.moduleCode || ''
    if (
      ['FIN_BANK_SEND_TASK', 'FIN_BANK_SEND_EXECUTION_GATE', 'FIN_BANK_SEND_REQUEST'].includes(expectedFactOwner)
      && (
        observabilityOwner?.factOwner !== expectedFactOwner
        || payload.pageFactOwner !== expectedFactOwner
        || payload.moduleCode !== expectedFactOwner
      )
    ) {
      throw new Error('page_fact_owner_unique: diagnostic owner mismatch')
    }
    const serialized = assertSafeDiagnosticPayload(payload)
    const contract = acceptanceContract.value
    const currentStrictServerFacts = payload.strictServerFacts
      || strictServerFacts
    const factLoadFacts = payload.factLoadFacts
      || currentStrictServerFacts.factLoadFacts
      || currentStrictServerFacts
    const factLoadStatus = payload.factLoadStatus
      || currentStrictServerFacts.factLoadStatus
      || ''
    const auditedFactLoadFacts = factLoadStatus
      ? assertPceFactLoadFacts(
          factLoadFacts,
          'copy-diagnostic',
          factLoadFacts?.apiUrl,
        )
      : factLoadFacts
    const resultCount = factLoadStatus === 'read_failed'
      ? null
      : payload.resultCount ?? currentStrictServerFacts.resultCount ?? 0
    const synchronizedStrictServerFacts = factLoadStatus === 'read_failed'
      ? {
          ...currentStrictServerFacts,
          ...auditedFactLoadFacts,
          factLoadFacts: { ...auditedFactLoadFacts },
          resultCount: null,
          rows: [],
          sourceObjects: [],
          passed: false,
        }
      : { ...currentStrictServerFacts }
    await navigator.clipboard.writeText(JSON.stringify({
      diagnosticGeneratedAt: new Date().toISOString(),
      ...JSON.parse(serialized),
      contractVersion: contract?.contractVersion || '',
      acceptanceMigrationVersion: contract?.acceptanceMigrationVersion || '',
      businessVersion: contract?.businessVersion || financePage.value?.runtimeBusinessVersion || '',
      moduleCode: contract?.moduleCode || financePage.value?.moduleCode || '',
      pageCode: contract?.pageCode || financePage.value?.pageStepId || '',
      pageType: contract?.pageType || 'list',
      canonicalName: contract?.canonicalName || pageTitle.value,
      fullUrl: window.location.href,
      previousModule: contract?.process?.previousModuleCode || '',
      currentModule: contract?.process?.currentModuleCode || '',
      nextModule: contract?.process?.nextModuleCode || '',
      currentStateSource: 'server',
      factLoadStatus,
      factLoadStatusLabel: {
        success: '加载成功',
        loaded: '已加载',
        empty_valid: '有效空数据',
        read_failed: '读取失败',
      }[factLoadStatus] || '未加载',
      apiUrl: auditedFactLoadFacts.apiUrl || '',
      httpStatus: auditedFactLoadFacts.httpStatus ?? 0,
      errorCode: auditedFactLoadFacts.errorCode || '',
      errorMessage: auditedFactLoadFacts.errorMessage || '',
      loadedAt: auditedFactLoadFacts.loadedAt || '',
      tenantId: auditedFactLoadFacts.tenantId || '',
      batchId: auditedFactLoadFacts.batchId || '',
      pageFactOwner: payload.pageFactOwner || '',
      pageFactOwnerGuard: payload.pageFactOwnerGuard || '',
      factLoadFacts: { ...auditedFactLoadFacts },
      resultCount,
      currentObject: payload.currentObject || payload.selectedObject || currentStrictServerFacts.currentObject || null,
      sourceObjects: payload.sourceObjects || currentStrictServerFacts.sourceObjects || [],
      status: payload.status || currentStrictServerFacts.status || '',
      strictServerFacts: synchronizedStrictServerFacts,
    }, null, 2))
    ElMessage.success('诊断数据已复制')
  } catch {
    ElMessage.error('诊断数据复制失败，请检查浏览器剪贴板权限')
  }
}

function returnToProcessCenter() {
  const moduleCode = String(
    governedPage.value?.returnModuleCode
      || scmStandardGovernance.value?.moduleCode
      || governedPage.value?.businessModule
      || financePage.value?.moduleCode
      || operationConfig.value?.moduleCode
      || '',
  ).trim().toUpperCase()
  router.push({
    path: '/process-center',
    query: moduleCode ? { module: moduleCode } : {},
  })
}
</script>

<style scoped>
.pce-list-page-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  width: 100%;
  box-sizing: border-box;
  gap: 14px;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
}

.pce-list-page-shell :deep(.app-page-shell),
.pce-list-page-shell :deep(.wms-page),
.pce-list-page-shell :deep(.payment-draft-page),
.pce-list-page-shell :deep(.operation-shell),
.pce-list-page-shell :deep(.el-card),
.pce-list-page-shell :deep(.el-card__body) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.pce-list-page-content {
  display: block;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  box-sizing: border-box;
}

.pce-list-page-shell .pce-list-page-content :deep(> *) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

.pce-list-page-content :deep(.panel),
.pce-list-page-content :deep(.el-card),
.pce-list-page-content :deep(.el-card__body) {
  min-width: 0;
  max-width: 100%;
}

.pce-list-page-header {
  display: grid;
  gap: 8px;
  padding: 16px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #ffffff;
}

.pce-version-classification {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  color: #2563eb;
  font-size: 13px;
}
.pce-version-classification strong { font-weight: 800; }

.pce-page-action-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}

.pce-compact-page-guide {
  padding: 10px 14px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #fff;
  color: #334155;
}

.pce-compact-page-guide summary {
  cursor: pointer;
  color: #1d4ed8;
  font-weight: 800;
}

.pce-compact-page-guide__body {
  display: grid;
  gap: 8px;
  padding-top: 10px;
}

.pce-compact-page-guide__body p {
  margin: 0;
}

.pce-common-region {
  display: grid;
  gap: 10px;
  padding: 16px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #fff;
}

.pce-common-region h2,
.pce-common-region p {
  margin: 0;
}

.pce-main-process-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.pce-main-process-steps li {
  display: grid;
  gap: 4px;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #f8fafc;
}

.pce-main-process-steps li[data-step-state="current"] {
  border-color: #2563eb;
  outline: 2px solid #bfdbfe;
}

.pce-main-process-steps li[data-step-state="completed"] {
  border-color: #16a34a;
}

.pce-main-process-steps small {
  color: #475569;
}

.pce-process-facts,
.pce-navigation-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.pce-navigation-actions a {
  padding: 8px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  color: #1d4ed8;
  font-weight: 800;
  text-decoration: none;
}

.pce-page-action-bar button {
  min-height: 34px;
  padding: 7px 14px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  cursor: pointer;
  font-weight: 800;
}

.pce-page-action-bar button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.pce-page-refresh-time {
  align-self: center;
  color: #475569;
  font-size: 13px;
}

.pce-list-page-header h1,
.pce-list-page-breadcrumb,
.pce-list-page-protection {
  margin: 0;
}

.pce-list-page-breadcrumb {
  display: flex;
  gap: 6px;
  align-items: center;
  color: #64748b;
  font-size: 13px;
  font-weight: 700;
}

.pce-list-page-breadcrumb strong {
  color: #0f172a;
}

.pce-list-page-protection {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.7;
}
.pce-compact-flow-navigation{padding:12px 16px;border:1px solid #dbe3ef;border-radius:10px;background:#fff;min-width:0}
.pce-compact-flow-navigation h2{font-size:16px;margin:0 0 8px;color:#193e5e}
.pce-compact-flow-navigation nav>span{display:flex;align-items:center;flex-wrap:wrap;gap:4px;min-width:0;overflow-wrap:anywhere}
.pce-compact-flow-navigation a{display:inline-flex;align-items:center;min-height:44px;color:#185b97;overflow-wrap:anywhere}
.pce-compact-flow-navigation :focus-visible{outline:3px solid #2563eb;outline-offset:2px}
@media(max-width:650px){.pce-compact-flow-navigation nav{flex-direction:column;gap:4px}}
</style>
