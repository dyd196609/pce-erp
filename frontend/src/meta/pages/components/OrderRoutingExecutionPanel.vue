<template>
  <section ref="panelRoot" class="card order-execution-panel" data-fact-source="server" data-order-execution-owner="order">
    <section v-if="ownEntry" aria-label="本人任务开工" data-assignee-entry>
      <h2>本人任务开工</h2><p>仅显示本人有效职责及资源范围内的获派任务。开工后可进入独立报工、完工审核及交接页面，各页面仍由服务端核验相应办理职责。</p>
      <p v-if="error" role="alert">{{ error }}</p><el-button :loading="busy || startBusy" @click="load">刷新本人任务</el-button>
      <label>本人任务所属订单 <el-select v-model="selectedId" @change="loadOperationStarts"><el-option v-for="item in arrangements" :key="item.id" :value="item.id" :label="item.orderNo" /></el-select></label>
      <p v-if="startError" role="alert">{{ startError }}</p>
      <label>本次实际开工说明（测试代办请明确注明）<el-input v-model="startReason" type="textarea" maxlength="300" :disabled="startWriting" placeholder="填写本次实际开工说明；测试代办须注明代办身份与测试用途" /></label>
      <template v-if="startFacts"><h3>{{ startFacts.workOrderNo }} · {{ startFacts.purposeLabel }}</h3><p>本人范围内任务{{ startFacts.summary.tasks }}项，已开工{{ startFacts.summary.started }}项，待开工{{ startFacts.summary.waiting }}项。此计数不是全公司或全工单数量。</p><p>{{ startFacts.timePolicyLabel }}</p>
        <article v-for="row in startFacts.rows" :key="row.taskId"><h3>{{ row.taskNo }} · {{ row.operationName }}</h3><p>获派本人：{{ row.employeeName }}（{{ row.username }}）；{{ row.positionName }}；{{ row.workCenterName }}</p><PceBusinessStatus :status-label="row.statusLabel" />
          <p v-if="row.execution">实际开工：{{ row.execution.startedAtLabel }}；办理人：{{ row.execution.startedByLabel }}；记录{{ row.execution.id }}；审计{{ row.execution.auditReference }}；状态转换{{ row.statusTransitionCount }}条。</p><p v-else>尚未开工；{{ row.assigneeBlockers.join('；') }}</p><p v-if="row.execution">{{ row.execution.reason }}</p><el-button v-if="row.availableAction.executable" :loading="startWriting" @click="startOperation(row)">{{ row.availableAction.displayName }}</el-button>
          <p v-if="row.execution?.testAgentProvenance">{{ row.execution.testAgentProvenance.statusLabel }}；{{ row.execution.testAgentProvenance.auditReference }}</p>
          <p v-if="row.execution && startFacts.mesNavigation"><router-link v-for="entry in startFacts.mesNavigation" :key="entry.route" :to="{ path: entry.route, query: { taskId: String(row.taskId) } }" style="margin-right: 1em">{{ entry.label }}</router-link></p>
        </article>
      </template>
    </section>
    <template v-else>
    <h2>订单工序执行安排</h2>
    <p class="task-hint">选择当前订单后，直接点击下方业务入口。安排、排程与工单状态分别展示；测试用途不具备正式制造资格。</p>
    <p v-if="readState==='loading'" role="status" data-arrangement-loading>正在读取订单安排并核验当前来源，请稍候…</p>
    <div v-if="readState==='read_failed'" role="alert" data-arrangement-read-error><strong>{{ readErrorCode==='MES_ASSIGNEE_SCOPE_NOT_APPLICABLE' ? '当前职责不适用此本人任务入口' : '订单安排读取失败' }}</strong><p>{{ error }}</p><router-link v-if="readErrorCode==='MES_ASSIGNEE_SCOPE_NOT_APPLICABLE'" to="/planning/mes-test-execution">按职责进入MES执行与历史验收</router-link><el-button v-else :loading="busy" @click="load">重试读取订单安排</el-button><p>标准路线目录读取成功不代表订单安排已读取。</p></div>
    <p v-if="readState==='empty_valid'" role="status">已成功读取，当前公司确实没有订单安排记录。</p>
    <p v-if="restoreNotice" role="status" class="restore-notice">{{ restoreNotice }}</p>
    <details class="arrangement-help"><summary>操作说明与标准引用（按需查看）</summary>
    <p>标准路线版本决定有哪些工序及顺序，只能在企业基础资料维护。这里选择固定标准版本，办理本订单已有工序的执行、不执行或待核定；材料不变时不增加物料清单版本，执行选择不增加路线版本。</p>
    <p>草稿直接保存并保留办理审计；已确认或被下游引用时，通过安排自身修订办理，不冒用标准路线版本号，也不新增审批。测试用途仍禁止制造。</p>
    <router-link :to="foundationRoute">标准模板缺项？前往企业基础资料→工艺路线</router-link>
    <p v-if="error && readState!=='read_failed'" role="alert">{{ error }}</p>
    <p class="source-identity-note">查看已有安排时，以下选择器回填真实来源；改选但未显式固定时，已保存来源仍以下方安排身份为准。长选项可展开完整查看。</p>
    <div v-if="choices" class="selection">
      <label>来源物料清单版本（当前安排回填）
        <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-bom" v-model="bomId" :disabled="navigationLocked" @change="preview=null" placeholder="明确选择已有版本"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option v-for="b in choices.bomVersions" :key="b.id" :value="b.id" :label="`版本名称${b.bom_version}（记录ID ${b.id}）`" /></el-select>
      </label>
      <label>固定标准路线版本（当前安排回填）
        <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-routing" v-model="routeId" :disabled="navigationLocked" placeholder="选择准确版本，不自动取最新版" @change="preview=null"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option v-for="v in choices.standardVersions" :key="v.id" :value="v.id" :label="`${v['routing__routing_code']}／${v['routing__name']}｜版本名称${v.routing_version}｜修订号${v.revision}｜记录ID ${v.id}`" /></el-select>
      </label>
      <el-button :disabled="!bomId || !routeId || navigationLocked" @click="previewStandard">读取所选标准结构</el-button>
      <template v-if="preview"><span>标准结构 {{ preview.steps.length }} 步（只读）</span><el-input v-model="selectReason" placeholder="固定引用的图纸或业务依据" style="width:28em" /><el-checkbox v-model="resetExecution">草稿显式重新固定引用并重新安排（原依据保留审计）</el-checkbox><el-button :disabled="!selectReason.trim() || !choices.maintenanceAuthorization?.allowed || navigationLocked" @click="selectStandard">固定此标准版本</el-button></template>
    </div>
    </details>
    <div class="arrangement-toolbar"><label v-if="currentArrangements.length">当前订单安排
      <el-select class="order-select order-select-arrangement" v-model="selectedId" :disabled="navigationLocked" @change="changeArrangement" placeholder="选择当前订单安排"><el-option v-for="a in currentArrangements" :key="a.id" :value="a.id" :label="`${a.orderNo}｜当前安排${a.id}｜自身修订${a.arrangementRevision}`" /></el-select>
    </label><el-button :loading="busy" @click="load">刷新订单安排</el-button></div>
    <nav v-if="selected && readState==='loaded'" class="order-business-entries" aria-label="订单业务区域" data-order-business-entries><el-button v-for="area in businessAreas" :key="area.key" :type="activeArea===area.key ? 'primary' : 'default'" :aria-pressed="activeArea===area.key" @click="selectBusinessArea(area.key)">{{ area.label }}</el-button></nav>
    <details class="history-arrangements"><summary>历史安排（只读沿革）</summary><p>历史安排保留已保存结果，不作为当前有效作业量使用。</p><el-button v-for="a in arrangements.filter(x=>!x.isCurrent)" :key="a.id" :disabled="navigationLocked" @click="openArrangement(a.id)">{{ a.orderNo }}｜历史安排{{ a.id }}｜自身修订{{ a.arrangementRevision }}</el-button></details>
    <article v-if="selected && readState==='loaded'">
      <header class="arrangement-identity" data-current-arrangement><h3>{{ selected.orderNo }}</h3><strong>{{ isCurrentSelection ? '当前有效安排' : '历史安排（不作当前消费）' }} {{ selected.id }} · 自身修订{{ selected.arrangementRevision }} · 编辑序号{{ selected.editVersion }}</strong><p>{{ selected.purposeLabel }} · 当前区域：<strong>{{ activeAreaLabel }}</strong></p><div class="separate-business-statuses"><span>安排状态：<PceBusinessStatus :status-label="selected.statusLabel" /></span><span>排程状态：{{ startFacts?.scheduleStatusLabel || taskFacts?.scheduleStatusLabel || activeTestSchedule?.statusLabel || (savedScheduleBusy ? '读取中' : scheduleFacts ? '无有效保存排程' : '尚未读取') }}</span><span>工单状态：{{ startFacts?.workOrderStatusLabel || taskFacts?.workOrderStatusLabel || workOrderFacts?.workOrder?.statusLabel || (workOrderBusy ? '读取中' : workOrderReadState==='empty_valid' ? '无当前工单承接来源' : '尚未读取') }}</span></div></header><details><summary>来源身份与固定版本</summary>
      <p>物料清单版本名称：{{ selected.bomVersionName }}；记录ID：{{ selected.bomVersionId }}。标准路线：{{ selected.routingCode }}／{{ selected.routingName }}；版本名称：{{ selected.routingVersionName }}；修订号：{{ selected.routingVersionRevision }}；固定记录ID：{{ selected.routingVersionId }}。</p>
      <p>来源核算 {{ selected.sourceCalculationNo }}（记录{{ selected.sourceCalculationId }}），工程来源{{ selected.sourceId }}，冻结基线{{ selected.baselineId }}；来源均由服务端真实关联读取。</p>
      <p><strong>订单执行安排记录ID {{ selected.id }}／自身修订号{{ selected.arrangementRevision }}</strong>；{{ selected.statusLabel }}；编辑序号{{ selected.editVersion }}。编辑序号用于并发保存控制，与标准路线修订号、安排自身修订号及记录ID不同。</p>
      </details>
      <section v-if="activeArea==='taskStart'" class="work-order-business-view" aria-label="任务开工" data-operation-start-area>
        <h3>任务开工</h3><p>先看本人任务和前序条件，再按权限办理。已派工不代表可开工；计划与实际时间分别展示。本轮不报工、不确认完工。</p>
        <p v-if="startBusy" role="status">正在核验当前来源、本人资格及固定路线前序…</p><p v-if="startError" role="alert">{{ startError }} <el-button @click="loadOperationStarts">重试读取任务开工</el-button></p>
        <template v-if="startFacts"><p v-if="!startFacts.workOrderId">{{ startFacts.emptyReason }}</p><template v-else><h4>{{ startFacts.workOrderNo }} · {{ startFacts.purposeLabel }}</h4>
          <p class="receipt-totals">任务{{ startFacts.summary.tasks }}份 · 已开工{{ startFacts.summary.started }}项 · 待开工{{ startFacts.summary.waiting }}项 · 前序未满足{{ startFacts.summary.predecessorBlocked }}项</p>
          <p>{{ startFacts.timePolicyLabel }}</p>
          <label>本次实际开工说明（测试代办请明确注明）<el-input v-model="startReason" type="textarea" maxlength="300" :disabled="startWriting" /></label>
          <div class="task-route-scroll"><article v-for="row in startFacts.rows" :key="row.taskId" :data-start-task="row.taskId"><h4>{{ row.sequence }}．{{ row.operationName }} · {{ row.statusLabel }}</h4>
            <p>任务：<strong>{{ row.taskNo }}</strong>；{{ row.workshopName }}／{{ row.workCenterName }}</p><p>实际派工操作人：{{ row.employeeName }}／{{ row.positionName }}（{{ row.username }}）</p>
            <p>计划开始：{{ dateText(row.planStart) }}<br />计划结束：{{ dateText(row.planEnd) }}</p>
            <p v-if="row.execution"><strong>实际开工：{{ row.execution.startedAtLabel }}</strong>；办理人：{{ row.execution.startedByLabel }}</p><p v-else>实际开工：尚未开工</p>
            <p>前序条件：{{ row.predecessors.statusLabel }}</p><p v-if="!row.execution && row.assigneeBlockers.length">当前准入未满足：{{ row.assigneeBlockers.join('；') }}</p>
            <p v-if="row.execution">办理说明：{{ row.execution.reason }}</p>
            <p v-if="row.execution?.testAgentProvenance">{{ row.execution.testAgentProvenance.statusLabel }}；{{ row.execution.testAgentProvenance.auditReference }}</p>
            <el-button v-if="row.availableAction.executable" :disabled="startWriting || navigationLocked" :loading="startWriting" @click="startOperation(row)">{{ row.availableAction.displayName }}</el-button>
            <details><summary>查看前序与开工来源</summary><p>{{ row.sourceProblem }}；准确固定步骤{{ row.stepId }}；{{ row.dispatchStatusLabel }}</p><ul><li v-for="item in row.predecessors.items" :key="item.sequence">{{ item.sequence }}．{{ item.operationName }}：{{ item.statusLabel }}</li></ul><p v-if="row.execution">已保存开工记录{{ row.execution.id }}；状态转换{{ row.statusTransitionCount }}条，审计{{ row.execution.auditReference }}</p></details>
          </article></div>
        </template></template><p v-if="startMessage" role="status">{{ startMessage }}</p>
      </section>
      <section v-if="activeArea==='dispatch'" class="work-order-business-view" data-workshop-dispatch-area aria-label="车间派工">
        <h3>车间派工</h3><p>按各工序自己的作业量和单位派工，产品数量、工序项数和排程占用段数分别保留。查看不派工，不开工、不报工。</p>
        <p v-if="taskBusy" role="status">正在核验工单、接收、岗位人员及已保存任务…</p><p v-if="taskError" role="alert">{{ taskError }} <el-button @click="loadWorkshopTasks">重试读取车间派工</el-button></p>
        <template v-if="taskFacts"><p v-if="!taskFacts.workOrderId">{{ taskFacts.emptyReason }}</p><template v-else><h4>{{ taskFacts.workOrderNo }} · {{ taskFacts.purposeLabel }}</h4>
          <p v-if="taskFacts.summary" class="receipt-totals">执行工序{{ taskFacts.summary.executingOperations }}项 · 已保存任务{{ taskFacts.summary.taskCount }}份 · 已有效派工{{ taskFacts.summary.dispatchedOperations }}项 · 剩余未派{{ taskFacts.summary.remainingOperations }}项</p>
          <p v-if="!taskFacts.currentSourceValid" role="alert">来源已失效，仅保留历史查看：{{ taskFacts.sourceProblem }}</p>
          <div class="task-route-scroll"><article v-for="group in taskFacts.groups" :key="group.workshopId" :data-task-workshop="group.workshopId"><h4>{{ group.workshopName }} · {{ group.dispatchedOperationCount }}/{{ group.rows.length }}项已派工</h4>
            <p>接收记录{{ group.receiptId }}；派工办理人：{{ group.dispatchers.map(x=>x.employeeName).join('、') || '尚无有效派工职责' }}。具体操作人见各工序。</p>
            <el-button v-if="group.availableAction.executable" :disabled="navigationLocked || taskWriting" :loading="taskWriting" @click="dispatchWorkshopTasks(group)">{{ group.availableAction.displayName }}</el-button>
            <ol class="task-operation-cards"><li v-for="row in group.rows" :key="row.operationId" :data-task-operation="row.operationId"><strong>{{ row.sequence }}．{{ row.operationName }}</strong> · <PceBusinessStatus :status-label="row.statusLabel" />
              <p>任务：<strong>{{ row.task?.no || '尚未保存' }}</strong>；派工对象：{{ row.task ? row.task.employeeName+'／'+row.task.positionName : row.autoChoice ? row.candidates[0].employeeName+'／'+row.candidates[0].positionName : row.candidateLabel }}</p>
              <p>本工序量 {{ row.quantity }} {{ row.unitLabel }}；已分配 {{ row.assignedQuantity ?? '待重新核定' }} {{ row.unitLabel }}；剩余 {{ row.remainingQuantity ?? '待重新核定' }} {{ row.unitLabel }}</p>
              <p>计划：{{ dateText(row.start) }}～{{ dateText(row.end) }}；工作中心：{{ row.workCenterName }}</p>
              <p v-if="row.task">派工人：{{ row.task.dispatchedByLabel }}；派工保存时间：{{ dateText(row.task.dispatchedAt) }}</p>
              <details><summary>查看人员、班组与来源依据</summary><p>有效候选：{{ row.candidates.map(x=>x.employeeName+'（'+x.positionName+'）').join('、') || '缺少有效候选' }}；{{ row.candidateLabel }}。</p><p>准确固定步骤{{ row.stepId }}，工单工序{{ row.operationId }}；任务沿父工单及本车间接收记录保留冻结来源。</p></details>
            </li></ol>
          </article></div><p>{{ taskFacts.resourcePolicyLabel }}有效设备候选{{ taskFacts.equipmentCount }}项。</p>
        </template></template><p v-if="taskMessage" role="status">{{ taskMessage }}</p>
      </section>
      <section v-if="activeArea==='workOrder'" class="work-order-business-view" data-work-order-business-area aria-label="工单与车间接收">
        <h3 ref="workOrderHeading" tabindex="-1">工单与车间接收</h3>
        <p v-if="workOrderBusy" role="status">正在读取当前订单的已保存排程、工单及车间接收结果，不重新计算日期预览…</p>
        <p v-if="workOrderError" role="alert">{{ workOrderError }} <el-button @click="loadWorkOrderReception">重试读取工单与接收</el-button></p>
        <p v-if="workOrderReadState==='empty_valid'" role="status">{{ workOrderEmptyLabel }}</p>
        <template v-if="workOrderFacts?.workOrder">
          <div class="work-order-summary" data-saved-test-work-order><h4>{{ workOrderFacts.workOrder.no }}</h4>
            <p><PceBusinessStatus :status-label="workOrderFacts.workOrder.statusLabel" /> · {{ workOrderFacts.workOrder.purposeLabel }} · 产品 <strong>{{ workOrderFacts.workOrder.quantity }} {{ workOrderFacts.workOrder.uomLabel }}</strong></p>
            <template v-if="workOrderFacts.dispatch"><p>下达人：<strong>{{ workOrderFacts.dispatch.releasedByLabel || workOrderFacts.dispatch.releasedById || '尚未下达' }}</strong>；下达时间：{{ dateText(workOrderFacts.dispatch.releasedAt) || '尚未下达' }}（北京时间）</p>
              <p class="receipt-totals">应接收 <strong>{{ workOrderFacts.dispatch.scopeCount }}</strong> 车间 · 已接收 <strong>{{ workOrderFacts.dispatch.receivedScopeCount }}</strong> · 剩余 <strong>{{ workOrderFacts.dispatch.remainingScopeCount }}</strong></p>
            </template>
          </div>
          <p v-if="!workOrderFacts.workOrder.currentSourceValid" role="alert">当前来源已变化，以下为保存历史，不能继续办理。</p>
          <div v-if="workOrderFacts.dispatch" data-test-work-order-dispatch>
            <table class="receipt-detail-table" aria-label="车间接收明细"><caption>各车间接收结果（北京时间）</caption><thead><tr><th>车间／接收状态</th><th>接收人／时间</th><th>工序范围</th></tr></thead><tbody>
              <template v-for="scope in workOrderFacts.dispatch.scopes" :key="scope.workshopId"><tr :data-test-receipt-workshop="scope.workshopId"><td><strong>{{ scope.workshopName }}</strong><br/><PceBusinessStatus :status-label="scope.receipt.statusLabel" /></td>
                <td><strong>{{ scope.receipt.receivedByLabel || '尚未接收' }}</strong><time :title="dateText(scope.receipt.receivedAtLabel)">{{ scope.receipt.receivedAtLabel ? compactReceiptTime(scope.receipt.receivedAtLabel) : '尚无接收时间' }}</time></td>
                <td>{{ scope.operationCount }}项<br/><el-button size="small" :aria-label="scope.workshopName+'：查看工序'" :aria-expanded="expandedReceiptWorkshop===scope.workshopId" @click="toggleReceiptScope(scope.workshopId)">{{ expandedReceiptWorkshop===scope.workshopId ? '收起工序' : '查看工序' }}</el-button></td></tr>
                <tr v-if="expandedReceiptWorkshop===scope.workshopId" :data-receipt-scope-detail="scope.workshopId"><td colspan="3"><h4>{{ scope.workshopName }}所属执行工序（{{ scope.operationCount }}项）</h4><ol><li v-for="op in scope.operations" :key="op.id">{{ op.sequence }}．{{ op.operationName }}；{{ dateText(op.start) }}～{{ dateText(op.end) }}</li></ol></td></tr>
              </template>
            </tbody></table>
            <p class="business-boundary">仅测试用途；本区域只查看下达与接收，车间派工请使用上方同级入口；本轮不开工、不报工。</p>
            <details v-if="workOrderFacts.dispatch.availableActions.some(x=>x.executable) || workOrderFacts.dispatch.scopes.some(x=>x.availableAction?.executable)"><summary>业务办理（按本人权限提供）</summary><label>办理说明 <input v-model="workOrderReleaseReason" maxlength="240" /></label><el-button v-for="item in workOrderFacts.dispatch.availableActions.filter(x=>x.executable)" :key="item.actionCode" :disabled="navigationLocked || workOrderGenerating" @click="releaseTestWorkOrder">{{ item.displayName }}</el-button><template v-for="scope in workOrderFacts.dispatch.scopes" :key="scope.workshopId"><el-button v-if="scope.availableAction?.executable" :disabled="navigationLocked || workOrderGenerating" @click="receiveTestWorkshop(scope)">{{ scope.workshopName }}：{{ scope.availableAction.displayName }}</el-button></template></details>
          </div>
          <details class="work-order-technical"><summary>来源、历史工序与技术说明（按需查看）</summary><p>来源排程：{{ workOrderFacts.workOrder.sourceScheduleNo }}；安排{{ workOrderFacts.workOrder.scope.arrangementId }}／自身修订{{ workOrderFacts.workOrder.scope.arrangementRevision }}／编辑{{ workOrderFacts.workOrder.scope.arrangementEditVersion }}。</p><p>保存开始：{{ dateText(workOrderFacts.workOrder.startAt) }}；保存完成：{{ dateText(workOrderFacts.workOrder.completionAt) }}。执行{{ workOrderFacts.workOrder.operationCount }}项；不执行{{ workOrderFacts.workOrder.skippedCount }}项依据仍冻结保留。引用来源排程占用，不新增资源。</p><p v-for="row in workOrderFacts.workOrder.routeSelections.filter(x=>x.decision==='NOT_APPLICABLE')" :key="row.stepId">{{ row.sequence }}．{{ row.operationName }}：{{ row.decisionBasis }}</p></details>
        </template>
        <template v-else-if="workOrderFacts && !workOrderBusy"><p>{{ workOrderFacts.statusLabel }}；当前来源尚无已保存工单。</p><details><summary>工单生成办理（按需查看）</summary><label>办理说明<input v-model="workOrderReason" maxlength="240" /></label><el-button v-for="item in workOrderFacts.availableActions.filter(x=>x.executable)" :key="item.actionCode" :disabled="navigationLocked || workOrderGenerating" @click="generateTestWorkOrder">{{ item.displayName }}</el-button></details></template>
        <p v-if="workOrderMessage" role="status">{{ workOrderMessage }}</p><p v-if="workOrderGenerateError" role="alert">{{ workOrderGenerateError }}</p>
      </section>

      <section v-if="activeArea==='schedule'" class="capacity-review" data-saved-schedule-area><h3>已保存排程</h3>
        <p v-if="savedScheduleBusy" role="status">正在读取当前安排的已保存排程…</p><p v-if="savedScheduleError" role="alert">{{ savedScheduleError }} <el-button @click="loadSavedSchedules">重试读取已保存排程</el-button></p>
        <template v-if="scheduleFacts"><aside data-test-schedule-status><h4>排程状态（与安排状态分别核对）</h4>
            <p v-if="scheduleMessage" role="status">{{ scheduleMessage }}</p><p v-if="scheduleError" role="alert">{{ scheduleError }}</p>
            <p v-if="activeTestSchedule"><strong>{{ activeTestSchedule.scheduleNo }} · {{ activeTestSchedule.statusLabel }}</strong> · {{ activeTestSchedule.purposeLabel }}</p><p v-else><strong>当前安排尚无有效已保存排程。</strong></p>
            <template v-if="activeTestSchedule"><p>安排{{ activeTestSchedule.arrangementId }}／自身修订{{ activeTestSchedule.arrangementRevision }}／编辑序号{{ activeTestSchedule.editVersion }}；{{ activeTestSchedule.currentSourceValid ? '当前来源核验有效' : '来源已变化，禁止继续承接；请取消后重新办理' }}</p><p>已保存开始：{{ dateText(activeTestSchedule.startAt) }}；已保存完成：{{ dateText(activeTestSchedule.completionAt) }}</p><p>当前有效加工占用{{ activeTestSchedule.activeReservationCount }}段；已释放{{ activeTestSchedule.releasedReservationCount }}段。准备／转运不独占，{{ selected.routeWorkloadSummary?.notApplicableSteps }}项不执行不占用；测试排程不得生成正式工单。</p></template>
            <p v-if="datePreview?.savedContextRead">正在回读已保存日期，已重新核验来源；当前资源池有{{ datePreview.currentResourceFacts.activeReservationCount }}段有效占用，不把本排程重复作为新任务排入。</p>
            
            <label>本次操作说明 <input v-model="scheduleReason" aria-label="测试排程操作说明" maxlength="300" /></label>
            <el-button :loading="scheduleBusy" :disabled="!scheduleAction('save-test-schedule')?.executable || navigationLocked" @click="saveTestSchedule">{{ scheduleAction('save-test-schedule')?.displayName || '保存测试排程' }}</el-button>
            <el-button v-if="activeTestSchedule" :loading="scheduleBusy" :disabled="!scheduleAction('cancel-test-schedule')?.executable || navigationLocked" @click="cancelTestSchedule">{{ scheduleAction('cancel-test-schedule')?.displayName }}</el-button>
            <p>保存前重新核验来源、日历及占用；若已变化将拒绝旧预览。重复保存不重复占用。预览、已保存、已取消是不同状态。</p>
            <details v-if="activeTestSchedule"><summary>查看已保存资源占用（{{ activeTestSchedule.activeReservationCount }}段）</summary><div class="schedule-reservations"><p v-for="part in activeTestSchedule.reservations" :key="part.id">顺序{{ part.sequence }}；固定步骤{{ part.stepId }}；工作中心{{ part.workCenterId }}：{{ dateText(part.start) }}～{{ dateText(part.end) }}；{{ part.minutes }}分钟；{{ part.released ? '已释放' : '有效占用' }}</p></div></details>
            <details v-if="scheduleFacts.history.length"><summary>测试排程历史及取消记录</summary><p v-for="item in scheduleFacts.history" :key="item.id">{{ item.scheduleNo }} · {{ item.statusLabel }}；有效{{ item.activeReservationCount }}段／已释放{{ item.releasedReservationCount }}段；开始{{ dateText(item.startAt) }}；完成{{ dateText(item.completionAt) }}</p></details>
          </aside></template></section>
      <section v-if="selected.operationWorkloads && activeArea==='workload'" data-saved-test-workloads aria-label="已保存工序测试作业量">
        <h3 tabindex="-1" ref="workloadHeading">工序作业量</h3>
        <p v-if="selected.routeWorkloadSummary" data-workload-summary>全路线{{ selected.routeWorkloadSummary.totalSteps }}步：{{ selected.routeWorkloadSummary.quantifiedSteps }}步有量／{{ selected.routeWorkloadSummary.notApplicableSteps }}步不执行／{{ selected.routeWorkloadSummary.unknownQuantitySteps }}步未知。{{ selected.operationWorkloads.overallStatusLabel }}</p>
        <p>数量和来源均为服务器保存结果；点击工序行的“查看来源”即可核对，不会重新生成数据。</p>
        <div class="workload-scroll" ref="workloadScroll" @scroll="rememberView" data-full-route-review>
          <ol class="workload-rows"><li v-for="step in selected.steps" :key="step.stepId" :data-review-step="step.stepId" :data-workload-id="savedForStep(step.stepId)?.id">
            <div class="workload-row"><strong>{{ step.sequence }}．{{ step.operationName }}</strong><span>{{ step.decisionLabel }}</span><strong>{{ step.workloadQuantityText ? step.workloadQuantityText+' '+step.workloadUnitLabel : step.workloadStatusLabel }}</strong><el-button size="small" @click="toggleSource(step.stepId)" :aria-expanded="openSources.includes(step.stepId)" :aria-label="`${step.operationName}：${openSources.includes(step.stepId)?'收起来源':'查看来源'}`">{{ openSources.includes(step.stepId)?'收起来源':'查看来源' }}</el-button></div>
            <div v-if="openSources.includes(step.stepId)" class="source-card" :data-source-step="step.stepId"><p><strong>来源说明：</strong>{{ step.workloadSourceLabel || step.basis }}</p><p>执行依据：{{ step.basis }}</p><template v-if="savedForStep(step.stepId)"><p>{{ savedForStep(step.stepId).purposeLabel }}；需求{{ savedForStep(step.stepId).id }}；自身修订{{ savedForStep(step.stepId).arrangementRevision }}／编辑序号{{ savedForStep(step.stepId).editVersion }}；规则版本{{ savedForStep(step.stepId).ruleVersion }}</p><ul><li v-for="input in savedForStep(step.stepId).inputs" :key="input.detailId">{{ input.componentLabel || '冻结部件' }}：{{ input.fieldLabel }} {{ input.quantityText }} {{ savedForStep(step.stepId).unitLabel }}；冻结明细{{ input.detailId }}；生产者{{ input.producerLabel }}</li></ul></template></div>
          </li></ol>
        </div>
      </section>
      <section v-if="activeArea==='capacity'" class="capacity-review" data-capacity-review>
        <h3 ref="capacityHeading" tabindex="-1">产能与日历核对（测试用途，不生成排程）</h3>
        <p v-if="capacityBusy" role="status">正在核验已保存产能、时间及班次日历来源…</p>
        <div v-if="capacityError" role="alert">{{ capacityError }} <el-button @click="loadCapacityReview">重试产能核对</el-button></div>
        <template v-if="capacityReview"><p data-capacity-summary>{{ capacityReview.summary.requiredCount }}步执行；{{ capacityReview.summary.calculatedCount }}步完成无日期产能核对；{{ capacityReview.summary.calendarReadyCount }}步测试日历可读；{{ capacityReview.summary.simulatedCapacityCount }}步使用模拟测试产能。</p><p>{{ capacityReview.statusLabel }}。{{ capacityReview.calendarCoverageLabel }}。</p>
        <div class="capacity-scroll"><article v-for="row in capacityReview.rows" :key="row.stepId" :data-capacity-step="row.stepId"><h4>{{ row.sequence }}．{{ row.operationName }} · {{ row.statusLabel }}</h4>
          <p v-if="row.decision==='REQUIRED'">作业量：{{ row.workloadQuantity }} {{ row.workloadUnitLabel }}；工作中心：{{ row.workCenterName }}</p>
          <template v-if="row.capacity"><p>标准产能：{{ row.capacity.capacityQuantity }} {{ row.capacity.uomLabel }}／{{ row.capacity.timeBasisQuantity }}天；记录{{ row.capacity.id }}，版本／生效来源{{ row.capacity.sourceVersion }}；{{ row.capacity.evidenceLabel }}</p></template>
          <p v-if="row.resultDisplay" class="capacity-time">加工资源天 {{ row.resultDisplay.productionDays }}天 ＋ 准备 {{ row.resultDisplay.preparationDays }}天 ＋ 转运 {{ row.resultDisplay.transferDays }}天 ＝ 合计 {{ row.resultDisplay.durationDays }}天</p>
          <p v-if="row.resultDisplay">准备依据：{{ row.preparationSource }}；转运依据：{{ row.transferSource }}。合计为本步骤资源时间，不是整单交期。</p>
          <p v-if="row.calendar">日历：{{ row.calendar.statusLabel }}<template v-if="row.calendar.source">；{{ row.calendar.source.shiftName }}；每日{{ row.calendar.source.dailyAvailableMinutes }}分钟；{{ row.calendar.source.basisLabel }}</template></p>
          <p v-for="issue in row.issues" :key="issue" class="save-error">{{ issue }}</p>
        </article></div></template>
      </section>
      <section v-if="activeArea==='date'" class="capacity-review" data-date-preview>
        <h3 ref="dateHeading" tabindex="-1">日期排产预览（隔离测试，不预占资源）</h3>
        <label>测试开始时间 <input type="datetime-local" v-model="testStart" aria-label="测试开始时间" @change="clearDatePreview();rememberView()" /> Asia/Shanghai（北京时间）</label>
        <el-button :loading="dateBusy" @click="loadDatePreview">重新计算日期预览</el-button>
        <p>这是本轮补拟测试输入，不是承诺生产日期。刷新后重新核验安排、产能、日历和已有占用；不会生成正式计划或工单。</p>
        <p v-if="dateBusy" role="status">正在读取真实安排、日历及占用，计算日期预览…</p>
        <p v-if="dateError" role="alert">{{ dateError }} <el-button @click="loadDatePreview">重试日期预览</el-button></p>
        <template v-if="datePreview"><p data-date-summary><strong>{{ datePreview.summary.previewedCount }}步日期预览／{{ datePreview.summary.skippedCount }}步跳过／{{ datePreview.summary.unknownCount }}步未知；预计全部完成：{{ dateText(datePreview.completionAt) }}</strong></p>

          <p>测试开始：{{ dateText(datePreview.testStartAt) }}；{{ datePreview.statusLabel }}。</p>
          <p>{{ datePreview.savedContextRead ? '保存前计算时读取' : '本次预览读取' }}{{ datePreview.resourceFacts.activeReservationCount }}条既有未释放占用；本预览区间重叠{{ datePreview.resourceFacts.overlappingHorizonCount }}条。{{ datePreview.resourceFacts.consideredLabel }}。</p>
          <p>测试用途不具备正式业务承接资格；本结果不是已保存排程。所有日期按北京时间展示。</p>
          <div class="capacity-scroll" data-date-rows><article v-for="row in datePreview.rows" :key="row.stepId" :data-date-step="row.stepId"><h4>{{ row.sequence }}．{{ row.operationName }} · {{ row.statusLabel }}</h4>
            <template v-if="row.decision==='REQUIRED'"><p><strong>{{ dateText(row.start) }} → {{ dateText(row.end) }}</strong>；工作中心：{{ row.workCenterName }}</p>
              <p>作业量 {{ row.workloadQuantity }} {{ row.workloadUnitLabel }}；标准产能 {{ row.capacity.capacityQuantity }} {{ row.capacity.uomLabel }}/天；一天={{ row.standardDayMinutes }}净工作分钟；前置顺序：{{ row.predecessorSequences.join('、') || '无' }}</p>
              <ul><li v-for="phase in row.phases" :key="phase.phase">{{ phaseLabel(phase.phase) }}：{{ phase.minutes }}分钟；{{ dateText(phase.start) }} → {{ dateText(phase.end) }}；{{ phase.occupancy==='WORK_TIME_ONLY' ? '仅按工作时间推进，不独占资源' : '占用实际工作中心（仅内存预览）' }}</li></ul>
              <details><summary>查看日期与日历来源</summary><p>{{ row.calendarSource.shiftName }}；{{ row.calendarSource.basisLabel }}；班次{{ row.calendarSource.shiftId }}；来源Hash {{ row.calendarSource.sourceHash }}</p><p>{{ row.basis.businessBasis }}。准备：{{ row.preparationSource }}；转运：{{ row.transferSource }}。</p><p>{{ datePreview.resourceFacts.phaseScopeLabel }}</p><p v-for="phase in row.phases" :key="phase.phase">{{ phaseLabel(phase.phase) }}实际工作段：<span v-for="(part,i) in phase.allocations" :key="i">{{ dateText(part.start) }}～{{ dateText(part.end) }}；</span></p></details>
            </template><p v-else>沿已保存安排不执行，不生成日期资源占用；前置完成时点继续传递。依据：{{ row.decisionBasis }}</p>
          </article></div>
        </template>
      </section>
      <details class="arrangement-edit"><summary>执行选择及安排办理（按需展开）</summary>
      <div class="execution-save-toolbar" data-order-execution-save-toolbar>
        <div class="save-primary-row"><strong role="status" aria-live="polite">{{ saveStatusLabel }}</strong>
          <el-button type="primary" size="large" data-order-execution-save :loading="saving" :disabled="!action('save')?.executable || busy || saving || (!dirty && !retryPending)" @click="saveDraft">{{ retryPending && !saving ? '核对上次保存结果' : (action('save')?.displayName || '保存订单执行安排') }}</el-button>
          <span>{{ dirtyCount }}步有未保存修改；待核定步骤也可以保存草稿。</span></div>
        <label class="save-reason">本次办理说明<el-input ref="saveReasonInput" v-model="reason" aria-label="本次办理说明" :disabled="editingLocked" maxlength="300" show-word-limit placeholder="填写本次办理说明，再点击保存；不是确认或发布" /></label>
        <p v-if="!action('save')?.executable" class="save-error">不能保存：{{ action('save')?.disabledReason || '尚未取得服务端维护权限' }}</p>
        <p v-if="saveMessage" :class="saveStatus==='success' ? 'save-success' : 'save-error'" aria-live="polite">{{ saveMessage }}</p>
        <p v-if="dirty">有未保存修改。离开或浏览器刷新前会提醒；页面内刷新保留输入，请先保存或明确放弃。</p>
        <p v-if="retryPending">上次结果尚未核实，输入保留并暂时锁定；“核对上次保存结果”复用原请求，不重复写入。</p>
        <el-button v-if="dirty && !retryPending" :disabled="busy || saving" @click="discardAndReload">放弃未保存修改并重新读取</el-button>
        <ul v-if="issues.length" class="field-issues" role="alert"><li v-for="issue in issues" :key="`${issue.stepId}-${issue.field}-${issue.message}`" class="field-issue">{{ issue.message }}</li></ul>
      </div>
      <label>适用对象
        <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-object" v-model="objectId" :disabled="navigationLocked" @change="changeObject"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option :value="0" label="整个订单行" /><el-option v-for="obj in selected.objects" :key="obj.id" :value="obj.id" :label="`冻结设计对象${obj.id}（设计项${obj.design_item_id}）`" /></el-select>
      </label>
      <p>下方工序区域可独立滚动，保存按钮位于区域前方。按标准版本真实顺序展示 {{ selected.standardStepCount }} 步。执行但无定量数据仍经过，不能用零值代替未知；订单页面不能增删工序。用户明确依据与补拟测试假设分别保存。</p>
      <div class="execution-steps-scroll" aria-label="订单工序执行编辑区域" tabindex="0"><ol class="execution-step-list">
        <li class="execution-step" :data-step-id="row.stepId" v-for="row in rows" :key="row.stepId">
          <strong>{{ row.sequence }}．{{ row.operationName }}</strong>；工作中心：{{ row.workCenterName }}；前序：{{ row.predecessors.join('、') || '起点' }}
          <div class="decision">
            <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-decision" v-model="row.decision" :disabled="!action('save')?.executable || editingLocked"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option value="REQUIRED" label="执行（经过，定量另行核定）" /><el-option value="NOT_APPLICABLE" label="本单不执行（需明确依据）" /><el-option value="PENDING" label="待核定（依据尚不足）" /></el-select>
            <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-evidence" v-model="row.evidenceClass" :disabled="!action('save')?.executable || editingLocked"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option value="USER_CONFIRMED" label="用户／业务明确依据" /><el-option value="TEST_ASSUMPTION" label="补拟测试假设" /><el-option value="UNRESOLVED" label="依据待核定" /></el-select>
            <el-input v-model="row.basis" :disabled="!action('save')?.executable || editingLocked" type="textarea" :rows="2" placeholder="图纸或业务依据，不从材料空值推断" />
          </div>
          <span v-if="isRowDirty(row)" class="unsaved-badge">此步有未保存修改</span>
          <p><strong>当前作业量：{{ row.workloadQuantityText ? row.workloadQuantityText+' '+row.workloadUnitLabel : row.workloadStatusLabel }}</strong></p><p v-if="row.workloadSourceLabel">数量来源：{{ row.workloadSourceLabel }}</p><p>服务端已保存：{{ row.decisionLabel }}；{{ row.evidenceLabel }}；适用：{{ row.scopeLabel }}；办理人：{{ row.operatorLabel || '尚未办理' }}；审计：{{ row.auditId || '尚无' }}</p><p v-for="issue in issues.filter(item=>item.stepId===row.stepId)" :key="issue.field+issue.message" class="save-error">{{ issue.message }}</p>
        </li>
      </ol></div>
      <details class="workflow-actions"><summary>确认／安排自身修订（与保存草稿分开）</summary><p>保存允许待核定；确认才要求全部必要判断齐备。先保存工序修改，再办理确认。</p><el-button v-for="name in ['confirm','revise']" :key="name" :disabled="!action(name)?.executable || editingLocked || dirtyCount>0 || !reason.trim()" :title="dirtyCount ? '请先保存修改' : action(name)?.disabledReason" @click="writeWorkflow(name)">{{ action(name)?.displayName || '动作状态未取得' }}</el-button><p>{{ action('confirm')?.disabledReason }}</p></details>
      <details><summary>本安排办理记录（标准版本与订单安排分别留痕）</summary><p v-for="audit in selected.auditHistory" :key="audit.id">审计{{ audit.id }}：{{ audit.actor__username }} · {{ audit.reason }} · {{ audit.created_at }}</p></details>
      </details>
    </article>
    </template>
  </section>
