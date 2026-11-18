<template>
  <section ref="panelElement" class="operation-workload-source" data-section="operation-workload-source" data-fact-source="server" :data-load-status="readState"
    :data-read-diagnostics="JSON.stringify(readDiagnostics)" data-read-diagnostics-kind="non-business-receive-parse-and-vue-commit-timing"
    :data-strict-facts="JSON.stringify(strictFacts)">
    <p v-for="notice in viewContextNotices" :key="notice" class="source-notice" role="status">{{ notice }}</p>
    <header class="source-header">
      <div>
        <h4>作业量来源配置</h4>
        <p>按正式来源方案查询工程量、工序需求和计划已保存负荷。</p>
      </div>
      <div class="draft-actions">
        <button type="button" :disabled="busy" @click="refreshSourceFacts">刷新来源事实</button>
        <button type="button" @click="copyCurrentDiagnostics">复制当前核对诊断</button>
      </div>
    </header>
    <p v-if="diagnosticCopyMessage" role="status">{{ diagnosticCopyMessage }}</p>

    <section class="route-source-overview" data-section="route-source-overview" :data-load-status="routeReadState"
      :data-no-date-read-state="routeConfiguration?.noDateCapacityIncluded ? routeReadState : 'not_read'"
      :data-no-date-result-hash="routeConfiguration?.noDateCapacitySummary?.resultHash"
      :data-no-date-assessed-at="routeConfiguration?.noDateCapacitySummary?.assessedAt">
      <h5>计划路线投产量总表</h5>
      <div class="route-overview-controls">
        <label>
          <span>路线总览计划</span>
          <select v-model="selectedRoutePlanId" :disabled="busy" @change="loadRouteOverview">
            <option value="">请选择生产计划</option>
            <option v-for="plan in catalog.productionPlans" :key="plan.id" :value="String(plan.id)">{{ optionLabel(plan) }}</option>
          </select>
        </label>
        <button type="button" :disabled="!selectedRoutePlanId || busy" @click="loadRouteOverview">刷新路线投产量</button>
      </div>
      <p class="source-notice" data-section="route-overview-scope">路线总览计划：{{ selectedRoutePlan ? optionLabel(selectedRoutePlan) : selectedRoutePlanId ? '正在读取计划名称' : '未选择生产计划' }}。详情生产计划由下方原下拉独立选择。</p>
      <p v-if="routeReadState === 'idle'" class="source-notice">选择计划后集中读取其正式路线步骤，无需先选工序。</p>
      <p v-else-if="routeReadState === 'loading'" class="source-notice" role="status">正在读取所选计划的正式路线、需求、分配及保存投产量；完成前各项事实未知。</p>
      <p v-else-if="routeReadState === 'read_failed'" class="source-error" role="alert">{{ routeReadError }} 当前路线事实未知，请重新读取。</p>
      <template v-else-if="routeConfiguration">
        <PceBusinessStatus :status-label="routeConfiguration.summary.workloadStatusLabel" />
        <p class="route-summary">路线步骤 {{ quantityText(routeConfiguration.summary.stepCount) }} 项；{{ routeConfiguration.summary.workloadStatusLabel }}。正式需求 {{ quantityText(routeConfiguration.summary.formalRequirementRecordCount) }} 条，分配 {{ quantityText(routeConfiguration.summary.allocationRecordCount) }} 条。</p>
        <p v-if="routeConfiguration.noDateCapacitySummary" class="route-summary" data-section="route-no-date-summary">{{ routeConfiguration.noDateCapacitySummary.statusLabel }}</p>
        <p class="source-notice">工程需求量、已保存投产量及无日期产能核对均来自本次正式读取，不跨工序或跨单位相加。展开可查看产能、理论用时及来源追溯；不表示日期排程、资源占用或实际完工。</p>
        <PceEnterpriseListTable
          ref="routeTableRef"
          :contract="routeListContract"
          page-id="operation-workload-route-overview"
          table-id="operation-workload-route-overview-table"
          :rows="routeRows"
          :table-rows="routeFilteredRows"
          :filter-schema="routeFilterSchema"
          :filters="routeFilters"
          :quick-search="routeQuickSearch"
          :advanced-visible="routeAdvancedVisible"
          :selected-count="routeSelectedRows.length"
          :active-filter-count="routeActiveFilterCount"
          :sort-text="routeSortText"
          :expand-row-keys="routeExpandedStepIds"
          @expand-change="rememberRouteExpansion"
          row-key="routingStepId"
          primary-field="stepLabel"
          primary-label="路线工序"
          :primary-width="140"
          :action-width="130"
          :show-action-column="mode === 'maintain'"
          :default-page-size="50"
          min-width="1500px"
          :show-refresh="true"
          :refreshing="routeReadState === 'loading'"
          @update:quick-search="routeQuickSearch = $event"
          @search="routeAppliedSearch = routeQuickSearch"
          @toggle-advanced="routeAdvancedVisible = !routeAdvancedVisible"
          @clear-filters="routeClearFilters"
          @clear-sort="routeClearSort"
          @export-current="routeExportCurrent"
          @clear-selection="routeSelectedRows = []"
          @update-filter="(field, value) => routeFilters[field] = value"
          @selection-change="routeSelectedRows = $event"
          @sort-change="routeHandleSort"
          @refresh="loadRouteOverview"
        >
          <template #columns>
            <el-table-column type="expand" width="48">
              <template #default="{ row }">
                <section class="route-workload-detail" :data-route-step="row.routingStepId">
                  <h6>{{ row.stepLabel }} · 来源与保存追溯</h6>
                  <p v-if="row.effectiveVersion?.versionLabel" data-cell="route-effective-version">{{ row.effectiveVersion.versionLabel }}</p>
                  <button v-if="mode !== 'maintain'" type="button" :disabled="busy" @click="openRouteStep(row)">查看完整来源追溯</button>
                  <p>{{ row.workloadReview.statusLabel }}</p>
                  <section v-if="row.noDateCapacity" data-section="route-no-date-capacity" data-fact-source="server"
                    :data-no-date-read-state="routeReadState" :data-no-date-result-hash="row.noDateCapacity.resultHash"
                    :data-no-date-assessed-at="row.noDateCapacity.assessedAt">
                    <h6>无日期产能与理论用时</h6>
                    <PceBusinessStatus :status-label="row.noDateCapacity.statusLabel" />
                    <p v-for="(label, key) in row.noDateCapacity.displayLabels" :key="key">{{ noDateDisplayFieldLabel(key) }}：{{ label }}</p>
                    <div data-section="route-no-date-time-references">
                      <p>原始时间参考：以下参考值不计入准确总工期，不据此选择时间或形成日期、资源占用。</p>
                      <p>路线步骤原始参考：准备 {{ row.noDateCapacity.timeReferences?.step?.preparationDays ?? '未知' }}；转运 {{ row.noDateCapacity.timeReferences?.step?.transferDays ?? '未知' }}；单位 {{ row.noDateCapacity.timeReferences?.step?.timeUnit === 'DAY' ? '天' : '未知' }}。</p>
                      <p v-for="reference in row.noDateCapacity.timeReferences?.standardCapacities || []" :key="reference.standardCapacityId">标准产能 {{ reference.standardCapacityId }} 原始参考：准备 {{ reference.preparationDays ?? '未知' }}；转运 {{ reference.transferDays ?? '未知' }}；单位 {{ reference.timeUnit === 'DAY' ? '天' : '未知' }}。</p>
                      <p v-if="!row.noDateCapacity.timeReferences?.standardCapacities?.length">标准产能原始参考未提供，准备和转运时间未知。</p>
                    </div>
                    <template v-if="row.noDateCapacity.capacityMatches.length > 1">
                      <article v-for="match in row.noDateCapacity.capacityMatches" :key="`${match.standardCapacityId}:${match.workCenterId || ''}`">
                        <p v-for="(label, key) in match.displayLabels" :key="key">{{ noDateDisplayFieldLabel(key) }}：{{ label }}</p>
                      </article>
                    </template>
                    <p v-for="(issue, index) in row.noDateCapacity.blockers" :key="index" class="source-error">{{ reasonLabel(issue) }}</p>
                  </section>
                  <section v-if="conditionalExecutionLabels(row.applicability).length" data-section="route-conditional-execution" data-fact-source="server">
                    <p v-for="(label, index) in conditionalExecutionLabels(row.applicability)" :key="index">{{ label }}</p>
                  </section>
                  <section v-if="row.quantityPolicy" data-section="route-quantity-policy" data-fact-source="server">
                    <PceBusinessStatus :status-label="row.quantityPolicy.statusLabel" />
                    <p v-if="row.quantityPolicy.scopeDeterminationLabel">{{ row.quantityPolicy.scopeDeterminationLabel }}</p>
                    <p>计划投产数量：{{ row.quantityPolicy.plannedQuantityReasonLabel }}</p>
                    <p>实际产量：{{ row.quantityPolicy.actualQuantityReasonLabel }}</p>
                    <p>统计单位：{{ row.quantityPolicy.statisticalUomReference.uomLabel }}；{{ row.quantityPolicy.statisticalUomReference.statusLabel }}</p>
                    <p>{{ row.quantityPolicy.capacityIndependenceLabel }}</p>
                  </section>
                  <p v-if="row.applicability?.formalSourceLabel">适用性正式依据：{{ row.applicability.formalSourceLabel }}</p>
                  <p v-if="row.resourceReferences?.statusLabel">产能适用范围：{{ row.resourceReferences.statusLabel }}</p>
                  <dl>
                    <div v-for="capacity in row.resourceReferences?.standardCapacityCandidates || []" :key="capacity.id"><dt>正式标准产能 {{ capacity.id }}</dt><dd>{{ capacity.name }}；{{ quantityText(capacity.quantity) }} {{ capacity.uomLabel || '单位未提供' }}／{{ capacity.timeUnitLabel || '时间单位未提供' }}；基准 {{ quantityText(capacity.timeBasisQuantity) }} {{ capacity.timeUnitLabel || '' }}；{{ capacity.statusLabel }}；适用产品 {{ capacity.productTypeName || '未提供' }}<span v-if="capacity.productTypeCode">（{{ capacity.productTypeCode }}）</span>；工作中心 {{ capacity.workCenterName || '未提供' }}</dd></div>
                  </dl>
                  <p>正式来源规则：{{ row.sourceRuleText }}</p>
                  <p>正式来源字段及生产版本：{{ row.sourceInputText }}</p>
                  <p>数量合同：{{ row.quantityContractText }}</p>
                  <p v-if="row.workloadReview.coverageStatusLabel">{{ row.workloadReview.coverageStatusLabel }}</p>
                  <dl>
                    <div v-for="source in row.sourceCandidates?.items || []" :key="`source:${source.sourceFactId}:${source.ruleId || ''}`"><dt>来源工程量</dt><dd>核算 {{ source.sourceCalculationId }}／事实 {{ source.sourceFactId }}；{{ quantityText(source.quantity ?? source.sourceQuantity) }} {{ source.uomLabel || '' }}</dd></div>
                    <div v-for="item in row.formalRequirements.items" :key="`requirement:${item.operationRequirementId}`"><dt>正式需求 {{ item.operationRequirementId }}</dt><dd>{{ quantityText(item.quantity ?? item.requirementQuantity ?? item.workloadQuantity) }} {{ item.uomLabel || '' }}；来源核算 {{ item.sourceCalculationId }}／事实 {{ item.sourceFactId }}<span v-if="item.generationKey">；生成身份 {{ item.generationKey }}</span></dd></div>
                    <div v-for="item in row.savedAllocations.items" :key="`allocation:${item.allocationId}`"><dt>分配 {{ item.allocationId }}／需求 {{ item.operationRequirementId }}</dt><dd>{{ quantityText(item.quantity) }} {{ item.uomLabel || '' }}；来源核算 {{ item.sourceCalculationId }}／事实 {{ item.sourceFactId }}<span v-if="item.auditId != null">；审计 {{ item.auditId }}</span><template v-if="item.objectCoverageProof"><p>{{ item.objectCoverageProof.statusLabel }}</p><p>{{ item.objectCoverageProof.snapshotStatusLabel }}</p><p v-if="item.objectCoverageProof.coverage">设计对象 {{ item.objectCoverageProof.coverage.designItemIds.join('、') }}；基线项 {{ item.objectCoverageProof.coverage.baselineItemIds.join('、') }}；输入事实 {{ item.objectCoverageProof.coverage.inputFactIds.join('、') }}</p></template></dd></div>
                  </dl>
                  <p v-for="(issue, index) in row.workloadReview.blockers" :key="index" class="source-error">{{ reasonLabel(issue) }}</p>
                </section>
              </template>
            </el-table-column>
            <el-table-column prop="noDateCapacityLabel" label="无日期产能核对" min-width="240" sortable show-overflow-tooltip />
            <el-table-column prop="noDateTimeLabel" label="理论用时／时间边界" min-width="250" sortable show-overflow-tooltip />
            <el-table-column prop="processingText" label="投产适用性／处理方式" min-width="220" sortable show-overflow-tooltip />
            <el-table-column prop="sourceBusinessLabel" label="正式投产来源口径" min-width="230" sortable show-overflow-tooltip />
            <el-table-column prop="formalRequirementLabel" label="正式需求量／保存状态／记录数" min-width="210" sortable show-overflow-tooltip />
            <el-table-column prop="savedQuantityText" label="计划已保存投产量／单位" min-width="200" sortable show-overflow-tooltip />
            <el-table-column prop="savedAllocationLabel" label="分配保存状态／记录数" min-width="200" sortable show-overflow-tooltip />
            <el-table-column prop="coverageStatusLabel" label="对象覆盖" min-width="220" sortable show-overflow-tooltip />
            <el-table-column prop="blockerText" label="真实缺项" min-width="240" show-overflow-tooltip />
          </template>
          <template #actions="{ row }">
            <button type="button" :disabled="busy" @click="openRouteStep(row)">{{ mode === 'maintain' ? '查看／维护来源' : '查看来源' }}</button>
          </template>
        </PceEnterpriseListTable>
      </template>
    </section>

    <label class="operation-selector">
      <span>工序</span>
      <select v-model="selectedOperationId" :disabled="busy" @change="changeOperation">
        <option value="">请选择工序</option>
        <option v-for="operation in operationOptions" :key="operation.id" :value="String(operation.id)">{{ optionLabel(operation) }}</option>
      </select>
    </label>

    <p v-if="readState === 'loading'" class="source-notice" role="status">正在读取当前范围；数量未知。</p>
    <p v-else-if="readState === 'read_failed'" class="source-error" role="alert">{{ readError }} 当前来源、需求和负荷未知，请重新读取。</p>

    <template v-if="readState === 'loaded' && serverFacts">
      <section v-if="selectedOperationId && configuration" class="configuration-overview" data-cell="source-configuration">
        <PceBusinessStatus :status-label="configuration.statusLabel" />
        <p>{{ configuration.summary }}</p>
        <p class="legacy-explanation">历史来源说明：{{ configuration.legacyQuantityDriver || '未填写' }}。该文字不作为正式来源查询依据。</p>
        <article v-for="source in configuration.sources || []" :key="source.ruleId || source.id || source.ruleCode" class="configured-source">
          <strong>{{ source.ruleName || source.label || source.ruleCode }}</strong>
          <PceBusinessStatus v-if="source.statusLabel" :status-label="source.statusLabel" />
          <p>{{ source.summary || source.sourceLabel }}</p>
          <p v-if="source.capacityUsageScopeLabel">{{ source.capacityUsageScopeLabel }}</p>
          <p v-if="source.capacityModeLabel">{{ source.capacityModeLabel }}</p>
          <small v-if="source.ruleCode">{{ source.ruleCode }} · {{ source.version || source.ruleVersion }}</small>
          <details :open="traceExpanded(traceKey('source', source.ruleId || source.id || source.ruleCode))" @toggle="rememberTraceExpansion(traceKey('source', source.ruleId || source.id || source.ruleCode), $event)">
            <summary>来源规则与数量口径</summary>
            <dl>
              <div><dt>正式来源字段及版本</dt><dd>{{ sourceInputText(source) }}</dd></div>
              <div><dt>来源生产规则</dt><dd>{{ quantityText(source.sourceSelector?.producerRuleId) }} / {{ source.producerVersion || source.producerRuleVersion || source.sourceSelector?.producerRuleVersion || '版本未知' }}</dd></div>
              <div><dt>数量表达及去重</dt><dd>{{ quantityContractText(source) }}</dd></div>
            </dl>
          </details>
        </article>
        <section v-if="configuration.overriddenSources?.length" class="legacy-explanation" data-cell="overridden-sources">
          <p>精确步骤配置已覆盖通用回退；以下旧规则保留追溯，不用于当前步骤来源。</p>
          <p v-for="source in configuration.overriddenSources" :key="source.ruleId">{{ source.ruleName || source.ruleCode }} / {{ source.ruleVersion || source.version || '版本未知' }}</p>
        </section>
        <p v-for="(blocker, index) in configuration.blockers || []" :key="index" class="source-error">{{ reasonLabel(blocker) }}</p>
      </section>
      <p v-else class="source-notice">选择工序后读取该工序的正式来源方案。</p>

      <section v-if="selectedOperationId" class="plan-source-read" data-section="plan-source-read">
        <h5>按计划读取当前步骤</h5>
        <div class="source-fields">
          <label>
            <span>生产计划</span>
            <select v-model="selectedPlanId" :disabled="busy" @change="changePlan">
              <option value="">请选择生产计划</option>
              <option v-for="plan in catalog.productionPlans" :key="plan.id" :value="String(plan.id)">{{ optionLabel(plan) }}</option>
            </select>
          </label>
          <label v-if="matchingSteps.length > 1">
            <span>计划路线步骤</span>
            <select v-model="selectedRoutingStepId" :disabled="busy" @change="loadSources">
              <option value="">请选择本次准确步骤</option>
              <option v-for="step in matchingSteps" :key="step.id" :value="String(step.id)">{{ optionLabel(step) }}</option>
            </select>
          </label>
          <p v-else-if="matchingSteps.length === 1" class="resolved-step">路线步骤：{{ optionLabel(matchingSteps[0]) }}</p>
        </div>
        <p v-if="!context" class="source-notice">{{ contextSelectionNotice }}</p>
        <template v-else>
          <p v-if="context.effectiveVersion?.versionLabel" class="source-notice" data-cell="detail-effective-version">{{ context.effectiveVersion.versionLabel }}</p>
          <p v-if="context.applicability?.resultLabel || context.applicability?.statusLabel" class="source-notice">步骤适用性：{{ context.applicability.resultLabel || context.applicability.statusLabel }}</p>
          <section v-if="conditionalExecutionLabels(context.applicability).length" class="input-preparation" data-section="conditional-execution" data-fact-source="server">
            <h6>条件执行准备</h6>
            <p v-for="(label, index) in conditionalExecutionLabels(context.applicability)" :key="index">{{ label }}</p>
          </section>
          <section v-if="context.quantityPolicy" class="input-preparation" data-section="quantity-policy" data-fact-source="server">
            <h6>投产数量政策</h6>
            <PceBusinessStatus :status-label="context.quantityPolicy.statusLabel" />
            <p v-if="context.quantityPolicy.scopeDeterminationLabel">{{ context.quantityPolicy.scopeDeterminationLabel }}</p>
            <p>计划投产数量：{{ context.quantityPolicy.plannedQuantityReasonLabel }}</p>
            <p>实际产量：{{ context.quantityPolicy.actualQuantityReasonLabel }}</p>
            <p>统计单位：{{ context.quantityPolicy.statisticalUomReference.uomLabel }}；{{ context.quantityPolicy.statisticalUomReference.statusLabel }}</p>
            <p>{{ context.quantityPolicy.capacityIndependenceLabel }}</p>
          </section>
          <section v-if="context.noDateCapacity" class="input-preparation" data-section="detail-no-date-capacity" data-fact-source="server"
            :data-no-date-read-state="readState" :data-no-date-result-hash="context.noDateCapacity.resultHash"
            :data-no-date-assessed-at="context.noDateCapacity.assessedAt">
            <h6>无日期产能与理论用时</h6>
            <PceBusinessStatus :status-label="context.noDateCapacity.statusLabel" />
            <p v-for="(label, key) in context.noDateCapacity.displayLabels" :key="key">{{ noDateDisplayFieldLabel(key) }}：{{ label }}</p>
            <div data-section="detail-no-date-time-references">
              <p>原始时间参考：以下参考值不计入准确总工期，不据此选择时间或形成日期、资源占用。</p>
              <p>路线步骤原始参考：准备 {{ context.noDateCapacity.timeReferences?.step?.preparationDays ?? '未知' }}；转运 {{ context.noDateCapacity.timeReferences?.step?.transferDays ?? '未知' }}；单位 {{ context.noDateCapacity.timeReferences?.step?.timeUnit === 'DAY' ? '天' : '未知' }}。</p>
              <p v-for="reference in context.noDateCapacity.timeReferences?.standardCapacities || []" :key="reference.standardCapacityId">标准产能 {{ reference.standardCapacityId }} 原始参考：准备 {{ reference.preparationDays ?? '未知' }}；转运 {{ reference.transferDays ?? '未知' }}；单位 {{ reference.timeUnit === 'DAY' ? '天' : '未知' }}。</p>
              <p v-if="!context.noDateCapacity.timeReferences?.standardCapacities?.length">标准产能原始参考未提供，准备和转运时间未知。</p>
            </div>
            <template v-if="context.noDateCapacity.capacityMatches.length > 1">
              <article v-for="match in context.noDateCapacity.capacityMatches" :key="`${match.standardCapacityId}:${match.workCenterId || ''}`">
                <p v-for="(label, key) in match.displayLabels" :key="key">{{ noDateDisplayFieldLabel(key) }}：{{ label }}</p>
              </article>
            </template>
            <p v-for="(issue, index) in context.noDateCapacity.blockers" :key="index" class="source-error">{{ reasonLabel(issue) }}</p>
          </section>
          <p v-if="context.sourceConfiguration?.statusLabel">来源方案：{{ context.sourceConfiguration.statusLabel }}</p>
          <section v-if="context.applicability?.formalSourceLabel || context.applicability?.objectApplicability" data-section="formal-applicability-proof" data-fact-source="server">
            <h6>当前计划对象适用性正式依据</h6>
            <p v-if="context.applicability.formalSourceLabel">{{ context.applicability.formalSourceLabel }}</p>
            <p v-if="context.applicability.objectApplicability?.statusLabel">{{ context.applicability.objectApplicability.statusLabel }}</p>
            <details :open="traceExpanded(traceKey('applicability', 'objects'))" @toggle="rememberTraceExpansion(traceKey('applicability', 'objects'), $event)">
              <summary>对象适用性记录与来源追溯</summary>
              <article v-for="item in context.applicability.objectApplicability?.objects || []" :key="item.recordId || item.baselineItemId">
                <p>{{ item.decisionLabel || item.resultLabel || item.statusLabel || item.label || '对象决定说明未提供' }}；记录 {{ item.recordId ?? '未提供' }}；基线项 {{ item.baselineItemId ?? '未提供' }}；设计对象 {{ item.designItemId ?? '未提供' }}；来源事实 {{ item.sourceFactId ?? '未提供' }}；审计 {{ item.auditId ?? '未提供' }}；写入请求 {{ item.writeRequestId ?? '未提供' }}</p>
                <p v-if="item.basis?.decisionReference?.statement">{{ item.basis.decisionReference.statement }}</p>
                <p v-if="item.basis?.decisionReference?.reference">依据出处：{{ item.basis.decisionReference.reference }}</p>
                <p v-if="item.reason">办理说明：{{ item.reason }}</p>
              </article>
            </details>
          </section>
          <section v-if="context.standardCapacityFacts?.length" data-section="current-standard-capacity-facts" data-fact-source="server">
            <h6>工序正式标准产能与适用范围</h6>
            <article v-for="capacity in context.standardCapacityFacts" :key="capacity.id">
              <p>{{ capacity.name }}；{{ quantityText(capacity.quantity) }} {{ capacity.uomLabel || '单位未提供' }}／{{ capacity.timeUnitLabel || '时间单位未提供' }}；基准 {{ quantityText(capacity.timeBasisQuantity) }} {{ capacity.timeUnitLabel || '' }}</p>
              <p>适用产品：{{ capacity.productTypeName || '未提供' }}<span v-if="capacity.productTypeCode">（{{ capacity.productTypeCode }}）</span>；工序：{{ capacity.operationName || '未提供' }}；工作中心 {{ capacity.workCenterId ?? '未提供' }}；生效日期：{{ capacity.effectiveDate || '未提供' }}；{{ capacity.statusLabel }}</p>
            </article>
          </section>
          <section v-if="context.capacitySemantics" class="input-preparation" data-section="capacity-business-semantics" data-fact-source="server">
            <h6>产能业务含义</h6>
            <PceBusinessStatus :status-label="context.capacitySemantics.statusLabel" />
            <p v-if="context.capacitySemantics.sourceStatusLabel">{{ context.capacitySemantics.sourceStatusLabel }}</p>
            <p v-if="context.capacitySemantics.recordPresenceStatusLabel">{{ context.capacitySemantics.recordPresenceStatusLabel }}</p>
            <p v-if="context.capacitySemantics.preparationTransferPolicyLabel">{{ context.capacitySemantics.preparationTransferPolicyLabel }}</p>
            <p v-if="context.capacitySemantics.dependencyPolicyLabel">{{ context.capacitySemantics.dependencyPolicyLabel }}</p>
          </section>
          <section v-if="inputPreparation" class="input-preparation" data-section="operation-input-preparation" data-fact-source="server">
            <h6>当前正式读取状态</h6>
            <dl data-section="current-operation-workload-state">
              <div><dt>投产来源配置</dt><dd>{{ context.sourceConfiguration?.statusLabel || '尚未读取' }}</dd></div>
              <div><dt>正式工序需求</dt><dd>{{ context.formalRequirements?.statusLabel || '尚未读取' }}</dd></div>
              <div><dt>计划已保存投产量</dt><dd>{{ context.savedAllocations?.statusLabel || '尚未读取' }}<span v-if="context.savedAllocations?.persistence?.statusLabel">；{{ context.savedAllocations.persistence.statusLabel }}</span><span v-if="context.savedAllocations?.quantity != null && context.savedAllocations.quantity !== ''">；{{ quantityText(context.savedAllocations.quantity) }} {{ context.savedAllocations.uomLabel || '' }}</span></dd></div>
            </dl>
            <p class="source-notice">当前状态来自本次正式读取；下方记录保留保存时的原文，不覆盖当前来源、需求及分配事实。</p>
            <details data-section="historical-input-preparation" :open="traceExpanded(traceKey('history', 'preparation'))" @toggle="rememberTraceExpansion(traceKey('history', 'preparation'), $event)">
              <summary>记录保存时状态／历史依据</summary>
            <PceBusinessStatus :status-label="inputPreparation.statusLabel" />
            <dl>
              <div><dt>投入标准</dt><dd>{{ inputPreparation.inputStandardStatusLabel }}</dd></div>
              <div><dt>记录保存时产能裁决</dt><dd>{{ inputPreparation.capacityMeasurementStatusLabel }}</dd></div>
              <div v-if="inputPreparation.capacityBusinessValue != null"><dt>准备记录业务裁决值</dt><dd>{{ quantityText(inputPreparation.capacityBusinessValue) }}</dd></div>
              <div v-if="inputPreparation.quantityPolicy && inputPreparation.standardCapacityReference"><dt>所引用正式标准产能</dt><dd>{{ quantityText(inputPreparation.standardCapacityReference.quantity) }} {{ inputPreparation.standardCapacityReference.uomLabel || '单位未提供' }}</dd></div>
              <div v-else><dt>正式标准产能数量</dt><dd>{{ quantityText(inputPreparation.capacityQuantity) }}</dd></div>
              <div v-if="inputPreparation.formalRuleStatusLabel"><dt>正式规则</dt><dd>{{ inputPreparation.formalRuleStatusLabel }}</dd></div>
            </dl>
            <p v-if="inputPreparation.capacityResolution?.statusLabel" class="source-notice">{{ inputPreparation.capacityResolution.statusLabel }}</p>
            <template v-if="inputPreparation.capacityTristatePrinciples">
              <p><strong>正数：</strong>{{ inputPreparation.capacityTristatePrinciples.positive?.statusLabel }}</p>
              <p><strong>0：</strong>{{ inputPreparation.capacityTristatePrinciples.zero?.statusLabel }}</p>
              <p><strong>空值：</strong>{{ inputPreparation.capacityTristatePrinciples.blank?.statusLabel }}</p>
            </template>
            <article v-for="(entry, index) in inputPreparation.businessBasisPresentation || []" :key="index" class="preparation-basis">
              <PceBusinessStatus :status-label="entry.statusLabel" />
              <p><strong>业务依据原答复：</strong>{{ entry.exactStatement }}</p>
              <p>出处：{{ entry.reference }}</p>
              <p>适用范围：{{ inputPreparation.scopeLabel }}</p>
            </article>
            <p v-if="inputPreparation.remainingItems?.length">具体待维护项：</p>
            <ul v-if="inputPreparation.remainingItems?.length">
              <li v-for="(item, index) in inputPreparation.remainingItems" :key="index">{{ item.statusLabel }}</li>
            </ul>
            <p v-if="inputPreparation.readinessStatusLabel" class="source-notice">{{ inputPreparation.readinessStatusLabel }}</p>
            </details>
          </section>
          <div class="quantity-states">
            <article v-for="card in quantityCards" :key="card.key" :data-cell="card.key">
              <h6>{{ card.label }}</h6>
              <PceBusinessStatus :status-label="card.facts?.statusLabel || '尚未读取'" />
              <template v-if="card.key === 'formalRequirements'">
                <p class="source-notice" data-cell="requirement-view-scope">详情计划：{{ selectedPlan ? optionLabel(selectedPlan) : '未选择生产计划' }}；工序：{{ selectedOperation ? optionLabel(selectedOperation) : '未选择工序' }}。</p>
                <p v-for="(quantity, index) in card.facts?.quantitySummary || []" :key="index" class="quantity" data-cell="formal-requirement-quantity-summary">{{ quantityText(quantity.quantity) }} {{ quantity.uomLabel || '单位未提供' }}</p>
              </template>
              <p v-if="card.facts?.persistence?.statusLabel" data-cell="persistence-status">{{ card.facts.persistence.statusLabel }}</p>
              <p v-if="card.facts?.persistence?.quantityStatusLabel" data-cell="persistence-quantity-status">{{ card.facts.persistence.quantityStatusLabel }}</p>
              <p v-if="card.key === 'savedAllocations' && card.facts?.statusCode !== 'NOT_APPLICABLE' && card.facts?.quantity != null && card.facts.quantity !== ''" class="quantity">{{ quantityText(card.facts.quantity) }} {{ card.facts.uomLabel || '' }}</p>
              <p v-else-if="card.key !== 'savedAllocations' && card.facts?.statusCode !== 'NOT_APPLICABLE' && card.facts?.statusCode !== 'WAITING_TRIGGER' && card.facts?.statusCode !== 'NOT_SEPARATELY_MEASURED' && !card.facts?.persistence && (!card.facts || !Array.isArray(card.facts.items) || card.facts.items.length === 0)" class="quantity">数量未知</p>
              <section v-for="(item, index) in card.facts?.statusCode === 'NOT_APPLICABLE' ? [] : card.facts?.items || []" :key="item.allocationId || item.operationRequirementId || item.sourceFactId || index" class="quantity-item">
                <p v-if="card.key !== 'savedAllocations'" class="quantity">{{ quantityText(item.quantity ?? item.workloadQuantity ?? item.requirementQuantity) }} {{ item.uomLabel || '' }}</p>
                <p v-if="item.statusLabel">{{ item.statusLabel }}</p>
                <p v-if="item.objectLabel || item.designItemLabel">{{ item.objectLabel || item.designItemLabel }}</p>
                <details :open="traceExpanded(traceKey(card.key, item.allocationId || item.operationRequirementId || item.sourceFactId || index))" @toggle="rememberTraceExpansion(traceKey(card.key, item.allocationId || item.operationRequirementId || item.sourceFactId || index), $event)">
                  <summary>来源与保存追溯</summary>
                  <dl>
                    <div v-if="item.sourceFactId != null"><dt>来源事实</dt><dd>{{ item.sourceFactId }}</dd></div>
                    <div v-if="item.sourceCalculationId != null"><dt>来源核算</dt><dd>{{ item.sourceCalculationId }}</dd></div>
                    <div v-if="item.operationRequirementId != null"><dt>正式工序需求</dt><dd>{{ item.operationRequirementId }}</dd></div>
                    <div v-if="item.allocationId != null"><dt>已保存分配</dt><dd>{{ item.allocationId }}</dd></div>
                    <div v-if="item.auditId != null"><dt>审计</dt><dd>{{ item.auditId }}</dd></div>
                    <div v-if="item.ruleCode || item.ruleId"><dt>来源规则</dt><dd>{{ item.ruleCode || item.ruleId }} · {{ item.ruleVersion }}</dd></div>
                    <template v-if="item.objectCoverageProof">
                      <div data-cell="object-coverage-proof"><dt>覆盖证明</dt><dd>{{ item.objectCoverageProof.statusLabel }}</dd></div>
                      <div><dt>历史快照</dt><dd>{{ item.objectCoverageProof.snapshotStatusLabel }}</dd></div>
                      <template v-if="item.objectCoverageProof.coverage">
                        <div><dt>设计对象</dt><dd>{{ item.objectCoverageProof.coverage.designItemIds.join('、') }}</dd></div>
                        <div><dt>基线项</dt><dd>{{ item.objectCoverageProof.coverage.baselineItemIds.join('、') }}</dd></div>
                        <div><dt>原始输入事实</dt><dd>{{ item.objectCoverageProof.coverage.inputFactIds.join('、') }}</dd></div>
                      </template>
                    </template>
                  </dl>
                </details>
              </section>
              <p v-for="(blocker, index) in card.facts?.blockers || []" :key="index" class="source-error">{{ reasonLabel(blocker) }}</p>
            </article>
          </div>
          <p v-for="(blocker, index) in context.blockers || []" :key="index" class="source-error">{{ reasonLabel(blocker) }}</p>
        </template>
      </section>

      <section v-if="selectedOperationId" class="source-maintenance" data-section="source-maintenance">
        <h5>来源方案草稿与校验</h5>
        <p>从正式目录选择来源与数量合同，校验草稿不会生成工序需求或保存计划分配。</p>
        <p v-if="mode !== 'maintain'" class="source-notice">当前为只读查看，可选择草稿并校验；正式办理仍需维护模式及完整执行资格。</p>
        <p v-if="!configureAuthorization.allowed" class="source-error" data-cell="source-write-blocked">{{ configureAuthorization.statusLabel || configureAuthorization.reason || '当前账号不具备正式来源方案保存条件。' }}</p>
        <p v-for="(blocker, index) in configureAuthorization.blockers || []" :key="index" class="source-error">{{ reasonLabel(blocker) }}</p>
        <form @submit.prevent="saveSource">
          <fieldset :disabled="busy">
            <div class="source-fields">
              <label v-if="hasCapacityModes">
                <span>产能承接方式</span>
                <select v-model="form.capacityMode" required @change="refreshResourceSelection">
                  <option value="">请选择产能承接方式</option>
                  <option v-for="option in capacityModes" :key="option.value" :value="option.value">{{ option.statusLabel }}</option>
                </select>
              </label>
              <label v-for="field in visibleConfigurationFields" :key="field.key">
                <span>{{ field.label }}</span>
                <select v-model="form[field.key]" required @change="refreshResourceSelection">
                  <option value="">请选择{{ field.label }}</option>
                  <option v-for="row in optionsFor(field.key)" :key="row.id" :value="String(row.id)">{{ optionLabel(row) }}</option>
                </select>
              </label>
              <label>
                <span>来源条件维护方式</span>
                <select :value="form.sourceSelectorMode || 'CATALOG'" @change="form.sourceSelectorMode = $event.target.value">
                  <option value="CATALOG">选择已有正式来源条件</option>
                  <option value="EXPLICIT_CONDITIONS">明确维护本方案来源条件</option>
                </select>
              </label>
              <label v-if="hasTraceOptions && !explicitSelectorMode">
                <span>正式来源条件</span>
                <select :value="selectedTraceOption?.key || ''" :disabled="traceOptions.length < 2" required @change="form.traceOptionKey = $event.target.value">
                  <option value="">请选择本次准确来源条件</option>
                  <option v-for="option in traceOptions" :key="option.key" :value="option.key">{{ option.statusLabel || option.label || '正式来源条件说明未提供' }}</option>
                </select>
              </label>
              <section v-if="explicitSelectorMode" class="explicit-source-conditions" data-section="explicit-source-selector">
                <p>逐项声明所选正式生产者的追溯条件；不按现有Fact猜测条件，不把空条件当作通配授权。</p>
                <div v-for="(condition, index) in explicitTraceRows" :key="index" class="source-fields">
                  <label><span>条件字段</span><input v-model.trim="condition.key" required /></label>
                  <label><span>条件值类型</span><select v-model="condition.valueType" @change="condition.value = ''"><option value="string">文本</option><option value="integer">整数</option><option value="boolean">是／否</option><option value="null">空值</option></select></label>
                  <label v-if="condition.valueType !== 'null'"><span>条件值</span><select v-if="condition.valueType === 'boolean'" v-model="condition.value" required><option value="">请选择</option><option value="true">是</option><option value="false">否</option></select><input v-else v-model="condition.value" :inputmode="condition.valueType === 'integer' ? 'numeric' : 'text'" /></label>
                  <button type="button" class="secondary" @click="explicitTraceRows.splice(index, 1)">移除条件</button>
                </div>
                <button type="button" class="secondary" @click="explicitTraceRows.push({ key:'',valueType:'string',value:'' })">新增来源条件</button>
                <p v-if="explicitTraceState.error" class="source-error">{{ explicitTraceState.error }}</p>
              </section>
              <template v-if="hasConfigurationOptions">
                <label>
                  <span>数量合同</span>
                  <select v-model="form.quantityBasis" required @change="refreshResourceSelection">
                    <option value="">请选择正式数量合同</option>
                    <option v-for="option in quantityContracts" :key="option.code" :value="option.code">{{ option.statusLabel || option.label }}</option>
                  </select>
                </label>
                <label v-if="selectedQuantityContract?.requiresBasisQuantity">
                  <span>正式基准数量</span><input v-model.trim="form.basisQuantity" inputmode="decimal" required />
                </label>
                <label v-if="selectedQuantityContract?.requiresBasisUomId">
                  <span>正式基准单位</span>
                  <select v-model="form.basisUomId" required>
                    <option value="">请选择正式基准单位</option>
                    <option v-for="unit in catalog.units || []" :key="unit.id" :value="String(unit.id)">{{ optionLabel(unit) }}</option>
                  </select>
                </label>
                <label>
                  <span>单输入数量表达式</span><input v-model.trim="form.expression" required />
                </label>
                <label>
                  <span>规则适用范围</span>
                  <select v-model="form.scopeCode" required @change="refreshResourceSelection">
                    <option value="">请选择正式范围</option>
                    <option v-for="option in scopeContracts" :key="option.code" :value="option.code">{{ option.statusLabel || option.label }}</option>
                  </select>
                </label>
                <label v-if="selectedScopeContract?.requiresRoutingContext">
                  <span>准确路线步骤</span>
                  <select v-model="form.routingContextKey" required>
                    <option value="">请选择正式路线步骤</option>
                    <option v-for="routing in routingOptions" :key="routingKey(routing)" :value="routingKey(routing)">{{ optionLabel(routing) }}</option>
                  </select>
                </label>
              </template>
              <label><span>方案编码</span><input v-model.trim="form.ruleCode" required maxlength="80" /></label>
              <label><span>方案名称</span><input v-model.trim="form.ruleName" required maxlength="200" /></label>
              <label><span>版本</span><input v-model.trim="form.version" required maxlength="40" /></label>
              <label><span>生效日期</span><input v-model="form.effectiveFrom" type="date" required /></label>
              <label v-if="hasConfigurationOptions"><span>失效日期（可选）</span><input v-model="form.effectiveTo" type="date" /></label>
            </div>
            <p v-if="selectedProducer" class="source-notice">来源定义：{{ optionLabel(selectedProducer) }}；{{ selectedProducer.canonicalField || selectedProducer.sourceCanonicalField || '字段由正式生产规则确定' }}；{{ selectedProducer.uomLabel || '单位由正式生产规则确定' }}</p>
            <p v-if="selectedProducer?.sourceSemantics?.statusLabel" class="source-notice">{{ selectedProducer.sourceSemantics.statusLabel }}</p>
            <details v-if="selectedProducer?.sourceSemantics?.groupKeys?.length" :open="traceExpanded(traceKey('producer', selectedProducer.id))" @toggle="rememberTraceExpansion(traceKey('producer', selectedProducer.id), $event)">
              <summary>来源汇总与去重依据</summary>
              <p>{{ selectedProducer.sourceSemantics.groupKeys.join('、') }}</p>
            </details>
            <p v-if="hasConfigurationOptions" class="source-notice">{{ catalog.expressionContract?.statusLabel }} 可用输入：{{ catalog.expressionContract?.inputAlias }}。相同计量单位不能代替投入口径证明；明细、汇总及派生面积仍按正式来源去重。</p>
            <p v-if="catalog.capacitySemanticVerification?.statusLabel" class="source-notice">{{ catalog.capacitySemanticVerification.statusLabel }}</p>
            <p v-if="selectedCapacityMode?.requiresPlanPreparation" class="source-notice">本来源方案可复用；每次运行仍须核验所选计划和步骤的有效精确裁决。请先选择上方生产计划及准确步骤，裁决不会保存为企业永久豁免。</p>
            <p v-for="(supported, index) in catalog.supportedScopes || []" :key="`supported-${index}`" class="source-notice">{{ reasonLabel(supported) }}</p>
            <p v-for="(priority, index) in catalog.matchingPriorityLabels || []" :key="`priority-${index}`" class="source-notice">{{ reasonLabel(priority) }}</p>
            <p v-for="(unsupported, index) in catalog.unsupportedScopes || []" :key="index" class="source-notice">{{ reasonLabel(unsupported) }}</p>
            <p v-if="hasTraceOptions && !explicitSelectorMode && !selectedTraceOption" class="source-notice">{{ traceOptions.length ? '存在多个正式来源条件，请明确选择，系统不采用首条。' : '当前产品类型没有匹配的正式来源条件，尚不能保存。' }}</p>
            <label class="source-reason"><span>办理原因（正式保存必填）</span><textarea v-model.trim="form.reason" /></label>
            <div class="draft-actions">
              <button v-if="hasConfigurationOptions" type="button" :disabled="!canPreview" @click="previewSourceConfiguration">{{ previewState === 'loading' ? '正在只读校验…' : '校验并预览草稿' }}</button>
              <button v-if="mode === 'maintain'" type="submit" :disabled="!canSave">{{ saving ? '正在保存并读回…' : '保存并发布来源方案' }}</button>
            </div>
          </fieldset>
        </form>
        <p v-if="previewState === 'read_failed'" class="source-error" role="alert">{{ previewError }} 当前草稿尚未取得有效校验结果。</p>
        <section v-if="currentPreview" class="draft-preview" data-section="configuration-draft-preview">
          <PceBusinessStatus :status-label="currentPreview.configurationPreview.statusLabel" />
          <p>仅校验本次草稿；未生成正式需求或保存分配。</p>
          <div class="quantity-states">
            <article v-for="card in previewCards" :key="card.key">
              <h6>{{ card.label }}</h6>
              <PceBusinessStatus :status-label="card.facts?.statusLabel || '尚未读取'" />
              <p v-if="!card.facts?.items?.length">{{ card.key === 'expressionOutputs' ? '预计输出未知' : '来源数量未知' }}</p>
              <p v-for="(item, index) in card.facts?.items || []" :key="item.sourceFactId || index">{{ quantityText(card.key === 'expressionOutputs' ? item.outputQuantity : item.sourceQuantity ?? item.quantity) }} {{ item.uomLabel || '' }}<span v-if="item.statusLabel">；{{ item.statusLabel }}</span></p>
            </article>
          </div>
          <p v-for="(issue, index) in previewIssues" :key="index" class="source-error">{{ reasonLabel(issue) }}</p>
        </section>
      </section>
    </template>
    <p v-if="saveMessage" :class="saveReadbackFailed ? 'source-error' : 'source-notice'" role="status">{{ saveMessage }}</p>
  </section>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { pdeApi } from '@/api/pde.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { explicitTraceConditions } from '@/meta/runtime/sourceFormatMaintenanceForm.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import { createComponentReadLifecycle, componentReadUrl } from '@/meta/runtime/componentReadLifecycle.js'
