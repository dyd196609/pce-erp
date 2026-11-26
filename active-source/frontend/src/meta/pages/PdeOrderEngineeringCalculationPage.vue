<template>
  <main class="calculation-page" data-page-code="pde-order-engineering-calculation" data-business-object="EngineeringCalculationRecord" data-fact-source="server" :data-access-mode="accessMode" :data-active-business-page="activeBusinessPage" :data-business-write-count="writeCount" :data-engineering-option-source="engineeringInputOptions.source || 'not-loaded'" :data-engineering-category-count="engineeringInputOptions.productCategories?.length || 0" :data-production-plan-status="productionPlan.statusLabel" :data-source-record-id="selectedOrder?.sourceRecordId || ''" :data-work-order-scope="selectedOrder?.isSourceTrial ? 'whole-order-source' : selectedOrder ? 'sales-order-line' : 'none'" :data-work-order-count="workOrderRows.length" :data-source-result-count="sourceCalculationRows.length">
    <nav class="breadcrumb" aria-label="面包屑"><router-link to="/process-center?module=PDE">PDE业务流程</router-link><span>›</span><router-link to="/pde/engineering-calculations">工程核算 / 物料核算</router-link><span>›</span><strong>{{ activePageDefinition.label }}</strong></nav>
    <header class="workspace-header">
      <div><div class="eyebrow"><span :class="['environment-chip', ruleOnlyEntryMode || readiness.runtimeEnvironment?.nonProduction ? 'safe' : 'error']">{{ ruleOnlyEntryMode ? '规则权限隔离入口' : (readiness.runtimeEnvironment?.nonProduction ? '非生产验收' : '环境待确认') }}</span><span>{{ loading ? '读取中' : overallLabel }}</span></div><h1>{{ ruleOnlyEntryMode ? '工程规则入口' : activePageDefinition.label }}</h1><p>{{ ruleOnlyEntryMode ? '仅提供当前公司工程规则定义入口；不会读取或展示订单、来源、设计对象、基线、实例或核算结果。' : activePageDefinition.description }}</p></div>
      <dl v-if="calculationAccessAllowed"><div><dt>订单</dt><dd>{{ selectedOrder?.orderNo || '未选择' }}</dd></div><div><dt>客户／项目</dt><dd>{{ savedRecordSelected ? '客户／项目未冻结；当前关系另行查看' : selectedOrder?.customerName || selectedOrder?.sourceCaseName || selectedOrder?.installationArea || '未提供' }}</dd></div><div><dt>工程版本</dt><dd>{{ displayedSourceVersion }}</dd></div><div><dt>业务状态</dt><dd>{{ currentBusinessStatus }}</dd></div></dl>
    </header>
    <section v-if="accessMode === 'loading'" class="notice pending" data-state="permission-loading"><strong>正在核对当前账号的规则与核算查看权限…</strong></section>
    <section v-else-if="ruleOnlyEntryMode" class="rule-entry-card" data-section="engineering-rule-entry" data-navigation-scope="rules-entry">
      <header><div><h2>工程规则</h2><p>当前账号具备工程规则查看权限，但不具备工程核算查看权限。本区域与核算数据完全隔离。</p></div><span class="pill">当前公司共用规则</span></header>
      <dl class="rule-entry-facts"><div><dt>当前公司</dt><dd>{{ permissionProfile?.organization?.name || '当前登录公司' }}（{{ permissionProfile?.organization?.code || `组织#${permissionProfile?.organization?.id || '待核实'}` }}）</dd></div><div><dt>查看范围</dt><dd>当前公司共用工程规则</dd></div><div><dt>所需权限</dt><dd>查看工程规则定义</dd></div><div><dt>核算数据</dt><dd>未请求、未展示</dd></div></dl>
      <div class="actions"><el-button type="primary" class="formal-card-action" @click="router.push(ruleDefinitionsLocation)">打开工程规则定义</el-button><router-link to="/process-center?module=PDE">返回PDE业务流程</router-link></div>
    </section>
    <section v-else-if="accessMode === 'denied'" class="notice error" data-state="permission_denied"><strong>当前账号无权进入工程核算或工程规则</strong><p>服务端统一权限资料未授予“查看工程核算”或“查看工程规则定义”。页面没有请求受限业务事实。</p><router-link to="/process-center?module=PDE">返回PDE业务流程</router-link></section>
    <section v-else-if="accessMode === 'failed'" class="notice error" data-state="initial-read-failed"><strong>工程来源读取失败，当前数据数量未知</strong><p>{{ loadError }}</p><details v-if="initialReadFailure"><summary>查看读取诊断</summary><p>请求地址：{{ initialReadFailure.apiUrl }}；HTTP结果：{{ initialReadFailure.httpStatus || '未收到响应' }}；错误码：{{ initialReadFailure.errorCode }}</p><p>{{ initialReadFailure.errorMessage }}</p></details><button type="button" @click="refresh">重试读取</button><router-link to="/process-center?module=PDE">返回PDE业务流程</router-link></section>
    <nav v-if="calculationAccessAllowed && !configurationSubview" class="business-page-tabs" aria-label="整单工程核算四页">
      <span v-for="page in businessPages" :key="page.key" class="business-page-tab">
        <button type="button" :class="{ active: activeBusinessPage === page.key }" :aria-current="activeBusinessPage === page.key ? 'page' : undefined" @click="switchBusinessPage(page.key)">{{ page.label }}</button>
        <router-link :to="businessPageLocation(page.key)" target="_blank" rel="noopener" class="new-tab-action" :aria-label="`${page.label}新标签打开`">新标签打开</router-link>
      </span>
    </nav>
    <details v-if="calculationAccessAllowed" class="environment-details" data-section="runtime-environment"><summary>环境与相关页面</summary><div class="detail-grid"><span><b>环境：</b>{{ readiness.runtimeEnvironment?.label || '运行环境待服务端声明' }}</span><span><b>数据库：</b>{{ readiness.runtimeEnvironment?.databaseIdentity || '未声明' }}</span><span><b>运行代码：</b>{{ readiness.runtimeEnvironment?.codeIdentity || 'working-tree' }}</span><span><b>验收身份：</b>{{ readiness.runtimeEnvironment?.acceptanceIdentity || '未声明' }}</span></div><nav class="related-navigation"><router-link v-for="subview in calculationIdentity.subviews" :key="subview.key" :to="foundationSubviewLocation(calculationIdentity.moduleId, subview.key)">{{ subview.label }}</router-link><router-link to="/pde/product-boms">BOM管理</router-link></nav></details>
    <section v-if="permissionAllowed(CALCULATION_VIEW_PERMISSION) && !configurationSubview && !savedRecordSelected" class="order-context-strip workbook-source-context" data-section="workbook-source-selection" aria-label="选择工作簿来源版本">
      <label>工作簿来源版本<select v-model="selectedWorkbookSourceRecordId" :disabled="loading || formalBusy || busy" @change="selectWorkbookSource"><option value="">历史登记来源（只读）</option><option v-if="selectedWorkbookSourceRecordId && !selectedWorkbookSource" :value="selectedWorkbookSourceRecordId">原选来源不在当前可用目录内，请重新选择</option><option v-for="source in workbookSources" :key="source.id" :value="String(source.id)">{{ source.label || `${source.sourceNo} · ${source.sourceVersion} · ${source.statusLabel}` }}</option></select></label>
      <span v-if="workbookSourcesLoading">正在读取当前公司来源版本…</span><span v-else-if="selectedWorkbookSource">{{ selectedWorkbookSource.statusLabel }} · SHA-256：{{ selectedWorkbookSource.contentHash }}</span><span v-else-if="!selectedWorkbookSourceRecordId">保留历史固定引用；新执行须明确选择正式来源版本。</span>
      <span v-if="selectedWorkbookSourceRecordId && workbookSourceIntake.sourceIntakeStatusLabel">{{ workbookSourceIntake.sourceIntakeStatusLabel }}</span>
      <p v-if="workbookSourcesError" class="error-text" role="alert">{{ workbookSourcesError }}</p>
      <router-link to="/foundation/master-data/engineering-source-records" target="_blank" rel="noopener">打开工程来源记录</router-link>
    </section>
    <section v-if="calculationAccessAllowed && !configurationSubview" class="order-context-strip" data-section="shared-order-context" aria-label="选择订单工程上下文">
      <label>订单／来源范围<select v-model.number="selection.salesOrderItemId" @change="selectOrder"><option :value="null">请选择订单或工程来源</option><option v-for="row in orders" :key="row.salesOrderItemId" :value="row.salesOrderItemId">{{ row.isSourceTrial ? `${row.orderNo} · ${row.sourceOrderNo || '来源待核对'} · 整单${row.draft?.rows?.length || 0}行` : `${row.orderNo}/${row.lineNo} · ${row.materialCode}` }}</option></select></label>
      <span><b>订单：</b>{{ selectedOrder?.orderNo || '未选择' }}</span><span><b>工程来源：</b>{{ savedRecordSelected ? savedContext?.sourceNo || '冻结来源待读取' : selectedOrder?.sourceOrderNo || selectedOrder?.sourceNo || '未选择' }}</span><span><b>当前范围：</b>{{ currentScopeLabel }}</span><span><b>工程版本：</b>{{ displayedSourceVersion }}</span><span><b>关联设计：</b>{{ selectedOrder?.linkedDesignItemCount ?? selectedOrder?.designItemCount ?? 0 }}项</span><span><b>状态：</b>{{ currentBusinessStatus }}</span>
      <div class="context-actions"><button type="button" class="secondary" @click="refresh">刷新</button><details><summary>更多</summary><button type="button" class="link" @click="copyDiagnostics">复制诊断数据</button><router-link to="/process-center?module=PDE">返回业务流程中心</router-link></details></div>
    </section>
    <section v-if="calculationAccessAllowed && versionStale && !savedRecordSelected" class="stale-notice" data-state="version-stale"><strong>工程版本已有更新</strong><span>本页仍保留 {{ requestedEngineeringVersion }}，订单当前工程版本为 {{ latestEngineeringVersion }}。请先保存当前编辑，再刷新或重新核算；系统不会自动覆盖本页内容。</span></section>
    <section v-if="savedRecordSelected" class="card" data-section="saved-record-context" aria-label="所选核算冻结上下文">
      <h2>所选核算冻结资料</h2>
      <p v-if="savedContext">{{ savedContext.orderNo }} · 订单行ID {{ savedContext.salesOrderItemId }} · {{ savedContext.calculationNo }} · 核算修订R{{ savedContext.calculationRevision }} · 基线 {{ savedContext.baselineNo }} · 来源 {{ savedContext.sourceNo }}／{{ savedContext.sourceVersion }}</p>
      <p v-if="savedContext">各区读取同一记录的冻结输入、精确设计修订及已保存结果；切换记录后重新读取。核算修订是核算记录版次，设计修订是设计内容版次。</p>
      <p v-if="savedNativeContext">工作表／行号／单元格：不适用／原生设计来源。门洞输入、门套与门扇计算尺寸、实际厚度和门套深度分别列示。</p>
      <p v-if="savedContext">资料性质按冻结来源保留；开发测试假设不代表现实设计完成或制造批准。</p>
      <p v-else class="notice pending">{{ calculationDetailLoading ? '正在读取冻结资料，各区暂不展示候选替代值。' : activeCalculation?.savedPageContext?.statusLabel || calculationDetailError || '历史记录未冻结完整页面资料；仅查看其原始核算输入与结果，不使用当前设计补齐。' }}</p>
    </section>
    <SemiFinishedConfigurationPreview v-if="calculationAccessAllowed && configurationSubview" :preview="readiness.semiFinishedConfiguration || null" :loading="loading" :error="loadError" />
    <template v-else-if="calculationAccessAllowed">
      <section v-if="loadError" class="notice error" data-state="read_failed"><strong>读取失败，当前数据数量未知</strong><p>{{ loadError }}</p><button type="button" @click="refresh">重试</button></section>
      <section v-else-if="loading" class="notice pending" data-state="loading"><strong>正在读取工程核算服务端事实…</strong></section>
      <section v-if="auxiliaryReadNotice && !loadError" class="notice pending" data-state="permission_denied"><strong>页面已打开；部分受限数据未加载</strong><p>{{ auxiliaryReadNotice }}</p></section>
      <section v-else-if="!loading && !loadError && !orders.length" class="notice empty" data-state="empty"><strong>没有可显示的订单行</strong><p>服务端读取成功，当前组织尚无订单工程核算候选。</p></section>
      <div v-show="!loading && !loadError" data-state="fact-read-succeeded">
      <section v-show="activeBusinessPage === 'input'" class="card" data-section="order-selection">
        <header><div><h2>工程数据录入</h2><p>{{ savedRecordSelected ? '查看所选核算的冻结输入与已保存结果；当前候选及只读准入另区说明，不覆盖本记录。' : '从产品设计管理读取当前候选事实，校验与保存分别办理；不维护第二套设计资料。' }}</p></div><span class="pill">{{ selectedOrder?.currentDesignInputs?.length || 0 }} 项当前设计</span></header>
        <div class="form-grid">
          <label>销售订单 / 工程来源范围<select v-model.number="selection.salesOrderItemId" @change="selectOrder"><option :value="null">请选择订单或工程来源</option><option v-for="row in orders" :key="row.salesOrderItemId" :value="row.salesOrderItemId">{{ row.isSourceTrial ? `${row.orderNo} · ${row.sourceOrderNo || '来源待核对'} · 整单${row.draft?.rows?.length || 0}行` : `${row.orderNo}/${row.lineNo} · ${row.materialCode} · ${row.orderQuantity} ${row.orderUomCode || '单位待维护'} · ${calculationStatusLabel({ status: row.status, statusLabel: row.statusLabel })}` }}</option></select></label>
          <label>订单工程实例<input :value="orderEngineeringInstanceScopeLabel" readonly></label>
          <label>工程来源 / 版本<input :value="savedRecordSelected ? `${savedContext?.sourceNo || '待读取'} / ${displayedSourceVersion}` : selectedOrder ? `${selectedOrder.sourceNo || '未绑定'} / ${selectedOrder.sourceVersion || '-'}` : ''" readonly></label>
          <label>产品 / 版本<input :value="savedRecordSelected ? `冻结分类ID ${savedContext?.rows?.[0]?.productCategoryId ?? '未提供'} / 设计修订见冻结输入` : selectedOrder ? `${selectedOrder.productId || selectedOrder.productCategoryId || '-'} / ${selectedOrder.productVersionId || '-'}` : ''" readonly></label>
        </div>
        <section id="formal-engineering-continuation" v-if="selectedOrder && formalContinuation.lines?.length" class="formal-continuation" data-section="formal-engineering-continuation">
          <header><div><h3>正式接续办理（当前候选及准入）</h3><p>本区读取当前候选及权限；与所选已保存核算的冻结资料分开，预检不代表重新保存或制造放行。</p><p v-if="selectedOrder.isSourceTrial">正式订单存在、来源关联、来源确认、订单工程实例和已保存核算是彼此独立的状态；本区复用原正式接续服务端事实。</p><p v-else>当前订单 {{ selectedOrder.orderNo }} · 第{{ selectedOrder.lineNo }}行 · 实例 {{ formalContinuationLine?.orderEngineeringInstanceNo || '未建立' }}；查看不会创建、确认或保存任何业务记录。</p></div><div class="formal-header-actions"><span class="pill">{{ formalContinuationObjectCount }} 个稳定对象</span><button v-if="!selectedOrder.isSourceTrial && formalSummaryReturnTarget" type="button" class="secondary formal-summary-return" data-action="return-formal-order-summary" @click="returnToFormalSummary">返回整单汇总<small v-if="formalSummaryReturnTarget.lineCount">返回后查看本订单{{ formalSummaryReturnTarget.lineCount }}行</small></button></div></header>
          <template v-if="selectedOrder.isSourceTrial">
            <div class="notice pending formal-context-notice" data-state="read-only-formal-context">
              <strong>{{ sourceOrderAssociation.title }}</strong>
              <p>{{ sourceOrderAssociation.detail }}</p>
            </div>
            <div class="formal-continuation-grid">
              <div><b>当前正式订单</b><span>{{ selectedOrder.orderNo }} · 已存在</span><small>{{ formalContinuation.lines.length }} 个订单行，{{ formalContinuationObjectCount }} 个设计对象稳定归属</small></div>
              <div><b>工程来源</b><span>{{ formalContinuation.lines[0]?.sourceStatusLabel || '待读取' }}</span><small>对象归属订单不等于来源记录已确认。</small></div>
              <div><b>订单工程实例</b><span>{{ formalContinuationInstanceCount ? `${formalContinuationInstanceCount} 个已建立` : '0 个 · 未形成' }}</span><small>不以正式订单存在替代实例状态。</small></div>
              <div><b>整单工程基线</b><span>{{ confirmedBaselineSummary }}</span><small>仅回读既有基线，不创建、不确认、不改绑。</small></div>
              <div><b>正式规则包</b><span>{{ formalContinuation.formalRulePackages?.length || 0 }}/{{ formalContinuation.requiredRulePackages?.length || 2 }} 已发布</span><small>{{ (formalContinuation.requiredRulePackages || []).join('、') }}</small><el-button type="primary" class="formal-card-action" @click="router.push(ruleDefinitionsLocation)">打开工程规则定义</el-button></div>
              <div><b>正式核算保存</b><span>{{ formalOrderSavedState.label }}</span><small>来源预览和预计位置不冒充正式持久化记录。</small></div>
            </div>
            <div class="table-wrap formal-lines-table" data-section="formal-order-summary-lines"><table><thead><tr><th>订单行</th><th>设计对象</th><th>来源状态</th><th>订单工程实例</th><th>完整办理条件校验</th><th>预计结果位置</th><th>正式保存</th><th class="formal-line-action">只读查看</th></tr></thead><tbody><tr v-for="row in formalSummaryLines" :key="row.salesOrderItemId"><th>第{{ row.lineNo }}行<small>订单行ID {{ row.salesOrderItemId }}</small></th><td>{{ row.designObjectCount }} 项</td><td>{{ row.sourceStatusLabel }}</td><td>{{ row.orderEngineeringInstanceNo || '未形成' }} · {{ row.instanceStatusLabel }}<small v-if="row.lifecycleStateFacts">{{ row.lifecycleStateFacts.statusLabel }} · {{ row.lifecycleStateFacts.statusTransitionCount }}条转换记录</small></td><td><span :class="row.fullValidation?.status === 'passed' ? 'pass-text' : row.fullValidation?.status === 'read_failed' ? 'error-text' : ''">{{ row.fullValidation?.statusLabel || '尚未取得完整校验结果' }}</span><small v-if="row.fullValidation?.checkedAt">服务端只读校验：{{ formatTime(row.fullValidation.checkedAt) }}</small><small v-if="row.fullValidation?.blockers?.length">{{ row.fullValidation.blockers.map(item => item.reason).join('；') }}</small></td><td>{{ row.fullValidation?.resultPositionCount ?? '未形成' }}<small>预计可追溯位置，不代表已保存数值</small></td><td>{{ formalSavedState(row.formalCalculationState, conditionPreflightOperation.state === 'failed').label }}<small v-for="record in row.formalCalculationState?.records || []" :key="record.id">{{ record.calculationNo }} · {{ record.statusLabel }}</small></td><td class="formal-line-action"><button type="button" class="secondary line-detail-action" data-action="view-formal-order-line" @click="openFormalLine(row)">查看本行办理详情</button><small>只读，不执行保存</small></td></tr></tbody><tfoot><tr><th>整单合计</th><td>{{ formalContinuationObjectCount }} 项</td><td colspan="3">{{ formalValidationSummary }}</td><td>{{ formalValidationResultPositionTotal }} 个位置</td><td>{{ formalOrderSavedState.label }}</td><td class="formal-line-action">只读汇总</td></tr></tfoot></table></div>
            <div v-if="conditionPreflightOperation.state === 'failed'" class="notice error"><strong>{{ conditionPreflightOperation.title }}</strong><p>{{ conditionPreflightOperation.message }} 当前结果未知，未伪装成无阻断或0项。</p></div>
            <div v-else-if="formalContinuationBlockers.length" class="notice error"><strong>正式办理仍有阻断</strong><ul><li v-for="row in formalContinuationBlockers" :key="row.code">{{ row.code }}：{{ row.reason }}</li></ul></div>
            <p v-else class="notice success">当前正式办理前置事实一致；基线与正式规则可用于逐实例完整校验。{{ formalOrderSavedState.label }}；完整校验与正式保存分别判断。</p>
            <p class="boundary-note">当前来源上下文不显示形成实例、确认来源或执行保存按钮；下方只读条件预检可说明阻断，但不会代替订单行级完整校验。</p>
          </template>
          <template v-else>
          <div class="formal-continuation-grid">
            <div><b>实例范围</b><span>{{ selectedOrder.orderNo }}/{{ selectedOrder.lineNo }} · {{ formalContinuationLine?.designObjectCount || selectedOrder.designItemCount || 0 }} 项</span><small>{{ formalContinuationLine?.designItemNos?.join('、') || '对象身份由服务端读取' }}</small></div>
            <div><b>工程来源</b><span>{{ formalContinuationLine?.sourceStatusLabel || '待读取' }}</span><router-link :to="formalContinuation.sourceMaintenancePath || '/foundation/master-data/engineering-source-records'" target="_blank" rel="noopener">打开工程来源记录</router-link></div>
            <div><b>订单工程实例</b><span>{{ formalContinuationLine?.orderEngineeringInstanceNo || '未建立' }} · {{ formalContinuationLine?.instanceStatusLabel || '未建立' }}</span><small>{{ formalContinuationLine?.writeImpact || '服务端将按订单行唯一判断' }}</small></div>
            <div><b>正式核算保存</b><span>{{ formalSelectedSavedState.label }}</span><small v-for="record in formalSelectedSavedState.records || []" :key="record.id">{{ record.calculationNo }} · {{ record.statusLabel }} · {{ record.baselineNo || '基线未提供' }}</small></div>
            <label><b>整单工程基线</b><select v-model.number="selectedBaselineId"><option :value="null">请选择已确认基线</option><option v-for="row in formalBaselines" :key="row.id" :value="row.id">{{ row.baselineNo }} · {{ row.statusLabel }} · {{ row.itemCount }}项</option></select><small>执行时服务端重验公司、订单、状态、候选哈希、快照哈希和本实例对象子集。</small></label>
            <div><b>正式规则包</b><span>{{ formalContinuation.formalRulePackages?.length || 0 }}/{{ formalContinuation.requiredRulePackages?.length || 2 }} 已发布</span><small>{{ (formalContinuation.requiredRulePackages || []).join('、') || 'APPROVED_SOURCE_NET@V1、SOURCE_LINEAR_CONTINUATION@V1' }}</small><el-button type="primary" class="formal-card-action" @click="router.push(ruleDefinitionsLocation)">打开工程规则定义</el-button></div>
          </div>
          <div class="actions formal-actions">
            <button v-if="!formalContinuationLine?.orderEngineeringInstanceId" type="button" :disabled="formalBusy || !formalPermission('production.engineering.order.maintain')" @click="createFormalInstance">形成当前订单行工程实例</button>
            <button v-else-if="formalContinuationLine.instanceStatus === 'draft'" type="button" :disabled="formalBusy || formalContinuationLine.sourceStatus !== 'confirmed' || !formalPermission('production.engineering.order.maintain')" @click="confirmFormalInstanceSource">确认实例采用当前工程来源</button>
            <button type="button" class="secondary" :disabled="formalBusy || !formalContinuationLine?.orderEngineeringInstanceId || !selectedBaselineId" @click="validateFormalContinuation">校验正式办理条件</button>
            <button type="button" :disabled="formalBusy || !formalValidation.ready || !formalPermission('production.engineering.calculation.execute')" @click="executeFormalContinuation">按实例执行并保存</button>
          </div>
          <p class="boundary-note">{{ formalExecutionReason }}</p>
          <p v-if="formalValidation.ready" class="notice success">校验通过：基线 {{ formalValidation.selection?.baselineReference?.baselineNo }}；本实例 {{ formalValidation.selection?.objectCount }} 个对象；预计保存 {{ formalValidation.selection?.resultPositionCount }} 个结果位置。</p>
          <div v-else-if="formalValidation.blockers?.length" class="notice error"><strong>当前仍有阻断</strong><ul><li v-for="(row, index) in formalValidation.blockers" :key="`${row.code}-${index}`">{{ row.code }}：{{ row.reason || row.impact }}</li></ul></div>
          <p class="boundary-note">{{ formalContinuation.writeBoundary || '创建实例、状态确认和正式执行均会写入；校验零写入。' }} 写动作须另获明确业务批准，不能以校验通过代替批准。</p>
          <section v-if="mainContinuationFacts" class="formal-continuation" data-section="main-calculation-version-continuation" :aria-busy="formalBusy">
            <h3>主核算版本接续</h3>
            <p>{{ mainContinuationFacts.statusLabel }}</p>
            <p v-if="mainContinuationFacts.legacyAdoptionNo">历史承接：{{ mainContinuationFacts.legacyAdoptionNo }} · {{ mainContinuationFacts.frozenScopeLabel }}</p>
            <div class="formal-continuation-grid">
              <label><b>原主核算</b><select v-model.number="selectedPredecessorCalculationId" :disabled="formalBusy"><option :value="null">请选择原主核算</option><option v-for="row in mainContinuationFacts.predecessorCalculations || []" :key="row.id" :value="row.id">{{ row.calculationNo }} · {{ row.baselineNo }} · {{ row.statusLabel }}</option></select></label>
              <div><b>接续工程基线</b><span>{{ formalBaselines.find(row => row.id === selectedBaselineId)?.baselineNo || '请在原基线下拉中明确选择' }}</span><small>沿用上方已确认基线选择；预览与执行由服务端重验。</small></div>
            </div>
            <div class="actions formal-actions"><button v-for="action in mainContinuationActions" :key="action.actionCode" type="button" :disabled="formalBusy || action.allowed !== true || !mainContinuationPayload() || (action.actionCode === 'execute' && !mainContinuationCanExecute)" @click="runMainContinuationAction(action.actionCode)">{{ action.displayName }}</button></div>
            <p v-if="mainContinuationError" class="notice error" data-state="main-continuation-read-failed">{{ mainContinuationError }}</p>
            <div v-if="mainContinuationPreview" data-section="main-continuation-preview">
              <p>{{ mainContinuationPreview.statusLabel }}</p>
              <p v-if="mainContinuationPreview.continuationBasis">{{ mainContinuationPreview.continuationBasis.exactStatement || mainContinuationPreview.continuationBasis.summary || mainContinuationPreview.continuationBasis.reference }}</p>
              <ul v-if="mainContinuationPreview.blockers?.length"><li v-for="(blocker, index) in mainContinuationPreview.blockers" :key="index">{{ blocker.statusLabel || blocker.reason || blocker.message }}</li></ul>
            </div>
            <p v-if="mainContinuationReadback" class="notice success" data-section="main-continuation-committed-readback">{{ mainContinuationReadback.statusLabel }} · 新主核算 {{ mainContinuationReadback.calculationNo || mainContinuationReadback.newCalculationId }}</p>
            <p class="boundary-note">预览只读；正式接续只形成当前订单行的新主核算及其承接证明。后续BOM、制造输出、步骤绑定、需求和投产量分别办理。</p>
          </section>
          </template>
        </section>
        <section v-if="designInputRows.length" class="design-input-detail" data-section="current-design-calculation-inputs">
          <header><div><h3>{{ savedRecordSelected ? '所选核算冻结工程输入' : '当前设计逐项工程输入（候选）' }}</h3><p>“输入状态”和“缺项／不适用提示”说明设计对象资料；紧邻“订单行”的“核算保存前需完成”说明所属销售订单行的来源、实例、基线、规则与权限准备。查看不会确认、创建、发布或保存任何业务记录。</p></div><span class="pill">{{ designInputRows.length }} 项</span></header>
          <p class="baseline-relationship">{{ currentBaselineRelationship }}</p>
          <PceEnterpriseListTable
            ref="designInputTableRef"
            :contract="designInputListContract"
            page-id="pde-engineering-calculation-input-detail"
            table-id="pde-current-design-inputs"
            :rows="designInputRows"
            :table-rows="filteredDesignInputRows"
            :filter-schema="designInputFilterSchema"
            :filters="designInputFilters"
            :quick-search="designInputQuickSearch"
            :advanced-visible="designInputAdvancedVisible"
            :selected-count="selectedDesignInputRows.length"
            :active-filter-count="designInputActiveFilterCount"
            :sort-text="designInputSortText"
            primary-field="designItemNo"
            primary-label="设计对象编号"
            :primary-width="230"
            min-width="3600px"
            scroll-acceptance-id="pde-design-input-horizontal-scroll"
            :show-action-column="false"
            :show-refresh="false"
            :default-page-size="20"
            :page-sizes="[20, 50, 100]"
            @update:quick-search="designInputQuickSearch=$event"
            @search="designInputAppliedSearch=designInputQuickSearch"
            @toggle-advanced="designInputAdvancedVisible=!designInputAdvancedVisible"
            @clear-filters="clearDesignInputFilters"
            @clear-sort="clearDesignInputSort"
            @export-current="exportCurrentDesignInputs"
            @clear-selection="clearDesignInputSelection"
            @update-filter="updateDesignInputFilter"
            @selection-change="selectedDesignInputRows=$event"
            @sort-change="handleDesignInputSort"
          >
            <template #primary="{ row }"><span>{{ row.designItemNo }}</span><small>{{ row.itemName || '名称待完善' }}</small></template>
            <template #columns>
              <el-table-column prop="orderLineNo" label="订单行" width="105" sortable="custom" />
              <el-table-column label="核算保存前需完成" min-width="310">
                <template #default="{row}">
                  <span :class="{'error-text': conditionPreflightOperation.state === 'failed'}">{{ row.saveReadinessSummary }}</span>
                  <button
                    type="button"
                    class="link line-condition-trigger"
                    :data-sales-order-item-id="row.salesOrderItemId"
                    :aria-expanded="selectedConditionSalesOrderItemId === row.salesOrderItemId"
                    :disabled="conditionPreflightOperation.state === 'running' || !row.salesOrderItemId"
                    @click="showLineConditions(row)"
                  >查看本行条件</button>
                </template>
              </el-table-column>
              <el-table-column label="产品／位置" min-width="230" show-overflow-tooltip><template #default="{row}">{{ row.productCategoryName || '分类待匹配' }}<small>{{ [row.space, row.installationPosition].filter(Boolean).join('／') || '位置待维护' }}</small></template></el-table-column>
              <el-table-column label="数量／单位" width="150"><template #default="{row}">{{ row.physicalQuantity }} {{ row.physicalUomName || row.physicalUom || '单位待维护' }}<small>{{ row.savedFrozen ? '冻结数量／单位' : row.physicalUomMatchStatus === 'EXACT' ? '正式单位已匹配' : '来源单位快照' }}</small></template></el-table-column>
              <el-table-column label="尺寸语义(mm)" min-width="260" show-overflow-tooltip><template #default="{row}">{{ dimensionSemanticsText(row) }}</template></el-table-column>
              <el-table-column label="材料身份／规格" min-width="300" show-overflow-tooltip><template #default="{row}">{{ designMaterialText(row) }}<small>{{ row.materialProcess || (row.savedFrozen ? '材料工艺未冻结' : '材料工艺待维护') }}</small></template></el-table-column>
              <el-table-column prop="edgeMethod" label="封边" width="150" show-overflow-tooltip />
              <el-table-column prop="visibleCondition" label="见光" width="130" show-overflow-tooltip />
              <el-table-column prop="processConfiguration" label="工艺配置" min-width="240" show-overflow-tooltip />
              <el-table-column prop="paintProcess" label="油漆工艺" min-width="190" show-overflow-tooltip />
              <el-table-column label="颜色／版本" min-width="180" show-overflow-tooltip><template #default="{row}">{{ row.colorVersion || '来源未提供' }}<small>{{ row.revision ? `设计R${row.revision}` : '当前有效设计' }}</small></template></el-table-column>
              <el-table-column label="来源证据" min-width="260" show-overflow-tooltip><template #default="{row}">{{ row.sourceLocationLabel || `${row.sourceSheet}!${row.sourceRow}` }}<small>{{ row.sourceKey || row.inputAuthority }}</small></template></el-table-column>
              <el-table-column prop="calculationStatusLabel" label="输入状态" width="160" />
              <el-table-column label="缺项／不适用提示" min-width="320" show-overflow-tooltip><template #default="{row}">{{ designInputGapText(row) }}</template></el-table-column>
            </template>
          </PceEnterpriseListTable>
          <section
            v-if="selectedConditionSalesOrderItemId"
            id="sales-order-line-condition-detail"
            class="line-condition-detail"
            data-section="sales-order-line-save-readiness"
            :data-sales-order-item-id="selectedConditionSalesOrderItemId"
          >
            <template v-if="selectedLineCondition">
              <header><div><h4>销售订单第{{ selectedLineCondition.lineNo }}行 · {{ selectedLineCondition.designObjectCount }}个对象</h4><p>这是所属销售订单行的核算保存准备，不改变上方每个设计对象的“输入状态”和“缺项／不适用提示”。</p></div><span class="pill">{{ selectedLineCondition.saveReadinessStatusLabel }}</span></header>
              <dl class="line-condition-grid">
                <div><dt>工程来源</dt><dd>{{ selectedLineCondition.sourceStatus === 'confirmed' ? '已确认' : `未确认（${selectedLineCondition.sourceStatusLabel || '状态待核对'}）` }}</dd></div>
                <div><dt>订单工程实例</dt><dd>{{ selectedLineCondition.orderEngineeringInstanceId ? `已形成（${selectedLineCondition.orderEngineeringInstanceNo}）` : '尚未形成' }}</dd><small>用于把该销售订单行的设计对象、来源、基线和后续核算记录对应起来的办理记录。</small></div>
                <div><dt>所选工程基线</dt><dd>{{ selectedLineCondition.confirmedBaseline ? `${String(selectedLineCondition.confirmedBaseline.baselineNo).split('-').at(-1)} · ${selectedLineCondition.confirmedBaseline.statusLabel}` : '尚无已确认基线' }}</dd></div>
                <div><dt>所需核算规则</dt><dd>{{ selectedLineCondition.releasedRulePackageCount }}/{{ selectedLineCondition.requiredRulePackageCount }} 已发布</dd><small>{{ (conditionPreflight.requiredRulePackages || []).join('、') }}</small></div>
              </dl>
              <div class="line-condition-permissions"><strong>当前账号相关权限（服务端实时判定）</strong><span v-for="permission in lineConditionPermissions" :key="permission.code">{{ permission.label }}：{{ permission.allowed ? '有权限' : '无权限' }}<small>{{ permission.reason || permission.decisionCode }}</small></span></div>
              <div class="line-condition-pending"><strong>尚未完成的具体事项</strong><ul v-if="selectedLineCondition.blockers?.length"><li v-for="blocker in selectedLineCondition.blockers" :key="blocker.code">{{ blocker.reason }}</li></ul><p v-else>本行可进入完整执行前校验；仍须由有权人员明确执行后才会保存正式核算记录。</p></div>
            </template>
            <div v-else-if="conditionPreflightOperation.state === 'failed'" class="notice error"><strong>{{ conditionPreflightOperation.title }}</strong><p>{{ conditionPreflightOperation.message }} 本次读取结果未知，未按“不具备条件”处理。</p><button type="button" class="secondary" @click="preflightSelection">重试读取本行条件</button></div>
            <p v-else class="notice pending">本行条件尚未读取完成，请稍候或使用下方“校验核算条件（只读预检）”。</p>
          </section>
        </section>
        <details v-if="selectedOrder && !savedRecordSelected" class="auxiliary-panel" data-section="source-case"><summary>查看当前候选来源、正式规则与材料身份</summary><div class="case-summary">
          <strong>真实工程来源重建的非生产案例</strong>
          <dl><div><dt>验收对象</dt><dd>{{ selectedOrder.sourceCaseName }} · {{ selectedOrder.installationArea }}</dd></div><div><dt>来源位置</dt><dd>{{ selectedOrder.sourceFile }} / {{ selectedOrder.sourceSheet }} 第 {{ selectedOrder.sourceRow }} 行</dd></div><div><dt>正式订单关联</dt><dd>{{ stableOrderLinkLabel(selectedOrder.stableOrderLinkStatus) }}</dd></div><div><dt>实际覆盖范围</dt><dd>{{ selectedOrder.coverageStatement }}</dd></div></dl>
        </div>
        <div v-if="selectedOrder" class="table-wrap input-table" data-section="calculation-inputs"><table><thead><tr><th>中文字段</th><th>来源原值</th><th>规范输入</th><th>单位</th><th>来源与字段</th></tr></thead><tbody><tr v-for="row in selectedOrder.canonicalInputs || []" :key="row.id"><th>{{ row.displayName }}</th><td>{{ row.rawValue ?? '来源未填写' }}</td><td>{{ row.normalizedValue ?? '尚未确认' }}</td><td>{{ row.uomCode || '来源未填写' }}</td><td>{{ row.rawSource }} / {{ row.rawSheet || selectedOrder.sourceSheet }} · {{ row.rawField }}<small>{{ row.sourceType }}</small></td></tr></tbody></table></div>
        <fieldset><legend>历史／参考：旧G1规则目录（明确选择）</legend><p>此处的“已发布”只表示公司规则目录状态；是否适用于当前实例由下方旧G1服务端校验判定，不替代上方两套V1正式接续规则。</p><label v-for="rule in rules" :key="rule.id" class="check"><input v-model="selection.ruleIds" type="checkbox" :value="rule.id"><span>{{ rule.ruleCode }}@{{ rule.version }} · {{ rule.ruleName }} · {{ rule.resultDomain }}</span></label><p v-if="!rules.length">当前组织没有可选择的已发布规则。</p></fieldset>
        <div v-if="rules.length" class="table-wrap rule-table"><table><thead><tr><th>规则</th><th>计算表达式</th><th>输入</th><th>输出 / 单位</th><th>来源依据</th><th>目录／适用状态</th></tr></thead><tbody><tr v-for="rule in rules" :key="`detail-${rule.id}`"><th>{{ rule.ruleName }}<small>{{ rule.ruleCode }}@{{ rule.version }}</small></th><td><code>{{ rule.expression }}</code></td><td>{{ (rule.inputs || []).map(inputLabel).join('、') }}</td><td>{{ resultLabel(rule.calculationItem) }} / {{ rule.outputUnit }}</td><td>{{ rule.sourceEvidence }}</td><td>{{ rule.status === 'released' ? '公司目录已发布；本实例适用性待旧G1校验' : rule.status }}</td></tr></tbody></table></div>
        <div v-if="selectedMaterial" class="material-contract"><strong>材料身份与正式单位</strong><span>{{ selectedMaterial.sourceCode }} → {{ selectedMaterial.formalMaterialMatch }}</span><span>来源单位：{{ selectedOrder?.sourceUnit || '来源未填写' }}；正式基本单位：{{ selectedMaterialUom?.baseUom || '未确认' }}</span><small>内部对象号与来源证据保留在诊断数据中。</small></div></details>
        <div v-if="designSourceOwned" class="design-source-contract" data-section="product-design-source-contract">
          <div><strong>{{ savedRecordSelected ? '设计事实依据：所选核算的精确冻结设计修订' : '设计事实唯一来源：产品设计管理' }}</strong><p>{{ savedRecordSelected ? '本区只读所选核算对应的冻结修订和基线；当前设计的后续修改不会替换历史记录。发现差异需另行修订并形成新版本，本页不改写快照。' : '本页按当前有效设计投影候选输入。发现设计错误时，请回到源头修改并刷新；本页不会保存设计字段副本。' }}</p></div>
          <router-link class="primary-action" :to="productDesignReturnLocation">返回产品设计修改</router-link>
        </div>
        <div v-if="selectedOrder && !designSourceOwned" class="engineering-editor" data-section="engineering-input-editor">
          <header><div><h3>工程原始数据草稿</h3><p>人工录入与系统核算分开；保存会新增服务端草稿修订，不覆盖原来源或历史结果。</p></div><span class="pill">{{ draftRows.length }} 行</span></header>
          <div class="assignment-grid" data-section="engineering-responsibilities">
            <label v-for="role in responsibilityRoleDefinitions" :key="role.key">{{ role.label }}
              <el-select v-model="draftAssignments[role.key].employeeId" filterable clearable placeholder="搜索姓名或工号">
                <el-option v-for="employee in employeeOptions(role.key)" :key="employee.employeeId" :value="String(employee.employeeId)" :label="`${employee.label} · ${employee.positionName || '岗位待完善'}`" />
                <el-option v-if="historicalEmployeeOption(role.key)" :value="String(historicalEmployeeOption(role.key).employeeId)" :label="`${historicalEmployeeOption(role.key).label} · 历史记录`" disabled />
              </el-select>
              <small>{{ engineeringInputOptions.employeeRoles?.[role.key]?.statusLabel || '员工档案读取中' }}</small>
            </label>
            <label>包装方式
              <select v-model="draftPackaging.id" :disabled="!engineeringInputOptions.packagingMethods?.length"><option value="">未维护</option><option v-for="row in engineeringInputOptions.packagingMethods || []" :key="row.id" :value="String(row.id)">{{ row.label }}</option></select>
              <small>{{ engineeringInputOptions.packagingMethodState?.statusLabel || '读取中' }}；原 Excel 内容未导入。</small>
            </label>
          </div>
          <div v-if="Object.keys(confirmedResponsibilityFacts).length" class="confirmed-facts" data-section="confirmed-responsibility-facts"><strong>用户已确认的责任人</strong><span v-for="role in responsibilityRoleDefinitions" :key="`fact-${role.key}`">{{ role.label }}：{{ confirmedResponsibilityFacts[role.key]?.fullName || '未记录' }}（{{ confirmedResponsibilityFacts[role.key]?.employeeNo || '-' }}） · {{ confirmedResponsibilityFacts[role.key]?.statusLabel || '状态待核对' }}</span></div>
          <div class="actions"><router-link :to="engineeringInputOptions.maintenanceEntries?.employees || '/foundation/pfm/employees'" target="_blank" rel="noopener">维护员工档案</router-link><router-link :to="engineeringInputOptions.maintenanceEntries?.engineeringBreakdownOptions || '/foundation/master-data/engineering-breakdown-options?workspace=engineering-breakdown'" target="_blank" rel="noopener">维护工艺／拆单基础选项</router-link><span>尺寸、数量仍用数值输入；只有启用的正式标准项可供新选择。</span></div>
          <p v-if="selectedWorkbookSourceRecordId" class="boundary-note" data-section="workbook-object-source-boundary">{{ workbookSourceIntake.sourceIntakeStatusLabel || '当前来源版本的工程对象保存资格未知。' }}</p>
          <div class="actions"><button type="button" :disabled="savingRegisteredSource || !workbookObjectWriteAllowed" @click="saveRegisteredSource">{{ savingRegisteredSource ? '正在接入71行…' : '接入已登记71行真实来源' }}</button><button type="button" class="secondary" @click="addDraftRow('房门单')">新增房门行</button><button type="button" class="secondary" @click="addDraftRow('三合一单')">新增三合一行</button><button type="button" class="secondary" :disabled="!draftRows.length" @click="copyDraftRow">复制末行</button><label class="import-button">导入 CSV 预览<input type="file" accept=".csv,text/csv" @change="previewCsvImport"></label></div>
          <p v-if="importPreview" class="notice pending">导入预览：新建 {{ importPreview.newCount }} 行；冲突 {{ importPreview.conflictCount }} 行；缺项 {{ importPreview.missingCount }} 行。确认保存前不会写入。</p>
          <div class="table-wrap governed-scroll-table engineering-input-table" data-scroll-owner="engineering-input-table"><table><thead><tr><th class="sticky-sequence">序号</th><th class="sticky-identity">来源*</th><th>空间/房间</th><th>产品分类／产品*</th><th>部件/半成品*</th><th>编码</th><th>数量/单位*</th><th>来源尺寸(mm；房门第三项=墙厚)</th><th>材料规格</th><th>标准选项</th><th>封边方式／见光条件</th><th>来源材料编码</th><th>工艺配置</th><th>工艺及加工要求／图纸</th></tr></thead><tbody><tr v-for="(row, rowIndex) in draftRows" :key="row.id" :data-source-row-id="row.id" :data-source-sheet="row.sourceSheet || row.sourceType" :data-source-physical-row="row.sourceRow || ''"><td class="sticky-sequence">{{ rowIndex + 1 }}</td><td class="sticky-identity"><select v-model="row.sourceType"><option>房门单</option><option>三合一单</option></select></td><td><input v-model="row.space" placeholder="选填"></td><td><select v-model="row.productCategoryId" @change="applyProductCategory(row)"><option value="">产品分类确实未匹配</option><option v-for="option in productCategoryOptions(row)" :key="option.id" :value="String(option.id)">{{ option.label }}</option></select><input v-model="row.product" :class="{missing: !row.product}" placeholder="产品名称必填"></td><td><input v-model="row.component" :class="{missing: !row.component}" placeholder="必填"></td><td><input v-model="row.componentCode" placeholder="尚未形成正式编码"></td><td><input v-model="row.quantity" :class="{missing: !row.quantity}" placeholder="数量"><select v-model="row.unitId" :class="{missing: !row.unitId}" @change="applyUnit(row)"><option value="">正式单位未匹配（保留来源单位）</option><option v-for="option in unitOptions(row)" :key="option.id" :value="String(option.id)">{{ option.label }}</option></select></td><td><input v-model="row.length" :placeholder="row.sourceType === '房门单' ? '门洞/门套高' : '设计长'"><input v-model="row.width" :placeholder="row.sourceType === '房门单' ? '门洞/门套宽' : '设计宽'"><input v-model="row.thickness" :placeholder="row.sourceType === '房门单' ? '墙厚' : '部件厚'"></td><td><input v-model="row.materialName" placeholder="正式材料未匹配"><input v-model="row.specification" placeholder="正式规格未匹配"></td><td><select v-model="row.doorOpeningDirectionOptionId"><option value="">来源说明已保留／正式选项未匹配</option><option v-for="option in engineeringInputOptions.doorOpeningDirections || []" :key="option.id" :value="String(option.id)">{{ option.label }}</option></select><select v-model="row.lineStyleOptionId"><option value="">来源说明已保留／正式线型未匹配</option><option v-for="option in engineeringInputOptions.lineStyles || []" :key="option.id" :value="String(option.id)">{{ option.label }}</option></select><select v-model="row.edgeMethodOptionId"><option value="">封边方式确需确认</option><option v-for="option in engineeringInputOptions.edgeMethods || []" :key="option.id" :value="String(option.id)">{{ option.label }}</option></select></td><td><input v-model="row.edgeMode" placeholder="来源封边原值"><select v-model="row.visibleConditionCode" @change="applyVisibleCondition(row)"><option value="">见光条件确需确认</option><option v-for="option in engineeringInputOptions.visibleConditions || []" :key="option.code" :value="option.code">{{ option.name }} · {{ option.statusLabel }}</option></select></td><td><input v-model="row.materialProcessCode" placeholder="来源未提供"></td><td><input v-model="row.routingProcessCode" placeholder="来源未提供"></td><td><input v-model="row.processingNote" placeholder="来源未提供工艺、加工与质量要求"><small v-if="row.drawingReference">{{ row.drawingReference.statusLabel }}：{{ row.drawingReference.displayText }}</small></td></tr></tbody></table></div>
          <label class="reason-field">修订说明<input v-model="draftReason" placeholder="说明本次新增或修改内容"></label>
          <div class="actions"><button type="button" :disabled="!draftRows.length || savingDraft || !workbookObjectWriteAllowed" @click="saveDraft">{{ savingDraft ? '正在保存…' : '保存工程草稿' }}</button><select v-model="activeDraftId" @change="openDraft"><option value="">重新打开历史草稿</option><option v-for="draft in drafts" :key="draft.id" :value="String(draft.id)">{{ draft.sourceVersion }} · {{ draft.rows.length }}行 · {{ draft.revisionReason || '无说明' }}</option></select></div>
        </div>
        <div v-if="selectedOrder?.isSourceTrial" class="notice pending"><strong>{{ sourceOrderAssociation.title }}</strong><p>{{ sourceOrderAssociation.detail }} 当前只读展示不会绑定 PDE-ACCEPT-G1、生成BOM或进入生产计划。</p></div>
        <section v-if="selectedOrder" class="condition-preflight" data-section="read-only-condition-preflight">
          <header><div><h3>核算条件预检</h3><p>预检只回读当前订单、来源、实例、基线、正式规则包与权限事实；完整执行前校验和正式执行保存仍是后续独立动作。</p></div><span class="pill">零业务写入</span></header>
          <div class="actions"><button type="button" class="secondary" data-action="preflight-order-engineering-calculation" :disabled="busy || !selectedOrder.orderNo" @click="preflightSelection">{{ conditionPreflightOperation.state === 'running' ? '正在预检…' : '校验核算条件（只读预检）' }}</button><button type="button" disabled>执行工程／物料核算（正式办理）</button></div>
          <p class="boundary-note">{{ formalExecutionReason }}</p>
          <div v-if="conditionPreflightOperation.message" :class="['operation-feedback', conditionPreflightOperation.state]" data-state="condition-preflight-operation"><strong>{{ conditionPreflightOperation.title }}</strong><p>{{ conditionPreflightOperation.message }}</p></div>
          <div v-if="conditionPreflight.blockers?.length" class="notice error"><strong>预检完成，当前尚不可进入完整执行前校验</strong><ul><li v-for="row in conditionPreflight.blockers" :key="row.code"><b>{{ row.code }}</b>：{{ row.reason }} <span v-if="row.nextStepLabel">下一步：{{ row.nextStepLabel }}</span></li></ul></div>
          <p v-else-if="conditionPreflight.readyForFullValidation" class="notice success">预检未发现订单级阻断；请选择一个订单行进入完整执行前校验。预检通过不等于正式执行已获准。</p>
          <p class="completion-state"><b>{{ formalSelectedSavedState.label }}</b>：{{ formalSelectedSavedState.explanation }}</p>
        </section>
        <details v-if="selectedOrder && !selectedOrder.isSourceTrial" class="auxiliary-panel" data-section="legacy-g1-validation"><summary>旧G1规则验收入口（不替代本订单正式规则包）</summary><p>此处保留原订单工程闭环的旧规则校验和执行职责；当前订单正式接续使用上方两个正式规则包及订单行级办理，不以旧G1选择结果替代。</p><div class="actions"><button type="button" class="secondary" data-action="validate-order-engineering-calculation" :disabled="busy" @click="validateSelection">{{ validationOperation.state === 'running' ? '正在校验…' : actionLabel('validate-order-engineering-calculation') }}</button><button type="button" :disabled="!validation.ready || busy" @click="executeCalculation">{{ actionLabel('execute-order-engineering-calculation') }}</button></div></details>
      </section>
      <section v-show="activeBusinessPage === 'results'" class="card primary-workspace" data-section="work-order-main" :data-order-no="selectedOrder?.orderNo || ''" :data-row-count="workOrderRows.length">
        <header><div><h2>施工单／整单核算结果</h2><p><strong>{{ savedRecordSelected ? '施工单（所选核算冻结资料只读投影）' : '车间施工单（当前候选只读投影）' }}</strong>直接复用产品设计的分类、单位、尺寸、工艺与来源证据；正式主数据未匹配、本业务不适用和确需人工确认分别显示。已保存记录只读展示冻结事实；未冻结的材料、颜色、五金等真实缺项继续保留，不形成制造指令。</p></div><span class="pill">{{ workOrderRows.length }} 条</span></header>
        <div v-if="workOrderRows.length" class="table-wrap work-order-table governed-scroll-table" data-scroll-owner="work-order-table"><table><thead><tr><th class="sticky-sequence">序号</th><th class="sticky-identity">订单／项目</th><th>产品／空间／安装位置</th><th>半成品／部件</th><th>数量／正式单位</th><th>尺寸语义(mm)</th><th>材料身份／规格</th><th>封边</th><th>见光</th><th>颜色／工艺配置／油漆工艺</th><th>加工要求</th><th>五金／玻璃</th><th>资料状态</th></tr></thead><tbody><tr v-for="(row, rowIndex) in workOrderRows" :key="row.id" :data-design-item-no="row.designItemNo || ''" :data-order-line-no="row.orderLineNo || ''"><td class="sticky-sequence">{{ rowIndex + 1 }}</td><td class="sticky-identity">{{ displayFact(row.orderNo, selectedOrder?.orderNo || '订单未提供') }}<small>{{ row.orderLineLabel || `第${row.orderLineNo || '-'}行` }} · {{ row.projectReference || (row.savedFrozen ? '项目未冻结' : selectedOrder?.projectName) || '项目未提供' }}</small></td><td>{{ displayFact(row.product, '来源未提供产品分类') }}<small>{{ [row.space, row.installationPosition].filter(Boolean).join('／') || '来源未提供空间／安装位置' }}</small></td><td>{{ displayFact(row.component, '来源未提供部件') }}<small>{{ row.componentCode || row.designItemNo || '未形成正式产品编码' }}<small v-if="row.structureLabel">{{ row.structureLabel }} · 设计修订R{{ row.revision }}</small></small></td><td>{{ displayFact(row.quantity, '来源未提供数量') }} {{ displayFact(row.unit, '来源未提供单位') }}<small>{{ row.unitStatusLabel }}</small></td><td><span v-for="dimension in row.dimensionSemantics || []" :key="dimension.key" class="fact-line">{{ dimension.label }} {{ dimension.value }} {{ dimension.unit || '' }}</span></td><td>{{ materialSpecText(row) }}<small>{{ row.materialStatusLabel }}</small></td><td>{{ displayFact(row.edgeMode, '确需确认') }}<small>{{ row.edgeStatusLabel }}</small></td><td>{{ displayFact(row.visibleCondition, '确需确认') }}<small>{{ row.visibleStatusLabel }}</small></td><td>{{ row.colorVersion || '来源未提供颜色／版号' }}<small>配置：{{ row.processConfigurationLabel || row.routingProcessCode || '来源未提供' }}；油漆：{{ row.paintProcess || '来源未提供' }}</small></td><td>{{ displayFact(row.processingNote, '来源未提供加工要求') }}</td><td>{{ displayFact(row.hardware, '来源未提供五金要求') }}<small>玻璃：{{ row.glass || '来源未提供' }}</small></td><td><button v-if="workOrderMissingFields(row).length" type="button" class="link" @click="openMissingRow = openMissingRow === row.id ? '' : row.id">{{ workOrderMissingFields(row).length }}项需确认</button><span v-else class="pass-text">现有资料已带入</span><div v-if="openMissingRow === row.id" class="inline-detail">{{ workOrderMissingFields(row).join('；') }}</div></td></tr></tbody></table></div>
        <div v-else class="empty-state"><strong>尚未形成施工单明细</strong><span>请先在“工程数据录入”页保存工程草稿。</span><button type="button" class="link" @click="switchBusinessPage('input')">打开工程数据录入</button></div>
        <section v-if="!savedRecordSelected && sourceCalculationRows.length" class="source-result-workspace" data-section="source-engineering-results">
          <header><div><h3>工程／管理整单核算结果</h3><p><strong>当前设计试算／预览（非正式保存）</strong> · {{ activeDraft?.currentInputCalculation?.readStatusLabel || activeDraft?.sourceCalculation?.readStatusLabel || '按当前产品设计输入与既有核算规则只读计算；不是正式订单写入记录。' }}</p></div><strong class="pill">{{ sourceCalculationRows.length }} 项预览结果</strong></header>
          <section v-if="activeDraft?.currentInputCalculation?.baselineRelationship" class="confirmed-facts" data-section="calculation-input-baseline-relationship"><strong>核算输入与工程基线关系</strong><span>{{ activeDraft.currentInputCalculation.baselineRelationship.statusLabel }}</span><span>{{ activeDraft.currentInputCalculation.baselineRelationship.bindingStatusLabel }}</span></section>
          <section class="current-comparison" data-section="current-calculation-comparison"><h4>当前核算对照</h4><div class="result-stat-strip"><span>有效数值 {{ sourceResultSummary.numeric }}</span><span>独立对照一致 {{ sourceResultSummary.consistent }}</span><span>无独立对照 {{ sourceResultSummary.noIndependentComparison }}</span><span>已确认设计变更差异 {{ sourceResultSummary.confirmedDesignChangeDifferences }}</span><span>异常差异 {{ sourceResultSummary.unexplainedDifferences }}</span><span>当前缺条件 {{ sourceResultSummary.missing }}</span></div><p class="comparison-regression-status">{{ historicalAcceptanceRegression.statusLabel || '历史验收一致性读取中' }}</p><div class="comparison-actions"><button type="button" class="secondary" @click="comparisonView = 'no-comparison'">查看无独立对照（{{ sourceResultSummary.noIndependentComparison }}）</button><button type="button" class="secondary" @click="comparisonView = 'confirmed-design-changes'">查看已确认设计变更差异（{{ sourceResultSummary.confirmedDesignChangeDifferences }}）</button><button type="button" class="secondary" @click="comparisonView = 'differences'">查看异常差异（{{ sourceResultSummary.unexplainedDifferences }}）</button><button type="button" class="secondary" @click="comparisonView = 'historical'">查看历史基线</button></div><p v-if="differenceExplanation" class="difference-explanation">{{ differenceExplanation }}</p></section>
          <details v-if="historicalSourceCalculationRows.length" class="acceptance-comparison" data-section="historical-baseline-comparison" :open="comparisonView === 'historical'"><summary>原 71 行核算基线（独立保护，不被当前设计覆盖）</summary><p>{{ activeDraft?.sourceCalculation?.readStatusLabel }}；共 {{ historicalSourceCalculationRows.length }} 项，核对一致 {{ historicalSourceResultSummary.consistent }} 项，缺失 {{ historicalSourceResultSummary.missing }} 项。</p><p>当前设计输入快照：{{ activeDraft?.currentInputCalculation?.inputSnapshotVersion || '未建立' }} / {{ activeDraft?.currentInputCalculation?.inputSnapshotHash || '-' }}；相对原来源值变化 {{ activeDraft?.currentInputCalculation?.designInputChangeCount || 0 }} 处。</p></details>
          <div v-if="['no-comparison', 'confirmed-design-changes', 'differences'].includes(comparisonView)" class="table-wrap comparison-result-table"><table><thead><tr><th>来源</th><th>产品／部件</th><th>计算项目</th><th>当前结果</th><th>独立对照</th><th>差值</th><th>状态</th><th>当前计算依据</th><th>历史设计变更依据</th></tr></thead><tbody><tr v-for="row in focusedComparisonRows" :key="`focused-${row.id}`"><td>{{ row.sheet }} 第{{ row.row }}行</td><td>{{ row.product }}／{{ row.component }}</td><td>{{ row.project }}</td><td>{{ row.value }} {{ row.unit || '' }}</td><td>{{ row.expected ?? '原来源未形成独立数值' }}</td><td>{{ row.difference ?? '不可比较' }}</td><td>{{ row.statusLabel }}</td><td>{{ row.sourceCell }} · {{ row.reason || row.expression }}</td><td>{{ row.historicalAcceptance?.designChangeBasis || (row.comparisonClassification === 'NEW_UNEXPLAINED_DIFFERENCE' ? '未匹配历史正式验收依据' : '旧来源未形成独立数值') }}</td></tr></tbody></table></div>
          <details class="acceptance-comparison"><summary>验收对照：房门第11行与三合一代表记录</summary><div class="table-wrap"><table><thead><tr><th>来源记录</th><th>中文字段名</th><th>单位</th><th>软件结果</th><th>独立核对值</th><th>差异</th><th>来源／规则依据</th></tr></thead><tbody><tr v-for="row in acceptanceComparisonRows" :key="`compare-${row.id}`"><td>{{ row.sourceLabel }}</td><td>{{ row.project }}</td><td>{{ row.unit || '无单位' }}</td><td>{{ row.softwareValue }}</td><td>{{ row.independentValue }}</td><td>{{ row.differenceLabel }}</td><td>{{ row.sourceCell || '来源条件缺失' }} · {{ row.ruleVersion || row.reason }}</td></tr></tbody></table></div></details>
          <div class="table-wrap source-result-table"><table><thead><tr><th>来源</th><th>产品／部件</th><th>计算项目</th><th>结果／单位</th><th>状态</th><th>依据</th></tr></thead><tbody><tr v-for="row in sourceCalculationRows" :key="row.id"><td>{{ row.sheet }} 第{{ row.row }}行</td><td>{{ row.product }}／{{ row.component }}</td><td>{{ row.project }}</td><td>{{ row.value ?? '未形成' }} {{ row.unit || '' }}</td><td>{{ row.statusLabel }}</td><td><details><summary>查看计算依据</summary><p>{{ row.sourceCell }} · {{ row.ruleVersion }}</p><p>{{ row.reason || row.expression }}</p></details></td></tr></tbody></table></div>
        </section>
        <div class="production-plan" data-section="production-plan">
          <header><div><h3>{{ savedRecordSelected ? '当前生产计划（非本核算冻结输入）' : '生产计划' }}</h3><p>工序来自当前订单工程版本的正式工艺路线；日期只读取生产计划，不在施工单内编辑或生成。</p></div><strong class="pill pending">{{ productionPlan.statusLabel }}</strong></header>
          <div v-if="productionPlan.rows?.length" class="table-wrap"><table><thead><tr><th>工序顺序</th><th>生产对象</th><th>工序名称</th><th>计划开工日期</th><th>计划完工日期</th><th>状态</th></tr></thead><tbody><tr v-for="row in productionPlan.rows" :key="row.key"><td>{{ row.sequence }}</td><td>{{ row.objectLabel }}</td><td>{{ row.operationName }}<small>{{ row.operationCode }}</small></td><td>{{ row.plannedStartDate || '—' }}</td><td>{{ row.plannedFinishDate || '—' }}</td><td>{{ row.statusLabel }}</td></tr></tbody></table></div>
          <div v-else class="empty-state"><strong>{{ productionPlan.statusLabel }}</strong><span>{{ productionPlan.detail || '当前订单和工程版本没有可显示的正式工序计划；不会使用当天日期、交期或承诺日期代填。' }}</span></div>
          <details v-if="productionPlan.routingVersion || productionPlan.planNo"><summary>查看关联依据</summary><p>工程版本：{{ productionPlan.engineeringVersion || '未建立' }}；工艺路线：{{ productionPlan.routingCode || '未建立' }} / {{ productionPlan.routingVersion || '未建立' }}；计划批次：{{ productionPlan.planBatch || '未排计划' }}。</p></details>
        </div>
      </section>
      <section v-show="activeBusinessPage === 'results'" class="card" data-section="validation">
        <header><div><h2>核算记录</h2><p>服务端条件校验的状态与结果直接显示；公式、来源单元格、错误码和对账过程按需查看。</p></div><strong :class="['pill', validation.ready ? 'pass' : 'pending']">{{ validationState }}</strong></header>
        <div v-if="validationOperation.message" :class="['operation-feedback', validationOperation.state]" data-state="validation-operation" :data-operation-state="validationOperation.state"><strong>{{ validationOperation.title }}</strong><p>{{ validationOperation.message }}</p></div>
        <div v-if="validation.ready" class="notice pass-box">已具备尺寸核算条件。订单行、实例、来源、规范输入及尺寸规则包已通过当前服务端校验；材料数量与BOM条件仍独立判断。</div>
        <div v-else-if="validation.blockers?.length" class="table-wrap"><table><thead><tr><th>对象</th><th>影响</th><th>维护入口</th><th>详情</th></tr></thead><tbody><tr v-for="row in validation.blockers" :key="`${row.code}-${row.subject}`"><td>{{ row.subject }}</td><td>{{ row.impact }}</td><td>{{ row.maintenancePath }}</td><td><details><summary>技术详情</summary><code>{{ row.code }}</code></details></td></tr></tbody></table></div><p v-else>请选择订单行并点击校验。</p>
      </section>
      <section v-show="activeBusinessPage === 'results'" class="card" data-section="calculation-records">
        <header><div><h2>正式持久化核算记录</h2><p>与上方“来源工程量预览”分开；保存的正式修订和历史记录继续保留。</p></div><button v-if="selectedOrder && !selectedOrder.isSourceTrial" type="button" class="secondary" @click="loadCalculations">刷新记录</button></header>
        <div v-if="!visibleCalculations.length" class="notice empty">{{ selectedOrder?.isSourceTrial ? `当前为整单来源范围的只读预览。${formalOrderSavedState.label}；各行正式记录请从“工程数据录入”的“查看本行办理详情”进入本页查看。来源预览不代替已保存记录。` : '尚无当前订单工程核算记录。' }}</div>
        <div v-else class="table-wrap"><table><thead><tr><th>记录</th><th>状态</th><th>核算修订</th><th>工程结果</th><th>材料需求</th><th>工序需求</th><th>操作</th></tr></thead><tbody><tr v-for="row in visibleCalculations" :key="row.id" :class="{ selected: activeCalculation?.id === row.id }"><td><b>{{ row.calculationNo }}</b></td><td>{{ calculationStatusLabel(row) }}<details v-if="row.errorCode"><summary>查看失败详情</summary><small class="error-text">{{ row.errorMessage }}（{{ row.errorCode }}）</small></details></td><td>R{{ row.revision }}</td><td>{{ row.derivedFacts?.length || 0 }} 项</td><td>{{ row.materialRequirements?.length ? `${row.materialRequirements.length} 项` : '本次核算未生成' }}</td><td>{{ row.operationRequirements?.length ? `${row.operationRequirements.length} 项` : '本次核算未生成' }}</td><td><button type="button" class="link" @click="chooseSavedRecord(row)">查看结果</button></td></tr></tbody></table></div>
        <div v-if="activeCalculation" class="result-detail" data-section="calculation-results">
          <div class="record-meta"><span>记录：{{ activeCalculation.calculationNo }}</span><span>完成时间：{{ formatTime(activeCalculation.finishedAt) }}</span><span>规则包：{{ activeCalculation.ruleSetVersion }}</span><span>核算修订：R{{ activeCalculation.revision }}</span></div>
          <p v-if="calculationDetailLoading" class="notice">正在读取所选正式记录的完整追溯。</p>
          <p v-else-if="calculationDetailError" class="notice error">{{ calculationDetailError }} 请通过本记录的“查看结果”重试。</p>
          <section v-if="calculationTraceRows(activeCalculation).length" class="formal-saved-trace" aria-label="已保存记录来源与基线追溯"><h3>已保存记录来源与基线追溯</h3><dl><template v-for="item in calculationTraceRows(activeCalculation)" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></template></dl><p>以上依据来自所选正式记录的持久化追溯，不使用当前设计预览替代。</p></section>
          <div class="table-wrap"><table><thead><tr><th>业务结果</th><th>数值 / 单位</th><th>计算依据</th></tr></thead><tbody><tr v-for="row in activeCalculation.details || []" :key="row.id"><th>{{ row.outputLabel || resultLabel(row.outputName) }}</th><td>{{ decimalValue(row.outputValue) }} {{ row.uomCode || '' }}</td><td><details class="calculation-input-trace"><summary>查看计算依据</summary><b>{{ row.ruleCode }}@{{ row.ruleVersion }}</b><p v-for="(input, index) in calculationInputLines(row.inputSnapshot)" :key="index">{{ input }}</p><code>{{ row.expressionSnapshot }}</code><small>舍入 {{ row.rounding }}；精度 {{ row.precision }}</small></details></td></tr></tbody></table></div>
          <div class="result-grid"><article><h3>物料需求</h3><p v-if="!activeCalculation.materialRequirements?.length" class="blocked-copy"><b>本次核算未生成材料需求，不表示材料消耗为0。</b><br>请核对已选规则是否输出材料需求，以及正式材料身份、基本单位和单件／订单总量口径；上方只读批量结果不会自动写入这里。已有尺寸和工程净量继续保留，不用数量1占位。预留或损耗未维护时，毛量保持未知，不等于已有净量无效。</p><dl v-for="row in activeCalculation.materialRequirements || []" :key="row.id"><div><dt>{{ row.materialCode }} · {{ row.materialName }}</dt><dd>{{ row.netQuantity }} {{ row.uomCode }}（{{ row.quantityBasis }}）</dd></div><div><dt>损耗</dt><dd>{{ row.scrapRateStatus === 'maintained' ? `${row.scrapRate}；含损耗 ${row.grossQuantity}` : '未知，保持空值' }}</dd></div></dl></article><article><h3>工序作业量</h3><p v-if="!activeCalculation.operationRequirements?.length">本次核算未生成工序作业量，不表示作业量为0；需有绑定正式工序及核算单位的工序作业量规则，不影响查看尺寸结果。工程量不等于工时。</p><dl v-for="row in activeCalculation.operationRequirements || []" :key="row.id"><div><dt>{{ row.operationCode }} · {{ row.operationName }}</dt><dd>{{ row.workloadQuantity }} {{ row.uomCode }}</dd></div></dl></article></div>
        </div>
      </section>
      <details v-show="activeBusinessPage === 'results'" class="card auxiliary-panel" data-section="method-trial-reconciliation"><summary>查看候选方法试算与独立对账</summary><div class="details-body">
        <header><div><h2>4. 候选核算方法试算与独立对账</h2><p>复用正式核算的安全表达式核心；候选规则保持draft，试算结果不写入正式核算、物料需求或BOM。</p></div><strong :class="['pill', methodTrial?.trialStatus === 'PASS' ? 'pass' : 'pending']">{{ methodTrialState }}</strong></header>
        <div v-if="candidateMethods.length" class="candidate-methods">
          <fieldset><legend>选择适用于当前对象的候选方法</legend><label v-for="method in candidateMethods" :key="method.id" class="check"><input v-model="selection.candidateRuleIds" type="checkbox" :value="method.id"><span>{{ method.ruleName }} · {{ method.ruleCode }}@{{ method.version }} · {{ method.methodStatus }}</span></label></fieldset>
          <div class="table-wrap rule-table"><table><thead><tr><th>方法</th><th>适用条件</th><th>计算表达式</th><th>输入</th><th>输出</th><th>来源依据</th></tr></thead><tbody><tr v-for="method in candidateMethods" :key="`candidate-${method.id}`"><th>{{ method.ruleName }}<small>{{ method.methodStatus }}</small></th><td>{{ applicabilityText(method.applicability) }}</td><td><code>{{ method.expression }}</code></td><td>{{ method.inputs.map(inputLabel).join('、') }}</td><td>{{ method.outputLabel }} / {{ method.outputUnit }}</td><td>{{ method.sourceEvidence }}</td></tr></tbody></table></div>
          <div class="actions"><button type="button" :disabled="!activeCalculation || !selection.candidateRuleIds.length || busy" data-action="trial-engineering-methods" @click="trialMethods">{{ methodTrialOperation.state === 'running' ? '正在试算并对账…' : '执行候选方法试算' }}</button></div>
        </div>
        <p v-else class="blocked-copy">当前组织尚未登记可试算的draft候选方法；已发布尺寸结果仍可查看。</p>
        <div v-if="methodTrialOperation.message" :class="['operation-feedback', methodTrialOperation.state]"><strong>{{ methodTrialOperation.title }}</strong><p>{{ methodTrialOperation.message }}</p></div>
        <template v-if="methodTrial">
          <div class="trial-summary"><b>基于尺寸核算：{{ methodTrial.sourceCalculationNo }}</b><span>订单数量 {{ methodTrial.orderQuantity }}</span><span>对账方式：精确Decimal数值与单位</span><span>预期值未作为系统输入</span></div>
          <div class="table-wrap"><table><thead><tr><th>工程净量</th><th>系统试算</th><th>独立来源核对</th><th>差异</th><th>公式与代入值</th><th>状态</th></tr></thead><tbody><tr v-for="row in methodTrial.rows" :key="row.ruleId"><th>{{ row.outputLabel }}<small>{{ row.ruleCode }}@{{ row.ruleVersion }} · {{ row.methodStatus }}</small></th><td>{{ row.systemValue }} {{ row.systemUnit }}</td><td>{{ row.independentValue }} {{ row.independentUnit }}<small>{{ row.sourceCell }}</small></td><td>{{ row.difference }} {{ row.systemUnit }}</td><td><code>{{ row.expression }}</code><small>{{ substitutionText(row.substitution) }}</small><small>精度 {{ row.precision }}；最终 {{ row.outputScale }} 位；{{ row.rounding }}</small></td><td><b :class="row.result === 'PASS' ? 'pass-text' : 'error-text'">{{ row.result === 'PASS' ? '对账一致' : '存在差异' }}</b></td></tr></tbody></table></div>
          <div class="result-grid"><article><h3>本轮已成立</h3><p>封边净长度可从当前真实尺寸与订单数量重新试算并下钻到公式、代入值和来源核对；结果仍是工程派生事实，不是正式材料耗用量。</p></article><article><h3>仍待完成</h3><p>“25/50”规格含义、正式封边材料身份、逐边预留参数及毛量仍未确认；不会据此生成材料需求或BOM。</p></article></div>
          <p class="boundary">后续衔接：工程量需携带产品/部件、适用工序、数量与单位、工艺/规则版本、来源和计算批次；工程量不等于工时，本次不占用产能、不排产。</p>
        </template>
      </div></details>
      <details v-if="!savedRecordSelected" v-show="activeBusinessPage === 'results'" class="card auxiliary-panel" data-section="source-calculation-details"><summary>查看71行来源、核算依据与对账明细</summary><div class="details-body"><EngineeringCalculationBatchPanel :order="selectedOrder || null" :non-production="!!readiness.runtimeEnvironment?.nonProduction" :workbook-source-record-id="selectedWorkbookSourceRecordId" /></div></details>
      <section v-show="activeBusinessPage === 'scheduling'" class="card" data-section="scheduling-summary">
        <header><div><h2>工程作业量汇总</h2><p>查看同订单、同工程版本的房门单＋三合一单工程事实，包含面积、长度和数量。工程量不等于工时；本页不是 APS 输入确认或排产页面。</p></div><PceBusinessStatus v-if="engineeringWorkloadSummary" :status-code="engineeringWorkloadSummary.statusCode" :status-label="engineeringWorkloadSummary.statusLabel" /></header>
        <p class="boundary-note">工程事实经已发布规则转换、确认数量口径并分配到正式计划步骤后，才能另行验证排产输入。本页仅展示服务端事实，不执行转换、生成日期、分配资源或形成产能结论。</p>
        <div class="actions"><el-button v-if="permissionAllowed(RULE_VIEW_PERMISSION)" type="primary" @click="router.push(ruleDefinitionsLocation)">打开工程规则定义</el-button></div>
        <div class="workshop-tabs"><button type="button" :class="{active: workshopView === 'paint'}" @click="workshopView = 'paint'">油漆车间：按物料编码</button><button type="button" :class="{active: workshopView === 'wood'}" @click="workshopView = 'wood'">木工车间：按工艺编码</button></div>
        <div v-if="!engineeringWorkloadSummary" class="notice" :class="engineeringWorkloadDisplayError ? 'error' : 'empty'" data-state="engineering-workload-unknown"><strong>{{ engineeringWorkloadDisplayError ? '工程作业量汇总读取失败' : engineeringWorkloadReadState === 'loading' ? '正在读取工程作业量汇总' : '工程作业量汇总尚未完整读取' }}</strong><p>{{ engineeringWorkloadDisplayError || '请先选择订单或工程来源，再刷新当前版本。数量与转换状态未知，未补为零。' }}</p></div>
        <template v-else>
          <p>{{ engineeringWorkloadSummary.readStatusLabel }}</p>
          <EngineeringWorkloadPurposeReview :facts="engineeringWorkloadSummary.purposeReview" :source-objects="engineeringWorkloadSourceObjects" :source-sales-order-item-id="selectedOrder?.salesOrderItemId" :refreshing="engineeringWorkloadReadState === 'loading' || calculationDetailLoading" @refresh="refreshEngineeringWorkload" />
          <p v-for="(snapshot, index) in engineeringWorkloadSummary.sourceSnapshots || []" :key="index"><PceBusinessStatus :status-code="snapshot.readStatus" :status-label="snapshot.readStatusLabel" /></p>
          <div class="record-meta"><span v-for="snapshot in engineeringWorkloadSummary.sourceSnapshots || []" :key="snapshot.key">{{ snapshot.key === 'currentInputCalculation' ? '当前预览' : '历史来源' }}：{{ displayFact(snapshot.resultCount, '未知') }}</span><span>已保存工程事实：{{ displayFact(engineeringWorkloadSummary.counts?.formalFactCount, '未知') }}</span><span>已核验工序需求：{{ displayFact(engineeringWorkloadSummary.counts?.verifiedOperationRequirementCount, '未知') }}</span><span>有效工序规则：{{ displayFact(engineeringWorkloadSummary.counts?.nativeOperationRuleCount, '未知') }}</span></div>
          <p class="boundary-note">当前预览与历史来源是两份独立快照，不叠加为订单工程量。</p>
          <p class="boundary-note">{{ workshopView === 'paint' ? '油漆车间按物料编码归组。' : '木工车间按工艺编码归组，并保留木工＋油漆工艺信息。' }}来源编码用于工程归组，不代表已绑定正式工序。不同单位、不同来源性质分别展示。</p>
          <ul v-if="engineeringWorkloadSummary.missingReasons?.length"><li v-for="(reason, index) in engineeringWorkloadSummary.missingReasons" :key="index">{{ reason.statusLabel }}</li></ul>
          <section v-for="list in engineeringWorkloadLists" :key="list.id" :data-section="list.id">
            <h3>{{ list.title }}</h3>
            <p>{{ list.description }}</p>
            <PceEnterpriseListTable
              :ref="component => list.runtime.tableRef = component"
              :contract="list.contract"
              :page-id="list.id"
              :table-id="`${list.id}-table`"
              :rows="list.rows"
              :table-rows="list.runtime.filteredRows"
              :filter-schema="engineeringWorkloadFilterSchema"
              :filters="list.runtime.filters"
              :quick-search="list.runtime.quickSearch"
              :advanced-visible="list.runtime.advancedVisible"
              :selected-count="list.runtime.selectedRows.length"
              :active-filter-count="list.runtime.activeFilterCount"
              :sort-text="list.runtime.sortText"
              row-key="key"
              primary-field="sourceCode"
              :primary-label="list.id === 'engineering-workload-formal-facts' ? '来源编码' : workshopView === 'paint' ? '来源物料编码' : '来源工艺编码'"
              :primary-width="210"
              min-width="1900px"
              action-label="来源与关联"
              :action-width="220"
              :default-page-size="20"
              :page-sizes="[20, 50, 100]"
              :refreshing="engineeringWorkloadReadState === 'loading' || calculationDetailLoading"
              @update:quick-search="list.runtime.quickSearch=$event"
              @search="list.runtime.applySearch"
              @toggle-advanced="list.runtime.advancedVisible=!list.runtime.advancedVisible"
              @clear-filters="list.runtime.clearFilters"
              @clear-sort="list.runtime.clearSort"
              @export-current="list.runtime.exportCurrent"
              @clear-selection="list.runtime.clearSelection"
              @update-filter="list.runtime.updateFilter"
              @selection-change="list.runtime.handleSelectionChange"
              @sort-change="list.runtime.handleSort"
              @refresh="refreshEngineeringWorkload"
            >
              <template #primary="{row}">{{ displayFact(row.sourceCode, '来源编码未提供') }}</template>
              <template #columns>
                <el-table-column prop="sourceProject" label="来源工程项目" min-width="230" sortable="custom" show-overflow-tooltip />
                <el-table-column prop="dataTypeLabel" label="数据类型" min-width="160" sortable="custom" />
                <el-table-column prop="quantity" label="工程数量" width="150" sortable="custom"><template #default="{row}">{{ displayFact(row.quantity, '未知') }}</template></el-table-column>
                <el-table-column prop="uomLabel" label="单位" width="125"><template #default="{row}">{{ displayFact(row.uomLabel || row.uomCode, '单位未确认') }}</template></el-table-column>
                <el-table-column prop="sourceNatureLabel" label="来源性质" min-width="220" sortable="custom" />
                <el-table-column prop="statusLabel" label="转换状态" min-width="230"><template #default="{row}"><PceBusinessStatus :status-code="row.statusCode" :status-label="row.statusLabel" /></template></el-table-column>
                <el-table-column label="缺少规则／待确认事项" min-width="260"><template #default="{row}"><span v-if="!Array.isArray(row.missingReasons)">缺项事实未提供</span><ul v-else><li v-for="(reason, index) in row.missingReasons" :key="index">{{ reason.statusLabel }}</li></ul></template></el-table-column>
              </template>
              <template #actions="{row}"><details class="engineering-workload-trace"><summary>来源贡献与关联</summary><p>房门单：{{ displayFact(row.contributions?.door, '未知') }}；三合一单：{{ displayFact(row.contributions?.threeInOne, '未知') }}</p><p v-if="row.contributions?.other != null">其他来源：{{ row.contributions.other }}</p><p v-for="(item, index) in row.contributions?.items || []" :key="item.id || item.sourceKey || index">{{ item.sheet }} 第{{ item.row }}行 · {{ item.sourceProject }} · {{ displayFact(item.quantity, '未知') }} {{ item.uomCode }}<small>{{ item.sourceNatureLabel }}</small></p><p v-if="row.sourceCalculationId">来源核算记录：{{ row.sourceCalculationId }}；事实：{{ row.sourceFactId }}；成功明细：{{ row.sourceDetailId }}</p><p v-if="row.operationRequirementIds?.length">已关联工序需求：{{ row.operationRequirementIds.join('、') }}</p><article v-for="requirement in row.conversion?.requirements || []" :key="requirement.operationRequirementId"><b>工序需求 {{ requirement.operationCode }} · {{ requirement.operationName }}</b><p>工序作业量：{{ displayFact(requirement.workloadQuantity, '未知') }} {{ requirement.uomLabel || requirement.uomCode }}</p><p>来源工程数量与工序作业量分别保留，转换关联不代表已完成计划步骤分配。</p></article></details></template>
            </PceEnterpriseListTable>
          </section>
        </template>
      </section>
      <section v-show="activeBusinessPage === 'materials'" class="card" data-section="material-summary">
        <header><div><h2>材料汇总</h2><p>正式材料需求、工程量预览和待补齐事项分开显示；预览不进入领料或采购。</p></div><strong class="pill">{{ materialSummaryRows.length ? `${materialSummaryRows.length}种正式材料` : '正式清单待形成' }}</strong></header>
        <section class="formal-continuation material-requirement-preview" data-section="material-requirement-handoff-preview" data-preview-mode="r1-no-recalc-readback" :data-business-write-count="materialRequirementPreview.databaseBusinessWriteCount ?? ''">
          <header><div><h3>材料需求承接预览与正式Readback</h3><p>读取现有完成核算、已保存明细／派生事实、正式Material/UOM、已发布Mapping与正式需求；页面不重算、读取0写入，候选行不冒充正式材料清单。</p></div><span class="pill">{{ materialRequirementPreviewLoading ? '读取中' : materialRequirementPreview.objectCount != null ? `整单${materialRequirementPreview.objectCount}对象` : '待读取' }}</span></header>
          <div v-if="materialRequirementPreviewError" class="notice error" data-state="material-preview-read-failed"><strong>材料需求承接预览读取失败</strong><p>{{ materialRequirementPreviewError }} 当前数量未知，未伪装成0。</p></div>
          <template v-else-if="materialRequirementPreview.objectCount != null">
            <div class="formal-continuation-grid material-preview-facts">
              <div><b>设计对象</b><span>{{ materialRequirementPreview.objectCount }}</span><small>互斥分类合计 {{ materialPreviewClassificationTotal }}；闭合：{{ materialRequirementPreview.classificationClosed ? '是' : '否' }}</small></div>
              <div><b>正式Material</b><span>{{ materialRequirementPreview.metrics?.formalMaterialReferencedCount || 0 }}</span><small>缺Material：{{ materialRequirementPreview.metrics?.missingMaterialCount || 0 }}</small></div>
              <div><b>对象物理UOM</b><span>{{ materialRequirementPreview.metrics?.physicalUomCompleteCount || 0 }} 完整</span><small>缺UOM：{{ materialRequirementPreview.metrics?.physicalUomMissingCount || 0 }}</small></div>
              <div><b>承接已确认</b><span>{{ materialPreviewCounts.CONFIRMED || 0 }}</span><small>待形成候选 {{ materialPreviewCounts.READY_FOR_REQUIREMENT || 0 }}；候选行 {{ materialRequirementPreview.candidateCount || 0 }}</small></div>
              <div><b>缺Mapping</b><span>{{ materialPreviewCounts.MISSING_MAPPING || 0 }}</span><small>缺Material {{ materialPreviewCounts.MISSING_MATERIAL || 0 }}；多候选 {{ materialPreviewCounts.AMBIGUOUS_MATERIAL || 0 }}</small></div>
              <div><b>正式材料需求</b><span>{{ materialRequirementPreview.formalEngineeringMaterialRequirementCount || 0 }}</span><small>业务写入 {{ materialRequirementPreview.databaseBusinessWriteCount || 0 }}；核算重执行：{{ materialRequirementPreview.calculationReexecuted ? '是' : '否' }}</small></div>
            </div>
            <p class="boundary-note"><b>{{ materialRequirementPreview.bomGate?.code || 'MATERIAL_REQUIREMENT_REQUIRED' }}</b>：{{ materialRequirementPreview.bomGate?.blocked ? '继续阻断' : '按正式需求另行校验' }}。Preview候选不替代EngineeringMaterialRequirement。</p>
            <section v-if="businessConfirmationPackage.objectCount" class="business-confirmation-package" data-section="material-mapping-business-confirmation-package" :data-confirmation-only="(businessConfirmationPackage.confirmedMappingCount || 0) === 0">
              <header><div><h4>Material Requirement Mapping 业务确认与正式Readback</h4><p>{{ businessConfirmationPackage.modeLabel }} 页面没有确认、批准或发布动作，当前只读展示正式结果。</p></div><span class="pill">已确认 {{ businessConfirmationPackage.confirmedMappingCount || 0 }}／{{ businessConfirmationPackage.decisionUnitCount || 0 }}</span></header>
              <div class="formal-continuation-grid material-preview-facts">
                <div><b>71项覆盖</b><span>{{ businessConfirmationPackage.objectCount }}</span><small>闭合：{{ businessConfirmationPackage.coverageClosed ? '是' : '否' }}</small></div>
                <div><b>缺Material业务组</b><span>{{ businessConfirmationPackage.missingMaterialBusinessGroupCount }}</span><small>{{ businessConfirmationPackage.missingMaterialObjectCount }}个对象，不等于新建{{ businessConfirmationPackage.missingMaterialObjectCount }}个物料</small></div>
                <div><b>已有Material确认卡</b><span>{{ businessConfirmationPackage.formalMaterialMappingCardCount }}</span><small>已确认 {{ businessConfirmationPackage.confirmedMappingCount || 0 }}；其余继续待确认</small></div>
                <div><b>待确认单元</b><span>{{ businessConfirmationPackage.pendingDecisionUnitCount ?? businessConfirmationPackage.decisionUnitCount }}</span><small>已确认 {{ businessConfirmationPackage.confirmedMappingCount || 0 }} 个正式Mapping/Requirement关系</small></div>
                <div><b>多个现有候选</b><span>{{ materialDecisionCounts.MULTIPLE_EXISTING_CANDIDATES || 0 }}</span><small>唯一候选 {{ materialDecisionCounts.EXACT_EXISTING_MATERIAL_CANDIDATE || 0 }}</small></div>
                <div><b>资料不足组</b><span>{{ materialDecisionCounts.INSUFFICIENT_BUSINESS_FACTS || 0 }}</span><small>已证明无现有Material {{ materialDecisionCounts.NO_EXISTING_MATERIAL_CONFIRMED || 0 }}</small></div>
              </div>
              <p class="boundary-note"><b>数量边界：</b>{{ businessConfirmationPackage.quantityBoundary?.proof }} 正式Mapping回读 {{ businessConfirmationPackage.mappingReadbackCount || 0 }}，Requirement回读 {{ businessConfirmationPackage.requirementReadbackCount || 0 }}；本页业务写入 {{ businessConfirmationPackage.databaseBusinessWriteCount || 0 }}。</p>
              <details open><summary>查看{{ businessConfirmationPackage.missingMaterialBusinessGroupCount || 0 }}个待确认业务材料组</summary>
                <div class="table-wrap material-preview-table"><table><thead><tr><th>组／对象</th><th>业务语义</th><th>工艺条件</th><th>Quantity Fact族</th><th>Material判断</th><th>待确认问题</th></tr></thead><tbody><tr v-for="group in businessConfirmationPackage.groups || []" :key="group.groupNo"><td><b>{{ group.groupNo }} · {{ group.objectCount }}项</b><small>{{ group.sourceKeyRange }}</small></td><td>{{ group.product }} / {{ group.component }}<small>来源码：{{ group.sourceCode }}；角色：{{ group.potentialRequirementRoles?.join('、') }}</small></td><td>{{ group.processConfiguration }} / {{ group.paintProcess }}<small>封边 {{ group.edgeMethod || '未提供' }}；见光 {{ group.visibleCondition || '未提供' }}</small></td><td>{{ group.quantityFactFamily?.join('、') }}</td><td><b>{{ materialDecisionLabel(group.materialDecision) }}</b><small v-if="group.existingMaterialCandidates?.length">{{ group.existingMaterialCandidates.map(row => `${row.code} · ${row.name}`).join('；') }}</small><small>{{ businessConfirmationStatusLabel(group.currentStatus) }}</small></td><td>{{ group.question }}<small>责任：{{ group.requiredConfirmers?.join('＋') }}</small></td></tr></tbody></table></div>
              </details>
              <details open><summary>查看{{ businessConfirmationPackage.formalMaterialMappingCardCount || 0 }}张Material Mapping确认卡</summary>
                <div class="table-wrap material-preview-table"><table><thead><tr><th>Mapping／对象</th><th>正式Material／来源身份</th><th>正式Requirement／数量依据</th><th>乘数路径</th><th>损耗／角色</th><th>承接状态</th></tr></thead><tbody><tr v-for="card in businessConfirmationPackage.mappingCards || []" :key="`${card.mappingNo}-${card.designItem?.id}`"><td><b>{{ card.mappingNo }}</b><small>Mapping ID：{{ card.confirmedMapping?.id ?? '待确认' }}</small><small>{{ card.designItem?.objectNo }} · {{ card.designItem?.sourceKey }}</small><small>销售项目：{{ card.salesOrderItem?.quantity }} {{ card.salesOrderItem?.uom }}</small></td><td><b>Material{{ card.material?.id }}</b> · {{ card.material?.code }} · {{ card.material?.name }}<small>{{ card.specification || '规格沿用正式Material' }}；基础UOM {{ card.outputUom }}</small><small>ExternalIdentity{{ card.sourceExternalIdentity?.id ?? '待确认' }} · {{ card.sourceExternalIdentity?.externalId || '未回读' }}</small></td><td><b>EngineeringMaterialRequirement{{ card.formalRequirement?.id ?? '待形成' }}</b><small>{{ card.recommendedQuantitySource?.sourceFactCode }} · {{ card.recommendedQuantitySource?.name }}</small><small>{{ card.recommendedQuantitySource?.savedValue }} {{ card.recommendedQuantitySource?.uom }}；{{ card.recommendedQuantityBasis }}</small><details class="fact-option-list"><summary>查看全部已保存Fact选项</summary><small v-for="fact in card.savedDerivedFacts || []" :key="fact.sourceFactId">{{ fact.sourceFactCode }} · {{ fact.name }} = {{ fact.value }} {{ fact.uom || '无单位' }}</small></details></td><td>{{ card.multiplicationPath }}<small>Sales multiplier：{{ card.salesItemMultiplier }}</small></td><td>{{ card.itemRole }} / {{ card.requirementType }} / {{ card.supplyType }}<small>{{ card.currentStatus === 'CONFIRMED' ? '损耗率未维护(NULL)，grossQuantity保持NULL' : '损耗率：待确认（未代填0）' }}</small><small>Mapping版本：{{ card.mappingVersionSuggestion }}</small></td><td><b>{{ card.acceptanceStatusLabel || businessConfirmationStatusLabel(card.currentStatus) }}</b><small>{{ card.question }}</small><small>责任：{{ card.requiredConfirmers?.join('＋') }}</small></td></tr></tbody></table></div>
              </details>
              <details><summary>查看“组”UOM、五金/玻璃及Material/工艺边界</summary><p><b>{{ businessConfirmationPackage.uomQuestion?.question }}</b> {{ businessConfirmationPackage.uomQuestion?.objectNo }}（{{ businessConfirmationPackage.uomQuestion?.sourceKey }}）；当前正式UOM目录{{ businessConfirmationPackage.uomQuestion?.formalUomExists ? '已有' : '没有' }}“组”。{{ businessConfirmationPackage.uomQuestion?.boundary }}</p><p><b>五金/玻璃：</b>{{ businessConfirmationPackage.hardwareAndGlass?.decision }} 当前玻璃柜门对象 {{ businessConfirmationPackage.hardwareAndGlass?.glassNamedObjectCount || 0 }} 个；结构化五金 {{ businessConfirmationPackage.hardwareAndGlass?.structuredHardwareObjectCount || 0 }}，结构化玻璃 {{ businessConfirmationPackage.hardwareAndGlass?.structuredGlassObjectCount || 0 }}。</p><p><b>Material：</b>{{ businessConfirmationPackage.processBoundary?.material }} <b>Painting Process：</b>{{ businessConfirmationPackage.processBoundary?.paintingProcess }} <b>Operation：</b>{{ businessConfirmationPackage.processBoundary?.operation }} <b>Routing：</b>{{ businessConfirmationPackage.processBoundary?.routing }}</p></details>
            </section>
            <div class="table-wrap material-preview-table"><table><thead><tr><th>设计对象</th><th>来源</th><th>正式Material／来源身份</th><th>Mapping／Requirement</th><th>对象UOM</th><th>承接状态</th><th>缺失条件／来源码裁决</th></tr></thead><tbody><tr v-for="row in materialRequirementPreview.classifications || []" :key="row.designItemId"><td>{{ row.objectNo }}<small>{{ row.objectName }}</small></td><td>{{ row.sourceKey }}</td><td><b v-if="row.material">Material{{ row.material.id }}</b><span v-if="row.material"> · {{ row.material.code }} · {{ row.material.name }}</span><span v-else>未绑定</span><small v-if="row.sourceExternalIdentity">ExternalIdentity{{ row.sourceExternalIdentity.id }} · {{ row.sourceExternalIdentity.externalId }}</small></td><td><span>Mapping {{ row.confirmedMappingIds?.length ? row.confirmedMappingIds.join('、') : '待确认' }}</span><small>EngineeringMaterialRequirement {{ row.formalRequirementIds?.length ? row.formalRequirementIds.join('、') : '待形成' }}</small></td><td>{{ row.physicalUnit ? `${row.physicalUnit.code} · ${row.physicalUnit.name}` : '未绑定' }}</td><td><b>{{ row.acceptanceStatusLabel || row.statusLabel }}</b></td><td>{{ row.missingConditions?.join('；') || '无' }}<small>来源码：{{ row.sourceMaterialAnalysis?.sourceCode || '未提供' }}；{{ sourceMaterialAnalysisLabel(row.sourceMaterialAnalysis?.category) }}</small></td></tr></tbody></table></div>
            <details><summary>查看Mapping合同与67项来源码匹配边界</summary><p>Mapping合同：{{ materialRequirementPreview.mappingContract?.contractCode }}；存储：{{ materialRequirementPreview.mappingContract?.storageDecision }}；Schema变更：{{ materialRequirementPreview.mappingContract?.schemaChangeRequired ? '需要' : '不需要' }}。</p><p>67项分析：可复用但需确认 {{ sourceMaterialAnalysisCounts.UNIQUE_EXISTING_REQUIRES_CONFIRMATION || 0 }}；多候选 {{ sourceMaterialAnalysisCounts.AMBIGUOUS_MATERIAL || 0 }}；确无来源Material {{ sourceMaterialAnalysisCounts.NO_FORMAL_MATERIAL || 0 }}；非纯Material编码 {{ sourceMaterialAnalysisCounts.NON_PURE_MATERIAL_CODE || 0 }}。</p><p>{{ materialRequirementPreview.mappingContract?.uomPolicy }}</p></details>
          </template>
          <div v-else-if="materialRequirementPreviewLoading" class="notice pending"><strong>正在读取服务端R1承接事实…</strong></div>
          <div v-else class="empty-state"><strong>尚未取得材料需求承接预览</strong><span>请选择具有唯一正式订单关联的整单工程来源。</span></div>
        </section>
        <h3>已确认工程材料用量</h3>
        <div v-if="materialSummaryRows.length" class="table-wrap"><table><thead><tr><th>材料名称</th><th>规格</th><th>单位</th><th>已有净量</th><th>适用准备量</th><th>待完善事项</th><th>详情</th></tr></thead><tbody><tr v-for="row in materialSummaryRows" :key="row.key"><td>{{ row.name }}</td><td>{{ row.specification }}</td><td>{{ row.unit }}</td><td>{{ row.net }}</td><td>{{ row.gross }}</td><td>{{ row.missing }}</td><td><details><summary>来源明细</summary><p>{{ row.trace }}</p><p>正式材料编码：{{ row.code }}</p></details></td></tr></tbody></table></div>
        <div v-else class="empty-state"><strong>尚未形成正式材料清单</strong><span>当前核算没有具备正式材料身份与单位的材料需求；不显示为用量零，也不伪造材料行。</span></div>
        <h3>待补齐材料／规格／规则</h3>
        <div class="compact-blocker"><strong>其余对象尚未映射为正式材料需求</strong><p>服务端已回读 {{ businessConfirmationPackage.confirmedMappingCount || 0 }} 个正式Mapping/Requirement确认关系；仍有 {{ businessConfirmationPackage.pendingDecisionUnitCount ?? 0 }} 个业务确认单元待处理。已确认对象不再显示为缺Material或待形成Requirement；损耗、采购取整和库存抵扣仍按各对象正式事实分别判断。</p><details><summary>查看具体缺项</summary><ul><li>正式材料身份与规格</li><li>工程量到材料用量的适用关系</li><li>损耗／预留政策（与净用量分开）</li></ul></details></div>
        <h3>已有工程量预览（非正式材料清单）</h3>
        <div v-if="engineeringUsagePreviewRows.length" class="table-wrap"><table><thead><tr><th>工程量项目</th><th>来源范围</th><th>已有净量</th><th>单位</th><th>性质</th><th>详情</th></tr></thead><tbody><tr v-for="row in engineeringUsagePreviewRows" :key="row.key"><td>{{ row.project }}</td><td>{{ row.sheet }}</td><td>{{ row.net }}</td><td>{{ row.unit }}</td><td>非生产工程量预览</td><td><details><summary>来源明细</summary><p>{{ row.known }} 项已知，{{ row.missing }} 项缺失；{{ row.trace }}</p></details></td></tr></tbody></table></div>
        <div v-else class="empty-state"><strong>尚无可显示的工程量预览</strong><span>先保存已登记来源或执行正式订单核算。</span><router-link :to="businessPageLocation('results')" target="_blank" rel="noopener">查看施工与核算结果</router-link></div>
      </section>
      <details v-show="activeBusinessPage === 'materials'" class="card auxiliary-panel" data-section="bom-draft" data-contract-title="订单BOM草稿衔接"><summary>相关操作：订单BOM草稿</summary><div class="details-body"><header><div><h2>订单BOM草稿</h2><p>需要时再预览条件并明确确认；原服务与门禁保持不变。</p></div><strong :class="['pill', bomPreviewStateClass]">{{ bomPreviewState }}</strong></header>
        <div class="actions"><button type="button" class="secondary" data-action="preview-order-bom-draft" :disabled="activeCalculation?.status !== 'completed' || busy" @click="previewBom">{{ bomPreviewOperation.state === 'running' ? '正在预览…' : actionLabel('preview-order-bom-draft') }}</button><button type="button" :disabled="!bomPreview?.previewHash || busy || !materialRequirementPreview.bomGate?.canGenerate" :title="materialRequirementPreview.bomGate?.generationDisabledReason" @click="generateBom">{{ actionLabel('generate-order-bom-draft') }}</button><button v-if="bomPreview?.bomId" type="button" class="secondary" @click="openBom">{{ actionLabel('view-order-bom') }}</button></div>
        <div v-if="bomPreviewOperation.message" :class="['operation-feedback', bomPreviewOperation.state]" data-state="bom-preview-operation" :data-operation-state="bomPreviewOperation.state"><strong>{{ bomPreviewOperation.title }}</strong><p>{{ bomPreviewOperation.message }}</p></div>
        <div v-if="bomBlocker || (activeCalculation?.status === 'completed' && !activeCalculation.materialRequirements?.length)" class="compact-blocker" data-state="bom-blocked" data-blocker-code="MATERIAL_REQUIREMENT_REQUIRED"><strong>材料清单待完善</strong><p>{{ bomBlocker || '当前核算没有正式材料需求，不能生成空BOM草稿。' }}</p><details><summary>查看具体缺项</summary><ul><li>正式订单关联：{{ stableOrderLinkLabel(selectedOrder?.stableOrderLinkStatus) }}</li><li>材料需求依据：当前记录没有材料用量输出</li><li>覆盖范围：当前来源或订单的已核对范围，不冒充完整BOM</li></ul></details></div>
        <div v-if="bomPreview" class="table-wrap"><table><thead><tr><th>行</th><th>物料</th><th>数量 / UOM</th><th>角色 / 类型 / 供给</th><th>损耗</th><th>来源需求</th></tr></thead><tbody><tr v-for="row in bomPreview.rows" :key="row.lineNo"><td>{{ row.lineNo }}</td><td>{{ row.materialCode }} · {{ row.materialName }}</td><td>{{ row.quantity }} {{ row.uomCode }}</td><td>{{ row.itemRole }} / {{ row.requirementType }} / {{ row.supplyType }}</td><td>{{ row.scrapRateStatus === 'maintained' ? row.scrapRate : '未知（空）' }}</td><td>{{ row.sourceRequirementIds.join('、') }}</td></tr></tbody></table></div>
        <p class="boundary">边界：{{ materialRequirementPreview.bomGate?.generationDisabledReason || '未取得开发验证草稿边界。' }} 不发布BOM，不创建计划、工单、采购、库存或财务事实。</p>
      </div></details>
      </div>
    </template>
  </main>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { clearDynamicPageTitle, setDynamicPageTitle } from '@/meta/runtime/pageTitleManager'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pdeApi } from '@/api/pde.js'