</template>
<script setup>
import {computed,ref,watch,nextTick,onMounted,onBeforeUnmount} from 'vue'
import {onBeforeRouteLeave,onBeforeRouteUpdate} from 'vue-router'
import {ElMessageBox} from 'element-plus'
import {pdeApi} from '@/api/pde'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import {getFoundationCanonicalModuleByEntity} from '@/meta/master-data/foundationEntryUnificationRegistry'
import {resolveCurrentIdentity} from '@/meta/runtime/pageTitleManager'
import {assertFoundationRequestIdentity} from '@/meta/runtime/foundationRoutingRead'
import {changedExecutionRows,executionFieldIssues,draftErrorMessage,createExecutionDraftSaver} from '@/meta/runtime/orderExecutionDraft'
const emit=defineEmits(['facts','state','draft-state','capacity-facts','date-facts','schedule-facts','work-order-facts','workshop-task-facts','operation-start-facts'])
function u(r){
  if(r?.success===false || r?.factLoadFacts?.factLoadStatus==='read_failed'){
    const code=r.error?.code || r.factLoadFacts?.errorCode || 'READ_FAILED'
    const message=code==='ECONNABORTED' ? '订单安排读取超时，服务器未在请求时限内返回。请点击下方重试。' : [401,403].includes(r.meta?.status) ? '当前登录身份或权限未通过核验：'+(r.error?.message || '请正常登录后重试') : r.meta?.status>=500 ? `服务器暂时无法完成订单安排读取（HTTP ${r.meta.status}），请重试；原记录未改动。` : code==='ERR_NETWORK' ? '无法连接隔离服务，请检查服务连接后重试。' : (r.error?.message || r.factLoadFacts?.errorMessage || '服务器读取失败，请稍后重试。')
    throw Object.assign(new Error(message),{code,details:r.error?.details,factLoadFacts:r.factLoadFacts})
  }
  return r?.data??r
}
const foundationRoute=getFoundationCanonicalModuleByEntity('routings').routePath
const arrangements=ref([]),choices=ref(null),selected=ref(null),selectedId=ref(null),objectId=ref(0),rows=ref([]),error=ref(''),busy=ref(false)
const ownEntry=ref(false)
const readErrorCode=ref('')
const bomId=ref(null),routeId=ref(null),preview=ref(null),selectReason=ref(''),reason=ref(''),resetExecution=ref(false)
const originalRows=ref([]),saveStatus=ref('idle'),saveMessage=ref(''),retryPending=ref(false),serverIssues=ref([]),saveReasonInput=ref(null)
const capacityHeading=ref(null)
const dateHeading=ref(null),datePreview=ref(null),dateVisible=ref(false),dateBusy=ref(false),dateError=ref(''),testStart=ref('2026-11-09T08:00');let dateOwner=0
const dateText=value=>value?.replace('T',' ').replace('+08:00',' 北京时间')
const phaseLabel=value=>({preparation:'准备',processing:'加工',transfer:'转运'}[value] || value)
const workOrderGenerating=ref(false),workOrderReason=ref('隔离测试工单草稿生成与保存'),workOrderGenerateError=ref(''),workOrderMessage=ref('');let workOrderGenerateKey=''
async function generateTestWorkOrder(){
 if(!workOrderFacts.value?.canGenerate || workOrderGenerating.value || navigationLocked.value)return
 workOrderGenerating.value=true;workOrderGenerateError.value='';const identity=selected.value,source=workOrderFacts.value
 try{if(!workOrderReason.value.trim())throw Error('请填写本次生成说明')
  const data=u(await pdeApi.saveOrderRoutingExecution({action:'generate-test-work-order',arrangementId:identity.id,scheduleId:source.sourceSchedule.id,executionToken:source.executionToken,idempotencyKey:workOrderGenerateKey || (workOrderGenerateKey=`test-wo-${crypto.randomUUID()}`),reason:workOrderReason.value.trim()}));const value=data.testWorkOrderReception;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==selected.value?.id || value.scope.arrangementRevision!==selected.value?.arrangementRevision || value.scope.arrangementEditVersion!==selected.value?.editVersion)throw Error('当前安排已变化，请重新读取工单')
  workOrderFacts.value=value;emit('work-order-facts',data);workOrderMessage.value=data.testWorkOrderOperation.idempotent?'已回读原工单，没有新增明细或占号':'测试草稿工单已提交保存并回读';workOrderGenerateKey=''
 }catch(e){workOrderGenerateError.value=draftErrorMessage(e)}finally{workOrderGenerating.value=false}
}
const workOrderReleaseReason=ref('隔离测试工单下达与车间接收验证');let workOrderReleaseKey=''
async function receiveTestWorkshop(scope){
 const dispatch=workOrderFacts.value?.dispatch
 if(!dispatch || !scope.availableAction?.executable || workOrderGenerating.value)return
 workOrderGenerating.value=true;workOrderGenerateError.value=''
 try{
  const data=u(await pdeApi.saveOrderRoutingExecution({action:scope.availableAction.actionCode,workOrderId:dispatch.workOrderId,workshopId:scope.workshopId,expectedWorkOrderVersion:dispatch.version,expectedWorkOrderSnapshotHash:dispatch.snapshotHash,expectedScopeSnapshotHash:scope.sourceHash,executionToken:scope.availableAction.executionToken,idempotencyKey:`test-receipt-${crypto.randomUUID()}`,reason:workOrderReleaseReason.value.trim()}));const value=data.testWorkOrderDispatch;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.workOrderId!==workOrderFacts.value?.workOrder.id)throw Error('工单已切换，请重新读取')
  workOrderFacts.value={...workOrderFacts.value,dispatch:value};workOrderMessage.value='本车间测试工序已接收保存';emit('work-order-facts',{...data,testWorkOrderReception:workOrderFacts.value})
 }catch(e){workOrderGenerateError.value=draftErrorMessage(e)}finally{workOrderGenerating.value=false}
}
async function releaseTestWorkOrder(){
 const source=workOrderFacts.value,dispatch=source?.dispatch
 if(!dispatch?.availableActions.some(x=>x.executable) || workOrderGenerating.value)return
 workOrderGenerating.value=true;workOrderGenerateError.value=''
 try{
  if(!workOrderReleaseReason.value.trim())throw Error('请填写本次下达说明')
  const data=u(await pdeApi.saveOrderRoutingExecution({action:'release-test-work-order',workOrderId:dispatch.workOrderId,expectedVersion:dispatch.version,executionToken:dispatch.releaseToken,idempotencyKey:workOrderReleaseKey || (workOrderReleaseKey=`test-wo-release-${crypto.randomUUID()}`),reason:workOrderReleaseReason.value.trim()}));const value=data.testWorkOrderReception;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==selected.value?.id || value.sourceSchedule.id!==activeTestSchedule.value?.id)throw Error('当前来源已变化，请重新读取')
  workOrderFacts.value=value;emit('work-order-facts',data);workOrderMessage.value=data.testWorkOrderOperation.idempotent?'已读取原下达结果，没有重复下达':'测试工单已实际下达保存，未派工、开工或报工';workOrderReleaseKey=''
 }catch(e){
  workOrderGenerateError.value=draftErrorMessage(e)+'；正在从服务器核对实际下达结果，不重复提交。'
  await loadWorkOrderReception({restore:true})
  if(workOrderFacts.value?.dispatch?.releasedAt){workOrderGenerateError.value='';workOrderMessage.value='已回读服务器：测试工单下达已提交，未重复下达'}
 }finally{workOrderGenerating.value=false}
}
const workOrderVisible=ref(false),workOrderFacts=ref(null),workOrderBusy=ref(false),workOrderError=ref(''),workOrderHeading=ref(null);let workOrderOwner=0
const startFacts=ref(null),startBusy=ref(false),startWriting=ref(false),startError=ref(''),startMessage=ref(''),startReason=ref('');let startOwner=0;const startKeys=new Map()
async function loadOperationStarts(){
 if(!selected.value)return
 const identity=selected.value,owner=++startOwner;startBusy.value=true;startError.value='';startFacts.value=null;emit('operation-start-facts',null);rememberView()
 try{const data=u(await pdeApi.orderRoutingExecution({action:'test-operation-starts',arrangementId:identity.id}));if(owner!==startOwner)return
  const value=data.testOperationStarts;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==selected.value?.id || value.scope.arrangementRevision!==selected.value?.arrangementRevision || value.scope.arrangementEditVersion!==selected.value?.editVersion)throw Error('开工结果与当前安排版本不一致，请重新读取')
  startFacts.value=value;emit('operation-start-facts',data)
 }catch(e){if(owner===startOwner)startError.value=draftErrorMessage(e)}finally{if(owner===startOwner)startBusy.value=false}
}
async function startOperation(row){
 if(!row.availableAction.executable || startWriting.value || navigationLocked.value)return
 if(startReason.value.trim().length<2){startError.value='请填写2至300字的实际开工说明，测试代办须明确注明。';return}
 const identity=selected.value,owner=startOwner,scopeKey=identity.id+':'+row.taskId+':'+row.sourceSnapshotHash
 if(!startKeys.has(scopeKey))startKeys.set(scopeKey,key())
 startWriting.value=true;startError.value=''
 try{const data=u(await pdeApi.saveOrderRoutingExecution({action:row.availableAction.actionCode,taskId:row.taskId,expectedVersion:row.version,expectedSourceSnapshotHash:row.sourceSnapshotHash,expectedAssignmentHash:row.assignmentHash,reason:startReason.value.trim(),idempotencyKey:startKeys.get(scopeKey)}))
  if(owner!==startOwner || selected.value?.id!==identity.id)return
  assertFoundationRequestIdentity(resolveCurrentIdentity(),data.testOperationStarts?.requestIdentity)
  startFacts.value=data.testOperationStarts;emit('operation-start-facts',data);startMessage.value=data.testOperationStartOperation.idempotent?'已回读原开工记录，未重复开工':'测试开工已保存；尚未报工或完工';startKeys.delete(scopeKey)
 }catch(e){startError.value=draftErrorMessage(e)+'；请重新读取服务器结果，不自动重放开工'}finally{startWriting.value=false}
}
const taskFacts=ref(null),taskBusy=ref(false),taskWriting=ref(false),taskError=ref(''),taskMessage=ref('');let taskOwner=0;const taskKeys=new Map()
async function loadWorkshopTasks(){
 if(!selected.value)return
 const identity=selected.value,owner=++taskOwner;taskBusy.value=true;taskError.value='';taskFacts.value=null;emit('workshop-task-facts',null);rememberView()
 try{const data=u(await pdeApi.orderRoutingExecution({action:'test-workshop-tasks',arrangementId:identity.id}));if(owner!==taskOwner)return
  const value=data.testWorkshopTasks;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==selected.value?.id || value.scope.arrangementRevision!==selected.value?.arrangementRevision || value.scope.arrangementEditVersion!==selected.value?.editVersion)throw Error('派工结果与当前订单安排版本不一致，请重新读取')
  taskFacts.value=value;emit('workshop-task-facts',data)
 }catch(e){if(owner===taskOwner)taskError.value=draftErrorMessage(e)}finally{if(owner===taskOwner)taskBusy.value=false}
}
async function dispatchWorkshopTasks(group){
 if(!group.availableAction.executable || startWriting.value || taskWriting.value || navigationLocked.value)return
 const source=taskFacts.value,identity=selected.value;taskWriting.value=true;taskError.value=''
 const assignments=group.rows.filter(x=>!x.task && x.autoChoice).map(x=>({operationId:x.operationId,...x.autoChoice}))
 const scopeKey=`${source.workOrderId}:${group.workshopId}`
 if(!taskKeys.has(scopeKey))taskKeys.set(scopeKey,`test-task-${crypto.randomUUID()}`)
 try{const data=u(await pdeApi.saveOrderRoutingExecution({action:group.availableAction.actionCode,workOrderId:source.workOrderId,workshopId:group.workshopId,sourceToken:group.sourceToken,assignments,reason:'本轮隔离测试派工：按唯一有效岗位与人员，不开工不报工',idempotencyKey:taskKeys.get(scopeKey)}));const value=data.testWorkshopTasks;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==identity.id || value.scope.arrangementRevision!==identity.arrangementRevision || value.scope.arrangementEditVersion!==identity.editVersion)throw Error('派工后来源已改变，请重新读取')
  taskFacts.value=value;emit('workshop-task-facts',data);taskMessage.value=data.testWorkshopTaskOperation.idempotent?'已回读原任务，无重复派工':'本车间测试任务已保存并派工；尚未开工或报工';taskKeys.delete(scopeKey)
 }catch(e){taskError.value=draftErrorMessage(e)+'；将重新读取服务器保存结果，不重放写入';await loadWorkshopTasks()}finally{taskWriting.value=false}
}
const workOrderReadState=ref('idle'),workOrderEmptyLabel=ref(''),expandedReceiptWorkshop=ref(null)
const savedScheduleBusy=ref(false),savedScheduleError=ref('');let savedScheduleOwner=0
const compactReceiptTime=value=>dateText(value)?.replace(/\.\d+/, '').replace(' 北京时间','')
function toggleReceiptScope(id){expandedReceiptWorkshop.value=expandedReceiptWorkshop.value===id?null:id;rememberView()}
async function loadSavedSchedules(options={}){
 if(!selected.value)return null
 const identity=selected.value,owner=++savedScheduleOwner;savedScheduleBusy.value=true;savedScheduleError.value='';scheduleFacts.value=null;emit('schedule-facts',null)
 try{
  const data=u(await pdeApi.orderRoutingExecution({action:'test-schedules',arrangementId:identity.id}));if(owner!==savedScheduleOwner)return null
  const value=data.orderExecutionTestSchedule;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==selected.value?.id || value.scope.arrangementRevision!==selected.value?.arrangementRevision || value.scope.arrangementEditVersion!==selected.value?.editVersion)throw Error('已保存排程与当前订单安排版本不一致，请重新读取')
  scheduleFacts.value=value;emit('schedule-facts',data);return value
 }catch(e){if(owner===savedScheduleOwner)savedScheduleError.value=draftErrorMessage(e);throw e}
 finally{if(owner===savedScheduleOwner)savedScheduleBusy.value=false}
}
async function loadWorkOrderReception(options={}){
 if(!selected.value)return
 workOrderVisible.value=true;workOrderBusy.value=true;workOrderReadState.value='loading';workOrderEmptyLabel.value='';workOrderError.value='';workOrderFacts.value=null;scheduleFacts.value=null;emit('work-order-facts',null);emit('schedule-facts',null);rememberView();const owner=++workOrderOwner,identity=selected.value,scheduleOwner=++savedScheduleOwner;savedScheduleBusy.value=true;savedScheduleError.value=''
 try{
  const data=u(await pdeApi.orderRoutingExecution({action:'saved-order-work-orders',arrangementId:identity.id}));if(owner!==workOrderOwner || scheduleOwner!==savedScheduleOwner)return
  const saved=data.orderExecutionTestSchedule;assertFoundationRequestIdentity(resolveCurrentIdentity(),saved?.requestIdentity)
  if(saved.scope.arrangementId!==selected.value?.id || saved.scope.arrangementRevision!==selected.value?.arrangementRevision || saved.scope.arrangementEditVersion!==selected.value?.editVersion)throw Error('保存结果与当前订单安排版本不一致，请重新读取')
  scheduleFacts.value=saved;emit('schedule-facts',data)
  const value=data.testWorkOrderReception
  if(!saved.activeSchedule){workOrderReadState.value='empty_valid';workOrderEmptyLabel.value='当前安排没有有效的已保存排程，尚无当前工单承接来源；历史记录请到“已保存排程”查看。';return}
  assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(value.scope.arrangementId!==selected.value?.id || value.scope.arrangementRevision!==selected.value?.arrangementRevision || value.scope.arrangementEditVersion!==selected.value?.editVersion || value.sourceSchedule.id!==saved.activeSchedule.id)throw Error('工单与接收来源已变化，请重新读取')
  workOrderFacts.value=value;workOrderReadState.value='loaded';emit('work-order-facts',data)
  if(!value.dispatch?.scopes.some(x=>x.workshopId===expandedReceiptWorkshop.value))expandedReceiptWorkshop.value=null
 }catch(e){if(owner===workOrderOwner){workOrderReadState.value='read_failed';workOrderError.value=draftErrorMessage(e)}}finally{if(owner===workOrderOwner)workOrderBusy.value=false;if(scheduleOwner===savedScheduleOwner)savedScheduleBusy.value=false}
}
const scheduleFacts=ref(null),scheduleBusy=ref(false),scheduleMessage=ref(''),scheduleError=ref(''),scheduleReason=ref('隔离测试排程保存与占用核验');let scheduleSaveKey=''
const activeTestSchedule=computed(()=>scheduleFacts.value?.activeSchedule)
const scheduleAction=name=>scheduleFacts.value?.availableActions.find(x=>x.actionCode===name)
async function scheduleWrite(action){
 if(!selected.value || !datePreview.value || scheduleBusy.value || navigationLocked.value)return
 scheduleBusy.value=true;scheduleError.value='';scheduleMessage.value='';const identity=selected.value
 try{if(!scheduleReason.value.trim())throw Error('请填写本次测试操作说明')
  const common={action,arrangementId:identity.id,reason:scheduleReason.value.trim(),idempotencyKey:scheduleSaveKey || (scheduleSaveKey=`test-schedule-${crypto.randomUUID()}`)}
  const args=action==='save-test-schedule'?{...common,startAt:datePreview.value.testStartAt,admissionToken:datePreview.value.admissionToken}:{...common,scheduleId:activeTestSchedule.value.id,expectedVersion:activeTestSchedule.value.version}
  const data=u(await pdeApi.saveOrderRoutingExecution(args));const facts=data.orderExecutionTestSchedule;assertFoundationRequestIdentity(resolveCurrentIdentity(),facts?.requestIdentity)
  if(facts.scope.arrangementId!==selected.value?.id || facts.scope.arrangementRevision!==selected.value?.arrangementRevision || facts.scope.arrangementEditVersion!==selected.value?.editVersion)throw Error('安排或版本已切换，请重新读取排程')
  scheduleFacts.value=facts;emit('schedule-facts',data);scheduleMessage.value=data.testScheduleOperation.idempotent?'已回读原办理结果，没有新增排程或占用':action==='save-test-schedule'?'测试排程已提交保存并回读':'测试排程已取消，占用已释放，历史保留';scheduleSaveKey=''
 }catch(e){scheduleError.value=draftErrorMessage(e)}finally{scheduleBusy.value=false}
}
const saveTestSchedule=()=>scheduleWrite('save-test-schedule')
const cancelTestSchedule=()=>scheduleWrite('cancel-test-schedule')
function clearDatePreview(){startOwner++;startBusy.value=false;startFacts.value=null;startError.value='';startMessage.value='';emit('operation-start-facts',null);taskOwner++;taskBusy.value=false;taskFacts.value=null;taskError.value='';taskMessage.value='';emit('workshop-task-facts',null);savedScheduleOwner++;savedScheduleBusy.value=false;savedScheduleError.value='';workOrderReadState.value='idle';workOrderOwner++;workOrderFacts.value=null;workOrderBusy.value=false;workOrderError.value='';emit('work-order-facts',null);scheduleFacts.value=null;emit('schedule-facts',null);dateOwner++;dateBusy.value=false;datePreview.value=null;dateError.value='';emit('date-facts',null)}
async function loadDatePreview(options={}){
 if(!selected.value || dateBusy.value)return
 dateVisible.value=true;dateBusy.value=true;dateError.value='';datePreview.value=null;emit('date-facts',null);rememberView()
 const owner=++dateOwner,identity=selected.value,start=testStart.value
 await nextTick();if(!options.restore){dateHeading.value?.focus();dateHeading.value?.scrollIntoView({block:'start'});rememberView()}
 try{const data=u(await pdeApi.orderRoutingExecution({action:'date-preview',arrangementId:identity.id,startAt:start+':00+08:00'}));if(owner!==dateOwner || start!==testStart.value)return
  const value=data.orderExecutionDatePreview;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(!value || value.scope.arrangementId!==identity.id || value.scope.arrangementRevision!==identity.arrangementRevision || value.scope.arrangementEditVersion!==identity.editVersion)throw Error('日期预览的安排版本已变化，请重新读取')
  datePreview.value=value;scheduleFacts.value=value.scheduleFacts;emit('schedule-facts',data);emit('date-facts',data);if(workOrderVisible.value)void loadWorkOrderReception({restore:true})
 }catch(e){if(owner===dateOwner)dateError.value=draftErrorMessage(e)}finally{if(owner===dateOwner)dateBusy.value=false}
}
const capacityReview=ref(null),capacityVisible=ref(false),capacityBusy=ref(false),capacityError=ref('');let capacityOwner=0
const panelRoot=ref(null)
const businessAreas=[{key:'workload',label:'工序作业量'},{key:'capacity',label:'产能与日历'},{key:'date',label:'日期排产预览'},{key:'schedule',label:'已保存排程'},{key:'workOrder',label:'工单与车间接收'},{key:'dispatch',label:'车间派工'},{key:'taskStart',label:'任务开工'}]
const activeArea=ref('workload'),activeAreaLabel=computed(()=>businessAreas.find(x=>x.key===activeArea.value)?.label)
async function selectBusinessArea(name,options={}){
 if(!businessAreas.some(x=>x.key===name) || !selected.value)return
 activeArea.value=name;workloadOpen.value=name==='workload';capacityVisible.value=name==='capacity';dateVisible.value=name==='date';workOrderVisible.value=name==='workOrder';rememberView()
 try{
  if(name==='capacity')await loadCapacityReview({restore:true})
  else if(name==='date')await loadDatePreview({restore:true})
  else if(name==='schedule')await loadSavedSchedules({restore:true})
  else if(name==='workOrder')await loadWorkOrderReception({restore:true})
  else if(name==='dispatch')await loadWorkshopTasks()
  else if(name==='taskStart')await loadOperationStarts()
 }catch{} // Each loader exposes its own explicit error and retry.
}