import { createOperationWorkloadViewMemory, reconcileOperationWorkloadView } from '@/meta/runtime/operationWorkloadViewContext.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY, assertSafeDiagnosticPayload } from '@/meta/runtime/pageObservabilityActions.js'

const props = defineProps({
  operations: { type: Array, default: () => [] },
  mode: { type: String, default: 'view' },
  refreshKey: { type: [String, Number], default: 0 },
  invalidateKey: { type: [String, Number], default: 0 },
  parentReadStatus: { type: String, default: 'loaded' },
})
const emit = defineEmits(['saved'])
const CONTRACT = 'PCE-OPERATION-WORKLOAD-SOURCE-V1'
const viewIdentity = () => { const identity = readTabIdentity() || {}; return { userId: identity.userId, companyId: identity.companyId, authEpoch: getTabAuthEpoch() } }
const viewMemory = createOperationWorkloadViewMemory({ scope: viewIdentity })
let viewOwnerScope = JSON.stringify(viewIdentity())
const rememberedView = viewMemory.read()
const selectedOperationId = ref(rememberedView?.selectedOperationId || '')
const selectedPlanId = ref(rememberedView?.selectedPlanId || '')
const selectedRoutingStepId = ref(rememberedView?.selectedRoutingStepId || '')
const selectedRoutePlanId = ref(rememberedView?.selectedRoutePlanId || '')
const routeExpandedStepIds = ref(rememberedView?.routeExpandedStepIds || [])
const expandedTraceKeys = ref(rememberedView?.expandedTraceKeys || [])
const viewContextNotices = ref([])
const panelElement = ref(null)
let viewScrollTop = rememberedView?.scrollTop || 0
let viewHasCompletedRead = false
let navigationReadDepth = 0
let identityChangeNotice = ''
let restoringView = false
const routeFacts = ref(null)
const routeReadState = ref('idle')
const routeReadError = ref('')
const serverFacts = ref(null)
const readState = ref('idle')
const readError = ref('')
const saving = ref(false)
const saveMessage = ref('')
const saveReadbackFailed = ref(false)
const previewFacts = ref(null)
const previewState = ref('idle')
const previewError = ref('')
let readSequence = 0
let routeReadSequence = 0
let previewSequence = 0
let sourceScopeEpoch = 0
let routeScopeEpoch = 0
let sourceLoadOwner = null
let routeLoadOwner = null
let sourceRefreshOwner = null
const readDiagnostics = ref([])
const readScope = () => {
  const identity = readTabIdentity() || {}
  return JSON.stringify([getTabAuthEpoch(), identity.userId ?? null, identity.companyId ?? null,
    props.invalidateKey, props.refreshKey])
}
const reads = createComponentReadLifecycle({ context: readScope, changed: rows => { readDiagnostics.value = rows } })
const form = reactive({ productTypeId: '', modeId: '', producerRuleId: '', traceOptionKey: '', sourceSelectorMode:'CATALOG', workCenterId: '', standardCapacityId: '', capacityMode: '', ruleCode: '', ruleName: '', version: '', effectiveFrom: '', effectiveTo: '', quantityBasis: '', basisQuantity: '', basisUomId: '', expression: '', scopeCode: '', routingContextKey: '', reason: '' })
const explicitTraceRows = ref([{ key:'',valueType:'string',value:'' }])
const explicitSelectorMode = computed(() => form.sourceSelectorMode === 'EXPLICIT_CONDITIONS')
const explicitTraceState = computed(() => {
  try { return { trace:explicitTraceConditions(explicitTraceRows.value),error:'' } }
  catch (error) { return { trace:null,error:error.message } }
})
const emptyCatalog = Object.freeze({ producers: [], manufacturingModes: [], productTypes: [], standardCapacities: [], workCenters: [], productionPlans: [], configureAuthorization: {} })
const catalog = computed(() => serverFacts.value?.catalog || emptyCatalog)
const operationOptions = computed(() => serverFacts.value?.operations || props.operations)
const configuration = computed(() => context.value?.sourceConfiguration || serverFacts.value?.configuration || null)
const configureAuthorization = computed(() => catalog.value.configureAuthorization || {})
const busy = computed(() => saving.value || readState.value === 'loading' || routeReadState.value === 'loading'
  || props.parentReadStatus !== 'loaded')