import { validateWorkbookCatalog } from '@/meta/runtime/sourceFormatMaintenanceForm.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import SemiFinishedConfigurationPreview from '@/meta/components/SemiFinishedConfigurationPreview.vue'
import EngineeringCalculationBatchPanel from '@/meta/components/EngineeringCalculationBatchPanel.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import EngineeringWorkloadPurposeReview from './components/EngineeringWorkloadPurposeReview.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { foundationSubviewLocation, getFoundationCanonicalModule, resolveFoundationPageState } from '@/meta/master-data/foundationEntryUnificationRegistry.js'
import { pceBusinessActionLabel } from '@/meta/runtime/pceBusinessActionRegistry.js'
import { formatBusinessStatus } from '@/meta/runtime/businessDisplayValueFormatter.js'
import { loadPermissionProfile, resolvePermissionFact } from '@/meta/runtime/permissionProfileRuntime.js'
import { engineeringInstanceScopeLabel, summarizeFormalValidation } from '@/meta/runtime/formalContinuationPresentation.js'
import { buildFormalSummaryReturnContext, resolveFormalSummaryReturnTarget } from '@/meta/runtime/formalSummaryNavigation.js'
import { calculationInputLines, calculationTraceRows, formalSavedState, readSelectedCalculationDetail, savedPageContextForSelection } from '@/meta/runtime/formalCalculationReadbackPresentation.js'

