<template>
  <section ref="panelElement" class="formal-scheduling-panel panel block" data-section="production-plan-formal-scheduling" data-fact-source="server"
    :data-load-status="state.readState" :data-strict-facts="JSON.stringify(state.facts)">
    <h2>生产计划正式排程与资源占用</h2>
    <p>此处办理正式排程及加工资源占用。先读取计划并检查准入、精确用途依据和真实占用冲突，再明确保存；旧“全路线只读日期预览”继续只用于试算。</p>
    <div class="scheduling-controls">
      <label>生产计划<select :value="state.selectedPlanId" aria-label="正式排程生产计划" :disabled="parentLoading || state.writing" @change="selectPlan($event.target.value)">
        <option value="">请选择生产计划</option><option v-for="plan in plans" :key="plan.id" :value="String(plan.id)">{{ plan.label }}</option>
      </select></label>
      <button type="button" :disabled="!state.selectedPlanId || busy" @click="controller.load()">刷新正式结果</button>
    </div>
    <p v-if="state.readState === 'idle'">选择生产计划后读取当前正式版本、步骤及资源占用；当前事实未知。</p>
    <p v-else-if="state.readState === 'loading'" role="status">正在读取正式排程依据及结果；准入与冲突检查可能需要等待，完成前不展示旧结果。</p>
    <p v-if="state.error" class="scheduling-error" role="alert">{{ state.error }}</p>
    <p v-if="state.message" class="scheduling-message" role="status">{{ state.message }}</p>
    <template v-if="state.facts">
      <dl class="scheduling-facts" data-section="formal-scheduling-summary">
        <div><dt>当前计划</dt><dd>{{ state.facts.productionPlanNo }}</dd></div>
        <div><dt>正式状态</dt><dd><PceBusinessStatus :status-label="state.facts.statusLabel" /></dd></div>
        <div><dt>计划开始日期</dt><dd>{{ state.facts.savedStartDateLabel }}</dd></div>
        <div><dt>需求日期</dt><dd>{{ state.facts.requiredDateLabel }}</dd></div>
        <div><dt>显示时区</dt><dd>{{ state.facts.timezoneLabel }}</dd></div>
        <div><dt>当前环境</dt><dd>{{ state.facts.modeLabel }}</dd></div>
        <div><dt>正式版本数</dt><dd>{{ state.facts.scheduleCount }}</dd></div>
        <div><dt>当前有效加工占用</dt><dd>{{ state.facts.activeReservationCount }}</dd></div>
      </dl>
      <p v-if="state.facts.actionAuthorization.reason">{{ state.facts.actionAuthorization.reason }}</p>
      <section v-if="state.facts.admission" class="scheduling-readback" data-section="formal-scheduling-admission">
        <h3>本次正式准入与冲突检查</h3>
        <PceBusinessStatus :status-label="state.facts.admission.statusLabel" />
        <dl class="scheduling-facts"><div><dt>检查开始时间</dt><dd>{{ state.facts.admission.startLabel }}</dd></div>
          <div><dt>检查结束时间</dt><dd>{{ state.facts.admission.endLabel }}</dd></div></dl>
        <p v-for="(issue, index) in state.facts.admission.blockers" :key="`block-${index}`" class="scheduling-error">{{ issue.statusLabel }}</p>
        <p v-for="(conflict, index) in state.facts.admission.conflicts" :key="`conflict-${index}`" class="scheduling-error">{{ conflict.statusLabel }}</p>
      </section>
      <section v-if="state.facts.scopeGrantRequests.length" class="scheduling-readback" data-section="formal-scheduling-scope">
        <h3>精确用途依据</h3>
        <p>只读检查和保存排程不会自动增加用途。确认以下准确范围及指令依据后，才可单独办理本范围用途证明；不改变原始产能用途或其它计划权限。</p>
        <label>待确认精确范围<select v-model="state.selectedScopeIndex" aria-label="待确认精确用途范围" :disabled="busy">
          <option value="">请选择本次范围</option><option v-for="(request, index) in state.facts.scopeGrantRequests" :key="index" :value="String(index)">{{ request.scopeLabel }}</option>
        </select></label>
        <p v-if="selectedScopeRequest">{{ selectedScopeRequest.statusLabel }}</p>
        <dl v-if="selectedScopeRequest" class="scheduling-facts"><div><dt>用途依据来源</dt><dd>{{ selectedScopeRequest.referenceLabel }}</dd></div>
          <div><dt>生效日期</dt><dd>{{ selectedScopeRequest.effectiveFromLabel }}</dd></div><div><dt>截止日期</dt><dd>{{ selectedScopeRequest.effectiveToLabel }}</dd></div></dl>
        <label>指令依据<textarea v-model="state.instructionReference" aria-label="精确用途指令依据" maxlength="500" :disabled="busy" /></label>
      </section>
      <label class="scheduling-reason">操作原因<textarea v-model="state.reason" aria-label="正式排程操作原因" maxlength="300" :disabled="busy" /></label>
      <div class="scheduling-actions" data-section="formal-scheduling-actions">
        <div v-for="action in state.facts.availableActions" :key="action.actionCode" class="scheduling-action">
          <button type="button" :data-action-code="action.actionCode"
            :aria-describedby="`formal-scheduling-${action.actionCode}-availability`"
            :disabled="!action.enabled || busy || state.awaitingReadback" @click="controller.execute(action.actionCode)">{{ action.displayName }}</button>
          <p :id="`formal-scheduling-${action.actionCode}-availability`" class="scheduling-action-explanation"
            :data-action-availability="action.actionCode">{{ action.availabilityLabel }}</p>
        </div>
      </div>
      <p>保存会生成正式版本、步骤及加工资源占用。撤销只释放该版本对应的占用并保留版本、步骤和审计历史；不会删除原分配或修改计划需求日期。</p>
      <section class="scheduling-readback" data-section="formal-scheduling-versions">
        <h3>正式版本与步骤回读</h3>
        <p v-if="!state.facts.activeSchedule">当前没有生效的正式排程版本。</p>
        <label v-if="state.facts.history.length">查看正式版本<select v-model="state.selectedScheduleId" aria-label="正式排程版本" :disabled="busy">
          <option v-for="schedule in state.facts.history" :key="schedule.id" :value="String(schedule.id)">修订 {{ schedule.revision }} · {{ schedule.statusLabel }}</option>
        </select></label>
        <template v-if="selectedSchedule">
          <PceBusinessStatus :status-label="selectedSchedule.statusLabel" />
          <dl class="scheduling-facts"><div><dt>正式开始时间</dt><dd>{{ selectedSchedule.startLabel }}</dd></div><div><dt>正式完工时间</dt><dd>{{ selectedSchedule.endLabel }}</dd></div></dl>
          <dl class="scheduling-facts"><div><dt>本版本步骤数</dt><dd>{{ selectedSchedule.stepCount }}</dd></div><div><dt>本版本加工分段数</dt><dd>{{ selectedSchedule.processingSegmentCount }}</dd></div></dl>
          <label>工序日期与用时明细<select v-model="selectedStepId" aria-label="正式排程工序明细"><option value="">请选择工序</option>
            <option v-for="step in stepRows" :key="step.stepId" :value="String(step.stepId)">{{ step.stepLabel }}</option></select></label>
          <section v-if="selectedStep" class="scheduling-readback" data-section="formal-scheduling-step-detail">
            <h4>{{ selectedStep.stepLabel }}</h4><PceBusinessStatus :status-label="selectedStep.statusLabel" />
            <dl class="scheduling-facts"><div v-for="field in stepDetailFields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ selectedStep[field.key] }}</dd></div></dl>
          </section>
          <PceEnterpriseListTable :ref="element => stepsTable.tableRef = element" :contract="stepsContract" page-id="formal-scheduling-steps" table-id="formal-scheduling-steps-table"
            :rows="stepRows" :table-rows="stepsTable.filteredRows" :filter-schema="stepFilters" :filters="stepsTable.filters"
            v-model:quick-search="stepsTable.quickSearch" :advanced-visible="stepsTable.advancedVisible" :selected-count="stepsTable.selectedRows.length"
            :active-filter-count="stepsTable.activeFilterCount" :sort-text="stepsTable.sortText" row-key="stepId" primary-field="stepLabel" primary-label="正式排程工序"
            :primary-width="200" :show-action-column="false" :default-page-size="50"
            @search="stepsTable.appliedSearch = stepsTable.quickSearch" @toggle-advanced="stepsTable.advancedVisible = !stepsTable.advancedVisible"
            @clear-filters="stepsTable.clearFilters" @clear-sort="stepsTable.clearSort" @clear-selection="stepsTable.clearSelection" @export-current="stepsTable.exportCurrent"
            @selection-change="stepsTable.selectedRows = $event" @sort-change="stepsTable.handleSort">
            <template #columns>
              <el-table-column label="正式状态" min-width="155"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" /></template></el-table-column>
              <el-table-column v-for="field in stepDetailFields" :key="field.key" :prop="field.key" :label="field.label" min-width="180" />
            </template>
          </PceEnterpriseListTable>
          <h3>该版本资源占用</h3>
          <PceEnterpriseListTable :ref="element => reservationsTable.tableRef = element" :contract="reservationsContract" page-id="formal-scheduling-reservations" table-id="formal-scheduling-reservations-table"
            :rows="reservationRows" :table-rows="reservationsTable.filteredRows" :filter-schema="reservationFilters" :filters="reservationsTable.filters"
            v-model:quick-search="reservationsTable.quickSearch" :advanced-visible="reservationsTable.advancedVisible" :selected-count="reservationsTable.selectedRows.length"
            :active-filter-count="reservationsTable.activeFilterCount" :sort-text="reservationsTable.sortText" row-key="id" primary-field="primaryLabel" primary-label="正式占用记录"
            :primary-width="190" :show-action-column="false" :default-page-size="20"
            @search="reservationsTable.appliedSearch = reservationsTable.quickSearch" @toggle-advanced="reservationsTable.advancedVisible = !reservationsTable.advancedVisible"
            @clear-filters="reservationsTable.clearFilters" @clear-sort="reservationsTable.clearSort" @clear-selection="reservationsTable.clearSelection" @export-current="reservationsTable.exportCurrent"
            @selection-change="reservationsTable.selectedRows = $event" @sort-change="reservationsTable.handleSort">
            <template #columns>
              <el-table-column prop="workCenterLabel" label="工作中心" min-width="150" /><el-table-column prop="stepLabel" label="所属工序" min-width="170" />
              <el-table-column label="占用状态" min-width="130"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" /></template></el-table-column>
              <el-table-column prop="startLabel" label="占用开始时间" min-width="195" /><el-table-column prop="endLabel" label="占用结束时间" min-width="195" />
              <el-table-column prop="minutesLabel" label="加工占用分钟" min-width="145" />
            </template>
          </PceEnterpriseListTable>
        </template>
      </section>
    </template>
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
import { createFormalSchedulingController, createFormalSchedulingState } from '@/meta/runtime/formalProductionScheduling.js'

