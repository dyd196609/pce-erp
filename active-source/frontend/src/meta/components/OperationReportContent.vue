<template>
  <div class="operation-report-content" data-page="production-operation-report" data-fact-source="server" :data-load-status="state.readState" :data-visible-read-ms="visibleReadMs" :data-read-cycle="readCycle">
    <MesUnifiedPageGuide title="工序报工" purpose="登记本人已开工任务的实际完成量或实际经过。" people="本人任务指定执行人" />
<nav class="report-navigation" aria-label="报工查看导航"><button v-if="selected" type="button" :disabled="busy || pending" @click="returnToTasks">返回本人任务</button><button type="button" :aria-expanded="learningOpen" aria-controls="report-learning" @click="learningOpen = !learningOpen; learning.write(learningOpen)">操作说明{{ learningOpen ? " · 关闭" : "" }}</button></nav>
    <section ref="taskArea" class="card task-action-card" tabindex="-1" aria-label="本人已开工任务及报工资格">
      <header class="employee-heading"><div><p class="eyebrow">{{ selected ? '本人任务 · 填写报工' : '本人任务' }}</p><h2>{{ selected?.operationName || '找到要办理的任务' }}</h2><p v-if="!selected">先按工序或任务编号查找，再点击任务行的“填写报工”或“查看报工记录”。</p></div></header>
      <p v-if="selected" class="task-reference">{{ selected.no }} · {{ selected.workOrderNo }}</p>
      <p v-if="!selected && state.facts?.tasks?.length && state.facts.tasks.every(task => task.qualification?.ready === false)" role="status">当前没有可办理的报工或经过登记任务；原任务和记录仍可查看，选择任务后核对具体原因。</p>
      <div class="controls">
        <label>本人已开工任务<select aria-label="本人已开工任务" :value="state.taskId" :disabled="busy || pending" @change="selectTask($event.target.value)">
          <option value="">请选择本人已开工任务</option>
          <option v-for="row in displayFacts?.tasks || []" :key="row.taskId" :value="String(row.taskId)">{{ row.operationName }} · {{ row.quantityStatusLabel }} · {{ row.no }}</option>
        </select></label>
        <button type="button" :disabled="busy" @click="controller.load()">刷新当前任务</button>
      </div>
      <p v-if="state.readState === 'loading'" role="status">正在读取当前后台身份、本人已开工任务及正式数量，当前结果尚未核实。</p>
      <p v-if="state.error" role="alert" class="warning">{{ state.error }}</p>
      <p v-if="pending" role="alert" class="warning">结果待确认：当前仅可查询原记录，不要再次提交。</p>
      <p v-if="authenticationRequired" role="alert" class="warning">会话已失效，请<router-link :to="{path:'/system-login',query:{redirect:route.fullPath}}">重新登录并返回当前报工位置</router-link>。当前数量和资格尚未核实。</p>
      <p v-if="!state.facts && state.lastDisplayFacts" class="warning">以下仅为同一账号、同一任务的上次只读展示，当前资格及提交结果未核实，不能据此报工。</p>
      <p v-if="state.message" role="status" class="warning"><strong v-if="!state.facts && state.writeState === 'verified'">上次办理反馈（当前事实尚未重新核实）：</strong>{{ state.message }}</p>
      <template v-if="displayFacts">
        <details class="actor-provenance"><summary>当前账号与读取范围：{{ displayFacts.currentActorEvidence.employeeName || displayFacts.currentActorEvidence.username }}</summary><dl class="facts">
          <div><dt>本次后台账号</dt><dd>{{ displayFacts.currentActorEvidence.username }}</dd></div>
          <div><dt>正式员工</dt><dd>{{ displayFacts.currentActorEvidence.employeeName || '当前员工关联未核实' }}</dd></div>
          <div><dt>公司</dt><dd>{{ displayFacts.currentActorEvidence.companyName }}（{{ displayFacts.currentActorEvidence.companyCode }}）</dd></div>
          <div><dt>本次读取范围</dt><dd>本人合法获派且由本人实际开工的任务</dd></div>
        </dl></details>
        <template v-if="selected">
          <h3>任务信息</h3>
          <dl class="facts source-facts">
            <div><dt>任务编号／派工状态</dt><dd>{{ selected.no }}／{{ selected.dispatchStatusLabel }}</dd></div>
            <div><dt>报工数量状态</dt><dd><PceBusinessStatus :status-label="selected.quantityStatusLabel" /></dd></div>
            <div><dt>正式工单／工序</dt><dd>{{ selected.workOrderNo }}／{{ selected.sequence }} · {{ selected.operationName }}</dd></div>
            <div><dt>执行岗位／指定执行人</dt><dd>{{ selected.positionName }}／{{ selected.employeeName }}</dd></div>
            <div><dt>车间／工作中心</dt><dd>{{ selected.workshopName }}／{{ selected.workCenterName }}<span v-if="selected.workCenterCode">（{{ selected.workCenterCode }}）</span></dd></div>
            <div><dt>正式执行模式</dt><dd data-execution-mode>{{ selected.executionModeLabel }}</dd></div>
            
          </dl>
          <MesTaskDates :facts="selected.dateFacts" :task-id="selected.taskId" :current="!!state.facts" />
          <h3>本次报工依据</h3>
          <dl class="facts quantity-summary">
            <template v-if="selected.quantityApplicable === true">
            <div><dt>任务原始作业量／单位</dt><dd data-original-quantity>{{ selected.workloadQuantity }} {{ selected.workloadUomLabel }}</dd></div>
            <div><dt>累计已报量</dt><dd data-reported-quantity>{{ selected.reportedQuantityLabel }}</dd></div>
            <div><dt>剩余未报量</dt><dd data-remaining-quantity>{{ selected.remainingQuantityLabel }}</dd></div>
            <div><dt>正式单位小数位数／最小报工量</dt><dd>{{ selected.quantityPrecision }}／{{ selected.minimumReportQuantity }} {{ selected.workloadUomLabel }}</dd></div>
            </template>
            <template v-else-if="selected.quantityApplicable === false">
              <div><dt>实际完成数量</dt><dd data-nonquantitative-rule>本工序不单独统计实际完成数量，不填写数量或单位。</dd></div>
              <div><dt>工程参考（不是本次实际产量）</dt><dd data-reference-workload>{{ selected.referenceWorkload.quantity ?? '无工程参考量' }} {{ selected.referenceWorkload.uomLabel || '' }}；{{ selected.referenceWorkload.statusLabel || '仅用于正式来源追溯' }}</dd></div>
            </template>
          </dl>
          <p v-if="selected.precisionNotice" class="warning" data-precision-notice>{{ selected.precisionNotice }}</p>
          <p v-if="selected.remainingBelowUnitPrecision" class="warning">剩余量低于正式单位最小报工量，本页不会补齐、截断、归零或认定完工。请先维护正式数量与单位口径。</p>
          <p v-if="state.facts?.qualification" data-report-qualification>{{ state.facts.qualification.statusLabel }}</p>
          <MesActionRestrictions v-if="state.facts" :groups="restrictionGroups" />
          <h3>当前办理</h3>
          <p class="operation-essentials">{{ selected.quantityApplicable === false ? '只登记本人真实经过原因，不填写数量或单位。' : '填写本次实际完成数量和2至300字原因；不得超过服务端剩余量与单位精度。' }}结果待确认时仅查询原记录。</p>
          <label v-if="selected.quantityApplicable === true">本次实际完成数量（{{ selected.workloadUomLabel }}）<input v-model="state.quantity" type="text" inputmode="decimal" aria-label="本次实际完成数量" autocomplete="off" :disabled="busy || pending || !state.facts || !reportAction.enabled" placeholder="请本人填写本次实际完成量" /></label>
          <label>{{ selected.quantityApplicable === false ? '本次实际经过登记原因' : '本次报工说明' }}<textarea v-model="state.reason" rows="2" maxlength="300" :aria-label="selected.quantityApplicable === false ? '本次实际经过登记原因' : '本次报工说明'" :disabled="busy || pending || !state.facts || !reportAction.enabled" :placeholder="selected.quantityApplicable === false ? '请填写2至300字的真实经过及登记原因；不填写实际产量' : '例如说明本次完成的内容；填写2至300字'" /></label>
          <div class="actions"><button type="button" :data-action-code="reportAction.actionCode" :disabled="!submission.enabled" aria-describedby="operation-report-submission-reason" @click="controller.execute()">{{ reportAction.displayName }}</button></div>
          <p id="operation-report-submission-reason" data-report-submission-reason role="status" aria-live="polite">{{ !reportAction.enabled ? '当前不可提交，具体原因见上方办理限制。' : submission.disabledReason || (selected.quantityApplicable === false ? '填写完整，请由本人确认已经实际经过后决定登记；不创建数量报工。' : '填写完整，当前可以提交本次报工；请由本人确认实际完成量后决定提交。') }}</p>
          <p v-if="selected.quantityApplicable === true">后续核对：<router-link :to="{path:'/planning/operation-completions',query:{taskId:String(selected.taskId)}}">工序完工申请及独立审核</router-link>（进入后按原服务重新核定资格；数量达量不等于工序完工）。</p>
          <section aria-label="本次办理结果" aria-live="polite">
            <h3>本次办理结果</h3>
            <button type="button" class="record-link" @click="showOriginalRecords">查看报工记录</button>
            <p v-if="pending" class="warning">结果待核实：请点击“刷新当前任务”并查看下方报工记录；不要再次提交。</p>
            <p v-else-if="state.readState === 'read_failed'" class="warning">读取失败，当前事实与资格未知；请使用上方原读取入口。上次结果不能作为当前办理依据。</p>
            <p v-else-if="state.writeState === 'verified'">{{ selected.quantityApplicable === false ? '实际经过登记成功：已查询原记录并确认保存，请核对登记时间。' : '报工成功：已查询原记录并确认保存，请核对报工数量和时间。' }}</p>
            <p v-else-if="state.writeState === 'rejected'">本次提交被拒绝，请核对上方原原因与字段；未自动重试。</p>
            <p v-else-if="submission.blockingCode.startsWith('QUANTITY_') || submission.blockingCode === 'REASON_LENGTH'">字段校验未通过：{{ submission.disabledReason }}</p>
            <p v-else>尚未提交本次报工。填写后请核对数量和说明，再由本人确认提交。</p>
          </section>

          <details ref="historyDisclosure" class="history-disclosure">
          <summary>报工记录与业务追溯</summary>
          <template v-if="selected.quantityApplicable === false">
            <h3 ref="originalRecords" id="operation-report-original-records" tabindex="-1">正式实际经过登记</h3>
            <p v-if="selected.executionConfirmation" data-execution-confirmation><PceBusinessStatus :status-label="selected.executionConfirmation.statusLabel" />；本人：{{ selected.executionConfirmation.confirmedByLabel }}；实际时间：{{ selected.executionConfirmation.confirmedAtLabel }}；原因：{{ selected.executionConfirmation.reason }}；审计：{{ selected.executionConfirmation.auditReference }}</p>
            <p v-else>本任务尚无正式实际经过登记；读取、刷新和填写原因不会创建记录。</p>
            <p>下一正式节点：<router-link :to="{path:'/planning/operation-completions',query:{taskId:String(selected.taskId)}}">工序完工申请及独立审核</router-link>；已登记实际经过不等于工序已正式完工。</p>
          </template>
          <template v-if="selected.quantityApplicable === true">
          <h3 ref="originalRecords" id="operation-report-original-records" tabindex="-1">正式分次报工记录</h3>
          <ol v-if="selected.reports.length" class="report-history">
            <li v-for="record in selected.reports" :key="record.id">
              <PceBusinessStatus :status-label="record.statusLabel" />；本次数量：{{ record.quantityLabel }}；报工人：{{ record.reportedByLabel }}；实际时间：{{ record.reportedAtLabel }}；原因：{{ record.reason }}<details><summary>报工审计标识</summary><p>{{ record.auditReference }}</p></details>
              <details><summary>本次状态与审计历史（{{ record.statusTransitionCount }}）</summary><p v-for="event in record.statusTransitionHistory" :key="event.id">{{ event.actionLabel }}：{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；{{ event.timestampLabel }}；{{ event.auditReference }}</p></details>
            </li>
          </ol>
          <p v-else>本任务尚无正式报工记录；查看任务与核对数量不会创建报工记录。</p>
          </template>
          <details><summary>来源依据与接收证明</summary><dl class="facts">
            <div><dt>实际开工人／时间</dt><dd>{{ selected.startedByLabel }}／{{ selected.startedAtLabel }}</dd></div>
            <div><dt>正式开工记录／审计</dt><dd>{{ selected.startRecordId }}／{{ selected.startAuditReference }}</dd></div>
            <div><dt>来源工单版本／路线版本／步骤</dt><dd>{{ selected.workOrderVersion ?? '未核实' }}／{{ selected.routeVersionId ?? '未核实' }}／{{ selected.stepId ?? '未核实' }}</dd></div>
            <div><dt>车间接收记录</dt><dd>{{ selected.receiptId ?? '未核实' }}／{{ selected.receiptStatusLabel }}</dd></div>
            <div v-if="selected.resourceSource?.effectiveReceptionAuthority"><dt>本工序有效接收依据</dt><dd data-effective-reception>{{ selected.resourceSource.effectiveReceptionAuthority }}；{{ selected.resourceSource.effectiveWorkshop?.name }}</dd></div>
            <div v-if="selected.resourceSource?.selectionFact"><dt>正式资源选择依据</dt><dd>{{ selected.resourceSource.selectionFact.statusLabel }}；{{ selected.resourceSource.selectionFact.ref }}</dd></div>
            <div v-if="selected.resourceSource?.preciseReceipt"><dt>逐工序精确接收证明</dt><dd data-precise-receipt>{{ selected.resourceSource.preciseReceipt.statusLabel }}；{{ selected.resourceSource.preciseReceipt.actorLabel }}；{{ selected.resourceSource.preciseReceipt.timeLabel }}；{{ selected.resourceSource.preciseReceipt.auditReference }}</dd></div>
</dl></details>
          </details>
        </template>
        <p v-else-if="displayFacts.tasks.length">请明确选择本人已开工任务，系统不会默认选择或自动填写数量。</p>
        <p v-else>本次正式范围内没有由本人合法获派且实际开工的任务。请核对当前登录人；本页不会显示他人任务或由主任代报工。</p>
      </template>
    </section>
    <details id="report-learning" class="card usage-explanation" aria-label="工序报工操作说明" :open="learningOpen" @toggle="onLearningToggle"><summary>操作说明</summary><MesExecutionContext :facts="state.facts" /><p v-if="state.facts?.purposeLabel">{{ state.facts.purposeLabel }}</p>
      <h2>操作说明</h2>
      <ol>
        <li>由任务指定执行人、实际开工人本人登录，选择“本人已开工任务”。</li>
        <li>重新读取并核对正式任务原始作业量、单位、累计已报量、剩余未报量及本次报工资格。</li>
        <li>本人填写大于0且不超过剩余可报量的本次实际完成数量，小数位不得超过当前正式计量单位允许的位数；无需补零。再填写2至300字原因，符合条件后点击“提交本次报工”。</li>
        <li>正式模式为“必经但不统计实际量”时，本页显示“登记实际经过”，只填写真实经过原因，不填写实际数量或单位。工程参考单独展示，不能当成本次实际产量。登记后仍须原完工申请及生产跟单员独立审核。</li>
        <li>本人准入满足后，还须完成当前事实读取及表单校验。按钮旁会说明当前阻止提交的原因；读取或提交中请等待，结果待核实时只重新读取，不重复报工。</li>
        <li>提交后独立只读回查本次数量、报工人、服务端实际时间和审计。结果不明时只重新读取，不重复提交。</li>
      </ol>
      <p><strong>技术交付不代办正式动作；数量报工或实际经过登记均由本人决定并执行。</strong>正量本次数量默认空白，须由本人填写；无统计量模式不填写数量或单位。报工量已达任务量仅是数量事实，不表示工序完工、不证明前序完成，也不放行后续任务。</p>
      <p>本页不执行完工、转移、库存扣减、占用释放或排程调整；读取、刷新和复制诊断均不创建报工记录。</p>
      
    </details>
    <details class="card technical-details"><summary>技术详情</summary><p data-report-form-version>报工表单校验：{{ OPERATION_REPORT_FORM_VERSION }}</p><pre>{{ state.error || "当前无读取错误" }}</pre></details>
    <section v-if="displayFacts" v-show="!selected" ref="taskListArea" class="card task-list-card" :class="{ 'task-list-first': !selected }" aria-label="本人已开工任务列表">
      <h2>本人任务列表</h2>
      <p>{{ state.facts ? `任务记录：${state.serverSurface.resultCount}；正式报工记录：${state.facts.operationReportRecordCount}` : '当前数量未知，上次列表仅供回看。' }}</p>
      <PceEnterpriseListTable :ref="element => table.tableRef = element" :contract="listContract" :page-id="OPERATION_REPORT_PAGE.pageCode"
        table-id="production-operation-report-main" :rows="rows" :table-rows="table.filteredRows" :filter-schema="OPERATION_REPORT_FILTERS"
        :filters="table.filters" :quick-search="table.quickSearch" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length"
        :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="no" primary-label="工序任务编号"
        :primary-width="200" compact-freeze-primary min-width="2100px" :action-width="compactViewport ? 104 : 130"
        @update:quick-search="table.quickSearch = $event" @search="table.appliedSearch = table.quickSearch" @toggle-advanced="table.advancedVisible = !table.advancedVisible"
        @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @export-current="table.exportCurrent"
        @clear-selection="table.selectedRows = []" @update-filter="table.updateFilter" @selection-change="table.selectedRows = $event" @sort-change="table.handleSort">
        <template #columns>
          <el-table-column prop="workOrderNo" label="生产工单编号" :width="compactViewport ? 152 : 190" /><el-table-column prop="operationName" label="工序" :width="compactViewport ? 84 : 130" />
          <el-table-column prop="workshopName" label="车间" :width="compactViewport ? 76 : 110" /><el-table-column prop="workCenterName" label="工作中心" :width="compactViewport ? 120 : 180" />
          <el-table-column prop="workloadLabel" label="任务原始作业量／单位" :width="compactViewport ? 128 : 180" /><el-table-column prop="reportedQuantityLabel" label="累计已报量" :width="compactViewport ? 116 : 170" />
          <el-table-column prop="remainingQuantityLabel" label="剩余未报量" :width="compactViewport ? 116 : 170" /><el-table-column prop="positionName" label="执行岗位" :width="compactViewport ? 104 : 170" />
          <el-table-column prop="employeeName" label="指定执行人" :width="compactViewport ? 84 : 130" /><el-table-column prop="quantityStatusLabel" label="报工数量状态" :width="compactViewport ? 152 : 210"><template #default="{ row }"><PceBusinessStatus :status-label="row.quantityStatusLabel" /></template></el-table-column>
          <el-table-column prop="startedAtLabel" label="实际开工时间" :width="compactViewport ? 176 : 200" />
        </template>
        <template #actions="{ row }"><button type="button" :disabled="busy || pending" :data-task-view="row.taskId" @click="viewTask(String(row.taskId))">{{ row.qualification?.ready === true ? '填写报工' : '查看报工记录' }}</button></template>
      </PceEnterpriseListTable>
    </section>
  </div>
</template>
<script setup>
import MesTaskDates from './MesTaskDates.vue'
import MesActionRestrictions from './MesActionRestrictions.vue'
import MesUnifiedPageGuide from './MesUnifiedPageGuide.vue'
import { learningPreference } from '@/meta/runtime/employeePagePresentation.js'
import MesExecutionContext from '@/meta/components/MesExecutionContext.vue'
import {mesReadContext,mesWorkOrderFilter} from '@/meta/runtime/mesTestProcessNavigation.js'
import { useMesReadTiming } from '@/meta/runtime/mesReadTiming.js'
import { useCompactViewport } from '@/meta/runtime/useCompactViewport.js'
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { operationReportsApi } from '@/api/operationReports.js'
import { createOperationReportState, createOperationReportController, OPERATION_REPORT_FORM_VERSION } from '@/meta/runtime/operationReport.js'
import { OPERATION_REPORT_PAGE, OPERATION_REPORT_FILTERS, OPERATION_REPORT_SEARCH_FIELDS, OPERATION_REPORT_EXPORT_COLUMNS } from '@/meta/runtime/operationReportContract.js'
import { OPERATION_REPORT_ACTION_CONTRACT, resolvePceOperationReportAction } from '@/meta/runtime/pceBusinessActionRegistry.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
const originalRecords = ref(null), historyDisclosure = ref(null)
const learning = learningPreference('operation-reports', readTabIdentity)
const learningOpen = ref(learning.read()), taskListArea = ref(null), listReturn = ref(null), restoringList = ref(false)
function onLearningToggle(event) { learningOpen.value=event.target.open;learning.write(learningOpen.value) }
const taskArea = ref(null), compactViewport = useCompactViewport()
async function showOriginalRecords() {
  if (historyDisclosure.value) historyDisclosure.value.open = true
  await nextTick()
  originalRecords.value?.scrollIntoView({ block: 'start' })
  originalRecords.value?.focus({ preventScroll: true })
}
const emit = defineEmits(['refresh-status']), route = useRoute(), router = useRouter()
const state = reactive(createOperationReportState())
const owner = () => JSON.stringify([getTabAuthEpoch(), readTabIdentity()?.userId, readTabIdentity()?.companyId, readTabIdentity()?.username])
const {visibleReadMs,readCycle}=useMesReadTiming(()=>state.readState)
const controller = createOperationReportController({ state, api: {...operationReportsApi,readRecovery:params=>operationReportsApi.read(params),read:params=>operationReportsApi.read({...params,...mesWorkOrderFilter(route)})}, owner,
  companyId: () => readTabIdentity()?.companyId, userId: () => readTabIdentity()?.userId })
const authenticationRequired = computed(() => Number(state.factLoadFacts?.httpStatus) === 401 || ['not_authenticated','token_not_valid','AUTHENTICATION_CONTEXT_CHANGED'].includes(state.factLoadFacts?.errorCode))
const displayFacts = computed(() => state.facts || state.lastDisplayFacts), selected = computed(() => displayFacts.value?.selectedTask)
const busy = computed(() => state.readState === 'loading' || state.writeState === 'writing'), pending = computed(() => state.writeState === 'readback_pending')
const reportAction = computed(() => {
  const facts = state.facts || state.lastDisplayFacts
  const action = facts ? resolvePceOperationReportAction(facts) : OPERATION_REPORT_ACTION_CONTRACT
  return state.facts ? action : { ...action, enabled: false, disabledReason: '结果待核实，请仅重新读取。' }
})
const submission = computed(() => controller.submission())
const rows = computed(() => displayFacts.value?.tasks || [])
const listContract = createPceEnterpriseListContract({ pageCode: OPERATION_REPORT_PAGE.pageCode, pageType: 'list', title: OPERATION_REPORT_PAGE.title, moduleCode: 'MES' })
const table = reactive(usePceEnterpriseListRuntime({ rows, filterSchema: OPERATION_REPORT_FILTERS, pageCode: OPERATION_REPORT_PAGE.pageCode,
  searchFields: OPERATION_REPORT_SEARCH_FIELDS, exportFileName: '本人工序报工.csv', exportColumns: OPERATION_REPORT_EXPORT_COLUMNS }))
function rememberTaskList(rowId) { if(selected.value)return;const t=table.tableRef,wrap=t?.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap');listReturn.value={page:t?.currentPage||1,size:t?.pageSize||20,top:wrap?.scrollTop||0,left:wrap?.scrollLeft||0,pageY:window.scrollY,rowId} }
async function restoreTaskList() { if(!restoringList.value || selected.value)return;await nextTick();await new Promise(resolve=>requestAnimationFrame(resolve));const saved=listReturn.value,t=table.tableRef;if(saved&&t){t.pageSize=saved.size;t.currentPage=saved.page;await nextTick();const wrap=t.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap');if(wrap){wrap.scrollLeft=saved.left;wrap.scrollTop=saved.top}window.scrollTo({top:saved.pageY,left:0});t.$el?.querySelector(`[data-task-view="${saved.rowId}"]`)?.focus({preventScroll:true})}else taskListArea.value?.scrollIntoView({block:'start'});restoringList.value=false }
async function returnToTasks() { if(busy.value||pending.value)return;restoringList.value=true;await selectTask('');if(!busy.value)await restoreTaskList() }
async function selectTask(value) { if (busy.value || pending.value) return;if(value)rememberTaskList(value); await router.replace({ query: { ...route.query, taskId: value || undefined } }) }
async function viewTask(value) {
  if (busy.value || pending.value) return
  await selectTask(value)
  await nextTick()
  taskArea.value?.scrollIntoView({block:'start'})
  taskArea.value?.focus({preventScroll:true})
}
function safeDiagnostics(value) {
  if (Array.isArray(value)) return value.map(safeDiagnostics)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).filter(([key]) => !/executionToken|idempotency|password|authorization|cookie|jwt|secret/i.test(key))
    .map(([key, item]) => [key, safeDiagnostics(item)]))
}
function buildDiagnostics() {
  const factLoadFacts = state.factLoadFacts || createReadFailedFactLoad({ apiUrl: OPERATION_REPORT_PAGE.apiUrl,
    errorCode: 'FACTS_NOT_LOADED', errorMessage: '报工事实尚未读取，任务数量、累计、剩余量及资格未知。' })
  const server = state.serverSurface || { ...factLoadFacts, factLoadFacts, operationReportFacts: null, resultCount: null, passed: false }
  return safeDiagnostics({ ...factLoadFacts, factOwner: OPERATION_REPORT_PAGE.moduleId, pageFactOwner: OPERATION_REPORT_PAGE.moduleId,
    moduleCode: OPERATION_REPORT_PAGE.moduleId, factSource: 'server', operationReportFacts: state.facts,
    strictFacts: server, strictServerFacts: server, factLoadFacts, resultCount: server.resultCount,
    readState: state.readState, writeState: state.writeState, errorMessage: state.error || null,
    reportSubmission: controller.submission() })
}
const provider = { factOwner: OPERATION_REPORT_PAGE.moduleId, refresh: () => controller.load(), buildDiagnostics }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
function authenticationChanged() {
  learningOpen.value=learning.read();listReturn.value=null;controller.invalidate(); table.selectedRows = []; table.clearFilters(); table.handleSort()
  controller.select(String(route.query.taskId || ''))
}
watch(() => [route.query.taskId,route.query.workOrderId], () => controller.select(String(route.query.taskId || '')), { immediate: true })
watch(() => state.readState, async value => {emit('refresh-status', ({ loading: 'refreshing', loaded: 'success', read_failed: 'error' })[value] || 'idle');if(value==='loaded')await restoreTaskList()})
onMounted(() => { observability?.register?.(provider); globalThis.window?.addEventListener?.('pce:authentication-changed', authenticationChanged) })
onBeforeUnmount(() => { controller.invalidate(); observability?.unregister?.(provider); globalThis.window?.removeEventListener?.('pce:authentication-changed', authenticationChanged) })
defineExpose({navigationContext:computed(()=>mesReadContext(state.facts)), refresh: () => controller.load(), buildDiagnostics })
const restrictionGroups=computed(()=>[{label:'报工资格',items:state.facts?.qualification?.missingItems || []},{label:reportAction.value.displayName || '提交报工',items:!reportAction.value.enabled && reportAction.value.disabledReason ? [reportAction.value.disabledReason] : []}])
</script>
<style scoped>
.operation-report-content{display:grid;gap:16px;min-width:0;padding:18px}.card{min-width:0;border:1px solid #dbe3ef;border-radius:12px;background:white;padding:20px}.card h2{margin:0 0 14px}.card p,.card li{line-height:1.7;overflow-wrap:anywhere}.controls,.actions{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.operation-report-content label{display:block;max-width:700px;margin:12px 0;min-width:220px}.controls label{flex:1}.operation-report-content select,.operation-report-content input,.operation-report-content textarea{display:block;box-sizing:border-box;width:100%;margin-top:7px;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font:inherit}.operation-report-content button{padding:9px 12px;border:1px solid #3568dc;border-radius:6px;background:#3568dc;color:white;cursor:pointer}.operation-report-content button:disabled{opacity:.5;cursor:not-allowed}.warning{padding:10px;background:#fff7e6;color:#744b0a;border-radius:6px}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px}.facts dt{font-size:12px;color:#64748b}.facts dd{margin:4px 0;font-weight:600;overflow-wrap:anywhere}.source-facts{border-top:1px solid #e2e8f0;padding-top:14px}.report-history li,details{margin:12px 0}@media(max-width:650px){.operation-report-content{padding:8px}.card{padding:14px}.facts{grid-template-columns:1fr}.controls{display:block}}
</style>

<style scoped>
.operation-report-content summary{cursor:pointer;min-height:44px;line-height:1.6;font-weight:600}.operation-report-content button,.operation-report-content select,.operation-report-content input{min-height:44px}.operation-report-content :focus-visible{outline:3px solid #2563eb;outline-offset:3px}
</style>

<style scoped>
.quantity-summary{padding:14px;background:#f0f6ff;border:1px solid #cddff8;border-radius:8px}.quantity-summary dd{font-size:18px}.operation-essentials{padding:10px 12px;background:#f0f6ff;border-radius:6px}.actor-provenance{margin:10px 0}.operation-report-content h3{scroll-margin-top:100px}.operation-report-content label{min-width:0;width:100%}.controls label{min-width:0}.operation-report-content select{max-width:100%;text-overflow:ellipsis}@media(max-width:650px){.controls button,.actions button{width:100%}.facts{gap:12px}.quantity-summary{padding:12px}}
</style>

<style scoped>
.operation-report-content h3{scroll-margin-top:200px}.operation-report-content .record-link{background:#fff;color:#1d4ed8}@media(max-width:650px){.operation-report-content h3{scroll-margin-top:250px}}
</style>

<style scoped>
@media(max-width:900px) {
  .operation-report-content { gap: 10px; padding: 4px 0; font-size: .875rem; }
  .card { padding: 10px; border-radius: 8px; }
  .card h2 { margin: 0 0 10px; font-size: 1.0625rem; line-height: 1.4; }
  .card h3 { margin: 14px 0 8px; font-size: .9375rem; line-height: 1.4; scroll-margin-top: calc(var(--pce-account-bookmark-height,52px) + var(--pce-system-bar-height,48px) + 12px); }
  .card p,.card li { margin-block: 8px; line-height: 1.5; }
  .task-action-card { order: 0; scroll-margin-top: calc(var(--pce-account-bookmark-height,52px) + var(--pce-system-bar-height,48px) + 12px); }
  .task-list-card { order: 2; }
  .usage-explanation { order: 3; }
  .operation-report-content > :deep(.mes-execution-context) { order: 4; }
  .test-provenance { order: 5; margin: 0; padding: 4px 10px; border: 1px solid #dbe3ef; border-radius: 8px; background: #fff; }
  .operation-report-content > details,.operation-report-content > :deep(details.mes-execution-context) { margin-block: 0; }
  .facts { grid-template-columns: repeat(2,minmax(0,1fr)); gap: 8px 12px; margin-block: 10px; }
  .facts dt { font-size: .75rem; line-height: 1.4; }
  .facts dd { margin-top: 3px; font-size: .875rem; line-height: 1.45; }
  .source-facts > div:nth-child(1),.source-facts > div:nth-child(3),.source-facts > div:last-child { grid-column: 1/-1; }
  .quantity-summary { padding: 10px; }
  .quantity-summary dd { font-size: 1rem; }
  .operation-essentials { padding: 8px; }
  .operation-report-content label { margin-block: 8px; font-size: .8125rem; }
  .operation-report-content input,.operation-report-content select,.operation-report-content textarea { font-size: 16px; padding: 8px; }
  .operation-report-content button { font-size: .8125rem; }
  .operation-report-content summary { font-size: .8125rem; line-height: 1.45; display: flex; align-items: center; }
  .operation-report-content summary::before { content: '▸'; margin-right: 6px; }
  .operation-report-content details[open] > summary::before { content: '▾'; }
  .history-disclosure { margin-block: 10px; padding: 4px 10px; border: 1px solid #dbe3ef; border-radius: 8px; }
  .controls { display: flex; gap: 6px; }
  .controls label { flex: 1 1 100%; }
  .controls button { width: auto; }
  .warning { padding: 8px; }
  .report-history { padding-left: 22px; }
}
</style>

<style scoped>
.operation-report-content{font-size:16px;line-height:1.6;gap:18px;max-width:100%;margin:0 auto;width:100%;box-sizing:border-box}
.employee-heading{display:flex;justify-content:space-between;align-items:start;gap:16px}.employee-heading h2{font-size:24px;margin:0 0 8px}.eyebrow{color:#52647b;font-size:14px;margin:0 0 4px}.task-reference{color:#52647b;font-size:14px;overflow-wrap:anywhere}
.task-action-card{order:0}.task-list-card{order:2}.task-list-first{order:1}.sample-context{order:6}.usage-explanation{order:5}.sample-context,.usage-explanation{background:#fff;border:1px solid #dbe3ef;padding:12px 16px;border-radius:10px}
.operation-report-content .record-link{background:white;color:#1e4fa0}.actions button{font-weight:600;padding:12px 24px}.operation-report-content button:disabled{opacity:1;background:#e8edf4;color:#596779;border-color:#b8c4d4}
.operation-report-content section[aria-label="本次办理结果"]{padding:14px 16px;border:1px solid #cbd9e9;border-radius:10px;margin:18px 0;background:#f6f9fd}
.facts dt{font-size:14px}.facts dd{font-size:16px}.quantity-summary dd{font-size:20px}.history-disclosure{padding:12px;border:1px solid #dbe3ef;border-radius:8px}summary{min-height:44px}
@media(max-width:650px){.operation-report-content{font-size:16px;padding:8px;gap:12px}.employee-heading{display:block}.employee-heading h2{font-size:22px}.employee-heading button{margin:8px 0}.card{padding:16px}.facts{grid-template-columns:1fr}.facts dt,.operation-report-content label{font-size:14px}.facts dd{font-size:16px}.operation-report-content button,.operation-report-content summary{font-size:15px}.controls button{width:100%}.quantity-summary dd{font-size:20px}.sample-context,.usage-explanation{padding:10px 14px}}
</style>

<style scoped>
.report-navigation{position:sticky;top:calc(var(--pce-account-bookmark-height,52px) + var(--pce-system-bar-height,48px));z-index:20;display:flex;gap:10px;flex-wrap:wrap;background:white;padding:6px 10px;border-bottom:1px solid #dbe3ef}.operation-report-content{font-size:15px;gap:12px}.card{padding:14px}.operation-report-content .employee-heading h2{font-size:21px}.operation-report-content button{min-height:44px}.technical-details pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
@media(max-width:900px){.operation-report-content{font-size:14.5px}.card{padding:12px}.operation-report-content .employee-heading h2{font-size:20px}.operation-report-content h3{font-size:17px}.operation-report-content label,.operation-report-content button,.operation-report-content summary,.facts dd{font-size:14.5px}.operation-report-content input,.operation-report-content select,.operation-report-content textarea{font-size:15px;min-height:44px}.operation-report-content .el-table{font-size:14px}}
</style>

<style scoped>
/* These page shells size to their content; their overflow must not become a false sticky scroll container. */
:global(.pce-list-page-shell:has(.operation-report-content)),:global(.pce-list-page-content:has(> .operation-report-content)){overflow:visible}
</style>