const route = useRoute(), router = useRouter()
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const calculationIdentity = getFoundationCanonicalModule('engineering-calculation')
const RULE_VIEW_PERMISSION = 'production.engineering.rule.view'
const CALCULATION_VIEW_PERMISSION = 'production.engineering.calculation.view'
const configurationSubview = computed(() => route.query.subview === 'semi-finished-structure')
const permissionProfile = ref(null)
const accessMode = ref('loading')
const permissionAllowed = code => resolvePermissionFact(permissionProfile.value, code).executable === true
const calculationAccessAllowed = computed(() => accessMode.value === 'calculation' && permissionAllowed(CALCULATION_VIEW_PERMISSION))
const ruleOnlyEntryMode = computed(() => accessMode.value === 'rules-only' && permissionAllowed(RULE_VIEW_PERMISSION))
const readiness = ref({}), calculations = ref([]), activeCalculation = ref(null), methodTrial = ref(null), bomPreview = ref(null), bomBlocker = ref('')
const materialRequirementHandoff = ref({}), materialRequirementPreviewLoading = ref(false), materialRequirementPreviewError = ref('')
const calculationDetailLoading = ref(false), calculationDetailError = ref('')
let calculationDetailSequence = 0
const formalContinuation = ref({}), formalValidation = ref({ ready: false, blockers: [] }), selectedBaselineId = ref(null), formalBusy = ref(false)
const selectedPredecessorCalculationId = ref(null), mainContinuationPreview = ref(null), mainContinuationError = ref(''), mainContinuationReadback = ref(null)
let mainContinuationRequestSequence = 0
let mainContinuationPreviewScope = ''
const formalSummaryReturnContext = ref(null)
const conditionPreflight = ref({ blockers: [] })
const conditionPreflightOperation = reactive({ state: 'idle', title: '', message: '', attempt: 0 })
const selectedConditionSalesOrderItemId = ref(null)
const validation = ref({ ready: false, blockers: [] })
const validationOperation = reactive({ state: 'idle', title: '', message: '', attempt: 0 })
const methodTrialOperation = reactive({ state: 'idle', title: '', message: '', attempt: 0 })
const bomPreviewOperation = reactive({ state: 'idle', title: '', message: '', attempt: 0 })
const selection = reactive({ salesOrderItemId: null, ruleIds: [], candidateRuleIds: [] })
const selectedWorkbookSourceRecordId = ref(''), workbookSources = ref([]), workbookSourcesLoading = ref(false), workbookSourcesError = ref('')
const selectedWorkbookSource = computed(() => workbookSources.value.find(row => String(row.id) === selectedWorkbookSourceRecordId.value))
const workbookSourceIntake = ref({})
const workbookObjectWriteAllowed = computed(() => !selectedWorkbookSourceRecordId.value || workbookSourceIntake.value.sourceIntakeAllowed === true)
const businessPages = Object.freeze([
  { key: 'input', label: '工程数据录入', description: '录入、检查并保存当前产品的工程原始数据。' },
  { key: 'results', label: '施工单／整单核算结果', description: '查看工位执行字段、历史修订和整单核算结果。' },
  { key: 'scheduling', label: '工程作业量汇总', description: '按来源编码查看工程事实、来源贡献及正式规则转换状态；本页不是APS输入。' },
  { key: 'materials', label: '材料汇总', description: '查看正式材料净量、准备量与待完善事项。' },
])
const resolveBusinessPage = value => businessPages.some(page => page.key === value) ? value : 'input'
const activeBusinessPage = ref(resolveBusinessPage(route.query.page)), workshopView = ref('paint')
const activePageDefinition = computed(() => businessPages.find(page => page.key === activeBusinessPage.value) || businessPages[0])
  const draftRows = ref([]), drafts = ref([]), unboundDrafts = ref([]), activeDraftId = ref(''), draftReason = ref(''), savingDraft = ref(false), savingRegisteredSource = ref(false), importPreview = ref(null)
