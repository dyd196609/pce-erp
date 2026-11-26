<template>
  <div class="workshop-task-content" data-page="production-workshop-task" data-fact-source="server" :data-load-status="state.readState">
    <section class="card" aria-label="车间任务派工操作说明">
      <h2>操作说明</h2>
      <ol>
        <li>选择已下达工单，再选择本车间已经接收的工序，核对来源、工作中心及正式作业量和单位。</li>
        <li>由主任明确选择实际执行岗位及人员。候选仅表示当前任职关系符合任务分派条件，不代表已经获得后续开工权限；系统不默认选择人员。</li>
        <li>填写原因并保存任务草稿；尚未确定人员时可以保留草稿，缺项须在正式派工前补齐。</li>
        <li>重新读取任务事实，核对执行人、版本及准入结果。后续由主任人工点击“正式派工”，再核对派工人、时间与审计。</li>
        <li>正式无统计量模式仍须真实资源、接收、派工和本人开工。模式、工程参考及具体缺项由后台给出；目录默认工作中心不是本工单已选资源，系统不补选或生成接收。</li>
      </ol>
      <p><strong>保存任务草稿与正式派工须由有职责的责任人分别明确确认。</strong>已派工任务只核对正式保存的冻结岗位、人员和审计，不重复派工。本页不执行开工或报工，也不修改排程及占用。</p>
    </section>
    <section class="card" aria-label="已接收工序及任务维护">
      <h2>已接收工序与任务草稿</h2>
      <div class="controls">
        <label>已下达工单<select aria-label="已下达工单" :value="state.workOrderId" :disabled="busy || pending" @change="selectOrder($event.target.value)">
          <option value="">请选择工单</option><option v-for="row in workOrders" :key="row.workOrderId" :value="String(row.workOrderId)">{{ row.workOrderNo }}</option>
        </select></label>
        <label>已接收工序（按权限可见）<select aria-label="已接收工序" :value="state.operationId" :disabled="busy || pending || !state.workOrderId" @change="selectOperation($event.target.value)">
          <option value="">请选择工序</option><option v-for="row in displayFacts?.operationOptions || []" :key="row.id" :value="String(row.id)">{{ row.sequence }} · {{ row.operationName }} · {{ row.workshopName }} · {{ row.workloadLabel }}</option>
        </select></label>
        <button type="button" :disabled="busy" @click="controller.load()">重新读取任务事实</button>
      </div>
      <p v-if="state.readState === 'loading'" role="status">正在读取本次后台身份、已接收工序及任务事实，资格尚未核实。</p>
      <p v-if="state.error" role="alert" class="warning">{{ state.error }}</p>
      <p v-if="!state.facts && state.lastDisplayFacts" class="warning">以下为同一身份、工单及工序的上次只读展示；{{ state.writeState === 'rejected' ? '本次提交已被服务端拒绝，当前资格待重新读取' : pending || state.writeState === 'writing' ? '当前资格和本次提交结果未核实' : '当前资格尚未核实' }}，不能据此提交。</p>
      <p v-if="state.message" role="status" class="warning">{{ state.message }}</p>
      <template v-if="displayFacts">
        <dl class="facts">
          <div><dt>本次后台账号</dt><dd>{{ displayFacts.currentActorEvidence.username }}</dd></div>
          <div><dt>正式员工／岗位</dt><dd>{{ displayFacts.currentActorEvidence.employeeName || '未建立有效任职' }}／{{ displayFacts.currentActorEvidence.positionName || '岗位未核实' }}</dd></div>
          <div><dt>公司</dt><dd>{{ displayFacts.currentActorEvidence.companyName }}（{{ displayFacts.currentActorEvidence.companyCode }}）</dd></div>
          <div><dt>岗位车间</dt><dd>{{ displayFacts.currentActorEvidence.workshopName || '岗位未关联车间' }}</dd></div>
        </dl>
        <template v-if="displayFacts.selectedOperation">
          <dl class="facts source-facts">
            <div><dt>正式工单／工序</dt><dd>{{ source.workOrderNo }}／{{ source.sequence }} · {{ source.operationName }}</dd></div>
            <div><dt>车间接收记录</dt><dd>{{ source.workshopName || '尚未正式归属车间' }}／{{ source.receiptId ? `接收记录${source.receiptId}` : '尚无本工序正式接收证明' }}</dd></div>
            <div v-if="source.resourceSource?.effectiveReceptionAuthority"><dt>本工序有效接收依据</dt><dd data-effective-reception>{{ source.resourceSource.effectiveReceptionAuthority }}；{{ source.resourceSource.effectiveWorkshop?.name }}</dd></div>
            <div v-if="source.resourceSource?.selectionFact"><dt>正式资源选择依据</dt><dd>{{ source.resourceSource.selectionFact.statusLabel }}；{{ source.resourceSource.selectionFact.ref }}</dd></div>
            <div v-if="source.resourceSource?.preciseReceipt"><dt>逐工序精确接收证明</dt><dd data-precise-receipt>{{ source.resourceSource.preciseReceipt.statusLabel }}；{{ source.resourceSource.preciseReceipt.actorLabel }}；{{ source.resourceSource.preciseReceipt.timeLabel }}；{{ source.resourceSource.preciseReceipt.auditReference }}</dd></div>
            <div><dt>工作中心</dt><dd>{{ source.workCenterId ? source.workCenterName : '尚未正式选定工作中心' }}<span v-if="source.workCenterId && source.workCenterCode">（{{ source.workCenterCode }}）</span></dd></div>
            <div><dt>正式执行模式</dt><dd data-execution-mode>{{ source.executionModeLabel }}</dd></div>
            <div><dt>正式作业量／单位</dt><dd>{{ source.workloadLabel }}</dd></div>
            <div v-if="source.quantityApplicable === false"><dt>工程参考（不是实际产量）</dt><dd data-reference-workload>{{ source.referenceWorkload.quantity ?? '无工程参考量' }} {{ source.referenceWorkload.uomLabel || '' }}；{{ source.referenceWorkload.statusLabel || '仅供来源追溯' }}</dd></div>
            <div v-if="source.referenceWorkshop"><dt>工艺目录参考（不是本单有效归属）</dt><dd>{{ source.referenceWorkshop.name || source.referenceWorkshop.workshopName || '正式目录参考' }}</dd></div>
            <div><dt>来源路线／步骤</dt><dd>{{ source.effectiveRoutingVersionId || source.routingVersionId }}／{{ source.effectiveStepId || source.routingStepId }}</dd></div>
            <div><dt>{{ !state.facts ? '上次读取任务（当前待核实）' : pending ? '当前只读任务（尚不能核实本次提交）' : '当前任务' }}</dt><dd>{{ displayFacts.selectedTask?.no || (!state.facts ? '上次读取未查到任务；当前待核实' : pending ? '本次读取尚未查到任务；原提交结果待核实' : '尚未保存草稿') }} <PceBusinessStatus v-if="displayFacts.selectedTask" :status-label="displayFacts.selectedTask.statusLabel" /></dd></div>
          </dl>
          <ul v-if="source.resourceSource?.blockingReasons?.length" class="warning" data-resource-blockers><li v-for="(item,index) in source.resourceSource.blockingReasons" :key="index">{{ item }}</li></ul>
          <p v-if="state.facts?.qualification">{{ state.facts.qualification.statusLabel }}</p>
          <ul v-if="state.facts?.qualification?.issues?.length"><li v-for="(issue,index) in state.facts.qualification.issues" :key="index">{{ issue.statusLabel || issue.message || issue }}</li></ul>
          <section v-if="assignmentReadOnly" class="assignment-readback" data-assignment-readback>
            <p v-if="dispatchedTask">{{ currentCandidatesReady ? '本任务已正式派工。以下为正式任务保存的冻结岗位及人员，不从当前候选重新选择或重复派工。' : '以下为上次正式派工任务的冻结岗位及人员；当前读取结果待核实，仅供只读核对。' }}</p>
            <p v-else>{{ assignmentReadbackMessage }}</p>
            <dl class="facts"><div><dt>{{ dispatchedTask ? '正式任务冻结岗位' : '本次已选岗位（待核实）' }}</dt><dd data-assignment-position>{{ assignmentDisplay.positionName }}</dd></div>
              <div><dt>{{ dispatchedTask ? '正式任务冻结人员' : '本次已选人员（待核实）' }}</dt><dd data-assignment-employee>{{ assignmentDisplay.employeeName }}</dd></div></dl>
          </section>
          <div v-else class="controls">
            <label>实际执行岗位<select aria-label="实际执行岗位" :value="state.positionId" :disabled="formDisabled" @change="controller.choosePosition($event.target.value)">
              <option value="">请选择执行岗位（可留空保存草稿）</option><option v-for="row in state.facts?.candidatePositions || []" :key="row.id" :value="String(row.id)">{{ row.name }}</option>
            </select></label>
            <label>实际执行人员<select aria-label="实际执行人员" :value="state.employeeId" :disabled="formDisabled || !state.positionId" @change="controller.chooseEmployee($event.target.value)">
              <option value="">请选择执行人员（可留空保存草稿）</option><option v-for="row in employees" :key="row.employeeId || row.id" :value="String(row.employeeId || row.id)">{{ row.employeeName }} · {{ row.employeeNo }} · {{ row.username }}</option>
            </select></label>
          </div>
          <p v-if="currentCandidatesReady && (!source.workCenterId || !source.workshopId || !source.receiptId)" class="warning">本工序尚缺正式执行资源或逐工序接收证明，当前不能保存任务或派工；目录资源仅供参考，不默认选择人员，也不以修改员工替代资源和接收事实。</p>
          <p v-else-if="currentCandidatesReady && !dispatchedTask && !state.facts.candidatePositions.length" class="warning">当前没有合法执行岗位候选。可先保存缺项草稿；由用户通过“组织结构→岗位管理／员工档案”维护同公司、同车间的有效岗位和任职关系，再重新读取。系统不会创建员工或账号。</p>
          <p v-else-if="currentCandidatesReady && !dispatchedTask && state.positionId && !selectedPositionResolved" class="warning">原选择岗位尚未在本次正式候选中核实，请重新读取并核对当前岗位；尚不能判断该岗位的人员候选，不据此维护员工档案。</p>
          <p v-else-if="currentCandidatesReady && !dispatchedTask && selectedPositionResolved && !employees.length" class="warning">所选岗位没有合法执行人员候选。请在“组织结构→员工档案”核对正式部门、岗位、有效任职及登录账号，再重新读取；不替用户指定人员。</p>
          <label>本次操作原因<textarea v-model="state.reason" rows="2" :disabled="formDisabled" placeholder="说明本次保存草稿或正式派工的原因" /></label>
          <div class="actions">
            <button type="button" :data-action-code="saveAction.actionCode" :disabled="!canSave" @click="controller.execute('saveDraft')">{{ saveAction.displayName }}</button>
            <button type="button" :data-action-code="dispatchAction.actionCode" :disabled="!canDispatch" @click="controller.execute('dispatch')">{{ dispatchAction.displayName }}</button>
          </div>
          <p v-if="currentCandidatesReady && saveAction.disabledReason">{{ saveAction.disabledReason }}</p>
          <p v-if="currentCandidatesReady && state.formDirty">执行岗位或人员选择尚未保存，请先保存草稿并回读，再进行人工正式派工。</p>
          <p v-else-if="currentCandidatesReady && dispatchAction.disabledReason">{{ dispatchAction.disabledReason }}</p>
          <template v-if="displayFacts.selectedTask">
            <p v-if="pending" class="warning">{{ state.facts ? '以下为本次读取的当前只读事实，尚不能核实本次提交。' : '以下为上次读取的只读事实，本次提交结果待核实。' }}原已选岗位及人员仍按上方待核实摘要保留；请仅重新读取，不重复提交。</p>
            <p>{{ displayFacts.selectedTask.dispatchQualification?.statusLabel }}</p>
            <ul v-if="displayFacts.selectedTask.missingItems?.length"><li v-for="(item,index) in displayFacts.selectedTask.missingItems" :key="index">{{ item.statusLabel || item.label || item }}</li></ul>
            <dl class="facts"><div><dt>已保存执行岗位／人员</dt><dd>{{ displayFacts.selectedTask.positionName || '未指定' }}／{{ displayFacts.selectedTask.employeeName || '未指定' }}</dd></div><div><dt>派工人／派工时间</dt><dd>{{ displayFacts.selectedTask.dispatchedByLabel || '尚未派工' }}／{{ displayFacts.selectedTask.dispatchedAtLabel || '尚未派工' }}</dd></div></dl>
            <details><summary>任务状态与审计历史（{{ displayFacts.selectedTask.statusTransitionCount }}）</summary><p v-for="event in displayFacts.selectedTask.statusTransitionHistory" :key="event.id">{{ event.actionLabel }}：{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；{{ event.timestampLabel }}；{{ event.auditReference }}</p></details>
          </template>
        </template>
        <p v-else>请明确选择已接收工序；不会默认选择工序、岗位或人员。</p>
      </template>
    </section>
    <section v-if="displayFacts" class="card" aria-label="车间任务列表">
      <h2>车间任务列表</h2>
      <p>{{ state.facts ? `列表来自本次正式服务。任务记录：${state.serverSurface.resultCount}` : '当前任务数量未知；以下为上次只读列表，不能作为本次资格或操作结果的依据。' }}</p>
      <PceEnterpriseListTable :ref="element => table.tableRef = element" :contract="listContract" :page-id="WORKSHOP_TASK_PAGE.pageCode"
        table-id="production-workshop-task-main" :rows="rows" :table-rows="table.filteredRows" :filter-schema="WORKSHOP_TASK_FILTERS"
        :filters="table.filters" :quick-search="table.quickSearch" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length"
        :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="no" primary-label="工序任务编号"
        :primary-width="200" min-width="1900px" :action-width="120"
        @update:quick-search="table.quickSearch = $event" @search="table.appliedSearch = table.quickSearch" @toggle-advanced="table.advancedVisible = !table.advancedVisible"
        @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @export-current="table.exportCurrent"
        @clear-selection="table.selectedRows = []" @update-filter="table.updateFilter" @selection-change="table.selectedRows = $event" @sort-change="table.handleSort">
        <template #columns>
          <el-table-column prop="workOrderNo" label="生产工单编号" width="190" /><el-table-column prop="operationName" label="工序" width="130" />
          <el-table-column prop="workshopName" label="车间" width="110" /><el-table-column prop="workCenterName" label="工作中心" width="180" />
          <el-table-column prop="workloadLabel" label="正式作业量／单位" width="180" /><el-table-column prop="positionName" label="执行岗位" width="170" />
          <el-table-column prop="employeeName" label="执行人员" width="130" /><el-table-column prop="statusLabel" label="任务状态" width="120"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" /></template></el-table-column>
          <el-table-column prop="dispatchedByLabel" label="派工人" width="130" /><el-table-column prop="dispatchedAtLabel" label="派工时间" width="200" />
        </template>
        <template #actions="{ row }"><button type="button" :disabled="busy || pending" @click="openTask(row)">查看任务</button></template>
      </PceEnterpriseListTable>
    </section>
  </div>
</template>
<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { workshopTasksApi } from '@/api/workshopTasks.js'
import { createWorkshopTaskController, createWorkshopTaskState } from '@/meta/runtime/workshopTaskDispatch.js'
import { WORKSHOP_TASK_PAGE, WORKSHOP_TASK_FILTERS, WORKSHOP_TASK_SEARCH_FIELDS, WORKSHOP_TASK_EXPORT_COLUMNS } from '@/meta/runtime/workshopTaskDispatchContract.js'
import { WORKSHOP_TASK_ACTION_CONTRACTS, resolvePceWorkshopTaskActions } from '@/meta/runtime/pceBusinessActionRegistry.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
const emit = defineEmits(['refresh-status'])
const state = reactive(createWorkshopTaskState()), route = useRoute(), router = useRouter()
const owner = () => JSON.stringify([getTabAuthEpoch(), readTabIdentity()?.userId, readTabIdentity()?.companyId])
const controller = createWorkshopTaskController({ state, api: workshopTasksApi, owner, companyId: () => readTabIdentity()?.companyId })
const displayFacts = computed(() => state.facts || state.lastDisplayFacts), source = computed(() => displayFacts.value?.selectedOperation)
const busy = computed(() => state.readState === 'loading' || state.writeState === 'writing')
const pending = computed(() => state.writeState === 'readback_pending')
const currentCandidatesReady = computed(() => state.readState === 'loaded' && !!state.facts && !busy.value && !pending.value)
const dispatchedTask = computed(() => !pending.value && state.writeState !== 'writing'
  && displayFacts.value?.selectedTask?.statusCode === 'dispatched' ? displayFacts.value.selectedTask : null)
const assignmentReadOnly = computed(() => !currentCandidatesReady.value || !!dispatchedTask.value)
const assignmentReadbackMessage = computed(() => state.writeState === 'rejected'
  ? '本次提交已被服务端拒绝。原岗位及人员选择仅只读保留，当前资格待重新读取；不会自动重试。'
  : state.writeState === 'writing' ? '正在提交本次明确意图。已选岗位及人员仅作同一账号、工单和工序的只读展示，当前结果尚未核实，请勿再次提交。'
    : pending.value ? '本次提交结果待核实。原已选岗位及人员仅作同一账号、工单和工序的只读展示，请仅重新读取，不重复提交。'
      : '正在重新读取或本次读取尚未通过。原岗位及人员选择仅作同一账号、工单和工序的只读展示，当前资格待核实，不能据此提交。')
// Ephemeral display labels only, never candidates, eligibility or write intent.
// Current facts remain the sole authority for actions and editable selectors.
const selectionDisplay = ref(null)
const selectionContext = () => JSON.stringify([owner(), state.workOrderId, state.operationId])
watch([() => state.facts, () => state.positionId, () => state.employeeId, () => state.workOrderId, () => state.operationId,
  () => state.readState, () => state.writeState], () => {
  const context = selectionContext(), previous = selectionDisplay.value
  if (previous?.context !== context) selectionDisplay.value = null
  if ((state.writeState === 'writing' || pending.value) && previous?.context === context
    && previous.positionId === state.positionId && previous.employeeId === state.employeeId) return
  const facts = state.facts, actor = readTabIdentity(), operation = facts?.selectedOperation
  if (!facts) return
  if (facts.currentActorEvidence?.userId !== Number(actor?.userId) || facts.currentActorEvidence?.companyId !== Number(actor?.companyId)
    || operation?.id !== Number(state.operationId) || operation?.workOrderId !== Number(state.workOrderId)) {
    selectionDisplay.value = null; return
  }
  const task = facts.selectedTask, samePosition = previous?.context === context && previous.positionId === state.positionId
  const sameEmployee = samePosition && previous.employeeId === state.employeeId
  const position = facts.candidatePositions.find(row => String(row.id) === state.positionId)
  const employee = facts.candidateEmployees.find(row => String(row.positionId) === state.positionId && String(row.employeeId || row.id) === state.employeeId)
  selectionDisplay.value = { context, positionId: state.positionId, employeeId: state.employeeId,
    sourceSnapshotHash: operation.sourceSnapshotHash, taskId: task?.id ?? null, taskVersion: task?.version ?? null,
    positionName: !state.positionId ? '未选择' : position?.name || (String(task?.positionId) === state.positionId ? task.positionName : '')
      || (samePosition ? previous.positionName : '') || '所选岗位名称待核实',
    employeeName: !state.employeeId ? '未选择' : employee?.employeeName
      || (String(task?.positionId) === state.positionId && String(task?.employeeId) === state.employeeId ? task.employeeName : '')
      || (sameEmployee ? previous.employeeName : '') || '所选人员名称待核实' }
}, { flush: 'sync' })
const assignmentDisplay = computed(() => {
  if (dispatchedTask.value) return { positionName: dispatchedTask.value.positionName || '未指定', employeeName: dispatchedTask.value.employeeName || '未指定' }
  const value = selectionDisplay.value
  return value?.context === selectionContext() && value.positionId === state.positionId && value.employeeId === state.employeeId ? value
    : { positionName: state.positionId ? '所选岗位名称待核实' : '未选择', employeeName: state.employeeId ? '所选人员名称待核实' : '未选择' }
})
const formDisabled = computed(() => busy.value || pending.value || !state.facts || state.facts.selectedTask?.statusCode === 'dispatched')
const workOrders = computed(() => [...new Map((displayFacts.value?.operationOptions || []).map(row => [row.workOrderId, row])).values()])
const employees = computed(() => (state.facts?.candidateEmployees || []).filter(row => String(row.positionId) === state.positionId))
const selectedPositionResolved = computed(() => !!state.positionId && !!state.facts?.candidatePositions.some(row => String(row.id) === state.positionId))
const actions = computed(() => state.facts ? resolvePceWorkshopTaskActions(state.facts) : {})
const saveAction = computed(() => actions.value.saveDraft || { ...WORKSHOP_TASK_ACTION_CONTRACTS[0], enabled: false, disabledReason: '' })
const dispatchAction = computed(() => actions.value.dispatch || { ...WORKSHOP_TASK_ACTION_CONTRACTS[1], enabled: false, disabledReason: '' })
const canSave = computed(() => !formDisabled.value && saveAction.value.enabled && state.reason.trim())
const canDispatch = computed(() => !formDisabled.value && !state.formDirty && dispatchAction.value.enabled && state.reason.trim())
const rows = computed(() => displayFacts.value?.tasks || [])
const listContract = createPceEnterpriseListContract({ pageCode: WORKSHOP_TASK_PAGE.pageCode, pageType: 'list', title: WORKSHOP_TASK_PAGE.title, moduleCode: 'MES' })
const table = reactive(usePceEnterpriseListRuntime({ rows, filterSchema: WORKSHOP_TASK_FILTERS, pageCode: WORKSHOP_TASK_PAGE.pageCode,
  searchFields: WORKSHOP_TASK_SEARCH_FIELDS, exportFileName: '车间任务派工.csv', exportColumns: WORKSHOP_TASK_EXPORT_COLUMNS }))
async function selectOrder(value) { if (busy.value || pending.value) return; await router.replace({ query: { ...route.query, workOrderId: value || undefined, operationId: undefined } }) }
async function selectOperation(value) { if (busy.value || pending.value) return; await router.replace({ query: { ...route.query, operationId: value || undefined } }) }
async function openTask(row) { await router.replace({ query: { ...route.query, workOrderId: String(row.workOrderId), operationId: String(row.operationId) } }) }
function safeDiagnostics(value) {
  if (Array.isArray(value)) return value.map(safeDiagnostics)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).filter(([key]) => !/executionToken|idempotency|password|authorization|cookie|jwt|secret/i.test(key)).map(([key,item]) => [key, safeDiagnostics(item)]))
}
function buildDiagnostics() {
  const resultCount = state.serverSurface?.resultCount ?? null
  const factLoadFacts = state.factLoadFacts || createReadFailedFactLoad({ apiUrl: WORKSHOP_TASK_PAGE.apiUrl,
    errorCode: 'FACTS_NOT_LOADED', errorMessage: '任务事实尚未读取；当前数量及资格未知。' })
  const serverSurface = state.serverSurface || { ...factLoadFacts, factLoadFacts,
    workshopTaskFacts: null, resultCount: null, passed: false }
  return safeDiagnostics({ ...factLoadFacts, pageFactOwner: WORKSHOP_TASK_PAGE.moduleId,
    moduleCode: WORKSHOP_TASK_PAGE.moduleId, factSource: 'server', workshopTaskFacts: state.facts,
    strictFacts: serverSurface, strictServerFacts: serverSurface,
    factLoadFacts, resultCount,
    readState: state.readState, writeState: state.writeState, errorMessage: state.error || null })
}
const provider = { factOwner: WORKSHOP_TASK_PAGE.moduleId, refresh: () => controller.load(), buildDiagnostics }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
function authenticationChanged() { selectionDisplay.value = null; controller.invalidate(); controller.select(String(route.query.workOrderId || ''), String(route.query.operationId || '')) }
watch(() => [route.query.workOrderId, route.query.operationId], ([workOrderId,operationId]) => controller.select(String(workOrderId || ''), String(operationId || '')), { immediate: true })
watch(() => state.readState, value => emit('refresh-status', ({ loading: 'refreshing', loaded: 'success', read_failed: 'error' })[value] || 'idle'))
onMounted(() => { observability?.register?.(provider); globalThis.window?.addEventListener?.('pce:authentication-changed', authenticationChanged) })
onBeforeUnmount(() => { controller.invalidate(); observability?.unregister?.(provider); globalThis.window?.removeEventListener?.('pce:authentication-changed', authenticationChanged) })
defineExpose({ refresh: () => controller.load(), buildDiagnostics })
</script>
<style scoped>
.workshop-task-content{display:grid;gap:16px;min-width:0;padding:18px}.card{min-width:0;border:1px solid #dbe3ef;border-radius:12px;background:white;padding:20px}.card h2{margin:0 0 14px}.card p,.card li{line-height:1.7;overflow-wrap:anywhere}.controls,.actions{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.workshop-task-content label{display:block;max-width:700px;margin:12px 0;min-width:220px}.controls label{flex:1}.workshop-task-content select,.workshop-task-content textarea{display:block;box-sizing:border-box;width:100%;margin-top:7px;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font:inherit}.workshop-task-content button{padding:9px 12px;border:1px solid #3568dc;border-radius:6px;background:#3568dc;color:white;cursor:pointer}.workshop-task-content button:disabled{opacity:.5;cursor:not-allowed}.warning{padding:10px;background:#fff7e6;color:#744b0a;border-radius:6px}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px}.facts dt{font-size:12px;color:#64748b}.facts dd{margin:4px 0;font-weight:600;overflow-wrap:anywhere}.source-facts{border-top:1px solid #e2e8f0;padding-top:14px}details{margin:12px 0}@media(max-width:650px){.workshop-task-content{padding:8px}.card{padding:14px}.facts{grid-template-columns:1fr}.controls{display:block}}
</style>