const hasConfigurationOptions = computed(() => Array.isArray(catalog.value.quantityContracts) && Boolean(catalog.value.expressionContract))
const hasCapacityModes = computed(() => Array.isArray(catalog.value.capacityModes) && catalog.value.capacityModes.length > 0)
const capacityModes = computed(() => catalog.value.capacityModes || [])
const selectedCapacityMode = computed(() => capacityModes.value.find(option => option.value === form.capacityMode))
const hasRequiredPreparationContext = computed(() => !selectedCapacityMode.value?.requiresPlanPreparation
  || Boolean(selectedPlanId.value && matchingSteps.value.some(row => String(row.id) === selectedRoutingStepId.value)))
const quantityContracts = computed(() => catalog.value.quantityContracts || [])
const selectedQuantityContract = computed(() => quantityContracts.value.find(option => option.code === form.quantityBasis))
const scopeContracts = computed(() => catalog.value.scopeContracts || [])
const selectedScopeContract = computed(() => scopeContracts.value.find(option => option.code === form.scopeCode))
const selectedOperation = computed(() => operationOptions.value.find(row => String(row.id) === selectedOperationId.value))
const operationUomId = computed(() => selectedOperation.value?.calculation_uom_id ?? selectedOperation.value?.calculationUomId ?? selectedOperation.value?.uomId)
const routingOptions = computed(() => (catalog.value.routingContexts || []).filter(row =>
  String(row.operationId) === selectedOperationId.value
  && (!Array.isArray(row.productTypeIds) || row.productTypeIds.some(id => String(id) === form.productTypeId))))