const responsibilityRoleDefinitions = Object.freeze([
  { key: 'salesperson', label: '业务员' },
  { key: 'designer', label: '设计师' },
  { key: 'breakdownOwner', label: '拆单员' },
])
const draftAssignments = reactive({ salesperson: { employeeId: '', snapshot: null }, designer: { employeeId: '', snapshot: null }, breakdownOwner: { employeeId: '', snapshot: null } })
const draftPackaging = reactive({ id: '', name: '', statusLabel: '未维护' })
const confirmedResponsibilityFacts = ref({})
const businessOrderReference = ref({})
const lastSavedDraftJson = ref('[]')
const loading = ref(false), busy = ref(false), loadError = ref(''), auxiliaryReadNotice = ref(''), writeCount = ref(0)
const initialReadFailure = ref(null)
const openMissingRow = ref('')
const comparisonView = ref('summary')
const sourceTrialOrders = computed(() => unboundDrafts.value.map(draft => {
  const first = draft.rows?.[0] || {}
  const count = draft.rows?.length || 0
  const orderReference = draft.businessOrderReference || {}
  return {
    isSourceTrial: true, salesOrderItemId: -1000000 - Number(draft.id), sourceRecordId: draft.id,
    orderEngineeringInstanceId: null, orderEngineeringInstanceNo: '未形成订单工程实例',
    orderNo: draft.linkedOrders?.[0]?.orderNo || orderReference.sourceOrderNo || (count === 71 ? '真实来源批量试录' : `真实来源试录 #${draft.id}`), lineNo: '-',
    sourceOrderNo: orderReference.sourceOrderNo || '', linkedOrders: draft.linkedOrders || [],
    linkedDesignItemCount: (draft.linkedOrders || []).reduce((sum, row) => sum + Number(row.designItemCount || 0), 0),
    customerName: orderReference.customerName || '订单／客户关系待确认', projectName: orderReference.projectName || '', sourceCaseName: first.product || first.component || draft.sourceName,
    installationArea: orderReference.projectName || first.space || '来源空间待核对', sourceFile: '工程拆单及订单排产数据核算方式.xlsx',
    sourceSheet: first.sourceSheet || '来源Sheet待核对', sourceRow: count === 1 ? first.sourceRow : `${first.sourceRow || '-'}等${count}`,
    sourceNo: draft.sourceNo, sourceVersion: draft.sourceVersion, sourceScopeKey: draft.sourceScopeKey,
    sourceMaterialCode: first.materialProcessCode || '', materialCode: first.materialProcessCode || '',
    materialName: first.component || '', customerProductName: first.product || '',
    orderQuantity: count, orderUomCode: count === 1 ? first.unit : '行',
    productCategoryId: first.productCategoryId || null, stableOrderLinkStatus: draft.linkedOrders?.length ? 'DESIGN_SOURCE_LINKED' : orderReference.stableOrderLinkStatus || 'NO_STABLE_KEY',
    coverageStatement: count === 71 ? '登记来源71行：房门8行＋三合一63行；缺项逐行保留。' : `独立来源草稿${count}行；订单归属与办理状态分别显示。`,
    statusLabel: '产品设计输入核算', canonicalInputs: [], currentDesignInputs: draft.currentDesignInputs || [], draft,
  }
}))
const formalOrders = computed(() => readiness.value.orders || [])
const orders = computed(() => [...formalOrders.value, ...sourceTrialOrders.value])
const rules = computed(() => (readiness.value.formalRules || []).filter(row => row.status === 'released'))
const candidateMethods = computed(() => readiness.value.candidateMethods || [])
const selectedOrder = computed(() => orders.value.find(row => row.salesOrderItemId === selection.salesOrderItemId))
const savedRecordSelected = computed(() => Boolean(activeCalculation.value?.id))
const savedContext = computed(() => savedPageContextForSelection(activeCalculation.value, selectedOrder.value))
const savedNativeContext = computed(() => savedContext.value?.rows?.length && savedContext.value.rows.every(row => row.sourceType === 'NATIVE_DESIGN_REVISION'))
const displayedSourceVersion = computed(() => savedRecordSelected.value ? (savedContext.value?.sourceVersion || '冻结版本待读取') : activeDraft.value?.sourceVersion || selectedOrder.value?.sourceVersion || '未建立')
const engineeringWorkloadSourceObjects = computed(() => {
  const order = selectedOrder.value
  if (!order || order.salesOrderItemId == null) return []
  const inCurrentLine = rows => (Array.isArray(rows) ? rows : []).filter(row => row.salesOrderItemId != null
    && String(row.salesOrderItemId) === String(order.salesOrderItemId))
  const direct = inCurrentLine(order.currentDesignInputs)
  if (order.sourceRecordId == null || !String(order.sourceRecordId).trim() || !String(order.sourceVersion || '').trim()) return direct
  const contexts = unboundDrafts.value.filter(draft => draft.id != null && draft.sourceVersion != null
    && String(draft.id) === String(order.sourceRecordId) && String(draft.sourceVersion) === String(order.sourceVersion))
  return contexts.length === 1 && Array.isArray(contexts[0].currentDesignInputs)
    ? inCurrentLine(contexts[0].currentDesignInputs) : direct
})
function linkedWholeOrderSummary(orderNo) {
  const normalizedOrderNo = String(orderNo || '').trim()
  if (!normalizedOrderNo) return null
  const matches = sourceTrialOrders.value.filter(summary => (summary.linkedOrders || []).some(linked => String(linked.orderNo || '').trim() === normalizedOrderNo))
  return matches.length === 1 ? matches[0] : null
}
const formalSummaryReturnTarget = computed(() => resolveFormalSummaryReturnTarget({
  context: formalSummaryReturnContext.value,
  routeQuery: route.query,
  summaries: sourceTrialOrders.value,
  selectedLine: selectedOrder.value?.isSourceTrial ? null : selectedOrder.value,
}))
const formalContinuationLine = computed(() => (formalContinuation.value.lines || []).find(row => row.salesOrderItemId === selectedOrder.value?.salesOrderItemId))
const conditionLinesBySalesOrderItemId = computed(() => new Map(
  (conditionPreflight.value.lines || []).map(row => [Number(row.salesOrderItemId), row]),
))
const selectedLineCondition = computed(() => conditionLinesBySalesOrderItemId.value.get(Number(selectedConditionSalesOrderItemId.value)) || null)
const lineConditionPermissions = computed(() => [
  ['production.engineering.calculation.view', '查看工程核算'],
  ['production.engineering.source.maintain', '确认工程来源'],
  ['production.engineering.order.maintain', '形成订单工程实例'],
  ['production.engineering.rule.release', '发布核算规则'],
  ['production.engineering.calculation.execute', '执行并保存核算'],
].map(([code, label]) => ({ code, label, ...(conditionPreflight.value.permissions?.[code] || {}) })))
const formalBaselines = computed(() => (formalContinuation.value.baselines || []).filter(row => row.status === 'confirmed'))
const mainContinuationFacts = computed(() => formalContinuationLine.value?.calculationContinuation || null)
const mainContinuationActions = computed(() => (mainContinuationPreview.value?.availableActions || mainContinuationFacts.value?.availableActions || []).filter(row => ['preview', 'execute'].includes(row.actionCode)))
const mainContinuationCanExecute = computed(() => mainContinuationPreview.value?.ready === true && Boolean(mainContinuationPreview.value.expectedContextHash && mainContinuationPreview.value.continuationBasisHash) && mainContinuationPreviewScope === mainContinuationScopeKey() && mainContinuationActions.value.some(action => action.actionCode === 'execute' && action.allowed === true))
const formalContinuationObjectCount = computed(() => (formalContinuation.value.lines || []).reduce((sum, row) => sum + Number(row.designObjectCount || 0), 0))
const formalContinuationInstanceCount = computed(() => (formalContinuation.value.lines || []).filter(row => row.orderEngineeringInstanceId).length)
const formalSummaryLines = computed(() => (formalContinuation.value.lines || []).map(row => ({
  ...row,
  ...(conditionLinesBySalesOrderItemId.value.get(Number(row.salesOrderItemId)) || {}),
})))
const formalValidationPresentation = computed(() => summarizeFormalValidation(conditionPreflightOperation.state, formalSummaryLines.value))
const formalValidationResultPositionTotal = computed(() => formalValidationPresentation.value.resultPositionTotal)
const formalValidationSummary = computed(() => formalValidationPresentation.value.label)
const formalOrderSavedState = computed(() => formalSavedState(
  conditionPreflight.value.formalCalculationState || formalContinuation.value.formalCalculationState,
  conditionPreflightOperation.state === 'failed',
))
const formalSelectedSavedState = computed(() => selectedOrder.value?.isSourceTrial ? formalOrderSavedState.value : formalSavedState(
  conditionLinesBySalesOrderItemId.value.get(Number(selectedOrder.value?.salesOrderItemId))?.formalCalculationState || formalContinuationLine.value?.formalCalculationState,
  conditionPreflightOperation.state === 'failed',
))
const orderEngineeringInstanceScopeLabel = computed(() => {
  if (!selectedOrder.value) return ''
  return engineeringInstanceScopeLabel({
    sourceScope: selectedOrder.value.isSourceTrial,
    selectedInstanceNo: selectedOrder.value.orderEngineeringInstanceNo || formalContinuationLine.value?.orderEngineeringInstanceNo,
    instanceCount: formalContinuationInstanceCount.value,
    lineCount: formalContinuation.value.lines?.length || 0,
    factsLoaded: Boolean(formalContinuation.value.lines?.length),
  })
})
const confirmedBaselineSummary = computed(() => formalBaselines.value.length
  ? formalBaselines.value.map(row => `${row.baselineNo} · ${row.itemCount}项 · ${row.statusLabel}`).join('；')
  : '尚无已确认基线')
