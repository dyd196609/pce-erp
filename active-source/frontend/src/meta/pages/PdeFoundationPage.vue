<template>
  <main
    class="pde-page"
    :data-acceptance-id="`${definition.pageCode}-page`"
    data-page-module="PDE"
    :data-page-version="pageVersion"
    data-page-template="PceListPageShell"
    data-fact-source="server"
    data-enterprise-list-contract="PCE-ENTERPRISE-LIST-CONTRACT-V1.1"
    data-detail-display-mode="PceBusinessDetailCard"
    data-danger-action-count="0"
  >
    <OrderEngineeringIdentityIntakePanel v-if="props.pageKind === 'engineeringReadiness' && route.query.salesOrderItemId" :sales-order-item-id="route.query.salesOrderItemId" @facts="identityIntakeFacts = $event" @saved="refresh" />
    <el-alert v-if="props.pageKind === 'bomVersions' && detailRow?.businessPurposeCode === 'TEST_BUSINESS'" :title="detailRow.formalManufacturingMessage" type="warning" :closable="false" />
    <TestBusinessBomHandoff ref="testBusinessPanel" @facts="testBusinessFacts = $event" v-if="props.pageKind === 'boms'" @saved="refresh" />
    <OrderRoutingExecutionPanel @operation-start-facts="orderOperationStartFacts=$event" @workshop-task-facts="orderWorkshopTaskFacts=$event" @work-order-facts="orderWorkOrderFacts=$event" @schedule-facts="orderScheduleFacts=$event" @date-facts="orderDateFacts=$event" @capacity-facts="orderCapacityFacts=$event" @draft-state="orderExecutionUiState=$event" @facts="orderExecutionFacts=$event" @state="orderExecutionState=$event" ref="orderRoutingPanel" v-if="['routings','routingVersions'].includes(props.pageKind)" />
    <component v-if="!assigneeEntryOnly" :is="['routings','routingVersions'].includes(props.pageKind) ? 'details' : 'div'" class="routing-reference-catalog"><summary v-if="['routings','routingVersions'].includes(props.pageKind)">标准路线目录、历史绑定与技术诊断（按需查看）</summary>
    <p v-if="foundationMaintenanceLocation"><router-link :to="foundationMaintenanceLocation">本页为只读运作总览；查看标准详情及正常编辑请进入企业基础资料对应模块</router-link></p>
    <TestEngineeringRoutingReadback ref="testRoutingPanel" v-if="['routings', 'routingVersions'].includes(props.pageKind)" :formal-handoff-count="historicalFormalHandoffCount" @facts="testRoutingFacts=$event" @state="testRoutingState=$event" />
    <OrderBomHandoffPreview
      v-if="props.pageKind === 'boms' && factsAvailable && handoff"
      :facts="handoff"
      :preview-state="bomPreviewState"
      :preview-busy="bomPreviewBusy"
      @select-order="selectHandoffOrder"
      @preview-bom="previewBomConditions"
    />
    <el-alert v-if="props.pageKind === 'boms' && factsAvailable && handoffReadFailure" :title="handoffReadFailure.statusLabel" :description="handoffReadFailure.message" type="warning" :closable="false" />
    <section class="card facts" data-acceptance-id="pde-server-facts">
      <h2>服务端持久事实</h2>
      <p>接口、页面、复制诊断、严格事实与验收事实复用同一产品研发与工程中心服务端事实。</p>
      <details v-if="['routings','routingVersions'].includes(props.pageKind)"><summary>服务端诊断（技术来源、页面版本及技术检查，不代替人工验收）</summary>
        <p>事实来源：{{ factSourceText }}；页面版本：{{ strictFacts.pageVersion || pageVersion }}；技术检查：{{ acceptanceStatusText }}</p>
      </details>
      <div class="fact-grid">
        <article v-if="!['routings','routingVersions'].includes(props.pageKind)"><small>事实来源</small><strong>{{ factSourceText }}</strong></article>
        <article><small>记录数量</small><strong>{{ recordCountText }}</strong></article>
        <article><small>业务节点</small><strong>{{ definition.title }}</strong></article>
        <article v-if="!['routings','routingVersions'].includes(props.pageKind)"><small>页面版本</small><strong>{{ strictFacts.pageVersion || pageVersion }}</strong></article>
        <article v-if="!['routings','routingVersions'].includes(props.pageKind)"><small>自动验收</small><strong>{{ acceptanceStatusText }}</strong></article>
      </div>
    </section>

    <section v-if="!factsAvailable" class="card load-state" :data-load-state="loadState">
      <el-alert :title="loadMessage" :type="authenticationRequired ? 'warning' : 'error'" show-icon :closable="false" />
      <div class="load-state-actions">
        <el-button v-if="authenticationRequired" type="primary" @click="goToLogin">正常登录并返回本页</el-button>
        <el-button :loading="loading" @click="refresh">重新读取</el-button>
      </div>
      <p>当前结果数量未取得；此状态不表示真实业务记录为 0 条。</p>
    </section>

    <EngineeringDocumentReleaseReadback
      v-if="props.pageKind === 'engineeringDocuments' && factsAvailable"
      :facts="strictFacts"
    />
    <ManufacturingOutputHandoff v-if="props.pageKind === 'manufacturingOutputs' && factsAvailable"
      :candidate="strictFacts.manufacturingOutputCandidate" :submitting="manufacturingOutputSubmitting"
      @generate="handleGenerateManufacturingOutput" @release="handleReleaseManufacturingOutput"
      @select-version="handleSelectManufacturingOutputVersion" />

    <section v-if="props.pageKind === 'manufacturingAdmissions' && factsAvailable" class="card" data-acceptance-id="manufacturing-admission-history-readback">
      <h2>正式制造承接确认历史</h2>
      <p>本入口只读，不重放确认、不新增任务、不创建生产需求。</p>
      <article v-for="record in rows" :key="record.id" class="fact-grid">
        <h3>{{ record.orderNo }}</h3>
        <p>制造承接：<PceBusinessStatus :status-label="record.statusLabel" source="server" /></p>
        <p>确认责任人：{{ record.responsibleName }} / User{{ record.responsibleUserId }}</p>
        <p>WorkflowInstance：{{ record.workflowInstanceId }}；ApprovalTask：{{ record.approvalTaskId }}；ApprovalDecision：{{ record.approvalDecisionId }}</p>
        <p>BusinessStateTransition：{{ record.businessStateTransitionId }}；Audit：{{ record.auditId }}</p>
        <p>确认时间：{{ record.confirmedAt }}；订单状态：{{ record.salesOrderStatusLabel }}</p>
      </article>
    </section>

    <section class="card relationship-facts" data-acceptance-id="pde-emd-source-facts">
      <h2>{{ definition.relationshipSectionTitle || '工程数据关系' }}</h2>
      <ul>
        <li v-for="fact in definition.relationshipFacts" :key="fact">{{ fact }}</li>
      </ul>
    </section>

    <section v-if="factsAvailable" class="card">
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        :page-id="definition.pageCode"
        :table-id="`${definition.pageCode}-table`"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="definition.filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        :primary-field="definition.primaryField"
        :primary-label="definition.primaryLabel"
        min-width="1480px"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event"
        @sort-change="handleSort"
      >
        <template #columns>
          <el-table-column
            v-for="column in definition.columns"
            :key="column[0]"
            :prop="column[0]"
            :label="column[1]"
            :width="column[2]"
            sortable
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <PceBusinessStatus
                v-if="column[0] === 'statusLabel' || column[0].endsWith('StatusLabel')"
                :status-label="row[column[0]]"
                source="server"
              />
              <span v-else>{{ row[column[0]] ?? '-' }}</span>
            </template>
          </el-table-column>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showDetail(row)">查看详情</el-button>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section
      class="card boundary"
      data-acceptance-id="pde-business-boundary-protection"
    >
      <h2>业务边界保护</h2>
      <p>产品研发与工程中心定位：订单驱动的产品研发与工程资料管理中心，不建设计算机辅助设计、三维设计、产品数据管理或产品生命周期管理工具。</p>
      <div class="relationship-chain" data-acceptance-id="pde-output-relationship">
        <strong>客户关系管理销售订单</strong><span>→</span>
        <strong>产品设计</strong><span>→</span>
        <strong>物料清单</strong><span>→</span>
        <strong>企业主数据物料 / 工作中心</strong><span>→</span>
        <strong>物料需求计划输入依据</strong><span>→</span>
        <strong>采购与生产</strong>
      </div>
      <div v-if="definition.boundaryFacts?.length" class="fact-grid">
        <article v-for="fact in definition.boundaryFacts" :key="fact.label">
          <small>{{ fact.label }}</small><strong>{{ fact.value }}</strong>
        </article>
      </div>
      <div v-else class="fact-grid">
        <article><small>生产用户数据写入</small><strong>0</strong></article>
        <article><small>SCM结算修改</small><strong>0</strong></article>
        <article><small>付款/银行/财务写入</small><strong>0</strong></article>
      </div>
    </section>

    <el-dialog v-model="detailVisible" :title="`${definition.title}详情`" :width="detailDialogWidth">
      <PceBusinessDetailCard v-if="detailRow" :detail="businessDetail" />
      <OrderEngineeringIdentityIntakePanel v-if="props.pageKind === 'engineeringReadiness' && detailRow" :key="detailRow.id" :sales-order-item-id="detailRow.salesOrderItemId || detailRow.id" @saved="refresh" />
      <BomMaterialDetailReadback
        v-if="['boms', 'bomVersions'].includes(props.pageKind) && detailRow"
        :detail="detailRow"
      />
      <BomVersionReleasePreflightReadback
        v-if="props.pageKind === 'bomVersions' && detailRow && detailRow.businessPurposeCode !== 'TEST_BUSINESS'"
        :detail="detailRow"
        @review-readback="handleBomVersionReviewReadback"
      />
      <RoutingVersionReadback
        v-if="['routings', 'routingVersions'].includes(props.pageKind) && detailRow"
        :definition-id="props.pageKind === 'routings' ? detailRow.id : detailRow.definitionId"
        :definition-code="detailRow.routingCode || ''"
        :definition-status-label="detailRow.definitionStatusLabel || ''"
        :versions="props.pageKind === 'routings' ? (detailRow.routingVersions || []) : [detailRow]"
        :modes="strictFacts.routingStepApplicabilityModes || []"
        :conditions="strictFacts.routingStepApplicabilityConditions || []"
        @create-successor="handleCreateRoutingSuccessor"
        @save-applicability="handleSaveRoutingStepApplicability"
        @save-manual-decision="handleSaveRoutingManualDecision"
        @review-version="handleReviewRoutingVersion"
        @release-version="handleReleaseRoutingVersion"
      />
      <RoutingPlanningReadiness
        v-if="props.pageKind === 'routings' && detailRow?.planningReadiness"
        :readiness="detailRow.planningReadiness"
        :foundation="strictFacts.routingFoundationAssessment"
      />
      <EngineeringDocumentReleaseReadback
        v-if="props.pageKind === 'engineeringDocuments' && detailRow"
        :facts="strictFacts"
        :detail="detailRow"
        :review-submitting="engineeringDocumentReviewSubmitting"
        :release-submitting="engineeringDocumentReleaseSubmitting"
        @review-version="handleReviewEngineeringDocumentVersion"
        @release-version="handleReleaseEngineeringDocumentVersion"
      />
    </el-dialog>
    </component>
  </main>