const selectedRoutingContext = computed(() => routingOptions.value.find(row => routingKey(row) === form.routingContextKey))
const selectedPlan = computed(() => catalog.value.productionPlans.find(row => String(row.id) === selectedPlanId.value))
const selectedRoutePlan = computed(() => catalog.value.productionPlans.find(row => String(row.id) === selectedRoutePlanId.value))
const matchingSteps = computed(() => (selectedPlan.value?.routingSteps || []).filter(row => String(row.operationId) === selectedOperationId.value))
const selectedProducer = computed(() => catalog.value.producers.find(row => String(row.id) === form.producerRuleId))
const hasTraceOptions = computed(() => Array.isArray(selectedProducer.value?.traceOptions))
const traceOptions = computed(() => (hasTraceOptions.value ? selectedProducer.value.traceOptions : []).filter(option =>
  String(option.productTypeId) === form.productTypeId && typeof option.key === 'string' && option.key
  && option.traceEquals && typeof option.traceEquals === 'object' && !Array.isArray(option.traceEquals)))
const selectedTraceOption = computed(() => traceOptions.value.length === 1 ? traceOptions.value[0]
  : traceOptions.value.find(option => option.key === form.traceOptionKey))
const draftIdentity = computed(() => canonicalSnapshot({ companyId: catalog.value.companyId,
  operationId: selectedOperationId.value, planId: selectedPlanId.value, stepId: selectedRoutingStepId.value,
  payload: sourcePayload(), reason: form.reason, scopeCode: form.scopeCode,
  explicitConditions: explicitSelectorMode.value ? explicitTraceRows.value : null,
  producerHash: selectedProducer.value?.specificationHash, producerVersion: selectedProducer.value?.version }))
const currentPreview = computed(() => previewFacts.value?.draftIdentity === draftIdentity.value ? previewFacts.value : null)
const previewCards = computed(() => [
  { key: 'sourceQuantities', label: '正式来源工程量', facts: currentPreview.value?.sourceQuantities },
  { key: 'expressionOutputs', label: '安全表达式预计输出', facts: currentPreview.value?.expressionOutputs },
])
const previewIssues = computed(() => {
  const seen = new Set()
  return [...(currentPreview.value?.configurationPreview?.conflicts || []),
    ...(currentPreview.value?.configurationPreview?.blockers || []), ...(currentPreview.value?.blockers || [])].filter(issue => {
    const identity = canonicalSnapshot(issue)
    if (seen.has(identity)) return false
    seen.add(identity)
    return true
  })
})
const context = computed(() => selectedPlanId.value && selectedRoutingStepId.value ? serverFacts.value?.context || null : null)
const inputPreparation = computed(() => context.value?.inputPreparation || null)
const routeConfiguration = computed(() => routeFacts.value?.routeConfiguration || null)
const diagnosticCopyMessage = ref('')
const strictFacts = computed(() => ({ factSource: 'server', currentStateSource: 'server',
  passed: readState.value === 'read_failed' || routeReadState.value === 'read_failed' ? false : null,
  route: { readState: routeReadState.value, scope: routeConfiguration.value?.scope || null,
    noDateReadState: routeConfiguration.value?.noDateCapacityIncluded === true ? routeReadState.value
      : routeReadState.value === 'read_failed' ? 'read_failed' : 'not_read',
    noDateCapacityIncluded: routeConfiguration.value?.noDateCapacityIncluded ?? null,
    summary: routeConfiguration.value?.noDateCapacitySummary || null,
    rows: routeConfiguration.value?.rows.map(row => ({ routingStepId: row.routingStepId,
      noDateCapacity: row.noDateCapacity || null })) || null },
  detail: { readState: readState.value, scope: context.value?.scope || null,
    noDateReadState: context.value?.noDateCapacityIncluded === true ? readState.value
      : readState.value === 'read_failed' ? 'read_failed' : 'not_read',
    noDateCapacity: context.value?.noDateCapacity || null } }))
const observability = typeof inject === 'function' ? inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null) : null
const observabilityProvider = { factOwner: 'foundation-formal-operations', refresh: refreshSourceFacts, buildDiagnostics }
observability?.register?.(observabilityProvider)
const routeRows = computed(() => (routeConfiguration.value?.rows || []).map(row => {
  const sources = row.sourceConfiguration?.sources || []
  const review = row.workloadReview
  const requirementQuantityText = (review.formalRequirementQuantitySummary || []).map(quantity =>
    `${quantityText(quantity.quantity)} ${quantity.uomLabel || '单位未提供'}`).join('；')
  return { ...row, stepLabel: `${row.sequence} / ${row.operationName}`,
    processingText: `${review.applicabilityLabel}；${review.processingLabel}`,
    sourceBusinessLabel: review.sourceBusinessLabel,
    sourceRuleText: serverDisplayLabel(review, 'sourceRuleDisplayLabel', sources.map(source => `${source.ruleName || source.ruleCode} / ${source.ruleVersion || source.version || ''}`).join('；') || '尚无正式来源规则'),
    sourceInputText: serverDisplayLabel(review, 'sourceInputDisplayLabel', sources.map(sourceInputText).join('；') || '正式来源字段及生产版本未知'),
    quantityContractText: serverDisplayLabel(review, 'quantityContractDisplayLabel', sources.map(quantityContractText).join('；') || '数量表达及去重口径未知'),
    formalRequirementLabel: serverDisplayLabel(review, 'formalRequirementDisplayLabel', `${requirementQuantityText ? `${requirementQuantityText}；` : ''}${review.formalRequirementStatusLabel}；${review.formalRequirementPersistenceLabel || recordCountText(review.formalRequirementCount)}`),
    savedQuantityText: serverDisplayLabel(review, 'savedQuantityDisplayLabel', review.savedQuantity == null || review.savedQuantity === '' ? review.allocationPersistenceLabel || review.allocationStatusLabel : `${quantityText(review.savedQuantity)}${review.uomLabel ? ` ${review.uomLabel}` : ''}`),
    savedAllocationLabel: serverDisplayLabel(review, 'allocationDisplayLabel', `${review.allocationStatusLabel}；${review.allocationPersistenceLabel || recordCountText(review.allocationCount)}`),
    coverageStatusLabel: review.coverageStatusLabel,
    noDateCapacityLabel: row.noDateCapacity?.displayLabels.capacityLabel || '尚未读取无日期产能，当前结论未知',
    noDateTimeLabel: row.noDateCapacity?.displayLabels.totalDaysLabel || '理论用时未知',
    blockerText: review.blockers.map(reasonLabel).join('；'),
  }
}))
const routeListContract = createPceEnterpriseListContract({ pageCode: 'operation-workload-route-overview',
  pageType: 'list', title: '计划路线投产量总表', moduleCode: 'PDE' })
// PceEnterpriseListTable owns the built-in PceEnterpriseAdvancedFilter and scrolling.
const routeFilterSchema = Object.freeze([
  { field: 'operationName', label: '工序', filterType: 'text' },
  { field: 'processingText', label: '投产适用性／处理方式', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'sourceBusinessLabel', label: '正式投产来源口径', filterType: 'text' },
  { field: 'formalRequirementLabel', label: '需求保存状态', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'savedAllocationLabel', label: '分配保存状态', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'coverageStatusLabel', label: '对象覆盖', filterType: 'select', optionsProvider: 'current_result' },
])
const routeExportColumns = Object.freeze([
  { field: 'sequence', label: '路线序位' }, { field: 'operationName', label: '工序' },
  { field: 'processingText', label: '投产适用性／处理方式' }, { field: 'sourceBusinessLabel', label: '正式投产来源口径' },
  { field: 'formalRequirementLabel', label: '正式需求量／保存状态／记录数' }, { field: 'savedQuantityText', label: '计划已保存投产量／单位' },
  { field: 'savedAllocationLabel', label: '分配保存状态／记录数' }, { field: 'coverageStatusLabel', label: '对象覆盖' },
  { field: 'blockerText', label: '真实缺项' },
])
const routeRuntime = usePceEnterpriseListRuntime({ rows: routeRows, filterSchema: routeFilterSchema,
  pageCode: 'operation-workload-route-overview', searchFields: [...routeExportColumns.map(column => column.field), 'noDateCapacityLabel', 'noDateTimeLabel'],
  exportFileName: () => `计划路线投产量-${selectedRoutePlanId.value}.csv`,
  exportColumns: () => routeConfiguration.value?.rows.some(row => row.noDateCapacity) ? [...routeExportColumns,
    { field: 'noDateCapacityLabel', label: '无日期产能核对' }, { field: 'noDateTimeLabel', label: '理论用时／时间边界' }] : routeExportColumns })
const { selectedRows: routeSelectedRows, quickSearch: routeQuickSearch, appliedSearch: routeAppliedSearch,
  advancedVisible: routeAdvancedVisible, filters: routeFilters, tableRef: routeTableRef,
  activeFilterCount: routeActiveFilterCount, sortText: routeSortText, filteredRows: routeFilteredRows,
  clearFilters: routeClearFilters, clearSort: routeClearSort, clearSelection: routeClearSelection,
  handleSort: routeHandleSort, exportCurrent: routeExportCurrent } = routeRuntime
const quantityCards = computed(() => [
  { key: 'sourceCandidates', label: '匹配的来源工程量', facts: context.value?.sourceCandidates },
  { key: 'formalRequirements', label: '正式工序需求', facts: context.value?.formalRequirements },
  { key: 'savedAllocations', label: '计划已保存负荷', facts: context.value?.savedAllocations },
])
const configurationFields = Object.freeze([
  { key: 'productTypeId', label: '产能产品类型' }, { key: 'modeId', label: '制造模式' },
  { key: 'producerRuleId', label: '来源生产规则' }, { key: 'workCenterId', label: '工作中心' },
  { key: 'standardCapacityId', label: '标准产能' },
])
const visibleConfigurationFields = computed(() => configurationFields.filter(field =>
  field.key !== 'standardCapacityId' || selectedCapacityMode.value?.requiresStandardCapacity !== false))
const contextSelectionNotice = computed(() => {
  if (!selectedPlanId.value) return '选择生产计划后，按其固定路线读取准确步骤。'
  if (matchingSteps.value.length > 1 && !selectedRoutingStepId.value) return '该计划的同一工序有多个步骤，请选择本次准确步骤。'
  if (matchingSteps.value.length === 0) return '该计划没有可选的对应工序步骤；尚未读取步骤数量。'
  return '当前步骤尚未返回来源、需求与已保存负荷。'
})

