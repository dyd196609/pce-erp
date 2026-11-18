<template>
  <div class="operation-completion-content" data-page="production-operation-completion" data-fact-source="server" :data-load-status="state.readState" :data-visible-read-ms="visibleReadMs" :data-read-cycle="readCycle">
    <MesUnifiedPageGuide title="独立审核完工" purpose="区分完工申请、独立审核及工序整体正式结果。" people="任务申请执行人、原服务指定独立审核人员" />
    <section v-if="displayFacts?.taskReadFailures?.length" role="alert" data-completion-directory-read-failures>
      <h2>部分任务读取失败</h2><p>授权任务总数：{{ displayFacts.authorizedTaskCount }}；失败任务如下。</p><p>以下任务的当前数量及完工状态未知，不能办理；其余已独立核实任务仍可选择读取。原失败记录保留。</p>
      <p v-for="item in displayFacts.taskReadFailures" :key="item.taskId">{{ item.workOrderNo }}／{{ item.taskNo }}／{{ item.operationName }}：{{ item.errorMessage }}</p>
    </section>
    <section class="card" aria-label="独审对象与定位" data-review-object>
      <div class="object-heading"><div><span class="eyebrow">{{ selected ? '当前审核对象' : '先选择正式任务' }}</span><h2>{{ selected?.no || '独立审核完工' }}</h2></div><PceBusinessStatus v-if="selected" :status-label="progress.overallCompletion.statusLabel" /></div>
      <dl v-if="selected" class="facts object-facts">
        <div><dt>工单／工序</dt><dd>{{ selected.workOrderNo }}／{{ selected.operationName }}</dd></div>
        <div><dt>车间／工作中心</dt><dd>{{ selected.workshopName }}／{{ selected.workCenterName }}</dd></div>
        <div><dt>申请执行人（原申请证明）</dt><dd>{{ selected.completionFact?.applicantLabel || '本次服务未提供执行人姓名；尚无原申请证明' }}</dd></div>
        <div><dt>实际审核人</dt><dd>{{ selected.reviewerLabel || selected.completionFact?.reviewerLabel || '尚未取得正式审核人记录' }}</dd></div>
        <div><dt>执行模式</dt><dd>{{ selected.executionModeLabel }}</dd></div>
      </dl>
      <div class="controls">
        <label>正式任务<select aria-label="工序完工任务" :value="state.taskId" :disabled="busy || pending" @change="selectTask($event.target.value)">
          <option value="">请选择正式任务</option>
          <option v-for="row in displayFacts?.tasks || []" :key="row.taskId" :value="String(row.taskId)">{{ row.no }} · {{ row.operationName }} · {{ progress.current ? row.overallCompletion.statusLabel : '结果待核实' }}</option>
        </select></label>
        <button type="button" :disabled="busy" @click="controller.load()">重新读取完工事实</button>
      </div>
      <p v-if="state.readState === 'loading'" role="status">正在读取当前后台身份、正式来源、开工、报工及完工责任，请等待。</p>
      <p v-if="state.error" role="alert" class="warning">{{ state.error }}</p>
      <p v-if="!state.facts && state.lastDisplayFacts" class="warning">以下仅为同一账号及任务的上次只读展示；当前准入和提交结果尚未核实，不能据此操作。</p>
      <p v-if="state.message" role="status" class="warning">{{ state.message }}</p>
      <p v-if="state.recoveryError" role="alert" class="warning">{{ state.recoveryError }}</p>
      <div v-if="state.selectionSummary && (busy || pending || !state.facts)" data-completion-original-intent><p>原提交只读摘要；当前显示不能替代本次结果证明。</p><p v-for="item in state.selectionSummary" :key="item.label">{{ item.label }}：{{ item.value }}</p></div>
      <p v-if="state.verifiedRecovery" data-completion-v3-proof>最近一次本页已核实动作：{{ recoveryActionLabel }}；对应原代次回查证明：{{ state.verifiedRecovery.proofRef }}；{{ state.verifiedRecovery.auditReference }}</p>

      <div v-if="feedbackLabel" class="outcome" :class="{warning: state.writeState !== 'verified'}" role="status" data-review-outcome><strong>{{ feedbackLabel }}</strong><p v-if="pending">请仅用“重新读取完工事实”核查原申请、原代次及原请求证明；不要重复申请或审核。</p></div>
      <p v-if="state.facts && !selected" data-review-empty role="status">{{ displayFacts.tasks.length ? '尚未选任务；请从上方选择或在下方查看准确任务，系统不会默认审核。' : '当前正式职责范围内没有可读取的工序完工任务；这不是读取失败。' }}</p>
      <details v-if="displayFacts"><summary>当前账号与公司职责依据</summary>        <dl class="facts">
          <div><dt>当前后台账号</dt><dd>{{ displayFacts.currentActorEvidence.username }}</dd></div>
          <div><dt>正式员工</dt><dd>{{ displayFacts.currentActorEvidence.employeeName || '当前员工关联未核实' }}</dd></div>
          <div><dt>公司</dt><dd>{{ displayFacts.currentActorEvidence.companyName }}（{{ displayFacts.currentActorEvidence.companyCode }}）</dd></div>
          <div><dt>职责范围</dt><dd>当前公司正式完工申请或审核职责范围内任务</dd></div>
        </dl>