</template>

<script setup>
import TestBusinessBomHandoff from './components/TestBusinessBomHandoff.vue'
import TestEngineeringRoutingReadback from './components/TestEngineeringRoutingReadback.vue'

import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pdeApi } from '@/api/pde.js'
import OrderEngineeringIdentityIntakePanel from './components/OrderEngineeringIdentityIntakePanel.vue'
import OrderBomHandoffPreview from './components/OrderBomHandoffPreview.vue'
import BomMaterialDetailReadback from './components/BomMaterialDetailReadback.vue'
import BomVersionReleasePreflightReadback from './components/BomVersionReleasePreflightReadback.vue'
import RoutingVersionReadback from './components/RoutingVersionReadback.vue'
import RoutingPlanningReadiness from './components/RoutingPlanningReadiness.vue'
import EngineeringDocumentReleaseReadback from './components/EngineeringDocumentReleaseReadback.vue'
import ManufacturingOutputHandoff from './components/ManufacturingOutputHandoff.vue'
import { submitManufacturingOutputGeneration, submitManufacturingOutputRelease } from './manufacturingOutputGenerationSubmission.js'
import {
  submitEngineeringDocumentVersionReview,
} from './engineeringDocumentVersionReviewSubmission.js'
import {
  submitEngineeringDocumentVersionRelease,
} from './engineeringDocumentVersionReleaseSubmission.js'
import OrderRoutingExecutionPanel from './components/OrderRoutingExecutionPanel.vue'
import {getFoundationCanonicalModuleByEntity} from '@/meta/master-data/foundationEntryUnificationRegistry'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { findPdePageDefinition, PDE_PAGE_VERSION } from './pdePageDefinitions.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import {
  createReadFailedFactLoad,
  readPceFactLoadEnvelope,
} from '@/meta/runtime/pceFactLoadContract.js'