const props = defineProps({ plans: { type: Array, default: () => [] }, parentLoading: { type: Boolean, default: false } })
const route = useRoute(), router = useRouter(), panelElement = ref(null), selectedStepId = ref('')
const state = reactive(createFormalSchedulingState())
const owner = () => JSON.stringify([getTabAuthEpoch(), readTabIdentity()?.userId, readTabIdentity()?.companyId])
const controller = createFormalSchedulingController({ state, api: planningApi, companyId: () => readTabIdentity()?.companyId, owner })
const busy = computed(() => props.parentLoading || state.writing || state.readState === 'loading')
const selectedScopeRequest = computed(() => state.selectedScopeIndex === '' ? null : state.facts?.scopeGrantRequests[Number(state.selectedScopeIndex)] || null)
const selectedSchedule = computed(() => state.facts?.history.find(row => String(row.id) === state.selectedScheduleId)
  || (String(state.facts?.activeSchedule?.id) === state.selectedScheduleId ? state.facts.activeSchedule : null))
const stepRows = computed(() => selectedSchedule.value?.steps || [])
const reservationRows = computed(() => selectedSchedule.value?.reservations || [])
const selectedStep = computed(() => stepRows.value.find(row => String(row.stepId) === selectedStepId.value) || null)
const stepDetailFields = Object.freeze([{ key: 'processingTimeLabel', label: '加工时间' }, { key: 'preparationTimeLabel', label: '准备时间' },
  { key: 'transferTimeLabel', label: '转运时间' }, { key: 'totalWorkTimeLabel', label: '合计工作分钟' },
  { key: 'startLabel', label: '步骤开始时间' }, { key: 'endLabel', label: '步骤结束时间' }])
