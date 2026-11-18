<template>
  <div class="operation-start-content" data-page="production-operation-start" data-fact-source="server" :data-load-status="state.readState">
    <section class="card" aria-label="工序开工操作说明">
      <h2>操作说明</h2>
      <ol>
        <li>由已派工任务指定的执行人本人登录，选择“本人获派任务”。主任派工与本人开工分别管理。</li>
        <li>点击“重新读取开工事实”，核对本人、执行岗位、车间接收、正式工单工序、工作中心、作业量及前序条件和准入结果。</li>
        <li>前序条件承接同公司、同工单、来源一致且经生产跟单员审核生效的正式完工证明；全部必需前序均满足后，仍须核对本人获派任务及执行资格。前序已完工不代表本任务已开工。</li>
        <li>经过但不统计数量、适用性待定及依赖节点，按正式工艺规则显示具体缺项；不得填写虚构数量或因无数量而跳过。组长执行与生产跟单审核分别管理，组长不能审核本人申请。</li>
        <li>必经无统计量任务开工后沿原“工序报工”入口登记实际经过，再申请完工及独立审核；正量任务继续分次报工。正式免执行只满足对应前置义务，不显示成已实际完工，且不省略其必需上游。</li>
        <li>实际开始作业时填写本次原因，再由本人明确点击“开工”。系统记录服务端实际时间；计划开始日期不代表实际开工时间。</li>
        <li>提交后只读回查开工人、实际时间与审计。若网络结果不明，只重新读取，不重复提交。</li>
      </ol>
      <p><strong>本轮交付核对停在点击“开工”之前。</strong>读取不代表开工；开工、报工、完工和转移是不同动作。本页不填写完成数量、不扣库存、不释放占用、不改变排程。</p>
    </section>
    <section class="card" aria-label="本人任务及开工资格">
      <h2>本人获派任务与开工准入</h2>
      <div class="controls">
        <label>本人获派任务<select aria-label="本人获派任务" :value="state.taskId" :disabled="busy || pending" @change="selectTask($event.target.value)">
          <option value="">请选择本人获派任务</option>
          <option v-for="row in displayFacts?.tasks || []" :key="row.taskId" :value="String(row.taskId)">{{ row.no }} · {{ row.operationName }} · {{ row.executionStatusLabel }}</option>
        </select></label>
        <button type="button" :disabled="busy" @click="controller.load()">重新读取开工事实</button>
      </div>
      <p v-if="state.readState === 'loading'" role="status">正在读取当前后台身份、本人任务及开工资格，当前结果尚未核实。</p>
      <p v-if="state.error" role="alert" class="warning">{{ state.error }}</p>
      <p v-if="!state.facts && state.lastDisplayFacts" class="warning">以下仅为同一账号、同一任务的上次只读展示，当前资格及提交结果未核实，不能据此开工。</p>
      <p v-if="state.message" role="status" class="warning">{{ state.message }}</p>
      <template v-if="displayFacts">
        <dl class="facts">
          <div><dt>本次后台账号</dt><dd>{{ displayFacts.currentActorEvidence.username }}</dd></div>
          <div><dt>正式员工</dt><dd>{{ displayFacts.currentActorEvidence.employeeName || '当前员工关联未核实' }}</dd></div>
          <div><dt>公司</dt><dd>{{ displayFacts.currentActorEvidence.companyName }}（{{ displayFacts.currentActorEvidence.companyCode }}）</dd></div>
          <div><dt>本次读取范围</dt><dd>本人合法获派任务；查看不创建开工记录</dd></div>
        </dl>
        <template v-if="selected">
          <dl class="facts source-facts">
            <div><dt>任务编号／派工状态</dt><dd>{{ selected.no }}／{{ selected.dispatchStatusLabel }}</dd></div>
            <div><dt>执行状态</dt><dd><PceBusinessStatus :status-label="selected.executionStatusLabel" /></dd></div>
            <div><dt>正式工单／工序</dt><dd>{{ selected.workOrderNo }}／{{ selected.sequence }} · {{ selected.operationName }}</dd></div>
            <div><dt>来源工单版本／路线版本／步骤</dt><dd>{{ selected.workOrderVersion ?? '未核实' }}／{{ selected.routeVersionId ?? '未核实' }}／{{ selected.stepId ?? '未核实' }}</dd></div>
            <div><dt>车间接收记录</dt><dd>{{ selected.receiptId ?? '未核实' }}／{{ selected.receiptStatusLabel || '接收事实尚未核实' }}</dd></div>
            <div v-if="selected.resourceSource?.effectiveReceptionAuthority"><dt>本工序有效接收依据</dt><dd data-effective-reception>{{ selected.resourceSource.effectiveReceptionAuthority }}；{{ selected.resourceSource.effectiveWorkshop?.name }}</dd></div>
            <div v-if="selected.resourceSource?.selectionFact"><dt>正式资源选择依据</dt><dd>{{ selected.resourceSource.selectionFact.statusLabel }}；{{ selected.resourceSource.selectionFact.ref }}</dd></div>
            <div v-if="selected.resourceSource?.preciseReceipt"><dt>逐工序精确接收证明</dt><dd data-precise-receipt>{{ selected.resourceSource.preciseReceipt.statusLabel }}；{{ selected.resourceSource.preciseReceipt.actorLabel }}；{{ selected.resourceSource.preciseReceipt.timeLabel }}；{{ selected.resourceSource.preciseReceipt.auditReference }}</dd></div>
            <div><dt>岗位／指定执行人</dt><dd>{{ selected.positionName }}／{{ selected.employeeName }}</dd></div>
            <div><dt>车间／工作中心</dt><dd>{{ selected.workshopName }}／{{ selected.workCenterName }}<span v-if="selected.workCenterCode">（{{ selected.workCenterCode }}）</span></dd></div>
            <div><dt>正式作业量／单位</dt><dd>{{ selected.workloadLabel }}</dd></div>
            <div><dt>正式执行模式</dt><dd data-execution-mode>{{ selected.executionModeLabel }}</dd></div>
            <div v-if="selected.quantityApplicable === false"><dt>工程参考（不是实际产量）</dt><dd data-reference-workload>{{ selected.referenceWorkload.quantity ?? '无工程参考量' }} {{ selected.referenceWorkload.uomLabel || '' }}；{{ selected.referenceWorkload.statusLabel || '仅供来源追溯' }}</dd></div>
          </dl>
          <p>{{ selected.predecessorFacts?.statusLabel }}</p>
          <ul v-if="selected.predecessorFacts?.items?.length"><li v-for="row in selected.predecessorFacts.items" :key="row.operationId">{{ row.sequence }} · {{ row.operationName }}：{{ row.statusLabel }}</li></ul>
          <p v-if="selected.quantityApplicable !== null" data-mode-next-step>本人实际开工后的下一正式动作：<router-link :to="{path:'/planning/operation-reports',query:{taskId:String(selected.taskId)}}">{{ selected.quantityApplicable === false ? '登记实际经过' : '工序分次报工' }}</router-link>；此说明不代表已经执行下一动作。</p>
          <p v-if="state.facts?.qualification" data-start-qualification>{{ state.facts.qualification.statusLabel }}</p>
          <ul v-if="state.facts?.qualification?.missingItems?.length"><li v-for="(item,index) in state.facts.qualification.missingItems" :key="index">{{ item.statusLabel || item.message || item }}</li></ul>
          <label>本次开工原因<textarea v-model="state.reason" rows="2" :disabled="busy || pending || !state.facts || !startAction.enabled" placeholder="实际开始作业时，由本人说明本次开工原因" /></label>
          <div class="actions"><button type="button" :data-action-code="startAction.actionCode" :disabled="!canStart" @click="controller.execute()">{{ startAction.displayName }}</button></div>
          <p v-if="startAction.disabledReason">{{ startAction.disabledReason }}</p>
          <template v-if="selected.executionRecord">
            <dl class="facts source-facts">
              <div><dt>实际开工人</dt><dd>{{ selected.executionRecord.startedByLabel }}</dd></div>
              <div><dt>实际开工时间</dt><dd>{{ selected.executionRecord.startedAtLabel }}</dd></div>
              <div><dt>开工审计</dt><dd>{{ selected.executionRecord.auditReference }}</dd></div>
              <div><dt>开工原因</dt><dd>{{ selected.executionRecord.reason }}</dd></div>
            </dl>
            <details><summary>开工状态与审计历史（{{ selected.statusTransitionCount }}）</summary><p v-for="event in selected.statusTransitionHistory" :key="event.id">{{ event.actionLabel }}：{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；{{ event.timestampLabel }}；{{ event.auditReference }}</p></details>
          </template>
          <p v-else>本任务已派工且尚无开工记录，因此显示待开工；读取和核对不会创建开工记录。</p>
        </template>
        <p v-else-if="displayFacts.tasks.length">请明确选择本人获派任务，系统不会默认选择或自动开工。</p>
        <p v-else>本次正式范围内没有本人合法获派任务。请核对当前登录人；本页不会显示他人任务或代为更换执行人。</p>
      </template>
    </section>
    <section v-if="displayFacts" class="card" aria-label="本人获派任务列表">
      <h2>本人获派任务列表</h2>
      <p>{{ state.facts ? `任务记录：${state.serverSurface.resultCount}；实际开工记录：${state.facts.operationStartRecordCount}` : '当前数量未知，上次列表仅供回看。' }}</p>
      <PceEnterpriseListTable :ref="element => table.tableRef = element" :contract="listContract" :page-id="OPERATION_START_PAGE.pageCode"
        table-id="production-operation-start-main" :rows="rows" :table-rows="table.filteredRows" :filter-schema="OPERATION_START_FILTERS"
        :filters="table.filters" :quick-search="table.quickSearch" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length"
        :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="no" primary-label="工序任务编号"
        :primary-width="200" min-width="1850px" :action-width="130"
        @update:quick-search="table.quickSearch = $event" @search="table.appliedSearch = table.quickSearch" @toggle-advanced="table.advancedVisible = !table.advancedVisible"
        @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @export-current="table.exportCurrent"
        @clear-selection="table.selectedRows = []" @update-filter="table.updateFilter" @selection-change="table.selectedRows = $event" @sort-change="table.handleSort">
        <template #columns>
          <el-table-column prop="workOrderNo" label="生产工单编号" width="190" /><el-table-column prop="operationName" label="工序" width="130" />
          <el-table-column prop="workshopName" label="车间" width="110" /><el-table-column prop="workCenterName" label="工作中心" width="180" />
          <el-table-column prop="workloadLabel" label="正式作业量／单位" width="180" /><el-table-column prop="positionName" label="执行岗位" width="170" />
          <el-table-column prop="employeeName" label="指定执行人" width="130" /><el-table-column prop="executionStatusLabel" label="执行状态" width="120"><template #default="{ row }"><PceBusinessStatus :status-label="row.executionStatusLabel" /></template></el-table-column>
          <el-table-column prop="startedByLabel" label="实际开工人" width="130" /><el-table-column prop="startedAtLabel" label="实际开工时间" width="200" />
        </template>
        <template #actions="{ row }"><button type="button" :disabled="busy || pending" @click="selectTask(String(row.taskId))">查看任务</button></template>
      </PceEnterpriseListTable>
    </section>
  </div>
</template>
<script setup>
import { computed, inject, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { operationStartsApi } from '@/api/operationStarts.js'
import { createOperationStartState, createOperationStartController } from '@/meta/runtime/operationStart.js'
import { OPERATION_START_PAGE, OPERATION_START_FILTERS, OPERATION_START_SEARCH_FIELDS, OPERATION_START_EXPORT_COLUMNS } from '@/meta/runtime/operationStartContract.js'
import { OPERATION_START_ACTION_CONTRACT, resolvePceOperationStartAction } from '@/meta/runtime/pceBusinessActionRegistry.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
const emit = defineEmits(['refresh-status']), route = useRoute(), router = useRouter()
const state = reactive(createOperationStartState())
const owner = () => JSON.stringify([getTabAuthEpoch(), readTabIdentity()?.userId, readTabIdentity()?.companyId, readTabIdentity()?.username])
const controller = createOperationStartController({ state, api: operationStartsApi, owner,
  companyId: () => readTabIdentity()?.companyId, userId: () => readTabIdentity()?.userId })
const displayFacts = computed(() => state.facts || state.lastDisplayFacts), selected = computed(() => displayFacts.value?.selectedTask)
const busy = computed(() => state.readState === 'loading' || state.writeState === 'writing'), pending = computed(() => state.writeState === 'readback_pending')
const startAction = computed(() => state.facts ? resolvePceOperationStartAction(state.facts)
  : { ...OPERATION_START_ACTION_CONTRACT, enabled: false, disabledReason: '' })
const canStart = computed(() => !busy.value && !pending.value && !!state.facts && startAction.value.enabled && !!state.reason.trim())
const rows = computed(() => displayFacts.value?.tasks || [])
const listContract = createPceEnterpriseListContract({ pageCode: OPERATION_START_PAGE.pageCode, pageType: 'list', title: OPERATION_START_PAGE.title, moduleCode: 'MES' })
const table = reactive(usePceEnterpriseListRuntime({ rows, filterSchema: OPERATION_START_FILTERS, pageCode: OPERATION_START_PAGE.pageCode,
  searchFields: OPERATION_START_SEARCH_FIELDS, exportFileName: '本人工序开工.csv', exportColumns: OPERATION_START_EXPORT_COLUMNS }))
async function selectTask(value) { if (busy.value || pending.value) return; await router.replace({ query: { ...route.query, taskId: value || undefined } }) }
function safeDiagnostics(value) {
  if (Array.isArray(value)) return value.map(safeDiagnostics)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).filter(([key]) => !/executionToken|idempotency|password|authorization|cookie|jwt|secret/i.test(key))
    .map(([key, item]) => [key, safeDiagnostics(item)]))
}
function buildDiagnostics() {
  const factLoadFacts = state.factLoadFacts || createReadFailedFactLoad({ apiUrl: OPERATION_START_PAGE.apiUrl,
    errorCode: 'FACTS_NOT_LOADED', errorMessage: '开工事实尚未读取，任务数量及资格未知。' })
  const server = state.serverSurface || { ...factLoadFacts, factLoadFacts, operationStartFacts: null, resultCount: null, passed: false }
  return safeDiagnostics({ ...factLoadFacts, factOwner: OPERATION_START_PAGE.moduleId, pageFactOwner: OPERATION_START_PAGE.moduleId,
    moduleCode: OPERATION_START_PAGE.moduleId, factSource: 'server', operationStartFacts: state.facts,
    strictFacts: server, strictServerFacts: server, factLoadFacts, resultCount: server.resultCount,
    readState: state.readState, writeState: state.writeState, errorMessage: state.error || null })
}
const provider = { factOwner: OPERATION_START_PAGE.moduleId, refresh: () => controller.load(), buildDiagnostics }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
function authenticationChanged() { controller.invalidate(); controller.select(String(route.query.taskId || '')) }
watch(() => route.query.taskId, value => controller.select(String(value || '')), { immediate: true })
watch(() => state.readState, value => emit('refresh-status', ({ loading: 'refreshing', loaded: 'success', read_failed: 'error' })[value] || 'idle'))
onMounted(() => { observability?.register?.(provider); globalThis.window?.addEventListener?.('pce:authentication-changed', authenticationChanged) })
onBeforeUnmount(() => { controller.invalidate(); observability?.unregister?.(provider); globalThis.window?.removeEventListener?.('pce:authentication-changed', authenticationChanged) })
defineExpose({ refresh: () => controller.load(), buildDiagnostics })
</script>
<style scoped>
.operation-start-content{display:grid;gap:16px;min-width:0;padding:18px}.card{min-width:0;border:1px solid #dbe3ef;border-radius:12px;background:white;padding:20px}.card h2{margin:0 0 14px}.card p,.card li{line-height:1.7;overflow-wrap:anywhere}.controls,.actions{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.operation-start-content label{display:block;max-width:700px;margin:12px 0;min-width:220px}.controls label{flex:1}.operation-start-content select,.operation-start-content textarea{display:block;box-sizing:border-box;width:100%;margin-top:7px;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font:inherit}.operation-start-content button{padding:9px 12px;border:1px solid #3568dc;border-radius:6px;background:#3568dc;color:white;cursor:pointer}.operation-start-content button:disabled{opacity:.5;cursor:not-allowed}.warning{padding:10px;background:#fff7e6;color:#744b0a;border-radius:6px}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px}.facts dt{font-size:12px;color:#64748b}.facts dd{margin:4px 0;font-weight:600;overflow-wrap:anywhere}.source-facts{border-top:1px solid #e2e8f0;padding-top:14px}details{margin:12px 0}@media(max-width:650px){.operation-start-content{padding:8px}.card{padding:14px}.facts{grid-template-columns:1fr}.controls{display:block}}
</style>