const props = defineProps({ pageKind: { type: String, required: true } })
const route = useRoute()
const router = useRouter()
const definition = computed(() => {
  const value = findPdePageDefinition(props.pageKind)
  if (!value) throw new Error(`Unknown PDE page: ${props.pageKind}`)
  return value
})
const pageVersion = PDE_PAGE_VERSION
const rows = ref([])
const handoff = ref(null)
const identityIntakeFacts = ref(null)
const handoffReadFailure = ref(null)
const testBusinessPanel = ref(null)
const testBusinessFacts = ref(null)
const bomPreviewState = ref(null)
const bomPreviewBusy = ref(false)
const strictFacts = ref({})
const factLoadFacts = ref(null)
const loading = ref(false)
const loadMessage = ref('正在读取服务端事实…')
const apiFacts = ref({})
const orderOperationStartFacts=ref(null)
const orderWorkshopTaskFacts=ref(null)
const orderWorkOrderFacts=ref(null)
const orderScheduleFacts=ref(null)
const orderDateFacts=ref(null)
const orderCapacityFacts=ref(null)
const orderExecutionFacts=ref(null),orderExecutionState=ref('loading'),orderExecutionUiState=ref(null)
const testRoutingPanel=ref(null),testRoutingFacts=ref(null),testRoutingState=ref('loading')
const diagnosticFacts = ref({})
const acceptanceFacts = ref({})
const detailVisible = ref(false)
const detailRow = ref(null)
const engineeringDocumentReviewSubmitting = ref(false)
const engineeringDocumentReleaseSubmitting = ref(false)
const manufacturingOutputSubmitting = ref(false)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const loadState = computed(() => loading.value
  ? 'loading'
  : (factLoadFacts.value?.factLoadStatus || 'read_failed'))