function navigationSnapshot() {
  return { selectedOperationId: selectedOperationId.value, selectedPlanId: selectedPlanId.value,
    selectedRoutingStepId: selectedRoutingStepId.value, selectedRoutePlanId: selectedRoutePlanId.value,
    routeExpandedStepIds: routeExpandedStepIds.value, expandedTraceKeys: expandedTraceKeys.value, scrollTop: viewScrollTop }
}
function rememberView() {
  if (!restoringView && viewOwnerScope === JSON.stringify(viewIdentity())) viewMemory.write(navigationSnapshot())
}
function viewScrollOwner() {
  let element = panelElement.value?.parentElement
  while (element && element !== globalThis.document?.body && element !== globalThis.document?.documentElement) {
    const style = globalThis.window?.getComputedStyle?.(element)
    if (/(auto|scroll)/.test(style?.overflowY || '') && element.scrollHeight > element.clientHeight + 1) return element
    element = element.parentElement
  }
  return null
}
function currentViewPosition() {
  const owner = viewScrollOwner()
  const top = owner ? owner.scrollTop : globalThis.window?.scrollY
  return Number.isFinite(top) ? Math.max(0, top) : null
}
function rememberViewPosition(event) {
  if (!viewHasCompletedRead || busy.value || navigationReadDepth > 0) return
  const owner = viewScrollOwner()
  if (event?.target && owner && event.target !== owner) return
  const top = owner ? owner.scrollTop : globalThis.window?.scrollY
  if (Number.isFinite(top)) viewScrollTop = top
  rememberView()
}
function applyNavigation(value) {
  restoringView = true
  selectedOperationId.value = value.selectedOperationId || ''
  selectedPlanId.value = value.selectedPlanId || ''
  selectedRoutingStepId.value = value.selectedRoutingStepId || ''
  selectedRoutePlanId.value = value.selectedRoutePlanId || ''
  routeExpandedStepIds.value = value.routeExpandedStepIds || []
  expandedTraceKeys.value = value.expandedTraceKeys || []
  restoringView = false
}
function ensureViewIdentity() {
  const currentScope = JSON.stringify(viewIdentity())
  if (currentScope === viewOwnerScope) return
  viewOwnerScope = currentScope
  applyNavigation({})
  viewScrollTop = 0
  viewHasCompletedRead = false
  identityChangeNotice = '当前账号、公司或登录上下文已变化，原查看选择不再恢复；请按当前正式权限重新选择。'
  viewContextNotices.value = [identityChangeNotice]
  rememberView()
}
function traceKey(kind, recordId) {
  return JSON.stringify([selectedOperationId.value, selectedPlanId.value, selectedRoutingStepId.value, kind, String(recordId)])
}
function traceExpanded(key) { return expandedTraceKeys.value.includes(key) }
function rememberTraceExpansion(key, event) {
  if (readState.value !== 'loaded') return
  expandedTraceKeys.value = event.target.open ? [...new Set([...expandedTraceKeys.value, key])]
    : expandedTraceKeys.value.filter(item => item !== key)
  rememberViewPosition()
}
function rememberRouteExpansion(row, expandedRows) {
  if (routeReadState.value !== 'loaded') return
  routeExpandedStepIds.value = Array.isArray(expandedRows) ? expandedRows.map(item => String(item.routingStepId))
    : expandedRows ? [...new Set([...routeExpandedStepIds.value, String(row.routingStepId)])]
      : routeExpandedStepIds.value.filter(key => key !== String(row.routingStepId))
  rememberViewPosition()
}
async function restoreViewPosition(scope, top = viewScrollTop) {
  await nextTick()
  if (scope !== readScope()) return
  viewScrollTop = top
  const owner = viewScrollOwner()
  ;(owner || globalThis.window)?.scrollTo?.({ top: viewScrollTop, behavior: 'instant' })
  viewHasCompletedRead = true
  rememberView()
}
function preserveViewPosition(read, enabled, isCurrent = () => true, useRememberedPosition = false) {
  const scope = readScope()
  const top = enabled ? useRememberedPosition ? viewScrollTop : currentViewPosition() : null
  if (top === null) return read()
  navigationReadDepth += 1
  return (async () => {
    try {
      const loaded = await read()
      if (loaded && scope === readScope() && isCurrent()) await restoreViewPosition(scope, top)
      return loaded
    } finally { navigationReadDepth -= 1 }
  })()
}
function currentDetailMatchesSelection() {
  if (readState.value !== 'loaded' || !serverFacts.value
    || String(serverFacts.value.configuration?.operationId ?? '') !== selectedOperationId.value) return false
  const scope = serverFacts.value.context?.scope
  if (selectedPlanId.value && selectedRoutingStepId.value) return Boolean(scope
    && String(scope.productionPlanId) === selectedPlanId.value && String(scope.routingStepId) === selectedRoutingStepId.value
    && (scope.operationId == null || String(scope.operationId) === selectedOperationId.value))
  return !scope
}
function optionLabel(row) {
  return row.label || row.ruleName || row.rule_name || row.name || row.planNo || row.code || '正式对象说明未提供'
}
function reasonLabel(reason) {
  return typeof reason === 'string' ? reason : reason?.statusLabel || reason?.message || reason?.reason || '正式校验未通过'
}
function serverDisplayLabel(review, field, fallback) {
  const label = review?.[field]
  return typeof label === 'string' && label.trim() ? label : fallback
}
function conditionalExecutionLabels(applicability) {
  const policy = applicability?.conditionalExecution
  if (policy?.triggerStatus !== 'WAITING_TRIGGER') return []
  return ['triggerPolicyLabel', 'pendingScopeLabel', 'executionFactLabel', 'capacityIndependenceLabel']
    .map(field => policy[field]).filter(label => typeof label === 'string' && label.trim())
}
function quantityText(value) {
  return value === null || value === undefined || value === '' ? '未知' : String(value)
}
function recordCountText(value) {
  return value === null ? '记录数未知' : `${value}条`
}
function sourceInputText(source) {
  return `${source.sourceCanonicalField || source.sourceSelector?.canonicalField || '来源字段未知'} / ${source.producerVersion || source.producerRuleVersion || source.sourceSelector?.producerRuleVersion || '生产版本未知'}`
}
function quantityContractText(source) {
  return `${source.quantityExpression || source.sourceExpression || '数量表达未知'}；${source.quantityBasisLabel || '数量口径未知'}；${source.deduplicationLabel || '去重口径未知'}`
}
function routingKey(row) {
  return `${row.routingId}:${row.routingVersionId}:${row.routingStepId}`
}
function sourcePayload() {
  const payload = { ruleCode: form.ruleCode, ruleName: form.ruleName, version: form.version,
    effectiveFrom: form.effectiveFrom,
    traceEquals: JSON.parse(JSON.stringify(explicitSelectorMode.value ? explicitTraceState.value.trace || {}
      : selectedTraceOption.value?.traceEquals || selectedProducer.value?.traceEquals || {})) }
  if (explicitSelectorMode.value) payload.sourceSelectorMode = 'EXPLICIT_CONDITIONS'
  visibleConfigurationFields.value.forEach(field => { payload[field.key] = Number(form[field.key]) })
  if (hasCapacityModes.value && selectedCapacityMode.value) {
    payload.capacityMode = selectedCapacityMode.value.value
    if (selectedCapacityMode.value.requiresStandardCapacity === false) payload.standardCapacityId = null
  }
  if (hasConfigurationOptions.value) {
    Object.assign(payload, { quantityBasis: form.quantityBasis, expression: form.expression })
    if (form.effectiveTo) payload.effectiveTo = form.effectiveTo
    if (selectedQuantityContract.value?.requiresBasisQuantity) payload.basisQuantity = form.basisQuantity.trim()
    if (selectedQuantityContract.value?.requiresBasisUomId) payload.basisUomId = Number(form.basisUomId)
    if (selectedScopeContract.value?.requiresRoutingContext && selectedRoutingContext.value) {
      const selected = selectedRoutingContext.value
      payload.routingContext = { contractVersion: selected.contractVersion, routingId: selected.routingId,
        routingVersionId: selected.routingVersionId, routingStepId: selected.routingStepId }
    }
  }
  return payload
}
function unwrap(response) {
  if (response?.success === false) throw new Error(response.error?.message || response.message || '正式来源服务请求失败。')
  return response?.data ?? response
}
function buildDiagnostics() {
  return { pageFactOwner: 'foundation-formal-operations', moduleCode: 'PDE',
    factSource: 'server', strictFacts: strictFacts.value, strictServerFacts: strictFacts.value,
    readDiagnostics: readDiagnostics.value }
}
function noDateDisplayFieldLabel(key) {
  return { capacityLabel: '产能口径', productionDaysLabel: '理论加工用时', preparationDaysLabel: '准备时间',
    transferDaysLabel: '转运时间', totalDaysLabel: '本步骤理论用时', timeSourceLabel: '时间来源',
    scopeBoundaryLabel: '核对边界' }[key] || '正式说明'
}
async function copyCurrentDiagnostics() {
  try {
    const serialized = assertSafeDiagnosticPayload(buildDiagnostics())
    if (!globalThis.navigator?.clipboard?.writeText) throw new Error('当前环境不能写入剪贴板。')
    await globalThis.navigator.clipboard.writeText(serialized)
    diagnosticCopyMessage.value = '已复制本次服务端核对事实与读取诊断。'
  } catch (error) {
    diagnosticCopyMessage.value = error.message || '诊断复制失败，请重新操作。'
  }
}
function validateNoDateCapacity(value, expectedScope) {
  const fields = ['companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
    'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId']
  const labelFields = ['capacityLabel', 'productionDaysLabel', 'preparationDaysLabel', 'transferDaysLabel',
    'totalDaysLabel', 'timeSourceLabel', 'scopeBoundaryLabel']
  const hasLabel = text => typeof text === 'string' && Boolean(text.trim())
  const validLabels = labels => labels && labelFields.every(key => hasLabel(labels[key]))
  const validDays = days => days === null || typeof days === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?(?:e[+-]?\d+)?$/i.test(days)
  if (value?.contractVersion !== 'PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1' || value.factSource !== 'server'
    || fields.some(key => !Number.isInteger(expectedScope?.[key]) || expectedScope[key] <= 0
      || value.scope?.[key] !== expectedScope[key])
    || !hasLabel(value.stage) || !hasLabel(value.statusCode) || !hasLabel(value.statusLabel)
    || !validLabels(value.displayLabels) || value.businessWriteCount !== 0 || value.auditWriteCount !== 0
    || !hasLabel(value.assessedAt) || !/^[a-f\d]{64}$/i.test(value.resultHash || '')
    || value.planningReady !== false || value.dateOccupationCount !== 0 || value.productionScheduleCreatedCount !== 0
    || ['legalEmptyLoadVerified', 'noDateMatchPassed', 'scopeNoDateReady']
      .some(key => typeof value[key] !== 'boolean')
    || ['matchedStepCount', 'matchedAllocationCount'].some(key => !Number.isInteger(value[key]) || value[key] < 0)
    || !Array.isArray(value.capacityMatches) || !Array.isArray(value.blockers)
    || value.blockers.some(issue => !hasLabel(issue?.statusLabel || issue?.label))
    || !(typeof value.independentAllocationRequired === 'boolean' || value.independentAllocationRequired === null
      && !value.legalEmptyLoadVerified && !value.noDateMatchPassed && value.blockers.length > 0)
    || !Array.isArray(value.dateLayerBlockers) || value.dateLayerBlockers.some(issue => !hasLabel(issue?.statusLabel || issue?.label))
    || !value.dateConditions || !hasLabel(value.dateConditions.statusLabel)
    || ['planStartDateProvided', 'calendarOccupationEvaluated', 'capacityAndResourceExecutionWindowEvaluated']
      .some(key => value.dateConditions[key] !== false)
    || value.legalEmptyLoadVerified && (value.independentAllocationRequired || value.noDateMatchPassed
      || value.scopeNoDateReady || value.capacityMatches.length !== 0 || value.matchedStepCount !== 0 || value.matchedAllocationCount !== 0)
    || value.noDateMatchPassed && (value.capacityMatches.length === 0 || value.legalEmptyLoadVerified)
    || value.capacityMatches.some(match => !Number.isInteger(match.standardCapacityId) || match.standardCapacityId <= 0
      || !(match.workCenterId === null || Number.isInteger(match.workCenterId) && match.workCenterId > 0)
      || !validLabels(match.displayLabels)
      || ['productionDays', 'preparationDays', 'transferDays', 'durationDays'].some(key => !validDays(match[key]))
      || ['preparationIncludedCount', 'transferIncludedCount'].some(key => !Number.isInteger(match[key]) || match[key] < 0))) {
    throw new Error('无日期产能核对与当前准确范围或只读合同不一致，当前结论与理论用时未知。')
  }
  return value
}
function validateFacts(value) {
  if (value?.contractVersion !== CONTRACT || value.factSource !== 'server' || !Array.isArray(value.operations) || !value.catalog
    || ['producers', 'manufacturingModes', 'productTypes', 'standardCapacities', 'workCenters', 'productionPlans'].some(key => !Array.isArray(value.catalog[key]))
    || value.catalog.producers.some(producer => producer.traceOptions !== undefined && !Array.isArray(producer.traceOptions))) {
    throw new Error('正式来源事实返回不完整。')
  }
  if (value.catalog.capacityModes !== undefined && (!Array.isArray(value.catalog.capacityModes)
    || value.catalog.capacityModes.length === 0
    || value.catalog.capacityModes.some(option => typeof option.value !== 'string' || !option.value.trim()
      || typeof option.statusLabel !== 'string' || !option.statusLabel.trim()
      || typeof option.requiresStandardCapacity !== 'boolean' || typeof option.requiresPlanPreparation !== 'boolean')
    || new Set(value.catalog.capacityModes.map(option => option.value)).size !== value.catalog.capacityModes.length
    || !Array.isArray(value.catalog.workCenterOperationCapabilities))) {
    throw new Error('正式产能承接方式或工作中心能力目录不完整，当前事实未展示。')
  }
  return value
}
function validateRequestedScope(value, params) {
  if (params.operationId && Number(value.configuration?.operationId) !== params.operationId) throw new Error('来源方案返回的工序范围与本次选择不一致。')
  if (!params.productionPlanId) return
  const current = value.context
  const scope = current?.scope
  if (Number(scope?.productionPlanId) === params.productionPlanId && Number(scope?.routingStepId) === params.routingStepId
    && (scope.operationId == null || Number(scope.operationId) === params.operationId)) {
    validateCapacitySemantics(current.capacitySemantics)
    validateInputPreparation(current.inputPreparation, scope, value.catalog.companyId, current)
    if (current.noDateCapacityIncluded === true || current.noDateCapacity !== undefined) {
      if (current.noDateCapacityIncluded === true && current.noDateCapacityContract !== 'PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1') {
        throw new Error('当前步骤无日期读取合同版本不一致，当前结论未知。')
      }
      validateNoDateCapacity(current.noDateCapacity, scope)
    }
    if (current.quantityPolicy != null || current.inputPreparation?.quantityPolicy != null) {
      validateQuantityPolicy(current.quantityPolicy, scope)
      if (canonicalSnapshot(current.quantityPolicy) !== canonicalSnapshot(current.inputPreparation?.quantityPolicy)) {
        throw new Error('当前数量政策与正式准备记录不一致，当前事实未展示。')
      }
    }
    return
  }
  const failedScope = scope && Object.keys(scope).length === 0 && Array.isArray(current.blockers) && current.blockers.length > 0
  const containsQuantity = ['sourceCandidates', 'formalRequirements', 'savedAllocations'].some(key =>
    (current?.[key]?.items || []).length > 0 || (current?.[key]?.quantity !== null && current?.[key]?.quantity !== undefined))
  if (failedScope && !containsQuantity && current.inputPreparation == null) return
  throw new Error('计划或路线步骤返回范围与本次选择不一致，数量未展示。')
}
function validateCapacitySemantics(semantics) {
  if (semantics == null) return
  const known = ['QUANTIFIED', 'NON_QUANTIFIED', 'NOT_APPLICABLE']
  if (semantics.contractVersion !== 'PCE-CAPACITY-TRISTATE-V1' || typeof semantics.valid !== 'boolean'
    || (semantics.valid ? !known.includes(semantics.meaningCode) : semantics.meaningCode !== null)
    || ['statusLabel', 'sourceStatusLabel', 'recordPresenceStatusLabel'].some(key => typeof semantics[key] !== 'string' || !semantics[key].trim())
    || ['quantitativeOccupancyAllowed', 'independentDurationAllowed'].some(key => typeof semantics[key] !== 'boolean')) {
    throw new Error('正式产能三态或记录来源合同不完整，当前事实未展示。')
  }
}
function validateInputPreparation(preparation, scope, companyId, current = null) {
  if (preparation == null) return
  const scopeFields = ['companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
    'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId']
  const hasLabel = value => typeof value === 'string' && Boolean(value.trim())
  const consumptionReference = preparation.capacityConsumptionReference != null
    || preparation.statusCode === 'POSITIVE_CAPACITY_REFERENCE_RECORDED'
    || preparation.businessBasis?.entries?.some(entry => entry.capacityConsumptionReference != null)
  if (preparation.contractVersion !== 'PCE-OPERATION-INPUT-PREPARATION-V1' || preparation.factSource !== 'server'
    || !['RECORDED', 'NOT_RECORDED'].includes(preparation.recordStatus)
    || scopeFields.some(key => !Number.isInteger(scope?.[key]) || scope[key] <= 0 || preparation.exactScope?.[key] !== scope[key])
    || scope.companyId !== companyId
    || ['businessWriteCount', 'auditWriteCount', 'stateTransitionWriteCount', 'supportWriteCount'].some(key => preparation[key] !== 0)
    || ['formalRulePublished', 'readyForGeneration', 'readyForAllocation', 'readyForScheduling'].some(key => preparation[key] !== false)
    || !consumptionReference && ['sourceQuantity', 'inputQuantity', 'capacityQuantity'].some(key => preparation[key] !== null)
    || !['statusLabel', 'inputStandardStatusLabel', 'capacityMeasurementStatusLabel', 'formalRuleStatusLabel', 'scopeLabel'].every(key => hasLabel(preparation[key]))
    || !Array.isArray(preparation.remainingItems) || preparation.remainingItems.some(item => !hasLabel(item?.statusLabel))) {
    throw new Error('工序投入准备记录与本次准确范围或只读合同不一致，当前事实未展示。')
  }
  if (preparation.recordStatus === 'RECORDED') {
    if (!Number.isInteger(preparation.recordId) || preparation.recordId <= 0
      || !Number.isInteger(preparation.revision) || preparation.revision <= 0 || !hasLabel(preparation.contextHash)
      || preparation.inputStandardStatus !== 'PENDING_CONFIRMATION'
      || !Array.isArray(preparation.businessBasis?.entries) || preparation.businessBasis.entries.length === 0
      || preparation.businessBasis.entries.some(entry => !['exactStatement', 'reference', 'referenceSha256'].every(key => hasLabel(entry?.[key])))
      || !Array.isArray(preparation.businessBasisPresentation) || preparation.businessBasisPresentation.length !== preparation.businessBasis.entries.length
      || preparation.businessBasisPresentation.some((entry, index) => entry.entryIndex !== index || !hasLabel(entry.statusLabel)
        || ['exactStatement', 'reference', 'referenceSha256'].some(key => entry[key] !== preparation.businessBasis.entries[index][key]))) {
      throw new Error('已保存准备记录的正式状态或业务依据不完整，当前事实未展示。')
    }
    if (consumptionReference) {
      validateCapacityConsumptionPreparation(preparation, scope, current)
      return
    }
    if (preparation.quantityPolicy != null || preparation.businessBasis?.quantityPolicy != null
      || preparation.context?.contractVersion === 'PCE-OPERATION-QUANTITY-POLICY-V1'
      || preparation.statusCode === 'NOT_SEPARATELY_MEASURED') {
      validateQuantityPolicyPreparation(preparation, scope)
      return
    }
    if (preparation.conditionalExecution != null || preparation.businessBasis?.conditionalExecution != null
      || preparation.context?.contractVersion === 'PCE-CONDITIONAL-EXECUTION-PREPARATION-V1'
      || preparation.statusCode === 'WAITING_TRIGGER') {
      validateConditionalPreparation(preparation, scope)
      return
    }
    const resolution = preparation.capacityResolution
    const confirmedZero = preparation.capacityMeasurementStatus === 'zero_capacity' && preparation.capacityBusinessValue === 0
      && resolution?.valid === true && resolution.originalConclusionRevoked === true && resolution.formalStandardCapacityPresent === false
    const unresolved = preparation.capacityMeasurementStatus === null && preparation.capacityBusinessValue === null && resolution?.valid === false
    if (!hasLabel(resolution?.statusLabel) || (!confirmedZero && !unresolved)) {
      throw new Error('准备记录未证明当前产能裁决或历史结论撤销，当前事实未展示。')
    }
  } else if (consumptionReference || preparation.inputStandardStatus !== null || preparation.capacityMeasurementStatus !== null
    || preparation.recordId !== null || preparation.revision !== null || (preparation.businessBasis?.entries || []).length > 0
    || preparation.conditionalExecution != null || preparation.businessBasis?.conditionalExecution != null
    || preparation.context?.contractVersion === 'PCE-CONDITIONAL-EXECUTION-PREPARATION-V1'
    || preparation.statusCode === 'WAITING_TRIGGER' || preparation.quantityPolicy != null
    || preparation.businessBasis?.quantityPolicy != null || preparation.statusCode === 'NOT_SEPARATELY_MEASURED'
    || preparation.context?.contractVersion === 'PCE-OPERATION-QUANTITY-POLICY-V1') {
    throw new Error('尚无准备记录不能声明待确认或尚未测定，当前事实未展示。')
  }
}
function validateCapacityConsumptionPreparation(preparation, scope, current) {
  const contract = 'PCE-PLAN-STEP-CAPACITY-CONSUMPTION-REFERENCE-V1'
  const positiveId = value => Number.isInteger(value) && value > 0
  const hash = value => typeof value === 'string' && /^[a-f\d]{64}$/i.test(value)
  const label = value => typeof value === 'string' && Boolean(value.trim())
  const positiveQuantity = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value) && /[1-9]/.test(value)
  const exact = value => value && Object.keys(scope).every(key => value[key] === scope[key])
  const ids = value => Array.isArray(value) && value.length > 0 && value.every(positiveId)
  const sameIds = (left, right) => ids(left) && ids(right)
    && canonicalSnapshot([...left].sort((a, b) => a - b)) === canonicalSnapshot([...right].sort((a, b) => a - b))
  const reference = preparation.capacityConsumptionReference
  const marker = preparation.businessBasis.entries.filter(entry => entry.capacityConsumptionReference != null).at(-1)?.capacityConsumptionReference
  const fact = reference?.selectedCapacityFact
  const load = reference?.savedLoadReference
  const shared = reference?.sharedTimeSource
  const saved = current?.savedAllocations
  const noDate = current?.noDateCapacity
  const proofFields = ['exactScope', 'capacityReference', 'selectedCapacityFact', 'capacityUsageScopeProof',
    'savedLoadReference', 'validatedObjectCoverage', 'sharedTimeSource']
  const compactFields = ['contractVersion', 'consumer', 'recordId', 'revision', 'auditIds', 'referenceHash']
  const sameCompact = value => value && compactFields.every(key => canonicalSnapshot(value[key]) === canonicalSnapshot(reference?.[key]))
  if (preparation.currentStateSource !== 'server' || preparation.isPersisted !== true
    || preparation.statusCode !== 'POSITIVE_CAPACITY_REFERENCE_RECORDED'
    || preparation.context?.consumer !== 'ALLOCATED_LOAD_NO_DATE' || !exact(preparation.context.exactScope)
    || preparation.context.contractVersion !== 'PCE-OPERATION-INPUT-PREPARATION-V1'
    || preparation.conditionalExecution != null || preparation.quantityPolicy != null
    || preparation.businessBasis.conditionalExecution != null || preparation.businessBasis.quantityPolicy != null
    || !hash(preparation.contentHash) || !hash(preparation.objectsHash) || !hash(preparation.contextHash)
    || preparation.context.objectsHash !== preparation.objectsHash
    || !ids(preparation.auditIds) || !positiveId(preparation.writeRequestId) || !positiveId(preparation.sourceIdentityId)
    || preparation.stateMachineConsistent !== true || !Array.isArray(preparation.statusTransitionHistory)
    || preparation.statusTransitionHistory.length === 0
    || preparation.statusTransitionCount !== preparation.statusTransitionHistory.length
    || preparation.standardCapacityId !== null
    || ['producerRuleId', 'manufacturingModeId', 'workCenterId'].some(key => !(preparation[key] === null || positiveId(preparation[key])))
    || preparation.remainingItems.length !== 0 || reference?.contractVersion !== contract
    || reference.consumer !== 'ALLOCATED_LOAD_NO_DATE' || reference.formalConsumptionValidated !== true
    || !exact(reference.exactScope) || reference.recordId !== preparation.recordId || reference.revision !== preparation.revision
    || !sameIds(reference.auditIds, preparation.auditIds) || !hash(reference.referenceHash)
    || ['grantsRulePublication', 'grantsRequirementGeneration', 'grantsAllocation', 'grantsScheduling'].some(key => reference[key] !== false)
    || marker?.contractVersion !== contract || marker.consumer !== reference.consumer
    || marker.effectiveFrom !== reference.effectiveFrom || marker.effectiveTo !== reference.effectiveTo
    || !label(reference.effectiveFrom) || !(reference.effectiveTo === null || label(reference.effectiveTo))
    || !marker.proof || proofFields.some(key => canonicalSnapshot(marker.proof[key]) !== canonicalSnapshot(reference[key]))
    || marker.standardCapacityId !== reference.capacityReference?.standardCapacityId
    || !positiveId(reference.capacityReference?.standardCapacityId)
    || ['capacityRecordHash', 'proofHash'].some(key => !hash(reference.capacityReference[key]))
    || fact?.factSource !== 'server' || fact.id !== reference.capacityReference.standardCapacityId
    || fact.operationId !== scope.operationId || fact.productTypeId !== scope.productTypeId
    || !positiveId(fact.workCenterId) || !positiveId(fact.uomId) || !label(fact.uomLabel)
    || !positiveQuantity(fact.quantity) || fact.capacityQuantity !== fact.quantity
    || fact.timeBasis !== 'day' || !/^1(?:\.0+)?$/.test(fact.timeBasisQuantity || '') || fact.timeUnit !== 'DAY'
    || fact.measurementStatus !== 'measured' || fact.available !== false || fact.independentApsSchedulingAllowed !== false
    || fact.capacityUsageScope?.usageScope !== 'ENGINEERING_EOR_ONLY'
    || fact.capacitySemantics?.valid !== true || fact.capacitySemantics.meaningCode !== 'QUANTIFIED'
    || preparation.capacityMeasurementStatus !== 'measured' || preparation.legacyCapacityMeasurementStatus !== 'UNMEASURED'
    || preparation.capacityBusinessValue !== fact.quantity || preparation.capacityQuantity !== fact.quantity
    || preparation.capacityResolution?.valid !== true || preparation.capacityResolution.code !== 'FORMAL_POSITIVE_CAPACITY_REFERENCE'
    || preparation.capacityResolution.formalStandardCapacityPresent !== true || preparation.capacityResolution.originalConclusionRevoked !== false
    || !label(preparation.capacityResolution.statusLabel)
    || reference.capacityUsageScopeProof?.contractVersion !== 'PCE-MANUFACTURING-CAPACITY-SCOPE-V1'
    || reference.capacityUsageScopeProof.standardCapacityId !== fact.id
    || !positiveId(reference.capacityUsageScopeProof.auditId) || !hash(reference.capacityUsageScopeProof.capacitySnapshotHash)
    || !positiveQuantity(load?.quantity) || !positiveId(load.uomId) || load.uomId !== fact.uomId
    || !hash(load.objectCoverageProofHash) || !hash(load.allocationRecordsHash)
    || preparation.sourceQuantity !== load.quantity || preparation.inputQuantity !== load.quantity
    || saved?.statusCode !== 'SAVED' || saved.quantity !== load.quantity || saved.uomId !== load.uomId
    || !Array.isArray(saved.items) || !sameIds(load.allocationIds, saved.items.map(item => item.allocationId))
    || !sameIds(load.operationRequirementIds, saved.items.map(item => item.operationRequirementId))
    || saved.items.some(item => item.uomId !== load.uomId || item.routingStepId !== scope.routingStepId)
    || !Array.isArray(preparation.objectCoverage) || preparation.objectCoverage.length === 0
    || !sameIds(reference.validatedObjectCoverage?.designItemIds, preparation.objectCoverage.map(item => item.designItemId))
    || !sameIds(reference.validatedObjectCoverage?.baselineItemIds, preparation.objectCoverage.map(item => item.baselineItemId))
    || !ids(reference.validatedObjectCoverage?.inputFactIds)
    || shared?.sourceId !== scope.productTypeId || shared.timeUnit !== 'DAY' || shared.countPolicy !== 'ONCE_PER_STEP'
    || !hash(shared.sourceSha256) || !hash(shared.referenceHash) || shared.proofHash !== shared.referenceHash
    || ['preparationDays', 'transferDays'].some(key => typeof shared[key] !== 'string' || !/^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(shared[key]))
    || marker.unifiedTimeSource?.referenceType !== 'FORMAL_CAPACITY_SOURCE_RULES_HEADER'
    || marker.unifiedTimeSource.productTypeId !== shared.sourceId || marker.unifiedTimeSource.sourceSha256 !== shared.sourceSha256
    || marker.unifiedTimeSource.effectiveDate !== shared.effectiveDate
    || !exact(noDate?.scope) || !sameCompact(noDate.capacityConsumptionReference)
    || !Array.isArray(noDate.capacityMatches) || noDate.capacityMatches.some(match => match.standardCapacityId !== fact.id
      || match.workCenterId !== fact.workCenterId || canonicalSnapshot(match.capacityFact) !== canonicalSnapshot(fact)
      || !sameCompact(match.capacityConsumptionReference)
      || ['preparationDays', 'transferDays'].some(key => match[key] !== shared[key])
      || ['preparation', 'transfer'].some(key => match.timeSelection?.[key]?.source !== 'CAPACITY_SOURCE_RULES_HEADER'
        || match.timeSelection[key].sourceId !== shared.sourceId || match.timeSelection[key].referenceHash !== shared.referenceHash
        || match.timeSelection[key].timeUnit !== 'DAY'
        || match.timeSelection[key].selectedDays !== shared[key === 'preparation' ? 'preparationDays' : 'transferDays']))) {
    throw new Error('正式正产能消费引用与本次保存负荷、范围或无日期事实不一致，当前事实未展示。')
  }
}
function validateConditionalPreparation(preparation, scope) {
  const contract = 'PCE-CONDITIONAL-EXECUTION-PREPARATION-V1'
  const hasLabel = value => typeof value === 'string' && Boolean(value.trim())
  const exactScope = value => value && Object.keys(preparation.exactScope).every(key => value[key] === scope[key])
  const unknownCoverage = value => value?.scopeType === 'PLAN_STEP_CONDITION'
    && value.status === 'UNKNOWN_UNTIL_TRIGGER' && value.objects === null && value.parts === null
  const policy = preparation.conditionalExecution
  const basis = preparation.businessBasis?.conditionalExecution
  const capacity = policy?.capacityPolicy
  const execution = policy?.executionFact
  const semantics = preparation.capacitySemantics
  const expectedCapacity = { appliesWhen: 'TRIGGERED', meaningCode: 'NON_QUANTIFIED', sourceValue: '0',
    quantitativeOccupancyAllowed: false, independentDurationAllowed: false }
  if (policy?.contractVersion !== contract || basis?.contractVersion !== contract
    || preparation.context?.contractVersion !== contract || preparation.currentStateSource !== 'server'
    || preparation.statusCode !== 'WAITING_TRIGGER' || preparation.triggerStatus !== 'WAITING_TRIGGER'
    || policy.triggerStatus !== 'WAITING_TRIGGER' || preparation.result !== 'PENDING'
    || !hasLabel(policy.conditionCode) || policy.conditionCode !== preparation.conditionCode
    || preparation.formalPolicyValidated !== true || preparation.formalApplicabilityValidated !== false
    || preparation.isPersisted !== true || preparation.context.scopeType !== 'PLAN_STEP_CONDITION'
    || !exactScope(preparation.context.exactScope) || preparation.context.sourceSelection !== null
    || [preparation.objectCoverage, preparation.context.objectCoverage].some(value => !unknownCoverage(value))
    || preparation.businessBasis.entries.some(entry => !exactScope(entry.scope) || !unknownCoverage(entry.objectCoverage))
    || ['affectedObjects', 'affectedParts', 'quantity', 'uomId'].some(key => policy[key] !== null)
    || preparation.quantity !== null || preparation.uomId !== null || preparation.draftSelection !== null
    || !hasLabel(policy.originalApplicabilityHash)
    || Object.keys(basis).some(key => canonicalSnapshot(basis[key]) !== canonicalSnapshot(policy[key]))
    || canonicalSnapshot(capacity) !== canonicalSnapshot(expectedCapacity)
    || canonicalSnapshot(preparation.conditionalCapacityPolicy) !== canonicalSnapshot(capacity)
    || execution?.mode !== 'SIMULATED' || execution.allMaterialUnissued !== true
    || execution.allWorkUnstarted !== true || !hasLabel(execution.statement)
    || ['triggerPolicyLabel', 'pendingScopeLabel', 'executionFactLabel', 'capacityIndependenceLabel'].some(key => !hasLabel(policy[key]))
    || preparation.capacityMeasurementStatus !== null || preparation.capacityBusinessValue !== null
    || preparation.capacityResolution?.valid !== false || preparation.capacityResolution.code !== 'WAITING_TRIGGER'
    || !hasLabel(preparation.capacityResolution.statusLabel)
    || semantics?.valid !== false || semantics.meaningCode !== null || semantics.sourceValue !== null
    || ['quantitativeOccupancyAllowed', 'grantsRulePublication', 'grantsRequirementGeneration',
      'grantsAllocation', 'grantsScheduling'].some(key => semantics[key] !== false)
    || !Array.isArray(preparation.auditIds) || preparation.auditIds.length === 0
    || preparation.auditIds.some(id => !Number.isInteger(id) || id <= 0)
    || ['writeRequestId', 'sourceIdentityId'].some(key => !Number.isInteger(preparation[key]) || preparation[key] <= 0)
    || preparation.stateMachineConsistent !== true || !Array.isArray(preparation.statusTransitionHistory)
    || preparation.statusTransitionHistory.length === 0
    || preparation.statusTransitionCount !== preparation.statusTransitionHistory.length) {
    throw new Error('条件准备未证明准确范围、待触发未知量或只读资格，当前事实未展示。')
  }
}
function validateQuantityPolicy(policy, scope) {
  const hasLabel = value => typeof value === 'string' && Boolean(value.trim())
  const fields = ['companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
    'salesOrderItemId', 'baselineId', 'routingVersionId', 'routingStepId', 'operationId', 'productTypeId']
  const reference = policy?.statisticalUomReference
  if (policy?.contractVersion !== 'PCE-OPERATION-QUANTITY-POLICY-V1'
    || policy.measurementMode !== 'NOT_SEPARATELY_MEASURED' || policy.formalPolicyValidated !== true
    || fields.some(key => !Number.isInteger(scope?.[key]) || scope[key] <= 0 || policy.exactScope?.[key] !== scope[key])
    || policy.plannedQuantity !== null || policy.actualQuantity !== null
    || ['statusLabel', 'plannedQuantityReasonLabel', 'actualQuantityReasonLabel', 'capacityIndependenceLabel'].some(key => !hasLabel(policy[key]))
    || !reference || ['uomId', 'sourceCompanyId', 'sourceProductionPlanId', 'sourceRoutingVersionId',
      'sourceRoutingStepId', 'sourceOperationId'].some(key => !Number.isInteger(reference[key]) || reference[key] <= 0)
    || reference.sourceCompanyId !== scope.companyId || reference.sourceProductionPlanId !== scope.productionPlanId
    || reference.sourceRoutingVersionId !== scope.routingVersionId || reference.sourceRoutingStepId === scope.routingStepId
    || ['uomCode', 'uomLabel', 'statusLabel'].some(key => !hasLabel(reference[key]))
    || typeof reference.proofHash !== 'string' || !/^[a-f0-9]{64}$/i.test(reference.proofHash)) {
    throw new Error('投产数量政策或统计单位精确来源合同不完整，当前事实未展示。')
  }
}
function validateQuantityPolicyPreparation(preparation, scope) {
  validateQuantityPolicy(preparation.quantityPolicy, scope)
  const policy = preparation.quantityPolicy
  const basis = preparation.businessBasis?.quantityPolicy
  const resolution = preparation.capacityResolution
  if (basis?.contractVersion !== policy.contractVersion || basis.measurementMode !== policy.measurementMode
    || basis.plannedQuantity !== null || basis.actualQuantity !== null
    || basis.nullReason !== 'NOT_SEPARATELY_MEASURED' || basis.scopeDetermination !== 'DRAWING_AND_SITE'
    || basis.objectCoverageClaimed !== false
    || basis.statisticalUomReference?.referenceType !== 'ROUTE_STEP_SOURCE_CONFIGURATION'
    || basis.statisticalUomReference.routingStepId !== policy.statisticalUomReference.sourceRoutingStepId
    || !Number.isInteger(basis.capacityReference?.standardCapacityId) || basis.capacityReference.standardCapacityId <= 0
    || preparation.context?.contractVersion !== policy.contractVersion
    || Object.keys(preparation.exactScope).some(key => preparation.context.exactScope?.[key] !== scope[key])
    || preparation.conditionalExecution != null || preparation.businessBasis?.conditionalExecution != null
    || preparation.statusCode !== 'NOT_SEPARATELY_MEASURED' || preparation.currentStateSource !== 'server'
    || preparation.isPersisted !== true || preparation.formalPolicyValidated !== true
    || preparation.capacityMeasurementStatus !== 'zero_capacity' || preparation.capacityBusinessValue !== 0
    || resolution?.valid !== true || resolution.code !== 'FORMAL_AUXILIARY_ZERO_REFERENCE'
    || resolution.formalStandardCapacityPresent !== true || resolution.originalConclusionRevoked !== false
    || typeof resolution.statusLabel !== 'string' || !resolution.statusLabel.trim()
    || !Array.isArray(preparation.auditIds) || preparation.auditIds.length === 0
    || preparation.auditIds.some(id => !Number.isInteger(id) || id <= 0)
    || ['writeRequestId', 'sourceIdentityId'].some(key => !Number.isInteger(preparation[key]) || preparation[key] <= 0)
    || preparation.stateMachineConsistent !== true || !Array.isArray(preparation.statusTransitionHistory)
    || preparation.statusTransitionHistory.length === 0
    || preparation.statusTransitionCount !== preparation.statusTransitionHistory.length) {
    throw new Error('不单独计量政策未证明正式准备及独立产能引用，当前事实未展示。')
  }
}
function validateRouteFacts(value, plan, companyId) {
  const route = value?.routeConfiguration
  const scope = route?.scope
  const hasLabel = text => typeof text === 'string' && Boolean(text.trim())
  if (value?.contractVersion !== CONTRACT || value.factSource !== 'server' || !route
    || !Array.isArray(route.rows) || !route.summary || value.businessWriteCount !== 0
    || route.businessWriteCount !== 0 || route.auditWriteCount !== 0
    || route.generated !== false || route.allocationSaved !== false || route.newEorRuleEvaluated !== false
    || route.workloadReviewIncluded !== true || route.workloadReviewContract !== 'PCE-ROUTE-WORKLOAD-READ-V1'
    || !hasLabel(route.summary.workloadStatusLabel)) {
    throw new Error('路线投产量正式读取合同不完整，当前事实未展示。')
  }
  if (route.noDateCapacityIncluded === true && route.noDateCapacityContract !== 'PCE-ALLOCATED-LOAD-NO-DATE-CAPACITY-V1') {
    throw new Error('路线无日期读取合同版本不一致，当前结论未知。')
  }
  if (route.noDateCapacityIncluded === true && (!hasLabel(route.noDateCapacitySummary?.statusLabel)
    || route.noDateCapacitySummary.readStepCount !== route.rows.length
    || !hasLabel(route.noDateCapacitySummary.assessedAt)
    || !/^[a-f\d]{64}$/i.test(route.noDateCapacitySummary.resultHash || ''))) {
    throw new Error('路线无日期核对摘要与本次完整步骤读取不一致，当前结论未知。')
  }
  const scopeFields = ['companyId', 'productionPlanId', 'manufacturingOutputId', 'mainCalculationId',
    'salesOrderItemId', 'baselineId', 'routingId', 'routingVersionId', 'productTypeId']
  if (scopeFields.some(key => !Number.isInteger(scope?.[key]) || scope[key] <= 0)
    || scope.productionPlanId !== Number(plan.id) || !Number.isInteger(companyId) || scope.companyId !== companyId
    || ['manufacturingOutputId', 'routingVersionId'].some(key => plan[key] != null && scope[key] !== Number(plan[key]))) {
    throw new Error('路线来源返回的公司、计划或制造路线范围与本次选择不一致。')
  }
  const expected = new Map((plan.allRoutingSteps || plan.routingSteps || []).map(step => [Number(step.id), Number(step.operationId)]))
  const seen = new Set()
  const sequences = new Set()
  if (expected.size === 0 || !Number.isInteger(route.summary.stepCount) || route.summary.stepCount !== route.rows.length
    || (expected.size > 0 && expected.size !== route.rows.length)) throw new Error('路线步骤清单与正式计划范围不一致。')
  for (const row of route.rows) {
    validateCapacitySemantics(row.capacitySemantics)
    if (route.noDateCapacityIncluded === true || row.noDateCapacity !== undefined) {
      validateNoDateCapacity(row.noDateCapacity, row.scope)
      const version = row.effectiveVersion
      if (row.scope.companyId !== scope.companyId || row.scope.productionPlanId !== scope.productionPlanId
        || row.scope.operationId !== row.operationId || row.scope.salesOrderItemId !== scope.salesOrderItemId
        || row.scope.productTypeId !== scope.productTypeId
        || row.scope.routingStepId !== (version?.effectiveRoutingStepId ?? row.routingStepId)
        || version && version.rootRoutingStepId !== row.routingStepId
        || [['manufacturingOutputId', 'effectiveManufacturingOutputId'], ['routingVersionId', 'effectiveRoutingVersionId'],
          ['baselineId', 'sourceBaselineId'], ['mainCalculationId', 'mainCalculationId']]
          .some(([field, versionField]) => row.scope[field] !== (version?.[versionField] ?? scope[field]))) {
        throw new Error('无日期产能返回的路线公司、计划或工序范围不一致，当前结论未知。')
      }
    }
    if (!Number.isInteger(row.routingStepId) || row.routingStepId <= 0 || seen.has(row.routingStepId)
      || !Number.isInteger(row.operationId) || row.operationId <= 0
      || !Number.isInteger(row.sequence) || row.sequence <= 0 || sequences.has(row.sequence)
      || (expected.size > 0 && expected.get(row.routingStepId) !== row.operationId)
      || !hasLabel(row.operationName) || !row.sourceConfiguration || !row.resourceReferences
      || !Array.isArray(row.predecessorSequences)
      || row.predecessorSequences.some(sequence => !Number.isInteger(sequence) || sequence <= 0 || sequence === row.sequence)
      || new Set(row.predecessorSequences).size !== row.predecessorSequences.length) {
      throw new Error('路线步骤身份或前置关系不一致，当前事实未展示。')
    }
    if (row.quantityPolicy != null || ['sourceCandidates', 'formalRequirements', 'savedAllocations']
      .some(key => row[key]?.statusCode === 'NOT_SEPARATELY_MEASURED')) {
      validateQuantityPolicy(row.quantityPolicy, { ...scope, routingStepId: row.routingStepId, operationId: row.operationId })
      const reference = row.quantityPolicy.statisticalUomReference
      if (expected.get(reference.sourceRoutingStepId) !== reference.sourceOperationId) {
        throw new Error('统计单位引用不属于本次正式路线步骤，当前事实未展示。')
      }
    }
    const review = row.workloadReview
    const formal = row.formalRequirements
    const saved = row.savedAllocations
    const unknownCountStatuses = ['NOT_READ', 'NOT_EVALUATED', 'READ_FAILED', 'PENDING', 'NOT_APPLICABLE']
    const labelFields = ['statusLabel', 'applicabilityLabel', 'processingLabel', 'sourceBusinessLabel',
      'formalRequirementStatusLabel', 'allocationStatusLabel', 'coverageStatusLabel']
    if (!review || !hasLabel(review.statusCode) || labelFields.some(field => !hasLabel(review[field]))
      || !Array.isArray(review.blockers) || review.blockers.some(issue => !hasLabel(reasonLabel(issue)))
      || [formal, saved, row.sourceCandidates].some(bucket => !bucket || !hasLabel(bucket.statusCode)
        || !hasLabel(bucket.statusLabel) || !Array.isArray(bucket.items) || !Array.isArray(bucket.blockers))
      || [formal, saved].some(bucket => unknownCountStatuses.includes(bucket.statusCode) && bucket.items.length !== 0)
      || review.formalRequirementStatusLabel !== formal.statusLabel
      || review.allocationStatusLabel !== saved.statusLabel
      || review.formalRequirementCount !== (unknownCountStatuses.includes(formal.statusCode) ? null : formal.items.length)
      || review.allocationCount !== (unknownCountStatuses.includes(saved.statusCode) ? null : saved.items.length)
      || review.savedQuantity !== saved.quantity || review.uomLabel !== saved.uomLabel
      || !(saved.quantity === null || typeof saved.quantity === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(saved.quantity))
      || saved.statusCode === 'SAVED' && (saved.quantity === null || !hasLabel(saved.uomLabel) || saved.items.length === 0)
      || !(saved.uomLabel === null || hasLabel(saved.uomLabel))) {
      throw new Error('路线投产量与原生需求、分配或数量状态不一致，当前事实未展示。')
    }
    const coverage = row.objectCoverage
    if (!coverage || !hasLabel(coverage.statusCode) || !hasLabel(coverage.statusLabel)
      || review.coverageStatusLabel !== coverage.statusLabel
      || ['designItemIds', 'baselineItemIds', 'inputFactIds'].some(field => coverage[field] !== null
        && (!Array.isArray(coverage[field]) || coverage[field].some(id => !Number.isInteger(id) || id <= 0)
          || new Set(coverage[field]).size !== coverage[field].length))) {
      throw new Error('路线对象覆盖证明合同不完整，当前事实未展示。')
    }
    seen.add(row.routingStepId)
    sequences.add(row.sequence)
  }
  if (route.rows.some(row => row.predecessorSequences.some(sequence => !sequences.has(sequence)))) {
    throw new Error('路线前置步骤不属于本次正式步骤集合，当前事实未展示。')
  }
  return value
}
function loadRouteOverview() {
  if (props.parentReadStatus !== 'loaded') return Promise.resolve(false)
  const key = reads.identity('route-owner', { planId: selectedRoutePlanId.value, generation: routeScopeEpoch })
  if (routeLoadOwner?.key === key) return routeLoadOwner.promise
  const planId = selectedRoutePlanId.value
  const samePlan = routeReadState.value === 'loaded' && String(routeFacts.value?.routeConfiguration?.scope?.productionPlanId) === planId
  const promise = preserveViewPosition(performRouteOverview, samePlan, () => planId === selectedRoutePlanId.value).finally(() => {
    if (routeLoadOwner?.promise === promise) routeLoadOwner = null
  })
  routeLoadOwner = { key, promise }
  return promise
}
async function performRouteOverview() {
  if (props.parentReadStatus !== 'loaded') return false
  const request = ++routeReadSequence
  const scope = readScope()
  const planId = selectedRoutePlanId.value
  const plan = catalog.value.productionPlans.find(row => String(row.id) === planId)
  const companyId = catalog.value.companyId
  routeFacts.value = null
  routeReadError.value = ''
  routeClearSelection()
  if (!planId) {
    routeReadState.value = 'idle'
    return false
  }
  if (!plan) {
    routeReadState.value = 'read_failed'
    routeReadError.value = '所选计划尚未取得当前正式目录，请先刷新来源事实。'
    return false
  }
  routeReadState.value = 'loading'
  try {
    const params = { routeOverview: 1, includeWorkloads: 1, productionPlanId: Number(planId) }
    const actualParams = { ...params, action: 'operationWorkloadSources' }
    const read = reads.run({ purpose: '计划路线投产量', url: componentReadUrl('/api/pde/a1-foundation/operations/', actualParams),
      params: { ...params, generation: routeScopeEpoch }, read: () => pdeApi.getOperationWorkloadSources(params) })
    const result = unwrap(await read)
    if (request !== routeReadSequence || planId !== selectedRoutePlanId.value || scope !== readScope()) return false
    const validationStart = reads.clock()
    routeFacts.value = validateRouteFacts(result, plan, companyId)
    const currentStepIds = new Set(routeFacts.value.routeConfiguration.rows.map(row => String(row.routingStepId)))
    routeExpandedStepIds.value = routeExpandedStepIds.value.filter(key => currentStepIds.has(key))
    reads.stage(read, 'validationMs', validationStart)
    routeReadState.value = 'loaded'
    const commitStart = reads.clock()
    await nextTick()
    if (request === routeReadSequence && scope === readScope()) reads.stage(read, 'vueCommitMs', commitStart)
    return true
  } catch (error) {
    if (request !== routeReadSequence || planId !== selectedRoutePlanId.value || scope !== readScope()) return false
    routeFacts.value = null
    routeReadState.value = 'read_failed'
    routeReadError.value = error?.response?.data?.message || error?.message || '正式路线来源读取失败。'
    return false
  }
}
async function openRouteStep(row) {
  const current = routeConfiguration.value?.rows.find(item => item.routingStepId === row.routingStepId && item.operationId === row.operationId)
  if (routeReadState.value !== 'loaded' || !current || routeConfiguration.value.scope.productionPlanId !== Number(selectedRoutePlanId.value)) return false
  selectedOperationId.value = String(current.operationId)
  selectedPlanId.value = selectedRoutePlanId.value
  selectedRoutingStepId.value = String(current.routingStepId)
  Object.keys(form).forEach(key => { form[key] = '' })
  saveMessage.value = ''
  return loadSources()
}
function optionsFor(key) {
  const name = { productTypeId: 'productTypes', modeId: 'manufacturingModes', producerRuleId: 'producers', workCenterId: 'workCenters', standardCapacityId: 'standardCapacities' }[key]
  const rows = catalog.value[name] || []
  if (hasConfigurationOptions.value && ['modeId', 'producerRuleId'].includes(key) && operationUomId.value != null) {
    return rows.filter(row => Number(row.uomId) === Number(operationUomId.value))
  }
  if (hasConfigurationOptions.value && key === 'workCenterId') {
    if (selectedCapacityMode.value?.requiresStandardCapacity === false) {
      return rows.filter(row => (catalog.value.workCenterOperationCapabilities || []).some(capability =>
        String(capability.operationId) === selectedOperationId.value && capability.workCenterId === row.id))
    }
    const matching = (catalog.value.standardCapacities || []).filter(row => String(row.operationId) === selectedOperationId.value
      && (!form.productTypeId || String(row.productTypeId) === form.productTypeId)
      && (operationUomId.value == null || Number(row.uomId) === Number(operationUomId.value)))
    return rows.filter(row => matching.some(capacity => capacity.workCenterId === row.id))
  }
  if (key !== 'standardCapacityId') return rows
  return rows.filter(row => String(row.operationId) === selectedOperationId.value
    && (!form.productTypeId || String(row.productTypeId) === form.productTypeId)
    && (!form.workCenterId || String(row.workCenterId) === form.workCenterId)
    && (!hasConfigurationOptions.value || operationUomId.value == null || Number(row.uomId) === Number(operationUomId.value)))
}
function refreshResourceSelection() {
  if (hasConfigurationOptions.value) {
    for (const key of ['modeId', 'producerRuleId', 'workCenterId']) {
      if (form[key] && !optionsFor(key).some(row => String(row.id) === form[key])) form[key] = ''
    }
    if (form.routingContextKey && !routingOptions.value.some(row => routingKey(row) === form.routingContextKey)) form.routingContextKey = ''
  }
  if (selectedCapacityMode.value?.requiresStandardCapacity === false) form.standardCapacityId = ''
  if (form.standardCapacityId && !optionsFor('standardCapacityId').some(row => String(row.id) === form.standardCapacityId)) form.standardCapacityId = ''
  if (form.traceOptionKey && !traceOptions.value.some(option => option.key === form.traceOptionKey)) form.traceOptionKey = ''
}
const draftFieldsComplete = computed(() => readState.value === 'loaded' && !busy.value && Boolean(selectedOperationId.value)
  && (explicitSelectorMode.value ? Boolean(explicitTraceState.value.trace) : (!hasTraceOptions.value || Boolean(selectedTraceOption.value)))
  && (!hasCapacityModes.value || Boolean(selectedCapacityMode.value))
  && visibleConfigurationFields.value.every(field => optionsFor(field.key).some(row => String(row.id) === form[field.key]))
  && ['ruleCode', 'ruleName', 'version', 'effectiveFrom'].every(key => String(form[key]).trim())
  && (!hasConfigurationOptions.value || (Boolean(selectedQuantityContract.value) && Boolean(selectedScopeContract.value)
    && Boolean(form.expression.trim())
    && (!selectedQuantityContract.value.requiresBasisQuantity || Boolean(form.basisQuantity.trim()))
    && (!selectedQuantityContract.value.requiresBasisUomId || (catalog.value.units || []).some(row => String(row.id) === form.basisUomId))
    && (!selectedScopeContract.value.requiresRoutingContext || Boolean(selectedRoutingContext.value)))))