const stepsContract = createPceEnterpriseListContract({ pageCode: 'formal-scheduling-steps', pageType: 'list', title: '正式排程步骤', moduleCode: 'APS' })
const reservationsContract = createPceEnterpriseListContract({ pageCode: 'formal-scheduling-reservations', pageType: 'list', title: '正式资源占用', moduleCode: 'APS' })
const stepFilters = Object.freeze([{ field: 'stepLabel', label: '工序', filterType: 'text' }, { field: 'statusLabel', label: '正式状态', filterType: 'select', optionsProvider: 'current_result' }])
const reservationFilters = Object.freeze([{ field: 'workCenterLabel', label: '工作中心', filterType: 'text' }, { field: 'stepLabel', label: '所属工序', filterType: 'text' },
  { field: 'statusLabel', label: '占用状态', filterType: 'select', optionsProvider: 'current_result' }])
const stepsTable = reactive(usePceEnterpriseListRuntime({ rows: stepRows, filterSchema: stepFilters, pageCode: 'formal-scheduling-steps',
  searchFields: ['stepLabel', 'statusLabel'], exportFileName: () => '正式排程步骤.csv',
  exportColumns: [{ field: 'stepLabel', label: '工序' }, { field: 'statusLabel', label: '正式状态' }, ...stepDetailFields.map(field => ({ field: field.key, label: field.label }))] }))
