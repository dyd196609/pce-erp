<template>
  <section
    class="production-foundation-maintenance"
    :class="{ 'routing-acceptance-mode': routingSubview }"
    data-acceptance-id="ENTERPRISE_FOUNDATION_FORMAL_MAINTENANCE"
    data-fact-source="server"
    data-maintenance-owner="EMD"
    data-formal-maintenance-implementation="ProductionFoundationMaintenance"
    data-duplicate-formal-maintenance-implementations="0"
    :data-load-status="loadStatus"
    :data-formal-model="currentIdentity.dataSource"
    :data-page-key="currentIdentity.pageKey"
    :data-api-url="factLoadFacts.apiUrl || currentIdentity.api"
    :data-module-key="pageState.moduleId"
    :data-registry-key="currentIdentity.navigationKey"
    :data-active-mode="pageState.mode"
    :data-rendered-component="pageState.mode==='maintain' ? (currentIdentity.maintenanceComponent || currentIdentity.component) : currentIdentity.component"
    :data-runtime-id="frontendRuntimeIdentity.buildRuntimeId"
    :data-router-registry-hash="frontendRuntimeIdentity.routerRegistryHash"
    :data-module-registry-hash="frontendRuntimeIdentity.moduleRegistryHash"
    :data-page-component-hash="frontendRuntimeIdentity.pageComponentHash"
    :data-api-record-count="currentIdentity.dataSource === 'system.Process' ? currentRecordCount : undefined"
    :data-read-diagnostics="JSON.stringify(readDiagnostics)"
    data-read-diagnostics-kind="non-business-receive-parse-and-vue-timing"
    :data-latest-base-data-template="latestTemplateAdoption ? latestTemplateVersion : undefined"
    :data-template-adoption-status="latestTemplateAdoption?.adoptionStatus"
    :data-provider-state="providerState"
  >
    <section v-if="identityError" class="identity-error" role="alert" data-page-identity-mismatch="true">
      <h2>PAGE IDENTITY MISMATCH</h2>
      <p>{{ identityError }}</p>
    </section>
    <el-dialog v-model="foundationDetailVisible" :title="`${currentDefinition.label}详情`" width="min(1200px,96vw)">
      <PceBusinessDetailCard :detail="foundationBusinessDetail" />
      <p>此为当前公司服务端业务记录。只读总览不代表没有正常维护权限；维护须满足后台权限、身份及对象阶段保护。</p>
      <el-button v-if="canMaintain && currentIdentity.availableModes.includes('maintain')" @click="openDetailMaintenance">进入本模块正常维护</el-button>
      <FoundationRoutingWorkbench v-if="selectedEntity==='routings' && foundationDetailRow" :routing-id="foundationDetailRow.id" :can-maintain="canMaintain && pageState.mode==='maintain'" />
      <p v-if="maintenanceAuthorizationBlockMessage">{{ maintenanceAuthorizationBlockMessage }}</p>
    </el-dialog>
    <template v-if="!identityError">
    <p v-if="standardRoutingSubentity">此为标准路线的从属只读资料。结构、顺序和新增版本统一在<router-link :to="{path:'/foundation/master-data/routings',query:{mode:'maintain'}}">企业基础资料→工艺路线</router-link>办理；订单执行选择请到订单工序执行安排。</p>
    <FoundationBreadcrumb v-if="!routingSubview" :show-acceptance-center="false" :group="activeGroup.label" :module="currentDefinition.label" />
    <header v-if="!routingSubview" class="maintenance-header">
      <div>
        <p class="eyebrow">企业基础资料 · Enterprise Master Data</p>
        <h2>{{ selectedEntity === 'engineering-rule-definitions' ? '工程规则定义' : (engineeringBreakdownWorkspace ? '工艺／拆单基础数据' : '企业基础资料正式维护') }}</h2>
        <p v-if="engineeringBreakdownWorkspace">直接维护基础选项、产品适用关系、工艺路线和业务参数；各分组继续写入现有正式对象、权限与审计链。</p>
        <p v-else>按物料与供应、产品工程、制造资源和仓储基础组织；所有保存均写入正式服务端事实。</p>
      </div>
      <div class="maintenance-header-actions">
        <router-link v-if="ruleReturnLocation" class="return-action" :to="ruleReturnLocation">{{ ruleReturnLabel }}</router-link>
        <button type="button" :disabled="loadStatus === 'loading'" @click="loadFacts">刷新服务端事实</button>
      </div>
    </header>

    <div v-if="ruleReturnLocation" class="rule-navigation-context">
      <strong>返回业务上下文</strong>
      <template v-if="queryText(route.query.navigationScope) !== 'rules-entry'">
        <span>订单：{{ route.query.orderNo || '未提供' }}</span>
        <span>来源：{{ route.query.sourceRecord ? `#${route.query.sourceRecord}` : '未提供' }}</span>
        <span>工程版本：{{ route.query.engineeringVersion || '未提供' }}</span>
      </template>
      <span v-else>进入方式：工程规则安全入口（无订单上下文）</span>
      <span>查看范围：{{ ruleReturnScopeLabel }}</span>
      <small>以上仅用于安全返回与业务提示；企业共用规则仍按当前公司、适用范围及服务端权限读取，不按订单过滤。</small>
    </div>

    <div v-if="!routingSubview" class="fact-strip">
      <article><small>维护入口</small><strong>{{ engineeringBreakdownWorkspace ? '工艺／拆单基础数据' : '企业基础资料' }}</strong></article>
      <article><small>事实来源</small><strong>{{ facts.factSource || '-' }}</strong></article>
      <article><small>localStorage正式事实</small><strong>{{ facts.legacyLocalStorageFormalFactCount ?? '-' }}</strong></article>
      <article><small>当前分组</small><strong>{{ activeGroup.label }}</strong></article>
      <article v-if="selectedEntity === 'operations'"><small>正式工序总数</small><strong>{{ currentRecordCount ?? '未知' }}</strong></article>
    </div>

    <nav v-if="!routingSubview" class="group-tabs" aria-label="生产基础资料业务分组">
      <button
        v-for="group in groups"
        :key="group.key"
        type="button"
        :class="{ active: selectedGroup === group.key }"
        @click="selectGroup(group.key)"
      >
        {{ group.label }}
      </button>
    </nav>

    <div class="maintenance-layout">
      <aside v-if="!routingSubview" class="entity-nav">
        <button
          v-for="entityKey in activeGroup.entities"
          :key="entityKey"
          type="button"
          :class="{ active: selectedEntity === entityKey }"
          @click="selectEntity(entityKey)"
        >
          <span>{{ definitions[entityKey].label }}</span>
          <strong>{{ entityCountLabel(entityKey) }}</strong>
        </button>
      </aside>

      <section class="entity-workspace">
        <header v-if="!routingSubview" class="entity-header">
          <div>
            <h3>{{ currentDefinition.label }}</h3>
            <p>{{ currentDefinition.help }}</p>
          </div>
          <button v-if="canCreateCurrentEntity && pageState.mode === 'maintain'" type="button" @click="startNewForm">新增{{ currentDefinition.shortLabel }}</button>
        </header>

        <nav class="operation-actions" :aria-label="`${currentIdentity.displayName}模块操作`">
          <button type="button" :class="{ active: pageState.mode === 'view' }" @click="setModuleMode('view')">查看数据</button>
          <button v-if="canMaintain && currentIdentity.availableModes.includes('maintain')" type="button" :class="{ active: pageState.mode === 'maintain' }" @click="setModuleMode('maintain')">维护</button>
          <button v-if="currentIdentity.availableModes.includes('source_compare')" type="button" :class="{ active: pageState.mode === 'source_compare' }" @click="setModuleMode('source_compare')">来源对照</button>
          <button v-if="currentIdentity.availableModes.includes('acceptance')" type="button" class="acceptance-action" :class="{ active: pageState.mode === 'acceptance' }" @click="setModuleMode('acceptance')">人工验收</button>
        </nav>

        <p
          v-if="maintenanceAuthorizationBlockMessage"
          class="authorization-blocker"
          role="alert"
          data-state="maintenance-authorization-denied"
        >
          {{ maintenanceAuthorizationBlockMessage }}
        </p>

        <p v-if="facts.requestIdentity && loadStatus === 'loaded'" class="read-identity">本次服务端读取身份：{{ facts.requestIdentity.username }}；公司：{{ facts.requestIdentity.companyId }}。已与本标签账户核对。</p>

        <p v-if="loadStatus === 'failed' && message" class="provider-error" role="alert">
          {{ message }}
        </p>

        <p v-else-if="providerFailed" class="provider-error" role="alert">
          读取失败，当前数据数量未知 · {{ providerStateLabel }}
        </p>

        <p v-else-if="loadStatus === 'loading' || loadStatus === 'idle'" class="provider-loading" data-state="loading">正在读取企业基础资料服务端事实…</p>

        <OperationWorkloadSourcePanel
          v-if="selectedEntity === 'operations' && operationPanelInitialized && !operationSubview"
          v-show="loadStatus === 'loaded' && !providerFailed"
          :operations="currentRows"
          :mode="pageState.mode"
          :refresh-key="workloadSourceRefreshKey"
          :invalidate-key="workloadSourceInvalidateKey"
          :parent-read-status="loadStatus"
          @saved="loadFacts"
        />

        <Group3AOperationTargetedRevalidationPage v-if="pageState.moduleId === 'operation' && pageState.mode === 'acceptance'" embedded />
        <Group3ManufacturingEngineeringAcceptancePage v-else-if="pageState.moduleId === 'operation' && pageState.mode === 'source_compare'" entity="operations" embedded />
        <Group3ManufacturingEngineeringAcceptancePage v-else-if="pageState.moduleId === 'routing' && entitySubview" entity="routings" embedded />
        <Group3ManufacturingEngineeringAcceptancePage v-else-if="pageState.moduleId === 'bom' && entitySubview" entity="boms" embedded />

        <template v-else-if="loadStatus === 'loaded' && !providerFailed">

        <section
          v-if="selectedEntity === 'engineering-rule-definitions'"
          class="rule-registration-materials"
          data-section="engineering-rule-registration-materials"
        >
          <header>
            <div>
              <h4>整单规则办理材料</h4>
              <p>以下内容来自现有可执行规则包合同，仅供正式登记审阅；与下方服务端正式规则分开统计。</p>
            </div>
            <strong>{{ ruleRegistrationCandidates.length }} 套</strong>
          </header>
          <article v-for="candidate in ruleRegistrationCandidates" :key="`${candidate.ruleCode}@${candidate.version}`">
            <div>
              <span><strong>{{ candidate.ruleName }}</strong><small>{{ candidate.ruleCode }}@{{ candidate.version }}</small></span>
              <button
                v-if="pageState.mode === 'maintain' && canCreateCurrentEntity"
                type="button"
                class="candidate-action"
                @click="prepareRuleCandidate(candidate)"
              >
                {{ candidate.formalRecordCount ? '打开已有正式记录' : '填写登记资料' }}
              </button>
            </div>
            <b>{{ candidate.registrationStatusLabel }}</b>
            <p>{{ candidate.businessExplanation?.purpose }}</p>
            <dl>
              <div><dt>正式记录</dt><dd>{{ candidate.formalRecordCount ? `${candidate.formalRecordCount} 条` : '0 条' }}</dd></div>
              <div><dt>适用范围</dt><dd>{{ candidate.applicability?.scope || '—' }} / {{ candidate.applicability?.resultScope || '—' }}</dd></div>
              <div><dt>执行实现</dt><dd>{{ candidate.executionAdapter }}</dd></div>
              <div><dt>内容指纹</dt><dd>{{ candidate.specificationHash }}</dd></div>
            </dl>
            <small>查看材料不会新建草稿、改变规则状态或读取订单、来源、基线及核算结果。</small>
          </article>
          <p v-if="ruleReviewWorkQueueMessage" class="rule-work-queue">{{ ruleReviewWorkQueueMessage }}</p>
        </section>

        <PceEnterpriseListTable
          v-if="latestTemplateAdoption"
          ref="wave1TableRef"
          :contract="wave1ListContract"
          :page-id="currentIdentity.pageKey"
          :table-id="`${currentIdentity.pageKey}-table`"
          :rows="currentRows"
          :table-rows="wave1FilteredRows"
          :filter-schema="wave1FilterSchema"
          :filters="wave1Filters"
          :quick-search="wave1QuickSearch"
          :advanced-visible="wave1AdvancedVisible"
          :selected-count="wave1SelectedRows.length"
          :active-filter-count="wave1ActiveFilterCount"
          :sort-text="wave1SortText"
          :primary-field="wave1PrimaryField"
          :primary-label="wave1PrimaryLabel"
          :primary-width="wave1PrimaryWidth"
          min-width="1100px"
          @update:quick-search="wave1QuickSearch = $event"
          @search="wave1AppliedSearch = wave1QuickSearch"
          @toggle-advanced="wave1AdvancedVisible = !wave1AdvancedVisible"
          @clear-filters="wave1ClearFilters"
          @clear-sort="wave1ClearSort"
          @export-current="wave1ExportCurrent"
          @clear-selection="wave1ClearSelection"
          @update-filter="(field, value) => wave1Filters[field] = value"
          @selection-change="wave1SelectedRows = $event"
          @sort-change="wave1HandleSort"
        >
          <template v-if="latestTemplateAdoption.importApplicability !== 'NOT_APPLICABLE_READ_ONLY'" #toolbar-extension>
            <LatestBaseDataImportToolbarExtension
              :entity="selectedEntity"
              :entity-name="currentDefinition.label"
              @import-committed="loadFacts"
            />
          </template>
          <template #columns>
            <el-table-column
              v-for="column in wave1SecondaryColumns"
              :key="column.key"
              :prop="column.key"
              :label="column.label"
              :min-width="column.minWidth || 150"
              sortable
              show-overflow-tooltip
          >
            <template #default="{ row }">{{ displayValue(row[column.key], column) }}</template>
          </el-table-column>
          </template>
          <template #actions="{ row }">
            <el-button link type="primary" @click="viewFoundationDetail(row)">查看详情</el-button>
            <template v-if="selectedEntity === 'engineering-rule-definitions'">
              <el-button link type="primary" @click="viewEngineeringRule(row)">查看</el-button>
              <el-button v-if="pageState.mode === 'maintain' && canEditRuleRow(row)" link type="primary" @click="editRow(row)">编辑草稿</el-button>
              <el-button v-else-if="pageState.mode === 'maintain' && canTransitionRuleRow(row)" link type="primary" @click="editRow(row)">状态维护</el-button>
            </template>
            <el-button v-else-if="canMaintain" link type="primary" @click="editRow(row)">编辑</el-button>
            <span v-else>只读</span>
          </template>
        </PceEnterpriseListTable>

        <div v-else class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th v-for="column in currentDefinition.columns" :key="column.key">{{ column.label }}</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="currentRows.length === 0">
                <td :colspan="currentDefinition.columns.length + 2" class="empty">暂无服务端正式记录</td>
              </tr>
              <tr v-for="(row, index) in currentRows" :key="row.id">
                <td>{{ index + 1 }}</td>
                <td v-for="column in currentDefinition.columns" :key="column.key">
                  {{ displayValue(row[column.key], column) }}
                </td>
                <td>
                  <button type="button" class="link" @click="viewFoundationDetail(row)">查看详情</button>
                  <button v-if="selectedEntity === 'engineering-rule-definitions'" type="button" class="link" @click="viewEngineeringRule(row)">查看</button>
                  <button v-else-if="canMaintain" type="button" class="link" @click="editRow(row)">编辑</button>
                  <span v-else>只读</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p
          v-if="canShowMaintenanceForm && pageState.mode === 'maintain' && !maintenanceFormOpen"
          class="maintenance-ready-notice"
          role="status"
        >
          已进入维护模式。请点击“新增{{ currentDefinition.shortLabel }}”，或点击现有记录的“编辑”打开正式维护表单。
        </p>

        <form
          v-if="canShowMaintenanceForm && pageState.mode === 'maintain' && maintenanceFormOpen"
          ref="maintenanceFormRef"
          class="entity-form"
          data-state="maintenance-form-open"
          @submit.prevent="save"
        >
          <header>
            <h4>{{ maintenanceFormTitle }}</h4>
            <span>正式路径：Page → API → Service → AuthorizationService → Transaction → Audit</span>
          </header>
          <p class="form-open-status" role="status">{{ formOpenStatus }}</p>
          <p v-if="maintenancePrerequisiteMessages.length" class="form-blocker" role="alert">
            {{ maintenancePrerequisiteMessages.join('；') }}
          </p>
          <p v-if="saveError" class="form-blocker" role="alert">{{ saveError }}</p>
          <section v-if="isNewCandidateRegistration" class="rule-registration-preview" data-state="unsaved-rule-registration">
            <strong>未保存登记资料，尚未形成正式规则</strong>
            <p>已从服务端受治理方案带入；打开、预览、清空可填写项或取消办理都不会生成正式ID或改变状态。</p>
            <dl>
              <div><dt>中文业务名称</dt><dd>{{ selectedRuleCandidate.ruleName }}</dd></div>
              <div><dt>正式编码</dt><dd>{{ selectedRuleCandidate.ruleCode }}</dd></div>
              <div><dt>登记版本</dt><dd>{{ selectedRuleCandidate.version }}</dd></div>
              <div><dt>适用范围</dt><dd>当前公司共用 · {{ selectedRuleCandidate.applicability?.scope }}</dd></div>
              <div><dt>内容指纹</dt><dd>{{ selectedRuleCandidate.specificationHash }}</dd></div>
              <div><dt>资料来源</dt><dd>既有可执行规则包服务端方案</dd></div>
            </dl>
          </section>

          <section v-if="editingId && selectedEntity === 'engineering-rule-definitions'" class="rule-state-guidance">
            <h5>当前规则与状态动作</h5>
            <dl>
              <div><dt>当前规则</dt><dd>{{ currentRow?.rule_name }}（{{ currentRow?.rule_code }}）</dd></div>
              <div><dt>当前版本</dt><dd>{{ currentRow?.version }}</dd></div>
              <div><dt>当前状态</dt><dd>{{ engineeringRuleStatusLabel(currentRow?.status) }}</dd></div>
              <div><dt>当前可做动作</dt><dd>{{ currentRuleActionLabel }}</dd></div>
            </dl>
            <p>{{ currentRuleActionReason }}</p>
            <p class="rule-readonly-notice">定义只读用于保护维护人员已提交的计算内容；评审／发布人员审核内容并推进状态，不在评审时直接改写定义。</p>
          </section>

          <section v-if="showApprovedEffectivityCorrection" class="rule-effectivity-correction" data-state="approved-id11-effectivity-correction">
            <h5>ID11 已发布规则有效期受控纠正</h5>
            <p>本动作只把已批准目标的失效日期从 <strong>2030-09-25</strong> 纠正为空值；不会重评审、重发布或修改定义。</p>
            <dl>
              <div><dt>正式身份</dt><dd>ID{{ currentRow?.id }} · {{ currentRow?.rule_code }}@{{ currentRow?.version }}</dd></div>
              <div><dt>公司</dt><dd>COMP001（公司ID {{ currentRow?.company_id }}）</dd></div>
              <div><dt>状态／生效</dt><dd>{{ engineeringRuleStatusLabel(currentRow?.status) }} · {{ currentRow?.effective_from }}</dd></div>
              <div><dt>当前失效日期</dt><dd>{{ currentRow?.effective_to || '长期有效（未设置失效日期）' }}</dd></div>
              <div><dt>目标值</dt><dd>长期有效（数据库空值）</dd></div>
              <div><dt>批准引用</dt><dd>{{ approvedEffectivityScope.approvalReference }}</dd></div>
            </dl>
            <p v-if="approvedEffectivityCorrectionComplete" class="correction-complete">服务端读回：失效日期为空，已按长期有效显示。</p>
            <button
              v-else-if="approvedEffectivityCorrectionPending"
              type="button"
              class="correction-action"
              :disabled="correctingEffectivity"
              @click="correctApprovedRuleEffectivity"
            >
              {{ correctingEffectivity ? '纠正并写入审计中…' : '受控纠正为长期有效' }}
            </button>
            <p v-else class="correction-blocked">当前服务端事实与获批旧值不一致，页面不会发起纠正。</p>
          </section>

          <section v-if="maintenanceRuleBusinessExplanation" class="rule-business-explanation">
            <h5>中文业务说明</h5>
            <p><strong>规则用于什么：</strong>{{ maintenanceRuleBusinessExplanation.purpose }}</p>
            <div class="rule-business-columns">
              <article><h6>适用对象</h6><ul><li v-for="item in maintenanceRuleBusinessExplanation.applicableObjects" :key="item">{{ item }}</li></ul></article>
              <article><h6>不适用／停止条件</h6><ul><li v-for="item in maintenanceRuleBusinessExplanation.excludedObjects" :key="item">{{ item }}</li></ul></article>
            </div>
            <h6>需要的输入</h6>
            <ul><li v-for="item in maintenanceRuleBusinessExplanation.inputs" :key="`${item.technicalName}-${item.name}`"><strong>{{ item.name }}</strong>（{{ item.unit }}）<small>{{ item.technicalName }} · {{ item.description }}</small></li></ul>
            <h6>主要计算关系／条件分支</h6>
            <ul><li v-for="item in maintenanceRuleBusinessExplanation.calculationRelations" :key="item">{{ item }}</li></ul>
            <h6>产生的结果</h6>
            <ul><li v-for="item in maintenanceRuleBusinessExplanation.outputs" :key="`${item.technicalName}-${item.name}`"><strong>{{ item.name }}</strong>（{{ item.unit }}）<small>{{ item.technicalName }}</small></li></ul>
            <p><strong>缺条件：</strong>{{ maintenanceRuleBusinessExplanation.missingCondition }}</p>
            <p><strong>精度与版本：</strong>{{ maintenanceRuleBusinessExplanation.precisionRule }} {{ maintenanceRuleBusinessExplanation.versionRule }}</p>
          </section>

          <template v-if="isNewCandidateRegistration">
            <div class="form-grid governed-rule-fields">
              <label><span>规则编码</span><input :value="form.rule_code" readonly /><small>系统从受治理方案带入，不含“@V1”。</small></label>
              <label><span>规则名称</span><input :value="form.rule_name" readonly /></label>
              <label><span>规则类型</span><input :value="engineeringRuleKindLabel(form.rule_kind)" readonly /></label>
              <label><span>规则版本</span><input :value="selectedRuleCandidate.version" readonly /><small>本方案严格登记为V1；不套用通用首版V1.0。</small></label>
              <label><span>生效日期</span><input v-model="form.effective_from" type="date" /></label>
              <label><span>失效日期</span><input v-model="form.effective_to" type="date" /></label>
            </div>
            <details class="rule-technical-trace">
              <summary>技术定义与追溯（默认收起，无需员工编写）</summary>
              <dl>
                <div><dt>执行实现</dt><dd>{{ selectedRuleCandidate.executionAdapter }}</dd></div>
                <div><dt>规范指纹</dt><dd>{{ selectedRuleCandidate.specificationHash }}</dd></div>
              </dl>
              <textarea :value="form.specification" readonly aria-label="规则规范技术原文" />
            </details>
          </template>
          <div v-else class="form-grid">
            <template v-for="field in generalFormFields" :key="field.key">
            <section v-if="selectedEntity === 'operations' && editingId && field.key === 'quantity_driver'" class="operation-source-scheme-field" data-operation-source-scheme :data-read-state="operationSchemeState">
              <h4>作业量来源方案</h4>
              <p>选择仅暂存于本表单；点击“保存并回读”后才维护当前范围的正式选择，其他范围保持不变。</p>
              <p v-if="operationSchemeState === 'loading'" role="status">正在读取正式候选和当前选择，当前事实未知…</p>
              <p v-else-if="operationSchemeState === 'read_failed'" role="alert" class="source-scheme-error">{{ operationSchemeError }}</p>
              <template v-else-if="operationSchemeState === 'loaded'">
                <p data-source-selection-status>{{ operationSchemeFacts.sourceSelection.statusLabel }}</p>
                <ul class="source-scheme-current" aria-label="已保存的全部范围方案">
                  <li v-for="selection in operationSchemeFacts.sourceSelection.selections" :key="operationSchemeKey(selection)">
                    <strong>{{ selection.label }}</strong>
                    <span>{{ selection.quantityBasisLabel }}；{{ selection.uomLabel }}；{{ selection.productTypeLabel }}；{{ selection.routingContextLabel }}</span>
                    <span v-for="rule in selection.ruleRefs" :key="rule.ruleId">{{ rule.label }}</span>
                  </li>
                </ul>
                <label>
                  <span>选择正式方案（含完整规则组及适用范围）</span>
                  <select v-model="operationSchemeDraftKey" aria-label="作业量来源方案" :disabled="saving || !operationSchemeCanConfigure">
                    <option value="">不改选，保留全部当前范围</option>
                    <option v-for="option in operationSchemeFacts.sourceSchemes" :key="operationSchemeKey(option)" :value="operationSchemeKey(option)">{{ operationSchemeOptionLabel(option) }}</option>
                  </select>
                </label>
                <p v-if="operationSchemeFacts.sourceSchemes.length === 0">本次正式读取没有可选方案；不会按历史文字匹配或自动创建。</p>
                <p v-if="!operationSchemeCanConfigure" class="source-scheme-error">{{ operationSchemeFacts.configureAuthorization.statusLabel || operationSchemeFacts.configureAuthorization.reason || '当前账号不具备正式来源方案维护权限。' }}</p>
                <div v-if="operationSchemeDraft" class="source-scheme-draft">
                  <strong>{{ operationSchemeDraft.label }}</strong>
                  <p>{{ operationSchemeDraft.quantityBasisLabel }}；{{ operationSchemeDraft.uomLabel }}；{{ operationSchemeDraft.productTypeLabel }}；{{ operationSchemeDraft.routingContextLabel }}</p>
                  <p v-for="rule in operationSchemeDraft.ruleRefs" :key="rule.ruleId">{{ rule.label }}</p>
                  <p>{{ operationSchemeChanged ? '本次待保存改选，仅影响上述同一范围。' : '与该范围当前正式选择相同，本次不提交来源改选。' }}</p>
                  <button type="button" class="secondary" :disabled="saving" @click="operationSchemeDraftKey = ''">取消本次改选</button>
                </div>
              </template>
              <button v-if="operationSchemeState === 'read_failed'" type="button" class="secondary" :disabled="saving" @click="loadOperationSourceSchemes">重新读取正式方案</button>
              <label class="source-scheme-history"><span>{{ field.label }}（只读追溯）</span><input :value="form[field.key]" readonly /><small>{{ field.note }}</small></label>
            </section>
            <label v-else>
              <span>{{ field.label }}<b v-if="field.required"> *</b></span>
              <select v-if="field.type === 'select'" v-model="form[field.key]" :required="field.required" :disabled="fieldReadOnly(field)">
                <option value="">请选择</option>
                <option v-for="option in field.options" :key="option.value" :value="option.value">
                  {{ option.label }}
                </option>
              </select>
              <select v-else-if="field.type === 'ref'" v-model="form[field.key]" :required="field.required" :disabled="fieldReadOnly(field)">
                <option value="">请选择</option>
                <option v-for="row in rowsFor(field.entity)" :key="row.id" :value="row.id">
                  {{ rowLabel(row) }}
                </option>
              </select>
              <textarea v-else-if="field.type === 'textarea' || field.type === 'json'" v-model="form[field.key]" :placeholder="field.placeholder || ''" :required="field.required" :readonly="fieldReadOnly(field)" />
              <input v-else-if="field.type === 'boolean'" v-model="form[field.key]" type="checkbox" :disabled="fieldReadOnly(field)" />
              <input v-else v-model="form[field.key]" :type="field.type || 'text'" :inputmode="field.inputMode" :step="field.step" :min="field.min" :placeholder="field.placeholder || ''" :required="field.required" :readonly="fieldReadOnly(field)" />
              <small v-if="field.note">{{ field.note }}</small>
            </label>
            </template>
          </div>
          <EngineeringRuleDefinitionEditor
            v-if="selectedEntity === 'engineering-rule-definitions' && !isNewCandidateRegistration"
            :key="`rule-${editingId || 'new'}-${formSession}`"
            v-model="form.specification"
            :rule-code="form.rule_code"
            :rule-version="form.version || 'V1.0'"
            :readonly="ruleFormFieldsReadOnly"
            @validity="structuredDefinitionValid = $event"
          />
          <EngineeringSourceFormatInput
            v-if="selectedEntity === 'engineering-source-records'"
            :key="`source-${editingId || 'new'}-${formSession}`"
            v-model="form.source_payload"
            :rules="sourceFormatRules"
            :company-id="factLoadFacts.tenantId"
            :rules-error="sourceFormatRulesError"
            :workbook-contexts="sourceWorkbookContexts"
            :workbook-contexts-error="sourceWorkbookContextsError"
            :readonly="Boolean(editingId && currentRow?.status !== 'draft')"
            @validity="sourceFormatValid = $event"
            @previewed="applyNativeSourcePreview"
          />
          <label class="reason-field">
            <span>维护原因 *</span>
            <textarea v-model="form.reason" required placeholder="说明资料来源和本次维护原因" />
          </label>
          <div class="form-actions">
            <button v-if="canSaveCurrentForm" type="submit" :disabled="saving || !maintenancePrerequisitesReady">{{ saving ? '保存中…' : '保存并回读' }}</button>
            <button v-if="isNewCandidateRegistration" type="button" class="secondary" @click="clearRuleRegistrationInputs">清空可填写内容</button>
            <button v-if="isNewCandidateRegistration" type="button" class="secondary" @click="cancelRuleRegistration">取消本次登记</button>
            <button v-else type="button" class="secondary" @click="startNewForm">清空</button>
            <button type="button" class="secondary" @click="closeMaintenanceForm">关闭表单</button>
            <button
              v-for="transition in availableTransitions"
              :key="transition.target"
              type="button"
              class="secondary"
              :disabled="saving"
              @click="transitionCurrent(transition.target)"
            >
              {{ transition.label }}
            </button>
          </div>
        </form>
        </template>
      </section>
    </div>

    <el-dialog
      v-model="ruleDetailVisible"
      title="查看工程规则"
      width="760px"
      class="engineering-rule-detail-dialog"
      destroy-on-close
    >
      <p v-if="ruleDetailStatus === 'loading'" class="provider-loading">正在读取工程规则正式内容…</p>
      <p v-else-if="ruleDetailStatus === 'failed'" class="provider-error" role="alert">{{ ruleDetailError }}</p>
      <section v-else-if="ruleDetailRow" class="engineering-rule-detail" data-state="rule-detail-loaded">
        <p v-if="ruleDetailRow.status === 'released'" class="rule-readonly-notice">当前版本已发布，不可直接修改；查看不会创建草稿或改变状态。</p>
        <dl>
          <div><dt>规则编码</dt><dd>{{ ruleDetailRow.rule_code }}</dd></div>
          <div><dt>规则名称</dt><dd>{{ ruleDetailRow.rule_name }}</dd></div>
          <div><dt>规则版本</dt><dd>{{ ruleDetailRow.version }}</dd></div>
          <div><dt>状态</dt><dd>{{ engineeringRuleStatusLabel(ruleDetailRow.status) }}</dd></div>
          <div><dt>规则类型</dt><dd>{{ engineeringRuleKindLabel(ruleDetailRow.rule_kind) }}</dd></div>
          <div><dt>生效范围</dt><dd>{{ ruleDetailRow.effective_from || '未指定' }} 至 {{ ruleDetailRow.effective_to || '长期有效' }}</dd></div>
        </dl>
        <h4>规则定义正式内容</h4>
        <section v-if="ruleDetailBusinessExplanation" class="rule-business-explanation">
          <h5>中文业务说明</h5>
          <p><strong>规则用于什么：</strong>{{ ruleDetailBusinessExplanation.purpose }}</p>
          <div class="rule-business-columns">
            <article><h6>适用对象</h6><ul><li v-for="item in ruleDetailBusinessExplanation.applicableObjects" :key="item">{{ item }}</li></ul></article>
            <article><h6>不适用／停止条件</h6><ul><li v-for="item in ruleDetailBusinessExplanation.excludedObjects" :key="item">{{ item }}</li></ul></article>
          </div>
          <h6>输入、计算关系与结果</h6>
          <ul><li v-for="item in ruleDetailBusinessExplanation.inputs" :key="`${item.technicalName}-${item.name}`">输入：{{ item.name }}（{{ item.unit }}；{{ item.technicalName }}）</li></ul>
          <ul><li v-for="item in ruleDetailBusinessExplanation.calculationRelations" :key="item">关系：{{ item }}</li></ul>
          <ul><li v-for="item in ruleDetailBusinessExplanation.outputs" :key="`${item.technicalName}-${item.name}`">结果：{{ item.name }}（{{ item.unit }}；{{ item.technicalName }}）</li></ul>
          <p><strong>缺条件：</strong>{{ ruleDetailBusinessExplanation.missingCondition }}</p>
          <p><strong>精度与版本：</strong>{{ ruleDetailBusinessExplanation.precisionRule }} {{ ruleDetailBusinessExplanation.versionRule }}</p>
        </section>
        <details class="rule-technical-trace">
          <summary>技术定义与追溯</summary>
          <pre>{{ ruleDetailSpecification }}</pre>
        </details>
      </section>
      <template #footer>
        <el-button @click="ruleDetailVisible = false">关闭并返回规则列表</el-button>
      </template>
    </el-dialog>

    <p v-if="message && loadStatus !== 'failed'" class="message">{{ message }}</p>
    </template>
  </section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { pdeApi } from '@/api/pde.js'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import FoundationBreadcrumb from '@/meta/components/FoundationBreadcrumb.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import LatestBaseDataImportToolbarExtension from '@/meta/components/LatestBaseDataImportToolbarExtension.vue'
