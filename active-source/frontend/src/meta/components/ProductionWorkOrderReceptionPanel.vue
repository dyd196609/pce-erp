<template>
  <section ref="panelElement" class="work-order-reception-panel panel block" data-section="production-work-order-reception" data-fact-source="server"
    :data-load-status="state.readState" :data-strict-facts="JSON.stringify(state.facts)">
    <h2>生产工单：正式排程接收与准入</h2>
    <p v-if="upstreamRelationship">{{ upstreamRelationship.relationship }}：{{ upstreamRelationship.businessChain.join(' → ') }}</p>
    <p v-if="!displayFacts?.execution">本页只读接收已保存的正式排程并核对下达准入，不生成或下达生产工单。以下计划时段不代表车间实际开工、实际完工或报工。</p>
    <p v-else>先读取正式排程与当前准入，再由用户分别明确生成生产工单、下达生产工单；每次执行由后台重新核验。以下计划时段不代表车间实际开工、实际完工或报工。</p>
    <div class="reception-controls">
      <label>生产计划<select :value="state.selectedPlanId" aria-label="工单接收生产计划" :disabled="parentLoading || loading || executionBusy" @change="selectPlan($event.target.value)">
        <option value="">请选择生产计划</option><option v-for="plan in plans" :key="plan.id" :value="String(plan.id)">{{ plan.label }}</option>
      </select></label>
      <button type="button" :disabled="!state.selectedPlanId || parentLoading || loading || executionBusy" @click="controller.load()">刷新接收与准入结果</button>
    </div>
    <p v-if="planningReadDenied" role="note" data-section="work-order-plan-read-permission-note">当前账号没有计划查看权限。车间接收请使用下方‘车间接收已下达工单’。</p>
    <p v-if="state.readState === 'idle'">请选择生产计划；来源排程、接收结论和下达资格尚未读取。</p>
    <p v-else-if="loading" role="status">正在读取正式排程来源及当前准入检查，完成前不展示旧资格或执行结论。</p>
    <p v-if="state.error" role="alert" class="reception-error">{{ state.error }}</p>
    <p v-if="!state.facts && state.lastReadDisplay" role="alert" class="reception-error" data-section="work-order-previous-read-display">以下仅为同一账号、公司与计划的上次只读来源展示；当前资格及执行结果尚未核实，不作为本次放行依据。请重新读取当前结果。</p>
    <p v-if="state.executionMessage" role="status" class="work-order-boundary" data-section="work-order-execution-result">{{ state.executionMessage }}</p>
    <button v-if="state.executionState==='readback_pending'" type="button" :disabled="loading || executionBusy" @click="controller.load()">仅重新读取执行结果</button>
    <template v-if="displayFacts">
      <dl class="reception-facts" data-section="work-order-reception-summary">
        <div><dt>当前计划</dt><dd>{{ displayFacts.productionPlanNo }}</dd></div>
        <div><dt>{{ state.facts?'当前状态':'上次读取状态' }}</dt><dd><PceBusinessStatus :status-label="displayFacts.statusLabel" /></dd></div>
        <div><dt>显示时区</dt><dd>{{ displayFacts.timezoneLabel }}</dd></div>
        <div><dt>当前环境</dt><dd>{{ displayFacts.modeLabel }}</dd></div>
      </dl>
      <section class="reception-readback" data-section="work-order-reception-source-summary">
        <h3>接收的正式排程来源</h3>
        <p v-if="!displayFacts.sourceSchedule">未取得有效正式排程来源，来源步骤及资源占用未知。</p>
        <template v-if="displayFacts.sourceSchedule">
          <PceBusinessStatus :status-label="displayFacts.sourceSchedule.statusLabel" />
          <dl class="reception-facts">
            <div><dt>来源排程ID</dt><dd>{{ displayFacts.sourceSchedule.id }}</dd></div>
            <div><dt>来源修订</dt><dd>{{ displayFacts.sourceSchedule.revision }}</dd></div>
            <div><dt>来源版本</dt><dd>{{ displayFacts.sourceSchedule.version }}</dd></div>
            <div><dt>来源快照Hash</dt><dd>{{ displayFacts.sourceSchedule.snapshotHash }}</dd></div>
            <div><dt>来源步骤数量</dt><dd>{{ displayFacts.sourceSchedule.stepCount }}</dd></div>
            <div><dt>来源有效加工占用数量</dt><dd>{{ displayFacts.sourceSchedule.activeReservationCount }}</dd></div>
            <div><dt>来源计划开始时间</dt><dd>{{ displayFacts.sourceSchedule.startLabel }}</dd></div>
            <div><dt>来源计划完成时间</dt><dd>{{ displayFacts.sourceSchedule.endLabel }}</dd></div>
          </dl>
        </template>
      </section>
      <section v-if="displayFacts.execution" class="reception-readback" data-section="production-work-order-execution">
        <h3>正式生产工单</h3><PceBusinessStatus :status-label="displayFacts.workOrder.statusLabel" />
        <template v-if="displayFacts.workOrder.generated">
          <dl class="reception-facts" data-section="production-work-order-header">
            <div><dt>生产工单号</dt><dd>{{ displayFacts.workOrder.no }}</dd></div>
            <div><dt>工单版本</dt><dd>{{ displayFacts.workOrder.version }}</dd></div>
            <div><dt>生产物料</dt><dd>{{ displayFacts.workOrder.materialCode }} · {{ displayFacts.workOrder.materialName }}</dd></div>
            <div><dt>工单数量与单位</dt><dd>{{ displayFacts.workOrder.quantityLabel }}</dd></div>
            <div><dt>生成时间</dt><dd>{{ displayFacts.workOrder.createdAtLabel }}</dd></div>
            <div><dt>下达时间</dt><dd>{{ displayFacts.workOrder.releasedAtLabel }}</dd></div>
            <div><dt>来源排程ID / 修订 / 版本</dt><dd>{{ displayFacts.workOrder.sourceScheduleId }} / {{ displayFacts.workOrder.sourceScheduleRevision }} / {{ displayFacts.workOrder.sourceScheduleVersion }}</dd></div>
            <div><dt>来源排程快照Hash</dt><dd>{{ displayFacts.workOrder.sourceScheduleSnapshotHash }}</dd></div>
            <div><dt>工单快照Hash</dt><dd>{{ displayFacts.workOrder.snapshotHash }}</dd></div>
            <div><dt>工单工序数量</dt><dd>{{ displayFacts.workOrder.operationCount }}</dd></div>
          </dl>
          <h4>工单路线来源</h4>
          <dl v-for="(row,index) in displayFacts.workOrder.routeProvenance" :key="index" class="reception-facts" data-section="work-order-route-provenance">
            <div><dt>正式路线版本</dt><dd>{{ row.statusLabel }}</dd></div>
            <div><dt>根路线 / 有效路线版本ID</dt><dd>{{ row.rootRoutingVersionId }} / {{ row.effectiveRoutingVersionId }}</dd></div>
            <div><dt>原制造输出 / 有效制造输出ID</dt><dd>{{ row.originalManufacturingOutputId }} / {{ row.effectiveManufacturingOutputId }}</dd></div>
          </dl>
          <h4>正式工单工序</h4>
          <p>工序与路线逐条保留正式来源；空字段表示来源未登记或不适用，不用工单总数量补齐工序工作量。</p>
          <PceEnterpriseListTable :ref="element => operationsTable.tableRef = element" :contract="operationsContract" page-id="production-work-order-operations" table-id="production-work-order-operations-table"
            :rows="operationRows" :table-rows="operationsTable.filteredRows" :filter-schema="operationFilters" :filters="operationsTable.filters"
            v-model:quick-search="operationsTable.quickSearch" :advanced-visible="operationsTable.advancedVisible" :selected-count="operationsTable.selectedRows.length"
            :active-filter-count="operationsTable.activeFilterCount" :sort-text="operationsTable.sortText" row-key="id" primary-field="operationName" primary-label="工单工序"
            :primary-width="200" :show-action-column="false" :default-page-size="50"
            @search="operationsTable.appliedSearch = operationsTable.quickSearch" @toggle-advanced="operationsTable.advancedVisible = !operationsTable.advancedVisible"
            @clear-filters="operationsTable.clearFilters" @clear-sort="operationsTable.clearSort" @clear-selection="operationsTable.clearSelection" @export-current="operationsTable.exportCurrent"
            @selection-change="operationsTable.selectedRows = $event" @sort-change="operationsTable.handleSort">
            <template #columns><el-table-column v-for="field in operationFields" :key="field.key" :prop="field.key" :label="field.label" min-width="180" /></template>
          </PceEnterpriseListTable>
          <details><summary>查看正式工单状态迁移记录</summary>
            <p v-for="row in displayFacts.workOrder.stateTransitionHistory" :key="row.id">{{ row.actionLabel }}：{{ row.sourceStateLabel }} → {{ row.targetStateLabel }}；版本 {{ row.version }}；操作人ID {{ row.operatorId }}；{{ row.timestampLabel }}；原因：{{ row.reason }}</p>
          </details>
        </template>
        <p>生成与下达是两个独立操作，不自动连做；生成不推进原计划或排程，也不代表车间开工。</p>
        <label>本次操作原因（必填）<textarea v-model="state.reason" aria-label="生产工单操作原因" :disabled="loading || executionBusy || state.executionState==='readback_pending'" rows="3" /></label>
        <div v-for="action in executionActions" :key="action.actionCode" class="execution-action">
          <button type="button" :data-action-code="action.actionCode" :data-action-id="action.actionId" :disabled="!action.enabled || !state.reason.trim() || loading || parentLoading || executionBusy || state.executionState==='readback_pending'"
            @click="controller.execute(action.key)">{{ action.displayName }}</button>
          <p v-if="!action.enabled">{{ action.disabledReason }}</p>
        </div>
      </section>
      <section v-if="state.facts" class="reception-readback" data-section="work-order-reception-conclusions">
        <h3>排程接收结论</h3><PceBusinessStatus :status-label="displayFacts.reception.statusLabel" />
        <p v-for="(issue, index) in displayFacts.reception.issues" :key="`receive-${index}`">{{ issue.statusLabel }}</p>
        <h3>生产工单下达准入结论</h3><PceBusinessStatus :status-label="displayFacts.releaseAdmission.statusLabel" />
        <dl v-if="displayFacts.responsibility.currentActorEvidence?.username && displayFacts.responsibility.currentActorEvidence?.companyName && displayFacts.responsibility.currentActorEvidence?.companyCode"
          class="reception-facts" data-section="work-order-release-current-actor">
          <div><dt>本次核定后台账号</dt><dd>{{ displayFacts.responsibility.currentActorEvidence.username }}</dd></div>
          <div><dt>本次核定公司</dt><dd>{{ displayFacts.responsibility.currentActorEvidence.companyName }}（{{ displayFacts.responsibility.currentActorEvidence.companyCode }}）</dd></div>
        </dl>
        <ul v-if="displayFacts.releaseAdmission.issues.length" class="admission-issues">
          <li v-for="(issue, index) in displayFacts.releaseAdmission.issues" :key="`release-${index}`">
            <strong v-if="issue.categoryLabel">{{ issue.categoryLabel }}：</strong>{{ issue.statusLabel }}
          </li>
        </ul>
        <p class="work-order-boundary">{{ displayFacts.workOrder.statusLabel }}</p>
      </section>
      <section v-if="state.facts && displayFacts.releaseAdmission.remediations?.length" class="reception-readback" data-section="work-order-release-remediations">
        <h3>待补齐事项与操作路径</h3>
        <ol class="admission-remediations"><li v-for="(item, index) in displayFacts.releaseAdmission.remediations" :key="`remedy-${index}`">
          <p>{{ item.statusLabel }}</p><p>处理路径：{{ item.pathLabel }}</p>
        </li></ol>
      </section>
      <section v-if="state.facts" class="reception-readback" data-section="work-order-release-checks">
        <h3>当前下达准入检查</h3>
        <p v-for="check in displayFacts.releaseAdmission.checks" :key="check.checkCode"><PceBusinessStatus :status-label="check.statusLabel" /></p>
        <h3>责任与操作分工</h3>
        <dl class="reception-facts"><div><dt>工单准备及后续下达</dt><dd>{{ displayFacts.responsibility.preparationRoleLabel }}</dd></div>
          <div><dt>后续接收及执行</dt><dd>{{ displayFacts.responsibility.executionRoleLabel }}</dd></div></dl>
        <p>{{ displayFacts.responsibility.statusLabel }}</p>
        <h3>当前工程来源复核</h3><PceBusinessStatus :status-label="displayFacts.currentSourceChecks.statusLabel" />
        <p v-for="(issue, index) in displayFacts.currentSourceChecks.issues" :key="`source-${index}`">{{ issue.statusLabel }}</p>
        <details v-if="displayFacts.currentSourceChecks.steps.length"><summary>查看逐步骤来源复核</summary>
          <p v-for="step in displayFacts.currentSourceChecks.steps" :key="step.stepId">{{ step.statusLabel }}</p>
        </details>
      </section>
      <section class="reception-readback" data-section="work-order-reception-source">
        <h3>来源正式步骤与占用</h3>
        <template v-if="displayFacts.sourceSchedule">
          <label>来源工序日期与用时明细<select v-model="selectedStepId" aria-label="工单接收工序明细"><option value="">请选择工序</option>
            <option v-for="step in stepRows" :key="step.stepId" :value="String(step.stepId)">{{ step.stepLabel }}</option></select></label>
          <section v-if="selectedStep" class="reception-readback" data-section="work-order-reception-step-detail">
            <h4>{{ selectedStep.stepLabel }}</h4><PceBusinessStatus :status-label="selectedStep.statusLabel" />
            <dl class="reception-facts"><div v-for="field in stepFields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ selectedStep[field.key] }}</dd></div></dl>
          </section>
          <PceEnterpriseListTable :ref="element => stepsTable.tableRef = element" :contract="stepsContract" page-id="work-order-reception-steps" table-id="work-order-reception-steps-table"
            :rows="stepRows" :table-rows="stepsTable.filteredRows" :filter-schema="stepFilters" :filters="stepsTable.filters"
            v-model:quick-search="stepsTable.quickSearch" :advanced-visible="stepsTable.advancedVisible" :selected-count="stepsTable.selectedRows.length"
            :active-filter-count="stepsTable.activeFilterCount" :sort-text="stepsTable.sortText" row-key="stepId" primary-field="stepLabel" primary-label="来源正式工序"
            :primary-width="200" :show-action-column="false" :default-page-size="50"
            @search="stepsTable.appliedSearch = stepsTable.quickSearch" @toggle-advanced="stepsTable.advancedVisible = !stepsTable.advancedVisible"
            @clear-filters="stepsTable.clearFilters" @clear-sort="stepsTable.clearSort" @clear-selection="stepsTable.clearSelection" @export-current="stepsTable.exportCurrent"
            @selection-change="stepsTable.selectedRows = $event" @sort-change="stepsTable.handleSort">
            <template #columns>
              <el-table-column label="来源状态" min-width="155"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" /></template></el-table-column>
              <el-table-column v-for="field in stepFields" :key="field.key" :prop="field.key" :label="field.label" min-width="180" />
            </template>
          </PceEnterpriseListTable>
          <h3>来源正式资源占用</h3>
          <PceEnterpriseListTable :ref="element => reservationsTable.tableRef = element" :contract="reservationsContract" page-id="work-order-reception-reservations" table-id="work-order-reception-reservations-table"
            :rows="reservationRows" :table-rows="reservationsTable.filteredRows" :filter-schema="reservationFilters" :filters="reservationsTable.filters"
            v-model:quick-search="reservationsTable.quickSearch" :advanced-visible="reservationsTable.advancedVisible" :selected-count="reservationsTable.selectedRows.length"
            :active-filter-count="reservationsTable.activeFilterCount" :sort-text="reservationsTable.sortText" row-key="id" primary-field="primaryLabel" primary-label="来源正式占用记录"
            :primary-width="190" :show-action-column="false" :default-page-size="20"
            @search="reservationsTable.appliedSearch = reservationsTable.quickSearch" @toggle-advanced="reservationsTable.advancedVisible = !reservationsTable.advancedVisible"
            @clear-filters="reservationsTable.clearFilters" @clear-sort="reservationsTable.clearSort" @clear-selection="reservationsTable.clearSelection" @export-current="reservationsTable.exportCurrent"
            @selection-change="reservationsTable.selectedRows = $event" @sort-change="reservationsTable.handleSort">
            <template #columns>
              <el-table-column prop="workCenterLabel" label="工作中心" min-width="150" /><el-table-column prop="stepLabel" label="所属工序" min-width="170" />
              <el-table-column label="占用状态" min-width="130"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" /></template></el-table-column>
              <el-table-column prop="startLabel" label="占用计划开始时间" min-width="195" /><el-table-column prop="endLabel" label="占用计划完成时间" min-width="195" />
              <el-table-column prop="minutesLabel" label="加工占用分钟" min-width="145" />
            </template>
          </PceEnterpriseListTable>
        </template>
      </section>
    </template>
    <ProductionWorkOrderWorkshopReceiptPanel ref="workshopReceiptPanel" />
  </section>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { planningApi } from '@/api/planning.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import { createWorkOrderReceptionController, createWorkOrderReceptionState, projectWorkOrderExecutionActions } from '@/meta/runtime/productionWorkOrderReception.js'