const canPreview = computed(() => hasConfigurationOptions.value && draftFieldsComplete.value && previewState.value !== 'loading'
  && hasRequiredPreparationContext.value
  && (!selectedPlanId.value || matchingSteps.value.some(row => String(row.id) === selectedRoutingStepId.value))
  && Number.isInteger(catalog.value.companyId) && typeof pdeApi.previewOperationWorkloadSourceConfiguration === 'function')
const canSave = computed(() => props.mode === 'maintain' && draftFieldsComplete.value
  && hasRequiredPreparationContext.value
  && configureAuthorization.value.allowed === true && Boolean(form.reason.trim())
  && (!hasConfigurationOptions.value || currentPreview.value?.configurationPreview?.passed === true))

function clearDraftPreview() {
  previewSequence += 1
  previewFacts.value = null
  previewState.value = 'idle'
  previewError.value = ''
}
async function previewSourceConfiguration() {
  if (!canPreview.value) return false
  const request = ++previewSequence
  const identity = draftIdentity.value
  const payload = sourcePayload()
  const requestContext = { companyId: catalog.value.companyId }
  if (selectedPlanId.value && selectedRoutingStepId.value) {
    Object.assign(requestContext, { planId: Number(selectedPlanId.value), routingStepId: Number(selectedRoutingStepId.value) })
  }
  const operationId = Number(selectedOperationId.value)
  previewFacts.value = null
  previewError.value = ''
  previewState.value = 'loading'
  try {
    const value = unwrap(await pdeApi.previewOperationWorkloadSourceConfiguration(operationId, payload, requestContext))
    if (request !== previewSequence || identity !== draftIdentity.value) return false
    const scope = value?.scope
    if (value?.contractVersion !== CONTRACT || value.factSource !== 'server'
      || value.businessWriteCount !== 0 || value.auditWriteCount !== 0 || value.generated !== false || value.allocationSaved !== false
      || scope?.companyId !== requestContext.companyId || scope?.operationId !== operationId
      || (requestContext.planId ? scope?.productionPlanId !== requestContext.planId || scope?.routingStepId !== requestContext.routingStepId
        : scope?.productionPlanId != null || scope?.routingStepId != null)
      || !sameTrace(value.requestPayload, payload) || typeof value.configurationPreview?.passed !== 'boolean'
      || value.configurationPreview.isPersisted !== false || value.nativeValidation?.savedRule !== false) {
      throw new Error('草稿校验响应与本次配置或范围不一致，结果未展示。')
    }
    previewFacts.value = { ...value, draftIdentity: identity }
    previewState.value = 'loaded'
    return value.configurationPreview.passed
  } catch (error) {
    if (request !== previewSequence || identity !== draftIdentity.value) return false
    previewFacts.value = null
    previewState.value = 'read_failed'
    previewError.value = error?.response?.data?.message || error?.message || '只读草稿校验失败。'
    return false
  }
}