const readState=ref('loading'),restoreNotice=ref(''),workloadOpen=ref(true),openSources=ref([]),workloadScroll=ref(null),workloadHeading=ref(null)
const currentArrangements=computed(()=>arrangements.value.filter(a=>a.isCurrent))
const isCurrentSelection=computed(()=>arrangements.value.find(a=>a.id===selectedId.value)?.isCurrent===true)
const viewKey=()=>{const i=resolveCurrentIdentity();return `pce-order-arrangement-view:${i.companyId}:${i.userId || i.username}`}
let restoredView=null
try{restoredView=JSON.parse(sessionStorage.getItem(viewKey()) || 'null')}catch{}
if(restoredView){activeArea.value=businessAreas.some(x=>x.key===restoredView.activeArea)?restoredView.activeArea:restoredView.workOrderOpen?'workOrder':'workload';expandedReceiptWorkshop.value=restoredView.expandedReceiptWorkshop || null;workOrderVisible.value=Boolean(restoredView.workOrderOpen);dateVisible.value=Boolean(restoredView.dateOpen);testStart.value=restoredView.testStart || testStart.value;capacityVisible.value=Boolean(restoredView.capacityOpen);selectedId.value=restoredView.arrangementId;objectId.value=restoredView.objectId || 0;workloadOpen.value=restoredView.workloadOpen!==false;openSources.value=restoredView.openSources || []}
const signature=value=>JSON.stringify(['v2',value.id,value.arrangementRevision,value.editVersion,value.operationWorkloads?.rows.map(x=>[x.id,x.current,x.ruleVersion])])
function rememberView(){if(!selected.value)return;try{sessionStorage.setItem(viewKey(),JSON.stringify({activeArea:activeArea.value,expandedReceiptWorkshop:expandedReceiptWorkshop.value,arrangementId:selected.value.id,objectId:objectId.value,workloadOpen:workloadOpen.value,capacityOpen:capacityVisible.value,dateOpen:dateVisible.value,workOrderOpen:workOrderVisible.value,testStart:testStart.value,openSources:openSources.value,scrollTop:workloadScroll.value?.scrollTop || 0,pageY:window.scrollY,signature:signature(selected.value)}))}catch{}}
async function loadCapacityReview(options={}){
 if(!selected.value || capacityBusy.value)return
 capacityVisible.value=true;capacityBusy.value=true;capacityError.value='';capacityReview.value=null;emit('capacity-facts',null);rememberView()
 const owner=++capacityOwner,identity=selected.value
 await nextTick();if(!options.restore){capacityHeading.value?.focus();capacityHeading.value?.scrollIntoView({block:'start'});rememberView()}
 try{const data=u(await pdeApi.orderRoutingExecution({action:'capacity',arrangementId:identity.id}));if(owner!==capacityOwner)return
  const value=data.orderExecutionCapacity;assertFoundationRequestIdentity(resolveCurrentIdentity(),value?.requestIdentity)
  if(!value || value.scope.arrangementId!==identity.id || value.scope.arrangementRevision!==identity.arrangementRevision || value.scope.arrangementEditVersion!==identity.editVersion)throw Error('产能核对的安排版本已变化，请重新读取')
  capacityReview.value=value;emit('capacity-facts',data)
 }catch(e){if(owner===capacityOwner)capacityError.value=draftErrorMessage(e)}finally{if(owner===capacityOwner)capacityBusy.value=false}
}
function savedForStep(id){return selected.value?.operationWorkloads?.rows.find(x=>x.stepId===id && x.current) || selected.value?.operationWorkloads?.rows.find(x=>x.stepId===id)}
async function toggleSource(id){openSources.value=openSources.value.includes(id)?openSources.value.filter(x=>x!==id):[...openSources.value,id];await nextTick();if(openSources.value.includes(id))workloadScroll.value?.querySelector(`[data-source-step="${id}"]`)?.scrollIntoView({block:'nearest'});rememberView()}
async function showWorkloads(){return selectBusinessArea('workload')}
function openArrangement(id){selectedId.value=id;return changeArrangement()}
let loadPromise=null