import { listBusinessModuleRelationships } from '@/meta/process/businessProcessRegistry.js'
import ProductionWorkOrderWorkshopReceiptPanel from './ProductionWorkOrderWorkshopReceiptPanel.vue'

const props = defineProps({ plans: { type: Array, default: () => [] }, parentLoading: { type: Boolean, default: false }, planningReadDenied: { type: Boolean, default: false } })
const route = useRoute(), router = useRouter(), panelElement = ref(null), selectedStepId = ref('')
const state = reactive(createWorkOrderReceptionState()), workshopReceiptPanel = ref(null)
const upstreamRelationship = listBusinessModuleRelationships().find(row => row.fromModule === 'APS' && row.toModule === 'MES')
const owner = () => JSON.stringify([getTabAuthEpoch(), readTabIdentity()?.userId, readTabIdentity()?.companyId])
const controller = createWorkOrderReceptionController({ state, api: planningApi, companyId: () => readTabIdentity()?.companyId, owner })
const loading = computed(() => state.readState === 'loading')
const displayFacts = computed(() => state.facts || state.lastReadDisplay)
const executionBusy = computed(() => ['writing', 'reading'].includes(state.executionState))
const executionActions = computed(() => projectWorkOrderExecutionActions(state.facts))
const stepRows = computed(() => displayFacts.value?.sourceSchedule?.steps || [])
const reservationRows = computed(() => displayFacts.value?.sourceSchedule?.reservations || [])
const operationRows = computed(() => displayFacts.value?.workOrder?.operations || [])
const selectedStep = computed(() => stepRows.value.find(row => String(row.stepId) === selectedStepId.value) || null)
const stepFields = Object.freeze([{ key: 'processingTimeLabel', label: '加工时间' }, { key: 'preparationTimeLabel', label: '准备时间' },
  { key: 'transferTimeLabel', label: '转运时间' }, { key: 'totalWorkTimeLabel', label: '合计工作分钟' },
  { key: 'startLabel', label: '计划开始时间' }, { key: 'endLabel', label: '计划完成时间' }])