const sourceOrderAssociation = computed(() => {
  const linked = selectedOrder.value?.linkedOrders || []
  if (linked.length === 1) {
    const lines = formalContinuation.value.lines || []
    const sourceConfirmed = lines.length > 0 && lines.every(row => row.sourceStatus === 'confirmed')
    const instancesConfirmed = lines.length > 0 && lines.every(row => row.orderEngineeringInstanceId && ['source_confirmed', 'calculated'].includes(row.instanceStatus))
    return {
      title: `当前正式办理：订单 ${linked[0].orderNo || selectedOrder.value?.orderNo}、来源与实例状态已按服务端事实回读。`,
      detail: `当前${selectedOrder.value?.linkedDesignItemCount || 0}个设计对象稳定归属该订单；工程来源${sourceConfirmed ? '已确认' : '尚未全部确认'}，${formalContinuationInstanceCount.value}/${lines.length || 0}个订单行实例已建立${instancesConfirmed ? '并确认采用来源' : ''}。${formalOrderSavedState.value.label}。`,
    }
  }
  if (linked.length > 1) return { title: '当前设计对象关联到多个正式订单。', detail: '页面保留真实关联，不自动选择订单或形成办理上下文。' }
  return { title: '尚未取得稳定的正式订单关联。', detail: '当前仅显示来源设计事实，不猜测订单、实例或正式核算状态。' }
})
const formalContinuationBlockers = computed(() => {
  if (conditionPreflightOperation.state === 'failed') return []
  if (conditionPreflight.value.blockers) return conditionPreflight.value.blockers
  const rows = []
  if ((formalContinuation.value.lines || []).some(row => row.sourceStatus !== 'confirmed')) rows.push({ code: 'SOURCE_RECORD_NOT_CONFIRMED', reason: '工程来源仍为草稿，尚未确认。' })
  if (!formalContinuationInstanceCount.value) rows.push({ code: 'ORDER_ENGINEERING_INSTANCE_NOT_CREATED', reason: '4个订单行均未形成订单工程实例。' })
  if ((formalContinuation.value.formalRulePackages?.length || 0) < (formalContinuation.value.requiredRulePackages?.length || 2)) rows.push({ code: 'FORMAL_RULE_PACKAGES_INCOMPLETE', reason: `正式规则包仅${formalContinuation.value.formalRulePackages?.length || 0}/${formalContinuation.value.requiredRulePackages?.length || 2}已发布。` })
  return rows
})
const formalExecutionReason = computed(() => {
  if (!selectedOrder.value) return '请先选择订单或工程来源。'
  if (selectedOrder.value.isSourceTrial) {
    const blockers = conditionPreflight.value.blockers?.length ? conditionPreflight.value.blockers : formalContinuationBlockers.value
    return blockers.length
      ? `正式执行保持不可用：${blockers.map(row => row.reason).join('；')}`
      : '预检只说明可进入订单行级完整校验；不会直接开放正式执行保存。'
  }
  if (!formalContinuationLine.value?.orderEngineeringInstanceId) return '当前订单行尚未形成实例；正式执行保持不可用。'
  if (!formalValidation.value.ready) return '请在上方完成当前订单行的实例、基线与正式规则完整校验；预检不能代替该校验。'
  return '完整校验已通过；是否执行仍由服务端执行权限与点击确认共同控制。'
})
const designSourceOwned = computed(() => Boolean(
  selectedOrder.value?.linkedDesignItemCount
  || selectedOrder.value?.designItemCount
  || selectedOrder.value?.currentDesignInputs?.length,
))
const designInputRows = computed(() => (savedRecordSelected.value ? savedContext.value?.rows || [] : selectedOrder.value?.currentDesignInputs || []).map(row => {
  if (row.savedFrozen) return { ...row, saveReadinessSummary: '已保存记录输入；当前准入另见只读预检', orderLineNo: row.orderLineLabel, specification: row.materialStatusLabel, processConfiguration: row.processConfigurationLabel }
  const lineCondition = conditionLinesBySalesOrderItemId.value.get(Number(row.salesOrderItemId))
  let saveReadinessSummary = lineCondition?.saveReadinessSummary || '本行条件尚未读取'
  if (conditionPreflightOperation.state === 'running') saveReadinessSummary = '正在读取本行条件…'
  if (conditionPreflightOperation.state === 'failed') saveReadinessSummary = conditionPreflightOperation.title || '读取失败，状态未知'
  return {
    ...row,
    calculationStatusLabel: row.calculationReady ? '核算输入完整' : '存在缺项',
    orderLineNo: row.orderLineNo || row.salesOrderLineNo || '',
    saveReadinessSummary,
    specification: row.materialSpecification || row.specification || '',
    processConfiguration: row.processConfigurationLabel || row.processConfigurationCode || '',
    materialProcess: row.materialProcessName || row.materialProcessCode || '',
  }
}))
const designInputFilterSchema = Object.freeze([
  { field: 'orderLineNo', label: '订单行', filterType: 'text' },
  { field: 'productCategoryName', label: '产品分类', filterType: 'text' },
  { field: 'space', label: '空间', filterType: 'text' },
  { field: 'materialName', label: '物料名称', filterType: 'text' },
  { field: 'calculationStatusLabel', label: '输入状态', filterType: 'select', options: [{ label: '核算输入完整', value: '核算输入完整' }, { label: '存在缺项', value: '存在缺项' }] },
])
const designInputListContract = createPceEnterpriseListContract({ pageCode: 'pde-engineering-calculation-input-detail', pageType: 'list', title: '当前设计逐项工程输入', moduleCode: 'PDE' })
const {
  selectedRows: selectedDesignInputRows,
  quickSearch: designInputQuickSearch,
  appliedSearch: designInputAppliedSearch,
  advancedVisible: designInputAdvancedVisible,
  filters: designInputFilters,
  tableRef: designInputTableRef,
  activeFilterCount: designInputActiveFilterCount,
  sortText: designInputSortText,
  filteredRows: filteredDesignInputRows,
  clearFilters: clearDesignInputFilters,
  clearSort: clearDesignInputSort,
  clearSelection: clearDesignInputSelection,
  handleSort: handleDesignInputSort,
  exportCurrent: exportCurrentDesignInputs,
} = usePceEnterpriseListRuntime({
  rows: designInputRows,
  filterSchema: designInputFilterSchema,
  pageCode: 'pde-engineering-calculation-input-detail',
  searchFields: ['designItemNo', 'itemName', 'orderLineNo', 'saveReadinessSummary', 'productCategoryName', 'space', 'installationPosition', 'materialCode', 'materialName', 'specification', 'edgeMethod', 'visibleCondition', 'processConfiguration', 'paintProcess', 'colorVersion', 'sourceSheet', 'sourceKey', 'calculationStatusLabel'],
  exportFileName: '当前设计逐项工程输入.csv',
  exportColumns: [
    { field: 'designItemNo', label: '设计对象编号' }, { field: 'itemName', label: '对象名称' }, { field: 'orderLineNo', label: '订单行' },
    { field: 'saveReadinessSummary', label: '核算保存前需完成' },
    { field: 'productCategoryName', label: '产品分类' }, { field: 'space', label: '空间' }, { field: 'installationPosition', label: '安装位置' },
    { field: 'physicalQuantity', label: '数量' }, { field: 'physicalUomName', label: '单位' }, { field: 'materialCode', label: '材料编码' },
    { field: 'materialName', label: '物料名称' }, { field: 'specification', label: '规格' }, { field: 'edgeMethod', label: '封边' },
    { field: 'visibleCondition', label: '见光' }, { field: 'processConfiguration', label: '工艺配置' }, { field: 'paintProcess', label: '油漆工艺' },
    { field: 'colorVersion', label: '颜色/版本' }, { field: 'revision', label: '设计修订' }, { field: 'sourceSheet', label: '来源工作表' },
    { field: 'sourceRow', label: '来源行' }, { field: 'calculationStatusLabel', label: '输入状态' },
  ],
})
function updateDesignInputFilter(field, value) { designInputFilters[field] = value }
const currentBaselineRelationship = computed(() => savedRecordSelected.value ? `${savedContext.value?.baselineNo || '冻结基线待读取'}；仅使用所选记录冻结设计修订，不使用最新候选替代。` : activeDraft.value?.currentInputCalculation?.baselineRelationship?.statusLabel
  || activeDraft.value?.baselineRelationship?.statusLabel
  || '当前输入按产品设计实时读取；尚未取得可显示的已保存基线比较关系。')
const visibleCalculations = computed(() => selectedOrder.value && !selectedOrder.value.isSourceTrial
  ? calculations.value.filter(row => Number(row.salesOrderItemId) === Number(selectedOrder.value.salesOrderItemId))
  : [])
const activeDraft = computed(() => drafts.value.find(row => String(row.id) === String(activeDraftId.value)) || null)
const requestedEngineeringVersion = computed(() => String(route.query.engineeringVersion || ''))
const latestEngineeringVersion = computed(() => activeDraft.value?.sourceVersion || selectedOrder.value?.sourceVersion || '')
const versionStale = computed(() => !!requestedEngineeringVersion.value && !!latestEngineeringVersion.value && requestedEngineeringVersion.value !== latestEngineeringVersion.value)
const draftStateJson = () => JSON.stringify({ rows: draftRows.value, assignments: draftAssignments, packaging: draftPackaging, confirmedResponsibilityFacts: confirmedResponsibilityFacts.value, businessOrderReference: businessOrderReference.value })
const draftDirty = computed(() => draftStateJson() !== lastSavedDraftJson.value)
const selectedMaterial = computed(() => (readiness.value.materialIdentity || []).find(row => row.sourceCode === selectedOrder.value?.sourceMaterialCode) || null)
const selectedMaterialUom = computed(() => (readiness.value.materialBasePurchaseUom || []).find(row => row.sourceMaterial === selectedMaterial.value?.sourceMaterial) || null)
const engineeringInputOptions = computed(() => readiness.value.engineeringInputOptions || {})
const historicalSourceCalculationRows = computed(() => activeDraft.value?.sourceCalculation?.rows || [])
const sourceCalculationRows = computed(() => activeDraft.value?.currentInputCalculation?.rows || historicalSourceCalculationRows.value)
const summarizeResultRows = rows => ({
    total: rows.length,
    consistent: rows.filter(row => row.comparisonClassification === 'INDEPENDENT_COMPARISON_CONSISTENT' || row.statusLabel === '对账一致').length,
    noIndependentComparison: rows.filter(row => row.comparisonClassification === 'NO_INDEPENDENT_COMPARISON' || row.statusLabel === '已计算，缺独立对照').length,
    confirmedDesignChangeDifferences: rows.filter(row => row.comparisonClassification === 'SAME_CONFIRMED_DESIGN_CHANGE').length,
    unexplainedDifferences: rows.filter(row => row.comparisonClassification === 'NEW_UNEXPLAINED_DIFFERENCE' || row.statusLabel === '发现差异').length,
    numeric: rows.filter(row => row.state === 'calculated' && row.value != null).length,
    missing: rows.filter(row => row.state === 'missing').length,
    notApplicable: rows.filter(row => row.state === 'not_applicable').length,
    errors: rows.filter(row => row.state === 'error' || row.comparisonClassification === 'NEW_UNEXPLAINED_DIFFERENCE' || row.statusLabel === '发现差异').length,
  })
const sourceResultSummary = computed(() => activeDraft.value?.currentInputCalculation?.comparisonSummary
  || summarizeResultRows(sourceCalculationRows.value))
const historicalSourceResultSummary = computed(() => summarizeResultRows(historicalSourceCalculationRows.value))
const historicalAcceptanceRegression = computed(() => activeDraft.value?.currentInputCalculation?.historicalAcceptanceRegression || {})
const focusedComparisonRows = computed(() => sourceCalculationRows.value.filter(row => {
  if (comparisonView.value === 'confirmed-design-changes') return row.comparisonClassification === 'SAME_CONFIRMED_DESIGN_CHANGE'
  if (comparisonView.value === 'differences') return row.comparisonClassification === 'NEW_UNEXPLAINED_DIFFERENCE'
  return row.comparisonClassification === 'NO_INDEPENDENT_COMPARISON' || row.statusLabel === '已计算，缺独立对照'
}))
const differenceExplanation = computed(() => {
  if (!['confirmed-design-changes', 'differences'].includes(comparisonView.value)) return ''
  const classification = comparisonView.value === 'confirmed-design-changes'
    ? 'SAME_CONFIRMED_DESIGN_CHANGE'
    : 'NEW_UNEXPLAINED_DIFFERENCE'
  const row = sourceCalculationRows.value.find(item => item.comparisonClassification === classification)
  if (!row) return ''
  const inputs = (row.inputs || []).map(item => `${item.name || item.key}=${item.value}${item.unit ? ` ${item.unit}` : ''}`).join('；')
  const accepted = row.historicalAcceptance
    ? `该行已与${row.historicalAcceptance.acceptedAt || '历史'}正式验收依据逐项一致，裁决为“已确认设计变更差异”；${row.historicalAcceptance.designChangeBasis || ''}`
    : '该行未匹配历史正式验收依据，仍属于异常差异。'
  return `${row.sheet}第${row.row}行“${row.project}”：当前结果 ${row.value} ${row.unit || ''}，旧独立对照 ${row.expected ?? '无'}，差值 ${row.difference ?? '不可比较'}。当前值由${inputs || row.expression || '当前产品设计输入'}形成；旧对照值只用于比较，没有反向作为本次输入。${accepted}`
})
const acceptanceComparisonRows = computed(() => sourceCalculationRows.value
  .filter(row => (row.sheet === '房门单' && Number(row.row) === 11) || (row.sheet === '三合一生产单' && Number(row.row) === 7))
  .map(row => ({ ...row, sourceLabel: `${row.sheet}第${row.row}行`, softwareValue: row.value ?? '未形成', independentValue: row.expected ?? '无独立对照', differenceLabel: row.difference ?? '不可比较' })))
const productionPlan = computed(() => selectedOrder.value?.isSourceTrial ? {
  statusLabel: '当前来源预览未形成生产计划上下文',
  detail: `${selectedOrder.value?.orderNo || '正式订单'}已存在，但来源尚未确认且订单工程实例未形成；不读取或猜测生产计划。`,
  rows: [],
} : readiness.value.productionPlanByOrder?.[String(selection.salesOrderItemId)] || { statusLabel: selectedOrder.value ? '生产计划读取中' : '请先选择订单', rows: [] })
const overallLabel = computed(() => {
  if (ruleOnlyEntryMode.value) return '规则入口可用 · 核算数据保持隔离'
  if (loadError.value) return '读取失败'
  if (activeCalculation.value?.status === 'completed' && !activeCalculation.value.materialRequirements?.length) return '尺寸已完成 · 物料/BOM受阻'
  if (validation.value.ready) return '尺寸核算就绪'
  return readiness.value.overallStatusLabel || { PASS: '已就绪', BLOCKED: '存在缺项', FAILED: '读取失败' }[readiness.value.overallStatus] || '待选择'
})
const currentBusinessStatus = computed(() => savedRecordSelected.value ? calculationStatusLabel(activeCalculation.value) : selectedOrder.value?.isSourceTrial && sourceCalculationRows.value.length
  ? `产品设计已接入核算 · ${sourceResultSummary.value.numeric}项有效 / ${sourceResultSummary.value.confirmedDesignChangeDifferences}项已确认设计变更差异 / ${sourceResultSummary.value.unexplainedDifferences}项异常 / ${sourceResultSummary.value.missing}项缺失；原基线独立保留`
  : activeDraft.value ? (activeDraft.value.calculationRequired
      ? (sourceCalculationRows.value.length
          ? (sourceResultSummary.value.missing ? '工程输入已变更 · 预览仍有缺项' : '工程输入已变更 · 预览已重算')
          : '工程输入已变更 · 待重新核算')
      : '业务元数据已更新 · 原计算输入未变')
  : selectedOrder.value?.isSourceTrial ? '真实来源试录待保存' : calculationStatusLabel(activeCalculation.value || { status: selectedOrder.value?.orderEngineeringInstanceStatus }))
const currentScopeLabel = computed(() => savedRecordSelected.value ? `订单行ID ${savedContext.value?.salesOrderItemId || '待读取'} / 冻结设计${savedContext.value?.rows?.length ?? '待读取'}项` : selectedOrder.value?.isSourceTrial
  ? `整单来源 ${draftRows.value.length || selectedOrder.value?.draft?.rows?.length || 0} 行（房门8＋三合一63）`
  : selectedOrder.value ? `销售订单第${selectedOrder.value.lineNo}行 / 当前设计${selectedOrder.value.designItemCount || 0}项` : '未选择')
const validationState = computed(() => {
  if (validationOperation.state === 'running') return '正在校验'
  if (validation.value.ready) return '尺寸校验通过'
  if (validationOperation.state === 'failed') return '校验失败'
  if (validation.value.blockers?.length) return '校验受阻'
  return '待校验'
})
const bomPreviewState = computed(() => {
  if (bomPreviewOperation.state === 'running') return '正在预览'
  if (bomPreviewOperation.state === 'blocked') return '预览受阻'
  if (bomPreviewOperation.state === 'failed') return '预览失败'
  if (bomPreviewOperation.state === 'completed') return bomPreview.value?.alreadyGenerated ? '草稿已存在' : '预览完成'
  return '待预览'
})
const methodTrialState = computed(() => {
  if (methodTrialOperation.state === 'running') return '试算中'
  if (methodTrialOperation.state === 'failed') return '试算失败'
  if (methodTrial.value?.trialStatus === 'PASS') return '对账一致'
  if (methodTrial.value?.trialStatus === 'FAIL') return '存在差异'
  return '待试算'
})
const bomPreviewStateClass = computed(() => ['completed'].includes(bomPreviewOperation.state) ? 'pass' : 'pending')
const materialRequirementPreview = computed(() => materialRequirementHandoff.value?.materialRequirementPreview || {})
const materialPreviewCounts = computed(() => materialRequirementPreview.value.classificationCounts || {})
const materialPreviewClassificationTotal = computed(() => Object.values(materialPreviewCounts.value).reduce((sum, value) => sum + Number(value || 0), 0))
const sourceMaterialAnalysisCounts = computed(() => materialRequirementPreview.value.metrics?.sourceMaterialAnalysisCounts || {})
const businessConfirmationPackage = computed(() => materialRequirementPreview.value.businessConfirmationPackage || {})
const materialDecisionCounts = computed(() => businessConfirmationPackage.value.materialDecisionCounts || {})
function sourceMaterialAnalysisLabel(category) {
  return {
    FORMAL_MATERIAL_BOUND: '已有正式Material引用',
    UNIQUE_EXISTING_REQUIRES_CONFIRMATION: '存在唯一精确编码候选，仍需人工确认绑定',
    AMBIGUOUS_MATERIAL: '存在多个精确编码候选',
    NO_FORMAL_MATERIAL: '来源未提供可核对Material',
    NON_PURE_MATERIAL_CODE: '来源为材料＋工艺组合语义，不作为正式Material Code',
  }[category] || '未形成正式Material匹配结论'
}
function materialDecisionLabel(status) {
  return {
    EXACT_EXISTING_MATERIAL_CANDIDATE: '存在唯一正式Material候选（仍需业务确认）',
    MULTIPLE_EXISTING_CANDIDATES: '存在多个正式Material候选',
    NO_EXISTING_MATERIAL_CONFIRMED: '已证明没有现有Material',
    INSUFFICIENT_BUSINESS_FACTS: '业务资料不足，不能判断Material',
  }[status] || '尚未形成Material身份结论'
}
function businessConfirmationStatusLabel(status) {
  return {
    CONFIRMED: '已确认设计Mapping并形成正式材料需求',
    READY_FOR_BUSINESS_CONFIRMATION: '可提交业务确认（未批准）',
    MATERIAL_IDENTITY_REQUIRED: '需确认Material身份',
    QUANTITY_RULE_REQUIRED: '需确认数量规则',
    UOM_DEFINITION_REQUIRED: '需解释对象单位',
    BUSINESS_FACT_REQUIRED: '需补业务事实',
  }[status] || '待业务确认'
}
const materialSummaryRows = computed(() => (activeCalculation.value?.materialRequirements || []).map((row, index) => ({
  key: row.id || index,
  code: row.materialCode || '待建立',
  name: row.materialName || '材料名称待完善',
  specification: row.orderSpecification ? JSON.stringify(row.orderSpecification) : '规格待完善',
  unit: row.uomCode || '单位待完善',
  net: row.netQuantity == null ? '未知' : String(row.netQuantity),
  gross: row.grossQuantity == null ? '待确定' : String(row.grossQuantity),
  missing: row.scrapRateStatus === 'maintained' ? '无' : '损耗／预留待维护',
  trace: row.sourcePath || row.trace?.sourcePath || `核算记录 ${activeCalculation.value?.calculationNo || '-'}`,
})))
const engineeringUsagePreviewRows = computed(() => (activeDraft.value?.currentInputCalculation?.totals || activeDraft.value?.sourceCalculation?.totals || [])
  .filter(row => row.net != null && ['m', 'm2', '条'].includes(row.unit))
  .map(row => ({ key: `${row.resultScope}|${row.sheet}|${row.project}|${row.unit}`, project: row.project, sheet: row.sheet, net: row.net, unit: row.unit, known: row.known, missing: row.missing, trace: `${row.ids?.length || 0}项来源结果；${row.resultScopeLabel}` })))
const workOrderRows = computed(() => savedRecordSelected.value ? savedContext.value?.rows || [] : activeDraft.value?.workOrderRows || draftRows.value)
const engineeringWorkloadReadState = ref('not_requested')
const engineeringWorkloadReadError = ref('')
const engineeringWorkloadLoadedScope = ref('')
const engineeringWorkloadScope = computed(() => selectedOrder.value ? JSON.stringify({
  salesOrderItemId: selectedOrder.value.salesOrderItemId,
  sourceRecordId: selectedOrder.value.sourceRecordId,
  workbookSourceRecordId: selectedWorkbookSourceRecordId.value || null,
  orderEngineeringInstanceId: selectedOrder.value.orderEngineeringInstanceId,
  isSourceTrial: Boolean(selectedOrder.value.isSourceTrial),
}) : '')
const engineeringWorkloadFacts = computed(() => {
  if (loading.value || loadError.value || versionStale.value) return null
  let facts
  if (activeDraft.value) {
    if (engineeringWorkloadReadState.value !== 'loaded' || engineeringWorkloadLoadedScope.value !== engineeringWorkloadScope.value) return null
    facts = activeDraft.value.engineeringWorkloadSummary
  } else {
    if (calculationDetailLoading.value || calculationDetailError.value
      || !activeCalculation.value || activeCalculation.value.salesOrderItemId !== selectedOrder.value?.salesOrderItemId) return null
    facts = activeCalculation.value.engineeringWorkloadSummary
  }
  return facts?.contractVersion === 'PCE-ENGINEERING-WORKLOAD-SUMMARY-V1' && facts.factSource === 'server' ? facts : null
})
const engineeringWorkloadSummary = computed(() => {
  const facts = engineeringWorkloadFacts.value
  return facts?.readStatus === 'loaded'
    && Array.isArray(facts.workshopViews?.[workshopView.value]?.rows) && Array.isArray(facts.formalSavedFacts)
    ? facts : null
})
const engineeringWorkloadDisplayError = computed(() => engineeringWorkloadReadError.value || calculationDetailError.value || loadError.value
  || (engineeringWorkloadFacts.value?.readStatus === 'read_failed' ? engineeringWorkloadFacts.value.readStatusLabel : ''))