</details>
    </section>
    <section v-if="selected" class="card" aria-label="独审依据摘要" data-review-basis>
      <MesTaskDates :facts="selected.dateFacts" :task-id="selected.taskId" :current="!!state.facts" show-review />
      <h2>审核依据</h2><p v-if="!state.facts" class="warning">上次只读依据；当前数量、资格及审核结果未知。</p>
      <div v-if="selected.quantityApplicable === true" class="metrics" data-review-quantified>
        <div><strong>任务原始作业量</strong><p>{{ selected.workloadQuantity ?? '未核实' }} {{ selected.workloadUomLabel ?? '未核实单位' }}</p></div>
        <div><strong>累计已报量</strong><p>{{ selected.reportedQuantity ?? '未核实' }} {{ selected.workloadUomLabel ?? '未核实单位' }}</p></div>
        <div><strong>剩余未报量</strong><p>{{ selected.remainingQuantity ?? '未核实' }} {{ selected.workloadUomLabel ?? '未核实单位' }}</p></div>
      </div>
      <div v-else-if="selected.quantityApplicable === false" data-review-nonquantitative><p>本工序不单独统计实际完成数量，不填写数量或单位；实际经过与数量报工分别核对。</p><p>{{ selected.executionConfirmation?.statusLabel || '尚无经核验的正式实际经过登记' }}</p><p v-if="selected.executionConfirmation">实际经过确认人：{{ selected.executionConfirmation.confirmedByLabel }}；{{ selected.executionConfirmation.confirmedAtLabel }}；{{ selected.executionConfirmation.auditReference }}</p></div>
      <p v-else class="warning">本次服务尚未核实计量模式；不以0或1补造数量。</p>
          <p v-if="selected.quantityApplicable !== null" data-mode-previous-step>本次完工采用的前一正式执行事实：<router-link :to="{path:'/planning/operation-reports',query:{taskId:String(selected.taskId)}}">{{ selected.quantityApplicable === false ? '实际经过登记' : '工序数量报工' }}</router-link>；该事实仍不能替代生产跟单员独立审核。</p>

      <p>数量均为原服务事实；报齐、剩余为0或已有实际经过，均不能代替独立审核。原记录、单位精度和全部来源证明见下方追溯。</p>
    </section>
    <section v-if="selected" class="card" aria-label="本人独审办理" data-review-current-action>
      <h2>当前办理与资格</h2>
          <section class="record-progress" :key="progress.recordKey || `task-${selected.taskId}-unverified`" :data-completion-record-key="progress.recordKey || ''" aria-label="本次申请逐笔进度">
            <details v-if="progress.current && progress.recordId"><summary>本次申请追溯标识</summary><p data-completion-record-id>本次申请记录标识：{{ progress.recordId }}</p></details>
            <h3>本次申请提交进度</h3><p data-completion-submission-progress>{{ progress.submissionLabel }}</p>
            <h3>本次申请审核进度</h3><p data-completion-review-progress>{{ progress.reviewLabel }}</p>
            <p data-completion-progress-notice>{{ progress.noticeLabel }}</p>
            <p v-if="progress.current && progress.submitted && !progress.reviewed">审核责任：{{ progress.reviewResponsibilityLabel }}</p>
          </section>
      <MesActionRestrictions v-if="state.facts" :groups="restrictionGroups" />
      <div class="qualification"><h3>本人审核资格</h3><p>{{ selected.reviewQualification?.statusLabel || '本次服务未提供审核资格说明' }}</p><p v-if="approveAction.disabledReason" data-review-approve-blocker>当前不可审核，具体原因见上方办理限制。</p><p>申请与独审由各自责任人本人办理，不以界面显示代替原服务授权。</p></div>
          <label>{{ selected.completionProtocolVersion === 3 ? '本次申请、替代新申请或审核原因' : '本次申请或审核原因' }}<textarea v-model="state.reason" aria-label="本次完工申请或审核原因" maxlength="240" rows="3" :disabled="busy || pending || !state.facts || (!requestAction.enabled && !approveAction.enabled && !withdrawAction.enabled)"
            placeholder="请填写2至240字，申请与审核分别由本人明确操作" /></label>
          <div class="action-section" :key="`request-${progress.recordKey || selected.taskId}`">
            <button type="button" :data-action-code="requestAction.actionCode" :disabled="!requestSubmission.enabled"
              :data-record-key="progress.recordKey || ''" aria-describedby="completion-request-reason" @click="controller.execute('request')">{{ progress.requestButtonLabel }}</button>
            <p id="completion-request-reason" data-completion-request-reason role="status" aria-live="polite">{{ requestExplanation }}</p>
          </div>
          <div class="action-section" :key="`approve-${progress.recordKey || selected.taskId}`">
            <button type="button" :data-action-code="approveAction.actionCode" :disabled="!approveSubmission.enabled"
              :data-record-key="progress.recordKey || ''" aria-describedby="completion-approve-reason" @click="controller.execute('approve')">{{ progress.approveButtonLabel }}</button>
            <p id="completion-approve-reason" data-completion-approve-reason role="status" aria-live="polite">{{ approveExplanation }}</p>
          </div>
          <section v-if="selected.completionV3?.availableActions?.withdrawReplace" class="action-section" data-completion-withdraw-replace>
            <h3>原申请本人撤回并替代</h3>
            <p>先填写上方替代新申请原因，再单独说明撤回原待审申请的原因。本动作同时关闭原意图并建立新申请，不能修改原审核决定，也不能由审核人代替申请人办理。</p>
            <label>撤回原申请原因<textarea v-model="state.withdrawReason" aria-label="撤回原完工申请原因" maxlength="240" rows="2" :disabled="busy || pending || !state.facts || !withdrawAction.enabled" /></label>
            <button type="button" :data-action-code="withdrawAction.actionCode" :disabled="!withdrawSubmission.enabled" @click="controller.execute('withdrawReplace')">{{ withdrawAction.displayName }}</button>
            <p role="status">{{ !withdrawAction.enabled ? '当前不可撤回并替代，具体原因见上方办理限制。' : withdrawSubmission.disabledReason || '请原申请本人核对原代次及新生产事实后明确提交一次。' }}</p>
          </section>

    </section>
    <section v-if="displayFacts" class="card" aria-label="工序完工任务列表">
      <h2>工序完工任务列表</h2>
      <p>{{ state.facts ? `正式任务记录：${state.serverSurface.resultCount}` : '当前记录数量未知，上次列表仅供回看。' }}</p>
      <PceEnterpriseListTable :ref="element => table.tableRef = element" :contract="listContract" :page-id="OPERATION_COMPLETION_PAGE.pageCode"
        table-id="production-operation-completion-main" :rows="rows" :table-rows="table.filteredRows" :filter-schema="OPERATION_COMPLETION_FILTERS"
        :filters="table.filters" :quick-search="table.quickSearch" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length"
        :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="no" primary-label="工序任务编号" index-label="列表序号"
        :primary-width="200" compact-freeze-primary :compact-show-index="false" :compact-primary-width="120" min-width="2200px" :action-width="130"
        @update:quick-search="table.quickSearch = $event" @search="table.appliedSearch = table.quickSearch" @toggle-advanced="table.advancedVisible = !table.advancedVisible"
        @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @export-current="table.exportCurrent"
        @clear-selection="table.selectedRows = []" @update-filter="table.updateFilter" @selection-change="table.selectedRows = $event" @sort-change="table.handleSort">
        <template #columns>
          <el-table-column prop="frozenSequence" label="冻结路线／计划工序序号" width="180" /><el-table-column label="实际审核人" width="130"><template #default="{row}">{{ row.reviewerLabel || row.completionFact?.reviewerLabel || '尚未审核' }}</template></el-table-column><el-table-column prop="workOrderNo" label="生产工单编号" width="190" /><el-table-column prop="operationName" label="工序" width="130" />
          <el-table-column prop="workshopName" label="车间" width="110" /><el-table-column prop="workCenterName" label="工作中心" width="180" />
          <el-table-column prop="workloadQuantity" label="原始作业量" width="160"><template #default="{ row }">{{ row.quantityApplicable === false ? '不单独计量' : row.workloadQuantity ?? '未核实' }}</template></el-table-column><el-table-column prop="reportedQuantity" label="累计已报量" width="160"><template #default="{ row }">{{ row.quantityApplicable === false ? '不适用数量报工' : row.reportedQuantity ?? '未核实' }}</template></el-table-column>
          <el-table-column prop="remainingQuantity" label="剩余未报量" width="150"><template #default="{ row }">{{ row.quantityApplicable === false ? '不单独计量' : row.remainingQuantity ?? '未核实' }}</template></el-table-column><el-table-column prop="workloadUomLabel" label="单位" width="100"><template #default="{ row }">{{ row.quantityApplicable === false ? '不适用' : row.workloadUomLabel }}</template></el-table-column>
          <el-table-column prop="requestRecordId" label="申请追溯" width="170"><template #default="{ row }"><details><summary>查看追溯标识</summary>{{ row.requestRecordId ?? '尚无本次申请' }}</details></template></el-table-column>
          <el-table-column prop="submissionProgressLabel" label="本次提交进度" width="230" />
          <el-table-column prop="reviewProgressLabel" label="本次审核进度" width="200" />
          <el-table-column prop="overallProgressLabel" label="工序整体正式状态" width="220"><template #default="{ row }"><PceBusinessStatus :status-label="row.overallProgressLabel" /></template></el-table-column>
        </template>
        <template #actions="{ row }"><button type="button" :disabled="busy || pending" @click="selectTask(String(row.taskId))">查看任务</button></template>
      </PceEnterpriseListTable>
    </section>
    <details class="review-trace" data-review-trace><summary>原记录、审核证明与说明</summary>
      <MesExecutionContext :facts="state.facts" /><p v-if="state.facts?.purposeLabel" role="note">{{ state.facts.purposeLabel }}</p>
    <section class="card" aria-label="工序完工操作说明">
      <h2>操作说明</h2>
      <ol>
        <li>从正式任务中选择需要申请或审核的工序，重新读取并核对工单、工序、开工及报工数量。</li>
        <li>必经无统计量任务核对真实开工及正式实际经过登记，不填写数量或单位，也不使用数量报工替代经过证明。仍由本人申请、生产跟单员独立审核，三项进度分别查看。</li>
        <li>尚未提交时，任务指定执行人本人填写2至240字原因，符合条件后点击“提交完工申请”。正式回读确认后显示“已提交”；本次申请待生产跟单员审核，不重复提交。</li>
        <li>生产跟单员核对本次正式申请，填写2至240字审核原因后点击“审核完工数据”。正式回读确认后显示“已审核”，申请侧仍显示“已提交”；申请人不能审核本人申请。</li>
        <li>按钮旁显示当前阻止操作的具体原因。提交后独立只读回查申请、审核人、时间及审计；结果待核实时仅重新读取，不重复提交。</li>
      </ol>
      <p>报工量已达任务量、剩余量为0或原因写“已完成”都不能替代正式完工审核。本页不修改已报工数量，不执行转移、库存、后序放行、自动开工、排程或占用释放。</p>
      <p>读取、刷新、切换任务、填写原因、复制诊断及导出均不产生完工申请或审核。正式业务操作由相应责任人本人决定并执行。</p>
      <p>提交进度、审核进度均按本次申请记录标识查看，与工序整体正式完工状态分别显示。定量V3任务使用真实完工代次；申请仍待审而生产事实改变时，仅原申请本人可明确撤回并提交替代申请。撤回关闭不构成审核或驳回，原已审核代次保持历史。旧协议及必经无统计量任务继续沿用原申请、独立审核路径。</p>
    </section>
      <section v-if="selected" class="card" aria-label="审核来源完整依据"><h2>原任务、数量及实际经过依据</h2>          <dl class="facts source-facts">
            <div><dt>任务编号</dt><dd>{{ selected.no }}</dd></div>
            <div><dt>工序整体正式完工状态</dt><dd data-overall-completion-status><PceBusinessStatus :status-label="progress.overallCompletion.statusLabel" /></dd></div>
            <div><dt>工单／工序</dt><dd>{{ selected.workOrderNo }}／{{ selected.operationName }}</dd></div>
            <div><dt>车间／工作中心</dt><dd>{{ selected.workshopName }}／{{ selected.workCenterName }}</dd></div>
            <div v-if="selected.resourceSource?.effectiveReceptionAuthority"><dt>本工序有效接收依据</dt><dd data-effective-reception>{{ selected.resourceSource.effectiveReceptionAuthority }}；{{ selected.resourceSource.effectiveWorkshop?.name }}</dd></div>
            <div v-if="selected.resourceSource?.selectionFact"><dt>正式资源选择依据</dt><dd>{{ selected.resourceSource.selectionFact.statusLabel }}；{{ selected.resourceSource.selectionFact.ref }}</dd></div>
            <div v-if="selected.resourceSource?.preciseReceipt"><dt>逐工序精确接收证明</dt><dd data-precise-receipt>{{ selected.resourceSource.preciseReceipt.statusLabel }}；{{ selected.resourceSource.preciseReceipt.actorLabel }}；{{ selected.resourceSource.preciseReceipt.timeLabel }}；{{ selected.resourceSource.preciseReceipt.auditReference }}</dd></div>
            <div><dt>正式执行模式</dt><dd data-execution-mode>{{ selected.executionModeLabel }}</dd></div>
            <template v-if="selected.quantityApplicable === true">
            <div><dt>任务原始作业量</dt><dd>{{ selected.workloadQuantity ?? '未核实' }} {{ selected.workloadUomLabel ?? '未核实' }}</dd></div>
            <div><dt>累计已报量</dt><dd>{{ selected.reportedQuantity ?? '未核实' }} {{ selected.workloadUomLabel ?? '未核实' }}</dd></div>
            <div><dt>剩余未报量</dt><dd>{{ selected.remainingQuantity ?? '未核实' }} {{ selected.workloadUomLabel ?? '未核实' }}</dd></div>
            <div><dt>正式单位小数位数</dt><dd>{{ selected.quantityPrecision ?? '未核实' }}</dd></div>
            </template>
            <template v-else-if="selected.quantityApplicable === false">
              <div><dt>实际完成数量</dt><dd>本工序不单独统计实际完成数量，不填写数量或单位。</dd></div>
              <div><dt>工程参考（不是实际产量）</dt><dd data-reference-workload>{{ selected.referenceWorkload.quantity ?? '无工程参考量' }} {{ selected.referenceWorkload.uomLabel || '' }}；{{ selected.referenceWorkload.statusLabel || '仅供来源追溯' }}</dd></div>
              <div><dt>正式实际经过登记</dt><dd data-execution-confirmation>{{ selected.executionConfirmation?.statusLabel || '尚无经核验的正式实际经过登记' }}<span v-if="selected.executionConfirmation">；{{ selected.executionConfirmation.confirmedByLabel }}；{{ selected.executionConfirmation.confirmedAtLabel }}；{{ selected.executionConfirmation.auditReference }}</span></dd></div>
            </template>
          </dl>