const stepsContract = createPceEnterpriseListContract({ pageCode: 'work-order-reception-steps', pageType: 'list', title: '工单接收来源工序', moduleCode: 'MES' })
const reservationsContract = createPceEnterpriseListContract({ pageCode: 'work-order-reception-reservations', pageType: 'list', title: '工单接收来源占用', moduleCode: 'MES' })
const operationsContract = createPceEnterpriseListContract({ pageCode: 'production-work-order-operations', pageType: 'list', title: '正式生产工单工序', moduleCode: 'MES' })
const operationFields = Object.freeze([{key:'sequence',label:'正式工序顺序'},{key:'workCenterName',label:'工作中心'},{key:'workloadLabel',label:'工序工作量与单位'},
  {key:'startLabel',label:'计划开始时间'},{key:'endLabel',label:'计划完成时间'},{key:'rootRoutingVersionId',label:'根路线版本ID'},{key:'effectiveRoutingVersionId',label:'有效路线版本ID'},
  {key:'rootStepId',label:'根排程步骤ID'},{key:'effectiveStepId',label:'有效排程步骤ID'},
  {key:'originalManufacturingOutputId',label:'原制造输出ID'},{key:'effectiveManufacturingOutputId',label:'有效制造输出ID'}])
const operationFilters = Object.freeze([{field:'operationName',label:'工单工序',filterType:'text'},{field:'workCenterName',label:'工作中心',filterType:'select',optionsProvider:'current_result'}])
const stepFilters = Object.freeze([{ field: 'stepLabel', label: '工序', filterType: 'text' }, { field: 'statusLabel', label: '来源状态', filterType: 'select', optionsProvider: 'current_result' }])
const reservationFilters = Object.freeze([{ field: 'workCenterLabel', label: '工作中心', filterType: 'text' }, { field: 'stepLabel', label: '所属工序', filterType: 'text' },
  { field: 'statusLabel', label: '占用状态', filterType: 'select', optionsProvider: 'current_result' }])