const engineeringWorkloadRows = computed(() => engineeringWorkloadSummary.value?.workshopViews[workshopView.value].rows || [])
const engineeringWorkloadFormalRows = computed(() => engineeringWorkloadSummary.value?.formalSavedFacts || [])
// PceEnterpriseListTable owns PceEnterpriseAdvancedFilter, selection and scrolling.
const engineeringWorkloadFilterSchema = Object.freeze([
  { field: 'sourceCode', label: '来源编码', filterType: 'text' },
  { field: 'sourceProject', label: '来源工程项目', filterType: 'text' },
  { field: 'dataTypeLabel', label: '数据类型', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'uomLabel', label: '单位', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'sourceNatureLabel', label: '来源性质', filterType: 'select', optionsProvider: 'current_result' },
  { field: 'statusLabel', label: '转换状态', filterType: 'select', optionsProvider: 'current_result' },
])
const engineeringWorkloadLists = reactive([
  { id: 'engineering-workload-source-facts', title: '来源工程事实与预览', rows: engineeringWorkloadRows,
    description: '当前设计预览与历史来源分别保留，不代替已保存工程事实。' },
  { id: 'engineering-workload-formal-facts', title: '已保存工程事实与工序需求关联', rows: engineeringWorkloadFormalRows,
    description: '读取真实核算、派生事实、成功明细和已核验关联；数量与来源预览分别展示。' },
].map(list => ({ ...list,
  contract: createPceEnterpriseListContract({ pageCode: 'pde-order-engineering-calculation', title: list.title, moduleCode: 'PDE' }),
  runtime: reactive(usePceEnterpriseListRuntime({
    rows: list.rows, filterSchema: engineeringWorkloadFilterSchema, pageCode: 'pde-order-engineering-calculation',
    searchFields: ['sourceCode', 'sourceProject', 'dataTypeLabel', 'quantity', 'uomLabel', 'sourceNatureLabel', 'statusLabel'],
    exportFileName: `${list.title}.csv`,
    exportColumns: [{ field: 'sourceCode', label: '来源编码' }, { field: 'sourceProject', label: '来源工程项目' },
      { field: 'dataTypeLabel', label: '数据类型' }, { field: 'quantity', label: '工程数量' },
      { field: 'uomLabel', label: '单位' }, { field: 'sourceNatureLabel', label: '来源性质' }, { field: 'statusLabel', label: '转换状态' },
      { label: '房门单贡献', value: row => row.contributions?.door ?? '未知' },
      { label: '三合一单贡献', value: row => row.contributions?.threeInOne ?? '未知' },
      { label: '待确认事项', value: row => Array.isArray(row.missingReasons) ? row.missingReasons.map(reason => reason.statusLabel).join('；') : '未知' }],
  })),
})))
async function refreshEngineeringWorkload() {
  if (activeDraft.value || selectedOrder.value?.isSourceTrial || !activeCalculation.value) await loadDrafts()
  else await chooseCalculation(activeCalculation.value)
}
const actionLabel = id => pceBusinessActionLabel(id) || id
const displayFact = (value, fallback) => value === 0 || String(value || '').trim() ? value : fallback
const materialSpecText = row => [row.materialCode, row.materialName, row.specification].filter(Boolean).join('／') || '来源未提供材料身份'
const dimensionSemanticsText = row => (row.dimensionSemantics || []).map(item => `${item.label} ${item.value} ${item.unit || row.designUom || '单位未冻结'}`).join('；') || '尺寸语义待维护'
const designMaterialText = row => [row.materialCode, row.materialName, row.specification].filter(Boolean).join('／') || '材料身份待匹配'
function designInputGapText(row) {
  const missing = row.missingCalculationFields || []
  const gaps = row.designGaps || []
  const labels = { sourceKey: '来源位置', designLength: '长度', designWidth: '宽度', designThickness: '厚度', visibleCondition: '见光条件', edgeMethod: '封边方式', hardware: '五金', glass: '玻璃' }
  const normalized = values => values.map(item => labels[typeof item === 'string' ? item : (item.label || item.field || item.code)] || (typeof item === 'string' ? item : (item.label || item.field || item.code))).filter(Boolean)
  const parts = []
  if (missing.length) parts.push(`核算缺项：${[...new Set(normalized(missing))].join('、')}`)
  if (gaps.length) parts.push(`后续设计／材料需求补充：${[...new Set(normalized(gaps))].join('、')}未提供（当前工程量规则不读取，不阻断本次计算）`)
  const notApplicable = Object.entries(row.fieldApplicability || {}).filter(([, item]) => item?.classification === 'not_applicable').map(([key]) => key)
  if (notApplicable.length) parts.push(`本规则不适用：${[...new Set(normalized(notApplicable))].join('、')}`)
  return parts.join('；') || '无当前核算缺项；不适用字段保持原业务语义'
}
function workOrderMissingFields(row) {
  return row.remainingConfirmations || []
}
function stableOrderLinkLabel(status) {
  if (status === 'DESIGN_SOURCE_LINKED') return '已通过产品设计来源建立整单回链'
  if (status === 'NO_STABLE_KEY') return '尚未建立稳定订单关联'
  if (status === 'SOURCE_ORDER_NOT_ESTABLISHED') return '同一来源订单已确认；正式销售订单尚未建立或未唯一匹配'
  if (!status) return '关联状态未提供'
  return { LINKED: '已建立稳定订单关联', linked: '已建立稳定订单关联' }[status] || status
}
function businessPageLocation(page) {
  const query = { page }
  if (selectedWorkbookSourceRecordId.value) query.workbookSourceRecordId = selectedWorkbookSourceRecordId.value
  const locationContext = page === 'results' && !savedRecordSelected.value && selectedOrder.value && !selectedOrder.value.isSourceTrial
    ? linkedWholeOrderSummary(selectedOrder.value.orderNo) || selectedOrder.value
    : selectedOrder.value
  if (locationContext?.isSourceTrial) query.sourceRecord = String(locationContext.sourceRecordId)
  else if (selection.salesOrderItemId) query.order = String(selection.salesOrderItemId)
  if (!selectedOrder.value?.isSourceTrial && formalSummaryReturnTarget.value) {
    query.returnSourceRecord = formalSummaryReturnTarget.value.sourceRecordId
    if (formalSummaryReturnTarget.value.orderNo) query.returnOrderNo = formalSummaryReturnTarget.value.orderNo
    if (formalSummaryReturnTarget.value.engineeringVersion) query.returnEngineeringVersion = formalSummaryReturnTarget.value.engineeringVersion
    if (formalSummaryReturnTarget.value.lineCount) query.returnLineCount = String(formalSummaryReturnTarget.value.lineCount)
  }
  if (savedRecordSelected.value) query.calculationRecord = String(activeCalculation.value.id)
  const version = savedRecordSelected.value ? savedContext.value?.sourceVersion : activeDraft.value?.sourceVersion || selectedOrder.value?.sourceVersion
  if (version) query.engineeringVersion = String(version)
  return { path: '/pde/engineering-calculations', query }
}
const productDesignReturnLocation = computed(() => ({
  path: '/pde/product-definitions',
  query: {
    ...(selectedOrder.value?.orderNo ? { orderNo: selectedOrder.value.orderNo } : {}),
    ...(selectedOrder.value?.sourceRecordId ? { sourceRecord: String(selectedOrder.value.sourceRecordId) } : {}),
  },
}))
const ruleDefinitionsLocation = computed(() => {
  if (ruleOnlyEntryMode.value) return {
    name: 'FoundationEngineeringRuleDefinitions',
    query: {
      returnTo: '/pde/engineering-calculations?entry=rules',
      navigationScope: 'rules-entry',
    },
  }
  const returnLocation = businessPageLocation('input')
  const engineeringVersion = activeDraft.value?.sourceVersion
    || requestedEngineeringVersion.value
    || selectedOrder.value?.sourceVersion
  const sourceScope = Boolean(selectedOrder.value?.isSourceTrial)
  const scopeObjectCount = sourceScope
    ? (draftRows.value.length || selectedOrder.value?.draft?.rows?.length || 0)
    : (formalContinuationLine.value?.designObjectCount || selectedOrder.value?.designItemCount || 0)
  const stableSalesOrderItemId = !sourceScope && Number(selection.salesOrderItemId) > 0
    ? String(selection.salesOrderItemId)
    : ''
  return {
    name: 'FoundationEngineeringRuleDefinitions',
    query: {
      returnTo: returnLocation.path + `?${new URLSearchParams(returnLocation.query).toString()}`,
      ...(selectedOrder.value?.orderNo ? { orderNo: selectedOrder.value.orderNo } : {}),
      ...(selectedOrder.value?.sourceRecordId ? { sourceRecord: String(selectedOrder.value.sourceRecordId) } : {}),
      ...(engineeringVersion ? { engineeringVersion: String(engineeringVersion) } : {}),
      navigationScope: sourceScope ? 'source' : 'order-line',
      scopeObjectCount: String(scopeObjectCount),
      ...(stableSalesOrderItemId ? { salesOrderItemId: stableSalesOrderItemId } : {}),
      ...(!sourceScope && selectedOrder.value?.lineNo ? { salesOrderLineNo: String(selectedOrder.value.lineNo) } : {}),
    },
  }
})
async function syncContextUrl() {
  const location = businessPageLocation(activeBusinessPage.value)
  if (JSON.stringify(location.query) !== JSON.stringify(route.query)) await router.replace(location)
}
async function copyDiagnostics() {
  try { await navigator.clipboard.writeText(JSON.stringify(diagnostics(), null, 2)); ElMessage.success('诊断数据已复制。') } catch { ElMessage.error('浏览器未允许复制，请在环境详情中查看。') }
}
// Display-only compatibility for the existing endpoint; never alter server status or eligibility.
function calculationStatusLabel(row) {
  if (row.statusLabel) return row.statusLabel
  const label = formatBusinessStatus(row.status, '业务状态未提供')
  if (label !== row.status) return label
  return { calculated: '已核算', completed: '已完成', prepared: '已准备', running: '执行中', draft: '草稿', superseded: '已被新修订替代', obsolete: '已失效' }[row.status] || '业务状态未提供'
}
function unwrap(response) {
  if (response?.success === false) {
    const status = Number(response?.factLoadFacts?.httpStatus || response?.meta?.status || 0)
    const code = response?.error?.code || response?.factLoadFacts?.errorCode || `HTTP_${status || 'UNKNOWN'}`
    const message = response?.error?.message || response?.factLoadFacts?.errorMessage || '服务端请求失败'
    const error = new Error(message)
    error.response = { status, data: { code, message } }
    error.readFailure = response.factLoadFacts || null
    throw error
  }
  return response?.data ?? response ?? {}
}
const isAuthenticationFailure = error => Number(error?.response?.status || 0) === 401

const fieldLabels = Object.freeze({ opening_height: '门洞高度', opening_width: '门洞宽度', casing_height: '门套高度', casing_width: '门套宽度', door_height: '门扇高度', door_width: '门扇宽度', order_quantity: '订单数量', edge_band_25_net_length: '封边皮25净长度', edge_band_50_net_length: '封边皮50净长度' })
const inputLabel = name => fieldLabels[name] || name
const resultLabel = name => fieldLabels[name] || name || '未命名结果'
function decimalValue(value) {
  if (value && typeof value === 'object') {
    if (value.decimal !== undefined && value.decimal !== null) return value.decimal
    if (value.value !== undefined && value.value !== null) return decimalValue(value.value)
  }
  return value ?? '未生成'
}
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未记录'
function resetOperation(operation) { Object.assign(operation, { state: 'idle', title: '', message: '', attempt: 0 }) }
async function switchBusinessPage(page) {
  if (page === activeBusinessPage.value) return
  if (activeBusinessPage.value === 'input' && !savedRecordSelected.value && draftDirty.value) {
    try { await ElMessageBox.confirm('工程录入存在未保存修改。切换后内容会原样保留，不会自动保存或丢弃；返回录入页后可继续编辑。', '保留未保存内容并切换', { confirmButtonText: '保留并切换', cancelButtonText: '留在录入页', type: 'warning' }) } catch { return }
  }
  await router.push(businessPageLocation(page))
}
function employeeOptions(role) { return engineeringInputOptions.value.employeeRoles?.[role]?.options || [] }
function historicalEmployeeOption(role) {
  const current = draftAssignments[role]?.snapshot
  if (!current?.employeeId || employeeOptions(role).some(row => String(row.employeeId) === String(current.employeeId))) return null
  return { ...current, label: current.label || `${current.fullName || '历史员工'}（${current.employeeNo || current.employeeId}）` }
}
function productCategoryOptions(row) {
  const options = engineeringInputOptions.value.productCategories || []
  if (!row.productCategoryId || options.some(item => String(item.id) === String(row.productCategoryId))) return options
  return [...options, { id: row.productCategoryId, label: `${row.productCategoryName || '历史产品分类'}（${row.productCategoryCode || row.productCategoryId}）` }]
}
function unitOptions(row) {
  const options = engineeringInputOptions.value.units || []
  if (!row.unitId || options.some(item => String(item.id) === String(row.unitId))) return options
  return [...options, { id: row.unitId, label: `${row.unitName || row.unit || '历史单位'}（${row.unit || row.unitId}）` }]
}
function applyProductCategory(row) {
  const option = (engineeringInputOptions.value.productCategories || []).find(item => String(item.id) === String(row.productCategoryId))
  row.productCategoryCode = option?.code || row.productCategoryCode || ''
  row.productCategoryName = option?.name || row.productCategoryName || ''
}
function applyUnit(row) {
  const option = (engineeringInputOptions.value.units || []).find(item => String(item.id) === String(row.unitId))
  row.unit = option?.code || row.unit || ''
  row.unitName = option?.name || row.unitName || ''
}
function applyVisibleCondition(row) {
  const option = (engineeringInputOptions.value.visibleConditions || []).find(item => item.code === row.visibleConditionCode)
  row.visibleCondition = option?.name || ''
  row.visibleConditionSnapshot = option || null
}
function resetDraftAssignments(assignments = {}, packaging = {}) {
  for (const role of responsibilityRoleDefinitions) {
    const snapshot = assignments?.[role.key] || null
    draftAssignments[role.key].employeeId = snapshot?.employeeId ? String(snapshot.employeeId) : ''
    draftAssignments[role.key].snapshot = snapshot
  }
  Object.assign(draftPackaging, { id: packaging?.id ? String(packaging.id) : '', name: packaging?.name || '', statusLabel: packaging?.statusLabel || '未维护' })
}
function resetConfirmedFacts(draft = {}) {
  confirmedResponsibilityFacts.value = draft.confirmedResponsibilityFacts || {}
  businessOrderReference.value = draft.businessOrderReference || {}
}
function newDraftRow(sourceType = '房门单') { return { id: `DRAFT-${Date.now()}-${Math.random().toString(16).slice(2)}`, sourceType, space: '', productCategoryId: '', productCategoryCode: '', productCategoryName: '', product: '', component: '', componentCode: '', quantity: '', unitId: '', unit: '', unitName: '', length: '', width: '', thickness: '', materialCode: '', materialName: '', specification: '', doorOpeningDirectionOptionId: '', lineStyleOptionId: '', edgeMethodOptionId: '', edgeMode: '', edgeModeOriginal: '', visibleCondition: '', visibleConditionCode: '', visibleConditionSnapshot: null, materialProcessCode: '', routingProcessCode: '', processingNote: '', drawingReference: null } }
function seedDraftRows() {
  if (!selectedOrder.value) { draftRows.value = []; resetDraftAssignments(); lastSavedDraftJson.value = draftStateJson(); return }
  if (selectedOrder.value.isSourceTrial) {
    const draft = selectedOrder.value.draft
    draftRows.value = (draft?.rows || []).map(normalizeDraftRow)
    resetDraftAssignments(draft?.responsibilityAssignments, draft?.packagingMethod)
    resetConfirmedFacts(draft)
    draftReason.value = draft?.revisionReason || ''
    activeDraftId.value = draft?.id ? String(draft.id) : ''
    lastSavedDraftJson.value = draftStateJson(); return
  }
  const values = Object.fromEntries((selectedOrder.value.canonicalInputs || []).map(row => [row.canonicalField, row.normalizedValue]))
  const unit = (engineeringInputOptions.value.units || []).find(row => row.code === selectedOrder.value.orderUomCode)
  draftRows.value = [{ ...newDraftRow(selectedOrder.value.sourceSheet === '三合一生产单' ? '三合一单' : '房门单'), space: selectedOrder.value.installationArea || '', productCategoryId: selectedOrder.value.productCategoryId ? String(selectedOrder.value.productCategoryId) : '', product: selectedOrder.value.customerProductName || selectedOrder.value.materialName || '', component: selectedOrder.value.materialName || '', componentCode: selectedOrder.value.materialCode || '', quantity: selectedOrder.value.orderQuantity || '', unitId: unit ? String(unit.id) : '', unit: selectedOrder.value.orderUomCode || '', unitName: unit?.name || '', length: values.opening_height || values.casing_height || '', width: values.opening_width || values.casing_width || '', thickness: values.casing_depth || '', materialCode: selectedOrder.value.sourceMaterialCode || '', sourceSheet: selectedOrder.value.sourceSheet, sourceRow: selectedOrder.value.sourceRow }]
  applyProductCategory(draftRows.value[0]); resetDraftAssignments(); resetConfirmedFacts()
  lastSavedDraftJson.value = draftStateJson()
}
let draftReadSequence = 0
async function loadDrafts({ syncUrl = true } = {}) {
  const requestSequence = ++draftReadSequence
  const expectedSalesOrderItemId = selectedOrder.value?.salesOrderItemId
  const expectedWorkloadScope = engineeringWorkloadScope.value
  engineeringWorkloadReadState.value = 'loading'
  engineeringWorkloadReadError.value = ''
  engineeringWorkloadLoadedScope.value = ''
  if (!selectedOrder.value) { drafts.value = []; engineeringWorkloadReadState.value = 'not_requested'; return }
  if (selectedOrder.value.isSourceTrial) {
    try {
      const data = unwrap(await pdeApi.engineeringDesignCalculationContext(selectedOrder.value.sourceRecordId, { includeWorkloadSummary: activeBusinessPage.value === 'scheduling',workbookSourceRecordId:selectedWorkbookSourceRecordId.value }))
      if (requestSequence !== draftReadSequence || selectedOrder.value?.salesOrderItemId !== expectedSalesOrderItemId || expectedWorkloadScope !== engineeringWorkloadScope.value) return
      drafts.value = data.draft ? [data.draft] : []
      if (data.draft) { activeDraftId.value = String(data.draft.id); openDraft({ syncUrl }) }
      engineeringWorkloadLoadedScope.value = expectedWorkloadScope
      engineeringWorkloadReadState.value = data.draft?.engineeringWorkloadSummary?.readStatus === 'not_requested' ? 'not_requested' : 'loaded'
    } catch (error) {
      if (requestSequence === draftReadSequence && expectedWorkloadScope === engineeringWorkloadScope.value) {
        engineeringWorkloadReadState.value = 'read_failed'
        engineeringWorkloadReadError.value = explain(error, '产品设计核算上下文读取失败，工程作业量与转换状态未知')
      }
      ElMessage.error(explain(error, '产品设计核算上下文读取失败'))
    }
    return
  }
  const scope = selectedOrder.value.orderEngineeringInstanceId
  if (!scope) { drafts.value = []; engineeringWorkloadReadState.value = 'not_requested'; return }
  try {
    const data = unwrap(await pdeApi.engineeringDrafts(scope))
    if (requestSequence !== draftReadSequence || selectedOrder.value?.salesOrderItemId !== expectedSalesOrderItemId || expectedWorkloadScope !== engineeringWorkloadScope.value) return
    drafts.value = data.drafts || []
    if (selectedOrder.value.isSourceTrial) {
      const selected = drafts.value.find(row => String(row.id) === String(selectedOrder.value.sourceRecordId))
      if (selected) { activeDraftId.value = String(selected.id); openDraft() }
    }
    engineeringWorkloadLoadedScope.value = expectedWorkloadScope
    engineeringWorkloadReadState.value = 'loaded'
  } catch (error) {
    if (requestSequence === draftReadSequence && expectedWorkloadScope === engineeringWorkloadScope.value) {
      engineeringWorkloadReadState.value = 'read_failed'
      engineeringWorkloadReadError.value = explain(error, '工程草稿读取失败，工程作业量与转换状态未知')
    }
    ElMessage.error(explain(error, '工程草稿读取失败'))
  }
}
async function loadUnboundDrafts() {
  const requestedSequence = sequence, requestedWorkbookSourceId = selectedWorkbookSourceRecordId.value
  engineeringWorkloadReadState.value = 'loading'
  engineeringWorkloadLoadedScope.value = ''
  engineeringWorkloadReadError.value = ''
  try {
    const requestedSourceRecordId = String(route.query.sourceRecord || route.query.returnSourceRecord || '')
    const data = unwrap(await pdeApi.engineeringDesignCalculationContext(requestedSourceRecordId, { includeWorkloadSummary: false,workbookSourceRecordId:requestedWorkbookSourceId }))
    if (requestedSequence !== sequence || requestedWorkbookSourceId !== selectedWorkbookSourceRecordId.value) return
    unboundDrafts.value = data.draft ? [data.draft] : []
    auxiliaryReadNotice.value = ''
  } catch (error) {
    if (requestedSequence !== sequence || requestedWorkbookSourceId !== selectedWorkbookSourceRecordId.value) return
    engineeringWorkloadReadState.value = 'read_failed'
    engineeringWorkloadReadError.value = explain(error, '工程来源读取失败，工程作业量与转换状态未知')
    if (Number(error?.response?.status || 0) !== 403) throw error
    unboundDrafts.value = []
    auxiliaryReadNotice.value = '当前账号无查看权限。登录状态保持有效，不会跳回登录页；请由权限管理员授予工程核算查看权限。'
  }
}
function addDraftRow(type) { draftRows.value.push(newDraftRow(type)) }
function copyDraftRow() { if (!draftRows.value.length) return; draftRows.value.push({ ...draftRows.value.at(-1), id: `DRAFT-${Date.now()}-${Math.random().toString(16).slice(2)}` }) }
function cleanProcessingNote(value) { return String(value || '').split('；').filter(item => item && !/(?:饰面\/颜色|线型规格)：False$/.test(item)).join('；') }
function normalizeDraftRow(row) {
  const visible = (engineeringInputOptions.value.visibleConditions || []).find(option => option.code === row.visibleConditionCode || option.name === row.visibleCondition)
  return { ...newDraftRow(row.sourceType), ...row, processingNote: cleanProcessingNote(row.processingNote), productCategoryId: row.productCategoryId ? String(row.productCategoryId) : '', unitId: row.unitId ? String(row.unitId) : '', doorOpeningDirectionOptionId: row.doorOpeningDirectionOptionId ? String(row.doorOpeningDirectionOptionId) : '', lineStyleOptionId: row.lineStyleOptionId ? String(row.lineStyleOptionId) : '', edgeMethodOptionId: row.edgeMethodOptionId ? String(row.edgeMethodOptionId) : '', visibleConditionCode: visible?.code || '' }
}
function mergeDraftWithDesignProjection(row, draft) {
  const projection = (draft.workOrderRows || []).find(item => item.sourceSheet === row.sourceSheet && Number(item.sourceRow) === Number(row.sourceRow))
  if (!projection) return row
  return normalizeDraftRow({ ...row,
    space: projection.space || row.space, product: projection.product || row.product,
    productCategoryId: projection.productCategoryId || row.productCategoryId,
    productCategoryCode: projection.productCategoryCode || row.productCategoryCode,
    productCategoryName: projection.productCategoryName || row.productCategoryName,
    component: projection.component || row.component, componentCode: projection.componentCode || row.componentCode,
    quantity: projection.quantity ?? row.quantity, unitId: projection.unitId || row.unitId,
    unit: projection.unit || row.unit, unitName: projection.unitName || row.unitName,
    length: projection.length ?? row.length, width: projection.width ?? row.width, thickness: projection.thickness ?? row.thickness,
    materialCode: projection.materialCode || row.materialCode, materialName: projection.materialName || row.materialName,
    specification: projection.specification || row.specification,
    edgeMode: projection.edgeStatusLabel === '本业务不适用' ? row.edgeMode : projection.edgeMode || row.edgeMode,
    visibleCondition: projection.visibleStatusLabel === '本业务不适用' ? row.visibleCondition : projection.visibleCondition || row.visibleCondition,
    materialProcessCode: projection.materialProcessCode || row.materialProcessCode,
    routingProcessCode: projection.routingProcessCode || row.routingProcessCode,
    processingNote: projection.processingNote || row.processingNote,
  })
}
function openDraft({ syncUrl = true } = {}) { const draft = activeDraft.value; if (!draft) return; draftRows.value = (draft.rows || []).map(row => mergeDraftWithDesignProjection(row, draft)); resetDraftAssignments(draft.responsibilityAssignments, draft.packagingMethod); resetConfirmedFacts(draft); lastSavedDraftJson.value = draftStateJson(); draftReason.value = draft.revisionReason || ''; importPreview.value = null; if (syncUrl) syncContextUrl() }
async function saveDraft() {
  if (!workbookObjectWriteAllowed.value) { ElMessage.warning(workbookSourceIntake.value.sourceIntakeStatusLabel || '当前来源版本的工程对象保存资格未知。'); return }
  if (!selectedOrder.value?.orderEngineeringInstanceId && !selectedOrder.value?.isSourceTrial) { ElMessage.warning('当前订单未建立稳定工程实例，不能保存到服务端。'); return }
  savingDraft.value = true
  try {
    const responsibilityAssignments = Object.fromEntries(responsibilityRoleDefinitions.map(role => [role.key, { employeeId: draftAssignments[role.key].employeeId || null }]))
    const data = unwrap(await pdeApi.saveEngineeringDraft({ orderEngineeringInstanceId: selectedOrder.value.orderEngineeringInstanceId, salesOrderItemId: selectedOrder.value.isSourceTrial ? null : selectedOrder.value.salesOrderItemId, sourceRecordId: selectedOrder.value.sourceRecordId || null, sourceScopeKey: selectedOrder.value.sourceScopeKey, sourceName: selectedOrder.value.isSourceTrial ? selectedOrder.value.draft?.sourceName || selectedOrder.value.orderNo : `${selectedOrder.value.orderNo} 工程数据录入草稿`, revisionReason: draftReason.value, responsibilityAssignments, confirmedResponsibilityFacts: confirmedResponsibilityFacts.value, businessOrderReference: businessOrderReference.value, packagingMethod: { id: draftPackaging.id || null }, rows: draftRows.value }))
    if (data.previousSourceOverwritten !== false) throw new Error('服务端未证明旧工程来源保持不变，本次响应不作为保存成功。')
    writeCount.value += data.businessWriteSideEffectCount || 0
    if (selectedOrder.value.isSourceTrial) {
      await loadUnboundDrafts()
      selection.salesOrderItemId = -1000000 - Number(data.draft.id)
    }
    await loadDrafts(); activeDraftId.value = String(data.draft.id); openDraft(); await syncContextUrl()
    ElMessage.success(`工程草稿 ${data.draft.sourceVersion} 已保存并重新打开；原来源和历史核算未覆盖。`)
  } catch (error) { ElMessage.error(explain(error, '工程草稿保存失败')) } finally { savingDraft.value = false }
}
async function saveRegisteredSource() {
  if (!workbookObjectWriteAllowed.value) { ElMessage.warning(workbookSourceIntake.value.sourceIntakeStatusLabel || '当前来源版本的工程对象接入资格未知。'); return }
  savingRegisteredSource.value = true
  try {
    const data = unwrap(await pdeApi.saveRegisteredEngineeringSource({ revisionReason: '登记来源71行批量接入；房门8行＋三合一63行；缺项保留；未关联正式销售订单' }))
    if (data.previousSourceOverwritten !== false) throw new Error('服务端未证明历史来源保持不变。')
    writeCount.value += data.businessWriteSideEffectCount || 0
    await loadUnboundDrafts()
    selection.salesOrderItemId = -1000000 - Number(data.draft.id)
    seedDraftRows(); await loadDrafts(); await syncContextUrl()
    ElMessage.success(data.idempotent ? '已回读同一71行来源范围，未重复创建。' : `71行来源已保存为独立修订 ${data.draft.sourceVersion} 并完成回读。`)
  } catch (error) { ElMessage.error(explain(error, '71行来源接入失败')) } finally { savingRegisteredSource.value = false }
}
function previewCsvImport(event) {
  const file = event.target.files?.[0]; event.target.value = ''
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    const lines = String(reader.result || '').replace(/^\uFEFF/, '').split(/\r?\n/).filter(Boolean)
    const headers = (lines.shift() || '').split(',').map(value => value.trim())
    const parsed = lines.map(line => { const values = line.split(','); return Object.fromEntries(headers.map((key, index) => [key, values[index]?.trim() || ''])) })
    const ids = new Set(draftRows.value.map(row => row.id)); const conflicts = parsed.filter(row => row.id && ids.has(row.id)).length
    const missing = parsed.filter(row => !row.sourceType || !row.component || !row.quantity).length
    importPreview.value = { newCount: parsed.length - conflicts, conflictCount: conflicts, missingCount: missing }
    draftRows.value.push(...parsed.filter(row => !row.id || !ids.has(row.id)).map(row => ({ ...newDraftRow(row.sourceType), ...row })))
  }
  reader.readAsText(file, 'utf-8')
}
async function selectOrder() {
  // Invalidate every old scope before awaiting navigation or another read.
  calculationDetailSequence += 1; formalReadSequence += 1; conditionPreflightSequence += 1; draftReadSequence += 1; materialPreviewSequence += 1
  activeCalculation.value = null; calculationDetailError.value = ''; calculationDetailLoading.value = false
  formalContinuation.value = {}; selectedBaselineId.value = null; formalValidation.value = { ready:false,blockers:[] }
  conditionPreflight.value = { blockers:[] }; validation.value = { ready:false,blockers:[] }; selectedConditionSalesOrderItemId.value = null
  for (const operation of [conditionPreflightOperation,validationOperation,methodTrialOperation,bomPreviewOperation]) resetOperation(operation)
  methodTrial.value = null; bomPreview.value = null; bomBlocker.value = ''; activeDraftId.value = ''; drafts.value = []; draftRows.value = []
  materialRequirementHandoff.value = null
  const location = businessPageLocation(activeBusinessPage.value)
  if (JSON.stringify(location.query) === JSON.stringify(route.query)) await refresh()
  else await router.replace(location)
}