const factsAvailable = computed(() => ['loaded', 'empty_valid', 'success'].includes(loadState.value))
const historicalFormalHandoffCount = computed(() => factsAvailable.value ? apiFacts.value.formalHandoffCount : null)
const authenticationRequired = computed(() => (
  Number(factLoadFacts.value?.httpStatus) === 401
  || ['not_authenticated', 'authentication_failed', 'AUTHENTICATION_CONTEXT_CHANGED']
    .includes(String(factLoadFacts.value?.errorCode || ''))
))
const factSourceText = computed(() => loading.value
  ? '正在读取'
  : (factsAvailable.value ? (strictFacts.value.factSource || '服务端') : '未取得'))
const recordCountText = computed(() => factsAvailable.value ? strictFacts.value.recordCount : '未取得')
const acceptanceStatusText = computed(() => loading.value
  ? '正在读取'
  : ['routings','routingVersions'].includes(props.pageKind) && (!factsAvailable.value || (!assigneeEntryOnly.value && testRoutingState.value!=='loaded') || orderExecutionState.value!=='loaded')
    ? '本页读取未全部成功'
  : (factsAvailable.value ? (strictFacts.value.acceptanceStatus || '-') : '未取得'))
const enterpriseListContract = computed(() => createPceEnterpriseListContract({
  pageCode: definition.value.pageCode,
  pageType: 'list',
  title: definition.value.title,
  moduleCode: 'PDE',
}))
const runtime = usePceEnterpriseListRuntime({
  rows,
  filterSchema: definition.value.filterSchema,
  pageCode: definition.value.pageCode,
  searchFields: definition.value.searchFields,
  exportFileName: `${definition.value.title}.csv`,
  exportColumns: [
    { field: definition.value.primaryField, label: definition.value.primaryLabel },
    ...definition.value.columns.map(([field, label]) => ({ field, label })),
  ],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = runtime
const foundationMaintenanceLocation=computed(()=>getFoundationCanonicalModuleByEntity(definition.value.resource==='routing-versions'?'routings':definition.value.resource)?.routePath || '')
const labels = computed(() => new Map([
  [definition.value.primaryField, definition.value.primaryLabel],
  ...definition.value.columns.map(([field, label]) => [field, label]),
]))
const businessDetail = computed(() => ({
  sectionTitle: `${definition.value.title}业务信息`,
  fields: Object.entries(detailRow.value || {})
    .filter(([field]) => labels.value.has(field))
    .map(([field, value]) => ({ label: labels.value.get(field), value })),
}))
const detailDialogWidth = computed(() => {
  if (['boms', 'bomVersions'].includes(props.pageKind)) return 'min(1320px, 96vw)'
  if (['routings', 'routingVersions'].includes(props.pageKind)) return 'min(1320px, 96vw)'
  return '860px'
})

function showDetail(row) {
  detailRow.value = row
  detailVisible.value = true
}

async function handleBomVersionReviewReadback() {
  const selectedId = detailRow.value?.bomVersionId
  await refresh()
  detailRow.value = rows.value.find(row => row.bomVersionId === selectedId) || null
  detailVisible.value = Boolean(detailRow.value)
}

function newIdempotencyKey(prefix) {
  const suffix = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}:${suffix}`
}

async function handleCreateRoutingSuccessor() {
  if(foundationMaintenanceLocation.value) await router.push(foundationMaintenanceLocation.value)
}

async function handleSaveRoutingStepApplicability() {
  if(foundationMaintenanceLocation.value) await router.push(foundationMaintenanceLocation.value)
}

async function handleSaveRoutingManualDecision() {
  ElMessage.info('订单是否执行请在上方独立订单工序执行安排办理，不新增标准路线版本。')
}

async function handleReviewRoutingVersion() {
  if(foundationMaintenanceLocation.value) await router.push(foundationMaintenanceLocation.value)
}

async function handleReleaseRoutingVersion() {
  if(foundationMaintenanceLocation.value) await router.push(foundationMaintenanceLocation.value)
}

async function handleReviewEngineeringDocumentVersion(payload) {
  const rowId = detailRow.value?.id
  const versionId = payload.versionId
  if (!versionId || !String(payload.reason || '').trim()) return
  try {
    const submission = await submitEngineeringDocumentVersionReview({
      versionId,
      confirmSubmission: () => ElMessageBox.confirm(
        `确认由当前正式登录人员对工程资料版本${payload.versionNo || versionId}提交“评审通过”决定？本动作不会发布工程资料，也不会形成制造发布记录。`,
        '确认工程资料版本正式评审',
        { confirmButtonText: '确认评审通过', cancelButtonText: '取消', type: 'warning' },
      ),
      requestReview: () => pdeApi.reviewEngineeringDocumentVersion(
        versionId,
        {
          action: 'pde.engineering_document_version.review',
          reason: String(payload.reason).trim(),
        },
        newIdempotencyKey('engineering-document-version-review'),
      ),
      refreshFacts: refresh,
      getFormalReadback: () => rows.value.find(row => row.id === rowId) || null,
      isSubmitting: () => engineeringDocumentReviewSubmitting.value,
      setSubmitting: value => { engineeringDocumentReviewSubmitting.value = value },
    })
    if (submission.duplicateSuppressed) return
    detailRow.value = submission.row
    detailVisible.value = Boolean(detailRow.value)
    ElMessage.success('工程资料版本正式评审已完成事务提交并回读到一致状态；工程资料与制造发布均未执行。')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.userMessage || error?.response?.data?.error?.message || error?.message || '工程资料版本正式评审失败。')
  }
}

async function handleReleaseEngineeringDocumentVersion(payload) {
  const rowId = detailRow.value?.id
  const versionId = payload.versionId
  if (!versionId || !String(payload.reason || '').trim()) return
  try {
    const submission = await submitEngineeringDocumentVersionRelease({
      versionId,
      confirmSubmission: () => ElMessageBox.confirm(
        `确认由当前正式登录人员发布工程资料版本${payload.versionNo || versionId}？本动作只执行工程资料版本 reviewed → released，不会创建或推进制造发布记录。`,
        '确认工程资料版本正式发布',
        { confirmButtonText: '确认正式发布', cancelButtonText: '取消', type: 'warning' },
      ),
      requestRelease: () => pdeApi.releaseEngineeringDocumentVersion(
        versionId,
        {
          action: 'production.engineering.document.release',
          reason: String(payload.reason).trim(),
        },
        newIdempotencyKey('engineering-document-version-release'),
      ),
      refreshFacts: refresh,
      getFormalReadback: () => rows.value.find(row => row.id === rowId) || null,
      isSubmitting: () => engineeringDocumentReleaseSubmitting.value,
      setSubmitting: value => { engineeringDocumentReleaseSubmitting.value = value },
    })
    if (submission.duplicateSuppressed) return
    detailRow.value = submission.row
    detailVisible.value = Boolean(detailRow.value)
    ElMessage.success('工程资料版本正式发布已完成事务提交并回读一致；制造发布未执行。')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.userMessage || error?.response?.data?.error?.message || error?.message || '工程资料版本正式发布失败。')
  }
}

async function handleSelectManufacturingOutputVersion(selection) {
  if (manufacturingOutputSubmitting.value) return
  const query = { ...route.query }
  for (const key of ['salesOrderItemId', 'engineeringDocumentVersionId', 'predecessorOutputId']) {
    if (selection[key] === null || selection[key] === undefined || selection[key] === '') delete query[key]
    else query[key] = String(selection[key])
  }
  await router.replace({ path: route.path, query })
}

async function handleGenerateManufacturingOutput(payload) {
  try {
    const submission = await submitManufacturingOutputGeneration({
      confirm: () => ElMessageBox.confirm(
        `确认由当前正式登录人员为${strictFacts.value.manufacturingOutputCandidate.orderNo}行${strictFacts.value.manufacturingOutputCandidate.lineNo}生成制造输出草稿？`,
        '确认生成制造输出', { confirmButtonText: '确认生成草稿', cancelButtonText: '取消', type: 'warning' }),
      request: () => pdeApi.generateManufacturingOutput(payload, newIdempotencyKey('manufacturing-output-generate')),
      refresh,
      readback: () => strictFacts.value.manufacturingOutputCandidate,
      isSubmitting: () => manufacturingOutputSubmitting.value,
      setSubmitting: value => { manufacturingOutputSubmitting.value = value },
    })
    if (submission.duplicateSuppressed) return
    ElMessage.success(`制造输出 ID ${submission.result.row.id} 已生成并回读为草稿；制造发布未执行。`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '制造输出生成请求失败，请核实正式回执。')
  }
}

async function handleReleaseManufacturingOutput(payload) {
  try {
    const { outputId, ...body } = payload
    const submission = await submitManufacturingOutputRelease({
      confirm: () => ElMessageBox.confirm(
        `确认以当前正式账号将制造输出 ID ${outputId} 发布至制造？此操作不自动创建生产计划、MRP或工单。`,
        '确认正式制造发布', { confirmButtonText: '确认正式发布', cancelButtonText: '取消', type: 'warning' }),
      request: () => pdeApi.releaseManufacturingOutput(outputId, body, newIdempotencyKey('manufacturing-output-release')),
      refresh, readback: () => strictFacts.value.manufacturingOutputCandidate,
      isSubmitting: () => manufacturingOutputSubmitting.value,
      setSubmitting: value => { manufacturingOutputSubmitting.value = value },
    })
    if (submission.duplicateSuppressed) return
    ElMessage.success(`制造输出 ID ${submission.result.row.id} 正式发布已提交且回读一致；未创建下游业务。`)
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '制造发布请求失败，请核实正式回执。')
  }
}

function failureMessage(facts) {
  if (Number(facts.httpStatus) === 401) return '当前标签尚未登录或会话已失效。请从正常登录入口登录，成功后将自动返回本页并重新读取。'
  if (Number(facts.httpStatus) === 403) return `当前已登录账户没有本页查看资格。${facts.errorMessage || ''}`
  if (Number(facts.httpStatus) >= 500) return `服务端读取异常。${facts.errorMessage || ''}`
  if (Number(facts.httpStatus) === 0) return `无法连接正式数据服务或请求已超时。${facts.errorMessage || ''}`
  return `服务端事实读取失败。${facts.errorMessage || ''}`
}

function goToLogin() {
  router.push({ path: '/system-login', query: { redirect: route.fullPath, reason: 'pde-fact-read-required' } })
}

function panelFacts(fact){return ['routings','routingVersions'].includes(props.pageKind)?{...fact,orderRoutingExecution:orderExecutionFacts.value?.orderExecutionArrangements ?? null,orderRoutingExecutionReadState:orderExecutionState.value,testOperationStarts:orderOperationStartFacts.value?.testOperationStarts ?? null,testWorkshopTasks:orderWorkshopTaskFacts.value?.testWorkshopTasks ?? null,testWorkOrderReception:orderWorkOrderFacts.value?.testWorkOrderReception ?? null,orderExecutionTestSchedule:orderScheduleFacts.value?.orderExecutionTestSchedule ?? orderScheduleFacts.value?.orderExecutionDatePreview?.scheduleFacts ?? null,orderExecutionDatePreview:orderDateFacts.value?.orderExecutionDatePreview ?? null,orderExecutionCapacityRead:orderCapacityFacts.value?.orderExecutionCapacity ?? null}: {...fact}}
function publish() {
  const surfaces = [apiFacts.value, strictFacts.value, diagnosticFacts.value, acceptanceFacts.value]
  const consistent = surfaces.every(fact => (
    fact.factSource === 'server'
    && fact.recordCount === strictFacts.value.recordCount
    && fact.pageCode === strictFacts.value.pageCode
  ))
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    version: pageVersion,
    moduleCode: 'PDE',
    orderRoutingExecutionUiState: orderExecutionUiState.value,
    pageFacts: panelFacts(strictFacts.value),
    apiFacts: panelFacts(apiFacts.value),
    diagnosticFacts: panelFacts(diagnosticFacts.value),
    strictFacts: panelFacts(strictFacts.value),
    acceptanceFacts: panelFacts(acceptanceFacts.value),
    factSource: strictFacts.value.factSource,
    pageAssertions: [
      { rule: 'PDE-001', passed: true },
      { rule: 'PDE-006', passed: Boolean(definition.value.nodeCode) },
      { rule: 'PDE-FACT-001', passed: consistent },
      ...(['routings','routingVersions'].includes(props.pageKind)?[{rule:'PDE-ORDER-EXECUTION-READ',passed:orderExecutionState.value==='loaded'}]:[]),
    ],
  }
}

function diagnostics() {
  return {
    version: pageVersion,
    canonicalName: definition.value.title,
    moduleCode: 'PDE',
    pageFactOwner: definition.value.pageCode,
    factSource: strictFacts.value.factSource,
    apiFacts: panelFacts(apiFacts.value),
    pageFacts: panelFacts(strictFacts.value),
    diagnosticFacts: panelFacts(diagnosticFacts.value),
    strictFacts: panelFacts(strictFacts.value),
    acceptanceFacts: panelFacts(acceptanceFacts.value),
    orderEngineeringIdentityIntake: identityIntakeFacts.value,
    testBusinessHandoff: testBusinessFacts.value,
    orderRoutingExecutionUiState: orderExecutionUiState.value,
    orderRoutingExecutionPanelFacts: orderExecutionFacts.value,
    testOperationStartFacts: orderOperationStartFacts.value,
    testWorkshopTaskFacts: orderWorkshopTaskFacts.value,
    testWorkOrderReceptionFacts: orderWorkOrderFacts.value,
    orderExecutionTestScheduleFacts: orderScheduleFacts.value,
    orderExecutionDateFacts: orderDateFacts.value,
    orderExecutionCapacityFacts: orderCapacityFacts.value,
    orderRoutingExecutionPanelLoadState: orderExecutionState.value,
    testEngineeringRoutingPanelFacts: testRoutingFacts.value,
    testEngineeringRoutingPanelLoadState: testRoutingState.value,
    bomHandoff: handoff.value,
    bomPreviewState: bomPreviewState.value,
    resultCount: strictFacts.value.recordCount ?? null,
  }
}

watch([orderExecutionFacts,orderExecutionState,orderExecutionUiState,orderCapacityFacts,orderDateFacts,orderScheduleFacts,orderWorkOrderFacts,orderWorkshopTaskFacts,orderOperationStartFacts],publish)
let refreshSequence = 0
function selectHandoffOrder(orderId) {
  bomPreviewState.value = null
  const query = { ...route.query }
  delete query.sourceCalculationId
  if (orderId) query.orderId = orderId
  else delete query.orderId
  router.replace({ path: route.path, query })
}

async function previewBomConditions(records) {
  const scopedRecords = Array.isArray(records) ? records : []
  if (!scopedRecords.length || !handoff.value?.bomHandoffStatus?.canPreview) {
    ElMessage.warning('当前订单没有可执行只读BOM条件预览的正式核算。')
    return
  }
  bomPreviewBusy.value = true
  bomPreviewState.value = null
  const gate = handoff.value.bomHandoffStatus
  try {
    const results = await Promise.all(scopedRecords.map(async record => {
      try {
        const response = await pdeApi.previewOrderBom(record.calculationId)
        if (response?.success === false) {
          return {
            calculationId: record.calculationId,
            calculationNo: record.calculationNo,
            code: response.error?.code || response.factLoadFacts?.errorCode || 'BOM_PREVIEW_FAILED',
            message: response.error?.message || response.factLoadFacts?.errorMessage || '服务端未返回预览结果。',
            previewCreated: false,
            businessWriteSideEffectCount: response.error?.details?.businessWriteSideEffectCount
              ?? gate.previewService?.businessWriteSideEffectCount,
          }
        }
        const payload = response?.data ?? response ?? {}
        return {
          calculationId: record.calculationId,
          calculationNo: record.calculationNo,
          code: payload.status || 'BOM_PREVIEW_AVAILABLE',
          message: `服务端返回${payload.rowCount ?? 0}条BOM预览行。`,
          previewCreated: true,
          businessWriteSideEffectCount: payload.businessWriteSideEffectCount
            ?? gate.previewService?.businessWriteSideEffectCount,
        }
      } catch (error) {
        return {
          calculationId: record.calculationId,
          calculationNo: record.calculationNo,
          code: error?.code || 'BOM_PREVIEW_REQUEST_FAILED',
          message: error?.message || 'BOM条件预览请求失败。',
          previewCreated: false,
          businessWriteSideEffectCount: null,
        }
      }
    }))
    const blocked = results.filter(result => result.code === 'MATERIAL_REQUIREMENT_REQUIRED')
    const previews = results.filter(result => result.previewCreated)
    const unexpected = results.filter(result => !result.previewCreated && result.code !== 'MATERIAL_REQUIREMENT_REQUIRED')
    const allBlocked = blocked.length === results.length
    const partialPreview = previews.length > 0 && blocked.length > 0 && !unexpected.length
    const allPreview = previews.length === results.length
    bomPreviewState.value = {
      code: allBlocked
        ? 'MATERIAL_REQUIREMENT_REQUIRED'
        : partialPreview
          ? 'BOM_PARTIAL_PREVIEW_AVAILABLE'
          : allPreview
            ? 'BOM_PREVIEW_AVAILABLE'
            : (unexpected[0]?.code || 'BOM_PREVIEW_MIXED_RESULT'),
      statusLabel: allBlocked
        ? '工程材料需求尚未形成'
        : partialPreview
          ? '已确认材料Preview成功；整单仍未完成'
          : allPreview
            ? 'BOM条件Preview全部成功'
            : 'BOM条件预览请求未完成',
      message: (allBlocked || partialPreview) && gate.message
        ? gate.message
        : (unexpected[0]?.message || `服务端形成${previews.length}个只读Preview。`),
      attemptCount: results.length,
      blockedCount: blocked.length,
      previewCount: previews.length,
      businessWriteSideEffectCount: gate.previewService?.businessWriteSideEffectCount,
      results,
    }
    ElMessage[allBlocked ? 'warning' : previews.length && !unexpected.length ? 'success' : 'error'](
      bomPreviewState.value.message,
    )
  } finally {
    bomPreviewBusy.value = false
  }
}
const orderRoutingPanel = ref(null)
const assigneeEntryOnly=ref(false)
async function refresh() {
  if(['routings','routingVersions'].includes(props.pageKind)){
    await nextTick()
    await orderRoutingPanel.value?.load()
    assigneeEntryOnly.value=Boolean(orderRoutingPanel.value?.isOwnEntry())
    if(assigneeEntryOnly.value){
      const payload=orderOperationStartFacts.value
      if(payload){apiFacts.value=payload.apiFacts;strictFacts.value=payload.strictFacts;diagnosticFacts.value=payload.diagnosticFacts;acceptanceFacts.value=payload.acceptanceFacts;factLoadFacts.value=payload.factLoadFacts;rows.value=payload.rows || []}
      loading.value=false;loadMessage.value='已读取本人范围内的真实任务事实。';publish();return
    }
    void testRoutingPanel.value?.load()
  }
  await testBusinessPanel.value?.load()
  const current = ++refreshSequence
  loading.value = true
  loadMessage.value = '正在读取服务端事实…'
  try {
    const params = props.pageKind === 'boms' ? { handoff: '1', orderId: route.query.orderId, sourceCalculationId: route.query.sourceCalculationId }
      : props.pageKind === 'manufacturingAdmissions' ? { orderId: route.query.orderId }
      : props.pageKind === 'manufacturingOutputs' ? {
        salesOrderItemId: route.query.salesOrderItemId,
        engineeringDocumentVersionId: route.query.engineeringDocumentVersionId,
        predecessorOutputId: route.query.predecessorOutputId,
      } : {}
    const response = await pdeApi.facts(definition.value.resource, params)
    if (current !== refreshSequence) return
    const expectedApiUrl = `/api/pde/${definition.value.resource}/`
    const { data: payload, factLoadFacts: loadedFacts } = readPceFactLoadEnvelope(
      response,
      expectedApiUrl,
      definition.value.pageCode,
    )
    const previousOrderId = handoff.value?.selectedOrderId
    rows.value = payload.rows || []
    handoff.value = payload.handoff || null
    if (previousOrderId !== handoff.value?.selectedOrderId) bomPreviewState.value = null
    handoffReadFailure.value = payload.handoffReadFailure || null
    factLoadFacts.value = loadedFacts
    apiFacts.value = payload.apiFacts || {}
    strictFacts.value = payload.strictFacts || {}
    diagnosticFacts.value = payload.diagnosticFacts || {}
    acceptanceFacts.value = payload.acceptanceFacts || {}
    loadMessage.value = loadedFacts.factLoadStatus === 'empty_valid'
      ? '已成功读取，当前筛选范围没有匹配记录。'
      : '已成功读取服务端事实。'
    publish()
  } catch (error) {
    if (current !== refreshSequence) return
    rows.value = []
    handoff.value = null
    handoffReadFailure.value = null
    apiFacts.value = {}
    strictFacts.value = {}
    diagnosticFacts.value = {}
    acceptanceFacts.value = {}
    factLoadFacts.value = error?.factLoadFacts || createReadFailedFactLoad({
      apiUrl: `/api/pde/${definition.value.resource}/`,
      httpStatus: error?.response?.status || 0,
      errorCode: error?.code || 'FACT_READ_FAILED',
      errorMessage: error?.message || `${definition.value.title}服务端事实读取失败`,
    })
    loadMessage.value = failureMessage(factLoadFacts.value)
    ElMessage.error(loadMessage.value)
    publish()
  } finally {
    if (current === refreshSequence) loading.value = false
  }
}

let provider
const handleAuthenticationChanged = event => {
  if (event?.detail?.authenticated) refresh()
}
onMounted(async () => {
  provider = {
    factOwner: definition.value.pageCode,
    refresh,
    buildDiagnostics: diagnostics,
  }
  observability?.register?.(provider)
  window.addEventListener('pce:authentication-changed', handleAuthenticationChanged)
  await refresh()
  observability?.register?.(provider)
})
onBeforeUnmount(() => {
  refreshSequence += 1
  window.removeEventListener('pce:authentication-changed', handleAuthenticationChanged)
  observability?.unregister?.(provider)
})
watch(() => props.pageKind, refresh)
watch(() => [route.query.orderId, route.query.sourceCalculationId], () => { if (['boms', 'manufacturingAdmissions'].includes(props.pageKind)) refresh() })
watch(() => [route.query.salesOrderItemId, route.query.engineeringDocumentVersionId, route.query.predecessorOutputId],
  () => { if (props.pageKind === 'manufacturingOutputs') refresh() })
</script>

<style scoped>
.pde-page { display:grid; min-width:0; gap:18px; padding:20px; background:#f4f7fb; }
.card { min-width:0; padding:20px; border:1px solid #dce4ed; border-radius:12px; background:#fff; }
.facts h2 { margin-top:0; }
.relationship-facts h2 { margin-top:0; }
.relationship-facts li { margin:7px 0; color:#334155; }
.facts > p,.boundary > p { color:#64748b; }
.fact-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; }
.fact-grid article { display:grid; gap:5px; padding:12px; border-radius:9px; background:#f5f8fb; }
.fact-grid small { color:#64748b; }
.boundary { border-color:#b8d8c4; background:#f5fbf7; }
.relationship-chain { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin:14px 0; color:#1f4f3b; }
.load-state { border-color:#f3c57b; background:#fffaf0; }
.load-state-actions { display:flex; gap:10px; margin-top:14px; }
.load-state > p { margin:12px 0 0; color:#7c4a03; }
</style>