import Group3AOperationTargetedRevalidationPage from '@/meta/pages/Group3AOperationTargetedRevalidationPage.vue'
import Group3ManufacturingEngineeringAcceptancePage from '@/meta/pages/Group3ManufacturingEngineeringAcceptancePage.vue'
import OperationWorkloadSourcePanel from '@/meta/components/OperationWorkloadSourcePanel.vue'
import EngineeringRuleDefinitionEditor from '@/meta/components/EngineeringRuleDefinitionEditor.vue'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import FoundationRoutingWorkbench from '@/meta/components/FoundationRoutingWorkbench.vue'
import EngineeringSourceFormatInput from '@/meta/components/EngineeringSourceFormatInput.vue'
import { validateWorkbookCatalog } from '@/meta/runtime/sourceFormatMaintenanceForm.js'
import { useUserStore } from '@/stores/counter.js'
import { getTabAuthEpoch, readTabIdentity } from '@/meta/runtime/tabAuthenticationContext.js'
import {resolveCurrentIdentity} from '@/meta/runtime/pageTitleManager.js'
import {isScopedFoundationView,assertFoundationRequestIdentity} from '@/meta/runtime/foundationRoutingRead.js'
import { createComponentReadLifecycle } from '@/meta/runtime/componentReadLifecycle.js'
import { frontendRuntimeIdentity } from '@/meta/runtime/frontendRuntimeIdentity.js'
import {
  foundationMaintenanceGroups,
  getFoundationCanonicalModuleByEntity,
  resolveFoundationPageState,
  serializeFoundationMode,
} from '@/meta/master-data/foundationEntryUnificationRegistry.js'
import { findOrderProductionTemplateAdoption } from '@/meta/master-data/orderProductionBaseDataTemplateAdoption.js'
import { LATEST_BASE_DATA_TEMPLATE_VERSION } from '@/meta/contracts/latestBaseDataTemplateContract.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import {
  ENGINEERING_RULE_FILTER_SCHEMA,
  ENGINEERING_RULE_KIND_LABELS,
  canEditEngineeringRule,
  canTransitionEngineeringRule,
  engineeringRuleStatusLabel,
} from '@/meta/runtime/engineeringRuleListPresentation.js'
import { factLoadFailureFromError } from '@/meta/runtime/pceFactLoadContract.js'
import { dailyCapacityMaintenancePayload } from '@/meta/runtime/apsDailyCapacityMaintenance.js'
import {
  LATEST_BASE_DATA_PROVIDER_STATES,
  latestBaseDataProviderStateLabel,
  resolveLatestBaseDataProviderState,
} from '@/meta/runtime/latestBaseDataProviderState.js'