let generation=0,loadGeneration=0,loadedObjectId=0
const action=name=>selected.value?.availableActions?.find(a=>a.action===name)
const key=()=>`order-execution-${crypto.randomUUID()}`
const changed=computed(()=>changedExecutionRows(rows.value,originalRows.value))
const dirtyCount=computed(()=>changed.value.length)
const dirty=computed(()=>dirtyCount.value>0 || Boolean(reason.value.trim()))
const saving=computed(()=>['saving','verifying'].includes(saveStatus.value))
const editingLocked=computed(()=>busy.value || saving.value || retryPending.value || scheduleBusy.value || workOrderGenerating.value || startWriting.value || taskWriting.value)
const navigationLocked=computed(()=>editingLocked.value || dirty.value)
const issues=computed(()=>[...new Map([...executionFieldIssues(rows.value,originalRows.value),...serverIssues.value].map(x=>[`${x.stepId}:${x.field}:${x.message}`,x])).values()])
const saveStatusLabel=computed(()=>({saving:'保存中，请等待…',verifying:'已提交，正在核对服务端结果…',success:dirty.value?'有未保存修改':'保存成功，已回读',unverified:'保存结果待核对',error:'保存未完成，输入保留'}[saveStatus.value] || (dirty.value?'有未保存修改':'当前没有未保存修改')))
const isRowDirty=row=>changed.value.some(item=>item.stepId===row.stepId)
function applyLoaded(data){
  const value=data.orderExecutionArrangements?.[0]
  if(!value)throw Error('服务端未返回所选安排，不使用缓存补齐。')
  assertFoundationRequestIdentity(resolveCurrentIdentity(),value.requestIdentity)
  clearDatePreview();capacityOwner++;capacityBusy.value=false;capacityReview.value=null;capacityError.value='';emit('capacity-facts',null)
  selected.value=value;selectedId.value=value.id;bomId.value=value.bomVersionId;routeId.value=value.routingVersionId;rows.value=value.steps.map(row=>({...row}));originalRows.value=value.steps.map(row=>({...row}));loadedObjectId=objectId.value
  arrangements.value=arrangements.value.map(a=>a.id===value.id?{...a,...value}:a)
  if(restoredView?.signature?.startsWith('["v2"') && restoredView.arrangementId===value.id && restoredView.signature!==signature(value)){openSources.value=[];expandedReceiptWorkshop.value=null;restoreNotice.value='安排版本或来源记录已变化，已重新核验；请重新查看来源。'}
  readState.value='loaded'
  nextTick(()=>{if(workloadScroll.value && restoredView?.arrangementId===value.id)workloadScroll.value.scrollTop=restoredView.scrollTop || 0;panelRoot.value?.scrollIntoView({block:'start'});rememberView();restoredView=null;void selectBusinessArea(activeArea.value,{restore:true})})
  emit('facts',data);emit('state','loaded')
}
async function readSelected(){
  clearDatePreview()
  const current=++generation;error.value='';readState.value='loading';emit('state','loading')
  try{const data=u(await pdeApi.orderRoutingExecution({arrangementId:selectedId.value,...(objectId.value?{baselineItemId:objectId.value}:{})}));if(current!==generation)return;applyLoaded(data)}
  catch(e){if(current===generation){selected.value=null;rows.value=[];originalRows.value=[];error.value=draftErrorMessage(e);readState.value='read_failed';emit('facts',null);emit('state','read_failed')}}
}
function changeArrangement(){if(dirty.value || retryPending.value){selectedId.value=selected.value?.id;error.value='请先保存或明确放弃未保存修改，再切换安排。';return}objectId.value=0;expandedReceiptWorkshop.value=null;workOrderVisible.value=false;dateVisible.value=false;clearDatePreview();capacityVisible.value=false;capacityOwner++;capacityReview.value=null;openSources.value=[];restoreNotice.value='';return readSelected()}
function changeObject(){if(dirty.value || retryPending.value){objectId.value=loadedObjectId;error.value='请先保存或明确放弃修改，再切换适用对象。';return}return readSelected()}
async function load(){
  if(loadPromise)return loadPromise
  loadPromise=loadOnce().finally(()=>{loadPromise=null});return loadPromise
}
async function loadOnce(){
  if(selected.value){rememberView();try{restoredView=JSON.parse(sessionStorage.getItem(viewKey()) || 'null')}catch{}}
  if(dirty.value || retryPending.value){error.value='订单安排有未保存修改或未核实请求，未重新读取；输入仍保留，请先保存或明确放弃。';return false}
  const owner=++loadGeneration;const current=++generation;busy.value=true;readState.value='loading';error.value='';readErrorCode.value='';selected.value=null;rows.value=[];originalRows.value=[];choices.value=null;arrangements.value=[];preview.value=null;emit('facts',null);emit('state','loading')
  try{const response=await pdeApi.orderRoutingExecution({action:'index'});const entryData=u(response)
    if(entryData.readScope==='qualified_assignee_only'){
      if(current!==generation)return
      ownEntry.value=true;assertFoundationRequestIdentity(resolveCurrentIdentity(),entryData.requestIdentity);arrangements.value=entryData.orderExecutionArrangements
      selectedId.value=arrangements.value.some(x=>x.id===selectedId.value)?selectedId.value:arrangements.value[0]?.id
      selected.value=arrangements.value.find(x=>x.id===selectedId.value);readState.value='loaded';activeArea.value='taskStart'
      emit('facts',entryData);await loadOperationStarts();emit('state','loaded');return
    }
    ownEntry.value=false;const options=await pdeApi.orderRoutingExecution({action:'choices'});if(current!==generation)return
    const data=u(response),optionData=u(options);assertFoundationRequestIdentity(resolveCurrentIdentity(),data.requestIdentity);assertFoundationRequestIdentity(resolveCurrentIdentity(),optionData.requestIdentity)
    if(!Array.isArray(data.orderExecutionArrangements))throw Error('订单安排接口响应缺少记录列表，无法确认当前安排；请重试，若持续失败请联系维护人员。')
    arrangements.value=data.orderExecutionArrangements;choices.value=optionData
    if(arrangements.value.length){selectedId.value=arrangements.value.some(a=>a.id===selectedId.value)?selectedId.value:(arrangements.value.find(a=>a.isCurrent) || arrangements.value[0]).id;await readSelected()}else{readState.value='empty_valid';emit('facts',data);emit('state','loaded')}
  }catch(e){if(current===generation){readErrorCode.value=e.code||'';error.value=draftErrorMessage(e);readState.value='read_failed';emit('facts',null);emit('state','read_failed')}}finally{if(owner===loadGeneration)busy.value=false}
}
const saver=createExecutionDraftSaver({post:async payload=>u(await pdeApi.saveOrderRoutingExecution(payload)),read:async(id,object)=>{const envelope=u(await pdeApi.orderRoutingExecution({arrangementId:id,...(object?{baselineItemId:object}:{})}));return {envelope,arrangement:envelope.orderExecutionArrangements?.[0]}},makeKey:key,assertIdentity:actual=>assertFoundationRequestIdentity(resolveCurrentIdentity(),actual),onState:state=>{saveStatus.value=state.status;retryPending.value=state.pending;saveMessage.value=state.message||'';serverIssues.value=state.fieldErrors||[]}})
async function saveDraft(){
  if(!selected.value || !action('save')?.executable || busy.value || saving.value)return
  error.value=''
  const outcome=await saver.save({arrangement:selected.value,rows:rows.value,originalRows:originalRows.value,objectId:objectId.value||null,reason:reason.value})
  if(outcome.ok){applyLoaded(outcome.loaded.envelope);reason.value='';saveMessage.value=outcome.message}
  else if(!reason.value.trim() && !outcome.fieldErrors?.length)saveReasonInput.value?.focus()
}
async function discardAndReload(){
  if(retryPending.value){error.value='上次结果尚未核实，请先核对保存请求。';return}
  try{await ElMessageBox.confirm('放弃当前未保存输入并从服务端重新读取？此前已保存记录不变。','有未保存修改',{confirmButtonText:'放弃并重新读取',cancelButtonText:'保留输入',type:'warning'})}catch{return}
  rows.value=originalRows.value.map(row=>({...row}));reason.value='';serverIssues.value=[];saveMessage.value='';saveStatus.value='idle';await load()
}
async function previewStandard(){try{error.value='';preview.value=u(await pdeApi.orderRoutingExecution({action:'preview',bomVersionId:bomId.value,routingVersionId:routeId.value}))}catch(e){preview.value=null;error.value=draftErrorMessage(e)}}
async function selectStandard(){if(navigationLocked.value)return;busy.value=true;try{const existing=arrangements.value.find(a=>a.bomVersionId===bomId.value);const result=u(await pdeApi.saveOrderRoutingExecution({action:'select',bomVersionId:bomId.value,routingVersionId:routeId.value,referenceHash:preview.value.referenceHash,reason:selectReason.value,idempotencyKey:key(),expectedEditVersion:existing?.editVersion,resetExecution:resetExecution.value}));selectedId.value=result.id;objectId.value=0;preview.value=null;resetExecution.value=false;await load()}catch(e){error.value=draftErrorMessage(e)}finally{busy.value=false}}
async function writeWorkflow(name){if(editingLocked.value || dirtyCount.value)return;busy.value=true;try{await pdeApi.saveOrderRoutingExecution({action:name,arrangementId:selected.value.id,reason:reason.value,idempotencyKey:key(),expectedEditVersion:selected.value.editVersion});reason.value='';await load()}catch(e){error.value=draftErrorMessage(e)}finally{busy.value=false}}
function beforeUnload(event){rememberView();if(dirty.value || retryPending.value){event.preventDefault();event.returnValue='';return ''}}
async function permitLeave(){if(!dirty.value && !retryPending.value)return true;try{await ElMessageBox.confirm('当前有未保存修改或未核实请求。离开会丢失本地输入，是否仍要离开？','尚未完成保存',{confirmButtonText:'仍然离开',cancelButtonText:'返回保存',type:'warning'});return true}catch{return false}}
onBeforeRouteLeave(permitLeave);onBeforeRouteUpdate(permitLeave)
onMounted(()=>{window.addEventListener('beforeunload',beforeUnload);void load()})
onBeforeUnmount(()=>{rememberView();startOwner++;taskOwner++;savedScheduleOwner++;workOrderOwner++;dateOwner++;capacityOwner++;generation++;loadGeneration++;window.removeEventListener('beforeunload',beforeUnload)})
watch([dirty,dirtyCount,saveStatus,retryPending],()=>emit('draft-state',{hasUnsavedChanges:dirty.value,changedStepCount:dirtyCount.value,saveStatus:saveStatus.value,unverifiedRequest:retryPending.value}),{immediate:true})
watch(()=>JSON.stringify(rows.value.map(row=>[row.stepId,row.decision,row.evidenceClass,row.basis])),()=>{if(!saving.value && !retryPending.value)serverIssues.value=[]})
watch(dirty,value=>{if(value && saveStatus.value==='success'){saveStatus.value='idle';saveMessage.value=''}})
defineExpose({load,isOwnEntry:()=>ownEntry.value})
</script>
<style scoped>
.task-route-scroll{max-height:65vh;overflow:auto;border:1px solid #d7e2ed;padding:8px}.task-route-scroll article{margin-bottom:14px}.task-operation-cards{list-style:none;margin:0;padding:0}.task-operation-cards>li{padding:10px 6px;border-bottom:1px solid #d7e2ed}.task-operation-cards p{margin:5px 0;font-size:12px;line-height:1.5;overflow-wrap:anywhere}

.order-execution-panel{padding:12px!important}.order-execution-panel>h2{font-size:18px;margin:6px 0}.order-execution-panel>.task-hint{font-size:12px;line-height:1.45;padding:6px;margin:6px 0}.arrangement-toolbar>label{display:grid!important;gap:4px!important;width:100%;min-width:0;font-size:12px}.arrangement-toolbar .order-select-arrangement{width:100%!important}.order-business-entries .el-button{font-size:12px;padding:6px 8px!important;height:28px}.arrangement-help{font-size:12px;margin:6px 0!important}.arrangement-identity{font-size:12px;line-height:1.4;padding:8px!important}.arrangement-identity h3{font-size:15px!important}.arrangement-identity .separate-business-statuses{font-size:12px;gap:4px 10px}.work-order-business-view{padding:9px!important;font-size:12px}.work-order-business-view h3{font-size:16px;margin:4px 0!important}.work-order-business-view h4{font-size:14px;margin:4px 0!important}.work-order-summary p{font-size:12px;line-height:1.4!important;margin:6px 0!important}.work-order-summary :deep(.pce-business-status){white-space:normal}.receipt-detail-table{font-size:12px!important}.receipt-detail-table th,.receipt-detail-table td{padding:7px 5px!important}.receipt-detail-table :deep(.el-button){font-size:12px;padding:5px 7px}.receipt-totals{padding:6px!important}

.order-business-entries{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.order-business-entries .el-button{margin:0;padding:8px 10px}.work-order-business-view{border:1px solid #b5cce5;border-radius:8px;padding:12px;background:#fff}.work-order-business-view h3,.work-order-business-view h4{margin:6px 0}.work-order-summary p{margin:8px 0;line-height:1.55}.receipt-totals{padding:8px;background:#edf8f1}.receipt-detail-table{width:100%;border-collapse:collapse;font-size:13px;table-layout:fixed}.receipt-detail-table caption{text-align:left;font-weight:600;margin:8px 0}.receipt-detail-table th,.receipt-detail-table td{padding:9px 7px;border:1px solid #d4dfe9;text-align:left;vertical-align:top;overflow-wrap:anywhere}.receipt-detail-table th{background:#eef4fb}.receipt-detail-table th:nth-child(1){width:29%}.receipt-detail-table th:nth-child(2){width:43%}.receipt-detail-table th:nth-child(3){width:28%}.receipt-detail-table time{display:block;margin-top:4px;font-size:12px;white-space:normal}.receipt-detail-table :deep(.pce-business-status){white-space:normal;font-size:12px}.receipt-detail-table ol{max-height:320px;overflow:auto;padding-left:20px}.receipt-detail-table li{margin:8px 0}.separate-business-statuses{display:flex;gap:5px 16px;flex-wrap:wrap;font-size:13px}.work-order-technical,.business-boundary{font-size:12px;color:#52657d;margin:10px 0}.arrangement-toolbar{margin:8px 0!important}.arrangement-identity{padding:10px!important;margin:8px 0!important}.arrangement-identity h3{font-size:18px!important}.arrangement-identity p{margin:5px 0}.history-arrangements{font-size:12px;margin:4px 0!important}

.schedule-reservations{max-height:350px;overflow:auto} [data-test-schedule-status]{padding:12px;border:1px solid #8bbba5;background:#f4fbf7;margin:12px 0} [data-test-schedule-status] input{max-width:100%;width:25em} .capacity-review{margin:16px 0;padding:14px;border:1px solid #b6cfe8;border-radius:8px;background:#f8fbff}.capacity-scroll{max-height:65vh;overflow:auto}.capacity-scroll article{padding:12px 0;border-bottom:1px solid #dce4ed}.capacity-scroll p{line-height:1.7;overflow-wrap:anywhere}.capacity-time{font-weight:700;color:#204d78}

.arrangement-identity{background:#eef5ff;border:1px solid #aac7ed;border-radius:10px;padding:16px;margin:14px 0}.arrangement-identity h3{font-size:22px;margin:0 0 8px}.arrangement-toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:16px 0}.task-hint,.restore-notice{padding:10px;background:#f2f7fc}.arrangement-help,.history-arrangements,.arrangement-edit{margin:12px 0}.workload-scroll{max-height:65vh;overflow:auto;border:1px solid #dce4ed;border-radius:8px}.workload-rows{list-style:none;padding:0;margin:0}.workload-rows>li{padding:12px;border-bottom:1px solid #dce4ed}.workload-row{display:grid;grid-template-columns:minmax(140px,1.2fr) minmax(110px,1fr) minmax(130px,1fr) auto;gap:10px;align-items:center}.workload-row>span{font-size:13px;color:#52657d}.source-card{padding:12px;background:#f1f6fc;border-left:3px solid #5286bd;margin-top:10px;overflow-wrap:anywhere}.source-card p{margin:6px 0}.source-card li{margin:6px 0}@media(max-width:760px){.workload-row{grid-template-columns:1fr auto}.workload-row>span{grid-column:1}.workload-row>.el-button{grid-column:2;grid-row:1/3}}

.full-route-review-list{max-height:32rem;overflow-y:auto;border:1px solid #dce4ed;border-radius:8px;padding:8px 12px 8px 32px;line-height:1.6}.full-route-review-list li{padding:8px 0;border-bottom:1px solid #e5eaf0;overflow-wrap:anywhere}.full-route-review-list p{margin:4px 0;color:#52657d;font-size:13px}.saved-workload-details{margin:12px 0}

.selection,.decision{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:14px 0}.order-execution-panel label{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.execution-save-toolbar{position:sticky;top:64px;z-index:12;border:1px solid #a7c5ed;border-radius:10px;background:#f8fbff;padding:14px;margin:16px 0;box-shadow:0 3px 12px #203b5c18}.save-primary-row{display:flex;align-items:center;flex-wrap:wrap;gap:14px}.save-reason{margin-top:12px}.save-reason :deep(.el-input){flex:1;min-width:240px}.execution-save-toolbar p{margin:8px 0}.execution-steps-scroll{max-height:65vh;overflow-y:auto;border:1px solid #dce4ed;border-radius:8px;padding:0 16px;overscroll-behavior:contain}.execution-step-list{margin:0;padding-left:24px}.execution-step{padding:16px 0;border-bottom:1px solid #dce4ed}.unsaved-badge{margin-left:12px;color:#8b4b00;font-weight:700}.save-error,.field-issue{color:#a52020}.save-success{color:#146c3b}.field-issues{max-height:144px;overflow-y:auto;margin:8px 0;padding-left:20px}.field-issue{padding:4px 0;line-height:1.5}.workflow-actions{margin:16px 0}
.order-execution-panel .order-select{flex:0 1 auto;min-width:0;max-width:100%;vertical-align:middle}.order-select-bom{width:17rem}.order-select-routing{width:23rem}.order-select-arrangement{width:28rem}.order-select-object{width:18rem}.order-select-decision{width:16rem}.order-select-evidence{width:12rem}
.order-execution-panel .selection{align-items:end;gap:12px}.order-execution-panel .selection>label{display:grid;gap:6px;min-width:0}.source-identity-note{font-size:13px;color:#52657d}.order-select-label{display:block;width:100%;line-height:24px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.order-execution-panel :deep(.order-select .el-select__wrapper){height:32px;min-height:32px;padding:4px 10px;box-sizing:border-box;align-items:center;line-height:24px}.order-execution-panel :deep(.order-select .el-select__selection){height:24px;min-width:0;flex-wrap:nowrap;align-items:center}.order-execution-panel :deep(.order-select .el-select__placeholder){line-height:24px;white-space:nowrap}.order-execution-panel :deep(.order-select .el-select__suffix){height:24px;display:flex;align-items:center}.order-execution-panel :deep(.order-select .el-select__caret){width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center}
:global(.order-execution-select-options .el-select-dropdown__list){max-width:min(34rem,calc(100vw - 32px))}:global(.order-execution-select-options .el-select-dropdown__item){min-height:32px;height:auto;box-sizing:border-box;line-height:20px;padding:6px 12px;display:flex;align-items:center;white-space:normal;overflow-wrap:anywhere;word-break:normal}:global(.order-execution-select-options .el-select-dropdown__item span){white-space:normal;line-height:20px}
@media(max-width:760px){.order-execution-panel .selection{display:grid;grid-template-columns:minmax(0,1fr)}.order-execution-panel .selection>label,.order-execution-panel .selection .order-select{width:100%}}
@media(max-width:720px){.execution-save-toolbar{top:8px}.save-primary-row .el-button{width:100%;margin:0}.order-execution-panel :deep(.el-select){max-width:100%}.execution-steps-scroll{max-height:60vh}}
</style>