const reservationsTable = reactive(usePceEnterpriseListRuntime({ rows: reservationRows, filterSchema: reservationFilters, pageCode: 'formal-scheduling-reservations',
  searchFields: ['primaryLabel', 'workCenterLabel', 'stepLabel', 'statusLabel'], exportFileName: () => '正式资源占用.csv',
  exportColumns: [{ field: 'primaryLabel', label: '占用记录' }, { field: 'workCenterLabel', label: '工作中心' }, { field: 'stepLabel', label: '所属工序' },
    { field: 'statusLabel', label: '占用状态' }, { field: 'startLabel', label: '开始时间' }, { field: 'endLabel', label: '结束时间' }, { field: 'minutesLabel', label: '加工占用分钟' }] }))

async function selectPlan(planId) {
  await router.replace({ query: { ...route.query, section: 'formal-scheduling', productionPlanId: planId || undefined } })
  if (String(planId || '') !== state.selectedPlanId) await controller.select(planId)
}
async function syncPlan({ force = false } = {}) {
  if (props.parentLoading) return
  const planId = String(route.query.productionPlanId || state.selectedPlanId || '')
  if (!planId) return
  if (!props.plans.some(plan => String(plan.id) === planId)) { controller.invalidate(); return }
  if (planId !== state.selectedPlanId) await controller.select(planId)
  else if (force) await controller.load()
}
async function focusPanel() {
  if (route.query.section !== 'formal-scheduling') return
  await nextTick(); panelElement.value?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
}
function authenticationChanged() { controller.invalidate() }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const provider = { factOwner: 'planning-formal-scheduling', refresh: () => controller.load(),
  buildDiagnostics: () => ({ factSource: 'server', pageFactOwner: 'planning-formal-scheduling',
    strictFacts: state.facts, strictServerFacts: state.facts, lastExplicitActionReceipt: state.writeReceipt,
    readState: state.readState, errorMessage: state.error || null }) }
observability?.register?.(provider)
watch([() => route.query.productionPlanId, () => props.parentLoading, () => props.plans], (_, previous) => {
  syncPlan({ force: Boolean(previous?.[1] && !props.parentLoading) })
}, { immediate: true })
watch(() => route.query.section, focusPanel)
watch(() => state.selectedScheduleId, () => { selectedStepId.value = ''; stepsTable.clearSelection(); reservationsTable.clearSelection() })
onMounted(() => { globalThis.window?.addEventListener?.('pce:authentication-changed', authenticationChanged); focusPanel() })
onBeforeUnmount(() => { controller.invalidate(); globalThis.window?.removeEventListener?.('pce:authentication-changed', authenticationChanged); observability?.unregister?.(provider) })
</script>

<style scoped>
.formal-scheduling-panel{min-width:0;scroll-margin-top:12px}.formal-scheduling-panel p{line-height:1.6}.scheduling-controls,.scheduling-actions{display:flex;flex-wrap:wrap;gap:10px;align-items:end;margin:12px 0}.formal-scheduling-panel label{display:block;max-width:540px;margin:12px 0;font-weight:600}.formal-scheduling-panel select,.formal-scheduling-panel textarea{display:block;box-sizing:border-box;width:100%;margin-top:6px;padding:9px;border:1px solid #cbd5e1;border-radius:7px;font:inherit}.formal-scheduling-panel textarea{min-height:65px}.formal-scheduling-panel button{padding:9px 12px;border:1px solid #3568dc;border-radius:7px;background:#3568dc;color:#fff;cursor:pointer}.formal-scheduling-panel button:disabled{opacity:.55;cursor:not-allowed}.scheduling-readback{margin-top:16px;padding-top:12px;border-top:1px solid #dce4ef;min-width:0}.scheduling-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px 20px;margin:12px 0}.scheduling-facts dt{font-size:12px;color:#64748b}.scheduling-facts dd{margin:4px 0 0;font-weight:600;overflow-wrap:anywhere}.scheduling-error{padding:9px;background:#fff2f0;color:#9f241d;border-radius:7px}.scheduling-message{padding:9px;background:#eef9f3;color:#146141;border-radius:7px}@media(max-width:540px){.scheduling-facts{grid-template-columns:1fr}.scheduling-controls{display:block}}
.scheduling-actions{align-items:start}.scheduling-action{flex:1 1 250px;min-width:0}.scheduling-action-explanation{margin:6px 0 0;font-size:13px;color:#475569;overflow-wrap:anywhere}
</style>