const stepsTable = reactive(usePceEnterpriseListRuntime({ rows: stepRows, filterSchema: stepFilters, pageCode: 'work-order-reception-steps',
  searchFields: ['stepLabel', 'statusLabel'], exportFileName: () => '工单接收来源工序.csv',
  exportColumns: [{ field: 'stepLabel', label: '工序' }, { field: 'statusLabel', label: '来源状态' }, ...stepFields.map(field => ({ field: field.key, label: field.label }))] }))
const reservationsTable = reactive(usePceEnterpriseListRuntime({ rows: reservationRows, filterSchema: reservationFilters, pageCode: 'work-order-reception-reservations',
  searchFields: ['primaryLabel', 'workCenterLabel', 'stepLabel', 'statusLabel'], exportFileName: () => '工单接收来源占用.csv',
  exportColumns: [{ field: 'primaryLabel', label: '占用记录' }, { field: 'workCenterLabel', label: '工作中心' }, { field: 'stepLabel', label: '所属工序' },
    { field: 'statusLabel', label: '占用状态' }, { field: 'startLabel', label: '计划开始时间' }, { field: 'endLabel', label: '计划完成时间' }, { field: 'minutesLabel', label: '加工占用分钟' }] }))
const operationsTable = reactive(usePceEnterpriseListRuntime({rows:operationRows,filterSchema:operationFilters,pageCode:'production-work-order-operations',
  searchFields:['operationName','workCenterName'],exportFileName:()=> '正式生产工单工序.csv',
  exportColumns:[{field:'operationName',label:'工单工序'},...operationFields.map(field=>({field:field.key,label:field.label}))]}))