function formalRuleIds() { return (formalContinuation.value.formalRulePackages || []).map(row => row.id) }
function formalPermission(code) { return formalContinuation.value.permissions?.[code]?.allowed === true }
function mainContinuationPayload() {
  if (selectedWorkbookSourceRecordId.value !== '' && (!Number.isSafeInteger(Number(selectedWorkbookSourceRecordId.value)) || Number(selectedWorkbookSourceRecordId.value) <= 0)) return null
  if (!selectedOrder.value || selectedOrder.value.isSourceTrial || !formalContinuationLine.value?.orderEngineeringInstanceId || !formalBaselines.value.some(row => row.id === selectedBaselineId.value) || !mainContinuationFacts.value?.predecessorCalculations?.some(row => row.id === selectedPredecessorCalculationId.value)) return null
  return { salesOrderItemId: selectedOrder.value.salesOrderItemId, orderEngineeringInstanceId: formalContinuationLine.value.orderEngineeringInstanceId, orderEngineeringBaselineId: selectedBaselineId.value, predecessorCalculationId: selectedPredecessorCalculationId.value, ruleIds: formalRuleIds(),...(selectedWorkbookSourceRecordId.value ? { workbookSourceRecordId:Number(selectedWorkbookSourceRecordId.value) } : {}) }
}
function mainContinuationScopeKey() { return JSON.stringify({ salesOrderItemId: selectedOrder.value?.salesOrderItemId, orderEngineeringInstanceId: formalContinuationLine.value?.orderEngineeringInstanceId, orderEngineeringBaselineId: selectedBaselineId.value, predecessorCalculationId: selectedPredecessorCalculationId.value, ruleIds: formalRuleIds(),...(selectedWorkbookSourceRecordId.value ? { workbookSourceRecordId:Number(selectedWorkbookSourceRecordId.value) } : {}) }) }
function resetMainContinuationPreview() {
  mainContinuationRequestSequence += 1
  mainContinuationPreview.value = null
  mainContinuationPreviewScope = ''
  mainContinuationError.value = ''
  mainContinuationReadback.value = null
}
async function runMainContinuationAction(actionCode) {
  if (actionCode === 'preview') await previewMainContinuation()
  else if (actionCode === 'execute') await executeMainContinuation()
}
async function previewMainContinuation() {
  const payload = mainContinuationPayload()
  if (formalBusy.value || !payload || !mainContinuationActions.value.some(action => action.actionCode === 'preview' && action.allowed === true)) return
  resetMainContinuationPreview()
  const requestSequence = mainContinuationRequestSequence
  const scopeKey = mainContinuationScopeKey()
  const actorProfile = permissionProfile.value
  formalBusy.value = true
  try {
    const preview = unwrap(await pdeApi.previewEngineeringCalculationVersionContinuation(payload))
    if (requestSequence !== mainContinuationRequestSequence || scopeKey !== mainContinuationScopeKey() || actorProfile !== permissionProfile.value) return
    if (payload.workbookSourceRecordId && preview.workbookSourceRecordId !== payload.workbookSourceRecordId) throw new Error('正式预览未对应本次明确选择的工作簿来源版本；未取得执行资格。')
    mainContinuationPreview.value = preview
    mainContinuationPreviewScope = scopeKey
  } catch (error) {
    if (requestSequence === mainContinuationRequestSequence && scopeKey === mainContinuationScopeKey() && actorProfile === permissionProfile.value) mainContinuationError.value = explain(error, '主核算接续预览读取失败，资格未知；未执行保存。')
  } finally { formalBusy.value = false }
}
async function executeMainContinuation() {
  const payload = mainContinuationPayload()
  if (formalBusy.value || !payload || !mainContinuationCanExecute.value) return
  const preview = mainContinuationPreview.value
  const scopeKey = mainContinuationScopeKey()
  const requestSequence = mainContinuationRequestSequence
  const actorProfile = permissionProfile.value
  formalBusy.value = true
  try { await ElMessageBox.confirm('将按当前正式预览承接所选主核算和已确认基线，保留历史固定引用；不会自动形成下游投产量。确认继续？', '正式主核算版本接续', { confirmButtonText: '确认接续', cancelButtonText: '取消', type: 'warning' }) } catch { formalBusy.value = false; return }
  if (requestSequence !== mainContinuationRequestSequence || scopeKey !== mainContinuationScopeKey() || actorProfile !== permissionProfile.value || !mainContinuationCanExecute.value) { formalBusy.value = false; return }
  mainContinuationError.value = ''
  try {
    const result = unwrap(await pdeApi.executeEngineeringCalculationVersionContinuation({ ...payload, expectedContextHash: preview.expectedContextHash, continuationBasisHash: preview.continuationBasisHash, idempotencyKey: `engineering-calculation-continuation:${preview.expectedContextHash}`, reason: '原工程核算页面明确确认主核算版本接续' }))
    if (requestSequence !== mainContinuationRequestSequence || scopeKey !== mainContinuationScopeKey() || actorProfile !== permissionProfile.value) return
    if (!result.continuation?.id || !result.calculation?.id) throw new Error('执行响应没有返回完整承接和主核算身份；结果待核对，未自动重试。')
    const [, detailResponse] = await Promise.all([loadFormalContinuation(), pdeApi.engineeringCalculation(result.calculation.id), loadCalculations()])
    if (scopeKey !== mainContinuationScopeKey() || actorProfile !== permissionProfile.value) return
    const detail = unwrap(detailResponse).calculation
    const record = (mainContinuationFacts.value?.records || []).find(row => row.id === result.continuation?.id && row.newCalculationId === result.calculation?.id && row.predecessorCalculationId === payload.predecessorCalculationId && row.orderEngineeringBaselineId === payload.orderEngineeringBaselineId && row.stateMachineConsistent === true && row.requestStatus === 'COMMITTED')
    if (!record || detail?.id !== result.calculation.id || detail.companyId !== result.calculation.companyId || detail.salesOrderItemId !== payload.salesOrderItemId || detail.orderEngineeringInstanceId !== payload.orderEngineeringInstanceId || detail.trace?.baselineReference?.id !== payload.orderEngineeringBaselineId || detail.status !== 'completed') throw new Error('执行响应尚未与当前正式承接记录、新主核算及提交证明准确对应；结果待核对，未自动重试。')
    if (payload.workbookSourceRecordId) {
      const source = workbookSources.value.find(row => row.id === payload.workbookSourceRecordId)
      const proof = detail.trace?.workbookSource
      if (!source || record.workbookSourceRecordId !== payload.workbookSourceRecordId || proof?.sourceRecordId !== payload.workbookSourceRecordId
        || proof.contentHash !== source.contentHash || proof.workbookSha256 !== source.contentHash
        || proof.sourceVersion !== source.sourceVersion || proof.mappingRuleId !== source.formatRule?.ruleId
        || proof.mappingRuleVersion !== source.formatRule?.ruleVersion || proof.mappingSpecificationHash !== source.formatRule?.specificationHash) throw new Error('正式回读未证明本次工作簿、映射版本及文件指纹准确一致；结果待核对，未自动重试。')
    }
    mainContinuationReadback.value = record
    writeCount.value += result.idempotent ? 0 : 1
    ElMessage.success(record.statusLabel)
  } catch (error) {
    if (scopeKey === mainContinuationScopeKey() && actorProfile === permissionProfile.value) mainContinuationError.value = explain(error, '主核算接续未取得完整提交回读；请核对正式记录，未自动重试。')
  } finally { formalBusy.value = false }
}
async function openFormalLine(row) {
  if (!row?.salesOrderItemId) return
  if (selectedOrder.value?.isSourceTrial) formalSummaryReturnContext.value = buildFormalSummaryReturnContext({
    summary: { ...selectedOrder.value, linkedOrders: [{ ...(selectedOrder.value.linkedOrders?.[0] || {}), lineCount: formalContinuation.value.lines?.length || 0 }] },
    line: { ...row, orderNo: selectedOrder.value.orderNo },
    engineeringVersion: activeDraft.value?.sourceVersion || requestedEngineeringVersion.value || selectedOrder.value.sourceVersion,
    scrollTop: window.scrollY,
    tableScrollLeft: document.querySelector('[data-section="formal-order-summary-lines"]')?.scrollLeft || 0,
  })
  selection.salesOrderItemId = row.salesOrderItemId
  await selectOrder()
}
async function returnToFormalSummary() {
  const target = formalSummaryReturnTarget.value
  if (!target?.summary) { ElMessage.warning('未能从当前公司与订单上下文恢复整单范围；页面没有猜测其它订单。'); return }
  formalSummaryReturnContext.value = null
  selection.salesOrderItemId = target.summary.salesOrderItemId
  await selectOrder()
  await nextTick()
  const table = document.querySelector('[data-section="formal-order-summary-lines"]')
  if (table) table.scrollLeft = target.tableScrollLeft
  document.getElementById('formal-engineering-continuation')?.scrollIntoView?.({ block: 'start', behavior: 'smooth' })
}
let formalReadSequence = 0
async function loadFormalContinuation() {
  const requestSequence = ++formalReadSequence
  const orderNo = selectedOrder.value?.orderNo
  const sourceRecordId = selectedOrder.value?.sourceRecordId
  const workbookSourceRecordId = selectedWorkbookSourceRecordId.value
  const linkedOrders = selectedOrder.value?.linkedOrders || []
  if (!selectedOrder.value || !orderNo || (selectedOrder.value.isSourceTrial && linkedOrders.length !== 1)) { formalContinuation.value = {}; selectedBaselineId.value = null; return }
  try {
    const data = unwrap(await pdeApi.formalEngineeringContinuation(orderNo, workbookSourceRecordId ? { workbookSourceRecordId:Number(workbookSourceRecordId) } : {}))
    if (requestSequence !== formalReadSequence || selectedOrder.value?.orderNo !== orderNo || selectedOrder.value?.sourceRecordId !== sourceRecordId || workbookSourceRecordId !== selectedWorkbookSourceRecordId.value) return
    formalContinuation.value = data
    if (!formalBaselines.value.some(row => row.id === selectedBaselineId.value)) selectedBaselineId.value = formalBaselines.value[0]?.id || null
    await loadConditionPreflight({ announce: false, expectedOrderNo: orderNo, expectedSourceRecordId: sourceRecordId })
  } catch (error) {
    if (requestSequence !== formalReadSequence || workbookSourceRecordId !== selectedWorkbookSourceRecordId.value) return
    formalContinuation.value = {}
    selectedBaselineId.value = null
    auxiliaryReadNotice.value = explain(error, '正式接续事实读取失败')
  }
}
async function showLineConditions(row) {
  if (!row?.salesOrderItemId) return
  selectedConditionSalesOrderItemId.value = row.salesOrderItemId
  if (!conditionLinesBySalesOrderItemId.value.has(Number(row.salesOrderItemId)) && conditionPreflightOperation.state !== 'failed') {
    await loadConditionPreflight({ announce: false })
  }
  await nextTick()
  document.getElementById('sales-order-line-condition-detail')?.scrollIntoView?.({ block: 'nearest', behavior: 'smooth' })
}
async function createFormalInstance() {
  if (!selectedOrder.value) return
  formalBusy.value = true
  try {
    const result = unwrap(await pdeApi.formalEngineeringContinuationAction({ action: 'createInstance', salesOrderItemId: selectedOrder.value.salesOrderItemId, idempotencyKey: `formal-instance:${selectedOrder.value.salesOrderItemId}`, reason: '原工程核算页面明确形成当前订单行工程实例' }))
    await loadFormalContinuation()
    ElMessage.success(result.idempotent ? '已回读既有订单工程实例，未重复创建。' : '订单工程实例已形成并完成回读。')
  } catch (error) { ElMessage.error(explain(error, '订单工程实例形成失败')) } finally { formalBusy.value = false }
}
async function confirmFormalInstanceSource() {
  if (!formalContinuationLine.value?.orderEngineeringInstanceId) return
  formalBusy.value = true
  try {
    await pdeApi.formalEngineeringContinuationAction({ action: 'confirmInstanceSource', orderEngineeringInstanceId: formalContinuationLine.value.orderEngineeringInstanceId, reason: '原工程核算页面明确确认实例采用当前已确认工程来源' })
    await loadFormalContinuation()
    ElMessage.success('实例来源已确认并完成回读。')
  } catch (error) { ElMessage.error(explain(error, '实例来源确认失败')) } finally { formalBusy.value = false }
}
async function validateFormalContinuation() {
  if (!selectedOrder.value || !formalContinuationLine.value?.orderEngineeringInstanceId || !selectedBaselineId.value) return
  formalBusy.value = true
  formalValidation.value = { ready: false, blockers: [] }
  try {
    formalValidation.value = unwrap(await pdeApi.formalEngineeringContinuationAction({ action: 'validate', salesOrderItemId: selectedOrder.value.salesOrderItemId, orderEngineeringInstanceId: formalContinuationLine.value.orderEngineeringInstanceId, orderEngineeringBaselineId: selectedBaselineId.value, ruleIds: formalRuleIds() }))
    ElMessage[formalValidation.value.ready ? 'success' : 'warning'](formalValidation.value.ready ? '对象级基线与正式规则校验通过；本次校验零写入。' : '校验完成，仍有对象级阻断。')
  } catch (error) { ElMessage.error(explain(error, '正式办理条件校验失败')) } finally { formalBusy.value = false }
}
async function executeFormalContinuation() {
  if (!formalValidation.value.ready || !selectedOrder.value) return
  try { await ElMessageBox.confirm(`将按已确认基线保存当前实例的 ${formalValidation.value.selection?.resultPositionCount || 0} 个对象结果位置；不会形成材料需求或BOM。确认继续？`, '执行正式对象级核算', { confirmButtonText: '执行并保存', cancelButtonText: '取消', type: 'warning' }) } catch { return }
  formalBusy.value = true
  try {
    const result = unwrap(await pdeApi.formalEngineeringContinuationAction({ action: 'execute', salesOrderItemId: selectedOrder.value.salesOrderItemId, orderEngineeringInstanceId: formalContinuationLine.value.orderEngineeringInstanceId, orderEngineeringBaselineId: selectedBaselineId.value, ruleIds: formalValidation.value.selection?.ruleIds || formalRuleIds(), reason: '原工程核算页面明确执行对象级正式工程核算' }))
    writeCount.value += result.idempotent ? 0 : 1
    await Promise.all([loadFormalContinuation(), loadCalculations()])
    ElMessage.success(result.idempotent ? '相同实例、基线、对象输入和规则已回读原核算记录。' : `正式核算 ${result.calculation?.calculationNo || ''} 已保存并完成回读。`)
  } catch (error) { ElMessage.error(explain(error, '对象级正式工程核算失败')) } finally { formalBusy.value = false }
}
let conditionPreflightSequence = 0
async function loadConditionPreflight({ announce = false, expectedOrderNo = selectedOrder.value?.orderNo, expectedSourceRecordId = selectedOrder.value?.sourceRecordId } = {}) {
  if (!selectedOrder.value?.orderNo) return
  const requestSequence = ++conditionPreflightSequence
  const expectedWorkbookSourceRecordId = selectedWorkbookSourceRecordId.value
  if (announce) busy.value = true
  conditionPreflight.value = { blockers: [] }
  const attempt = conditionPreflightOperation.attempt + 1
  Object.assign(conditionPreflightOperation, { state: 'running', title: '正在只读预检', message: `第${attempt}次请求正在回读服务端办理事实。`, attempt })
  try {
    const response = unwrap(await pdeApi.preflightOrderEngineeringCalculation({
      orderNo: expectedOrderNo,
      sourceRecordId: expectedSourceRecordId,
      ...(expectedWorkbookSourceRecordId !== '' && expectedWorkbookSourceRecordId != null ? { workbookSourceRecordId:Number(expectedWorkbookSourceRecordId) } : {}),
    }))
    if (requestSequence !== conditionPreflightSequence || selectedOrder.value?.orderNo !== expectedOrderNo || selectedOrder.value?.sourceRecordId !== expectedSourceRecordId || expectedWorkbookSourceRecordId !== selectedWorkbookSourceRecordId.value) return
    if (expectedWorkbookSourceRecordId !== '' && expectedWorkbookSourceRecordId != null && response.workbookSourceRecordId !== Number(expectedWorkbookSourceRecordId)) throw new Error('条件预检响应未对应本次明确选择的工作簿来源版本；当前资格未知。')
    conditionPreflight.value = response
    const ready = conditionPreflight.value.readyForFullValidation
    Object.assign(conditionPreflightOperation, {
      state: ready ? 'completed' : 'blocked',
      title: ready ? '只读预检完成' : '只读预检发现阻断',
      message: ready
        ? `第${attempt}次预检未发现订单级阻断；业务写入 ${conditionPreflight.value.businessWriteSideEffectCount || 0}。`
        : `第${attempt}次预检返回 ${conditionPreflight.value.blockers?.length || 0} 项准确阻断；业务写入 ${conditionPreflight.value.businessWriteSideEffectCount || 0}。`,
    })
    if (announce) ElMessage[ready ? 'success' : 'warning'](conditionPreflightOperation.message)
  } catch (error) {
    if (requestSequence !== conditionPreflightSequence || selectedOrder.value?.orderNo !== expectedOrderNo || selectedOrder.value?.sourceRecordId !== expectedSourceRecordId || expectedWorkbookSourceRecordId !== selectedWorkbookSourceRecordId.value) return
    const kind = failureKind(error)
    const detail = explain(error, '只读条件预检失败')
    Object.assign(conditionPreflightOperation, {
      state: kind === 'business' ? 'blocked' : 'failed',
      title: kind === 'permission' ? '无权查看预检事实' : kind === 'network' ? '预检读取失败' : kind === 'business' ? '预检上下文受阻' : '预检请求失败',
      message: detail,
    })
    if (announce) ElMessage.error(detail)
  } finally { if (announce) busy.value = false }
}
async function preflightSelection() { await loadConditionPreflight({ announce: true }) }
function explain(error, fallback) { const data = error?.response?.data || {}; if (data.code === 'ECONNABORTED') return '服务端读取等待超时，当前数据数量未知，请稍后重试。'; if (error?.response?.status === 401) return `登录身份无效或已过期：${data.message || fallback}`; if (error?.response?.status === 403) return `当前账号无查看权限。${data.message ? ` ${data.message}` : ''}`; return `${data.code ? `${data.code}：` : ''}${data.message || error?.message || fallback}` }
function failureKind(error) {
  const status = Number(error?.response?.status || 0)
  const code = String(error?.response?.data?.code || '')
  if (status === 401) return 'authentication'
  if (status === 403) return 'permission'
  if (!status || /NETWORK|ECONN|TIMEOUT/i.test(code)) return 'network'
  if ([400, 409, 422].includes(status) && code && !/^HTTP_/.test(code)) return 'business'
  return 'failure'
}
async function validateSelection() {
  busy.value = true
  validation.value = { ready: false, blockers: [] }
  const attempt = validationOperation.attempt + 1
  Object.assign(validationOperation, { state: 'running', title: '正在校验', message: `第${attempt}次校验操作已接收，正在调用服务端校验当前订单行、工程来源、输入与尺寸规则。`, attempt })
  try {
    validation.value = unwrap(await pdeApi.validateOrderEngineeringCalculation(contextPayload()))
    Object.assign(validationOperation, validation.value.ready
      ? { state: 'completed', title: '尺寸校验已完成', message: `第${attempt}次服务端校验已完成：已具备尺寸核算条件；材料数量与BOM条件仍保持独立，不代表材料用量已经就绪。` }
      : { state: 'blocked', title: '尺寸校验受阻', message: `第${attempt}次服务端校验已完成；存在阻断项，请按下方维护入口处理。` })
    ElMessage[validation.value.ready ? 'success' : 'warning'](validationOperation.message)
  } catch (error) {
    const kind = failureKind(error)
    const detail = explain(error, '核算条件校验失败')
    Object.assign(validationOperation, {
      state: kind === 'business' ? 'blocked' : 'failed',
      title: kind === 'permission' ? '校验权限失败' : kind === 'network' ? '校验网络失败' : kind === 'business' ? '尺寸校验受阻' : '校验请求失败',
      message: detail,
    })
    ElMessage.error(detail)
  } finally { busy.value = false }
}
async function executeCalculation() { busy.value = true; try { const result = unwrap(await pdeApi.executeEngineeringCalculation({ scope: 'order_engineering', ...contextPayload(), reason: 'PDE订单工程／物料核算页面明确执行' })); writeCount.value += result.idempotent ? 0 : 1; activeCalculation.value = result.calculation; await loadCalculations(); ElMessage.success(result.idempotent ? '相同输入已回读原核算记录，未重复写入。' : '核算已持久化并完成回读。') } catch (error) { ElMessage.error(explain(error, '工程核算执行失败')) } finally { busy.value = false } }
let materialPreviewSequence = 0
async function loadMaterialRequirementPreview() {
  const requestSequence = ++materialPreviewSequence
  materialRequirementHandoff.value = {}
  materialRequirementPreviewError.value = ''
  if (activeBusinessPage.value !== 'materials' || !selectedOrder.value) return
  const linkedOrders = selectedOrder.value.linkedOrders || []
  const orderId = linkedOrders.length === 1
    ? linkedOrders[0].salesOrderId
    : selectedOrder.value.salesOrderId || selectedOrder.value.orderId
  if (!Number(orderId)) {
    materialRequirementPreviewError.value = '当前工程范围没有唯一正式SalesOrder身份。'
    return
  }
  materialRequirementPreviewLoading.value = true
  try {
    const response = unwrap(await pdeApi.orderBomHandoff({ orderId: Number(orderId) }))
    if (requestSequence !== materialPreviewSequence) return
    if (!response.handoff) {
      const failure = response.handoffReadFailure
      throw new Error(failure?.message || '服务端未返回材料需求承接事实。')
    }
    materialRequirementHandoff.value = response.handoff
  } catch (error) {
    if (requestSequence === materialPreviewSequence) materialRequirementPreviewError.value = explain(error, '材料需求承接预览读取失败')
  } finally {
    if (requestSequence === materialPreviewSequence) materialRequirementPreviewLoading.value = false
  }
}
async function loadCalculations() { if (selectedOrder.value?.isSourceTrial) { calculations.value = []; activeCalculation.value = null; return } try { const data = unwrap(await pdeApi.engineeringCalculations({ scope: 'order_engineering' })); calculations.value = data.rows || []; const selected = activeCalculation.value ? visibleCalculations.value.find(row => row.id === activeCalculation.value.id) : null; if (selected) await chooseCalculation(selected); else activeCalculation.value = null } catch (error) { ElMessage.error(explain(error, '核算记录读取失败')) } }
async function chooseSavedRecord(row) {
  if (!visibleCalculations.value.some(item => item.id === row.id)) return
  if (String(route.query.calculationRecord || '') === String(row.id)) await chooseCalculation(row)
  else await router.replace({ path: route.path, query: { ...businessPageLocation(activeBusinessPage.value).query, calculationRecord: String(row.id) } })
}
async function chooseCalculation(row) {
  const requestSequence = ++calculationDetailSequence
  const selectedLineId = selectedOrder.value?.salesOrderItemId
  const isCurrent = () => requestSequence === calculationDetailSequence && activeCalculation.value?.id === row.id && selectedOrder.value?.salesOrderItemId === selectedLineId
  activeCalculation.value = row; bomPreview.value = null; bomBlocker.value = ''; resetOperation(bomPreviewOperation)
  calculationDetailLoading.value = true; calculationDetailError.value = ''
  try {
    const detail = await readSelectedCalculationDetail(row, async id => unwrap(await pdeApi.engineeringCalculation(id)).calculation, isCurrent)
    if (detail) activeCalculation.value = detail
  } catch (error) {
    if (isCurrent()) calculationDetailError.value = explain(error, '正式记录追溯读取失败')
  } finally { if (isCurrent()) calculationDetailLoading.value = false }
}
const applicabilityText = value => Object.entries(value || {}).map(([key, item]) => `${key}=${item}`).join('；') || '未限定'
const substitutionText = value => Object.entries(value || {}).map(([key, item]) => `${inputLabel(key)}=${decimalValue(item)}${item?.unit ? ` ${item.unit}` : ''}`).join('；')
async function trialMethods() {
  busy.value = true
  methodTrial.value = null
  const attempt = methodTrialOperation.attempt + 1
  Object.assign(methodTrialOperation, { state: 'running', title: '正在试算并独立对账', message: `第${attempt}次候选方法试算已接收；不创建正式核算记录、物料需求或BOM。`, attempt })
  try {
    methodTrial.value = unwrap(await pdeApi.trialEngineeringMethods({ ...contextPayload(), ruleIds: [...selection.candidateRuleIds] }))
    const pass = methodTrial.value.trialStatus === 'PASS'
    Object.assign(methodTrialOperation, { state: pass ? 'completed' : 'failed', title: pass ? '候选方法试算与对账完成' : '候选方法存在差异', message: pass ? `第${attempt}次试算完成：系统结果与独立来源核对值及单位一致；候选方法仍待业务确认。` : `第${attempt}次试算完成：存在差异，请查看逐项结果。` })
    ElMessage[pass ? 'success' : 'warning'](methodTrialOperation.message)
  } catch (error) {
    const detail = explain(error, '候选方法试算失败')
    Object.assign(methodTrialOperation, { state: 'failed', title: '候选方法试算失败', message: detail })
    ElMessage.error(detail)
  } finally { busy.value = false }
}
async function previewBom() {
  busy.value = true
  bomBlocker.value = ''
  bomPreview.value = null
  const attempt = bomPreviewOperation.attempt + 1
  Object.assign(bomPreviewOperation, { state: 'running', title: '正在预览', message: `第${attempt}次预览操作已接收，正在调用服务端检查BOM草稿预览条件；本操作不写入BOM。`, attempt })
  try {
    bomPreview.value = unwrap(await pdeApi.previewOrderBom(activeCalculation.value.id))
    Object.assign(bomPreviewOperation, { state: 'completed', title: '本次预览已完成', message: `第${attempt}次服务端预览已完成；已返回BOM草稿预览，本操作未写入BOM。` })
    ElMessage.success(bomPreviewOperation.message)
  } catch (error) {
    const kind = failureKind(error)
    const detail = explain(error, 'BOM草稿预览失败')
    bomBlocker.value = detail
    Object.assign(bomPreviewOperation, {
      state: kind === 'business' ? 'blocked' : 'failed',
      title: kind === 'business' ? '本次预览检查已完成：预览受阻' : kind === 'permission' ? '预览权限失败' : kind === 'network' ? '预览网络失败' : '预览请求失败',
      message: kind === 'business' ? `第${attempt}次服务端预览检查已完成：${detail}；未形成BOM预览，未写入BOM。` : `第${attempt}次请求：${detail}`,
    })
    ElMessage[kind === 'business' ? 'warning' : 'error'](bomPreviewOperation.message)
  } finally { busy.value = false }
}
async function generateBom() { try { await ElMessageBox.confirm('仅生成订单BOM草稿，不发布、不进入计划。确认继续？', '明确生成草稿', { confirmButtonText: '生成草稿', cancelButtonText: '取消', type: 'warning' }) } catch { return } busy.value = true; try { const result = unwrap(await pdeApi.generateOrderBom(activeCalculation.value.id, { previewHash: bomPreview.value.previewHash, reason: '用户在PDE核算页面明确确认生成订单BOM草稿' })); writeCount.value += result.idempotent ? 0 : 1; bomPreview.value = result; ElMessage.success(result.idempotent ? '已回读同一BOM草稿，未重复生成。' : '订单BOM草稿已生成并完成回读。') } catch (error) { ElMessage.error(explain(error, 'BOM草稿生成失败')) } finally { busy.value = false } }
function openBom() { router.push({ path: '/pde/product-boms', query: { q: bomPreview.value.orderNo, sourceCalculationId: activeCalculation.value.id } }) }
function diagnostics() { return { pageCode: 'pde-order-engineering-calculation', factSource: 'server', accessMode: accessMode.value, permissionFacts: { ruleView: permissionAllowed(RULE_VIEW_PERMISSION), calculationView: permissionAllowed(CALCULATION_VIEW_PERMISSION), organizationId: permissionProfile.value?.organization?.id || null }, restrictedCalculationFactsRequested: ruleOnlyEntryMode.value ? false : null, readiness: readiness.value, formalContinuation: formalContinuation.value, conditionPreflight: conditionPreflight.value, formalValidation: formalValidation.value, validation: validation.value, activeCalculation: activeCalculation.value, engineeringWorkloadSummary: engineeringWorkloadFacts.value, engineeringWorkloadReadState: engineeringWorkloadFacts.value?.readStatus || engineeringWorkloadReadState.value, engineeringWorkloadReadError: engineeringWorkloadDisplayError.value, materialRequirementHandoff: materialRequirementHandoff.value, bomPreview: bomPreview.value, localStorageFormalFactCount: 0, writeCount: writeCount.value } }
let sequence = 0
async function refresh() {
  resetMainContinuationPreview()
  const current = ++sequence
  calculationDetailSequence += 1; activeCalculation.value = null; calculationDetailLoading.value = false; calculationDetailError.value = ''; formalContinuation.value = {}; conditionPreflight.value = { blockers:[] }
  loading.value = true; loadError.value = ''; initialReadFailure.value = null; auxiliaryReadNotice.value = ''; accessMode.value = 'loading'
  try {
    activeBusinessPage.value = resolveBusinessPage(route.query.page)
    if (route.query.subview) resolveFoundationPageState(route)
    permissionProfile.value = await loadPermissionProfile({ force: true })
    if (current !== sequence) return
    const canViewCalculation = permissionAllowed(CALCULATION_VIEW_PERMISSION)
    const canViewRules = permissionAllowed(RULE_VIEW_PERMISSION)
    if (!canViewCalculation) {
      accessMode.value = canViewRules ? 'rules-only' : 'denied'
      readiness.value = {}; calculations.value = []; formalContinuation.value = {}; conditionPreflight.value = { blockers: [] }
      selection.salesOrderItemId = null; selection.ruleIds = []; selection.candidateRuleIds = []
      workbookSources.value = []; selectedWorkbookSourceRecordId.value = ''; workbookSourcesError.value = ''
      return
    }
    accessMode.value = 'calculation'
    selectedWorkbookSourceRecordId.value = route.query.calculationRecord ? '' : String(route.query.workbookSourceRecordId ?? '')
    workbookSourcesLoading.value = true; workbookSourcesError.value = ''; workbookSources.value = []; workbookSourceIntake.value = {}
    try {
      const workbookCatalog = validateWorkbookCatalog(unwrap(await pdeApi.calculationBatchCatalog({ action:'workbookSources' })))
      if (current !== sequence) return
      workbookSources.value = workbookCatalog.workbookSources
      workbookSourceIntake.value = { sourceIntakeAllowed:workbookCatalog.sourceIntakeAllowed,sourceIntakeStatusLabel:workbookCatalog.sourceIntakeStatusLabel }
      if (selectedWorkbookSourceRecordId.value && !selectedWorkbookSource.value) throw new Error('所选工作簿来源已失效或不在当前公司及权限范围内；未切换为其他来源。')
    } catch (error) { if (current === sequence) workbookSourcesError.value = explain(error, '工作簿来源目录读取失败，选择资格未知'); throw error }
    finally { if (current === sequence) workbookSourcesLoading.value = false }
    const params = { readAt: Date.now(), ...(configurationSubview.value ? { subview: route.query.subview } : {}),...(selectedWorkbookSourceRecordId.value ? { workbookSourceRecordId:Number(selectedWorkbookSourceRecordId.value) } : {}) }
    const data = unwrap(await pdeApi.engineeringCalculationReadiness(params))
    if (current !== sequence) return
    readiness.value = data
    if (!configurationSubview.value) {
      selection.ruleIds = rules.value.map(row => row.id)
      selection.candidateRuleIds = candidateMethods.value.map(row => row.id)
      await loadUnboundDrafts()
      if (current !== sequence) return
      const requestedSourceRecordId = String(route.query.sourceRecord || '')
      const requestedSource = sourceTrialOrders.value.find(row => String(row.sourceRecordId) === requestedSourceRecordId)
      const requestedOrderId = Number(route.query.order || 0)
      if (requestedOrderId > 0 && !orders.value.some(row => row.salesOrderItemId === requestedOrderId)) throw new Error('所选订单行不存在或不在当前读取范围内，未保留上一订单资料。')
      const requestedOrderNo = String(route.query.orderNo || '')
      const requestedFormalOrder = orders.value.find(row => !row.isSourceTrial && row.orderNo === requestedOrderNo)
      const legacySource = requestedOrderId === -1 ? sourceTrialOrders.value.find(row => row.draft?.rows?.length === 1 && Number(row.draft?.rows?.[0]?.sourceRow) === 36) : null
      if (requestedSource) selection.salesOrderItemId = requestedSource.salesOrderItemId
      else if (legacySource) selection.salesOrderItemId = legacySource.salesOrderItemId
      else if (orders.value.some(row => row.salesOrderItemId === requestedOrderId)) selection.salesOrderItemId = requestedOrderId
      else if (requestedFormalOrder) selection.salesOrderItemId = requestedFormalOrder.salesOrderItemId
      else if (!orders.value.some(row => row.salesOrderItemId === selection.salesOrderItemId)) {
        selection.salesOrderItemId = null
      }
      if (!route.query.calculationRecord && activeBusinessPage.value === 'results' && selectedOrder.value && !selectedOrder.value.isSourceTrial) {
        const wholeOrder = linkedWholeOrderSummary(selectedOrder.value.orderNo)
        if (wholeOrder) selection.salesOrderItemId = wholeOrder.salesOrderItemId
      }
      if (selectedOrder.value && !selectedOrder.value.isSourceTrial) {
        const restoredTarget = resolveFormalSummaryReturnTarget({ routeQuery: route.query, summaries: sourceTrialOrders.value, selectedLine: selectedOrder.value })
        formalSummaryReturnContext.value = restoredTarget ? { ...restoredTarget, summary: undefined } : null
      } else if (selectedOrder.value?.isSourceTrial) formalSummaryReturnContext.value = null
      activeCalculation.value = null; formalValidation.value = { ready: false, blockers: [] }; seedDraftRows()
      const contextDraft = selectedOrder.value?.draft
      drafts.value = contextDraft ? [contextDraft] : []
      if (contextDraft) { activeDraftId.value = String(contextDraft.id); openDraft({ syncUrl: false }); engineeringWorkloadLoadedScope.value = engineeringWorkloadScope.value; engineeringWorkloadReadState.value = contextDraft.engineeringWorkloadSummary?.readStatus === 'not_requested' ? 'not_requested' : 'loaded'; engineeringWorkloadReadError.value = '' }
      const requestedDraft = drafts.value.find(row => row.sourceVersion === requestedEngineeringVersion.value)
      if (requestedDraft) { activeDraftId.value = String(requestedDraft.id); openDraft({ syncUrl: false }) }
      if (selectedOrder.value?.isSourceTrial && activeBusinessPage.value === 'scheduling') {
        await loadDrafts({ syncUrl: false })
        if (current !== sequence) return
      }
      await Promise.all([loadCalculations(), loadFormalContinuation(), loadMaterialRequirementPreview()])
      if (selection.salesOrderItemId) {
        const requestedRecord = route.query.calculationRecord
        const selected = requestedRecord ? visibleCalculations.value.find(row => String(row.id) === String(requestedRecord)) : visibleCalculations.value.find(row => row.status === 'completed')
        if (requestedRecord && !selected) throw new Error('所选核算记录不属于当前订单行，已停止展示，不切换到其他记录。')
        if (selected) await chooseCalculation(selected)
      }
    }
  } catch (error) {
    if (current !== sequence) return
    accessMode.value = 'failed'
    loadError.value = explain(error, '工程核算事实加载失败'); initialReadFailure.value = error.readFailure || null
    if (isAuthenticationFailure(error) && route.path !== '/system-login') await router.replace({ path: '/system-login', query: { redirect: route.fullPath, reason: 'pde-server-authentication-required' } })
  } finally { if (current === sequence) { loading.value = false; updateDocumentTitle() } }
}
async function selectWorkbookSource() {
  resetMainContinuationPreview()
  loading.value = true
  formalReadSequence += 1; draftReadSequence += 1; calculationDetailSequence += 1; materialPreviewSequence += 1
  activeCalculation.value = null
  const query = { ...route.query }
  if (selectedWorkbookSourceRecordId.value) query.workbookSourceRecordId = selectedWorkbookSourceRecordId.value
  else delete query.workbookSourceRecordId
  if (String(route.query.workbookSourceRecordId ?? '') === selectedWorkbookSourceRecordId.value) await refresh()
  else await router.replace({ path:route.path,query })
}
watch([selectedBaselineId, selectedPredecessorCalculationId, () => selection.salesOrderItemId, () => formalContinuation.value], resetMainContinuationPreview, { flush: 'sync' })
watch(selectedWorkbookSourceRecordId, resetMainContinuationPreview, { flush:'sync' })
watch(() => route.fullPath, refresh)
const titleOwner = Symbol('engineering-calculation')
const titleRoute = '/pde/engineering-calculations'
let titleActive = true
function updateDocumentTitle() {
  if (!titleActive || route.path !== titleRoute) return
  setDynamicPageTitle(route, titleOwner, `${ruleOnlyEntryMode.value ? '工程规则入口' : activePageDefinition.value.label}${selectedOrder.value?.orderNo ? ` · ${selectedOrder.value.orderNo}` : ''}｜PCE`)
}
async function checkForNewVersion() { if (selectedOrder.value?.isSourceTrial) await loadUnboundDrafts(); if (selectedOrder.value?.orderEngineeringInstanceId || selectedOrder.value?.isSourceTrial) await loadDrafts() }
watch([activeBusinessPage, selectedOrder], updateDocumentTitle)
let provider
onMounted(async () => { provider = { factOwner: 'pde-order-engineering-calculation', refresh, buildDiagnostics: diagnostics }; observability?.register?.(provider); window.addEventListener('focus', checkForNewVersion); await refresh(); updateDocumentTitle() })
onBeforeUnmount(() => {
  titleActive = false
  clearDynamicPageTitle(titleRoute, titleOwner)
  window.removeEventListener('focus', checkForNewVersion)
  observability?.unregister?.(provider)
})
</script>

