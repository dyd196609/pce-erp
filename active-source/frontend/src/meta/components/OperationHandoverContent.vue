<template>
  <div class="handover-content" data-page="production-operation-handover" data-fact-source="server" :data-load-status="state.readState" :data-visible-read-ms="visibleReadMs" :data-read-cycle="readCycle">
    <MesUnifiedPageGuide title="工序交接" purpose="按实际产出及保管职责核对交出、实收与已有记录。" people="本人交出责任人及指定接收人" :return-location="guideListLocation" :before-list-return="prepareListReturn" />
    <nav class="view-navigation" aria-label="交接查看导航">
      <h2>{{ detailView ? '交接详情' : '交接列表' }}</h2>
      <button v-if="detailView" type="button" :disabled="busy || locked" @click="returnToList">返回交接列表</button>
      <router-link v-if="route.query.from === 'own-tasks'" :to="{path:'/planning/operation-reports',query:route.query.workOrderId ? {workOrderId:route.query.workOrderId} : {}}">返回本人任务</router-link>
      <button type="button" class="secondary-button" :aria-expanded="learningOpen" aria-controls="handover-learning" @click="learningOpen = !learningOpen; learning.write(learningOpen)">操作说明{{ learningOpen ? ' · 关闭' : '' }}</button>
    </nav>
    <p v-if="state.readState === 'loading'" role="status">{{ detailView ? '交接详情待核，正在读取并核验交接、产出、投入和保管依据。' : '正在读取交接记录，请稍候。' }}</p>
    <p v-if="state.error" role="alert" class="warning">{{ userMessage(state.error) }}</p>
    <p v-if="!detailView && state.readState === 'loaded' && state.factLoadFacts?.factLoadStatus === 'empty_valid'" role="status" data-handover-direction-empty>当前方向没有可查看的交接单</p>
    <div v-if="!detailView" class="list-locators">
      <label>交接读取方向<select aria-label="列表读取方向" :value="state.params.direction || 'outgoing'" :disabled="busy || locked" @change="selectDirection($event.target.value)"><option value="incoming">本任务接收的上游交接</option><option value="outgoing">本任务交出的下游交接</option></select></label>
      <label>交接编号
        <select aria-label="选单交接编号" :value="numberSearch.selection" :disabled="busy || locked || !numberOptions.length" @change="chooseNumber($event.target.value)">
          <option value="">请选择本方向交接单</option>
          <option v-for="row in numberOptions" :key="row.id" :value="String(row.id)">{{ row.displayNo }} · {{ row.workOrderNo }}</option>
        </select>
      </label>
      <label>手输交接编号<input aria-label="列表交接编号" :value="numberSearch.value" :disabled="busy || locked" placeholder="业务编号或原交接编号" @input="editNumber($event.target.value)" @keyup.enter="lookupNumber" /></label>
      <button type="button" :disabled="busy || locked || !numberSearch.value.trim()" @click="lookupNumber">按编号查看</button>
    </div>
    <section v-show="detailView" class="card" aria-label="工序交接事实与定位">

      <div class="object-heading" data-handover-object>
        <div><span class="eyebrow">{{ selectedHeader ? '正在查看本张交接记录' : selectedTask ? '当前来源任务' : '请选择交接对象' }}</span><h2>{{ selectedHeader?.businessNo || selectedHeader?.no || selectedTask?.taskNo || '工序交接' }}</h2></div>
        <PceBusinessStatus v-if="selectedHeader" :status-label="selectedHeader.receiptStateLabel || selectedHeader.statusLabel" />
      </div>
      <dl v-if="selectedHeader || selectedTask" class="facts object-facts">
        <div><dt>来源任务／工序</dt><dd>{{ selectedHeader?.sourceTaskNo || selectedTask?.taskNo || sourceTaskOption?.taskNo || '本次服务未提供任务编号' }} · {{ selectedHeader?.sourceOperationName || selectedTask?.operationName || sourceTaskOption?.operationName || '本次服务未提供工序名称' }}</dd></div>
        <div><dt>{{ selectedHeader ? '历史工作中心去向（当时记录）' : '来源工作中心' }}</dt><dd>{{ selectedHeader?.sourceWorkCenterName || selectedTask?.workCenterName || '待选择' }} → {{ selectedHeader?.targetWorkCenterName || '尚未选择交接单' }}</dd></div>
        <div v-if="selectedHeader?.workOrderNo || selectedTask?.workOrderNo || sourceTaskOption?.workOrderNo"><dt>原工单</dt><dd>{{ selectedHeader?.workOrderNo || selectedTask?.workOrderNo || sourceTaskOption?.workOrderNo }}</dd></div>
        <div v-if="selectedHeader"><dt>去处及保管标识</dt><dd>{{ selectedHeader.destinationLabel || selectedHeader.destinationKindLabel }}{{ selectedHeader.destinationReference ? ' · '+selectedHeader.destinationReference : '' }}</dd></div>
      </dl>
      <dl v-if="selectedHeader" class="facts" data-handover-history-summary>
        <div><dt>本张历史交接（当时记录）</dt><dd>{{ selectedHeader.directionDisplay.historical.processLabel }}</dd></div>
        <div><dt>当前正式工艺</dt><dd data-current-process-direction>{{ selectedHeader.directionDisplay.current.processLabel }}</dd></div>
        <div><dt>当前正式工作中心（路线资源）</dt><dd>{{ selectedHeader.directionDisplay.current.workCenterLabel }}</dd></div>
        <div><dt>历史交出人 → 历史接收人</dt><dd>{{ selectedHeader.historicalSender?.employeeName || '尚未交出' }} → {{ selectedHeader.historicalReceiver?.employeeName || '尚未接收' }}</dd></div>
        <div><dt>实际交出时间</dt><dd>{{ selectedHeader.dispatchedAt || '尚无实际交出事件' }}</dd></div>
        <div><dt>最近实际接收事件时间</dt><dd>{{ selectedHeader.lastReceivedAt || '尚无实际接收事件' }}</dd></div>
        <div><dt>原交接编号</dt><dd>{{ selectedHeader.legacyNo || selectedHeader.no }}</dd></div>
      </dl>
      <p v-if="selectedHeader" :class="{warning:selectedHeader.directionDisplay.historicalConflict}" role="note" data-history-current-explanation>{{ selectedHeader.directionDisplay.current.explanation }}</p>
      <section v-if="selectedHeader?.directionDisplay.current.waiting.length" class="waiting-guidance" aria-label="后续工序等待说明">
        <div v-for="waiting in selectedHeader.directionDisplay.current.waiting" :key="waiting.operationId"><h3>{{ waiting.title }}</h3><p>{{ waiting.missing }}</p><p>{{ waiting.impact }}</p><p>{{ waiting.history }}</p></div>
      </section>
      <details v-if="displayFacts?.currentRoute" class="business-source" aria-label="工艺适用与后序依据" data-current-route-facts><summary>工艺适用与后序依据</summary>
        <p>以下后序与投入依据属于当前定位任务：{{ selectedTask?.taskNo || displayFacts.taskId }}；本张历史交接当时的去向在上方单独保留。</p>
        <p v-if="displayFacts.currentRoute.continuationPlan" data-continuation-plan>{{ displayFacts.currentRoute.continuationPlan.businessLabel }}：{{ displayFacts.currentRoute.continuationPlan.statusLabel }}</p>
        <p>半成品工艺编码：{{ displayFacts.currentRoute.productTypeCodes.join('、') || '正式关联待核实' }}</p>
        <p>下一实际执行工序：{{ displayFacts.currentRoute.nextExecutionOperations.map(row => row.operationName).join('、') || (displayFacts.currentRoute.unresolvedSuccessors.length ? '正式来源待核实，不能跳过' : '当前路线无后续执行工序') }}</p>
        <p>实物交接目标：{{ displayFacts.currentRoute.physicalHandoverTargets.map(row => row.operationName).join('、') || displayFacts.currentRoute.handoverTargetStatusLabel }}</p>
        <p>{{ displayFacts.currentRoute.quantitySourceLabel }}</p>
        <div v-for="target in displayFacts.currentRoute.physicalHandoverTargets" :key="target.operationId">
          <p>{{ target.operationName }}接收工作中心：{{ target.capacitySource.workCenterNames?.join('、') || '正式接收资源待核实' }}</p>
          <p v-for="batch in target.receivedInputBatches" :key="batch.handoverId">{{ target.operationName }} · {{ batch.businessNo }}：本单实收 {{ batch.receivedQuantity }} {{ batch.uomLabel }}；当前在手 {{ batch.currentHeldQuantity }} {{ batch.uomLabel }}。{{ batch.statusLabel }}</p>
          <p v-if="!target.receivedInputBatches.length">{{ target.operationName }}尚无本工单对应的有效实收批次；任务与执行为什么等待，见上方说明。</p>
        </div>
        <p v-if="displayFacts.currentRoute.physicalHandoverTargets.some(row => row.logisticsReconciliationAvailable)">实物交接数量及单位取交出批次；目标计划量、任务、开工及报工资格另行核实，不因配置缺失跳过工序。</p>
        <p v-for="reason in displayFacts.currentRoute.blockingReasons" :key="reason" class="warning">{{ userMessage(reason) }}</p>
        <details><summary>工序适用、产能与投产数量依据</summary>
          <p>标准产能与投产数量分别读取；产能数值不作为实物数量，缺失数量不等于非量经过。</p>
          <ol><li v-for="row in displayFacts.currentRoute.operations" :key="row.operationId">
            {{ row.sequence }} · {{ row.operationName }}：{{ row.applicability === 'REQUIRED' ? '执行' : row.applicability === 'NOT_APPLICABLE' ? '正式不执行' : '依据待核实' }}；
            {{ row.capacitySource.meaning || row.capacitySource.reason || '正式产能来源未核实' }}；
            标准产能：{{ row.capacitySource.sourceValuePresent ? (row.capacitySource.sourceValue ?? '已保存空值') : '未知' }}；
            投产数量模式：{{ row.quantityModeLabel || (row.applicability === 'NOT_APPLICABLE' ? '不执行，无需交接' : '正式数量依据待核实') }}。
            <p v-if="row.executionPlanLabel">{{ row.executionPlanLabel }}：{{ row.productionPlanningStatusLabel }}</p>
            <p v-if="row.productionInputPlanRef">正式投产投入参考：{{ row.productionInputQuantity }} {{ row.productionInputUomLabel }}；批次 {{ row.productionInputBatchNos.join('、') }}。实际投入与产出按各自正式事实核验。</p>
            <p v-for="reason in row.executionBlockingReasons" :key="reason" class="warning">生产执行阻断：{{ userMessage(reason) }}</p>
          </li></ol>
        </details>
      </details>
      <p v-if="!state.facts && displayFacts" class="warning">{{ state.readState === 'loading' ? '正在重新读取；下方暂保留上次定位，当前数量及资格尚未核实。' : '本次读取失败；下方为上次只读定位，当前数量及资格未知。' }}</p>

      <details class="secondary-locators"><summary>切换查看对象</summary><p data-handover-direction>{{ displayFacts?.readDirectionLabel || '读取方向待核实' }}</p>
      <p v-if="state.facts?.selectedHandover">本处显示本工单的可查看任务。查看其他工单时，请返回交接列表。</p>
      <div class="controls">
        <label>交接读取方向<select aria-label="交接读取方向" :value="state.params.direction || 'outgoing'" :disabled="busy || locked" @change="selectDirection($event.target.value)"><option value="incoming">本任务接收的上游交接</option><option value="outgoing">本任务交出的下游交接</option></select></label>
        <label>交接编号查询<input aria-label="交接编号查询" v-model="numberSearch.value" :disabled="busy || locked" placeholder="业务编号或完整原HO编号" @keyup.enter="lookupNumber" /></label><button type="button" :disabled="busy || locked || !numberSearch.value.trim()" @click="lookupNumber">查询交接编号</button>
        <label>本次定位任务<select aria-label="工序交接来源任务" :value="String(state.params.taskId || '')" :disabled="busy || locked" @change="selectLocator('taskId',$event.target.value)"><option value="">请选择正式任务</option><option v-for="row in displayFacts?.taskOptions || []" :key="row.taskId || row.id" :value="String(row.taskId || row.id)">{{ row.workOrderNo }} · {{ row.taskNo }} · {{ row.operationName }} · {{ row.workshopName }}</option></select></label>
        <label>正式交接单<select aria-label="工序交接单记录" :value="String(state.params.handoverId || '')" :disabled="busy || locked" @change="selectLocator('handoverId',$event.target.value)"><option value="">请选择要核对的交接单</option><option v-for="row in displayFacts?.handovers || []" :key="row.id" :value="String(row.id)">{{ row.businessNo || row.no }} · {{ row.workOrderNo }} · 历史 {{ row.sourceOperationName }} → {{ row.targetOperationName }} · {{ row.statusLabel }}</option></select></label>
        <button type="button" :disabled="busy" @click="refresh">重新读取交接事实</button>
      </div>
      <details class="secondary-locators"><summary>产出、异常与保管范围定位</summary><div class="controls">
        <label>正式产出记录<select aria-label="工序交接产出记录" :value="String(state.params.outputId || '')" :disabled="busy || locked" @change="selectLocator('outputId',$event.target.value)"><option value="">请选择要核对的产出记录</option><option v-for="row in displayFacts?.outputs || []" :key="row.id" :value="String(row.id)">{{ row.batchLabel }} · {{ row.statusLabel }}</option></select></label>
        <label>准确关联异常<select aria-label="工序交接关联异常" :value="String(state.params.exceptionId || '')" :disabled="busy || locked" @change="selectLocator('exceptionId',$event.target.value)"><option value="">请选择异常，或清空后登记新异常</option><option v-for="row in displayFacts?.exceptions || []" :key="row.id" :value="String(row.id)">{{ row.kindLabel || '正式关联异常' }} · 记录 {{ row.id }} · {{ row.statusLabel }}</option></select></label>
        <label>读取当前保管职责范围<select aria-label="读取当前保管职责范围" :value="String(state.params.custodyWorkCenterId || '')" :disabled="busy || locked" @change="selectLocator('custodyWorkCenterId',$event.target.value)"><option value="">请选择本次实际保管中心后重新核验</option><option v-for="row in displayFacts?.custodyContexts || []" :key="row.id" :value="String(row.id)">{{ row.name }} · {{ row.workshopName }} · {{ row.statusLabel }}</option></select></label>
      </div></details>
      </details><p v-if="state.facts && !selectedHeader && !selectedTask" role="status" data-handover-empty>{{ displayFacts.taskOptions?.length ? '尚未选择来源任务或交接单；请先核对对象。' : '当前服务未返回可选来源任务。' }}{{ displayFacts.handovers?.length ? '可从下方正式列表查看原交接单。' : '当前职责范围暂无交接单；这不是读取失败。' }}</p>
      <p v-if="state.readState === 'loading'" role="status">正在读取当前账号、职责范围、正式产出及保管份额，请等待。</p>
      <div v-if="feedbackLabel" class="outcome" :class="{warning: state.writeState !== 'verified'}" role="status" data-handover-outcome><strong>{{ feedbackLabel }}</strong><p v-if="locked">结果尚未核实，请使用“重新读取交接事实”只读核查原动作及下方原请求证明；不要再次提交。</p></div>
      <p v-if="state.error" role="alert" class="warning">{{ userMessage(state.error) }}</p><p v-if="state.recoveryError" role="alert" class="warning">{{ userMessage(state.recoveryError) }}</p><p v-if="state.message" role="status" class="warning">{{ userMessage(state.message) }}</p>
      <p v-if="!state.facts && displayFacts" class="warning">以下为同一身份及对象的上次只读事实；当前数量、资格及本次结果未知，不能据此操作。</p>
      <div v-if="state.selectionSummary && (busy || locked || !state.facts)" data-handover-original-summary class="warning"><p>{{ state.writeState.startsWith('rejected') ? '本次提交已被明确拒绝，原选择只读保留。' : locked || state.writeState === 'writing' ? '本次原意图摘要；不能用新候选或当前状态替代原请求证明。' : '正在重新读取；以下仅保留本页原选择，未提交新的业务动作，不作当前资格或结果依据。' }}</p><p v-for="item in state.selectionSummary" :key="item.label">{{ item.label }}：{{ item.value }}</p></div>
      <p v-if="locked && !state.selectionSummary" class="warning">已恢复本账号本公司原动作的技术标识；原原因、数量和候选未存入浏览器。请仅核查原动作，不能根据空表单推定未办理。</p>
      <p v-if="state.verifiedRecovery" data-handover-verified-proof>最近一次本页已核实动作：{{ recoveryActionLabel }}；对应原请求正式证明：{{ state.verifiedRecovery.proofReference }}；{{ state.verifiedRecovery.auditReference || '' }}</p>
      <template v-if="displayFacts">
        <details><summary>本人身份与来源依据</summary>
        <p>后台账号：{{ displayFacts.currentActorEvidence.username }}；正式员工：{{ displayFacts.currentActorEvidence.employeeName || '请核对正式关联' }}；公司：{{ displayFacts.currentActorEvidence.companyName || displayFacts.companyId }}</p>
        <p>{{ displayFacts.statusLabel }}</p>
        <dl v-if="selectedTask" class="facts"><div><dt>{{ state.facts ? '本次读取的正式任务' : '上次读取任务（当前待核实）' }}</dt><dd>{{ selectedTask.taskNo }} · {{ selectedTask.workOrderNo }} · {{ selectedTask.operationName }}</dd></div>
          <div><dt>原生产来源工作中心／车间</dt><dd>{{ selectedTask.workCenterName }}／{{ selectedTask.workshopName }}</dd></div><div><dt>来源任务正式执行模式</dt><dd>{{ selectedTask.executionModeLabel }}</dd></div>
          <div v-if="selectedTask.quantityApplicable === false"><dt>本节点实际产量</dt><dd data-handover-nonquantitative>不适用；不填写本节点产量。请按服务端续送根读取原定量批次及原单位。</dd></div>
          <div v-if="selectedTask.resourceSource?.selectionFact"><dt>正式资源选择引用</dt><dd>{{ selectedTask.resourceSource.selectionFact.statusLabel }}；{{ selectedTask.resourceSource.selectionFact.ref }}</dd></div>
          <div v-if="selectedTask.resourceSource?.preciseReceipt"><dt>逐工序精确接收证明</dt><dd>{{ selectedTask.resourceSource.preciseReceipt.statusLabel }}；{{ selectedTask.resourceSource.preciseReceipt.auditReference }}</dd></div>
        </dl>
        </details>
        <p v-if="state.facts?.qualification" data-handover-qualification>{{ state.facts.qualification.statusLabel }}</p>
        <p v-if="qualificationIssues.length">当前资格受限，具体原因见下方办理限制。</p>
      </template>
    </section>
    <section v-if="selectedHeader" v-show="detailView" ref="businessRecords" id="handover-existing-records" tabindex="-1" class="card business-records" aria-labelledby="handover-existing-records-heading">
      <h2 id="handover-existing-records-heading">已有交出与接收记录</h2>
      <p v-if="!state.facts" role="status">{{ state.readState === 'loading' ? '正在重新读取已有记录；下方暂不作为本次核实结果。' : '已有记录本次读取失败；请重新读取，不能据此判断为没有记录。' }}</p>
      <template v-else>
        <p>{{ selectedHeader.directionDisplay.historical.title }}：{{ selectedHeader.directionDisplay.historical.processLabel }}；{{ selectedHeader.receiptStateLabel || selectedHeader.statusLabel }}</p>
        <dl class="facts"><div><dt>历史实际交出量</dt><dd>{{ quantityText(selectedHeader.sentQuantity) }} {{ selectedHeader.uomLabel }}</dd></div><div><dt>历史原始实收量</dt><dd>{{ quantityText(selectedHeader.rawDeclaredReceiveQuantity) }} {{ selectedHeader.uomLabel }}</dd></div><div><dt>历史净匹配实收量</dt><dd>{{ quantityText(selectedHeader.correctedMatchedReceiveQuantity) }} {{ selectedHeader.uomLabel }}</dd></div><div><dt>当前目标在手余额（单独列示）</dt><dd>{{ quantityText(selectedHeader.currentTargetHeldQuantity) }} {{ selectedHeader.uomLabel }}</dd></div></dl>
        <h3>原交出记录</h3>
        <ul v-if="selectedHeader.historicalDispatches.length" class="history-entries"><li v-for="event in selectedHeader.historicalDispatches" :key="event.eventId"><strong>已实际交出</strong> · {{ event.employeeName || '本次未取得人员姓名' }} · {{ quantityText(event.quantity) }} {{ event.uomLabel }}<p>实际发生时间：{{ event.occurredAt }}</p></li></ul>
        <p v-else>本张交接记录已成功读取，尚无实际交出事件。</p>
        <h3>原实收记录</h3>
        <ul v-if="selectedHeader.historicalReceipts.length" class="history-entries"><li v-for="event in selectedHeader.historicalReceipts" :key="event.eventId"><strong>已登记本次实收</strong> · {{ event.employeeName || '本次未取得人员姓名' }} · 原始实收 {{ quantityText(event.rawQuantity) }} {{ event.uomLabel }}；本次匹配 {{ quantityText(event.matchedQuantity) }} {{ event.uomLabel }}<p>实际发生时间：{{ event.occurredAt }}</p></li></ul>
        <p v-else>本张交接记录已成功读取，尚无实际接收事件。</p>
        <p>以上是本张交接的原始发生记录；当前在手为0不会清除历史实收。</p>
        <details><summary>查看状态变化与原原因</summary><p v-for="event in selectedHeader.statusTransitionHistory" :key="event.id">{{ event.timestampLabel || event.timestamp }}；{{ userMessage(event.reason) }}</p></details>
      </template>
    </section>
    <section v-if="selectedHeader || account" v-show="detailView" class="card quantity-summary" aria-label="当前交接数量摘要">
      <h2>数量与单位</h2><p v-if="!state.facts" class="warning">上次读取的数量；当前数量未知，不作为本次办理依据。</p>
      <p v-if="selectedHeader">本物流腿 · 来源单位：{{ selectedHeader.uomLabel || '本次未取得明确单位' }}</p>
      <div v-if="selectedHeader" class="metrics"><div v-for="metric in currentLegMetrics" :key="metric.field" :data-current-leg="metric.field"><strong>{{ metric.label }}</strong><p>{{ quantityText(selectedHeader[metric.field]) }} <small>{{ selectedHeader.uomLabel || '' }}</small></p></div></div>
      <details v-if="account"><summary>其他数量账户</summary><p v-if="account.quantityApplicable === false" data-handover-summary-nonquantitative>本节点不单独统计产量；不填写本节点产量。物流沿用原定量来源及原单位，不以0或1代替。</p><p>原数量账户单位：{{ account.uom?.label || account.uom?.name || account.uom?.code || '本次未取得明确单位' }}</p><div class="metrics"><div v-for="metric in currentAccountMetrics" :key="metric.field"><strong>{{ metric.label }}</strong><p>{{ quantityText(account[metric.field]) }} <small>{{ account.uom?.label || account.uom?.name || account.uom?.code || '' }}</small></p></div></div></details>
      <p v-if="displayFacts?.selectedCustodySource?.availableManagedQuantity !== undefined">本次所选责任中心可用范围量：{{ quantityText(displayFacts.selectedCustodySource.availableManagedQuantity) }} {{ displayFacts.selectedCustodySource.uomLabel || '' }}；仅针对本责任中心准确份额。</p>

      <p>以上均为原服务事实；本腿当前未收范围包含在途及待核，不等于可再次交出。完整账户口径见下方追溯。</p>
    </section>
    <section v-if="displayFacts" v-show="detailView" class="card" aria-label="本人正式交接操作">
      <p v-if="historicalReceived">本单已收齐。请优先查看上方已有记录，原交出和接收不需要重办。<button class="secondary-button" @click="showBusinessRecords">查看已有记录</button></p>
      <details :open="!historicalReceived || (!!form.key && assessment.enabled)"><summary>{{ historicalReceived ? '其他操作及办理条件（按需查看）' : '本人可用操作及条件' }}</summary>
      <h2>{{ historicalReceived ? '其他操作与条件' : '当前办理' }}</h2><p>{{ historicalReceived ? '本张历史单已收齐，不再交出或接收。仅在确有其他业务需要且服务允许时，由本人明确选择相应动作。' : '请本人核对职责、对象及当前服务资格；交出和接收分别办理。' }}</p>
      <MesActionRestrictions v-if="state.facts" :groups="restrictionGroups" /><div class="action-overview" v-if="state.facts"><article v-for="key in ['prepare','dispatch','receive','cancel'].filter(key => displayFacts.availableActions?.[key])" :key="key"><h3>{{ key === 'receive' ? '接收方' : '交出方' }} · {{ displayFacts.availableActions[key].displayName }}</h3><p :class="{warning: !displayFacts.availableActions[key].enabled}">{{ !displayFacts.availableActions[key].enabled ? '当前不可办理，具体原因见本区办理限制。' : '本次服务允许准备此动作；仍须核对原字段与提交校验。' }}</p><button type="button" :disabled="formLocked" @click="displayFacts.availableActions[key].enabled ? initializeForm(key) : showActionCondition(key)">{{ displayFacts.availableActions[key].enabled ? '准备办理' : '查看办理条件' }}</button></article></div>
      <p v-if="displayFacts.outputReadStatus === 'read_denied'" class="warning">本账号未获准读取产出区；此状态不是没有产出，不以空列表替代。</p>
      <p v-if="conditionKey" class="warning" data-readonly-action-condition>{{ displayFacts.availableActions[conditionKey]?.displayName }}：{{ userMessage(displayFacts.availableActions[conditionKey]?.disabledReason || '请核对当前服务资格') }}。此处只读查看条件，不填写或提交业务。</p>
      <label>本次动作<select aria-label="本次工序交接动作" v-model="form.key" :disabled="formLocked" @change="initializeForm(form.key)"><option value="">请选择本人要明确办理的动作</option><option v-for="item in actionContracts" :key="item.key" :value="item.key" :disabled="!displayFacts.availableActions[item.key]?.enabled">{{ item.displayName }}{{ displayFacts.availableActions[item.key]?.enabled ? '' : '（当前不可办理）' }}</option></select></label>
      <p v-if="form.key && !formLocked && (!historicalReceived || assessment.enabled)">{{ userMessage(assessment.disabledReason) }}</p>
      <p v-if="formStale" class="warning">正式版本或来源已变化；表单保留原意图，不能覆盖新事实。</p><button v-if="formStale && !formLocked" type="button" @click="initializeForm(form.key)">明确用本次事实重新准备表单</button>
      <fieldset v-if="form.key && !formLocked && (!historicalReceived || assessment.enabled)" :disabled="formStale || !assessment.enabled">
        <legend>{{ actionContracts.find(row => row.key === form.key)?.displayName }}</legend>
        <template v-if="['confirm','excess.report'].includes(form.key)">
          <p v-if="selectedTask?.quantityApplicable !== true" class="warning">本节点不填写实际产量。续送原定量根仅办理物流，不在本节点重复生产。</p>
          <label>真实批次标识<input v-model="form.batchLabel" aria-label="真实批次标识" maxlength="160" /></label><label>批次清单引用<input v-model="form.scopeReference" aria-label="批次清单引用" /></label><label>准确实物范围<input v-model="form.scopeRange" aria-label="准确实物范围" /></label>
          <label v-if="form.key === 'excess.report'">本次超计划实际量<input v-model="form.quantity" aria-label="本次超计划实际量" inputmode="decimal" /></label>
          <div v-if="form.key === 'confirm'" data-report-coverage><h3>本次确认所覆盖的正式报工范围</h3><p>每行来自正式未定位区段；只勾选真实范围并填写本次确认量，系统不会默认选全量，不修改原累计报工上限。</p><p v-if="!form.reportAllocations.length">本次未取得可定位的正式报工区段；不能据此另造产量。</p><label v-for="(row,index) in form.reportAllocations" :key="`${row.reportId}:${row.startAtom}`" class="range"><input v-model="row.selected" type="checkbox" :aria-label="`选择报工范围${index+1}`" />{{ row.label }}；本次确认量<input v-model="row.quantity" :aria-label="`报工范围${index+1}本次确认量`" inputmode="decimal" /></label></div>
          <template v-if="form.key === 'confirm'">
          <label class="inline"><input v-model="form.inputPurpose.enabled" type="checkbox" />同时明确同车间真实投入用途（不生成免交接物流单）</label>
          <template v-if="form.inputPurpose.enabled"><label>正式投入目标任务<select v-model="form.inputPurpose.taskId" aria-label="正式投入目标任务" @change="syncInputPurpose"><option value="">请选择目标任务</option><option v-for="row in state.facts?.inputTargetTasks || []" :key="row.id || row.taskId" :value="String(row.id || row.taskId)">{{ row.taskNo }} · {{ row.operationName }}</option></select></label><label>本次投入用途依据<input v-model="form.inputPurpose.reference" aria-label="本次投入用途依据" /></label></template>
          <h3>真实投入来源范围（存在已释放前序时须闭合）</h3><p>已开工不代表已投入全部前序；只选择真实投入份额，并明确该来源对应本产出单位下的准确区间。多个来源须共同覆盖真实产出范围，不能只投入一小片就证明全部产出；最终由服务端验真。未闭合的新产出由正式服务受控冻结，不能双出。</p><label v-for="(row,index) in form.inputAllocations" :key="row.sliceId" class="range"><input v-model="row.selected" type="checkbox" :aria-label="`选择投入范围${index+1}`" />{{ row.label }}<input v-model="row.quantity" :aria-label="`投入范围${index+1}数量`" placeholder="真实投入数量" inputmode="decimal" /><input v-model="row.evidenceReference" :aria-label="`投入范围${index+1}依据`" placeholder="实际投入范围依据" /><input v-model="row.outputRangeStart" :aria-label="`投入范围${index+1}对应产出起点`" placeholder="对应本产出区间起点（本产出单位）" inputmode="decimal" /><input v-model="row.outputRangeEnd" :aria-label="`投入范围${index+1}对应产出终点`" placeholder="对应本产出区间终点（本产出单位）" inputmode="decimal" /></label>
          </template>
          <p v-if="form.key === 'excess.report'">补充报工及跟单独审仅确认真实产量，不代替来源负责人释放或核实投入。涉及前序投入的产出保持受控冻结，后续由正式来源负责人明确办理真实投入关联；本次不填写投入释放用途。</p>
        </template>
        <template v-if="['prepare','forward','return'].includes(form.key)">
          <p data-actual-source-context>实际交出中心：{{ state.facts?.custodyContexts?.find(row => row.id === Number(form.sourceWorkCenterId))?.name || '请先在上方明确读取当前保管职责范围' }}。本次表单沿用该次正式核验的中心，不借用原生产中心的职责。</p>
          <label v-if="form.key !== 'prepare'">原关联物流单<select v-model="form.previousHandoverId" aria-label="原关联物流单"><option value="">请选择原关联物流单</option><option v-for="row in state.facts?.handovers || []" :key="row.id" :value="String(row.id)">{{ row.businessNo || row.no }} · {{ row.workOrderNo }} · 历史 {{ row.sourceOperationName }} → {{ row.targetOperationName }} · {{ row.statusLabel }}</option></select></label>
          <article v-for="(delivery,index) in form.deliveries" :key="index" class="delivery"><h3>去处 {{ index+1 }}</h3>
            <label>真实去处类型<select v-model="delivery.destinationKind" :aria-label="`去处${index+1}类型`"><option value="">请选择</option><option value="production">生产去处</option><option value="storage">受托暂存</option></select></label>
            <label>目标工作中心<select v-model="delivery.targetWorkCenterId" :aria-label="`去处${index+1}目标工作中心`"><option value="">请选择真实目标</option><option v-for="row in state.facts?.targetWorkCenters || []" :key="row.id" :value="String(row.id)">{{ row.name }} · {{ row.workshopName }}</option></select></label>
            <label v-if="delivery.destinationKind === 'production'">本工单目标工序<select v-model="delivery.targetOperationId" :aria-label="`去处${index+1}目标工序`"><option value="">请选择正式目标工序</option><option v-for="row in (form.key === 'prepare' ? state.facts?.legalPrepareTargets : state.facts?.targetOperations) || []" :key="row.operationId || row.id" :value="String(row.operationId || row.id)">{{ row.sequence }} · {{ row.name }} · {{ row.workCenterName }}</option></select></label>
            <label v-if="delivery.destinationKind === 'storage'">唯一暂存区或容器标识<input v-model="delivery.destinationReference" :aria-label="`去处${index+1}暂存保管标识`" /></label>
            <label>本次真实物流用途<input v-model="delivery.purpose" :aria-label="`去处${index+1}用途`" placeholder="非直接工艺后序须说明用途；不代表后序准入" /></label>
            <p v-if="!delivery.sliceAllocations.length">本次服务未提供可选择的真实保管份额；不能用账户总余额代填份额。</p><label v-for="(row,part) in delivery.sliceAllocations" :key="row.sliceId" class="range"><input v-model="row.selected" type="checkbox" :disabled="!sliceCanChoose(row)" :aria-label="`去处${index+1}选择份额${part+1}`" />{{ row.label }}<input v-model="row.quantity" :disabled="!sliceCanChoose(row)" :aria-label="`去处${index+1}份额${part+1}数量`" placeholder="本次明确份额量" inputmode="decimal" /></label>
            <button type="button" @click="form.deliveries.splice(index,1)">移除此去处意图</button>
          </article><button type="button" @click="addDelivery">新增一个真实去处</button>
        </template>
        <template v-if="form.key === 'receive'"><h3>本次实际收讫</h3><label v-for="(row,index) in form.receipts" :key="row.allocationId" class="range"><input v-model="row.selected" type="checkbox" :aria-label="`选择收讫分量${index+1}`" />{{ row.label }}<input v-model="row.quantity" :aria-label="`收讫分量${index+1}原始实收量`" inputmode="decimal" placeholder="保留本次原始实收数" /><select v-model="row.intent" :aria-label="`收讫分量${index+1}范围意图`"><option value="">请选择本次核对范围</option><option value="partial">本次部分到达，余量继续在途</option><option value="scope_closed_short">本范围已核完，未收部分转差额待核</option></select></label></template>
        <template v-if="form.key === 'range.release'"><h3>当前来源负责人明确已有批次用途</h3><p>先在上方明确读取当前真实保管中心。本动作仅给已有准确份额明确同车间责任范围或真实后序投入用途，不建交接单、不交出、不投入、不增加有效产出；实际投入仍由对应责任人另行确认。</p><label>本次范围用途目标类别<select v-model="form.rangeTargetMode" aria-label="范围用途目标类别" @change="clearRangeTarget"><option value="">请明确选择</option><option value="center">本工单同车间责任中心范围（不指定投入任务）</option><option value="task">真实已派后序定量投入任务</option></select></label><p v-if="form.rangeTargetMode === 'center'">本次只给本工单本中心明确可支配范围，可以不指定任务；不创建待执行任务，不代表开工、投产、实收或投入。无统计量节点继续沿原定量批次，不填写本节点产量。</p><template v-if="form.rangeTargetMode === 'center'"><label>真实责任工作中心<select v-model="form.inputPurpose.workCenterId" aria-label="范围用途真实责任中心"><option value="">请选择同车间真实受控中心</option><option v-for="row in state.facts?.rangeTargetWorkCenters || state.facts?.targetWorkCenters || []" :key="row.id" :value="String(row.id)">{{ row.name }} · {{ row.workshopName }}</option></select></label><label>正式目标工序（可不指定）<select v-model="form.inputPurpose.operationId" aria-label="范围用途可选目标工序"><option value="">不指定，仅本工单责任中心范围</option><option v-for="row in (form.key === 'prepare' ? state.facts?.legalPrepareTargets : state.facts?.targetOperations) || []" :key="row.id" :value="String(row.id)">{{ row.sequence }} · {{ row.name }}</option></select></label></template><label v-if="form.rangeTargetMode === 'task'">真实后序目标任务<select v-model="form.inputPurpose.taskId" aria-label="范围用途真实目标任务" @change="syncInputPurpose"><option value="">请选择真实已派定量后序任务</option><option v-for="row in state.facts?.inputTargetTasks || []" :key="row.taskId || row.id" :value="String(row.taskId || row.id)">{{ row.taskNo }} · {{ row.operationName }} · {{ row.workCenterName }} · {{ row.workshopName }}</option></select></label><label>本次真实范围用途依据<input v-model="form.inputPurpose.reference" aria-label="本次真实范围用途依据" /></label><p>来源中心：{{ state.facts?.custodyContexts?.find(row => row.id === Number(form.sourceWorkCenterId))?.name || '请先明确读取当前保管职责范围' }}；仅可选择该中心本次正式服务标为可支配的份额。</p><label v-for="(row,index) in form.rangeAllocations" :key="row.sliceId" class="range"><input v-model="row.selected" type="checkbox" :disabled="!sliceCanChoose(row)" :aria-label="`选择用途释放份额${index+1}`" />{{ row.label }}<input v-model="row.quantity" :aria-label="`用途释放份额${index+1}数量`" :disabled="!sliceCanChoose(row)" inputmode="decimal" placeholder="本次真实来源范围量" /></label></template>
        <template v-if="form.key === 'excess.review'"><p>须原正常报工达到原标准后由不同真实员工及正式生产跟单审核职责确认；原报工上限保持。审核只确认产量，不替来源负责人确认投入或解除投入未闭合冻结。</p><label>本次超产事实审核意见<select v-model="form.decision" aria-label="本次超产事实审核意见"><option value="">请选择明确意见</option><option value="approve">确认本次真实超产事实</option><option value="reject">拒绝本次超产声明</option></select></label></template>
        <template v-if="form.key === 'input.confirm'"><h3>本产出的真实投入闭合</h3><p>只确认实际投入的原定量批次范围；不以当前任务已开工推定全部投入，不重复创建本批产出。</p><label v-for="(row,index) in form.inputAllocations" :key="row.sliceId" class="range"><input v-model="row.selected" type="checkbox" :aria-label="`选择闭合投入范围${index+1}`" />{{ row.label }}<input v-model="row.quantity" :aria-label="`闭合投入范围${index+1}数量`" placeholder="真实投入数量" inputmode="decimal" /><input v-model="row.evidenceReference" :aria-label="`闭合投入范围${index+1}依据`" placeholder="实际投入范围依据" /><input v-model="row.outputRangeStart" :aria-label="`闭合投入范围${index+1}对应产出起点`" placeholder="对应本产出区间起点（本产出单位）" inputmode="decimal" /><input v-model="row.outputRangeEnd" :aria-label="`闭合投入范围${index+1}对应产出终点`" placeholder="对应本产出区间终点（本产出单位）" inputmode="decimal" /></label></template>
        <template v-if="form.key === 'exception.submit'">
          <label>本次实际责任工作中心<select v-model="form.sourceWorkCenterId" aria-label="异常实际责任工作中心"><option value="">请选择本次责任中心</option><option v-for="row in state.facts?.sourceWorkCenters || []" :key="row.id" :value="String(row.id)">{{ row.name }} · {{ row.workshopName }}</option></select></label>
          <template v-if="state.facts?.selectedException"><p>本次仅确认所选原异常的本责任方事实，不另建异常、不代替独立处置决定。</p><label>本责任方准确范围确认依据<input v-model="form.confirmationReference" aria-label="本责任方准确范围确认依据" /></label></template>
          <template v-else><p>先准确关联原物流段／原份额，再填写原始证据；不能通过更正增加生产量。跨责任收讫更正仍须双方不同真实负责人确认并独立处置。</p>
            <label>本次真实异常类型<select v-model="form.exceptionKind" aria-label="本次真实异常类型"><option value="">请选择明确意图</option><option value="LOSS">差额正式核定损失提案</option><option value="LOCATE_SHORT">差额找到实物并定位实际保管方</option><option value="RECEIPT_CORRECTION">原匹配收讫范围调减提案</option><option value="OUTPUT_CORRECTION">来源未交出产出范围调减提案</option><option value="UNMATCHED_CLAIM">实收未匹配余数关联真实未收来源</option></select></label>
            <label>准确原物流分量<select v-model="form.allocationId" aria-label="异常准确原物流分量"><option value="">请选择当前交接单原分量</option><option v-for="row in state.facts?.selectedHandover?.allocations || []" :key="row.id" :value="String(row.id)">分量 {{ row.id }} · {{ row.quantity }} · {{ row.statusLabel }}</option></select></label>
            <label v-if="['RECEIPT_CORRECTION','OUTPUT_CORRECTION'].includes(form.exceptionKind)">准确原在手份额<select v-model="form.sliceId" aria-label="异常准确原在手份额"><option value="">请选择本次可核对的原份额</option><option v-for="row in state.facts?.slices || []" :key="row.id" :value="String(row.id)">{{ row.batchLabel }} · {{ row.quantity }} · {{ row.statusLabel }}</option></select></label>
            <label>本次准确异常范围量<input v-model="form.quantity" aria-label="本次准确异常范围量" inputmode="decimal" /></label><label>真实原始依据<input v-model="form.evidenceReference" aria-label="异常真实原始依据" /></label>
            <template v-if="form.exceptionKind === 'LOCATE_SHORT'"><label>实际保管工作中心<select v-model="form.actualCustodianWorkCenterId" aria-label="差额实际保管工作中心"><option value="">请选择真实受控中心</option><option v-for="row in state.facts?.targetWorkCenters || []" :key="row.id" :value="String(row.id)">{{ row.name }} · {{ row.workshopName }}</option></select></label><label>实际保管区或容器引用<input v-model="form.holderReference" aria-label="差额实际保管范围引用" /></label></template>
            <label v-if="form.exceptionKind === 'UNMATCHED_CLAIM'">准确待匹配原物流分量<select v-model="form.matchedAllocationId" aria-label="准确待匹配原物流分量"><option value="">请选择另一真实未收来源分量</option><option v-for="row in matchingAllocations" :key="row.allocationId" :value="String(row.allocationId)">{{ row.handoverNo }} · 分量 {{ row.allocationId }} · {{ row.quantity }} · {{ row.statusLabel }}</option></select></label>
          </template>
        </template>
        <template v-if="['exception.confirm','correct'].includes(form.key)"><p>此为所选准确关联异常的独立确认；真实原始依据、双方责任确认及原冻结范围仍由服务端逐项验真。拒绝不表示已完成生产或物流平账。</p><label>本次关联处置意见<select v-model="form.decision" aria-label="本次关联处置意见"><option value="">请选择明确意见</option><option value="approve">确认所选原处置提案</option><option value="reject">拒绝本次处置提案</option></select></label></template>
        <label v-if="needsOccurredAt">本次实际发生时间（北京时间，须含 +08:00）<input v-model="form.occurredAt" aria-label="本次交接实际发生时间" placeholder="YYYY-MM-DDTHH:mm:ss+08:00；请按真实发生填写" /></label>
        <label>本次正式动作原因<textarea v-model="form.reason" aria-label="本次工序交接动作原因" maxlength="300" rows="3" placeholder="填写2至300字本次真实原因；各动作须分别明确提交" /></label>
      </fieldset>
      <button v-if="form.key && (!historicalReceived || assessment.enabled)" type="button" :data-action-code="selectedActionContract?.actionCode" :disabled="!canSubmit" @click="submit">{{ selectedActionContract?.displayName }}</button>
      <p v-if="form.key && (!historicalReceived || assessment.enabled)" role="status">{{ userMessage(submitExplanation) }}</p>
      </details>
    </section>
    <section v-if="displayFacts" v-show="!detailView" ref="listArea" class="card handover-list" aria-label="工序交接正式列表">
      <h2 class="visually-hidden">工序交接正式列表</h2><p>{{ state.facts ? `本次服务端记录数量：${state.serverSurface.resultCount}` : '当前数量未知；以下为上次只读列表，不作本次资格或结果依据。' }}</p>
      <PceEnterpriseListTable :ref="element => table.tableRef = element" :contract="listContract" :page-id="OPERATION_HANDOVER_PAGE.pageCode" table-id="production-operation-handover-main" :rows="rows" :table-rows="table.filteredRows" :filter-schema="filterSchema" :filters="table.filters" :quick-search="table.quickSearch" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length" :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="displayNo" primary-label="交接业务编号" :primary-width="215" compact-freeze-primary :compact-show-index="false" :compact-primary-width="112" min-width="2000px" :action-width="120"
        @update:quick-search="table.quickSearch = $event" @search="table.appliedSearch = table.quickSearch" @toggle-advanced="table.advancedVisible = !table.advancedVisible" @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @export-current="table.exportCurrent" @clear-selection="table.selectedRows = []" @update-filter="table.updateFilter" @selection-change="table.selectedRows = $event" @sort-change="table.handleSort">
        <template #columns><el-table-column prop="workOrderNo" label="生产工单编号" width="180" /><el-table-column prop="historicalProcessDirection" label="本张历史交接（当时记录）" width="240" /><el-table-column prop="currentProcessDirection" label="当前正式工艺" width="230" /><el-table-column prop="currentWorkCenterDirection" label="当前正式工作中心（路线资源）" width="300" /><el-table-column prop="sourceWorkCenterName" label="历史来源中心（当时记录）" width="180" /><el-table-column prop="targetWorkCenterName" label="历史接收中心（当时记录）" width="180" /><el-table-column prop="sentQuantity" label="本腿交出量" width="140" ><template #default="{ row }">{{ quantityText(row.sentQuantity) }}</template></el-table-column><el-table-column prop="uomLabel" label="来源单位" width="110" /><el-table-column prop="rawDeclaredReceiveQuantity" label="原申报实收量" width="150" ><template #default="{ row }">{{ quantityText(row.rawDeclaredReceiveQuantity) }}</template></el-table-column><el-table-column prop="correctedMatchedReceiveQuantity" label="更正后匹配净实收" width="170" ><template #default="{ row }">{{ quantityText(row.correctedMatchedReceiveQuantity) }}</template></el-table-column><el-table-column prop="inTransitQuantity" label="明确在途" width="140" ><template #default="{ row }">{{ quantityText(row.inTransitQuantity) }}</template></el-table-column><el-table-column prop="shortQuantity" label="差额待核" width="140" ><template #default="{ row }">{{ quantityText(row.shortQuantity) }}</template></el-table-column><el-table-column prop="statusLabel" label="交接状态" width="200"><template #default="{ row }"><PceBusinessStatus :status-label="row.receiptStateLabel || row.statusLabel" /></template></el-table-column></template>
        <template #actions="{ row }"><button type="button" :disabled="busy || locked" @click="openHandover(row)" :data-handover-view="row.id">查看交接单</button></template>
      </PceEnterpriseListTable>
    </section>

    <details v-show="detailView" class="handover-trace" data-handover-trace><summary>技术详情与完整追溯</summary>
      <pre class="technical-errors">{{ technicalErrors }}</pre>
    <section v-if="account" class="card" aria-label="生产与保管数量账户">
      <h2>生产与保管数量账户</h2>
      <p>{{ state.facts ? '以下数量由本次正式服务提供。' : '上次读取的账户；当前数量未知。' }}{{ account.statusLabel }}</p>
      <p>本账户按同一原定量来源展示全范围事实，不是当前登录人的可操作数量。实际动作只针对本次正式责任范围内的准确份额，不能动用其他工作中心或整车间的全部材料。</p>
      <p>数量基准：{{ account.basis?.statusLabel || account.basis?.label || '冻结任务工序作业量，须沿正式来源及原单位核对' }}；来源单位：{{ account.uom?.label || account.uom?.name || account.uom?.code || '本节点不适用或尚未核实' }}</p>
      <p v-if="account.workOrderPlannedQuantity !== undefined">工单产品计划量另列：{{ account.workOrderPlannedQuantity }} {{ account.workOrderUomLabel || `（工单正式单位记录 ${account.workOrderUomId}）` }}；不能替代本工序冻结作业量，也不与不同单位的移交量相减。</p>
      <p>生产事实版本：{{ account.productionRevision ?? '不适用' }}；份额释放版本：{{ account.releaseRevision ?? '不适用' }}；保管版本：{{ account.custodyRevision ?? '不适用' }}。物流累计流量可重复经过，不能相加冒充产量。</p>
      <p v-if="account.quantityApplicable === false" data-account-nonquantitative>本节点生产数量不适用；P、R、E均不填数。工程参考量仅追溯，不能创建本节点实际产量。物流请明确选择关联的原定量来源任务。</p>
      <template v-else><section v-for="group in metricGroups" :key="group.title"><h3>{{ group.title }}</h3><div class="metrics"><div v-for="metric in metrics.filter(row => group.fields.includes(row.field))" :key="metric.field" :data-quantity-field="metric.field"><strong>{{ metric.label }}</strong><p>{{ quantityText(account[metric.field]) }}</p><small>{{ metric.explanation }}</small></div></div></section></template>
      <p v-if="account.logisticsMetricBasisLabel" data-logistics-metric-basis>{{ account.logisticsMetricBasisLabel }}</p>
      <p>H、F是在手份额的互斥子集，不另加到有效产出。已报待确认量不表示确定未生产；差额待核不自动回源或损失。可交余额由服务端返回，页面不重新计算。</p>
      <ul v-if="state.facts && account.blockingReasons?.length" class="warning"><li v-for="(item,index) in account.blockingReasons" :key="index">{{ issueLabel(item) }}</li></ul>
    </section>
    <section v-if="displayFacts?.selectedOutput" class="card" aria-label="本批产出正式证明">
      <h2>{{ state.facts ? (locked ? '当前只读产出（尚不能核实本次提交）' : '本批产出正式证明') : '上次读取产出（当前待核实）' }}</h2>
      <p>{{ displayFacts.selectedOutput.batchLabel }} · {{ displayFacts.selectedOutput.kindLabel || '正式产出声明／确认记录' }} · <PceBusinessStatus :status-label="displayFacts.selectedOutput.statusLabel" /></p>
      <dl class="facts"><div><dt>本批声明或确认范围量</dt><dd>{{ displayFacts.selectedOutput.quantity }} {{ account?.uom?.name || account?.uom?.label || '' }}</dd></div><div><dt>真实批次清单及范围</dt><dd>{{ displayFacts.selectedOutput.scopeManifest.reference }}；{{ displayFacts.selectedOutput.scopeManifest.range }}</dd></div>
        <div><dt>实际产出发生时间</dt><dd>{{ displayFacts.selectedOutput.occurredAt }}；业务时区：{{ displayFacts.selectedOutput.businessTimezone }}</dd></div><div><dt>正式确认人依据</dt><dd>{{ displayFacts.selectedOutput.confirmedByLabel || (displayFacts.selectedOutput.proof.confirmedById ? `正式确认账号记录 ${displayFacts.selectedOutput.proof.confirmedById}` : '本次读取尚未取得独立确认人证明') }}</dd></div>
        <div><dt>本批正式证明引用</dt><dd data-output-proof-reference>{{ displayFacts.selectedOutput.proof.ref }}</dd></div><div><dt>本批证明Hash</dt><dd>{{ displayFacts.selectedOutput.proof.proofHash }}</dd></div></dl>
      <p>本区逐笔显示正式声明或确认的原范围与证据。已报或已申报不等于已有效确认；是否计入有效产出须核对本次正式确认状态及服务端E。原整体已覆盖量定位不重复增产，关联调减更正也不能解释成新增产量。</p>
      <details><summary>产出正式审计（{{ displayFacts.selectedOutput.proof.statusTransitionCount }}）</summary><p v-for="event in displayFacts.selectedOutput.proof.statusTransitionHistory" :key="event.id">{{ event.timestamp }}；{{ event.reason }}；{{ event.auditReference }}</p></details>
    </section>
    <section v-if="selectedHeader" class="card" aria-label="本物流段正式事实">
      <h2>{{ state.facts ? (locked ? '当前只读交接单（尚不能核实本次提交）' : '本物流段正式事实') : '上次读取交接单（当前待核实）' }}</h2>
      <p>{{ selectedHeader.no }} · <PceBusinessStatus :status-label="selectedHeader.receiptStateLabel || selectedHeader.statusLabel" /></p>
      <dl class="facts"><div><dt>实际来源／目标</dt><dd>{{ selectedHeader.sourceWorkCenterName }} → {{ selectedHeader.targetWorkCenterName }}</dd></div><div><dt>去处及保管标识</dt><dd>{{ selectedHeader.destinationLabel || selectedHeader.destinationKindLabel }}；{{ selectedHeader.destinationReference }}</dd></div>
        <div v-for="metric in legMetrics" :key="metric.field" :data-leg-quantity-field="metric.field"><dt>{{ metric.label }}</dt><dd>{{ quantityText(selectedHeader[metric.field]) }} {{ selectedHeader.uomLabel || '' }}</dd></div>
        <div><dt>实际交出人／时间</dt><dd>{{ selectedHeader.senderLabel || selectedHeader.senderEmployeeName || (selectedHeader.senderEmployeeId ? `正式员工记录 ${selectedHeader.senderEmployeeId}` : '本次读取未取得交出人记录') }}；{{ selectedHeader.dispatchedAtLabel || selectedHeader.dispatchedAt || '本次未取得实际交出时间' }}</dd></div><div><dt>正式原意图及审计</dt><dd>{{ selectedHeader.proofReference || selectedHeader.auditReference || '请核对以下正式审计历史' }}</dd></div></dl>
      <p>各腿交出量、匹配实收量和闭合差额分列，不同物流腿不能累计成生产数量；超收未匹配余数不计有效产出或原物流匹配实收。</p>
      <h3>本单原备交范围与真实份额</h3><p>以下为本单原准确分量，不能用来源总占用量代替；原备交量不代表已经交出或当前仍在手。当前交出、收讫及差额另见上方正式值。</p><ol data-handover-original-allocations><li v-for="row in selectedHeader.allocations" :key="row.id">原分量 {{ row.id }}；{{ row.batchLabel || `原产出记录 ${row.outputId}` }}；原备交量 {{ row.quantity }} {{ row.uomLabel || `（来源单位记录 ${row.uomId}）` }}<span v-if="row.scopeManifest">；准确清单／范围：{{ row.scopeManifest.reference }}／{{ row.scopeManifest.range }}</span></li></ol>
      <p v-if="selectedHeader.receiptMetricBasisLabel" data-receipt-metric-basis>{{ selectedHeader.receiptMetricBasisLabel }}</p>
      <p>实际接收人：{{ selectedHeader.receiverEmployeeName || (selectedHeader.receiverEmployeeId ? `正式员工记录 ${selectedHeader.receiverEmployeeId}` : '本次未取得接收人记录') }}；最近实际收讫时间：{{ selectedHeader.lastReceivedAt || '本次未取得收讫发生时间' }}；业务时区：{{ selectedHeader.businessTimezone }}</p>
      <details v-if="selectedHeader.receiptCorrectionReferences?.length" data-receipt-corrections><summary>原实收关联更正证明（原申报历史保留）</summary><p v-for="row in selectedHeader.receiptCorrectionReferences" :key="row.eventId">正式保管事件 {{ row.eventId }}；关联异常 {{ row.exceptionId }}；范围量 {{ row.quantity }}；实际时间 {{ row.occurredAt }}；事件Hash：{{ row.eventHash }}</p></details>
      <div v-if="selectedHeader.targetPlanSummary" data-target-own-plan><h3>目标工序自身正式计划</h3><p>{{ selectedHeader.targetPlanSummary.statusLabel }}；{{ selectedHeader.targetPlanSummary.executionModeLabel }}</p><p v-if="selectedHeader.targetPlanSummary.quantityApplicable === true">目标计划量：{{ selectedHeader.targetPlanSummary.quantity }} {{ selectedHeader.targetPlanSummary.uom?.name }}；该值与本物流段来源数量及来源单位分别列示，不作隐式换算。</p><p v-else-if="selectedHeader.targetPlanSummary.quantityApplicable === false">目标本节点不单独统计产量，不能用工程参考量充作交接数量。原定量来源批次及单位继续沿用。</p><p v-if="selectedHeader.targetPlanSummary.quantityApplicable === false && selectedHeader.targetPlanSummary.referenceWorkload">目标工程参考（不作交接或实际产量）：{{ selectedHeader.targetPlanSummary.referenceWorkload.quantity ?? '无工程参考量' }} {{ selectedHeader.targetPlanSummary.referenceWorkload.uomLabel || '' }}；{{ selectedHeader.targetPlanSummary.referenceWorkload.statusLabel }}</p><p>目标原来源证明：{{ selectedHeader.targetPlanSummary.sourceHash }}</p></div>
      <details><summary>状态与审计历史（{{ selectedHeader.statusTransitionCount }}）</summary><p v-for="event in selectedHeader.statusTransitionHistory" :key="event.id"><span v-if="event.actionLabel">{{ event.actionLabel }}；</span><span v-if="event.sourceStateLabel && event.targetStateLabel">{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；</span>{{ event.timestampLabel || event.timestamp }}；{{ event.reason }}；{{ event.auditReference }}</p></details>
    </section>
    <section v-if="displayFacts?.rangeReleases?.length" class="card" aria-label="来源范围用途正式证明">
      <h2>{{ state.facts ? (locked ? '当前只读范围用途（尚不能核实本次提交）' : '来源范围用途正式证明') : '上次读取范围用途（当前待核实）' }}</h2>
      <p>范围用途证明不新增产量，不表示实际交出或投入；目标实际投入时仍须独立核对准确范围与版本并办理投入关联。</p>
      <article v-for="record in displayFacts.rangeReleases" :key="record.id" data-range-release-proof><p>正式保管事件 {{ record.id }} · <PceBusinessStatus :status-label="record.statusLabel" /></p><p>来源负责人：{{ record.sourceEmployeeName }}；实际时间：{{ record.occurredAt }}；{{ record.businessTimezone }}</p><p>目标责任中心记录 {{ record.source.target.workCenterId }}；{{ record.source.target.statusLabel }}；目标任务：{{ record.source.target.taskId ?? '未指定，不创建任务' }}；目标工序：{{ record.source.target.operationId ?? '未指定' }}；真实范围用途依据：{{ record.source.reference }}</p><p v-for="row in record.source.ranges" :key="row.sliceId">来源批次 {{ row.rootId }}／份额 {{ row.sliceId }}；本范围量 {{ row.quantity }}（来源正式单位记录 {{ row.uomId }}）</p><p v-if="record.actualReceipt">实际接收：{{ record.actualReceipt.receiverName }}；{{ record.actualReceipt.occurredAt }}；接收事件 {{ record.actualReceipt.eventId }}；原单位数量 {{ record.actualReceipt.quantity }}；接收证明 {{ record.actualReceipt.eventHash }}</p><p>正式事件Hash：{{ record.eventHash }}</p><div v-if="!record.actualReceipt && record.receiptAction"><p>此处确认本范围当前实际收讫，实际时间由服务端记录；不替代投入或完工确认。</p><label>本次实际收讫说明<input v-model="rangeReceiptForm.reasons[record.id]" maxlength="300" :disabled="formLocked || !record.receiptAction.enabled" /></label><button type="button" :disabled="formLocked || !record.receiptAction.enabled || String(rangeReceiptForm.reasons[record.id] || '').trim().length &lt; 2" @click="receiveRange(record)">{{ record.receiptAction.displayName }}</button><p v-if="record.receiptAction.disabledReason">{{ record.receiptAction.disabledReason }}</p></div></article>
    </section>
    <section v-if="displayFacts?.selectedException" class="card" aria-label="准确关联异常事实">
      <h2>{{ state.facts ? (locked ? '当前只读异常（尚不能核实本次提交）' : '准确关联异常事实') : '上次读取异常（当前待核实）' }}</h2>
      <p>原异常记录：{{ displayFacts.selectedException.id }}；<PceBusinessStatus :status-label="displayFacts.selectedException.statusLabel" />；准确范围量：{{ displayFacts.selectedException.quantity }}</p>
      <p>原始依据：{{ displayFacts.selectedException.data?.evidenceReference || '请核对原关联事实' }}；原物流段：{{ displayFacts.selectedException.handoverId ?? '无物流段关联' }}；原分量：{{ displayFacts.selectedException.allocationId ?? '无物流分量关联' }}</p>
      <p>差额定位先核实实际保管方并转受控暂存，不计原目标收讫、不增产出或物流匹配实收；真正退回原来源后才核销原腿退回量。更正必须依原准确份额及独立责任处置，不能只填原因平账。</p>
      <details><summary>原异常正式审计（{{ displayFacts.selectedException.statusTransitionCount }}）</summary><p v-for="event in displayFacts.selectedException.statusTransitionHistory" :key="event.id">{{ event.timestamp }}；{{ event.reason }}；{{ event.auditReference }}</p></details>
    </section>
    </details>
    <details id="handover-learning" class="learning-notes" :open="learningOpen" @toggle="onLearningToggle"><summary>操作说明</summary>
      <MesExecutionContext :facts="state.facts" />
      <p v-if="state.facts?.purposeLabel" role="note">{{ state.facts.purposeLabel }}</p>
    <section class="card" aria-label="工序交接单操作说明">
      <h2>操作说明</h2>
      <ol><li>从正式任务读取原作业量、报工、有效产出和实物保管账户。报工记录不等于已经确认的实物批次；允许部分产出先确认、先交，不要求先办整工序完工。</li>
        <li>来源工作中心负责人先明确真实批次及本次份额，再按实际去处备交。备交只占用份额，实际交出由责任人另行确认；未知结果不会自动释放占用。</li>
        <li>目标负责人按本次原始实收量登记。部分到达且继续等候应选“余量继续在途”；本范围已核完但不足才选“本范围核完，差额待核”。实收超过原分量仍保留原数，未匹配余数单列核查。</li>
        <li>暂存须有真实受控工作中心、明确负责人和唯一暂存区或容器标识。转送、退回引用已收讫且未投入份额；执行且有正式投产数量的工序，无论车间内部或跨车间均须实物交接；非量经过保留执行及完工事实，不生成本节点数量。已有批次明确给本工单同车间责任中心或后序任务使用，由当前来源负责人另行“确认已有批次范围用途”，不代表已交出或实际投入。</li>
        <li>执行人、派工人及班组长称谓不自动取得交接权；交出人与接收人须为不同真实员工。负责人范围在既有组织权限治理入口维护。</li>
      </ol>
      <p>本页不办理开工、原数量报工、整工序完工、库存或排程占用释放。必经无统计量节点不填写本节点产量；续送应选择原合法定量来源根及原单位，不能用工程参考量替代。</p>
      <p>每次提交后独立GET核查原动作与原请求证明。仍未知时只重新读取，不换标识、不重复提交；本页不会自动重试写入。</p>
    </section>
<p>历史实收是原接收记录，当前在手是本次读取的保管余额；二者不能互相替代。未收范围包含在途及待核，不能再次当作可交量。</p></details>

  </div>
</template>
<script setup>
import MesActionRestrictions from './MesActionRestrictions.vue'
import MesUnifiedPageGuide from './MesUnifiedPageGuide.vue'
import { learningPreference, handoverListQuery, readableCondition } from '@/meta/runtime/employeePagePresentation.js'

import MesExecutionContext from '@/meta/components/MesExecutionContext.vue'
import {mesReadContext} from '@/meta/runtime/mesTestProcessNavigation.js'
import { useMesReadTiming } from '@/meta/runtime/mesReadTiming.js'
import { computed, inject, onBeforeUnmount, onMounted, reactive, watch, ref, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { operationHandoversApi } from '@/api/operationHandovers.js'
import { createOperationHandoverState, createOperationHandoverController } from '@/meta/runtime/operationHandover.js'
import { emptyHandoverForm, newHandoverDelivery, buildHandoverPayload } from '@/meta/runtime/operationHandoverForm.js'
import { OPERATION_HANDOVER_PAGE, OPERATION_HANDOVER_ACTION_CONTRACTS, OPERATION_HANDOVER_METRICS, OPERATION_HANDOVER_FILTERS, OPERATION_HANDOVER_SEARCH_FIELDS, OPERATION_HANDOVER_EXPORT_COLUMNS } from '@/meta/runtime/operationHandoverContract.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
const learning = learningPreference('operation-handovers', readTabIdentity)
const learningOpen = ref(learning.read()), listArea = ref(null), businessRecords = ref(null), listReturn = ref(null), restoringList = ref(false)
const detailView = computed(() => route.query.screen !== 'list' && ['handoverId','businessNo','taskId','outputId','exceptionId','custodyWorkCenterId','subview'].some(key => !!route.query[key]))
const conditionKey = ref('')
function showActionCondition(key) { conditionKey.value = key }
const historicalReceived = computed(() => selectedHeader.value?.statusCode === 'received')
const technicalErrors = computed(() => JSON.stringify({readError:state.error,recoveryError:state.recoveryError,message:state.message,routeReasons:displayFacts.value?.currentRoute?.blockingReasons,conditions:qualificationIssues.value,actionReasons:Object.values(displayFacts.value?.availableActions || {}).map(x=>x.disabledReason).filter(Boolean)},null,2))
function onLearningToggle(event) { learningOpen.value=event.target.open; learning.write(learningOpen.value) }
function listPresentationOwner() {
  const identity = readTabIdentity()
  return identity?.companyId && identity?.userId ? `${identity.companyId}:${identity.userId}` : null
}
function rememberList(rowId) {
  if (detailView.value) return
  const list = table.tableRef
  const wrap = list?.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
  listReturn.value = JSON.parse(JSON.stringify({
    owner: listPresentationOwner(), query: {...route.query}, rowId,
    page: list?.currentPage || 1, size: list?.pageSize || 20,
    top: wrap?.scrollTop || 0, left: wrap?.scrollLeft || 0, pageY: window.scrollY,
    quickSearch: table.quickSearch, appliedSearch: table.appliedSearch, filters: table.filters,
    advancedVisible: table.advancedVisible, sort: table.sortState,
  }))
}
function detailNavigationState() {
  const saved = listReturn.value
  return saved?.owner ? {handoverListPresentation: JSON.parse(JSON.stringify(saved))} : undefined
}
async function openHandover(row) {
  if (busy.value || locked.value) return
  rememberList(row.id)
  await selectLocator('handoverId', String(row.id), row.receivingTaskId)
  await nextTick()
  document.querySelector('.view-navigation')?.scrollIntoView({block:'start'})
}
async function restoreListPresentation() {
  if (!restoringList.value || detailView.value) return
  const saved = listReturn.value
  if (saved) {
    table.quickSearch = saved.quickSearch
    table.appliedSearch = saved.appliedSearch
    table.advancedVisible = saved.advancedVisible
    table.handleSort(saved.sort)
    for (const key of Object.keys(table.filters)) table.updateFilter(key, saved.filters[key])
  }
  await nextTick()
  await new Promise(resolve => requestAnimationFrame(resolve))
  const list = table.tableRef
  if (saved && list) {
    list.pageSize = saved.size
    list.currentPage = saved.page
    await nextTick()
    const wrap = list.$el?.querySelector('.el-table__body-wrapper .el-scrollbar__wrap')
    if (wrap) {
      wrap.scrollLeft = saved.left
      wrap.scrollTop = saved.top
    }
    window.scrollTo({top: saved.pageY, left: 0})
    list.$el?.querySelector(`[data-handover-view="${saved.rowId}"]`)?.focus({preventScroll:true})
  } else listArea.value?.scrollIntoView({block:'start'})
  restoringList.value = false
}
function prepareListReturn() {
  if (busy.value || locked.value) return false
  if (detailView.value) restoringList.value = true
  return true
}
async function returnToList() {
  if (!prepareListReturn()) return
  await router.push(guideListLocation.value)
  if (!busy.value) await restoreListPresentation()
}
async function showBusinessRecords() { if(businessRecords.value){await nextTick();businessRecords.value.scrollIntoView({block:'start'});businessRecords.value.focus({preventScroll:true})} }
const emit = defineEmits(['refresh-status']), route = useRoute(), router = useRouter()
const guideListLocation = computed(() => ({
  path: route.path,
  query: detailView.value ? listReturn.value?.query || handoverListQuery(route.query) : {...route.query},
}))
const state = reactive(createOperationHandoverState()), form = reactive(emptyHandoverForm())
const {visibleReadMs,readCycle}=useMesReadTiming(()=>state.readState)
const owner = () => JSON.stringify([getTabAuthEpoch(),readTabIdentity()?.userId,readTabIdentity()?.companyId])
const rangeReceiptForm = reactive({ selectedId: null, reasons: {} })
const controller = createOperationHandoverController({ state, api: operationHandoversApi, identity: readTabIdentity, owner,
  rangeReceiptSelection: () => rangeReceiptForm.selectedId })
const displayFacts = computed(() => state.facts || state.lastDisplayFacts), selectedTask = computed(() => displayFacts.value?.selectedTask || displayFacts.value?.selectedCustodySource)
const selectedHeader = computed(() => displayFacts.value?.selectedHandover), account = computed(() => displayFacts.value?.selectedQuantityAccount)
const busy = computed(() => state.readState === 'loading' || state.writeState === 'writing'), locked = computed(() => !!state.pendingIntent || !!state.recoveryError)
const formLocked = computed(() => busy.value || locked.value || !state.facts)
const metrics = OPERATION_HANDOVER_METRICS
const metricGroups=[{title:'生产事实与批次定位',fields:['P','R','E','W','unconfirmedReportedQuantity','planDeficit','excessQuantity']},
  {title:'当前保管份额与占用',fields:['U','S','V','I','Q','Z','C','H','F','availableSource','availableStorage','availableDestination']},
  {title:'当前离源净额与全路径累计物流',fields:['D','plannedDispatchDeficit','O','A','X']}]
const actionContracts = computed(() => Object.values(OPERATION_HANDOVER_ACTION_CONTRACTS).filter(row => Object.hasOwn(displayFacts.value?.availableActions || {},row.key)))
const recoveryActionLabel=computed(()=>Object.values(OPERATION_HANDOVER_ACTION_CONTRACTS).find(row=>row.actionCode===state.verifiedRecovery?.actionCode)?.displayName || '对应原正式动作')
const legMetrics = [{field:'sentQuantity',label:'本物流腿已实际交出量'},{field:'rawDeclaredReceiveQuantity',label:'原始申报实收量（保留历史）'},
  {field:'originalMatchedReceiveQuantity',label:'原事件毛匹配实收量'},{field:'correctedMatchedReceiveQuantity',label:'本单历史净匹配实收（关联更正后）'},{field:'currentTargetHeldQuantity',label:'本单当前目标在手余额（含占用）'},
  {field:'originalUnmatchedReceiveQuantity',label:'原申报未匹配余数'},{field:'declaredToMatchedDifferenceQuantity',label:'原申报与当前净匹配差异'},
  {field:'receiptDifferenceQuantity',label:'本腿当前未收范围（在途及待核）'},{field:'inTransitQuantity',label:'明确仍在途'},
  {field:'shortQuantity',label:'差额待核'},{field:'lostQuantity',label:'已核定损失'},{field:'returnedBeforeReceiptQuantity',label:'未签原腿实际退回'},{field:'unmatchedQuantity',label:'当前实收未匹配余数'}]
const userMessage = readableCondition
const issueLabel = readableCondition
const qualificationIssues = computed(() => state.facts?.qualification?.missingItems || state.facts?.qualification?.blockingIssues || [])
const quantityText = value => value === null ? '不适用' : value === undefined ? '本次未取得明确数量' : value
const fingerprint = () => {
  const facts=state.facts,task=facts?.selectedTask || facts?.selectedCustodySource
  return JSON.stringify([task?.id ?? task?.taskId,task?.expectations?.expectedVersion,task?.expectations?.expectedSourceSnapshotHash || task?.sourceSnapshotHash,facts?.selectedQuantityAccount?.accountSnapshotHash,facts?.custodyAccountSnapshotHash,facts?.selectedCustodyWorkCenterId,facts?.selectedHandover?.id,facts?.selectedHandover?.version,facts?.selectedOutput?.id,facts?.selectedOutput?.version,facts?.selectedException?.id,facts?.selectedException?.version,facts?.selectedException?.sourceSnapshotHash])
}
const formStale = computed(() => !!state.facts && !!form.formContext && form.formContext !== fingerprint())
const assessment = computed(() => controller.submission(form.key)), selectedActionContract = computed(() => OPERATION_HANDOVER_ACTION_CONTRACTS[form.key])
const needsOccurredAt = computed(() => form.key !== 'excess.review')
const formProblem = computed(() => { if (!form.key || !state.facts) return '请选择本次明确动作并读取当前事实。'; try { buildHandoverPayload(state.facts,form); return '' } catch (error) { return error.message } })
const canSubmit = computed(() => !formLocked.value && !formStale.value && assessment.value.enabled && !formProblem.value && form.reason.trim().length >= 2 && form.reason.trim().length <= 300)
const submitExplanation = computed(() => assessment.value.disabledReason || (formStale.value ? '请核对新事实并明确重新准备表单。' : formProblem.value || (form.reason.trim().length < 2 ? '请填写2至300字真实原因。' : '请相应责任人本人核对后明确提交一次；随后独立只读回查。')))

const numberSearch = reactive({value:'', selection:''})
function chooseNumber(value) {
  const row = numberOptions.value.find(row => String(row.id) === value)
  numberSearch.selection = row ? value : ''
  numberSearch.value = row?.displayNo || ''
}
function editNumber(value) {
  numberSearch.selection = ''
  numberSearch.value = value
}
async function lookupNumber() {
  if (busy.value || locked.value) return
  const value = numberSearch.value.trim()
  if (!value || value.length > 80) return
  const row = numberOptions.value.find(row => [row.businessNo,row.legacyNo,row.no].includes(value))
  if (row) return openHandover(row)
  rememberList(null)
  const params = routeParams()
  await router.push({query:{...route.query, screen:undefined, view:undefined, handoverId:undefined,
    businessNo:value, direction:params.direction}, state:detailNavigationState()})
}
const sourceTaskOption = computed(() => displayFacts.value?.taskOptions?.find(row => Number(row.taskId || row.id) === Number(selectedHeader.value?.taskId)))
const currentLegMetrics = computed(() => legMetrics.filter(row => ['sentQuantity','rawDeclaredReceiveQuantity','correctedMatchedReceiveQuantity','currentTargetHeldQuantity','receiptDifferenceQuantity','inTransitQuantity','shortQuantity'].includes(row.field)))
const currentAccountMetrics = computed(() => metrics.filter(row => ['availableSource','availableStorage','availableDestination','H'].includes(row.field)))
const feedbackLabel = computed(() => state.writeState === 'verified' ? '提交成功 · 原动作已独立回查核实' : locked.value ? '提交后结果待确认／原动作核查受阻' : state.readState === 'read_failed' ? (Number(state.factLoadFacts?.httpStatus) === 403 ? '读取权限被拒绝' : '读取失败 · 当前事实未知') : state.writeState.startsWith('rejected') ? '提交被明确拒绝 · 请核对以下原服务原因' : form.key && assessment.value.enabled && formProblem.value ? '字段尚未校验通过 · '+formProblem.value : state.writeState === 'writing' ? '正在提交本次原动作' : '')

const rows = computed(() => (displayFacts.value?.handovers || []).map(row=>({...row,displayNo:row.businessNo || row.no,historicalProcessDirection:row.directionDisplay?.historical.processLabel,currentProcessDirection:row.directionDisplay?.current.processLabel,currentWorkCenterDirection:row.directionDisplay?.current.workCenterLabel})))
const numberOptions = computed(() => !detailView.value && state.facts?.readMode === 'directory'
  && state.facts.readDirection === (route.query.direction || 'outgoing') ? rows.value : [])
watch(() => route.query.direction || 'outgoing', () => editNumber(''))
const filterSchema = reactive(OPERATION_HANDOVER_FILTERS.map(row => ({...row, ...(row.field === 'statusLabel' ? {options:[]} : {})})))
const listContract = createPceEnterpriseListContract({pageCode:OPERATION_HANDOVER_PAGE.pageCode,pageType:'list',title:OPERATION_HANDOVER_PAGE.title,moduleCode:'MES'})
const table = reactive(usePceEnterpriseListRuntime({rows,filterSchema,pageCode:OPERATION_HANDOVER_PAGE.pageCode,searchFields:[...OPERATION_HANDOVER_SEARCH_FIELDS,'historicalProcessDirection','currentProcessDirection','currentWorkCenterDirection','businessNo','legacyNo','sourceOperationName','targetOperationName'],exportFileName:'工序交接单.csv',exportColumns:OPERATION_HANDOVER_EXPORT_COLUMNS}))
const sliceChoices = () => (state.facts?.slices || []).map(row => ({sliceId:row.id,expectedVersion:row.version,quantity:'',selected:false,available:row.available,
  availableForForward:row.availableForForward,availableForReturn:row.availableForReturn,unreceivedScopeUnresolved:row.unreceivedScopeUnresolved,
  responsibilityWorkCenterId:Number.isSafeInteger(row.currentResponsibilityWorkCenterId)&&row.currentResponsibilityWorkCenterId>0?row.currentResponsibilityWorkCenterId:null,
  label:[row.batchLabel || row.rootLabel || '正式批次','原保管中心：'+(row.holderWorkCenterName || '本次未取得名称'),'当前责任中心：'+(Number.isSafeInteger(row.currentResponsibilityWorkCenterId)&&row.currentResponsibilityWorkCenterId>0?(row.currentResponsibilityWorkCenterName || '正式责任中心记录 '+row.currentResponsibilityWorkCenterId):row.currentResponsibilityWorkCenterId===null?'本次无可支配责任中心':'本次责任事实待核实'),row.statusLabel,row.quantity+' '+(row.uomLabel || '')].join(' · ')}))
const sliceCanChoose=row=>row.available===true && row.responsibilityWorkCenterId===Number(form.sourceWorkCenterId)
  && (form.key!=='forward' || row.availableForForward!==false)
  && (form.key!=='return' || row.availableForReturn!==false)
  && (form.key!=='range.release' || row.unreceivedScopeUnresolved!==true)
const matchingAllocations = computed(() => (state.facts?.matchingAllocationOptions || []).filter(row => !row.originalAllocationId || row.originalAllocationId===Number(form.allocationId)))
function addDelivery() { const delivery = newHandoverDelivery(); delivery.sliceAllocations = sliceChoices(); form.deliveries.push(delivery) }
function initializeForm(key = '') {
  if (formLocked.value) return
  if (key && !state.facts?.availableActions?.[key]?.enabled) { showActionCondition(key);return }
  conditionKey.value=''
  state.selectionSummary=null
  Object.assign(form,emptyHandoverForm(),{key,formContext:fingerprint()})
  if (state.facts?.selectedCustodyWorkCenterId) form.sourceWorkCenterId=String(state.facts.selectedCustodyWorkCenterId)
  form.reportAllocations = (state.facts?.selectedTask?.reportCoverageOptions || []).map(row => ({reportId:row.reportId,startAtom:row.startAtom,endAtom:row.endAtom,quantityPrecision:row.quantityPrecision,quantity:'',selected:false,label:`正式报工 ${row.reportId} · ${row.statusLabel} · ${row.quantity} ${row.uomLabel || ''}`}))
  form.inputAllocations = (state.facts?.inputOptions || []).map(row => ({sliceId:row.id ?? row.sliceId,expectedVersion:row.expectedVersion ?? row.version,quantity:'',evidenceReference:'',outputRangeStart:'',outputRangeEnd:'',selected:false,label:[row.batchLabel,row.quantity,row.uomLabel,row.statusLabel].filter(Boolean).join(' · ')}))
  form.receipts = (state.facts?.selectedHandover?.allocations || []).map(row => ({allocationId:row.id,expectedVersion:row.version,quantity:'',intent:'',selected:false,label:`${row.batchLabel || '原物流分量'} · ${row.quantity} ${row.uomLabel || ''}`}))
  form.rangeAllocations=sliceChoices()
  if (['prepare','forward','return'].includes(key)) addDelivery()
}
function clearRangeTarget() { Object.assign(form.inputPurpose,{taskId:'',operationId:'',workCenterId:''}) }
function syncInputPurpose() { const target = (state.facts?.inputTargetTasks || []).find(row => Number(row.id ?? row.taskId) === Number(form.inputPurpose.taskId)); form.inputPurpose.operationId = target?.operationId ?? target?.sourceOperationId ?? ''; form.inputPurpose.workCenterId = target?.workCenterId ?? '' }
function originalSummary() {
  const facts=state.facts,summary=[{label:'原动作',value:selectedActionContract.value.displayName},{label:'原任务',value:selectedTask.value?.taskNo || '无任务定位'},{label:'原交接单',value:selectedHeader.value?.no || '本次新建意图'},{label:'真实批次',value:form.batchLabel || facts.selectedOutput?.batchLabel || '沿原正式份额'}]
  if(form.sourceWorkCenterId)summary.push({label:'实际责任中心',value:(facts.custodyContexts || facts.sourceWorkCenters || []).find(row=>row.id===Number(form.sourceWorkCenterId))?.name || '原明确中心待正式回查'})
  for(const [index,row]of form.deliveries.entries())summary.push({label:'原去处 '+(index+1),value:[(facts.targetWorkCenters || []).find(item=>item.id===Number(row.targetWorkCenterId))?.name || '原明确去处待正式回查',row.destinationReference,row.purpose,...row.sliceAllocations.filter(part=>part.selected).map(part=>part.label+'；本次量 '+part.quantity)].filter(Boolean).join('；')})
  for(const [index,row]of form.reportAllocations.filter(row=>row.selected).entries())summary.push({label:'原报工分量 '+(index+1),value:row.label+'；本次确认量 '+row.quantity})
  for(const [index,row]of form.receipts.filter(row=>row.selected).entries())summary.push({label:'原收讫分量 '+(index+1),value:row.label+'；原始实收量 '+row.quantity+'；'+(row.intent==='partial'?'余量继续在途':'本范围核完，差额待核')})
  for(const [index,row]of form.inputAllocations.filter(row=>row.selected).entries())summary.push({label:'原投入范围 '+(index+1),value:row.label+'；数量 '+row.quantity+'；对应本产出区间 '+row.outputRangeStart+' 至 '+row.outputRangeEnd+'；依据 '+row.evidenceReference})
  if(form.inputPurpose.taskId){const target=(facts.inputTargetTasks || []).find(row=>Number(row.taskId ?? row.id)===Number(form.inputPurpose.taskId));summary.push({label:'原明确用途目标任务',value:target?[target.taskNo,target.operationName,target.workCenterName,target.workshopName,form.inputPurpose.reference].filter(Boolean).join('；'):'原目标任务记录 '+form.inputPurpose.taskId})}
  if(form.key==='range.release' && form.rangeTargetMode==='center'){
    const center=(facts.rangeTargetWorkCenters || facts.targetWorkCenters || []).find(row=>row.id===Number(form.inputPurpose.workCenterId)),operation=(facts.targetOperations || []).find(row=>Number(row.operationId ?? row.id)===Number(form.inputPurpose.operationId))
    summary.push({label:'原明确责任中心范围',value:[center?.name || '原责任中心记录 '+form.inputPurpose.workCenterId,center?.workshopName,operation?operation.sequence+' · '+operation.name:'未指定目标工序','不指定投入任务',form.inputPurpose.reference].filter(Boolean).join('；')})
  }
  for(const [index,row]of form.rangeAllocations.filter(row=>row.selected).entries())summary.push({label:'原用途份额 '+(index+1),value:row.label+'；本次范围量 '+row.quantity})
  if(form.quantity)summary.push({label:'本次原明确范围量',value:form.quantity})
  if(facts.selectedException)summary.push({label:'原异常',value:'记录 '+facts.selectedException.id+'；'+facts.selectedException.statusLabel})
  return summary
}
async function submit() { if (!canSubmit.value) return; try { await controller.execute(form.key,buildHandoverPayload(state.facts,form),originalSummary());await synchronizeRecoveredRoute() } catch (error) { state.error = error.message } }
async function receiveRange(record) {
  if (formLocked.value || record.actualReceipt || !record.receiptAction?.enabled) return
  rangeReceiptForm.selectedId = record.id
  const action = controller.submission('range.receive').action
  if (!action) return
  await controller.execute('range.receive', { taskId: action.sourceTaskId, releaseEventId: action.objectId,
    targetTaskId: action.targetTaskId, reason: String(rangeReceiptForm.reasons[record.id] || '').trim() },
    `接收原来源事件${record.id}的准确份额；不新增产出、不替代完工或投入确认。`)
  await synchronizeRecoveredRoute()
}
const locatorKeys = ['workOrderId','taskId','outputId','handoverId','exceptionId','custodyWorkCenterId']
let recoveredRouteReadToSkip=null
const locatorSignature=query=>JSON.stringify([...locatorKeys.map(key=>query[key] ?? null),query.direction || 'outgoing',query.businessNo || null])
function routeParams() { const direction=route.query.direction || 'outgoing';if(!['incoming','outgoing'].includes(direction))throw new Error('交接读取方向不合法');const businessNo=route.query.businessNo;if(businessNo!==undefined && (typeof businessNo!=='string'||!businessNo||businessNo.length>80))throw new Error('交接编号不合法');return {direction,...(!detailView.value && !businessNo ? {readMode:'directory'} : {}),...(businessNo?{businessNo}:{}),...Object.fromEntries(locatorKeys.filter(key => route.query[key] !== undefined).map(key => { const raw = route.query[key]; if (typeof raw !== 'string' || !/^[1-9]\d*$/.test(raw) || !Number.isSafeInteger(Number(raw))) throw new Error('页面定位标识不合法，已停止读取。'); return [key,Number(raw)] }))} }
async function synchronizeRecoveredRoute() { if (!state.pendingIntent && !state.verifiedRecovery) return; const query = {...route.query}; let changed = false; for (const key of locatorKeys) { const next = state.params[key] ? String(state.params[key]) : undefined; if (query[key] !== next) {query[key] = next;changed=true} } if (changed) {recoveredRouteReadToSkip=locatorSignature(query);await router.replace({query})} }
async function refresh() { if (state.facts && form.key && !locked.value) state.selectionSummary=originalSummary(); await controller.load(); await synchronizeRecoveredRoute() }
async function readRoute() { const signature=locatorSignature(route.query);if(recoveredRouteReadToSkip===signature){recoveredRouteReadToSkip=null;return}recoveredRouteReadToSkip=null;try { const params = routeParams(); if (!locked.value) { Object.assign(form,emptyHandoverForm()); await controller.select(params) } else await controller.load(); await synchronizeRecoveredRoute() } catch (error) { state.error = error.message; state.readState='read_failed' } }
async function selectDirection(direction) { if(busy.value || locked.value)return;const query={...route.query,direction};for(const key of ['businessNo','outputId','handoverId','exceptionId','custodyWorkCenterId'])delete query[key];editNumber('');await router.push({query}) }
async function selectLocator(key,value,receivingTaskId) { if (busy.value || locked.value) return; const query = {...route.query,[key]:value || undefined}; if (receivingTaskId) query.taskId=String(receivingTaskId); delete query.screen; delete query.view; delete query.businessNo; if (key === 'taskId') {delete query.workOrderId;delete query.outputId;delete query.handoverId;delete query.exceptionId;delete query.custodyWorkCenterId} await router.push({query, state:detailNavigationState()}) }
function safe(value) { if (Array.isArray(value)) return value.map(safe); if (!value || typeof value !== 'object') return value; return Object.fromEntries(Object.entries(value).filter(([key, item]) => !/executionToken|idempotencyKey|password|cookie|jwt|secret/i.test(key) && !(key.toLowerCase() === 'authorization' && typeof item === 'string')).map(([key,item]) => [key,safe(item)])) }
function buildDiagnostics() { const factLoadFacts = state.factLoadFacts || createReadFailedFactLoad({apiUrl:OPERATION_HANDOVER_PAGE.apiUrl,errorCode:'FACTS_NOT_LOADED',errorMessage:'本次工序交接事实未读取，当前数量和资格未知。'}); const server=state.serverSurface || {...factLoadFacts,factLoadFacts,operationHandoverFacts:null,resultCount:null,passed:false}; return safe({...factLoadFacts,factOwner:OPERATION_HANDOVER_PAGE.moduleId,pageFactOwner:OPERATION_HANDOVER_PAGE.moduleId,factSource:'server',operationHandoverFacts:state.facts,strictFacts:server,strictServerFacts:server,factLoadFacts,resultCount:server.resultCount,readState:state.readState,writeState:state.writeState,recoveryError:state.recoveryError || null}) }
const provider = {factOwner:OPERATION_HANDOVER_PAGE.moduleId,refresh,buildDiagnostics}, observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY,null)
function authenticationChanged() { editNumber('');learningOpen.value=learning.read();listReturn.value=null;recoveredRouteReadToSkip=null;Object.assign(form,emptyHandoverForm());rangeReceiptForm.selectedId=null;rangeReceiptForm.reasons={}; table.selectedRows=[];controller.invalidate();readRoute() }
watch(() => [...locatorKeys.map(key => route.query[key]),route.query.direction || 'outgoing',route.query.businessNo || '',route.query.view || '',route.query.screen || ''].join('|'),readRoute,{immediate:true})
watch(() => state.readState,async value => {emit('refresh-status',({loading:'refreshing',loaded:'success',read_failed:'error'})[value] || 'idle');if(value==='loaded')await restoreListPresentation()})
watch(() => state.writeState,value => {if (value === 'verified') {form.reason='';form.formContext=null}})
watch(() => state.facts?.filterOptions?.statusLabels,values => {if (Array.isArray(values)) filterSchema.find(row => row.field === 'statusLabel').options=values.map(value => typeof value === 'string' ? {label:value,value}:value)})
onMounted(() => {
  const saved = window.history.state?.handoverListPresentation
  if (detailView.value && saved?.owner && saved.owner === listPresentationOwner()) listReturn.value = saved
  observability?.register?.(provider)
  window.addEventListener('pce:authentication-changed', authenticationChanged)
})
onBeforeUnmount(() => {controller.invalidate();observability?.unregister?.(provider);globalThis.window?.removeEventListener?.('pce:authentication-changed',authenticationChanged)})
defineExpose({navigationContext:computed(()=>mesReadContext(state.facts)),refresh,buildDiagnostics})
const restrictionGroups=computed(()=>[{label:'来源数量账户',items:account.value?.blockingReasons || []},{label:'本人资格',items:qualificationIssues.value},...Object.values(displayFacts.value?.availableActions || {}).filter(a=>!a.enabled&&a.disabledReason).map(a=>({label:a.displayName || '当前动作',items:[a.disabledReason]}))])
</script>
<style scoped>
.handover-content{display:grid;gap:16px;min-width:0;padding:18px}.card{min-width:0;border:1px solid #dbe3ef;border-radius:12px;background:white;padding:20px}.card h2{margin:0 0 14px}.card p,.card li{line-height:1.7;overflow-wrap:anywhere}.controls{display:flex;gap:14px;flex-wrap:wrap;align-items:end}.handover-content label{display:block;max-width:760px;margin:12px 0;min-width:180px}.controls label{flex:1}.handover-content select,.handover-content textarea,.handover-content input:not([type=checkbox]){display:block;box-sizing:border-box;width:100%;margin-top:6px;padding:8px;border:1px solid #cbd5e1;border-radius:5px;font:inherit}.handover-content .inline,.handover-content .range{display:flex;align-items:center;gap:10px;flex-wrap:wrap;max-width:1100px}.range input:not([type=checkbox]),.range select{width:230px;flex:1}.handover-content button{padding:9px 12px;margin:5px 6px 5px 0;border:1px solid #3568dc;border-radius:5px;background:#3568dc;color:white;cursor:pointer}.handover-content button:disabled{opacity:.5;cursor:not-allowed}.warning{padding:10px;background:#fff7e6;color:#744b0a;border-radius:5px}.facts,.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.facts dt{font-size:12px;color:#64748b}.facts dd{margin:4px 0;overflow-wrap:anywhere}.metrics>div{padding:12px;background:#f6f8fb;border:1px solid #e2e8f0;border-radius:7px}.metrics p{font-size:22px;margin:8px 0}.metrics small{line-height:1.7;color:#475569}fieldset{min-width:0;border:1px solid #cbd5e1;border-radius:6px;padding:15px}.delivery{margin:12px 0;border:1px solid #e2e8f0;border-radius:6px;padding:12px}@media(max-width:850px){.facts,.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.handover-content{padding:8px}.facts,.metrics{grid-template-columns:1fr}.card{padding:14px}}

.object-heading{display:flex;justify-content:space-between;align-items:start;gap:12px}.object-heading h2{overflow-wrap:anywhere;margin:6px 0 12px}.eyebrow{color:#64748b;font-size:.85em}.object-facts{margin-top:0}.handover-content summary{cursor:pointer;min-height:44px;line-height:1.5;padding:10px 0;font-weight:600}.handover-trace{min-width:0;border:1px solid #dbe3ef;border-radius:12px;padding:0 16px;background:#f8fafc}.handover-trace[open]{display:grid;gap:12px;padding-bottom:16px}.action-overview{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.action-overview article{min-width:0;border:1px solid #dbe3ef;border-radius:8px;padding:12px}.action-overview h3{margin:0;font-size:1em}.outcome.warning{background:#fff7e6;color:#744b0a}.outcome{padding:10px;border-radius:6px;background:#edf7ef}.handover-content :focus-visible{outline:3px solid #2563eb;outline-offset:2px}.metrics small{font-size:.8125rem}
@media(max-width:900px){.handover-content{gap:10px;padding:8px;font-size:.8125rem;line-height:1.5}.card{padding:12px;border-radius:9px}.card h2{font-size:1.125rem;margin-bottom:10px}.card h3{font-size:.9375rem}.card p,.card li{line-height:1.5}.controls{gap:8px;align-items:stretch}.controls label{flex-basis:220px}.handover-content label{min-width:0;max-width:100%;margin:8px 0;overflow-wrap:anywhere}.handover-content select,.handover-content input:not([type=checkbox]),.handover-content textarea{min-height:44px;max-width:100%;font-size:16px}.handover-content button{min-height:44px;max-width:100%;white-space:normal;overflow-wrap:anywhere;font-size:inherit}.metrics{gap:8px;grid-template-columns:repeat(2,minmax(0,1fr))}.metrics>div{padding:10px}.metrics p{font-size:1.125rem;margin:6px 0;overflow-wrap:anywhere}.facts{gap:10px}.facts dt{font-size:.75rem}.range input:not([type=checkbox]),.range select{min-width:0;flex-basis:180px}.handover-trace{padding-inline:10px}.action-overview{grid-template-columns:1fr}.object-heading{flex-wrap:wrap}fieldset{padding:10px}}
@media(max-width:380px){.metrics{grid-template-columns:1fr}}
</style>

<style scoped>
.view-navigation{position:sticky;top:calc(var(--pce-account-bookmark-height,52px) + var(--pce-system-bar-height,48px));z-index:20;background:#fff;border-bottom:1px solid #dbe3ef;display:flex;align-items:center;gap:10px;flex-wrap:wrap;padding:8px 12px}.view-navigation h2{font-size:20px;margin:0 auto 0 0}.view-navigation button,.view-navigation a{min-height:44px;display:inline-flex;align-items:center}.secondary-button{background:white!important;color:#2455a0!important}.handover-content{font-size:15px;gap:12px}.card{padding:14px}.card h2{font-size:18px}.learning-notes{border:1px solid #dbe3ef;border-radius:8px;padding:8px 14px;background:#fff}.list-locators{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.list-locators label{flex:1;margin:0;min-width:170px}.metrics p{font-size:19px}.metrics>div{padding:10px}.metrics small{font-size:14px}.technical-errors{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}.business-records summary{font-size:16px}.handover-content button{min-height:44px}.visually-hidden{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
@media(max-width:900px){.handover-content{font-size:14.5px;padding:6px;gap:10px}.card{padding:12px}.card h2,.object-heading h2{font-size:18px}.card h3{font-size:16px}.facts dt{font-size:13px}.facts dd,.handover-content label,.handover-content summary,.handover-content button{font-size:14.5px}.handover-content input,.handover-content select,.handover-content textarea{font-size:15px;min-height:44px}.metrics p{font-size:18px}.view-navigation{padding:6px 8px}.view-navigation h2{font-size:18px}.list-locators label{flex-basis:100%;min-width:0}.handover-content .el-table{font-size:14px}}
</style>

<style scoped>
/* These page shells size to their content; their overflow must not become a false sticky scroll container. */
:global(.pce-list-page-shell:has(.handover-content)),:global(.pce-list-page-content:has(> .handover-content)){overflow:visible}
</style>

<style scoped>
/* Phone density only. Keep native disclosures, natural wrapping and 44px touch targets. */
@media(max-width:900px){
.handover-content{font-size:14px;line-height:1.4;gap:6px;padding:4px}
.handover-content .card{padding:8px}
.handover-content .card p,.handover-content .card li{line-height:1.4;margin-block:6px}
.handover-content .card h2{font-size:17px;line-height:1.4;margin:0 0 6px}
.handover-content .card h3{font-size:16px;line-height:1.4;margin-block:8px 4px}
.handover-content .facts{gap:6px 10px;margin-block:8px}
.handover-content .facts dt{font-size:12px;line-height:1.4}
.handover-content .facts dd{font-size:14px;line-height:1.4;margin:2px 0 0}
.handover-content label{font-size:14px;line-height:1.4;margin-block:6px}
.handover-content button,.handover-content input,.handover-content select,.handover-content textarea{box-sizing:border-box;font-size:14px;line-height:1.4;min-height:44px}
.handover-content button{margin:0;padding:6px 10px}
.handover-content summary{box-sizing:border-box;min-height:44px;padding:10px 0;font-size:14px;line-height:1.4}
.handover-content details{margin-block:0}
.handover-content>details{padding-inline:10px}
.handover-content>details:not([open]){padding-block:0;height:auto;min-height:0}
.handover-content>details[open]{padding-bottom:8px}
.handover-content .view-navigation{padding:2px 6px;gap:6px;box-sizing:border-box}
.handover-content .view-navigation h2{font-size:16px;line-height:1.4;margin:0 auto 0 0}
.handover-content .object-heading{gap:4px}
.handover-content .object-heading h2{font-size:18px;margin:2px 0 4px}
.handover-content .object-heading :deep(.pce-business-status){white-space:normal;overflow-wrap:anywhere;font-size:14px;line-height:1.4}
.handover-content .metrics{gap:6px}
.handover-content .metrics>div{padding:8px}
.handover-content .metrics p{font-size:16px;line-height:1.4;margin:4px 0 0}
.handover-content .metrics small{font-size:12px;line-height:1.4}
.handover-content .eyebrow{font-size:12px}
.handover-content .warning{padding:8px}
.handover-content .business-records>summary{font-size:14px}
:global(.cockpit-shell:has(.handover-content) .system-bar){min-height:44px;padding:4px 12px;gap:4px}
:global(.cockpit-shell:has(.handover-content) .system-title p){font-size:11px;line-height:1.2}
:global(.cockpit-shell:has(.handover-content) .system-title h1){font-size:18px;line-height:1.3}
}
</style>

<style scoped>
.business-records{scroll-margin-top:calc(var(--pce-account-bookmark-height,52px) + var(--pce-system-bar-height,48px) + 90px)}
.business-records:focus{outline:2px solid #94b4e8;outline-offset:2px}.history-entries{padding-left:22px}.history-entries li{margin-block:8px}.waiting-guidance{border-left:4px solid #bd8a18;background:#fff8e6;padding:10px 14px;margin-block:12px}.waiting-guidance h3{margin:0 0 6px}.waiting-guidance p{margin:6px 0;line-height:1.6}
.list-locators{grid-template-columns:repeat(3,minmax(0,1fr)) auto}@media(max-width:800px){.list-locators{grid-template-columns:1fr}}
</style>