function reconcileStep() {
  const steps = matchingSteps.value
  if (steps.length === 1) selectedRoutingStepId.value = String(steps[0].id)
  else if (!steps.some(row => String(row.id) === selectedRoutingStepId.value)) selectedRoutingStepId.value = ''
}
async function changeOperation() {
  selectedRoutingStepId.value = ''
  reconcileStep()
  Object.keys(form).forEach(key => { form[key] = '' })
  saveMessage.value = ''
  await loadSources()
}
async function changePlan() {
  selectedRoutingStepId.value = ''
  reconcileStep()
  await loadSources()
}
function loadSources({ catalogOnly = false } = {}) {
  if (props.parentReadStatus !== 'loaded') return Promise.resolve(false)
  const key = reads.identity('source-owner', { catalogOnly, operationId: selectedOperationId.value, planId: selectedPlanId.value,
    stepId: selectedRoutingStepId.value, generation: sourceScopeEpoch })
  if (sourceLoadOwner?.key === key) return sourceLoadOwner.promise
  const selection = JSON.stringify([selectedOperationId.value, selectedPlanId.value, selectedRoutingStepId.value])
  const promise = preserveViewPosition(() => performSourceRead(catalogOnly), !catalogOnly && currentDetailMatchesSelection(),
    () => selection === JSON.stringify([selectedOperationId.value, selectedPlanId.value, selectedRoutingStepId.value])).finally(() => {
    if (sourceLoadOwner?.promise === promise) sourceLoadOwner = null
  })
  sourceLoadOwner = { key, promise }
  return promise
}
async function performSourceRead(catalogOnly = false) {
  if (props.parentReadStatus !== 'loaded') return false
  const request = ++readSequence
  const scope = readScope()
  const operationId = selectedOperationId.value
  const planId = selectedPlanId.value
  const stepId = selectedRoutingStepId.value
  const params = !catalogOnly && operationId ? { operationId: Number(operationId) } : {}
  if (!catalogOnly && operationId && planId && stepId) Object.assign(params, { productionPlanId: Number(planId), routingStepId: Number(stepId) })
  serverFacts.value = null
  readState.value = 'loading'
  readError.value = ''
  try {
    const read = reads.run({ purpose: operationId && planId && stepId ? '工序计划步骤详细追溯' : '工序来源目录',
      url: componentReadUrl('/api/pde/a1-foundation/operations/', { ...params, action: 'operationWorkloadSources' }),
      params: { ...params, generation: sourceScopeEpoch }, read: () => pdeApi.getOperationWorkloadSources(params) })
    const raw = await read
    if (request !== readSequence || operationId !== selectedOperationId.value || planId !== selectedPlanId.value
      || stepId !== selectedRoutingStepId.value || scope !== readScope()) return false
    const validationStart = reads.clock()
    const result = validateFacts(unwrap(raw))
    validateRequestedScope(result, params)
    if (String(result.catalog.companyId) !== String(viewIdentity().companyId)) throw new Error('正式来源所属公司与当前身份不一致，当前事实未展示。')
    serverFacts.value = result
    if (hasConfigurationOptions.value && !form.expression) form.expression = catalog.value.expressionContract.defaultExpression || ''
    reads.stage(read, 'validationMs', validationStart)
    readState.value = 'loaded'
    const commitStart = reads.clock()
    await nextTick()
    if (request === readSequence && scope === readScope()) reads.stage(read, 'vueCommitMs', commitStart)
    return true
  } catch (error) {
    if (request !== readSequence || scope !== readScope()) return false
    serverFacts.value = null
    readState.value = 'read_failed'
    readError.value = error?.response?.data?.message || error?.message || '正式来源事实读取失败。'
    return false
  }
}
function savedSourceReadback(payload, receipt) {
  const nativeRule = receipt?.nativeResult?.rules?.find(row => row.code === payload.ruleCode && row.version === payload.version)
  const expectedId = receipt?.ruleId ?? nativeRule?.id
  const source = configuration.value?.sources?.find(row => row.ruleCode === payload.ruleCode && row.ruleVersion === payload.version
    && Number(row.operationId) === payload.operationId && Number(row.productTypeId) === payload.productTypeId
    && Number(row.manufacturingModeId) === payload.modeId && Number(row.workCenterId) === payload.workCenterId
    && (payload.standardCapacityId == null ? row.standardCapacityId === null : Number(row.standardCapacityId) === payload.standardCapacityId)
    && (payload.capacityMode == null || row.capacityMode === payload.capacityMode)
    && Number(row.sourceSelector?.producerRuleId) === payload.producerRuleId
    && sameTrace(row.sourceSelector?.traceEquals, payload.traceEquals)
    && (payload.quantityBasis == null || (row.quantityBasis === payload.quantityBasis
      && (row.quantityExpression || row.sourceExpression) === payload.expression
      && (!Object.hasOwn(payload, 'basisQuantity') || String(row.quantityBasisContract?.basisQuantity) === String(payload.basisQuantity))
      && (!Object.hasOwn(payload, 'basisUomId') || Number(row.quantityBasisContract?.basisUomId) === payload.basisUomId)
      && sameTrace(row.routingContext || null, payload.routingContext || null)
      && row.effectiveFrom === payload.effectiveFrom && (row.effectiveTo || null) === (payload.effectiveTo || null)))
    && (expectedId == null || Number(row.ruleId) === Number(expectedId)))
  if (configuration.value?.hasValidSourceConfiguration !== true || !source || !Number.isInteger(source.ruleId) || source.ruleId <= 0) {
    throw new Error('独立读回尚未证明本次发布方案的精确规则、来源和资源身份，请读取当前正式结果后核对。')
  }
  return source
}
function sameTrace(left, right) {
  return canonicalSnapshot(left) === canonicalSnapshot(right)
}
function canonicalSnapshot(value) {
  const normalize = value => Array.isArray(value) ? value.map(normalize) : value && typeof value === 'object'
    ? Object.fromEntries(Object.keys(value).sort().map(key => [key, normalize(value[key])])) : value
  return JSON.stringify(normalize(value))
}
async function saveSource() {
  if (!canSave.value) return
  const routeRefresh = invalidateRouteOverview()
  saving.value = true
  saveMessage.value = ''
  saveReadbackFailed.value = false
  let submitted = false
  try {
    const payload = { ...sourcePayload(), operationId: Number(selectedOperationId.value), reason: form.reason }
    if (selectedCapacityMode.value?.requiresPlanPreparation) {
      payload.generationContext = { productionPlanId: Number(selectedPlanId.value), routingStepId: Number(selectedRoutingStepId.value) }
    }
    const receipt = unwrap(await pdeApi.saveOperationWorkloadSource(payload))
    submitted = true
    if (!await loadSources()) {
      failRouteOverview(routeRefresh, '保存请求已返回，但来源事实独立读回失败；当前路线配置尚未重新核对。')
      saveReadbackFailed.value = true
      saveMessage.value = '保存请求已返回，但来源事实独立读回失败；请刷新核对后再办理。'
      return
    }
    const saved = savedSourceReadback(payload, receipt)
    if (ownsRouteRefresh(routeRefresh) && selectedRoutePlanId.value) await loadRouteOverview()
    saveMessage.value = receipt?.statusLabel || '来源方案保存结果已返回，已重新读取正式来源事实。'
    emit('saved', { operationId: payload.operationId, ruleId: saved.ruleId })
  } catch (error) {
    failRouteOverview(routeRefresh, '来源方案保存或独立读回未完成；当前路线配置尚未重新核对。')
    saveReadbackFailed.value = true
    saveMessage.value = (submitted ? '保存请求已返回，后续核对失败：' : '来源方案未确认保存：') + (error?.response?.data?.message || error?.message || '请读取当前正式结果。')
  } finally {
    saving.value = false
  }
}
function invalidateRouteOverview() {
  routeScopeEpoch += 1
  const token = { request: ++routeReadSequence, planId: selectedRoutePlanId.value }
  routeFacts.value = null
  routeReadError.value = ''
  routeReadState.value = token.planId ? 'loading' : 'idle'
  return token
}
function ownsRouteRefresh(token) {
  return token.request === routeReadSequence && token.planId === selectedRoutePlanId.value
}
function failRouteOverview(token, message) {
  if (!ownsRouteRefresh(token)) return
  routeFacts.value = null
  routeReadState.value = token.planId ? 'read_failed' : 'idle'
  routeReadError.value = token.planId ? message : ''
}
function refreshSourceFacts({ restoreRememberedPosition = false } = {}) {
  ensureViewIdentity()
  if (props.parentReadStatus !== 'loaded') return Promise.resolve(false)
  const key = reads.identity('refresh-owner', { operationId: selectedOperationId.value, planId: selectedPlanId.value,
    stepId: selectedRoutingStepId.value, routePlanId: selectedRoutePlanId.value })
  if (sourceRefreshOwner?.key === key) return sourceRefreshOwner.promise
  const promise = preserveViewPosition(performSourceRefresh, true, () => true, restoreRememberedPosition || !viewHasCompletedRead).finally(() => {
    if (sourceRefreshOwner?.promise === promise) sourceRefreshOwner = null
  })
  sourceRefreshOwner = { key, promise }
  return promise
}
async function performSourceRefresh() {
  if (props.parentReadStatus !== 'loaded') return false
  rememberViewPosition()
  ensureViewIdentity()
  const scope = readScope()
  sourceScopeEpoch += 1
  const routeRefresh = invalidateRouteOverview()
  const catalogLoaded = await loadSources({ catalogOnly: true })
  if (!catalogLoaded || scope !== readScope()) {
    failRouteOverview(routeRefresh, '当前正式目录读取失败；保留查看选择，当前路线事实未知。')
    return false
  }
  try {
    const reconciled = reconcileOperationWorkloadView(navigationSnapshot(), serverFacts.value, viewIdentity().companyId)
    applyNavigation(reconciled.value)
    if (!selectedRoutePlanId.value) { routeReadState.value = 'idle'; routeReadError.value = '' }
    viewContextNotices.value = [...(identityChangeNotice ? [identityChangeNotice] : []), ...reconciled.reasons]
    identityChangeNotice = ''
    rememberView()
  } catch (error) {
    serverFacts.value = null
    readState.value = 'read_failed'
    readError.value = error.message
    failRouteOverview(routeRefresh, error.message)
    return false
  }
  const loaded = selectedOperationId.value ? await loadSources() : true
  if (scope !== readScope() || routeRefresh.request !== routeReadSequence) return false
  if (!loaded) {
    failRouteOverview(routeRefresh, '来源事实刷新失败；当前路线配置尚未重新核对。')
    return false
  }
  const routeLoaded = selectedRoutePlanId.value ? await loadRouteOverview() : true
  return loaded && routeLoaded
}
watch([selectedOperationId, selectedPlanId, selectedRoutingStepId, selectedRoutePlanId, routeExpandedStepIds, expandedTraceKeys], rememberView, { deep: true, flush: 'sync' })
globalThis.window?.addEventListener?.('scroll', rememberViewPosition, { passive: true, capture: true })
watch(() => props.refreshKey, () => refreshSourceFacts({ restoreRememberedPosition: true }), { immediate: true })
watch([() => props.invalidateKey, () => props.parentReadStatus], ([invalidateKey, status], previous = []) => {
  // Becoming loaded starts the refreshKey read; it must not cancel that read.
  if (status === 'loaded' && invalidateKey === previous[0]) return
  if (status !== 'loaded' && previous[1] === 'loaded' && viewHasCompletedRead && navigationReadDepth === 0) {
    const top = currentViewPosition()
    if (top !== null) viewScrollTop = top
    rememberView()
  }
  readSequence += 1
  routeReadSequence += 1
  previewSequence += 1
  sourceScopeEpoch += 1
  routeScopeEpoch += 1
  serverFacts.value = null
  routeFacts.value = null
  readError.value = ''
  routeReadError.value = ''
  readState.value = props.parentReadStatus === 'failed' ? 'read_failed' : 'idle'
  routeReadState.value = props.parentReadStatus === 'failed' ? 'read_failed' : 'idle'
}, { flush: 'sync' })
watch(selectedOperationId, () => { form.sourceSelectorMode = 'CATALOG'; explicitTraceRows.value = [{ key:'',valueType:'string',value:'' }] })
watch(draftIdentity, clearDraftPreview, { flush: 'sync' })
onBeforeUnmount(() => { rememberViewPosition(); globalThis.window?.removeEventListener?.('scroll', rememberViewPosition, true); readSequence += 1; routeReadSequence += 1; previewSequence += 1; reads.dispose(); observability?.unregister?.(observabilityProvider) })
</script>