<style scoped>
.workbook-source-context{overflow-wrap:anywhere}.workbook-source-context label{min-width:0;max-width:100%}.workbook-source-context select{max-width:100%}.workbook-source-context>span{min-width:0;max-width:100%}

[data-section="scheduling-summary"]{min-width:0}
[data-section="scheduling-summary"]>header>div{min-width:0}
[data-section="scheduling-summary"] :deep(.pce-business-status){max-width:100%;white-space:normal;overflow-wrap:anywhere}
.engineering-workload-trace{max-width:220px;white-space:normal;overflow-wrap:anywhere;text-align:left}.engineering-workload-trace>summary{color:#17676c;font-weight:700;cursor:pointer}.engineering-workload-trace p{margin:7px 0}.engineering-workload-trace small{display:block;color:#637189}.engineering-workload-trace article{margin-top:10px;padding-top:8px;border-top:1px solid #dbe4ef}
.design-source-contract{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-top:18px;padding:16px;border:1px solid #9fc7b2;border-radius:10px;background:#eef9f3}.design-source-contract p{margin:6px 0 0;color:#315b4a}.primary-action{flex:none;padding:10px 14px;border-radius:8px;color:#fff;background:#17676c;text-decoration:none;font-weight:700}
.calculation-page{padding:20px;min-width:0;color:#17233a;background:#f4f7fb}.breadcrumb,.mode-tabs,.actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}.breadcrumb a,.mode-tabs a{color:#17676c;text-decoration:none}.hero,.card,.notice{border:1px solid #d9e2ec;border-radius:14px;background:#fff;padding:20px 22px;margin-bottom:16px}.hero,.card>header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.hero{color:#fff;background:linear-gradient(135deg,#173c6a,#17676c)}.hero p,.hero h1,.hero small,.card h2,.card p{margin:0}.hero h1{margin:5px 0 8px}.hero-state{display:grid;gap:8px;text-align:right}.environment-banner{display:flex;justify-content:space-between;gap:18px;margin-bottom:16px;padding:14px 18px;border:2px solid;border-radius:12px}.environment-banner.safe{color:#125a3b;border-color:#58a77e;background:#e8f7ee}.environment-banner.error{color:#8a251c;border-color:#d87870;background:#fff0ef}.environment-banner>div{display:grid;gap:4px}.environment-banner dl,.case-summary dl{display:flex;gap:18px;flex-wrap:wrap;margin:0}.environment-banner dl div,.case-summary dl div{display:grid;gap:3px}.environment-banner dt,.case-summary dt{font-size:12px;font-weight:700}.environment-banner dd,.case-summary dd{margin:0}.mode-tabs a{padding:9px 13px;border:1px solid #afd1cf;border-radius:9px;background:#fff;font-weight:700}.mode-tabs a.router-link-exact-active{color:#fff;background:#17676c}.card>header{margin-bottom:14px}.pill{padding:6px 10px;border-radius:999px;white-space:nowrap;background:#eef3f7}.pending{color:#855b00;background:#fff3d5}.pass,.pass-box{color:#17643a;background:#e5f6ec}.error{border-left:5px solid #b42318;background:#fff3f2}.empty{background:#f7f9fc}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-bottom:14px}.form-grid label{display:grid;gap:6px;font-weight:700}.form-grid input,.form-grid select{box-sizing:border-box;width:100%;padding:10px;border:1px solid #b9c7d8;border-radius:8px;background:#fff;font:inherit}.case-summary,.material-contract{display:grid;gap:10px;margin:14px 0;padding:14px;border:1px solid #93c5c2;border-radius:10px;background:#f1faf9}.material-contract span,.material-contract small{display:block}.input-table,.rule-table{margin:14px 0}.record-meta{display:flex;gap:16px;flex-wrap:wrap;margin:14px 0;padding:10px 12px;border-radius:8px;background:#eef3f7;font-weight:700}.blocked-copy{padding:10px;border-left:4px solid #d69a22;background:#fff8e7}.operation-feedback{margin:12px 0;padding:12px 14px;border:1px solid;border-radius:10px}.operation-feedback p{margin-top:5px}.operation-feedback.running{color:#315b7e;border-color:#9bb8d1;background:#eef6fc}.operation-feedback.completed{color:#17643a;border-color:#8bc5a3;background:#e5f6ec}.operation-feedback.blocked{color:#855b00;border-color:#e0ba68;background:#fff8e7}.operation-feedback.failed{color:#8a251c;border-color:#d87870;background:#fff0ef}fieldset{border:1px solid #d7e0eb;border-radius:10px}.check{display:flex;gap:8px;align-items:center;margin:8px 0}button{padding:9px 14px;border:0;border-radius:8px;color:#fff;background:#17676c;font-weight:700;cursor:pointer}button.secondary{color:#17676c;border:1px solid #78aaa7;background:#fff}button.link{padding:0;color:#17676c;background:transparent}button:disabled{opacity:.45;cursor:not-allowed}.table-wrap{overflow:auto;border:1px solid #dbe4ef;border-radius:10px}table{width:100%;min-width:900px;border-collapse:collapse}th,td{padding:10px 12px;border-bottom:1px solid #e5ebf2;text-align:left;vertical-align:top}th{background:#f3f7fb;color:#315b7e}td small,th small{display:block;margin-top:4px;color:#637189}tr.selected{background:#eef8f7}.error-text{color:#b42318}.result-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:16px}.result-grid article{padding:14px;border:1px solid #dbe4ef;border-radius:10px}.result-grid dl{padding:10px;background:#f6f8fb}.result-grid dt{font-weight:700}.result-grid dd{margin:4px 0}.boundary{margin-top:14px!important;padding:12px;border-left:4px solid #d69a22;background:#fff8e7}@media(max-width:760px){.hero,.card>header,.environment-banner{flex-direction:column}.form-grid,.result-grid{grid-template-columns:1fr}.calculation-page{padding:10px}}
.business-page-tabs,.workshop-tabs{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}.business-page-tabs button,.workshop-tabs button{color:#17676c;border:1px solid #78aaa7;background:#fff}.business-page-tabs button.active,.workshop-tabs button.active{color:#fff;background:#17676c}.order-context-strip{display:flex;align-items:end;gap:18px;flex-wrap:wrap;margin-bottom:16px;padding:13px 16px;border:1px solid #c8d7e5;border-radius:10px;background:#fff}.order-context-strip label{display:grid;gap:5px;font-weight:700}.order-context-strip select,.reason-field input,.actions select{padding:8px;border:1px solid #b9c7d8;border-radius:7px;background:#fff}.engineering-editor{margin-top:18px;padding-top:18px;border-top:1px solid #dbe4ef}.engineering-editor>header{display:flex;justify-content:space-between;gap:16px}.engineering-editor table{min-width:2100px}.engineering-editor td input,.engineering-editor td select{box-sizing:border-box;width:100%;min-width:105px;margin-bottom:4px;padding:7px;border:1px solid #c5d1de;border-radius:6px}.import-button{padding:9px 14px;border:1px solid #78aaa7;border-radius:8px;color:#17676c;background:#fff;font-weight:700;cursor:pointer}.import-button input{display:none}.reason-field{display:grid;gap:6px;margin:14px 0;font-weight:700}
.formal-card-action{display:flex;width:max-content;max-width:100%;min-height:38px;margin-top:13px;padding-inline:16px;font-size:14px;font-weight:700}
.rule-entry-card{margin-bottom:16px;padding:20px 22px;border:1px solid #89b8b5;border-radius:14px;background:#f1faf9}.rule-entry-card>header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.rule-entry-card h2,.rule-entry-card p{margin:0}.rule-entry-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}.rule-entry-facts>div{padding:12px;border:1px solid #c5dddb;border-radius:9px;background:#fff}.rule-entry-facts dt{color:#52637a;font-size:12px;font-weight:700}.rule-entry-facts dd{margin:5px 0 0;font-weight:700}.rule-entry-card .actions{margin-bottom:0}.rule-entry-card .actions a{align-self:center}
.workspace-header{display:flex;justify-content:space-between;gap:24px;margin-bottom:14px;padding:18px 20px;border:1px solid #d4dee9;border-radius:12px;background:#fff}.workspace-header h1{margin:6px 0;font-size:24px}.workspace-header p{margin:0;color:#52637a}.workspace-header dl{display:grid;grid-template-columns:repeat(2,minmax(130px,1fr));gap:10px 18px;margin:0;min-width:390px}.workspace-header dl div{display:grid;gap:3px}.workspace-header dt{font-size:12px;color:#637189}.workspace-header dd{margin:0;font-weight:700}.eyebrow{display:flex;align-items:center;gap:10px;color:#52637a;font-size:13px}.environment-chip{padding:4px 8px;border-radius:999px;font-weight:700}.environment-chip.safe{color:#17643a;background:#e5f6ec}.environment-chip.error{color:#8a251c;background:#fff0ef}.business-page-tab{display:flex;align-items:stretch;border:1px solid #c4d2df;border-radius:9px;background:#fff;overflow:hidden}.business-page-tab>button{border:0;border-radius:0;padding:10px 13px}.business-page-tab>.new-tab-action{display:flex;align-items:center;padding:0 9px;border-left:1px solid #d8e1ea;color:#52637a;background:#f7f9fc;text-decoration:none;font-size:11px;font-weight:600}.business-page-tab>button.active+.new-tab-action{border-left-color:#4f8688}.environment-details,.auxiliary-panel{margin-bottom:14px;border:1px solid #d7e0eb;border-radius:10px;background:#fff}.environment-details>summary,.auxiliary-panel>summary{padding:11px 14px;color:#315b7e;font-weight:700;cursor:pointer}.detail-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:0 14px 12px}.related-navigation{display:flex;gap:12px;flex-wrap:wrap;padding:0 14px 12px}.related-navigation a{color:#17676c}.context-actions{display:flex;gap:8px;margin-left:auto}.context-actions details{position:relative}.context-actions details>summary{padding:8px 12px;border:1px solid #78aaa7;border-radius:7px;color:#17676c;font-weight:700;cursor:pointer}.context-actions details[open]{display:grid;gap:8px;padding:0 8px 8px;border-radius:8px;background:#f3f7fb}.stale-notice{display:flex;gap:10px;align-items:center;margin-bottom:14px;padding:11px 14px;border-left:4px solid #d69a22;border-radius:8px;background:#fff8e7;color:#6f4d00}.details-body{padding:0 14px 14px}.primary-workspace{border-top:4px solid #17676c}.work-order-table table{min-width:1700px}.inline-detail{margin-top:7px;padding:7px;border-radius:6px;background:#fff8e7;color:#6f4d00}.fact-line{display:block;white-space:nowrap}.empty-state{display:grid;gap:9px;padding:22px;border:1px dashed #b8c6d5;border-radius:10px;background:#f8fafc;color:#52637a}.empty-state strong{color:#24364f;font-size:16px}.empty-state a,.actions a{width:max-content;color:#17676c;font-weight:700}.compact-blocker{margin-top:12px;padding:12px 14px;border-left:4px solid #d69a22;border-radius:8px;background:#fff8e7}.compact-blocker p{margin:5px 0}.engineering-editor td input.missing,.engineering-editor td select.missing{border-color:#d69a22;background:#fffaf0}.card.auxiliary-panel{padding:0}.card.auxiliary-panel>summary{list-style-position:inside}.card.auxiliary-panel[open]>summary{border-bottom:1px solid #e1e8f0}.card.auxiliary-panel .details-body>header{display:flex;justify-content:space-between;gap:16px;margin:14px 0}.pass-text{color:#17643a}.table-wrap details summary{color:#17676c;font-weight:700;cursor:pointer}.table-wrap details p{margin:7px 0}.order-context-strip>span{padding-bottom:8px}.mode-tabs,.hero,.environment-banner{display:none}@media(max-width:900px){.workspace-header{flex-direction:column}.workspace-header dl{min-width:0}.detail-grid{grid-template-columns:1fr}}@media(max-width:760px){.workspace-header dl{grid-template-columns:1fr}.stale-notice{align-items:flex-start;flex-direction:column}}
.assignment-grid{display:grid;grid-template-columns:repeat(4,minmax(180px,1fr));gap:12px;margin:14px 0;padding:14px;border:1px solid #dbe4ef;border-radius:10px;background:#f8fafc}.assignment-grid label{display:grid;gap:6px;font-weight:700}.assignment-grid select{width:100%;padding:8px;border:1px solid #b9c7d8;border-radius:7px;background:#fff}.assignment-grid small{color:#637189;font-weight:400}.production-plan{margin-top:18px;padding-top:18px;border-top:1px solid #dbe4ef}.production-plan>header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:12px}.production-plan h3,.production-plan p{margin:0}.production-plan table{min-width:900px}.production-plan>details{margin-top:10px;color:#52637a}.production-plan>details summary{color:#17676c;font-weight:700;cursor:pointer}@media(max-width:1000px){.assignment-grid{grid-template-columns:repeat(2,minmax(180px,1fr))}}@media(max-width:760px){.assignment-grid{grid-template-columns:1fr}.production-plan>header{flex-direction:column}}
.source-result-workspace{margin-top:18px;padding-top:18px;border-top:1px solid #dbe4ef}.source-result-workspace>header{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;margin-bottom:12px}.source-result-workspace h3,.source-result-workspace p{margin:0}.source-result-table{max-height:520px}.source-result-table table{min-width:1050px}
.confirmed-facts{display:grid;gap:6px;margin:10px 0 14px;padding:12px 14px;border-left:4px solid #315bcf;border-radius:8px;background:#eef3fb}.confirmed-facts span{color:#3e536d}.result-stat-strip{display:flex;gap:9px;flex-wrap:wrap;margin:0 0 12px}.result-stat-strip span{padding:7px 10px;border-radius:999px;background:#eef3f7;font-weight:700}.acceptance-comparison{margin-bottom:12px;border:1px solid #dbe4ef;border-radius:9px}.acceptance-comparison>summary{padding:10px 12px;color:#17676c;font-weight:700;cursor:pointer}.acceptance-comparison .table-wrap{border-width:1px 0 0;border-radius:0}.acceptance-comparison table{min-width:1050px}
.current-comparison{margin-bottom:12px;padding:14px;border:1px solid #93c5c2;border-radius:10px;background:#f1faf9}.current-comparison h4{margin:0 0 10px}.comparison-regression-status{margin:0 0 12px;color:#17676c;font-weight:700}.comparison-actions{display:flex;gap:8px;flex-wrap:wrap}.difference-explanation{margin:12px 0 0;padding:10px;border-left:4px solid #d69a22;background:#fff8e7}.comparison-result-table{margin-bottom:12px}.comparison-result-table table{min-width:1480px}
.formal-continuation{margin:16px 0;padding:16px;border:1px solid #89b8b5;border-radius:12px;background:#f1faf9}.formal-continuation>header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:13px}.formal-continuation h3,.formal-continuation p{margin:0}.formal-continuation-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.formal-continuation-grid>div,.formal-continuation-grid>label{display:grid;align-content:start;gap:5px;padding:11px;border:1px solid #c5dddb;border-radius:9px;background:#fff}.formal-continuation-grid span,.formal-continuation-grid select{font-weight:700}.formal-continuation-grid select{width:100%;padding:7px;border:1px solid #b9c7d8;border-radius:7px;background:#fff}.formal-continuation-grid small{color:#52637a}.formal-continuation-grid a{color:#17676c}.formal-actions{margin-top:13px}.boundary-note{margin-top:12px!important;padding:10px 12px;border-left:4px solid #d69a22;background:#fff8e7;color:#6f4d00}
.material-requirement-preview{margin-top:4px}.material-preview-table{margin-top:12px}.material-preview-table table{min-width:1120px}.material-preview-table td small{display:block;margin-top:4px;color:#52637a}.material-requirement-preview>details{margin-top:12px}.material-requirement-preview>details>summary{color:#17676c;font-weight:700;cursor:pointer}.material-requirement-preview>details p{margin:8px 0;color:#52637a}
.business-confirmation-package{margin-top:14px;padding:14px;border:1px solid #d8b56a;border-radius:10px;background:#fffdf7}.business-confirmation-package>header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:12px}.business-confirmation-package h4,.business-confirmation-package p{margin:0}.business-confirmation-package>details{margin-top:12px}.business-confirmation-package>details>summary{color:#795719;font-weight:700;cursor:pointer}.business-confirmation-package>details>p{margin:8px 0;color:#52637a}
.fact-option-list{margin-top:7px}.fact-option-list>summary{cursor:pointer;color:#17676c;font-weight:700}.fact-option-list small{font-weight:400}
.formal-header-actions{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;justify-content:flex-end}.formal-summary-return{display:grid;gap:2px;min-height:46px;padding:8px 14px;text-align:left}.formal-summary-return small{font-size:11px;font-weight:500}.formal-lines-table table{min-width:1120px}.formal-lines-table .formal-line-action{position:sticky;right:0;z-index:3;min-width:190px;background:#f8fafc;box-shadow:-2px 0 4px rgba(36,54,79,.12)}.formal-lines-table thead .formal-line-action{z-index:5;background:#eaf1f8}.formal-lines-table tbody .formal-line-action{background:#fff}.line-detail-action{display:block;width:100%;min-height:42px;padding:8px 12px;white-space:normal}.formal-line-action>small{display:block;margin-top:4px;text-align:center}
.line-condition-trigger{display:block;margin-top:6px}.line-condition-detail{margin-top:14px;padding:16px;border:1px solid #89b8b5;border-radius:12px;background:#f1faf9}.line-condition-detail>header{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.line-condition-detail h4,.line-condition-detail p{margin:0}.line-condition-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.line-condition-grid>div{padding:11px;border:1px solid #c5dddb;border-radius:9px;background:#fff}.line-condition-grid dt{color:#52637a;font-size:12px;font-weight:700}.line-condition-grid dd{margin:4px 0;font-weight:700}.line-condition-grid small,.line-condition-permissions small{display:block;margin-top:4px;color:#637189}.line-condition-permissions{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-bottom:12px}.line-condition-permissions>strong{grid-column:1/-1}.line-condition-permissions>span{padding:9px;border-radius:8px;background:#fff}.line-condition-pending{padding:11px 13px;border-left:4px solid #d69a22;background:#fff8e7}.line-condition-pending ul{margin:7px 0 0;padding-left:20px}
.table-wrap thead th{position:sticky;top:0;z-index:2;background:#f3f7fb}.table-wrap tbody th{position:static}
.governed-scroll-table{max-height:min(64vh,620px);overflow:auto;overscroll-behavior:contain;scrollbar-gutter:stable}.governed-scroll-table .sticky-sequence{position:sticky;left:0;box-sizing:border-box;width:64px;min-width:64px;max-width:64px;text-align:center;background:#f8fafc;z-index:3}.governed-scroll-table .sticky-identity{position:sticky;left:64px;min-width:150px;background:#fff;z-index:3;box-shadow:1px 0 0 #dbe4ef}.governed-scroll-table thead .sticky-sequence,.governed-scroll-table thead .sticky-identity{z-index:5;background:#eaf1f8}.governed-scroll-table tbody tr:hover .sticky-sequence,.governed-scroll-table tbody tr:hover .sticky-identity{background:#f1f7fb}
@media(max-width:900px){.formal-continuation-grid{grid-template-columns:1fr 1fr}}
@media(max-width:1100px){.line-condition-grid{grid-template-columns:1fr 1fr}.line-condition-permissions{grid-template-columns:1fr 1fr}}
@media(max-width:700px){.formal-continuation>header{flex-direction:column}.formal-continuation-grid{grid-template-columns:1fr}.governed-scroll-table .sticky-sequence{width:44px;min-width:44px;max-width:44px}.governed-scroll-table .sticky-identity{left:44px;width:84px;min-width:84px;max-width:84px;white-space:normal;overflow-wrap:anywhere}.governed-scroll-table .sticky-identity select{width:84px;min-width:0;max-width:84px}}
@media(max-width:700px){.line-condition-detail>header{flex-direction:column}.line-condition-grid,.line-condition-permissions{grid-template-columns:1fr}}
.formal-saved-trace{margin:12px 0;padding:12px;border:1px solid #c5dddb;border-radius:9px;background:#f1faf9;overflow-wrap:anywhere}
.formal-saved-trace dl{display:grid;grid-template-columns:minmax(100px,150px) minmax(0,1fr);gap:8px;margin:10px 0}.formal-saved-trace dt{font-weight:700}.formal-saved-trace dd{margin:0;white-space:normal;min-width:0}
.calculation-input-trace{min-width:240px;max-width:620px;white-space:normal;overflow-wrap:anywhere}.calculation-input-trace p{margin:5px 0;white-space:normal}
@media(max-width:700px){.formal-saved-trace dl{grid-template-columns:minmax(0,1fr)}.formal-saved-trace dd{margin-bottom:8px}}
</style>