</section>
      <section v-if="selected" class="card" aria-label="申请与独审原记录"><h2>申请与独审原记录</h2>          <details v-if="selected.completionV3?.generationHistory?.length" data-completion-generation-history><summary>正式完工代次历史（{{ selected.completionV3.generationHistory.length }}）</summary>
            <article v-for="row in selected.completionV3.generationHistory" :key="row.id || row.generationId"><h4>代次 {{ row.generationSequence || row.sequence || row.id || row.generationId }} · {{ row.statusLabel }}</h4>
              <p>申请依据：{{ row.requestAuditReference || row.requestProofReference || '请核对本代次正式申请引用' }}</p>
              <div v-if="row.closure"><p>原待审意图关闭；此记录不是审核决定，不显示成驳回。</p><p>{{ row.closure.statusLabel }}；{{ row.closure.closedByLabel }}；{{ row.closure.closedAtLabel || row.closure.closedAt }}；{{ row.closure.reason }}；{{ row.closure.auditReference }}</p><p>原申请：{{ row.closure.originalRequestReference }}；替代对象：{{ row.closure.replacementObjectId }}</p></div>
              <details v-if="row.bridgeHistory"><summary>原待审申请的独立承接与本人关闭历史（{{ row.bridgeHistory.statusTransitionCount }}）</summary><p>此历史用于承接原待审意图并办理本人撤回；原申请及原审核历史仍单独保留，不是重新报工、重新申请或审核驳回。</p><p v-for="event in row.bridgeHistory.statusTransitionHistory" :key="event.id">{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；{{ event.reason }}；{{ event.auditReference }}</p></details>
            </article>
          </details>
          <h3>{{ state.facts ? (pending ? '当前只读追溯（尚不能核实本次提交）' : '本次正式申请与审核追溯') : '上次回读追溯（当前结果待核实）' }}</h3>
          <template v-if="selected.completionFact">
            <dl class="facts source-facts">
              <div><dt>申请人／实际申请时间</dt><dd>{{ selected.completionFact.applicantLabel }}／{{ selected.completionFact.requestedAtLabel }}</dd></div>
              <div><dt>申请原因</dt><dd>{{ selected.completionFact.requestReason }}</dd></div>
              <div><dt>申请审计</dt><dd>{{ selected.completionFact.requestAuditReference }}</dd></div>
              <div><dt>审核人／生效时间</dt><dd>{{ selected.completionFact.reviewerLabel || '尚未审核确认' }}／{{ selected.completionFact.completedAtLabel || '尚未生效' }}</dd></div>
              <div><dt>审核原因</dt><dd>{{ selected.completionFact.reviewReason || '尚无正式审核原因' }}</dd></div>
              <div><dt>审核审计</dt><dd>{{ selected.completionFact.approvalAuditReference || '尚无正式审核审计' }}</dd></div>
            </dl>
            <details><summary>正式状态与审计历史（{{ selected.completionFact.statusTransitionCount }}）</summary>
              <p v-for="event in selected.completionFact.statusTransitionHistory" :key="event.id">{{ event.actionLabel }}：{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；{{ event.timestampLabel }}；{{ event.auditReference }}</p>
            </details>
          </template>
          <p v-else>{{ state.facts && !pending ? '本次读取尚无正式完工申请。仅核对报工量不会生成申请或认定完工。' : state.facts ? '本次只读暂未查到申请；原操作结果仍待核实，不能据此重复提交。' : '上次读取未取得正式申请；当前事实及原操作结果待核实。' }}</p></section>
      <section v-if="selected" class="card" aria-label="共享流程及生产代次依据">          <section aria-label="本任务共享流程" data-completion-shared-lifecycle>
            <h3>本任务共享流程</h3>
            <p>{{ state.facts ? (pending ? '以下为本次只读共享流程事实，尚不能核实原提交结果。' : '以下为本次服务核实的本任务共享流程事实。') : '以下仅为上次读取的本任务共享流程；当前待办、统计及原提交结果待核实。' }}</p>
            <p>范围仅限当前已授权任务的完工申请链，不是全局共享工作台。数量由正式服务返回，撤回关闭与独立批准、拒绝分别列示。</p>
            <p>这些是本任务历史申请及共享状态统计，不替代当前生产异常判断、整体完工独立审核或后序开工资格。历史已有批准记录时，当前生产事实更正仍可能阻断新准入；统计数量不决定任何操作按钮。</p>
            <template v-if="sharedLifecycle">
              <p data-completion-shared-status>{{ sharedLifecycle.statusLabel }}</p>
              <dl class="facts" data-completion-shared-counts>
                <div><dt>共享流程数量</dt><dd data-shared-count="workflowCount">{{ sharedLifecycle.workflowCount ?? '未核实' }}</dd></div>
                <div><dt>待审申请数量</dt><dd data-shared-count="pendingCount">{{ sharedLifecycle.pendingCount ?? '未核实' }}</dd></div>
                <div><dt>实际待办任务数量</dt><dd data-shared-count="pendingTaskCount">{{ sharedLifecycle.pendingTaskCount ?? '未核实' }}</dd></div>
                <div><dt>独立批准数量</dt><dd data-shared-count="approvedCount">{{ sharedLifecycle.approvedCount ?? '未核实' }}</dd></div>
                <div><dt>独立拒绝数量</dt><dd data-shared-count="rejectedCount">{{ sharedLifecycle.rejectedCount ?? '未核实' }}</dd></div>
                <div><dt>撤回待审关闭数量</dt><dd data-shared-count="closedCount">{{ sharedLifecycle.closedCount ?? '未核实' }}</dd></div>
              </dl>
              <p v-if="sharedLifecycle.availability === 'legacy_boundary'" data-completion-shared-boundary>原正式证明保留；共享实体关联属于历史边界，待办与统计尚未核实，不按零记录处理。</p>
              <p v-else-if="sharedLifecycle.availability === 'verified_empty'">正式服务已核实本任务尚无共享审批申请、待办或关闭记录。</p>
              <p v-if="sharedLifecycle.pendingTaskIds?.length" data-completion-shared-pending>本任务正式待办标识：<span v-for="id in sharedLifecycle.pendingTaskIds" :key="id">{{ id }}；</span></p>
              <article v-for="row in sharedLifecycle.workflows || []" :key="row.workflowInstanceId" data-completion-shared-workflow>
                <h4>共享流程 {{ row.workflowInstanceId }}／审批任务 {{ row.approvalTaskId }} · {{ row.statusLabel }}</h4>
                <p>申请审计：{{ row.requestAuditReference }}<span v-if="row.approvalAuditReference">；独立审核审计：{{ row.approvalAuditReference }}</span></p>
                <div v-if="row.closure" data-completion-shared-closure><p>撤回关闭不构成审核或拒绝。</p><p>{{ row.closure.statusLabel }}；{{ row.closure.closedByLabel }}；{{ row.closure.closedAtLabel || row.closure.closedAt }}；{{ row.closure.reason }}；{{ row.closure.auditReference }}</p><p>原申请：{{ row.closure.originalRequestReference }}；替代对象：{{ row.closure.replacementObjectId }}</p></div>
                <details v-for="group in row.sharedHistory || []" :key="`${group.objectType}-${group.objectId}`" data-completion-shared-history><summary>{{ sharedObjectLabel(group.objectType) }} {{ group.objectId }} · 正式历史（{{ group.statusTransitionCount ?? '未核实' }}）</summary>
                  <p v-for="event in group.statusTransitionHistory || []" :key="event.id">{{ event.sourceStateLabel }} → {{ event.targetStateLabel }}；操作人标识：{{ event.operatorId }}；{{ event.timestampLabel || event.timestamp }}；{{ event.reason }}；{{ event.auditReference }}</p>
                </details>
              </article>
              <p data-completion-shared-diagnostics>本任务共享转换历史数量：{{ sharedLifecycle.statusTransitionCount ?? '未核实' }}；历史与状态一致性：{{ sharedLifecycle.stateMachineConsistent === true ? '正式服务验真通过' : sharedLifecycle.stateMachineConsistent === false ? '正式服务验真未通过' : '未核实' }}。</p>
            </template>
            <p v-else data-completion-shared-unavailable>{{ state.facts ? '本次服务尚未提供' : '上次读取未取得' }}本任务共享流程投影；待办、关闭及统计未核实，不按零记录处理。</p>
          </section>
          <section v-if="selected.completionV3" data-completion-production-evidence>
            <h3>正式生产事实与完工代次</h3>
            <p>协议：{{ selected.completionV3.contractVersion }}；真实代次标识：{{ selected.completionV3.generationId }}；代次版本：{{ selected.completionV3.generationVersion }}</p>
            <p>生产事实版本：{{ selected.completionV3.productionRevision }}；生产事实证明：{{ selected.completionV3.productionHash }}</p>
            <p>已报、有效产出和物流保管分别核对；交出、接收或暂存流转不会自动产生新产量或替代独立完工审核。</p>
            <p v-if="selected.completionV3.currentProductionStatus" data-completion-current-production-status>{{ selected.completionV3.currentProductionStatus.statusLabel }}；原历史证明：{{ selected.completionV3.currentProductionStatus.historicalProofValid ? '正式服务验真通过' : '本次未取得有效历史完工证明' }}</p>
            <dl v-if="selected.completionV3.currentProductionStatus" class="facts" data-completion-production-quantities><div><dt>原冻结计划标准</dt><dd>{{ selected.completionV3.currentProductionStatus.planQuantity ?? '本次未取得明确值' }} {{ selected.workloadUomLabel }}</dd></div><div><dt>当前有效实际产出</dt><dd>{{ selected.completionV3.currentProductionStatus.wholeProductionQuantity ?? '本次未取得明确值' }} {{ selected.workloadUomLabel }}</dd></div></dl>
            <p v-if="selected.completionV3.currentProductionStatus?.productionChangeNotice">{{ selected.completionV3.currentProductionStatus.productionChangeNotice }}</p>
            <div v-if="selected.completionV3.currentProductionStatus?.currentCorrectionReferences?.length"><p>当前关联产量更正证明：</p><p v-for="row in selected.completionV3.currentProductionStatus.currentCorrectionReferences" :key="row.ref">{{ row.ref }}；{{ row.proofHash }}；本次关联范围量：{{ row.quantity }}</p></div>
            <ul v-if="state.facts && selected.completionV3.currentProductionStatus?.blockingIssues?.length" class="warning"><li v-for="(item,index) in selected.completionV3.currentProductionStatus.blockingIssues" :key="index">{{ item.statusLabel || item.message || item }}</li></ul>
            <ul v-if="state.facts && selected.completionV3.blockingIssues.length" class="warning"><li v-for="(item,index) in selected.completionV3.blockingIssues" :key="index">{{ item.statusLabel || item.message || item }}</li></ul>
          </section>
</section>
    </details>
  </div>
</template>
<script setup>
import MesTaskDates from './MesTaskDates.vue'
import MesActionRestrictions from './MesActionRestrictions.vue'
import MesUnifiedPageGuide from './MesUnifiedPageGuide.vue'
import MesExecutionContext from '@/meta/components/MesExecutionContext.vue'
import {mesReadContext,mesWorkOrderFilter} from '@/meta/runtime/mesTestProcessNavigation.js'
import { useMesReadTiming } from '@/meta/runtime/mesReadTiming.js'
import { computed, inject, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { operationCompletionsApi } from '@/api/operationCompletions.js'
import { createOperationCompletionState, createOperationCompletionController } from '@/meta/runtime/operationCompletion.js'
import { OPERATION_COMPLETION_PAGE, OPERATION_COMPLETION_FILTERS, OPERATION_COMPLETION_SEARCH_FIELDS, OPERATION_COMPLETION_EXPORT_COLUMNS } from '@/meta/runtime/operationCompletionContract.js'
import { OPERATION_COMPLETION_ACTION_CONTRACTS, OPERATION_COMPLETION_V3_ACTION_CONTRACTS, resolvePceOperationCompletionAction } from '@/meta/runtime/pceBusinessActionRegistry.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
const emit = defineEmits(['refresh-status']), route = useRoute(), router = useRouter()
const state = reactive(createOperationCompletionState())
const owner = () => JSON.stringify([getTabAuthEpoch(), readTabIdentity()?.userId, readTabIdentity()?.companyId, readTabIdentity()?.username])
const {visibleReadMs,readCycle}=useMesReadTiming(()=>state.readState)
const controller = createOperationCompletionController({ state, api: {...operationCompletionsApi,readRecovery:params=>operationCompletionsApi.read(params),read:params=>operationCompletionsApi.read({...params,...mesWorkOrderFilter(route)})}, owner,
  companyId: () => readTabIdentity()?.companyId, userId: () => readTabIdentity()?.userId })
const displayFacts = computed(() => state.facts || state.lastDisplayFacts), selected = computed(() => displayFacts.value?.selectedTask)
const sharedLifecycle = computed(() => selected.value?.sharedWorkflowLifecycle)
const sharedObjectLabel = type => ({ WorkflowInstance: '共享流程实例', ApprovalTask: '共享审批任务', WorkflowClosure: '正式撤回关闭记录' })[type] || '关联共享对象'
const busy = computed(() => state.readState === 'loading' || state.writeState === 'writing'), pending = computed(() => !!state.pendingIntent || !!state.recoveryError || state.writeState === 'readback_pending')
const action = key => state.facts?.selectedTask ? resolvePceOperationCompletionAction(state.facts, key)
  : { ...(key === 'withdrawReplace' || selected.value?.completionProtocolVersion === 3 ? OPERATION_COMPLETION_V3_ACTION_CONTRACTS : OPERATION_COMPLETION_ACTION_CONTRACTS)[key], enabled: false, disabledReason: '' }
const requestAction = computed(() => action('request')), approveAction = computed(() => action('approve'))
const withdrawAction = computed(() => selected.value?.completionV3?.availableActions?.withdrawReplace ? action('withdrawReplace') : { enabled: false })
const withdrawSubmission = computed(() => selected.value?.completionV3?.availableActions?.withdrawReplace ? controller.submission('withdrawReplace') : { enabled: false })
const requestSubmission = computed(() => controller.submission('request')), approveSubmission = computed(() => controller.submission('approve'))
const progress = computed(() => controller.progress())
const recoveryActionLabel=computed(()=>Object.values(OPERATION_COMPLETION_V3_ACTION_CONTRACTS).find(row=>row.actionCode===state.verifiedRecovery?.actionCode)?.displayName || '对应原正式完工动作')
const requestExplanation = computed(() => !progress.value.current ? progress.value.noticeLabel
  : progress.value.submitted ? progress.value.submissionLabel
    : !requestAction.value.enabled ? '当前不可申请，具体原因见上方办理限制。' : requestSubmission.value.disabledReason || '当前可以提交完工申请，提交后须生产跟单员审核。')
const approveExplanation = computed(() => !progress.value.current ? progress.value.noticeLabel
  : progress.value.reviewed ? progress.value.reviewLabel
    : progress.value.submitted && !approveAction.value.enabled && !progress.value.admissionIssues.length
      ? progress.value.reviewLabel : !approveAction.value.enabled ? '当前不可审核，具体原因见上方办理限制。' : approveSubmission.value.disabledReason || '请本人核对本次申请后审核完工数据。')
const issueLabel = item => typeof item === 'string' ? item : item?.statusLabel || item?.message || '原服务阻断项'
const feedbackLabel = computed(() => state.writeState === 'verified' ? '提交成功 · 原申请／审核动作已独立核实' : pending.value ? '结果待确认 · 请只读核查原动作' : state.readState === 'read_failed' ? (Number(state.factLoadFacts?.httpStatus) === 403 ? '读取权限被拒绝' : '读取失败 · 数量及审核结果未知') : state.writeState.startsWith('rejected') ? '提交已被明确拒绝 · 请核对原服务原因' : state.writeState === 'writing' ? '正在提交本次明确动作' : '')
const rows = computed(() => (displayFacts.value?.tasks || []).map(row => ({ ...row,
  requestRecordId: progress.value.current ? row.recordProgress.recordId : null,
  submissionProgressLabel: progress.value.current ? row.recordProgress.submissionLabel : '结果待核实',
  reviewProgressLabel: progress.value.current ? row.recordProgress.reviewLabel : '结果待核实',
  overallProgressLabel: progress.value.current ? row.overallCompletion.statusLabel : '结果待核实' })))
const listContract = createPceEnterpriseListContract({ pageCode: OPERATION_COMPLETION_PAGE.pageCode, pageType: 'list', title: OPERATION_COMPLETION_PAGE.title, moduleCode: 'MES' })
const table = reactive(usePceEnterpriseListRuntime({ rows, filterSchema: OPERATION_COMPLETION_FILTERS, pageCode: OPERATION_COMPLETION_PAGE.pageCode,
  searchFields: OPERATION_COMPLETION_SEARCH_FIELDS, exportFileName: '工序完工任务.csv', exportColumns: OPERATION_COMPLETION_EXPORT_COLUMNS }))
async function selectTask(value) { if (busy.value || pending.value) return; await router.replace({ query: { ...route.query, taskId: value || undefined } }) }
function safeDiagnostics(value) {
  if (Array.isArray(value)) return value.map(safeDiagnostics)
  if (!value || typeof value !== 'object') return value
  return Object.fromEntries(Object.entries(value).filter(([key, item]) => !/executionToken|idempotencyKey|password|cookie|jwt|secret/i.test(key) && !(key.toLowerCase() === 'authorization' && typeof item === 'string'))
    .map(([key, item]) => [key, safeDiagnostics(item)]))
}
function buildDiagnostics() {
  const factLoadFacts = state.factLoadFacts || createReadFailedFactLoad({ apiUrl: OPERATION_COMPLETION_PAGE.apiUrl,
    errorCode: 'FACTS_NOT_LOADED', errorMessage: '完工事实尚未读取，正式来源、数量及审核状态未知。' })
  const server = state.serverSurface || { ...factLoadFacts, factLoadFacts, operationCompletionFacts: null, resultCount: null, passed: false }
  return safeDiagnostics({ ...factLoadFacts, factOwner: OPERATION_COMPLETION_PAGE.moduleId, pageFactOwner: OPERATION_COMPLETION_PAGE.moduleId,
    moduleCode: OPERATION_COMPLETION_PAGE.moduleId, factSource: 'server', operationCompletionFacts: state.facts,
    strictFacts: server, strictServerFacts: server, factLoadFacts, resultCount: server.resultCount,
    readState: state.readState, writeState: state.writeState, errorMessage: state.error || null,
    submission: { request: controller.submission('request'), approve: controller.submission('approve') },
    recordProgressPresentation: controller.progress() })
}
const provider = { factOwner: OPERATION_COMPLETION_PAGE.moduleId, refresh: () => controller.load(), buildDiagnostics }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
let recoveredTaskReadToSkip=null
async function readTaskRoute(value) {
  const taskId=String(value || '')
  if(recoveredTaskReadToSkip===taskId){recoveredTaskReadToSkip=null;return}
  recoveredTaskReadToSkip=null
  await controller.select(taskId)
  if((state.pendingIntent || state.verifiedRecovery) && state.taskId !== String(route.query.taskId || '')) {
    recoveredTaskReadToSkip=state.taskId
    await router.replace({query:{...route.query,taskId:state.taskId || undefined}})
  }
}
function authenticationChanged() {
  recoveredTaskReadToSkip=null
  controller.invalidate(); table.selectedRows = []; table.clearFilters(); table.handleSort()
  readTaskRoute(route.query.taskId)
}
watch(() => [route.query.taskId,route.query.workOrderId], () => readTaskRoute(route.query.taskId), { immediate: true })
watch(() => [state.readState,state.facts?.taskReadFailures?.length], ([value,failed]) => emit('refresh-status', value==='loaded' && failed ? 'error' : ({ loading: 'refreshing', loaded: 'success', read_failed: 'error' })[value] || 'idle'))
onMounted(() => { observability?.register?.(provider); globalThis.window?.addEventListener?.('pce:authentication-changed', authenticationChanged) })
onBeforeUnmount(() => { controller.invalidate(); observability?.unregister?.(provider); globalThis.window?.removeEventListener?.('pce:authentication-changed', authenticationChanged) })
defineExpose({navigationContext:computed(()=>mesReadContext(state.facts)), refresh: () => controller.load(), buildDiagnostics })
const restrictionGroups=computed(()=>[
 {label:'本次申请准入',items:progress.value.current ? progress.value.admissionIssues : []},
 {label:'当前生产事实',items:selected.value?.completionV3?.currentProductionStatus?.blockingIssues || []},
 {label:'完工核验',items:selected.value?.completionV3?.blockingIssues || []},
 ...[requestAction.value,approveAction.value,withdrawAction.value].filter(a=>a.disabledReason&&!a.enabled).map(a=>({label:a.displayName || '当前动作',items:[a.disabledReason]}))])
</script>
<style scoped>
.operation-completion-content{display:grid;gap:16px;min-width:0;padding:18px}.card{min-width:0;border:1px solid #dbe3ef;border-radius:12px;background:white;padding:20px}.card h2{margin:0 0 14px}.card p,.card li{line-height:1.7;overflow-wrap:anywhere}.controls{display:flex;gap:14px;align-items:end;flex-wrap:wrap}.operation-completion-content label{display:block;max-width:700px;margin:12px 0;min-width:220px}.controls label{flex:1}.operation-completion-content select,.operation-completion-content textarea{display:block;box-sizing:border-box;width:100%;margin-top:7px;padding:9px;border:1px solid #cbd5e1;border-radius:6px;font:inherit}.operation-completion-content button{padding:9px 12px;border:1px solid #3568dc;border-radius:6px;background:#3568dc;color:white;cursor:pointer}.operation-completion-content button:disabled{opacity:.5;cursor:not-allowed}.warning{padding:10px;background:#fff7e6;color:#744b0a;border-radius:6px}.facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 20px}.facts dt{font-size:12px;color:#64748b}.facts dd{margin:4px 0;font-weight:600;overflow-wrap:anywhere}.source-facts{border-top:1px solid #e2e8f0;padding-top:14px}.action-section{margin:16px 0}.action-section p{margin:8px 0}@media(max-width:650px){.operation-completion-content{padding:8px}.card{padding:14px}.facts{grid-template-columns:1fr}.controls{display:block}}

.object-heading{display:flex;align-items:start;justify-content:space-between;gap:12px}.object-heading h2{margin:6px 0 12px;overflow-wrap:anywhere}.eyebrow{color:#64748b;font-size:.85em}.object-facts{margin-top:0}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.metrics>div{padding:12px;border:1px solid #dbe3ef;border-radius:8px;background:#f6f8fb}.metrics p{font-size:1.25rem;margin:8px 0;overflow-wrap:anywhere}.operation-completion-content summary{min-height:44px;line-height:1.5;padding:10px 0;font-weight:600;cursor:pointer}.review-trace{min-width:0;padding:0 16px;background:#f8fafc;border:1px solid #dbe3ef;border-radius:12px}.review-trace[open]{display:grid;gap:12px;padding-bottom:16px}.outcome{padding:10px;background:#edf7ef;border-radius:6px}.outcome.warning{background:#fff7e6;color:#744b0a}.qualification{padding:10px;border:1px solid #dbe3ef;border-radius:8px}.qualification h3{margin-top:0}.operation-completion-content :focus-visible{outline:3px solid #2563eb;outline-offset:2px}
@media(max-width:900px){.operation-completion-content{gap:10px;padding:8px;font-size:.8125rem;line-height:1.5}.card{padding:12px;border-radius:9px}.card h2{font-size:1.125rem;margin-bottom:10px}.card h3{font-size:.9375rem}.card p,.card li{line-height:1.5}.controls{display:flex;align-items:stretch;gap:8px}.controls label{flex-basis:220px}.operation-completion-content label{min-width:0;max-width:100%;margin:8px 0;overflow-wrap:anywhere}.operation-completion-content select,.operation-completion-content textarea{min-height:44px;font-size:16px;max-width:100%}.operation-completion-content button{min-height:44px;max-width:100%;font-size:inherit;overflow-wrap:anywhere;white-space:normal}.object-heading{flex-wrap:wrap}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.metrics>div{padding:10px}.metrics p{font-size:1.125rem}.facts{gap:10px}.facts dt{font-size:.75rem}.facts dd{font-weight:500}.review-trace{padding-inline:10px}}
@media(max-width:380px){.metrics{grid-template-columns:1fr}}
</style>