const props = defineProps({
  initialEntity: { type: String, default: 'materials' },
})

const enumOptions = (pairs) => pairs.map(([value, label]) => ({ value, label }))
const workCenterAssignmentRoleOptions = Object.freeze(enumOptions([
  ['primary', '主工作中心'],
  ['alternative', '备选工作中心'],
]))
const statusOptions = enumOptions([['draft', '草稿'], ['designed', '已设计'], ['released', '已发布']])
const versionStatusLabels = { draft: '草稿', reviewed: '已评审', released: '已发布', obsolete: '已失效' }
const bool = (key, label, defaultValue = true) => ({ key, label, type: 'boolean', default: defaultValue })
const text = (key, label, required = false, note = '') => ({ key, label, type: 'text', required, note })
const date = (key, label) => ({ key, label, type: 'date' })
const number = (key, label, required = false, step = 'any') => ({ key, label, type: 'number', required, step })
const exactDecimal = (key, label) => ({ key, label, type: 'text', inputMode: 'decimal', note: '填写十进制数字；保留原始精度，缺失时留空。' })
const refField = (key, label, entity, required = false) => ({ key, label, entity, type: 'ref', required })
const select = (key, label, options, required = false) => ({ key, label, options, type: 'select', required })
const json = (key, label, required = false) => ({ key, label, type: 'json', required, default: '{}', placeholder: '请输入有效JSON' })
const col = (key, label, type = '') => ({ key, label, type })
const enumCol = (key, label, options) => ({ key, label, type: 'enum', options })