async function selectPlan(planId) {
  await router.replace({ query: { ...route.query, section: 'work-order-reception', productionPlanId: planId || undefined } })
  if (String(planId || '') !== state.selectedPlanId) await controller.select(planId)
}
async function syncPlan() {
  if (props.parentLoading) { controller.invalidate(); return }
  const planId = String(route.query.productionPlanId || state.selectedPlanId || '')
  if (!planId) return
  if (!props.plans.some(plan => String(plan.id) === planId)) { controller.invalidate(); return }
  if (planId !== state.selectedPlanId) await controller.select(planId)
}
async function focusPanel() {
  if (route.query.section !== 'work-order-reception') return
  await nextTick(); panelElement.value?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
}
function authenticationChanged() { controller.invalidate() }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const provider = { factOwner: 'production-work-order-reception', refresh: async () => Promise.all([controller.load(),workshopReceiptPanel.value?.refresh()]),
  buildDiagnostics: () => ({ factSource: 'server', pageFactOwner: 'production-work-order-reception',
    strictFacts: state.facts || { passed: false, sourceSchedule: null, resultCount: null, stepCount: null, activeReservationCount: null },
    strictServerFacts: state.facts, factLoadFacts: state.factLoadFacts, readState: state.readState, executionReadbackState: state.executionState,
    executionMessage: state.executionMessage || null, errorMessage: state.error || null,
    workshopReception: workshopReceiptPanel.value?.buildDiagnostics() || null }) }