<style scoped>
.operation-workload-source{margin:16px 0;padding:16px;border:1px solid #d6e0ed;border-radius:10px;background:#fff;min-width:0}
.operation-workload-source :deep(.pce-business-status){white-space:normal;overflow-wrap:anywhere}.configured-source,dd{overflow-wrap:anywhere;min-width:0}dt{flex-shrink:0}
.source-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.source-header h4{margin:0 0 5px}.source-header p,p{margin:5px 0;color:#52627a}h5{font-size:15px;margin:0 0 10px}h6{font-size:14px;margin:0 0 8px}
.draft-actions{display:flex;flex-wrap:wrap;gap:10px}.draft-preview{margin-top:15px;padding-top:12px;border-top:1px solid #e2e8f0}
.operation-selector{display:block;max-width:440px;margin:14px 0}.source-fields{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.source-fields label,.source-reason{min-width:0}label span{display:block;margin:0 0 5px;font-weight:600;color:#34445b}
.route-source-overview{margin:18px 0;padding:15px 0;border-top:1px solid #e2e8f0;border-bottom:1px solid #e2e8f0;min-width:0}.route-overview-controls{display:flex;align-items:end;gap:12px;margin-bottom:12px}.route-overview-controls label{width:min(440px,100%)}.route-summary{margin:10px 0}.route-source-overview :deep(.pce-enterprise-row-actions button){font-size:12px;padding:6px}.route-source-overview :deep(.pce-enterprise-list-table){min-width:0}
.route-workload-detail{padding:12px 18px;max-width:1200px;overflow-wrap:anywhere}.route-workload-detail h6{margin:0 0 8px}.route-workload-detail p{margin:5px 0}.input-preparation>details>summary{cursor:pointer;font-weight:600;padding:8px 0}
input,select,textarea{box-sizing:border-box;width:100%;padding:9px;border:1px solid #cbd5e1;border-radius:7px;background:#fff;color:#26364d}textarea{min-height:75px;resize:vertical}.source-reason{display:block;margin:12px 0}
button{padding:9px 12px;border:1px solid #3568dc;border-radius:7px;background:#3568dc;color:#fff;cursor:pointer}button:disabled,fieldset:disabled button{opacity:.55;cursor:not-allowed}fieldset{border:0;margin:0;padding:0;min-width:0}
.configuration-overview,.plan-source-read,.source-maintenance{padding-top:15px;margin-top:15px;border-top:1px solid #e2e8f0}.legacy-explanation{padding:10px;background:#f5f7fa;border-radius:7px}.configured-source{margin-top:8px;padding:10px;border:1px solid #dce4ef;border-radius:7px}.configured-source strong{margin-right:10px}
.quantity-states{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:12px 0}.quantity-states>article{min-width:0;padding:12px;border:1px solid #dce4ef;border-radius:8px}.quantity{font-size:16px;font-weight:700;color:#243750}.quantity-item{padding:8px 0;border-top:1px solid #edf0f5;overflow-wrap:anywhere}
.input-preparation{margin:12px 0;padding:12px;border:1px solid #dce4ef;border-radius:8px;overflow-wrap:anywhere}.preparation-basis{margin-top:10px;padding-top:8px;border-top:1px solid #edf0f5}.input-preparation ul{margin:6px 0;padding-left:22px;color:#52627a}
.source-notice{padding:9px;background:#f2f6fc;border-radius:7px}.source-error{padding:9px;background:#fff2f0;border:1px solid #e5b2ac;border-radius:7px;color:#9f241d}.resolved-step{align-self:end;padding:10px;background:#f5f7fa;border-radius:7px}.source-maintenance>p{margin-bottom:12px}summary{cursor:pointer;font-size:12px;color:#45607e}dl{margin:8px 0}dl>div{display:flex;gap:10px;margin:4px 0}dt{color:#64748b}dd{margin:0;overflow-wrap:anywhere}
.explicit-source-conditions{grid-column:1/-1;padding:12px;border:1px solid #cad5e3;border-radius:6px}.explicit-source-conditions>.source-fields{margin-bottom:10px}
@media(max-width:1100px){.source-fields,.quantity-states{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.source-fields,.quantity-states{grid-template-columns:1fr}.source-header{flex-direction:column}}
</style>