const definitions = Object.freeze({
  units: { label: '计量单位', shortLabel: '单位', help: '物料、BOM和产能共享的正式计量单位；换算语义为“1当前单位 = 换算系数 × 基准单位”。', columns: [col('code', '编码'), col('name', '名称'), col('symbol', '符号'), col('dimension', '维度'), col('conversion_base_name', '换算基准'), col('conversion_factor', '换算系数'), col('decimal_places', '小数位')], fields: [text('code', '单位编码', true), text('name', '单位名称', true), text('symbol', '单位符号'), select('dimension', '计量维度', enumOptions([['count', '数量'], ['length', '长度'], ['area', '面积'], ['volume', '体积'], ['mass', '质量'], ['time', '时间'], ['other', '其他/待治理']]), true), refField('conversion_base_id', '换算基准单位', 'units'), { key: 'conversion_factor', label: '换算系数', type: 'number', required: true, step: 'any', default: 1, note: '1当前单位 = 换算系数 × 基准单位；基准单位本身保持1。' }, number('decimal_places', '小数位', true, '1'), bool('is_active', '启用')] },
  'material-categories': { label: '物料类别', shortLabel: '物料类别', help: 'Material.category唯一正式分类；类别与用途是两个不同业务维度。', columns: [col('code', '类别编码'), col('name', '类别名称'), col('parent_name', '上级类别'), col('sort_order', '排序'), col('is_active', '状态', 'boolean')], fields: [text('code', '类别编码', true), text('name', '类别名称', true), refField('parent_id', '上级类别', 'material-categories'), { key: 'sort_order', label: '排序', type: 'number', required: true, step: '1', default: 0 }, bool('is_active', '启用')] },
  materials: { label: '物料档案', shortLabel: '物料', help: '唯一Material事实；类别、用途、规格和基本单位共同参与Canonical精确重复保护，适用部位/说明不参与。', columns: [col('code', '物料编码'), col('name', '物料名称'), col('category_name', '物料类别'), col('purpose', '用途'), col('specification', '规格'), col('base_uom_name', '基本单位'), col('supply_type_display', '供应属性'), col('is_active', '状态', 'boolean')], fields: [text('code', '物料编码', false, '可留空；保存时由服务端正式编码规则自动生成。'), text('name', '物料名称', true), refField('category_id', '物料类别', 'material-categories', true), text('purpose', '用途'), text('specification', '规格', false, '自由文本；尺寸可按实际规格使用mm，BOM数量单位独立维护。'), select('material_type', '物料类型', enumOptions([['raw', '原材料'], ['semi', '半成品'], ['finished', '成品'], ['auxiliary', '辅料'], ['fixed_asset', '固定资产']]), true), select('unit_status', '基本单位状态', enumOptions([['confirmed', '已确认'], ['not_confirmed', '待维护']]), true), text('unit', '兼容单位（待维护时留空）'), refField('base_uom_id', '正式基本单位', 'units'), refField('purchase_uom_id', '采购单位', 'units'), bool('is_purchased', '采购件', false), bool('is_produced', '自制件', false), { key: 'application_notes', label: '适用部位/说明', type: 'textarea' }, bool('is_active', '启用')] },
  'product-categories': { label: '产品分类 / 产品族', shortLabel: '产品分类', help: '层级分类承担产品族语义，不建立第二套ProductFamily。', columns: [col('code', '编码'), col('name', '名称'), col('industry_type', '行业语义'), col('is_active', '状态', 'boolean')], fields: [text('code', '分类编码'), text('name', '分类名称', true), refField('parent_id', '上级分类', 'product-categories'), text('industry_type', '行业语义代码', true, '使用配置代码，不新增行业专属Schema。'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'manufacturing-process-types': { label: '工艺类型', shortLabel: '工艺类型', help: '公司内可维护的制造/涂饰工艺维度；具体名称来自正式数据。', columns: [col('code', '编码'), col('name', '名称'), col('is_active', '状态', 'boolean')], fields: [text('code', '工艺类型编码'), text('name', '工艺类型名称', true), text('description', '说明'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'engineering-breakdown-options': { label: '工程录入基础选项', shortLabel: '基础选项', help: '门开方向、线型、封边方式、包装方式按各自业务语义维护，不写入制造工艺类型；来源包装旧值明确排除。', columns: [col('option_type', '选项类别'), col('code', '编码'), col('name', '中文名称'), col('source_reference', '来源追溯'), col('is_active', '状态', 'boolean')], fields: [select('option_type', '选项类别', enumOptions([['door_opening_direction', '门开方向'], ['line_style', '线型'], ['edge_method', '封边方式'], ['packaging_method', '包装方式']]), true), text('code', '选项编码', true), text('name', '中文名称', true), text('description', '业务说明'), text('source_reference', '来源追溯'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  products: { label: '产品定义', shortLabel: '产品', help: '标准/按单工程只区分制造定义形成路径，均引用正式Material。', columns: [col('product_code', '产品编码'), col('product_name', '产品名称'), col('manufacturing_definition_mode', '形成模式'), col('status', '状态', 'status')], fields: [text('product_code', '产品编码'), text('product_name', '产品名称', true), text('specification', '规格'), text('model', '型号'), refField('category_id', '产品分类', 'product-categories'), refField('material_id', '成品/半成品物料', 'materials', true), text('emd_material_code', '正式物料编码', true), select('manufacturing_definition_mode', '制造定义形成模式', enumOptions([['standard', '标准制造'], ['order_engineered', '按单工程制造']]), true), select('status', '状态', statusOptions, true), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'product-versions': { label: '产品版本', shortLabel: '产品版本', help: '首次版本由系统自动产生V1.0；状态只通过正式工程生命周期动作推进。', columns: [col('product_id', '产品', 'ref:products'), col('version_no', '版本'), col('version_status', '状态', 'status'), col('effective_date', '生效日期')], fields: [refField('product_id', '产品', 'products', true), date('effective_date', 'PCE建档/发布生效日期'), date('expire_date', '失效日期'), text('change_reason', '变更原因')] },
  workshops: { label: '车间 / 生产区域', shortLabel: '车间', help: 'Workshop是组织/生产区域事实，不等同于WorkCenter。', columns: [col('code', '编码'), col('name', '名称'), col('department_id', '部门ID'), col('is_active', '状态', 'boolean')], fields: [text('code', '车间编码'), text('name', '车间名称', true), number('department_id', '正式部门ID', true, '1'), bool('is_active', '启用')] },
  teams: { label: '班组', shortLabel: '班组', help: '班组是实际人员组织／作业编组，可按淡旺季增减并设置有效期；不等同于工序或工作中心。', columns: [col('code', '班组编码'), col('name', '班组名称'), col('workshop_id', '所属车间', 'ref:workshops'), col('department_id', '所属部门', 'ref:team-departments'), col('effective_from', '生效日期'), col('effective_to', '失效日期'), col('is_active', '状态', 'boolean')], fields: [text('code', '班组编码', true), text('name', '班组名称', true), refField('workshop_id', '所属车间', 'workshops', true), refField('department_id', '所属部门', 'team-departments'), text('leader', '班组长（兼容文字）'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'team-memberships': { label: '班组成员', shortLabel: '成员关系', help: '成员按有效期加入实际班组；不会迁移员工部门、岗位或权限。', columns: [col('team_id', '班组', 'ref:teams'), col('employee_id', '员工', 'ref:team-membership-employees'), col('role_label', '班组内角色'), col('effective_from', '生效日期'), col('effective_to', '失效日期'), col('is_active', '状态', 'boolean')], fields: [refField('team_id', '班组', 'teams', true), refField('employee_id', '员工', 'team-membership-employees', true), text('role_label', '班组内角色'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'work-centers': { label: '工作中心', shortLabel: '工作中心', help: '生产资源归属中心；产能由StandardCapacity独立维护，工作日历按PCE-MFG-CALENDAR-V1.0写入产能策略。', columns: [col('code', '编码'), col('name', '名称'), col('department_id', '所属部门', 'ref:team-departments'), col('workshop_id', '所属车间', 'ref:workshops'), { ...col('dailyCapacitySummary', '日产能（产品类型 / 工序 / 单位）'), minWidth: 420 }, col('capacity_policy', '产能与日历策略'), col('is_active', '状态', 'boolean')], fields: [{ key: 'code', label: '工作中心编码', type: 'text', readOnly: true, serverGenerated: true, placeholder: '保存后由系统自动生成', note: '保存后由系统自动生成；正式编码由服务端统一编码规则分配，新增和编辑均不可人工填写或修改。' }, text('name', '工作中心名称', true), refField('department_id', '所属部门（可选）', 'team-departments'), refField('workshop_id', '所属车间', 'workshops'), json('resource_capabilities', '资源能力边界'), json('capacity_policy', '产能与制造日历策略', false), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  operations: { label: '工序', shortLabel: '工序', help: '正式工序及其核算、计量、作业量来源、转序、资源和验收状态；展示顺序不代表具体产品路线。', columns: [col('display_order', '展示顺序'), col('code', '工序编码'), col('name', '工序名称'), col('calculation_basis_label', '核算方式'), col('calculation_uom_label', '计量单位'), col('workload_source_status', '正式作业量来源'), col('quantity_driver', '历史来源说明'), col('transition_mode_label', '转序方式'), col('is_active', '启用状态', 'boolean'), col('source_mapping', '来源映射'), col('acceptance_status', '验收状态')], fields: [number('display_order', '展示顺序', true, '1'), text('code', '工序编码'), text('name', '工序名称', true), refField('workshop_id', '所属车间 / 生产区域', 'workshops', true), refField('work_center_id', '默认工作中心（可待维护）', 'work-centers'), select('operation_kind', '工序类型', enumOptions([['atomic', '单工序'], ['group', '工序组']]), true), select('calculation_basis', '核算维度', enumOptions([['count', '数量'], ['length', '长度'], ['area', '面积'], ['volume', '体积'], ['mass', '质量'], ['time', '时间'], ['other', '其他'], ['undetermined', '待确认']]), true), refField('calculation_uom_id', '核算计量单位', 'units'), text('quantity_driver', '历史来源说明', false, '保留原历史文字；正式作业量来源在来源方案中配置，不按该文字查询。'), select('default_transition_mode', '默认转序方式', enumOptions([['GENERAL', '一般工序'], ['KITTING', '齐套工序']]), true), text('skill_required', '技能要求'), bool('quality_check_required', '质量检查点', false), text('description', '说明'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'work-center-operation-capabilities': { label: '工序候选工作中心', shortLabel: '工序工作中心关系', help: '工序与工作中心的正式多对多能力关系；主工作中心和备选工作中心均按真实资料维护。', columns: [col('operation_id', '工序', 'ref:operations'), col('work_center_id', '工作中心', 'ref:work-centers'), enumCol('assignment_role', '资源角色', workCenterAssignmentRoleOptions), col('capability_code', '能力编码'), col('effective_from', '生效日期'), col('effective_to', '失效日期'), col('is_active', '状态', 'boolean')], fields: [refField('operation_id', '工序', 'operations', true), refField('work_center_id', '工作中心', 'work-centers', true), select('assignment_role', '资源角色', workCenterAssignmentRoleOptions, true), text('capability_code', '能力编码'), json('capability_parameters', '能力参数'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'operation-team-capabilities': { label: '工序可承担班组', shortLabel: '工序班组关系', help: '多对多、带有效期的能力与安排关系；不会因本次说明自动让全部班组承担全部工序。', columns: [col('operation_id', '工序', 'ref:operations'), col('team_id', '班组', 'ref:teams'), col('effective_from', '生效日期'), col('effective_to', '失效日期'), col('note', '能力与安排说明'), col('is_active', '状态', 'boolean')], fields: [refField('operation_id', '工序', 'operations', true), refField('team_id', '班组', 'teams', true), date('effective_from', '生效日期'), date('effective_to', '失效日期'), text('note', '能力与安排说明'), bool('is_active', '启用')] },
  'work-center-team-assignments': { label: '工作中心可用班组', shortLabel: '工作中心班组关系', help: '工作中心与班组的正式多对多分配；是否主班组不改变班组组织身份。', columns: [col('work_center_id', '工作中心', 'ref:work-centers'), col('team_id', '班组', 'ref:teams'), col('is_primary', '主班组', 'boolean'), col('is_active', '状态', 'boolean')], fields: [refField('work_center_id', '工作中心', 'work-centers', true), refField('team_id', '班组', 'teams', true), bool('is_primary', '主班组', false), bool('is_active', '启用')] },
  equipment: { label: '设备', shortLabel: '设备', help: '设备引用正式工作中心；接口身份只登记边界。', columns: [col('code', '编码'), col('name', '名称'), col('work_center_id', '工作中心', 'ref:work-centers'), col('is_active', '状态', 'boolean')], fields: [text('code', '设备编码'), text('name', '设备名称', true), text('equipment_type', '设备类型'), refField('work_center_id', '工作中心', 'work-centers', true), text('interface_identity', '标准接口标识'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'standard-capacities': {
    label: '标准产能', shortLabel: '标准产能',
    help: '按产品工艺、工序和工作中心读取正式产能及服务端三态解释，准备与转运时间使用天。此列表只展示正式标准产能记录；缺行不等于来源空白或不经过，准备记录业务裁决值也不替代标准产能数量。不把历史小时产能换名成日产能。',
    columns: [col('code', '产能编码'), col('name', '产能名称'), col('operation_name', '工序名称'), col('product_type_code', '产品工艺编码'), col('capacity_business_status_label', '产能业务含义'), col('capacity_source_status_label', '来源依据'), col('capacity_record_status_label', '正式产能记录'), col('product_type_id', '产品 / 半成品类型', 'ref:capacity-product-types'), col('work_center_id', '工作中心', 'ref:work-centers'), col('quantity', '正式每日标准产量'), col('uom_id', '产能单位', 'ref:units'), col('preparation_days', '准备时间（天）'), col('transfer_days', '转运时间（天）'), col('effective_from', '生效日期'), col('statusLabel', '状态')],
    fields: [text('code', '产能编码'), text('name', '产能名称', true), refField('product_type_id', '产品 / 半成品类型', 'capacity-product-types', true), refField('operation_id', '工序', 'operations', true), refField('work_center_id', '工作中心', 'work-centers', true), select('measurement_status', '正式产能记录值', enumOptions([['measured', '正数：经过且有产能数据'], ['zero_capacity', '0：经过但无法准确核算，不计定量产能占用']]), true), exactDecimal('quantity', '正式每日标准产量'), refField('uom_id', '产能单位', 'units', true), { ...select('time_basis', '产能时间基准', enumOptions([['day', '每日']]), true), default: 'day', readOnly: true }, { ...number('time_basis_quantity', '时间基准（天）', true), default: 1, readOnly: true }, { ...select('time_unit', '准备 / 转运时间单位', enumOptions([['DAY', '天']]), true), default: 'DAY', readOnly: true }, exactDecimal('preparation_days', '准备时间（天，缺失时留空）'), exactDecimal('transfer_days', '转运时间（天，缺失时留空）'), json('conditions', '适用条件'), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')],
  },
  boms: { label: 'BOM主表', shortLabel: 'BOM主表', help: '标准、分类模板与按单BOM共用唯一ProductBOM及适用范围契约。', columns: [col('bom_code', 'BOM编码'), col('name', '名称'), col('applicability_scope', '适用范围'), col('product_id', '产品', 'ref:products'), col('product_category_id', '产品分类', 'ref:product-categories'), col('status', '状态', 'status')], fields: [text('bom_code', 'BOM编码'), text('name', 'BOM名称', true), select('applicability_scope', '适用主体类型', enumOptions([['PRODUCT_DEFINITION', '长期产品定义'], ['PRODUCT_CATEGORY', '产品分类/模板'], ['ORDER_ENGINEERING', '订单工程实例']]), true), refField('product_id', '长期产品（按范围填写）', 'products'), refField('product_category_id', '产品分类（按范围填写）', 'product-categories'), refField('order_engineering_instance_id', '订单工程实例（按范围填写）', 'order-engineering-instances'), select('status', '状态', enumOptions([['draft', '草稿'], ['released', '已发布'], ['obsolete', '已失效']]), true), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'bom-versions': { label: 'BOM版本', shortLabel: 'BOM版本', help: '版本继承BOM主表适用主体；产品/产品版本仅用于产品级兼容。', columns: [col('bom_id', 'BOM', 'ref:boms'), col('bom_version', '版本'), col('bom_scope', '作用域'), col('status', '状态', 'status')], fields: [refField('bom_id', 'BOM主表', 'boms', true), refField('product_id', '兼容产品（仅产品级）', 'products'), refField('product_version_id', '兼容产品版本（仅产品级）', 'product-versions'), select('bom_scope', 'BOM作用域', enumOptions([['standard', '标准BOM'], ['order_specific', '按单BOM']]), true), refField('order_engineering_instance_id', '订单工程实例', 'order-engineering-instances'), date('effective_date', 'PCE建档/发布生效日期'), date('expire_date', '失效日期')] },
  'bom-items': { label: 'BOM明细', shortLabel: 'BOM明细', help: '损耗率未知保持空值/待维护；无替代记录不等于已确认无替代料。', columns: [col('bom_version_id', 'BOM版本', 'ref:bom-versions'), col('line_no', '行号'), col('material_id', '物料', 'ref:materials'), col('scrap_rate_status', '损耗率状态'), col('substitute_status', '替代料状态')], fields: [refField('bom_version_id', 'BOM版本', 'bom-versions', true), number('line_no', '行号', true, '1'), refField('material_id', '子项物料', 'materials', true), number('quantity', '数量', true), refField('uom_id', '单位', 'units', true), select('scrap_rate_status', '损耗率维护状态', enumOptions([['maintained', '已维护'], ['not_maintained', '待维护']]), true), number('scrap_rate', '损耗率（待维护时留空）'), select('substitute_status', '替代料维护状态', enumOptions([['not_maintained', '待维护'], ['confirmed_none', '已确认无替代料'], ['maintained', '已维护替代料']]), true), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'bom-substitutes': { label: 'BOM替代料', shortLabel: '替代料', help: '替代料属于BOM明细的受控子项；未维护不等于已确认无替代料。', columns: [col('bom_item_id', 'BOM明细', 'ref:bom-items'), col('substitute_material_id', '替代物料', 'ref:materials'), col('priority', '优先级'), col('conversion_rate', '换算率'), col('is_active', '状态', 'boolean')], fields: [refField('bom_item_id', 'BOM明细', 'bom-items', true), refField('substitute_material_id', '替代物料', 'materials', true), number('priority', '优先级', true, '1'), number('conversion_rate', '替代换算率', true), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  routings: { label: '工艺路线主表', shortLabel: '工艺路线', help: '唯一Routing主表；每条路线必须且只能引用一个适用主体，分类级路线同时引用可维护工艺类型。', columns: [col('routing_code', '路线编码'), col('name', '名称'), col('applicability_scope', '适用范围'), col('product_id', '产品', 'ref:products'), col('product_category_id', '产品分类', 'ref:product-categories'), col('manufacturing_process_type_id', '工艺类型', 'ref:manufacturing-process-types'), col('status', '状态', 'status')], fields: [text('routing_code', '路线编码'), text('name', '路线名称', true), select('applicability_scope', '适用主体类型', enumOptions([['PRODUCT_DEFINITION', '长期产品定义'], ['PRODUCT_CATEGORY', '产品分类/模板'], ['ORDER_ENGINEERING', '订单工程实例']]), true), refField('product_id', '长期产品（按范围填写）', 'products'), refField('product_category_id', '产品分类（按范围填写）', 'product-categories'), refField('order_engineering_instance_id', '订单工程实例（按范围填写）', 'order-engineering-instances'), refField('manufacturing_process_type_id', '工艺类型', 'manufacturing-process-types'), select('status', '状态', enumOptions([['draft', '草稿'], ['released', '已发布'], ['obsolete', '已失效']]), true), date('effective_from', '生效日期'), date('effective_to', '失效日期'), bool('is_active', '启用')] },
  'routing-versions': { label: '工艺路线版本', shortLabel: '路线版本', help: '版本继承Routing主表适用主体；产品/产品版本仅用于产品级兼容。', columns: [col('routing_id', '路线', 'ref:routings'), col('routing_version', '版本'), col('status', '状态', 'status'), col('effective_date', '生效日期')], fields: [refField('routing_id', '路线主表', 'routings', true), refField('product_id', '兼容产品（仅产品级）', 'products'), refField('product_version_id', '兼容产品版本（仅产品级）', 'product-versions'), date('effective_date', 'PCE建档/发布生效日期'), date('expire_date', '失效日期')] },
  'routing-steps': { label: '路线步骤', shortLabel: '路线步骤', help: '步骤保留既有结构并维护依赖、转序和资源选择；日产能及准备 / 转运天数在标准产能中维护，步骤天数只读，标准结构只在企业基础资料工艺路线维护；订单工序执行选择另存订单安排，不产生标准版本。', columns: [col('routing_version_id', '路线版本', 'ref:routing-versions'), col('sequence', '顺序'), col('operation_id', '工序', 'ref:operations'), col('work_center_id', '工作中心', 'ref:work-centers'), col('predecessor_sequences', '前置步骤'), col('preparation_days', '步骤准备时间（天，只读）'), col('transfer_days', '步骤转运时间（天，只读）')], fields: [refField('routing_version_id', '路线版本', 'routing-versions', true), number('sequence', '步骤顺序', true, '1'), refField('operation_id', '工序', 'operations', true), refField('workshop_id', '车间（可待维护）', 'workshops'), refField('work_center_id', '工作中心（可待维护）', 'work-centers'), refField('applies_to_item_id', '适用BOM项（可选）', 'bom-items'), json('predecessor_sequences', '前置步骤顺序'), select('effective_transition_mode', '步骤转序方式（可选覆盖）', enumOptions([['GENERAL', '一般工序'], ['KITTING', '齐套工序']])), json('resource_selection_rule', '资源选择规则'), bool('quality_checkpoint', '质量检查点', false), { key: 'instruction', label: '操作说明', type: 'textarea' }, bool('is_active', '启用')] },
  'engineering-documents': { label: '工程资料主表', shortLabel: '工程资料', help: '工程资料主表引用同一Product/BOM/Route。', columns: [col('document_no', '资料编号'), col('document_name', '资料名称'), col('document_type', '类型'), col('status', '状态', 'status')], fields: [text('document_no', '资料编号', true), text('document_name', '资料名称', true), select('document_type', '资料类型', enumOptions([['process', '工艺文件'], ['technical', '技术资料'], ['version_record', '版本记录']]), true), refField('product_id', '产品', 'products', true), refField('product_bom_id', 'BOM主表', 'boms', true), refField('routing_id', '路线主表', 'routings', true), select('status', '状态', enumOptions([['draft', '草稿'], ['released', '已发布'], ['obsolete', '已作废']]), true), date('effective_date', '生效日期')] },
  'engineering-document-versions': { label: '工程资料版本', shortLabel: '工程资料版本', help: '首次版本由系统自动产生V1.0，并锁定ProductVersion+BOMVersion+RoutingVersion。', columns: [col('document_id', '资料', 'ref:engineering-documents'), col('document_version', '版本'), col('status', '状态', 'status')], fields: [refField('document_id', '工程资料', 'engineering-documents', true), text('document_name', '资料版本名称', true), refField('related_product_id', '产品', 'products', true), refField('product_version_id', '产品版本', 'product-versions', true), refField('related_bom_id', 'BOM版本', 'bom-versions', true), refField('related_routing_id', '路线版本', 'routing-versions', true), date('effective_date', 'PCE建档/发布生效日期'), date('expire_date', '失效日期')] },
  'manufacturing-outputs': { label: '统一制造定义', shortLabel: '制造定义', help: '标准与按单工程最终均发布为ProductManufacturingOutput。', columns: [col('product_id', '产品', 'ref:products'), col('definition_mode', '模式'), col('release_status', '发布状态', 'status'), col('order_engineering_instance_id', '订单工程实例', 'ref:order-engineering-instances')], fields: [refField('product_id', '产品', 'products', true), refField('product_version_id', '产品版本', 'product-versions', true), refField('bom_version_id', 'BOM版本', 'bom-versions', true), refField('routing_version_id', '路线版本', 'routing-versions', true), refField('engineering_document_version_id', '工程资料版本', 'engineering-document-versions', true), select('definition_mode', '制造定义模式', enumOptions([['standard', '标准制造定义'], ['order_specific', '按单制造定义']]), true), refField('order_engineering_instance_id', '订单工程实例', 'order-engineering-instances'), select('engineering_status', '工程齐套状态', enumOptions([['incomplete', '不完整'], ['ready', '已齐套']]), true), date('effective_date', '生效日期')] },
  'engineering-source-records': { label: '工程来源记录', shortLabel: '工程来源', help: '受控保存原始/规范双层事实；Golden结果只用于验算，不得作为计算输入。', columns: [col('source_no', '来源编号'), col('source_name', '来源名称'), col('source_type', '来源类型'), col('source_version', '版本'), col('status', '状态', 'status')], fields: [text('source_no', '来源编号'), text('source_name', '来源名称', true), select('source_type', '来源类型', enumOptions([['order_input', '订单输入'], ['design_package', '设计包'], ['controlled_import', '受控导入'], ['manual_confirmed', '人工确认']]), true), text('source_version', '来源版本', true), json('source_payload', '原始/规范事实与Golden验证契约', true), text('content_hash', '原始文件SHA-256', true), date('effective_date', '生效日期')] },
  'engineering-rule-definitions': { label: '工程规则定义', shortLabel: '工程规则', help: '结构化维护安全表达式及来源格式映射；受治理方案使用方案自带版本。发布后定义不可直接修改。', columns: [col('rule_code', '规则编码'), col('rule_name', '规则名称'), col('version', '版本'), col('rule_kind', '类型'), col('status', '状态', 'status')], fields: [text('rule_code', '规则编码', true), text('rule_name', '规则名称', true), { ...text('version', '规则版本', true), default: 'V1.0' }, select('rule_kind', '规则类型', enumOptions([['formula', '安全表达式'], ['lookup', '受控查表'], ['aggregation', '受控聚合']]), true), json('specification', '规则规范', true), date('effective_from', '生效日期'), date('effective_to', '失效日期')] },
  warehouses: { label: '仓库', shortLabel: '仓库', help: 'Warehouse是仓储基础主数据；维护仓库不会产生库存事务。', columns: [col('code', '编码'), col('name', '名称'), col('location_code', '位置编码'), col('is_active', '状态', 'boolean')], fields: [text('code', '仓库编码', true), text('name', '仓库名称', true), text('location_code', '位置编码'), bool('is_active', '启用')] },
  'warehouse-locations': { label: '仓库库位', shortLabel: '库位', help: 'WarehouseLocation是库位身份主数据；Lot/Batch由业务交易形成，不在此维护。', columns: [col('warehouse_id', '仓库', 'ref:warehouses'), col('code', '库位编码'), col('name', '库位名称'), col('is_active', '状态', 'boolean')], fields: [refField('warehouse_id', '所属仓库', 'warehouses', true), text('code', '库位编码', true), text('name', '库位名称', true), bool('is_active', '启用')] },
})

const groups = foundationMaintenanceGroups

const transitionMap = Object.freeze({
  'product-versions': { draft: [['reviewed', '提交评审']], reviewed: [['released', '发布版本']], released: [['obsolete', '失效版本']] },
  'bom-versions': { draft: [['reviewed', '提交评审']], reviewed: [['released', '发布版本']], released: [['obsolete', '失效版本']] },
  'routing-versions': { draft: [['reviewed', '提交评审']], reviewed: [['released', '发布版本']], released: [['obsolete', '失效版本']] },
  'engineering-document-versions': { draft: [['reviewed', '提交评审']], reviewed: [['released', '发布资料']], released: [['obsolete', '失效资料']] },
  'manufacturing-outputs': { draft: [['engineering_review', '提交工程评审']], engineering_review: [['released_to_manufacturing', '发布至制造']], released_to_manufacturing: [['inactive', '失效制造定义']] },
  'engineering-source-records': { draft: [['confirmed', '确认来源']], confirmed: [['superseded', '替代来源']] },
  'engineering-rule-definitions': { draft: [['reviewed', '提交评审']], reviewed: [['released', '发布规则']], released: [['obsolete', '失效规则']] },
})

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const engineeringBreakdownWorkspace = computed(() => route.query.workspace === 'engineering-breakdown')
const initialIdentity = getFoundationCanonicalModuleByEntity(props.initialEntity)
const initialPageState = Object.freeze({
  domain: 'enterprise-master-data',
  moduleId: initialIdentity?.moduleId || '',
  mode: 'view',
  recordId: null,
  filters: Object.freeze({}),
  subview: null,
  identity: initialIdentity || Object.freeze({ dataSource: '', pageKey: '', api: '', navigationKey: '', component: '', availableModes: Object.freeze([]), displayName: '' }),
})
const foundationDetailVisible=ref(false),foundationDetailRow=ref(null)
const foundationBusinessDetail=computed(()=>({sectionTitle:`${currentDefinition.value.label}业务信息`,fields:currentDefinition.value.columns.map(column=>({label:column.label,value:displayValue(foundationDetailRow.value?.[column.key],column)}))}))
function viewFoundationDetail(row){foundationDetailRow.value=row;foundationDetailVisible.value=true}
async function openDetailMaintenance(){if(standardRoutingSubentity.value){await router.push({path:'/foundation/master-data/routings',query:{mode:'maintain'}});return}await setModuleMode('maintain');if(selectedEntity.value!=='routings'){const row=foundationDetailRow.value;foundationDetailVisible.value=false;editRow(row)}}
const facts = ref({})
const workloadSourceRefreshKey = ref(0)
const workloadSourceInvalidateKey = ref(0)
const operationPanelScope = ref(null)
const readDiagnostics = ref([])
const entityReadStates = ref({})
const operationReferencesState = ref('idle')
const operationReferencesError = ref('')
const readScope = () => {
  const identity = readTabIdentity() || {}
  return JSON.stringify([getTabAuthEpoch(), identity.userId ?? null, identity.companyId ?? null])
}
const reads = createComponentReadLifecycle({ context: () => JSON.stringify([readScope(), activeFactLoadRequest]), changed: rows => { readDiagnostics.value = rows } })
const operationPanelInitialized = computed(() => operationPanelScope.value !== null && operationPanelScope.value === readScope())
const factLoadFacts = ref({})
const loadStatus = ref('idle')
const message = ref('')
const saving = ref(false)
const correctingEffectivity = ref(false)
const approvedEffectivityReceipt = ref(null)
const pageState = ref(initialPageState)
const identityError = ref('')
const selectedGroup = ref(initialIdentity?.groupKey || '')
const selectedEntity = ref(initialIdentity?.entityKey || '')
const editingId = ref(null)
const form = reactive({ reason: '' })
const maintenanceFormRef = ref(null)
const maintenanceFormOpen = ref(false)
const formOpenStatus = ref('')
const currentEntityAuthorization = ref(null)
const saveError = ref('')
const formSession = ref(0)
const OPERATION_SOURCE_SELECTION_CONTRACT = 'PCE-OPERATION-SOURCE-SELECTION-V1'
const operationSchemeState = ref('idle')
const operationSchemeError = ref('')
const operationSchemeFacts = ref(null)
const operationSchemeDraftKey = ref('')
const operationSchemeOwner = ref('')
let operationSchemeRequest = 0
const operationSchemeDraft = computed(() => operationSchemeFacts.value?.sourceSchemes.find(option => operationSchemeKey(option) === operationSchemeDraftKey.value) || null)
const operationSchemeCanConfigure = computed(() => operationSchemeFacts.value?.configureAuthorization?.allowed === true && canMaintain.value)
const operationSchemeChanged = computed(() => {
  const option = operationSchemeDraft.value
  if (!option) return false
  return !operationSchemeFacts.value.sourceSelection.selections.some(current => sameOperationSchemeScope(current.scope, option.scope)
    && current.schemeId === option.schemeId && current.schemeHash === option.schemeHash)
})
const structuredDefinitionValid = ref(true)
const sourceFormatValid = ref(true)
const sourceFormatRules = ref([])
const sourceFormatRulesError = ref('')
const sourceWorkbookContexts = ref([]), sourceWorkbookContextsError = ref('')
let activeFactLoadRequest = 0
let pendingOperationLoad = null
const selectedRuleCandidateKey = ref('')
const ruleDetailVisible = ref(false)
const ruleDetailStatus = ref('idle')
const ruleDetailError = ref('')
const ruleDetailRow = ref(null)
const targetedFacts = ref({ focusRows: [] })
const operationFacts = ref(null)
const ruleActionAllowed = action => Boolean(facts.value.currentUserAuthorization?.[action]?.allowed)
const ruleRegistrationCandidates = computed(() => facts.value.engineeringRuleRegistrationCandidates || [])
const selectedRuleCandidate = computed(() => ruleRegistrationCandidates.value.find(
  candidate => `${candidate.ruleCode}@${candidate.version}` === selectedRuleCandidateKey.value,
) || null)
const isNewCandidateRegistration = computed(() => Boolean(selectedRuleCandidate.value) && !editingId.value)
const ruleAuthorization = computed(() => facts.value.currentUserAuthorization || {})
const canMaintain = computed(() => selectedEntity.value === 'engineering-rule-definitions'
  ? [
      'production.engineering.rule.create',
      'production.engineering.rule.update_draft',
      'production.engineering.rule.release',
    ].some(ruleActionAllowed)
  : currentEntityAuthorization.value?.allowed === true)
const standardRoutingSubentity=computed(()=>['routing-versions','routing-steps'].includes(selectedEntity.value))
const canCreateCurrentEntity = computed(() => standardRoutingSubentity.value ? false : selectedEntity.value === 'engineering-rule-definitions'
  ? ruleActionAllowed('production.engineering.rule.create')
  : canMaintain.value)
const maintenanceAuthorizationBlockMessage = computed(() => {
  if (selectedEntity.value === 'engineering-rule-definitions' || loadStatus.value !== 'loaded') return ''
  const authorization = currentEntityAuthorization.value
  if (!authorization || authorization.allowed) return ''
  return `当前账号${authorization.actor ? `“${authorization.actor}”` : ''}不能维护${currentDefinition.value.label}：${authorization.reason} `
    + `公司范围：${authorization.organizationId || '待核定'}。具体权限编码与维护身份见诊断。`
})
const maintenancePrerequisiteMessages = computed(() => {
  if (!['work-center-operation-capabilities', 'standard-capacities'].includes(selectedEntity.value)) return []
  const messages = []
  if (rowsFor('operations').length === 0) messages.push('当前公司没有可选正式工序，请先维护工序')
  if (rowsFor('work-centers').length === 0) messages.push('当前公司正式工作中心为0，请先在“工作中心”页面维护真实工作中心')
  if (selectedEntity.value === 'standard-capacities') {
    if (rowsFor('capacity-product-types').length === 0) messages.push('当前公司没有正式产能产品类型，请先补充来源明确的产品 / 半成品类型')
    if (editingId.value && (currentRow.value?.time_basis !== 'day' || Number(currentRow.value?.time_basis_quantity) !== 1)) {
      messages.push('该记录不是数量/天事实，不能直接更换时间基准；请依据真实日产能资料新增记录')
    }
  }
  return messages
})
const maintenancePrerequisitesReady = computed(() => maintenancePrerequisiteMessages.value.length === 0)
const ruleReturnLocation = computed(() => {
  if (selectedEntity.value !== 'engineering-rule-definitions') return null
  const target = String(route.query.returnTo || '')
  return target.startsWith('/pde/engineering-calculations')
    ? target
    : { path: '/pde/engineering-calculations', query: { page: 'input' } }
})
const queryText = value => String(Array.isArray(value) ? (value[0] || '') : (value || ''))
const ruleReturnLabel = computed(() => queryText(route.query.navigationScope) === 'rules-entry' ? '返回工程规则入口' : '返回工程数据录入')
const positiveIntegerText = value => {
  const text = queryText(value)
  return /^\d+$/.test(text) && Number(text) > 0 ? text : ''
}
const ruleReturnScopeLabel = computed(() => {
  if (selectedEntity.value !== 'engineering-rule-definitions') return ''
  const navigationScope = queryText(route.query.navigationScope)
  if (navigationScope === 'rules-entry') return '当前公司共用工程规则（无订单上下文）'
  const objectCount = positiveIntegerText(route.query.scopeObjectCount)
  const countLabel = objectCount ? `（${objectCount}项）` : ''
  if (navigationScope === 'source') return `整单来源${countLabel}`
  if (navigationScope === 'order-line') {
    const stableSalesOrderItemId = positiveIntegerText(route.query.salesOrderItemId)
    const salesOrderLineNo = positiveIntegerText(route.query.salesOrderLineNo)
    if (!stableSalesOrderItemId) return '销售订单行范围未核实'
    return salesOrderLineNo ? `销售订单第${salesOrderLineNo}行${countLabel}` : `已选择销售订单行${countLabel}`
  }
  return '未提供'
})
const operationSubview = computed(() => pageState.value.moduleId === 'operation' && ['acceptance', 'source_compare'].includes(pageState.value.mode))
const routingSubview = computed(() => pageState.value.moduleId === 'routing' && ['acceptance', 'source_compare'].includes(pageState.value.mode))
const entitySubview = computed(() => ['acceptance', 'source_compare'].includes(pageState.value.mode))
const newCreateIdempotencyKey = () => globalThis.crypto?.randomUUID?.()
  || `foundation-create-${Date.now()}-${Math.random().toString(16).slice(2)}`
const createIdempotencyKey = ref(newCreateIdempotencyKey())

const activeGroup = computed(() => groups.find((item) => item.key === selectedGroup.value) || Object.freeze({ key: '', label: '', entities: Object.freeze([]) }))
const currentDefinition = computed(() => definitions[selectedEntity.value] || Object.freeze({ label: '', shortLabel: '', help: '', columns: Object.freeze([]), fields: Object.freeze([]) }))
const currentIdentity = computed(() => pageState.value.identity)
const latestTemplateAdoption = computed(() => findOrderProductionTemplateAdoption(pageState.value.moduleId))
const providerState = computed(() => resolveLatestBaseDataProviderState({
  loading: loadStatus.value === 'loading' || loadStatus.value === 'idle',
  succeeded: loadStatus.value === 'loaded',
  factLoadFacts: factLoadFacts.value,
  count: currentRows.value.length,
}))
const providerStateLabel = computed(() => latestBaseDataProviderStateLabel(providerState.value))
const providerFailed = computed(() => ![
  LATEST_BASE_DATA_PROVIDER_STATES.LOADING,
  LATEST_BASE_DATA_PROVIDER_STATES.LOADED_EMPTY,
  LATEST_BASE_DATA_PROVIDER_STATES.LOADED_WITH_DATA,
].includes(providerState.value))
const calculationBasisLabels = Object.freeze({ count: '数量', length: '长度', area: '面积', volume: '体积', mass: '质量', time: '时间', other: '其他', undetermined: '待确认' })
const currentRows = computed(() => {
  const rows = rowsFor(selectedEntity.value)
  if (selectedEntity.value === 'standard-capacities') return rows.map(row => {
    const fact = row.dailyCapacityFact || {}
    const semantics = fact.capacitySemantics || row.capacitySemantics || {}
    return { ...row, operation_name: fact.operationName || '', product_type_code: fact.productTypeCode || '',
      capacity_business_status_label: semantics.statusLabel || '产能业务含义尚未核对',
      capacity_source_status_label: semantics.sourceStatusLabel || '来源依据尚未核对',
      capacity_record_status_label: semantics.recordPresenceStatusLabel || '正式产能记录尚未核对' }
  })
  if (selectedEntity.value !== 'operations') return rows
  const focusByName = Object.fromEntries((targetedFacts.value.focusRows || []).map(row => [row.operationName, row]))
  return rows.map(row => {
    const focus = focusByName[row.name] || {}
    const unit = rowsFor('units').find(item => String(item.id) === String(row.calculation_uom_id))
    return {
      ...row,
      calculation_basis_label: focus.calculationMethod || calculationBasisLabels[row.calculation_basis] || '待确认',
      calculation_uom_label: focus.calculationUom || (unit ? rowLabel(unit) : '待确认 / 来源未提供'),
      workload_source_status: [row.workloadSource?.statusLabel, row.workloadSource?.summary].filter(Boolean).join(' · ') || '尚未读取',
      transition_mode_label: focus.transitionMode || (row.default_transition_mode === 'KITTING' ? '齐套工序' : '一般工序'),
      source_mapping: focus.source || '01工序 → 正式工序',
      acceptance_status: focus.acceptanceStatus || '等待人工验收',
    }
  })
})
const currentRecordCount = computed(() => loadStatus.value === 'loaded' && !providerFailed.value ? currentRows.value.length : null)
function entityCountLabel(entity) {
  if (entity === selectedEntity.value && loadStatus.value !== 'loaded') return '未知'
  return entityReadStates.value[entity] === 'loaded' ? rowsFor(entity).length : '未读取'
}
const latestTemplateVersion = LATEST_BASE_DATA_TEMPLATE_VERSION
const wave1PrimaryField = computed(() => {
  if (selectedEntity.value === 'engineering-rule-definitions') return 'rule_code'
  if (selectedEntity.value === 'products') return 'product_code'
  if (selectedEntity.value === 'work-center-operation-capabilities') return 'capability_code'
  return 'code'
})
const wave1PrimaryLabel = computed(() => {
  if (selectedEntity.value === 'operations') return '工序编码'
  if (selectedEntity.value === 'standard-capacities') return '产能编码'
  if (selectedEntity.value === 'engineering-rule-definitions') return '规则编码'
  if (selectedEntity.value === 'products') return '产品编码'
  if (selectedEntity.value === 'work-center-operation-capabilities') return '能力编码'
  return '编码'
})
const wave1PrimaryWidth = computed(() => selectedEntity.value === 'engineering-rule-definitions' ? 260 : 220)
const wave1SecondaryColumns = computed(() => currentDefinition.value.columns.filter(column => column.key !== wave1PrimaryField.value))
const wave1RuntimeFilterSchema = Object.freeze([
  { field: 'code', label: '编码', filterType: 'text' },
  { field: 'rule_code', label: '规则编码', filterType: 'text' },
  { field: 'rule_name', label: '规则名称', filterType: 'text' },
  { field: 'version', label: '规则版本', filterType: 'text' },
  { field: 'product_code', label: '产品编码', filterType: 'text' },
  { field: 'name', label: '名称', filterType: 'text' },
  { field: 'product_name', label: '产品名称', filterType: 'text' },
  { field: 'specification', label: '物料规格', filterType: 'text' },
  { field: 'material_type', label: '物料类型', filterType: 'text' },
  { field: 'manufacturing_definition_mode', label: '制造定义形成模式', filterType: 'text' },
  { field: 'status', label: '状态', filterType: 'text' },
  { field: 'operation_id', label: '工序', filterType: 'text' },
  { field: 'operation_name', label: '工序名称', filterType: 'text' },
  { field: 'product_type_code', label: '产品工艺编码', filterType: 'text' },
  { field: 'capacity_business_status_label', label: '产能业务含义', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'work_center_id', label: '工作中心', filterType: 'text' },
  { field: 'product_type_id', label: '产品 / 半成品类型', filterType: 'select', optionsProvider: () => rowsFor('capacity-product-types').map(row => ({ value: row.id, label: rowLabel(row) })) },
  { field: 'uom_id', label: '产能单位', filterType: 'select', optionsProvider: () => rowsFor('units').map(row => ({ value: row.id, label: rowLabel(row) })) },
  { field: 'quantity', label: '每日标准产量', filterType: 'numberRange' },
  { field: 'preparation_days', label: '准备时间（天）', filterType: 'numberRange' },
  { field: 'transfer_days', label: '转运时间（天）', filterType: 'numberRange' },
  { field: 'statusLabel', label: '状态', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'assignment_role', label: '资源角色', filterType: 'select', options: workCenterAssignmentRoleOptions },
  { field: 'capability_code', label: '能力编码', filterType: 'text' },
  { field: 'effective_from', label: '生效日期', filterType: 'date' },
  { field: 'effective_to', label: '失效日期', filterType: 'date' },
  { field: 'is_active', label: '状态', filterType: 'select', options: [
    { value: true, label: '启用' },
    { value: false, label: '停用' },
  ] },
])
const wave1FilterSchema = computed(() => {
  if (selectedEntity.value === 'engineering-rule-definitions') return ENGINEERING_RULE_FILTER_SCHEMA
  const supportedFields = new Set(currentDefinition.value.columns.map(column => column.key))
  return wave1RuntimeFilterSchema.filter(field => supportedFields.has(field.field))
})
const wave1ListContract = computed(() => createPceEnterpriseListContract({
  pageCode: currentIdentity.value.pageKey,
  pageType: 'list',
  title: currentIdentity.value.displayName,
  moduleCode: 'EMD',
}))
const wave1Runtime = usePceEnterpriseListRuntime({
  rows: currentRows,
  filterSchema: wave1RuntimeFilterSchema,
  pageCode: 'wave1-order-production-base-data',
  searchFields: () => currentDefinition.value.columns.map(column => (
    row => displayValue(row[column.key], column)
  )),
  exportFileName: () => `${selectedEntity.value || 'wave1-order-production-base-data'}.csv`,
  exportColumns: () => currentDefinition.value.columns.map(column => ({
    field: column.key,
    label: column.label,
    value: row => displayValue(row[column.key], column),
  })),
})
const {
  selectedRows: wave1SelectedRows, quickSearch: wave1QuickSearch, appliedSearch: wave1AppliedSearch,
  advancedVisible: wave1AdvancedVisible, filters: wave1Filters, tableRef: wave1TableRef,
  activeFilterCount: wave1ActiveFilterCount, sortText: wave1SortText, filteredRows: wave1FilteredRows,
  clearFilters: wave1ClearFilters, clearSort: wave1ClearSort, clearSelection: wave1ClearSelection,
  handleSort: wave1HandleSort, exportCurrent: wave1ExportCurrent,
} = wave1Runtime
const currentRow = computed(() => currentRows.value.find((row) => row.id === editingId.value) || null)
const approvedEffectivityScope = Object.freeze({
  actorUsername: 'admin',
  companyId: 1,
  objectId: 11,
  ruleCode: 'APPROVED_SOURCE_NET',
  version: 'V1',
  status: 'released',
  effectiveFrom: '2026-09-25',
  expectedEffectiveTo: '2030-09-25',
  specificationHash: '8192dcd3224c2c0a34514b44f2bd0fe8480d7140446bf62c4b5cfbc6308c6df6',
  approvalReference: 'PDE-RULE-ID11-EFFECTIVITY-CORRECTION-20260925',
  idempotencyKey: 'pde-rule-id11-effectivity-correction-20260925-once',
})
const isApprovedTechnicalAdmin = computed(() => {
  const user = userStore.userInfo || {}
  const tabIdentity = readTabIdentity() || {}
  const username = user.username || tabIdentity.username
  const companyId = user.company_id ?? tabIdentity.companyId
  const knownRoles = user.access?.roles || []
  return username === approvedEffectivityScope.actorUsername
    && Number(companyId) === approvedEffectivityScope.companyId
    && (!user.username || knownRoles.includes('superadmin'))
})
const isApprovedEffectivityRecord = computed(() => {
  const row = currentRow.value
  return Boolean(row)
    && Number(row.id) === approvedEffectivityScope.objectId
    && Number(row.company_id) === approvedEffectivityScope.companyId
    && row.rule_code === approvedEffectivityScope.ruleCode
    && row.version === approvedEffectivityScope.version
    && row.status === approvedEffectivityScope.status
    && row.effective_from === approvedEffectivityScope.effectiveFrom
    && row.specificationHash === approvedEffectivityScope.specificationHash
})
const showApprovedEffectivityCorrection = computed(() => isApprovedTechnicalAdmin.value && isApprovedEffectivityRecord.value)
const approvedEffectivityCorrectionPending = computed(() => showApprovedEffectivityCorrection.value
  && currentRow.value?.effective_to === approvedEffectivityScope.expectedEffectiveTo)
const approvedEffectivityCorrectionComplete = computed(() => showApprovedEffectivityCorrection.value
  && (currentRow.value?.effective_to === null || currentRow.value?.effective_to === ''))
function canEditRuleRow(row) {
  return canEditEngineeringRule(row, ruleAuthorization.value)
}
function canTransitionRuleRow(row) {
  return canTransitionEngineeringRule(row, ruleAuthorization.value)
}
const canShowMaintenanceForm = computed(() => {
  if(standardRoutingSubentity.value)return false
  if (selectedEntity.value !== 'engineering-rule-definitions') return canMaintain.value
  if (!editingId.value) return canCreateCurrentEntity.value
  return canEditRuleRow(currentRow.value) || canTransitionRuleRow(currentRow.value)
})
const ruleFormFieldsReadOnly = computed(() => selectedEntity.value === 'engineering-rule-definitions'
  && Boolean(editingId.value)
  && !canEditRuleRow(currentRow.value))
const canSaveCurrentForm = computed(() => {
  if (loadStatus.value !== 'loaded' || providerFailed.value) return false
  if (selectedEntity.value === 'operations' && operationReferencesState.value !== 'loaded') return false
  if (selectedEntity.value === 'engineering-source-records') return canMaintain.value && sourceFormatValid.value
  if (selectedEntity.value === 'engineering-rule-definitions' && !isNewCandidateRegistration.value && !structuredDefinitionValid.value) return false
  if (selectedEntity.value !== 'engineering-rule-definitions') return canMaintain.value
  return editingId.value ? canEditRuleRow(currentRow.value) : canCreateCurrentEntity.value
})
const generalFormFields = computed(() => currentDefinition.value.fields.filter(field =>
  !(selectedEntity.value === 'engineering-rule-definitions' && field.key === 'specification')
  && !(selectedEntity.value === 'engineering-source-records' && field.key === 'source_payload')))
const maintenanceFormTitle = computed(() => {
  if (isNewCandidateRegistration.value) return `填写登记资料：${selectedRuleCandidate.value.ruleName}`
  if (!editingId.value) return `新增${currentDefinition.value.shortLabel}`
  if (ruleFormFieldsReadOnly.value) return `${currentDefinition.value.shortLabel}状态维护（定义只读）`
  return `编辑${currentDefinition.value.shortLabel}`
})
const ruleDetailSpecification = computed(() => JSON.stringify(ruleDetailRow.value?.specification ?? {}, null, 2))
const ruleDetailBusinessExplanation = computed(() => ruleDetailRow.value?.businessExplanation || null)
const engineeringRuleKindLabel = kind => ENGINEERING_RULE_KIND_LABELS[kind] || kind || '未提供'
const availableTransitions = computed(() => {
  if (!currentRow.value) return []
  const stateField = selectedEntity.value === 'product-versions' ? 'version_status'
    : selectedEntity.value === 'manufacturing-outputs' ? 'release_status' : 'status'
  return (transitionMap[selectedEntity.value]?.[currentRow.value[stateField]] || [])
    .map(([target, label]) => ({ target, label }))
})
const maintenanceRuleBusinessExplanation = computed(() => selectedRuleCandidate.value?.businessExplanation
  || currentRow.value?.businessExplanation
  || null)
const currentRuleActionLabel = computed(() => availableTransitions.value.map(item => item.label).join('、') || '当前状态没有可执行动作')
const currentRuleActionReason = computed(() => {
  if (!currentRow.value) return ''
  if (currentRow.value.status === 'released') return '当前规则已经发布，无需重复评审或发布；“失效规则”是后续生命周期动作，不是本批两套规则的办理步骤。'
  if (currentRow.value.status === 'reviewed') return '当前规则已评审；只有具备发布权限且确认正式内容无误后，才能执行“发布规则”。'
  if (currentRow.value.status === 'draft') return '当前规则为草稿；维护人员提交的定义保持只读，由具备生命周期权限的人员审阅后执行“提交评审”。'
  return '动作由当前正式状态和服务端权限共同决定。'
})
const candidatePendingFormalCount = computed(() => ruleRegistrationCandidates.value.reduce(
  (total, candidate) => total + (candidate.formalRecords || []).filter(record => ['draft', 'reviewed'].includes(record.status)).length,
  0,
))
const ruleReviewWorkQueueMessage = computed(() => {
  if (!ruleActionAllowed('production.engineering.rule.release')) return ''
  if (candidatePendingFormalCount.value === 0) return '当前暂无待评审／待发布的两套正式规则；需规则维护人员先保存草稿。候选材料本身不是评审对象。'
  return `当前两套目标中有 ${candidatePendingFormalCount.value} 条正式草稿／已评审记录，请按正式状态逐条审阅。`
})

function requireSuccess(response) {
  if (response?.success === false) {
    const error = new Error(response?.error?.message || '正式服务请求失败。')
    error.code = response?.error?.code
    error.factLoadFacts = response?.factLoadFacts
    throw error
  }
  return response?.data ?? response
}

function rowsFor(entity) {
  if (entity === 'operations' && Array.isArray(operationFacts.value)) return operationFacts.value
  return facts.value.facts?.[entity] || []
}

function rowLabel(row) {
  return [row.code, row.employee_no, row.full_name, row.product_code, row.bom_code, row.routing_code, row.source_no,
    row.instance_no, row.calculation_no, row.document_no, row.version_no,
    row.bom_version, row.routing_version, row.document_version, row.name,
    row.product_name, row.source_name, row.rule_name, row.item_name]
    .filter((value) => value !== undefined && value !== null && value !== '')
    .slice(0, 2).join(' · ') || `#${row.id}`
}

function displayValue(value, column) {
  if (column.type === 'boolean') return value === false ? '停用' : '启用'
  if (column.type === 'status') return versionStatusLabels[value] || value || '-'
  if (column.type === 'enum') {
    const option = column.options?.find(item => String(item.value) === String(value))
    return option?.label || (value === null || value === undefined || value === '' ? '-' : value)
  }
  if (column.type?.startsWith('ref:')) {
    const entity = column.type.slice(4)
    const row = rowsFor(entity).find((item) => String(item.id) === String(value))
    return row ? rowLabel(row) : (value ? `#${value}` : '-')
  }
  if (value && typeof value === 'object') return JSON.stringify(value)
  return value === null || value === undefined || value === '' ? '-' : value
}

function selectGroup(key) {
  const targetGroup = groups.find((item) => item.key === key)
  const targetEntity = targetGroup?.entities?.[0]
  if (!targetEntity) throw new Error(`PAGE IDENTITY MISMATCH: no entity for group ${key}`)
  navigateToEntity(targetEntity)
}

function selectEntity(key) {
  navigateToEntity(key)
}

function navigateToEntity(entity) {
  const identity = getFoundationCanonicalModuleByEntity(entity)
  if (!identity) throw new Error(`PAGE IDENTITY MISMATCH: no canonical module for ${entity}`)
  return router.push({ name: identity.routeName })
}

function syncPageState() {
  try {
    const resolved = resolveFoundationPageState(route)
    if (resolved.identity.entityKey !== props.initialEntity) throw new Error(`PAGE IDENTITY MISMATCH: route ${resolved.identity.entityKey} != component prop ${props.initialEntity}`)
    if (!definitions[resolved.identity.entityKey]) throw new Error(`PAGE IDENTITY MISMATCH: no page definition for ${resolved.identity.entityKey}`)
    if (route.meta?.componentKey !== resolved.identity.component) throw new Error(`PAGE IDENTITY MISMATCH: rendered component ${String(route.meta?.componentKey || '')} != ${resolved.identity.component}`)
    if (route.meta?.dataAdapter !== resolved.identity.api) throw new Error(`PAGE IDENTITY MISMATCH: data adapter ${String(route.meta?.dataAdapter || '')} != ${resolved.identity.api}`)
    identityError.value = ''
    pageState.value = resolved
    selectedGroup.value = resolved.identity.groupKey
    selectedEntity.value = resolved.identity.entityKey
    resetForm()
    maintenanceFormOpen.value = false
    formOpenStatus.value = ''
  } catch (error) {
    identityError.value = error?.message || 'PAGE IDENTITY MISMATCH'
    loadStatus.value = 'failed'
  }
}

function setModuleMode(mode) {
  if (!currentIdentity.value.availableModes.includes(mode)) throw new Error(`PAGE IDENTITY MISMATCH: ${pageState.value.moduleId} does not support ${mode}`)
  const view = serializeFoundationMode(mode)
  return router.replace({ name: currentIdentity.value.routeName, query: view ? { view } : {} })
}

watch([() => route.fullPath, () => props.initialEntity], async () => {
  const previousEntity = selectedEntity.value
  syncPageState()
  if(previousEntity!==selectedEntity.value){foundationDetailVisible.value=false;foundationDetailRow.value=null}
  if (!identityError.value && (loadStatus.value === 'idle' || previousEntity !== selectedEntity.value)) {
    await loadFacts()
  }
}, { immediate: true })

function resetForm() {
  clearOperationSourceSchemes()
  formSession.value += 1
  structuredDefinitionValid.value = true
  sourceFormatValid.value = true
  Object.keys(form).forEach((key) => delete form[key])
  currentDefinition.value.fields.forEach((field) => {
    form[field.key] = field.default ?? (field.type === 'boolean' ? false : '')
  })
  form.reason = ''
  if (selectedEntity.value === 'engineering-rule-definitions') form.rule_kind = 'formula'
  editingId.value = null
  selectedRuleCandidateKey.value = ''
  saveError.value = ''
  createIdempotencyKey.value = newCreateIdempotencyKey()
}

function hasUnsavedFormInput() {
  if (operationSchemeDraftKey.value) return true
  if (selectedRuleCandidate.value) return true
  if (form.reason) return true
  return currentDefinition.value.fields.some((field) => {
    const emptyValue = field.default ?? (field.type === 'boolean' ? false : '')
    return form[field.key] !== emptyValue
  })
}

function confirmDiscardUnsaved(messageText) {
  return !hasUnsavedFormInput() || globalThis.confirm(messageText)
}

async function revealMaintenanceForm(statusText) {
  maintenanceFormOpen.value = true
  formOpenStatus.value = statusText
  await nextTick()
  maintenanceFormRef.value?.scrollIntoView?.({ behavior: 'smooth', block: 'start' })
  maintenanceFormRef.value?.querySelector?.('input:not([type="checkbox"]), select, textarea')?.focus?.()
}

async function startNewForm() {
  if (!confirmDiscardUnsaved('当前有未保存资料。确认清空并重新开始吗？')) return
  if (!await ensureOperationReferences()) return
  resetForm()
  await revealMaintenanceForm(`已打开新增${currentDefinition.value.shortLabel}表单；尚未写入服务端。`)
}

function closeMaintenanceForm() {
  if (!confirmDiscardUnsaved('当前有未保存资料。确认关闭表单吗？')) return
  resetForm()
  maintenanceFormOpen.value = false
  formOpenStatus.value = ''
}

function ruleFieldReadOnly(field) {
  if (ruleFormFieldsReadOnly.value) return true
  return isNewCandidateRegistration.value
    && ['rule_code', 'rule_name', 'rule_kind', 'specification'].includes(field.key)
}

function fieldReadOnly(field) {
  if (selectedEntity.value === 'operations' && editingId.value && field.key === 'quantity_driver') return true
  if (selectedEntity.value === 'engineering-source-records' && field.key === 'content_hash') {
    try { if (JSON.parse(form.source_payload || '{}').sourceFormatReference) return true } catch { /* Invalid draft is rejected on save. */ }
  }
  return field.readOnly === true || ruleFieldReadOnly(field)
}

async function prepareRuleCandidate(candidate) {
  const formalRecords = candidate.formalRecords || []
  if (formalRecords.length) {
    const record = formalRecords.find(item => item.status === 'draft') || formalRecords[0]
    const row = rowsFor('engineering-rule-definitions').find(item => String(item.id) === String(record.id))
    if (!row) {
      message.value = '正式记录读取失败，不能按0条处理或重复创建；请刷新服务端事实后重试。'
      return
    }
    if ((record.status === 'draft' && canEditRuleRow(row)) || canTransitionRuleRow(row)) {
      editRow(row)
      message.value = `已打开已有${engineeringRuleStatusLabel(record.status)}记录，不会重复创建。`
    } else {
      await viewEngineeringRule(row)
    }
    return
  }
  if (!confirmDiscardUnsaved('当前有未保存资料。确认切换到所选受治理方案吗？')) return
  resetForm()
  selectedRuleCandidateKey.value = `${candidate.ruleCode}@${candidate.version}`
  form.rule_code = candidate.ruleCode
  form.rule_name = candidate.ruleName
  form.rule_kind = candidate.ruleKind
  form.specification = JSON.stringify(candidate.specification, null, 2)
  message.value = `已带入“${candidate.ruleName}”未保存登记资料；尚未形成正式规则。`
  await revealMaintenanceForm(`已打开${candidate.ruleName}登记表单；尚未写入服务端。`)
}

function clearRuleRegistrationInputs() {
  if ((form.reason || form.effective_from || form.effective_to)
    && !globalThis.confirm('仅清空维护原因和生效／失效日期；系统带入的受治理定义将保留。确认继续吗？')) return
  form.reason = ''
  form.effective_from = ''
  form.effective_to = ''
}

function cancelRuleRegistration() {
  if (!globalThis.confirm('确认取消本次未保存登记吗？不会生成正式规则或改变状态。')) return
  resetForm()
  message.value = '已取消未保存登记；正式规则和候选材料均未改变。'
}

async function editRow(row) {
  if(standardRoutingSubentity.value){await router.push({path:'/foundation/master-data/routings',query:{mode:'maintain'}});return}
  if (pageState.value.mode !== 'maintain') await setModuleMode('maintain')
  if (!await ensureOperationReferences()) return
  resetForm()
  editingId.value = row.id
  currentDefinition.value.fields.forEach((field) => {
    const value = row[field.key]
    form[field.key] = field.type === 'json'
      ? JSON.stringify(value ?? {}, null, 2)
      : (value ?? (field.type === 'boolean' ? false : ''))
  })
  form.reason = ''
  const candidate = ruleRegistrationCandidates.value.find(item => item.ruleCode === row.rule_code
    && item.version === row.version
    && item.specificationHash === row.specificationHash)
  selectedRuleCandidateKey.value = candidate ? `${candidate.ruleCode}@${candidate.version}` : ''
  await revealMaintenanceForm(`已打开${currentDefinition.value.shortLabel} #${row.id} 的正式编辑表单。`)
  if (selectedEntity.value === 'operations') await loadOperationSourceSchemes()
}

function operationSchemeCanonical(value) {
  if (Array.isArray(value)) return `[${value.map(operationSchemeCanonical).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${operationSchemeCanonical(value[key])}`).join(',')}}`
  return JSON.stringify(value)
}

function sameOperationSchemeScope(left, right) {
  return operationSchemeCanonical(left) === operationSchemeCanonical(right)
}

function operationSchemeKey(option) {
  return operationSchemeCanonical([option.scope, option.schemeId, option.schemeHash])
}

function operationSchemeOptionLabel(option) {
  return `${option.label}；${option.quantityBasisLabel}；${option.uomLabel}；${option.productTypeLabel}；${option.routingContextLabel}`
}

function validateOperationSourceSchemes(response, operationId, companyId) {
  const value = requireSuccess(response)
  const configuration = value?.configuration
  const selection = configuration?.sourceSelection
  const positive = number => Number.isSafeInteger(number) && number > 0
  const hash = text => typeof text === 'string' && /^[a-f0-9]{64}$/i.test(text)
  const label = text => typeof text === 'string' && text.trim().length > 0
  const invalid = () => { throw new Error('正式来源方案读取合同或公司、工序范围不一致；当前选择未知，不能按未配置处理。') }
  if (value?.factSource !== 'server' || Number(configuration?.operationId) !== Number(operationId)
    || !positive(value?.catalog?.companyId) || Number(value.catalog.companyId) !== Number(companyId)
    || !Array.isArray(configuration.sourceSchemes) || selection?.contractVersion !== OPERATION_SOURCE_SELECTION_CONTRACT
    || !Number.isSafeInteger(selection.revision) || selection.revision < 0 || !hash(selection.selectionHash)
    || !Array.isArray(selection.selections) || !label(selection.statusLabel)
    || typeof value.catalog.configureAuthorization?.allowed !== 'boolean') invalid()
  const validateOption = option => {
    const scope = option?.scope
    if (!scope || operationSchemeCanonical(Object.keys(scope).sort()) !== operationSchemeCanonical(['companyId', 'operationId', 'productTypeId', 'routingContext'].sort())
      || scope.companyId !== value.catalog.companyId || Number(scope.operationId) !== Number(operationId) || !positive(scope.productTypeId)
      || !/^(RULE|COMPOSITION):[1-9]\d*$/.test(option.schemeId) || !hash(option.schemeHash)
      || !positive(option.uomId) || option.productTypeId !== scope.productTypeId
      || !['label', 'statusLabel', 'quantityBasisLabel', 'uomLabel', 'productTypeLabel', 'routingContextLabel'].every(key => label(option[key]))
      || !sameOperationSchemeScope(option.routingContext, scope.routingContext)
      || !Array.isArray(option.ruleRefs) || option.ruleRefs.length === 0) invalid()
    if (scope.routingContext !== null && (!scope.routingContext
      || operationSchemeCanonical(Object.keys(scope.routingContext).sort()) !== operationSchemeCanonical(['routingId', 'routingVersionId', 'routingStepId'].sort())
      || !Object.values(scope.routingContext).every(positive))) invalid()
    const ruleIds = new Set()
    for (const rule of option.ruleRefs) {
      if (!positive(rule?.ruleId) || ruleIds.has(rule.ruleId) || !hash(rule.specificationHash)
        || !['ruleCode', 'ruleName', 'ruleVersion', 'label'].every(key => label(rule[key]))) invalid()
      ruleIds.add(rule.ruleId)
    }
    if (option.schemeId.startsWith('RULE:')) {
      if (option.compositionRef !== null || option.ruleRefs.length !== 1 || option.schemeId !== `RULE:${option.ruleRefs[0].ruleId}`) invalid()
    } else if (!option.compositionRef || !positive(option.compositionRef.id) || option.schemeId !== `COMPOSITION:${option.compositionRef.id}`
      || !hash(option.compositionRef.specificationHash) || !label(option.compositionRef.ruleCode) || !label(option.compositionRef.ruleVersion)) invalid()
  }
  const keys = new Set(), scopes = new Set()
  for (const option of configuration.sourceSchemes) {
    validateOption(option)
    const key = operationSchemeKey(option)
    if (keys.has(key)) invalid()
    keys.add(key)
  }
  for (const current of selection.selections) {
    validateOption(current)
    const key = operationSchemeCanonical(current.scope)
    if (scopes.has(key)) invalid()
    scopes.add(key)
  }
  return { sourceSchemes: configuration.sourceSchemes, sourceSelection: selection, configureAuthorization: value.catalog.configureAuthorization }
}

function clearOperationSourceSchemes() {
  operationSchemeRequest += 1
  operationSchemeState.value = 'idle'
  operationSchemeError.value = ''
  operationSchemeFacts.value = null
  operationSchemeDraftKey.value = ''
  operationSchemeOwner.value = ''
}

async function loadOperationSourceSchemes() {
  if (selectedEntity.value !== 'operations' || !editingId.value) return null
  const operationId = editingId.value, session = formSession.value, actorScope = readScope()
  const companyId = (readTabIdentity() || {}).companyId
  const request = ++operationSchemeRequest
  const current = () => request === operationSchemeRequest && selectedEntity.value === 'operations'
    && String(editingId.value) === String(operationId) && formSession.value === session && readScope() === actorScope
  operationSchemeState.value = 'loading'
  operationSchemeError.value = ''
  operationSchemeFacts.value = null
  operationSchemeDraftKey.value = ''
  operationSchemeOwner.value = ''
  try {
    const response = await pdeApi.getOperationWorkloadSources({ operationId })
    if (!current()) return null
    const result = validateOperationSourceSchemes(response, operationId, companyId)
    operationSchemeFacts.value = result
    operationSchemeOwner.value = operationSchemeCanonical([actorScope, session, operationId])
    operationSchemeState.value = 'loaded'
    return result
  } catch (error) {
    if (!current()) return null
    operationSchemeState.value = 'read_failed'
    operationSchemeError.value = error?.response?.data?.message || error?.message || '正式来源方案读取失败，当前选择未知。'
    return null
  }
}

function operationSourceSelectionIntent() {
  if (selectedEntity.value !== 'operations' || !editingId.value || !operationSchemeDraftKey.value) return null
  if (operationSchemeState.value !== 'loaded' || !operationSchemeDraft.value || !operationSchemeCanConfigure.value) {
    throw new Error('正式方案或维护权限尚未读取成功，不能提交来源改选。')
  }
  if (operationSchemeOwner.value !== operationSchemeCanonical([readScope(), formSession.value, editingId.value])) {
    throw new Error('当前账号或编辑范围已变化，请重新读取正式来源方案后再改选。')
  }
  if (!operationSchemeChanged.value) return null
  const option = operationSchemeDraft.value
  return { contractVersion: OPERATION_SOURCE_SELECTION_CONTRACT, expectedRevision: operationSchemeFacts.value.sourceSelection.revision,
    scope: JSON.parse(operationSchemeCanonical(option.scope)), schemeId: option.schemeId, schemeHash: option.schemeHash }
}

function verifyOperationSourceSelectionReadback(before, option, after, receipt) {
  const selection = after?.sourceSelection
  if (!selection || selection.revision !== before.revision + 1
    || operationSchemeCanonical(receipt) !== operationSchemeCanonical(selection)) throw new Error('来源方案已提交，但独立读回与正式保存回执不一致；请重新读取确认。')
  const expected = [...before.selections.filter(current => !sameOperationSchemeScope(current.scope, option.scope)), option]
  const ordered = rows => rows.map(operationSchemeCanonical).sort()
  if (operationSchemeCanonical(ordered(selection.selections)) !== operationSchemeCanonical(ordered(expected))) {
    throw new Error('来源方案独立读回未完整保留本次规则组或其他适用范围，不能确认保存完成。')
  }
}

async function viewEngineeringRule(row) {
  ruleDetailVisible.value = true
  ruleDetailStatus.value = 'loading'
  ruleDetailError.value = ''
  ruleDetailRow.value = null
  await nextTick()
  const formalRow = rowsFor('engineering-rule-definitions').find(item => String(item.id) === String(row?.id))
  if (!formalRow) {
    ruleDetailStatus.value = 'failed'
    ruleDetailError.value = '工程规则正式内容读取失败，请关闭后刷新服务端事实再重试。'
    return
  }
  ruleDetailRow.value = formalRow
  ruleDetailStatus.value = 'loaded'
}

function payloadFromForm() {
  const payload = { reason: form.reason }
  currentDefinition.value.fields.forEach((field) => {
    if (field.serverGenerated) return
    let value = form[field.key]
    if (field.type === 'json') {
      value = value ? JSON.parse(value) : {}
    } else if (['ref', 'number'].includes(field.type) && value === '') {
      value = null
    }
    payload[field.key] = value
  })
  if (selectedRuleCandidate.value && !editingId.value) {
    const candidate = selectedRuleCandidate.value
    if (payload.rule_code !== candidate.ruleCode
      || payload.rule_name !== candidate.ruleName
      || payload.rule_kind !== candidate.ruleKind
      || JSON.stringify(payload.specification) !== JSON.stringify(candidate.specification)) {
      throw new Error('受治理方案与未保存登记资料不一致，请取消后重新选择。')
    }
    payload.version = candidate.version
  }
  const sourceIntent = operationSourceSelectionIntent()
  if (sourceIntent) payload.sourceSchemeSelection = sourceIntent
  return selectedEntity.value === 'standard-capacities'
    ? dailyCapacityMaintenancePayload(payload, editingId.value ? currentRow.value : null)
    : payload
}

function loadFacts() {
  if (selectedEntity.value !== 'operations') return loadOtherEntityFacts()
  const scope = readScope()
  const key = `${scope}|operation-page`
  if (pendingOperationLoad?.key === key && pendingOperationLoad.requestId === activeFactLoadRequest) return pendingOperationLoad.promise
  const promise = loadOperationFacts(scope).finally(() => {
    if (pendingOperationLoad?.promise === promise) pendingOperationLoad = null
  })
  pendingOperationLoad = { key, promise, requestId: activeFactLoadRequest }
  return promise
}

function readFoundationEntity(entity, purpose) {
  return reads.run({ purpose, url: `/api/pde/a1-foundation/${entity}/`, params: { entity },
    read: () => pdeApi.productionFoundationA1(entity) })
}
function requireEntityFacts(response, entity) {
  const value = requireSuccess(response)
  if (!value || !Array.isArray(value.facts?.[entity]) || !['loaded', 'empty_valid'].includes(value.factLoadFacts?.factLoadStatus)) {
    throw new Error(`${definitions[entity]?.label || entity}正式读取合同不完整，数量未知。`)
  }
  return value
}
async function loadOperationFacts(scope) {
  if (scope !== readScope() || selectedEntity.value !== 'operations') return false
  if (operationPanelScope.value !== null && operationPanelScope.value !== scope) operationPanelScope.value = null
  const requestId = ++activeFactLoadRequest
  loadStatus.value = 'loading'
  workloadSourceInvalidateKey.value += 1
  currentEntityAuthorization.value = null
  operationFacts.value = null
  targetedFacts.value = { focusRows: [] }
  facts.value = {}
  entityReadStates.value = {}
  operationReferencesState.value = 'idle'
  operationReferencesError.value = ''
  message.value = ''
  const requests = [readFoundationEntity('operations', '工序主数据'), readFoundationEntity('units', '工序单位引用'),
    reads.run({ purpose: '工序正式定向依据', url: '/api/masterdata/group3a-operation-targeted-revalidation/',
      read: () => enterpriseMasterDataApi.group3AOperationTargetedRevalidation() })]
  const owns = () => requestId === activeFactLoadRequest && selectedEntity.value === 'operations' && scope === readScope()
  try {
    const [operationResponse, unitsResponse, targetedResponse] = await Promise.all(requests)
    if (!owns()) return false
    const validationStart = reads.clock()
    const operation = requireEntityFacts(operationResponse, 'operations')
    const units = requireEntityFacts(unitsResponse, 'units')
    if (operation.factLoadFacts.tenantId !== units.factLoadFacts.tenantId) throw new Error('工序与单位的正式公司范围不一致。')
    const targeted = requireSuccess(targetedResponse)
    if (!Array.isArray(targeted?.focusRows)) throw new Error('工序定向依据读取合同不完整，当前事实未知。')
    facts.value = { ...operation, facts: { operations: operation.facts.operations, units: units.facts.units } }
    operationFacts.value = operation.facts.operations
    targetedFacts.value = targeted
    factLoadFacts.value = operation.factLoadFacts
    currentEntityAuthorization.value = operation.currentEntityAuthorization || null
    entityReadStates.value = { operations: 'loaded', units: 'loaded' }
    operationPanelScope.value = scope
    // A retained maintenance draft must reacquire its reference options in this batch.
    if (maintenanceFormOpen.value && !await ensureOperationReferences(scope, true)) throw new Error(operationReferencesError.value)
    if (!owns()) return false
    loadStatus.value = 'loaded'
    workloadSourceRefreshKey.value += 1
    requests.forEach(request => reads.stage(request, 'validationMs', validationStart))
    const commitStart = reads.clock()
    await nextTick()
    if (owns()) requests.forEach(request => reads.stage(request, 'vueCommitMs', commitStart))
    return true
  } catch (error) {
    if (!owns()) return false
    operationFacts.value = null
    targetedFacts.value = { focusRows: [] }
    facts.value = {}
    entityReadStates.value = {}
    loadStatus.value = 'failed'
    currentEntityAuthorization.value = null
    factLoadFacts.value = factLoadFailureFromError(error, '/api/pde/a1-foundation/operations/', factLoadFacts.value)
    message.value = `读取失败，当前数据数量未知：${factLoadFacts.value.errorMessage}`
    return false
  }
}

async function ensureOperationReferences(scope = readScope(), duringRefresh = false) {
  if (selectedEntity.value !== 'operations') return true
  if (scope !== readScope() || (!duringRefresh && loadStatus.value !== 'loaded')) return false
  if (operationReferencesState.value === 'loaded') return true
  operationReferencesState.value = 'loading'
  operationReferencesError.value = ''
  const requestId = activeFactLoadRequest
  const owns = () => scope === readScope() && requestId === activeFactLoadRequest && selectedEntity.value === 'operations'
  try {
    const responses = await Promise.all(['workshops', 'work-centers'].map(entity => readFoundationEntity(entity, `工序维护引用：${entity}`)))
    if (!owns()) return false
    const references = Object.fromEntries(['workshops', 'work-centers'].map((entity, index) => {
      const value = requireEntityFacts(responses[index], entity)
      if (value.factLoadFacts.tenantId !== factLoadFacts.value.tenantId) throw new Error('工序维护引用不属于当前正式公司范围。')
      return [entity, value.facts[entity]]
    }))
    facts.value = { ...facts.value, facts: { ...facts.value.facts, ...references } }
    entityReadStates.value = { ...entityReadStates.value, workshops: 'loaded', 'work-centers': 'loaded' }
    operationReferencesState.value = 'loaded'
    return true
  } catch (error) {
    if (!owns()) return false
    operationReferencesState.value = 'failed'
    operationReferencesError.value = error?.response?.data?.message || error?.message || '工序维护引用读取失败，当前选项未知。'
    saveError.value = operationReferencesError.value
    return false
  }
}

async function loadOtherEntityFacts() {
  const requestId = ++activeFactLoadRequest
  const requestedEntity = selectedEntity.value
  loadStatus.value = 'loading'
  currentEntityAuthorization.value = null
  message.value = ''
  try {
    const isRuleDefinitions = requestedEntity === 'engineering-rule-definitions'
    const scopedRoutingView = isScopedFoundationView(requestedEntity,pageState.value.mode,entitySubview.value)
    const [response, entityResponse, operationResponse, targetedResponse, formatRulesResponse, workbookResponse] = await Promise.all([
      pdeApi.productionFoundationA1(isRuleDefinitions ? selectedEntity.value : scopedRoutingView ? requestedEntity : '', scopedRoutingView ? {readScope:'entity'} : {}),
      isRuleDefinitions || scopedRoutingView ? Promise.resolve(null) : pdeApi.productionFoundationA1(requestedEntity),
      isRuleDefinitions || scopedRoutingView ? Promise.resolve(null) : pdeApi.productionFoundationA1('operations'),
      requestedEntity === 'operations'
        ? enterpriseMasterDataApi.group3AOperationTargetedRevalidation().catch(() => null)
        : Promise.resolve(null),
      requestedEntity === 'engineering-source-records'
        ? pdeApi.productionFoundationA1('engineering-rule-definitions').catch(error => ({ sourceFormatReadError: error?.response?.data?.message || error?.message || '格式规则读取失败' }))
        : Promise.resolve(null),
      requestedEntity === 'engineering-source-records'
        ? pdeApi.calculationBatchCatalog({ action:'workbookSources' }).catch(error => ({ sourceContextReadError:error?.response?.data?.message || error?.message || '工作簿对象范围读取失败' }))
        : Promise.resolve(null),
    ])
    if (requestId !== activeFactLoadRequest || requestedEntity !== selectedEntity.value) return
    const loadedFacts = requireSuccess(response) || {}
    if(scopedRoutingView)assertFoundationRequestIdentity(resolveCurrentIdentity(),loadedFacts.requestIdentity)
    const entityFacts = entityResponse ? (requireSuccess(entityResponse) || {}) : loadedFacts
    facts.value = {
      ...loadedFacts,
      facts: {
        ...(loadedFacts.facts || {}),
        ...(entityFacts.facts || {}),
      },
    }
    entityReadStates.value = Object.fromEntries(Object.keys(facts.value.facts || {}).map(entity => [entity, 'loaded']))
    currentEntityAuthorization.value = entityFacts.currentEntityAuthorization || null
    sourceFormatRules.value = []
    sourceFormatRulesError.value = ''
    if (formatRulesResponse?.sourceFormatReadError) sourceFormatRulesError.value = formatRulesResponse.sourceFormatReadError
    else if (formatRulesResponse) sourceFormatRules.value = requireSuccess(formatRulesResponse)?.facts?.['engineering-rule-definitions'] || []
    sourceWorkbookContexts.value = []; sourceWorkbookContextsError.value = ''
    if (workbookResponse?.sourceContextReadError) sourceWorkbookContextsError.value = workbookResponse.sourceContextReadError
    else if (workbookResponse) {
      try { sourceWorkbookContexts.value = validateWorkbookCatalog(requireSuccess(workbookResponse)).sourceContexts }
      catch (error) { sourceWorkbookContextsError.value = error.message || '工作簿对象范围目录不完整' }
    }
    factLoadFacts.value = facts.value.factLoadFacts || {}
    if (operationResponse) {
      operationFacts.value = requireSuccess(operationResponse)?.facts?.operations || []
    } else {
      operationFacts.value = []
    }
    targetedFacts.value = targetedResponse?.data ?? targetedResponse ?? { focusRows: [] }
    loadStatus.value = 'loaded'
    workloadSourceRefreshKey.value += 1
  } catch (error) {
    if (requestId !== activeFactLoadRequest || requestedEntity !== selectedEntity.value) return
    loadStatus.value = 'failed'
    currentEntityAuthorization.value = null
    factLoadFacts.value = factLoadFailureFromError(
      error,
      currentIdentity.value.api || '/api/pde/a1-foundation/',
      factLoadFacts.value,
    )
    const forbiddenRuleRead = selectedEntity.value === 'engineering-rule-definitions'
      && Number(error?.response?.status || error?.response?.data?.status || 0) === 403
    message.value = forbiddenRuleRead
      ? '当前账号没有“查看工程规则定义”权限。'
      : `${providerStateLabel.value}：${factLoadFacts.value.errorMessage}`
  }
}

onBeforeUnmount(() => { activeFactLoadRequest += 1; clearOperationSourceSchemes(); reads.dispose() })

function applyNativeSourcePreview(result) {
  if (typeof result?.normalization?.rawContentHash === 'string') form.content_hash = result.normalization.rawContentHash
}

async function save() {
  saving.value = true
  message.value = ''
  saveError.value = ''
  try {
    if (!canSaveCurrentForm.value) throw new Error('当前规则状态或账号权限不允许保存定义。')
    const payload = payloadFromForm()
    const sourceBefore = payload.sourceSchemeSelection ? JSON.parse(operationSchemeCanonical(operationSchemeFacts.value.sourceSelection)) : null
    const sourceOption = sourceBefore ? JSON.parse(operationSchemeCanonical(operationSchemeDraft.value)) : null
    payload.idempotencyKey = createIdempotencyKey.value
    const saved = requireSuccess(await pdeApi.saveProductionFoundation(selectedEntity.value, payload, editingId.value))
    if (sourceBefore) {
      const after = await loadOperationSourceSchemes()
      verifyOperationSourceSelectionReadback(sourceBefore, sourceOption, after, saved?.row?.workloadSource?.sourceSelection)
    }
    const generatedCode = selectedEntity.value === 'work-centers' ? saved?.row?.code : ''
    message.value = generatedCode
      ? `${currentDefinition.value.shortLabel}已通过企业基础资料正式服务保存并回读。正式编码：${generatedCode}`
      : `${currentDefinition.value.shortLabel}已通过企业基础资料正式服务保存并回读。`
    await loadFacts()
    resetForm()
    maintenanceFormOpen.value = false
    formOpenStatus.value = ''
  } catch (error) {
    saveError.value = error?.response?.data?.message || error?.message || '正式保存失败。'
    message.value = saveError.value
  } finally {
    saving.value = false
  }
}

async function transitionCurrent(targetStatus) {
  if (!editingId.value) return
  saving.value = true
  message.value = ''
  try {
    requireSuccess(await pdeApi.transitionEngineering(selectedEntity.value, editingId.value, targetStatus, form.reason || '企业基础资料正式生命周期动作'))
    message.value = '工程状态已通过正式生命周期服务推进并写入审计。'
    await loadFacts()
    const row = rowsFor(selectedEntity.value).find((item) => item.id === editingId.value)
    if (row) editRow(row)
  } catch (error) {
    loadStatus.value = 'failed'
    message.value = error?.response?.data?.message || '工程生命周期动作失败。'
  } finally {
    saving.value = false
  }
}

async function correctApprovedRuleEffectivity() {
  const row = currentRow.value
  if (!approvedEffectivityCorrectionPending.value || !row) return
  if (!globalThis.confirm('确认仅将ID11 APPROVED_SOURCE_NET@V1的失效日期从2030-09-25受控纠正为空，并追加独立审计吗？')) return
  correctingEffectivity.value = true
  message.value = ''
  approvedEffectivityReceipt.value = null
  try {
    const response = await pdeApi.correctEngineeringRuleEffectivity(row.id, {
      expectedCompanyId: approvedEffectivityScope.companyId,
      expectedRuleCode: approvedEffectivityScope.ruleCode,
      expectedVersion: approvedEffectivityScope.version,
      expectedStatus: approvedEffectivityScope.status,
      expectedEffectiveFrom: approvedEffectivityScope.effectiveFrom,
      expectedEffectiveTo: approvedEffectivityScope.expectedEffectiveTo,
      expectedSpecificationHash: approvedEffectivityScope.specificationHash,
      expectedUpdatedAt: row.updated_at,
      correctedEffectiveTo: null,
      reason: '依据用户2026-09-25明确批准，将ID11已发布规则失效日期从2030-09-25受控纠正为空（长期有效）；保留规则身份、V1、定义、规范指纹、released状态、生效日期及原历史。',
      approvalReference: approvedEffectivityScope.approvalReference,
      idempotencyKey: approvedEffectivityScope.idempotencyKey,
    })
    approvedEffectivityReceipt.value = requireSuccess(response) || response
    await loadFacts()
    const refreshed = rowsFor('engineering-rule-definitions').find(item => Number(item.id) === approvedEffectivityScope.objectId)
    if (refreshed) editRow(refreshed)
    message.value = `ID11失效日期已通过专用正式服务纠正为空并回读；独立审计 #${approvedEffectivityReceipt.value?.auditId || '已生成'}。`
  } catch (error) {
    message.value = error?.response?.data?.message || error?.message || 'ID11有效期受控纠正失败。'
  } finally {
    correctingEffectivity.value = false
  }
}

</script>

<style scoped>
.production-foundation-maintenance { margin-top:18px; border:1px solid #cbd8eb; border-radius:14px; padding:20px; background:#fff; color:#17233a; }
.production-foundation-maintenance.routing-acceptance-mode{margin-top:0;padding:12px}.routing-acceptance-mode .maintenance-layout{display:block}.routing-acceptance-mode .operation-actions{position:sticky;top:0;z-index:8;margin-bottom:10px;background:#fff;border-color:#b7c9dd;box-shadow:0 4px 12px rgba(23,56,94,.08)}
.maintenance-header,.entity-header,.entity-form header { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; }
.maintenance-header-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.return-action{padding:9px 13px;border:1px solid #3568dc;border-radius:8px;color:#3568dc;background:#fff;text-decoration:none;font-weight:700}
.rule-navigation-context{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 16px;padding:12px 14px;border:1px solid #b9cce6;border-radius:9px;background:#f3f7fc}.rule-navigation-context span{padding:4px 8px;border-radius:999px;background:#fff}.rule-navigation-context small{flex-basis:100%;color:#52637a}
.operation-actions{display:flex;flex-wrap:wrap;gap:9px;margin:0 0 14px;padding:11px;border:1px solid #dbe3ef;border-radius:10px;background:#f7f9fc}.operation-actions button{background:#fff;color:#2457ba;border-color:#b9c8e3}.operation-actions button.active{background:#315bcf;color:#fff;border-color:#315bcf}.operation-actions .acceptance-action{margin-left:auto;border-color:#17676c;color:#17676c;font-weight:700}.operation-actions .acceptance-action.active{background:#17676c;color:#fff}
.authorization-blocker,.form-blocker{margin:0 0 14px;padding:12px 14px;border:1px solid #e0a09a;border-radius:9px;background:#fff2f0;color:#922b21;font-weight:700}.maintenance-ready-notice,.form-open-status{margin:12px 0;padding:10px 12px;border:1px solid #9dbce6;border-radius:8px;background:#f1f7ff;color:#274d7b}.entity-form{scroll-margin-top:18px}
.rule-registration-materials{margin:0 0 16px;padding:14px;border:1px solid #d7b468;border-radius:10px;background:#fffaf0}.rule-registration-materials>header,.rule-registration-materials article>div{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.rule-registration-materials article{margin-top:10px;padding:12px;border:1px solid #ead8ad;border-radius:8px;background:#fff}.rule-registration-materials article>div>span{display:flex;flex-direction:column;gap:3px}.rule-registration-materials article>b{display:inline-block;margin:8px 0;color:#9a5b00}.rule-registration-materials dl,.rule-registration-preview dl,.rule-state-guidance dl,.rule-technical-trace dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:4px 0 8px}.rule-registration-materials dl div,.rule-registration-preview dl div,.rule-state-guidance dl div,.rule-technical-trace dl div{min-width:0}.rule-registration-materials dt,.rule-registration-preview dt,.rule-state-guidance dt,.rule-technical-trace dt{font-size:12px;color:#65748a}.rule-registration-materials dd,.rule-registration-preview dd,.rule-state-guidance dd,.rule-technical-trace dd{margin:2px 0;overflow-wrap:anywhere}.rule-registration-materials small{color:#52637a}.candidate-action{white-space:nowrap}.rule-work-queue{margin-top:12px;padding:10px;border:1px solid #d7b468;border-radius:8px;background:#fff;color:#7a4b00;font-weight:700}
.rule-registration-preview,.rule-state-guidance,.rule-business-explanation{margin:12px 0;padding:13px;border:1px solid #b8cbea;border-radius:9px;background:#f5f9ff}.rule-registration-preview>strong{color:#8a5300}.rule-state-guidance .rule-readonly-notice{margin-top:10px;padding:9px;border:1px solid #d7b468;border-radius:7px;background:#fffaf0;color:#7a4b00}.rule-business-explanation h5,.rule-business-explanation h6{margin:8px 0}.rule-business-explanation ul{margin:5px 0 10px;padding-left:22px}.rule-business-explanation li{margin:4px 0}.rule-business-explanation li small{display:block;color:#66758a}.rule-business-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.rule-business-columns article{padding:9px;border:1px solid #dce4ef;border-radius:8px;background:#fff}.rule-technical-trace{margin:12px 0;padding:10px;border:1px solid #dce4ef;border-radius:8px;background:#fff}.rule-technical-trace summary{cursor:pointer;color:#35557c;font-weight:700}.rule-technical-trace textarea{margin-top:10px;min-height:220px;font-family:ui-monospace,SFMono-Regular,Consolas,monospace}.rule-technical-trace pre{max-height:360px;overflow:auto;white-space:pre-wrap}
.rule-effectivity-correction{margin:12px 0;padding:13px;border:1px solid #d7b468;border-radius:9px;background:#fffaf0}.rule-effectivity-correction dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:10px 0}.rule-effectivity-correction dl div{padding:8px;border:1px solid #ead8ad;border-radius:7px;background:#fff}.rule-effectivity-correction dt{font-size:12px;color:#65748a}.rule-effectivity-correction dd{margin:3px 0 0;overflow-wrap:anywhere}.correction-action{background:#8a5300;border-color:#8a5300}.correction-complete{padding:9px;border:1px solid #92c7a5;border-radius:7px;background:#edf8f1;color:#206b42;font-weight:700}.correction-blocked{color:#9f241d;font-weight:700}
.engineering-rule-detail .rule-readonly-notice{padding:10px 12px;border:1px solid #d7b468;border-radius:8px;background:#fffaf0;color:#7a4b00;font-weight:700}.engineering-rule-detail dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:0 0 14px}.engineering-rule-detail dl div{padding:9px;border:1px solid #dce4ef;border-radius:8px;min-width:0}.engineering-rule-detail dt{font-size:12px;color:#65748a}.engineering-rule-detail dd{margin:3px 0 0;overflow-wrap:anywhere}.engineering-rule-detail pre{max-height:360px;overflow:auto;padding:12px;border:1px solid #dce4ef;border-radius:8px;background:#f7f9fc;white-space:pre-wrap;overflow-wrap:anywhere;color:#26364d}
.eyebrow { margin:0; color:#3568dc; font-weight:700; }
h2,h3,h4 { margin:5px 0; }
p { margin:4px 0; color:#58677d; }
button { border:1px solid #3568dc; border-radius:8px; padding:9px 13px; background:#3568dc; color:#fff; cursor:pointer; }
button.secondary,.link { background:#fff; color:#3568dc; }
button:disabled { opacity:.55; cursor:not-allowed; }
.fact-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:16px 0; }
.fact-strip article { padding:12px; background:#f4f7fc; border-radius:9px; }
.fact-strip small,.fact-strip strong { display:block; }
.fact-strip strong { margin-top:5px; overflow-wrap:anywhere; }
.group-tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
.group-tabs button:not(.active) { background:#eef3fb; color:#28496f; border-color:#d6e0ed; }
.maintenance-layout { display:grid; grid-template-columns:220px minmax(0,1fr); gap:16px; }
.entity-nav { display:flex; flex-direction:column; gap:7px; }
.entity-nav button { display:flex; justify-content:space-between; gap:8px; text-align:left; background:#f4f7fc; color:#273b57; border-color:#dce4ef; }
.entity-nav button.active { background:#3568dc; color:#fff; }
.entity-workspace { min-width:0; }
.table-wrap { overflow:auto; border:1px solid #dce4ef; border-radius:10px; margin:12px 0; max-height:360px; }
table { width:100%; border-collapse:collapse; min-width:720px; }
th,td { padding:9px 10px; border-bottom:1px solid #e6ebf2; text-align:left; white-space:nowrap; }
th { background:#f5f8fc; position:sticky; top:0; z-index:1; }
.empty { text-align:center; color:#718096; }
.entity-form { border:1px solid #dce4ef; border-radius:10px; padding:15px; background:#fafcff; }
.entity-form header span { color:#5c6d82; font-size:13px; }
.form-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:12px; }
.operation-source-scheme-field{grid-column:1/-1;min-width:0;padding:12px;border:1px solid #b8cbea;border-radius:8px;background:#f5f9ff}.source-scheme-current{margin:8px 0;padding-left:22px}.source-scheme-current li{margin:6px 0;overflow-wrap:anywhere}.source-scheme-current span{display:block;font-weight:400}.source-scheme-draft,.source-scheme-history{display:block;margin-top:10px;padding-top:10px;border-top:1px solid #dce4ef}.source-scheme-error{color:#9f241d}.source-scheme-history input{background:#f3f5f8}
label span,label small { display:block; }
label span { margin-bottom:5px; color:#34445b; font-weight:600; }
label b { color:#c23a31; }
label small { margin-top:4px; color:#6b7889; }
input:not([type='checkbox']),select,textarea { width:100%; box-sizing:border-box; border:1px solid #cbd5e1; border-radius:7px; padding:8px; background:#fff; }
textarea { min-height:72px; resize:vertical; }
.reason-field { display:block; margin-top:12px; }
.form-actions { display:flex; flex-wrap:wrap; gap:9px; margin-top:12px; }
.message { margin-top:12px; padding:10px; background:#edf8f1; border-radius:8px; color:#206b42; }
.message.error { background:#fff0ef; color:#a8322a; }
.provider-error{padding:12px 14px;border:1px solid #e5a5a0;border-radius:9px;background:#fff2f0;color:#9f241d;font-weight:700}
.identity-error{border:2px solid #b42318;border-radius:10px;padding:18px;background:#fff2f0;color:#8f1d16}.identity-error h2,.identity-error p{color:inherit}
@media (max-width:1100px) { .maintenance-layout { grid-template-columns:1fr; } .entity-nav { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); } .form-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:700px) { .fact-strip,.form-grid,.entity-nav { grid-template-columns:1fr; } }
@media (max-width:700px) { .operation-actions .acceptance-action{margin-left:0} }
@media (max-width:700px) { .rule-registration-materials dl,.rule-registration-preview dl,.rule-state-guidance dl,.rule-technical-trace dl,.rule-business-columns{grid-template-columns:1fr} }
@media (max-width:700px) { .engineering-rule-detail dl{grid-template-columns:1fr} }
</style>