defineExpose({refresh:provider.refresh,buildDiagnostics:provider.buildDiagnostics})
observability?.register?.(provider)
watch([() => route.query.productionPlanId, () => props.parentLoading, () => props.plans], syncPlan, { immediate: true })
watch(() => route.query.section, focusPanel)
watch(() => state.selectedPlanId, () => { selectedStepId.value = ''; stepsTable.clearSelection(); reservationsTable.clearSelection(); operationsTable.clearSelection() })
onMounted(() => { globalThis.window?.addEventListener?.('pce:authentication-changed', authenticationChanged); focusPanel() })
onBeforeUnmount(() => { controller.invalidate(); globalThis.window?.removeEventListener?.('pce:authentication-changed', authenticationChanged); observability?.unregister?.(provider) })
</script>

<style scoped>
.work-order-reception-panel{min-width:0;scroll-margin-top:12px}.work-order-reception-panel p{line-height:1.6}.reception-controls{display:flex;flex-wrap:wrap;gap:10px;align-items:end;margin:12px 0}.work-order-reception-panel label{display:block;max-width:540px;margin:12px 0;font-weight:600}.work-order-reception-panel textarea{display:block;box-sizing:border-box;width:100%;margin-top:6px;padding:9px;border:1px solid #cbd5e1;border-radius:7px;font:inherit;resize:vertical}.execution-action{display:inline-block;vertical-align:top;max-width:100%;margin:6px 16px 6px 0}.execution-action p{max-width:420px;overflow-wrap:anywhere}.work-order-reception-panel select{display:block;box-sizing:border-box;width:100%;margin-top:6px;padding:9px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}.work-order-reception-panel button{padding:9px 12px;border:1px solid #3568dc;border-radius:7px;background:#3568dc;color:#fff;cursor:pointer}.work-order-reception-panel button:disabled{opacity:.55;cursor:not-allowed}.reception-readback{margin-top:16px;padding-top:12px;border-top:1px solid #dce4ef;min-width:0}.reception-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 20px;margin:12px 0}.reception-facts dt{font-size:12px;color:#64748b}.reception-facts dd{margin:4px 0 0;font-weight:600;overflow-wrap:anywhere}.reception-error{padding:9px;background:#fff2f0;color:#9f241d;border-radius:7px}.work-order-boundary{padding:10px;background:#eef5ff;border-radius:7px;font-weight:600}@media(max-width:540px){.reception-facts{grid-template-columns:1fr}.reception-controls{display:block}}
</style>
