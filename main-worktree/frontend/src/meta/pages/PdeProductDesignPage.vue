<template>
  <PceListPageShell
    module-id="pde-product-definitions"
    :governance="governance"
    :page-refresh-handler="refresh"
    :page-refresh-status="refreshStatus"
    :page-last-refresh-time="lastRefreshTime"
  >
    <div class="design-page" data-acceptance-id="pde-product-design-page" data-fact-source="server">
      <section class="card" data-acceptance-id="product-design-order-selection">
        <label for="product-design-order">选择产品设计订单</label>
        <select id="product-design-order" aria-label="选择产品设计订单" :value="selectedOrderNo" :disabled="refreshStatus === 'refreshing'" @change="selectDesignOrder">
          <option value="">请选择订单，不自动采用上一单</option>
          <option v-for="order in orderOptions" :key="order.orderId" :value="order.orderNo">{{ order.orderNo }} · {{ order.customer }} · {{ order.designItemCount }}项设计</option>
        </select>
        <p v-if="refreshStatus === 'awaiting-order'">{{ orderOptions.length ? '请先明确选择订单；选单后地址将记录订单，刷新仍读取同一订单。' : '当前公司没有可查看的已建产品设计订单；尚未准备的合法实例请从工程准备的本单入口进入。' }}</p>
      </section>
      <section class="card context-card">
        <div class="section-heading">
          <div><small>当前订单产品设计管理</small><h2>{{ loadError ? (route.query.orderNo || '读取失败') : (orderContext.orderNo || (refreshStatus === 'refreshing' ? '正在读取…' : '请选择订单')) }}</h2></div>
          <span class="nature">已有设计补齐流程</span>
        </div>
        <div class="context-grid">
          <article><small>客户 / 项目</small><strong>{{ orderContext.customer || '-' }} / {{ sourceContext.projectName || '-' }}</strong></article>
          <article><small>来源订单 / 版本</small><strong>{{ orderContext.sourceOrderNo || '-' }} / {{ sourceContext.sourceVersion || '-' }}</strong></article>
          <article><small>PDE评审</small><strong>{{ reviewContext.conclusionLabel || '-' }} · {{ reviewContext.signatureLabel || '-' }}</strong></article>
          <article><small>设计项 / 分组</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.recordCount ?? rows.length}项 / ${groups.length}组` : '数量未知' }}</strong></article>
          <article><small>计划已登记</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.plannedCount || 0}项` : '—' }}</strong></article>
          <article><small>已有完成事实</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.completedFactCount || 0}项` : '—' }}</strong></article>
          <article><small>完成日期已登记</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.datedCompletionCount || 0}项` : '—' }}</strong></article>
          <article><small>纳入真实绩效</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.performanceIncludedCount || 0}项` : '—' }}</strong></article>
          <article><small>已关联正式产品</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.formalProductLinkedCount || 0}项` : '—' }}</strong></article>
          <article><small>来源产品待正式化</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.sourceProductUnformalizedCount || 0}项` : '—' }}</strong></article>
          <article><small>客户定制工程对象</small><strong>{{ refreshStatus === 'success' ? `${strictFacts.customerEngineeringCount || 0}项` : '—' }}</strong></article>
        </div>
        <div class="quantity-definition" data-acceptance-id="product-design-quantity-definition">
          <strong>数量字段说明</strong>
          <span><b>商业数量：</b>销售合同数量，例如合同购买 1 套。</span>
          <span><b>实物数量：</b>实际设计、生产对象数量，例如柜门 6 件、侧板 2 件、层板 3 件。</span>
          <small>两种数量分别表达，禁止混算。</small>
        </div>
        <p class="boundary-note"><b>职责边界：</b>本页维护 Customer Engineering（客户订单工程设计），不是标准产品主数据。无正式产品定义仍可完成工程录入、核算和设计评审；来源名称不会自动成为正式产品。标准产品发布、标准BOM和标准制造引用必须另行满足 ProductDefinition + ProductVersion 及工程发布资格。工程数据录入只负责转换、核算、校验和输出，不再编辑第二套设计事实。</p>
      </section>

      <section v-if="route.query.orderEngineeringInstanceId && refreshStatus === 'success'" class="card">
        <p>操作顺序：首次准备 → 选择设计项、填写并保存 → 刷新核对。本单保留测试模拟性质，不自动登记设计完成、基线、发布或制造输出。</p>
        <el-button v-if="!rows.length" type="primary" :loading="saving" @click="prepareItems">首次准备本单设计项</el-button>
      </section>
      <section v-if="loadError" class="card error-card">
        <el-alert :title="`读取失败，当前数据数量未知。${loadError}`" type="error" show-icon :closable="false" />
        <el-button @click="refresh">重新读取</el-button>
      </section>

      <section v-else-if="refreshStatus === 'refreshing' || refreshStatus === 'idle'" class="card" data-state="loading">
        <el-alert title="正在读取产品设计服务端事实…" type="info" show-icon :closable="false" />
      </section>

      <section v-else-if="refreshStatus === 'success'" class="card group-card" data-acceptance-id="product-design-group-summary">
        <div class="section-heading"><div><small>订单行设计分组</small><h2>{{ groups.length }}个商业分组 · {{ rows.length }}个具体设计项</h2></div><span>当前服务端范围</span></div>
        <div class="group-grid">
          <article v-for="group in groups" :key="group.groupNo">
            <strong>{{ group.groupNo }}</strong><span>{{ group.productName }}</span>
            <small>设计项 {{ group.productItemCount }} · 已有完成 {{ group.completedItemCount }} · 有日期 {{ group.datedCompletionCount }}</small>
            <small>商业数量 {{ group.commercialQuantity }} {{ group.commercialUom }}（不与设计项数混算）</small>
          </article>
        </div>
      </section>

      <section v-if="refreshStatus === 'success'" class="card operation-card">
        <el-tabs v-model="activeSection">
          <el-tab-pane label="一、产品设计计划" name="plan">
            <div class="operation-intro"><strong>产品设计计划</strong><span>计划对象为销售订单 + 产品设计分组，不要求选择单个产品。</span></div>
            <div class="batch-steps"><strong>1 选择设计分组</strong><span>→</span><strong>2 选择设计负责人</strong><span>→</span><strong>3 填写计划开始/完成日期</strong><span>→</span><strong>4 保存该设计分组计划</strong></div>
            <el-form-item label="产品设计分组" class="wide design-group-scope" data-acceptance-id="product-design-plan-scope">
              <el-checkbox-group v-model="selectedDesignGroups">
                <el-checkbox v-for="group in groups" :key="group.designGroup" :value="group.designGroup" :label="group.designGroup">{{ group.designGroup }} · {{ group.productName }}</el-checkbox>
              </el-checkbox-group>
            </el-form-item>
            <div class="batch-preview" data-acceptance-id="product-design-plan-impact">
              <strong>当前计划影响：{{ plannedImpactCount }} 个设计项</strong>
              <span v-for="group in groups" :key="group.designGroup">{{ group.designGroup }}：{{ group.productItemCount }}项</span>
            </div>
            <el-alert v-if="!selectedDesignGroups.length" title="请选择需要安排计划的产品设计分组" type="info" :closable="false" show-icon />
            <div v-if="lastPlanSaveSummary" class="batch-preview" data-acceptance-id="product-design-plan-save-summary"><strong>最近保存：已安排 {{ lastPlanSaveSummary.groupCount }} 个设计范围、影响 {{ lastPlanSaveSummary.itemCount }} 项</strong><span>设计师：{{ lastPlanSaveSummary.designer }}</span><span>日期：{{ lastPlanSaveSummary.start }} 至 {{ lastPlanSaveSummary.finish }}</span></div>
            <el-table :data="groups" border stripe class="plan-register" data-acceptance-id="product-design-plan-register">
              <el-table-column prop="designGroup" label="设计分组" width="130" />
              <el-table-column label="设计负责人" min-width="160"><template #default="{ row }">{{ row.plan?.designer?.fullName || '未登记' }}</template></el-table-column>
              <el-table-column label="计划开始日期" width="150"><template #default="{ row }">{{ row.plan?.plannedStartDate || '未登记' }}</template></el-table-column>
              <el-table-column label="计划完成日期" width="150"><template #default="{ row }">{{ row.plan?.plannedFinishDate || '未登记' }}</template></el-table-column>
              <el-table-column prop="planStatusLabel" label="计划状态" width="120" />
            </el-table>
            <el-form label-position="top" class="operation-form">
              <el-form-item label="设计负责人（正式员工与设计职责）">
                <el-select v-model="planForm.designerEmployeeId" filterable clearable placeholder="请选择，不自动取第一项">
                  <el-option v-for="option in designerOptions" :key="option.employeeId" :value="option.employeeId" :label="`${option.employeeNo} · ${option.fullName} · ${option.positionName}`" />
                </el-select>
              </el-form-item>
              <el-form-item label="计划开始设计日期"><el-date-picker v-model="planForm.plannedStartDate" value-format="YYYY-MM-DD" type="date" /></el-form-item>
              <el-form-item label="计划完成设计日期"><el-date-picker v-model="planForm.plannedFinishDate" value-format="YYYY-MM-DD" type="date" /></el-form-item>
              <el-form-item label="计划性质">
                <el-select v-model="planForm.planType"><el-option label="开发演练模拟计划" value="SIMULATED_FOR_TEST" /><el-option label="历史计划依据" value="HISTORICAL_EVIDENCE" /><el-option label="正式计划" value="FORMAL" /></el-select>
              </el-form-item>
              <el-form-item label="调整原因"><el-input v-model="planForm.adjustmentReason" placeholder="首次可不填；调整时请说明原因" /></el-form-item>
              <div class="save-action"><el-button type="primary" :loading="saving" :disabled="!canSavePlan" data-acceptance-id="save-design-plan" @click="savePlan">保存该设计分组计划</el-button><small v-if="planSaveBlocker" class="save-blocker">{{ planSaveBlocker }}</small></div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="二、产品设计" name="design">
            <div class="operation-intro"><strong>产品综合设计区</strong><span>同一入口查看完整当前资料、维护单项或受控批量字段，并通过原正式服务形成设计修订。</span></div>
            <div class="target-selector" data-acceptance-id="product-design-comprehensive-targets">
              <el-form-item label="当前订单"><el-input :model-value="orderContext.orderNo" readonly /></el-form-item>
              <el-form-item label="范围产品分类（目标查找，不修改业务字段）"><el-select v-model="targetCategoryFilter" clearable filterable placeholder="全部产品分类"><el-option v-for="option in masterOptions.productCategories || []" :key="option.id" :label="`${option.code} · ${option.name}`" :value="option.id" /></el-select></el-form-item>
              <el-form-item label="设计分组（目标查找，不移动设计项）"><el-select v-model="targetGroupFilter" clearable placeholder="全部设计分组"><el-option v-for="group in groups" :key="group.designGroup" :label="`${group.designGroup} · ${group.productName}`" :value="group.designGroup" /></el-select></el-form-item>
              <el-form-item class="wide" label="选择产品设计项（现有订单工程对象）"><el-select :model-value="selectedDesignItemIds" multiple filterable collapse-tags :max-collapse-tags="3" placeholder="按产品标识、来源名称、安装位置选择" @update:model-value="selectComprehensiveTargets"><el-option v-for="row in targetRowsForPicker" :key="row.id" :label="targetOptionLabel(row)" :value="row.id" /></el-select></el-form-item>
              <div class="range-target-action" data-acceptance-id="product-design-range-target-action">
                <div><strong>{{ rangeScopeLabel }}</strong><span>当前完整范围候选 {{ rangeCandidateRows.length }} 项；变更范围只更新候选，不会自动增加、取消或保存目标。</span><small>下方列表搜索、高级筛选、排序和分页仅用于浏览，不参与本范围计算。</small></div>
                <el-button type="primary" @click="openRangeSelectionConfirmation">将本范围全部加入修改</el-button>
              </div>
              <div class="target-count"><strong>已选 {{ selectedRows.length }} 项</strong><span v-for="row in selectedRows" :key="row.id">{{ targetOptionLabel(row) }}</span></div>
            </div>
            <div v-if="singleComprehensiveTarget" class="current-facts" data-acceptance-id="product-design-current-complete-facts">
              <span><b>来源名称：</b>{{ singleComprehensiveTarget.productName }}</span><span><b>产品分类：</b>{{ singleComprehensiveTarget.productCategoryLabel || '来源分类未匹配' }}</span><span><b>正式产品定义：</b>{{ singleComprehensiveTarget.productDefinitionLabel || '未关联' }}</span><span><b>工程对象状态：</b>{{ singleComprehensiveTarget.engineeringIdentityStatusLabel }}</span><span><b>安装位置：</b>{{ singleComprehensiveTarget.installationPosition || '未维护' }}</span><span><b>第三尺寸语义：</b>{{ singleComprehensiveTarget.dimensionSemantic || '未维护' }}</span><span><b>设计计划开工：</b>{{ singleComprehensiveTarget.plannedStartDate || '未安排' }}</span><span><b>设计计划完工：</b>{{ singleComprehensiveTarget.plannedFinishDate || '未安排' }}</span><span><b>当前修订：</b>{{ singleComprehensiveTarget.listValues?.designRevisionLabel || '未形成' }}</span><span><b>当前修订原因：</b>{{ singleComprehensiveTarget.designRevision?.changeReason || '未形成修订' }}</span>
            </div>
            <div v-if="selectedRows.length" class="batch-preview" data-acceptance-id="saved-design-revision-summary">
              <strong>已保存的最近修订（服务端回读）</strong>
              <span v-for="item in selectedRows" :key="item.id">{{ item.itemNo }} · {{ item.designRevisionLabel || '未形成修订' }} · 设计性质：{{ item.designRevision?.designNatureLabel || item.designDataNatureLabel || '未登记' }} · 修订原因：{{ item.designRevision?.changeReason || '未形成修订' }}</span>
            </div>
            <section v-if="singleComprehensiveTarget?.designRevision" class="batch-preview">
              <strong>精确设计修订资料批准</strong>
              <p>批准保留资料来源性质。测试业务批准不等于生产适用，不自动确认基线。</p>
              <el-button @click="loadDesignApprovals">读取批准与获准后继</el-button>
              <el-input v-model="approvalReason" placeholder="填写本次批准、拒绝或撤销依据" />
              <div v-for="action in approvalFacts.actions || []" :key="action.action"><el-button :disabled="!action.available" @click="runDesignApproval(action.action)">{{ action.label }}</el-button></div>
              <article v-for="entry in approvalFacts.rows || []" :key="entry.id">
                <strong>{{ entry.statusLabel }} · {{ entry.scopeLabel }} · 原修订 R{{ entry.sourceRevision }}</strong>
                <p>来源 {{ entry.sourceRecordId }} / {{ entry.sourceVersion }}；申请人 {{ entry.applicant }}；获准后继 {{ entry.successorRevision ? `R${entry.successorRevision}` : '尚未生成' }}；原始资料性质：{{ entry.originNatureLabel }}。</p>
                <el-button v-for="action in entry.actions || []" :key="action.action" :disabled="!action.available" @click="runDesignApproval(action.action,entry)">{{ action.label }}</el-button>
              </article>
            </section>
            <div class="batch-steps"><strong>1 选择一个或多个产品设计项</strong><span>→</span><strong>2 勾选明确修改字段</strong><span>→</span><strong>3 查看前后值、单位及适用影响</strong><span>→</span><strong>4 确认保存设计修订</strong></div>
            <el-alert v-if="!selectedRows.length" title="请在上方或下方列表选择产品设计项；选择现有订单工程对象不要求先关联正式产品。" type="info" :closable="false" show-icon />
            <div v-else class="batch-preview" data-acceptance-id="product-design-batch-preview"><strong>本次修改</strong><span>影响设计项数量：{{ selectedRows.length }}</span><span>影响订单行：{{ selectedOrderLines.join('、') }}</span><span>修改字段：{{ designPatchLabels || '尚未填写字段' }}</span><span>第三尺寸语义：{{ selectedDimensionSemantics.join('、') || '未识别' }}</span><span v-for="change in batchChangePreview" :key="change.key"><b>{{ change.label }}</b>：原值 {{ change.before }} → 新值 {{ change.after }}</span></div>
            <el-alert v-if="mixedFieldKeys.length" :title="`所选对象存在多个值：${mixedFieldKeys.map(key => batchFieldOptions.find(field => field.value === key)?.label || key).join('、')}；这些提示不会写入数据库。`" type="warning" :closable="false" show-icon />
            <el-alert v-if="designUnitImpact.blocker" :title="designUnitImpact.blocker" type="error" :closable="false" show-icon />
            <div v-if="designUnitImpact.rows.length" class="unit-impact"><strong>尺寸单位换算影响</strong><span v-for="impact in designUnitImpact.rows" :key="impact">{{ impact }}</span></div>
            <el-checkbox-group v-model="batchSelectedFields" class="batch-field-selector" aria-label="选择要批量修改的字段">
              <el-checkbox v-for="field in batchFieldOptions" :key="field.value" :value="field.value" :label="field.value" :disabled="field.singleOnly && selectedRows.length !== 1">{{ field.label }}{{ field.singleOnly ? '（仅单项）' : '' }}</el-checkbox>
            </el-checkbox-group>
            <el-form label-position="top" class="operation-form design-fields">
              <el-form-item label="产品分类"><el-select v-model="designForm.productCategoryId" filterable clearable :placeholder="fieldHasMixedValues('productCategoryId') ? '多个值' : '正式产品分类'"><el-option v-for="option in masterOptions.productCategories || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
              <el-form-item label="关联正式产品（可选，仅单项）"><el-select v-model="designForm.productDefinitionId" filterable clearable :disabled="selectedRows.length !== 1" placeholder="未关联也可继续设计"><el-option v-for="option in comprehensiveProductOptions" :key="option.id" :value="option.id" :label="`${option.product_code} · ${option.product_name}`" /></el-select><small class="field-notice">{{ comprehensiveProductNotice }}</small></el-form-item>
              <el-form-item label="实物单位"><el-select v-model="designForm.physicalUomId" filterable clearable placeholder="正式计量单位"><el-option v-for="option in masterOptions.uoms || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
              <el-form-item label="设计尺寸单位"><el-select v-model="designForm.designUomId" filterable clearable :placeholder="fieldHasMixedValues('designUomId') ? '多个值' : '正式长度单位'"><el-option v-for="option in (masterOptions.uoms || []).filter(row => row.dimension === 'length')" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
              <el-form-item label="设计长"><el-input v-model="designForm.designLength" /></el-form-item>
              <el-form-item label="设计宽"><el-input v-model="designForm.designWidth" /></el-form-item>
              <el-form-item label="第三尺寸（按所选产品语义）"><el-input v-model="designForm.designThickness" :disabled="mixedDimensionSemantics" :placeholder="mixedDimensionSemantics ? '所选产品含不同第三尺寸语义，请分组批量操作' : selectedDimensionSemantics[0] || '请选择产品'" /></el-form-item>
              <el-form-item label="物料选择（编码、名称、规格同源）">
                <el-select v-model="designForm.materialId" filterable clearable placeholder="正式材料">
                  <el-option v-for="option in masterOptions.materials || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}${option.specification ? ` · ${option.specification}` : ''}`" />
                </el-select>
              </el-form-item>
              <el-form-item label="物料编码（同源回读）"><el-input :model-value="comprehensiveMaterialFacts.code" readonly /></el-form-item>
              <el-form-item label="物料名称（同源回读）"><el-input :model-value="comprehensiveMaterialFacts.name" readonly /></el-form-item>
              <el-form-item label="物料规格（同源回读）"><el-input :model-value="comprehensiveMaterialFacts.specification" readonly /></el-form-item>
              <el-form-item label="工艺配置">
                <el-select v-model="designForm.processConfigurationId" filterable clearable placeholder="来源完整工艺配置" @change="applyBatchProcessConfiguration">
                  <el-option v-for="option in batchProcessConfigurationOptions" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" :disabled="option.selectable === false" />
                </el-select>
              </el-form-item>
              <el-form-item label="油漆工艺">
                <el-select v-model="designForm.paintProcessTypeId" filterable clearable placeholder="正式油漆工艺">
                  <el-option v-for="option in masterOptions.paintProcessTypes || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" />
                </el-select>
              </el-form-item>
              <el-form-item label="封边方式">
                <el-select v-model="designForm.edgeMethodId" filterable clearable placeholder="正式工程选项">
                  <el-option v-for="option in masterOptions.edgeMethods || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" />
                </el-select>
              </el-form-item>
              <el-form-item label="见光条件"><el-select v-model="designForm.visibleConditionCode" clearable placeholder="受治理见光口径"><el-option v-for="option in masterOptions.visibleConditions || []" :key="option.code" :value="option.code" :label="`${option.name} · ${option.statusLabel}`" /></el-select></el-form-item>
              <el-form-item label="颜色/版号"><el-select v-model="designForm.colorVersionOptionId" filterable clearable placeholder="现有来源候选"><el-option v-for="option in masterOptions.colorVersionOptions || []" :key="option.id" :value="option.id" :label="`${option.name} · ${option.statusLabel}`" /></el-select></el-form-item>
              <el-form-item label="设计性质"><el-select v-model="designNature" placeholder="请按实际情况选择；多个值不自动合并"><el-option label="正式设计修订" value="FORMAL" /><el-option label="开发演练模拟设计" value="SIMULATED_FOR_TEST" /></el-select></el-form-item>
              <el-form-item class="wide" label="配置说明"><el-input v-model="designForm.configurationNotes" /></el-form-item>
              <el-form-item label="五金要求"><el-input v-model="designForm.hardware" /></el-form-item>
              <el-form-item label="玻璃要求"><el-input v-model="designForm.glass" /></el-form-item>
              <el-form-item class="wide" label="资料引用（可输入多个）"><el-select v-model="designForm.documentReferences" multiple filterable allow-create default-first-option /></el-form-item>
              <el-form-item class="wide" label="设计说明"><el-input v-model="designForm.designNotes" /></el-form-item>
              <el-form-item class="wide" label="修订原因"><el-input v-model="designReason" /><small class="field-notice">此处填写本次新修订原因；刷新或重新选择后可为空。已保存原因请查看下方最近修订信息，不会自动作为下次原因。</small></el-form-item>
              <CabinetTestPartsEditor v-if="selectedRows.length===1" :current="selectedRows[0]?.designRevision?.calculationInputs" @save="(inputs,reason)=>submit('SAVE_DESIGN',{designNature:'SIMULATED_FOR_TEST',designData:{calculationInputs:inputs},reason},'保存测试部件')" />
              <div class="save-action"><el-button type="primary" :loading="saving" :disabled="!canSaveDesign" data-acceptance-id="save-design-content" @click="saveDesign">保存所选产品设计</el-button><small v-if="designSaveBlocker" class="save-blocker">{{ designSaveBlocker }}</small></div>
            </el-form>
          </el-tab-pane>

          <el-tab-pane label="三、设计计划完成考核" name="completion">
            <div class="operation-intro"><strong>完成设计 / 登记历史完成</strong><span>实际完成业务日期与系统登记时间分开；模拟日期不进入真实绩效。</span></div>
            <el-alert v-if="!selectedRows.length" title="请先在下方选择需要登记完成情况的产品。查看本页签不要求先选择。" type="info" :closable="false" show-icon />
            <el-form label-position="top" class="operation-form">
              <el-form-item label="完成性质"><el-select v-model="completionForm.completionNature"><el-option label="正式完成登记" value="FORMAL" /><el-option label="已有完成事实补录" value="HISTORICAL_EVIDENCE" /><el-option label="开发演练模拟完成" value="SIMULATED_FOR_TEST" /><el-option label="返工/变更登记" value="REWORK" /></el-select></el-form-item>
              <el-form-item label="实际完成设计日期"><el-date-picker v-model="completionForm.actualCompletionDate" value-format="YYYY-MM-DD" type="date" clearable /></el-form-item>
              <el-form-item label="完成设计师"><el-select v-model="completionForm.designerEmployeeId" filterable clearable placeholder="可按依据选择"><el-option v-for="option in designerOptions" :key="option.employeeId" :value="option.employeeId" :label="`${option.employeeNo} · ${option.fullName}`" /></el-select></el-form-item>
              <el-form-item label="依据/说明"><el-input v-model="completionForm.completionBasis" /></el-form-item>
              <div class="save-action"><el-button type="primary" :loading="saving" :disabled="!canSaveCompletion" data-acceptance-id="record-design-completion" @click="saveCompletion">登记所选产品完成记录</el-button><small v-if="completionSaveBlocker" class="save-blocker">{{ completionSaveBlocker }}</small></div>
            </el-form>
          </el-tab-pane>
        </el-tabs>
      </section>

      <section v-if="refreshStatus === 'success'" class="card list-card">
        <div class="section-heading"><div><small>同一批具体产品记录</small><h2>产品设计</h2></div><span>已选 {{ selectedRows.length }} 项</span></div>
        <PceEnterpriseListTable
          ref="tableRef" :contract="enterpriseListContract" page-id="pde-product-definitions"
          table-id="pde-product-design-item-table" :rows="rows" :table-rows="filteredRows"
          :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
          :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
          :reserve-selection="true"
          :active-filter-count="activeFilterCount" :sort-text="sortText"
          primary-field="itemNo" primary-label="产品标识" :primary-width="250"
          min-width="4380px" :default-page-size="20" :page-sizes="[20, 50, 100]" action-width="440"
          @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
          @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters"
          @clear-sort="clearSort" @export-current="exportProductDesignExcel" @clear-selection="clearDesignSelection"
          @update-filter="(field, value) => filters[field] = value"
          @selection-change="handleDesignSelectionChange" @sort-change="handleSort"
        >
          <template #toolbar-extension>
            <div class="design-tools" data-acceptance-id="product-design-complete-tools">
              <el-button @click="downloadImportTemplate">导入模板</el-button>
              <el-button @click="chooseImportFile">导入</el-button>
              <el-button type="primary" @click="openAddItem">新增</el-button>
              <input ref="importFileInput" class="hidden-file" type="file" accept=".xlsx" @change="previewImportFile" />
            </div>
          </template>
          <template #columns>
            <el-table-column
              v-for="field in standardListColumns" :key="field.key"
              :prop="field.key" :label="field.label"
              :width="standardColumnWidth(field.key)" sortable show-overflow-tooltip
            >
              <template #default="{ row }">
                <PceBusinessStatus v-if="['designStatus', 'completionStatus', 'engineeringIdentityStatus'].includes(field.key)" :status-label="displayListValue(row, field.key)" source="server" />
                <span v-else>{{ displayListValue(row, field.key) }}</span>
              </template>
            </el-table-column>
          </template>
          <template #actions="{ row }"><el-button link @click="toggleBatchSelection(row)">{{ isRowSelected(row) ? '取消批量' : '加入批量' }}</el-button><el-button link type="primary" @click="openRowDesign(row)">编辑当前设计</el-button><el-button link @click="openRowCompletion(row)">登记完成</el-button><el-button link @click="showEvidence(row)">查看依据</el-button><el-button link type="danger" @click="deleteRow(row)">删除/保护检查</el-button></template>
        </PceEnterpriseListTable>
      </section>

      <el-dialog v-model="rangeConfirmVisible" title="确认将范围设计项加入修改目标" width="980px" data-acceptance-id="product-design-range-confirmation">
        <template v-if="rangeSnapshot">
          <el-alert v-if="!rangeSnapshot.productCategoryId && !rangeSnapshot.designGroup" title="本次范围是当前订单全部设计项；确认后只加入目标集合，不会直接保存。" type="warning" :closable="false" show-icon />
          <el-descriptions :column="3" border class="range-summary">
            <el-descriptions-item label="当前订单">{{ rangeSnapshot.orderNo }}</el-descriptions-item>
            <el-descriptions-item label="范围产品分类">{{ rangeCategoryLabel(rangeSnapshot.productCategoryId) }}</el-descriptions-item>
            <el-descriptions-item label="设计分组">{{ rangeSnapshot.designGroup || '全部设计分组' }}</el-descriptions-item>
            <el-descriptions-item label="范围匹配总数">{{ rangeSnapshot.matchedCount }}</el-descriptions-item>
            <el-descriptions-item label="范围内已选">{{ rangeSnapshot.alreadySelectedCount }}</el-descriptions-item>
            <el-descriptions-item label="本次新增">{{ rangeSnapshot.newCount }}</el-descriptions-item>
            <el-descriptions-item label="范围外原已选">{{ rangeSnapshot.selectedOutsideCount }}</el-descriptions-item>
            <el-descriptions-item label="加入后总数">{{ rangeSnapshot.finalCount }}</el-descriptions-item>
            <el-descriptions-item label="集合规则">追加并按稳定ID去重</el-descriptions-item>
          </el-descriptions>
          <el-table :data="rangePreviewRows" border stripe max-height="420" class="range-preview-table">
            <el-table-column prop="itemNo" label="产品标识" width="300" />
            <el-table-column prop="productName" label="来源名称" min-width="180" />
            <el-table-column prop="installationPosition" label="安装位置" min-width="180"><template #default="{ row }">{{ row.installationPosition || '未维护' }}</template></el-table-column>
            <el-table-column prop="sourcePosition" label="来源位置" min-width="160"><template #default="{ row }">{{ row.sourcePosition || '未维护' }}</template></el-table-column>
          </el-table>
          <el-pagination v-if="rangeSnapshot.matchedCount > rangePreviewPageSize" v-model:current-page="rangePreviewPage" :page-size="rangePreviewPageSize" layout="total, prev, pager, next" :total="rangeSnapshot.matchedCount" />
          <p class="range-confirm-note">确认只冻结并追加以上 ProductDesignItem 稳定ID；后续仍需明确选择修改字段、填写有效新值与修订原因，再走原保存确认和乐观版本校验。</p>
        </template>
        <template #footer><el-button @click="rangeConfirmVisible = false">取消</el-button><el-button type="primary" @click="confirmRangeSelection">确认加入目标集合</el-button></template>
      </el-dialog>

      <el-dialog v-model="addItemVisible" title="新增产品设计项" width="900px">
        <el-alert title="新增进入当前订单正式设计来源；不会创建永久物料，也不会改写原Excel。" type="info" :closable="false" />
        <el-form label-position="top" class="row-design-form">
          <el-form-item label="订单行"><el-select v-model="addItemForm.orderLineNo"><el-option v-for="group in groups" :key="group.orderLineNo" :value="group.orderLineNo" :label="`${group.groupNo} · ${group.productName}`" /></el-select></el-form-item>
          <el-form-item label="产品名称"><el-input v-model="addItemForm.itemName" /></el-form-item>
          <el-form-item label="安装位置"><el-input v-model="addItemForm.installationPosition" /></el-form-item>
          <el-form-item label="实物数量"><el-input v-model="addItemForm.physicalQuantity" /></el-form-item>
          <el-form-item label="实物单位"><el-select v-model="addItemForm.physicalUomId"><el-option v-for="option in masterOptions.uoms || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="产品分类"><el-select v-model="addItemForm.productCategoryId"><el-option v-for="option in masterOptions.productCategories || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="设计长"><el-input v-model="addItemForm.designLength" /></el-form-item>
          <el-form-item label="设计宽"><el-input v-model="addItemForm.designWidth" /></el-form-item>
          <el-form-item label="第三尺寸"><el-input v-model="addItemForm.designThickness" /></el-form-item>
          <el-form-item label="设计尺寸单位"><el-select v-model="addItemForm.designUomId"><el-option v-for="option in (masterOptions.uoms || []).filter(row => row.dimension === 'length')" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="第三尺寸语义"><el-select v-model="addItemForm.dimensionSemantic"><el-option label="墙厚" value="墙厚" /><el-option label="部件厚" value="部件厚" /><el-option label="实际厚度" value="实际厚度" /></el-select></el-form-item>
          <el-form-item class="wide" label="新增依据"><el-input v-model="addItemForm.reason" /></el-form-item>
        </el-form>
        <template #footer><el-button @click="addItemVisible=false">取消</el-button><el-button type="primary" :disabled="!canAddItem" @click="saveAddItem">确认新增并回读</el-button></template>
      </el-dialog>

      <el-dialog v-model="importVisible" title="产品设计导入预览" width="980px">
        <el-alert :title="importPreview.errorCount ? `发现 ${importPreview.errorCount} 行错误，修正后重新预览。` : `共 ${importPreview.validCount || 0} 行通过校验，确认后才会写入。`" :type="importPreview.errorCount ? 'error' : 'success'" :closable="false" show-icon />
        <el-table :data="importPreview.rows || []" max-height="420"><el-table-column prop="rowNumber" label="Excel行" width="90" /><el-table-column prop="operation" label="操作" width="90" /><el-table-column prop="stableProductId" label="产品标识" width="260" /><el-table-column prop="itemName" label="产品名称" width="160" /><el-table-column label="校验"><template #default="{row}"><span v-if="row.valid">通过</span><span v-else class="error-text">{{ row.errors.join('；') }}</span></template></el-table-column></el-table>
        <template #footer><el-button @click="importVisible=false">取消</el-button><el-button type="primary" :disabled="!importFile || importPreview.errorCount || !importPreview.validCount" @click="commitImport">确认导入</el-button></template>
      </el-dialog>

      <el-dialog v-model="rowDesignVisible" title="编辑当前产品设计" width="980px" destroy-on-close>
        <div v-if="rowDesignItem" class="row-edit-context"><strong>{{ rowDesignItem.itemNo }} · {{ rowDesignItem.productName }}</strong><span>{{ rowDesignItem.sourceProvenance?.sourceSheet }}!{{ rowDesignItem.sourceProvenance?.sourceRow }}；只保存本行并新增设计修订。</span></div>
        <el-descriptions v-if="rowDesignItem" :column="3" border class="engineering-identity-summary" data-acceptance-id="customer-engineering-identity">
          <el-descriptions-item label="来源名称">{{ rowDesignItem.productName || '未登记' }}</el-descriptions-item>
          <el-descriptions-item label="产品分类">{{ rowDesignItem.productCategoryLabel || '未匹配' }}</el-descriptions-item>
          <el-descriptions-item label="正式产品定义">{{ rowDesignItem.productDefinitionLabel || '未关联' }}</el-descriptions-item>
          <el-descriptions-item label="工程对象状态">{{ rowDesignItem.engineeringIdentityStatusLabel }}</el-descriptions-item>
          <el-descriptions-item label="订单工程">允许继续</el-descriptions-item>
          <el-descriptions-item label="标准产品/BOM发布">{{ rowDesignItem.engineeringIdentityFacts?.standardBomBlocked ? '阻断' : '需继续校验产品版本与发布资格' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="rowMaterialIdentityNotice" :title="rowMaterialIdentityNotice" type="info" :closable="false" show-icon />
        <el-alert v-if="rowUnmatchedSourceFacts.length" :title="`来源已有，正式主数据未匹配：${rowUnmatchedSourceFacts.join('；')}`" type="warning" :closable="false" show-icon />
        <el-form label-position="top" class="row-design-form">
          <el-form-item label="产品分类"><el-select v-model="rowDesignForm.productCategoryId" filterable clearable @change="handleRowProductCategoryChange"><el-option v-for="option in masterOptions.productCategories || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="正式产品定义（可选）">
            <el-select v-model="rowDesignForm.productDefinitionId" filterable clearable :placeholder="rowProductSelectionNotice || '请选择正式产品定义'"><el-option v-for="option in rowProductOptions" :key="option.id" :value="option.id" :label="`${option.product_code} · ${option.product_name}${option.specification ? ` · ${option.specification}` : ''}`" /></el-select>
            <small v-if="rowProductSelectionNotice" class="field-notice">{{ rowProductSelectionNotice }}</small>
            <small v-else class="field-notice">仅显式选择才会关联正式产品；来源名称不会自动认定为 ProductDefinition。</small>
          </el-form-item>
          <el-form-item label="实物单位"><el-select v-model="rowDesignForm.physicalUomId" filterable clearable><el-option v-for="option in masterOptions.uoms || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="设计尺寸单位"><el-select v-model="rowDesignForm.designUomId" filterable clearable><el-option v-for="option in (masterOptions.uoms || []).filter(row => row.dimension === 'length')" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="设计长"><el-input v-model="rowDesignForm.designLength" /></el-form-item><el-form-item label="设计宽"><el-input v-model="rowDesignForm.designWidth" /></el-form-item><el-form-item :label="rowDimensionSemantic"><el-input v-model="rowDesignForm.designThickness" /></el-form-item>
          <el-form-item label="物料选择（正式主数据）"><el-select v-model="rowDesignForm.materialId" filterable clearable><el-option v-for="option in masterOptions.materials || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}${option.specification ? ` · ${option.specification}` : ''}`" /></el-select></el-form-item>
          <el-form-item label="物料编码"><el-input :model-value="rowSelectedMaterial?.code || rowDesignItem?.listValues?.materialCode || ''" readonly /></el-form-item>
          <el-form-item label="物料名称"><el-input :model-value="rowSelectedMaterial?.name || rowDesignItem?.listValues?.materialName || ''" readonly /></el-form-item>
          <el-form-item label="物料规格"><el-input :model-value="rowSelectedMaterial?.specification || rowDesignItem?.listValues?.materialSpecification || ''" readonly /></el-form-item>
          <el-form-item label="工艺配置选择（Routing）"><el-select v-model="rowDesignForm.processConfigurationId" filterable clearable @change="applyRowProcessConfiguration"><el-option v-for="option in rowProcessConfigurationOptions" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" :disabled="option.selectable === false" /></el-select><small v-if="rowProcessConfigurationNotice" class="field-notice">{{ rowProcessConfigurationNotice }}</small></el-form-item>
          <el-form-item label="Routing编码"><el-input :model-value="rowSelectedProcessConfiguration?.code || rowDesignItem?.listValues?.processConfigurationCode || ''" readonly /></el-form-item>
          <el-form-item label="Routing名称"><el-input :model-value="rowSelectedProcessConfiguration?.selectable === false ? '未匹配正式工艺路线，保留来源值' : (rowSelectedProcessConfiguration?.name || rowDesignItem?.listValues?.processConfigurationName || '')" readonly /></el-form-item>
          <el-form-item label="油漆工艺选择"><el-select v-model="rowDesignForm.paintProcessTypeId" filterable clearable><el-option v-for="option in masterOptions.paintProcessTypes || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="油漆工艺编码"><el-input :model-value="rowSelectedPaintProcess?.code || rowDesignItem?.listValues?.paintProcessCode || ''" readonly /></el-form-item>
          <el-form-item label="油漆工艺名称"><el-input :model-value="rowSelectedPaintProcess?.name || rowDesignItem?.listValues?.paintProcessName || ''" readonly /></el-form-item>
          <el-form-item label="封边方式"><el-select v-model="rowDesignForm.edgeMethodId" filterable clearable><el-option v-for="option in masterOptions.edgeMethods || []" :key="option.id" :value="option.id" :label="`${option.code} · ${option.name}`" /></el-select></el-form-item>
          <el-form-item label="见光条件"><el-select v-model="rowDesignForm.visibleConditionCode" clearable><el-option v-for="option in masterOptions.visibleConditions || []" :key="option.code" :value="option.code" :label="`${option.name} · ${option.statusLabel}`" /></el-select></el-form-item>
          <el-form-item label="颜色/版号"><el-select v-model="rowDesignForm.colorVersionOptionId" filterable clearable><el-option v-for="option in colorVersionOptionsForRow" :key="option.id" :value="option.id" :label="`${option.name} · ${option.statusLabel}`" /></el-select></el-form-item>
          <el-form-item class="wide" label="配置说明"><el-input v-model="rowDesignForm.configurationNotes" /></el-form-item>
          <el-form-item label="五金要求"><el-input v-model="rowDesignForm.hardware" /></el-form-item>
          <el-form-item label="玻璃要求"><el-input v-model="rowDesignForm.glass" /></el-form-item>
          <el-form-item class="wide" label="资料引用"><el-select v-model="rowDesignForm.documentReferences" multiple filterable allow-create default-first-option /></el-form-item>
          <el-form-item class="wide" label="设计说明"><el-input v-model="rowDesignForm.designNotes" /></el-form-item><el-form-item class="wide" label="修订原因（必填）"><el-input v-model="rowDesignReason" /></el-form-item>
        </el-form>
        <template #footer><small v-if="rowDesignSaveBlocker" class="save-blocker">{{ rowDesignSaveBlocker }}</small><el-button @click="rowDesignVisible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!!rowDesignSaveBlocker" @click="saveRowDesign">保存本行设计修订</el-button></template>
      </el-dialog>

      <el-dialog v-model="rowCompletionVisible" title="登记单项产品完成记录" width="720px">
        <div v-if="rowCompletionItem" class="row-edit-context"><strong>{{ rowCompletionItem.itemNo }} · {{ rowCompletionItem.productName }}</strong><span>只处理本行；系统登记时间与实际完成日期分开。</span></div>
        <el-form label-position="top" class="row-design-form">
          <el-form-item label="完成性质"><el-select v-model="rowCompletionForm.completionNature"><el-option label="正式完成登记" value="FORMAL" /><el-option label="已有完成事实补录" value="HISTORICAL_EVIDENCE" /><el-option label="开发演练模拟完成" value="SIMULATED_FOR_TEST" /><el-option label="返工/变更登记" value="REWORK" /></el-select></el-form-item>
          <el-form-item label="实际完成设计日期"><el-date-picker v-model="rowCompletionForm.actualCompletionDate" value-format="YYYY-MM-DD" type="date" clearable /></el-form-item>
          <el-form-item label="完成设计师"><el-select v-model="rowCompletionForm.designerEmployeeId" filterable clearable><el-option v-for="option in designerOptions" :key="option.employeeId" :value="option.employeeId" :label="`${option.employeeNo} · ${option.fullName}`" /></el-select></el-form-item>
          <el-form-item label="依据/说明"><el-input v-model="rowCompletionForm.completionBasis" /></el-form-item>
        </el-form>
        <template #footer><small v-if="rowCompletionSaveBlocker" class="save-blocker">{{ rowCompletionSaveBlocker }}</small><el-button @click="rowCompletionVisible=false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!!rowCompletionSaveBlocker" @click="saveRowCompletion">保存本行完成记录</el-button></template>
      </el-dialog>

      <el-dialog v-model="evidenceVisible" title="产品设计项依据与历史" width="760px">
        <template v-if="evidenceRow">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="产品标识">{{ evidenceRow.itemNo }}</el-descriptions-item>
            <el-descriptions-item label="分组">{{ evidenceRow.groupNo }}</el-descriptions-item>
            <el-descriptions-item label="来源文件">{{ evidenceRow.sourceProvenance?.sourceFile || '-' }}</el-descriptions-item>
            <el-descriptions-item label="来源位置">{{ evidenceRow.sourceProvenance?.sourceSheet }}!{{ evidenceRow.sourceProvenance?.sourceRow }}</el-descriptions-item>
            <el-descriptions-item label="来源版本">{{ evidenceRow.sourceProvenance?.sourceVersion }}</el-descriptions-item>
            <el-descriptions-item label="D1兼容">{{ evidenceRow.legacyD1 ? `原记录 #${evidenceRow.legacyD1.sourceRecordId} / ${evidenceRow.legacyD1.sourceVersion}` : '无' }}</el-descriptions-item>
            <el-descriptions-item label="计划历史">{{ evidenceRow.plan ? `P${evidenceRow.plan.revision} · ${evidenceRow.plan.planNatureLabel}` : '未登记' }}</el-descriptions-item>
            <el-descriptions-item label="完成登记">{{ evidenceRow.completion?.completionNatureLabel || '未登记' }} · {{ evidenceRow.completion?.registeredAt || '-' }}</el-descriptions-item>
          </el-descriptions>
          <pre>{{ JSON.stringify({ matchResults: evidenceRow.matchResults, originalRequirement: evidenceRow.originalRequirement, existingDesign: evidenceRow.existingDesign, currentDesign: evidenceRow.designRevision }, null, 2) }}</pre>
        </template>
      </el-dialog>
    </div>
  </PceListPageShell>
</template>

<script setup>
import CabinetTestPartsEditor from '@/meta/components/CabinetTestPartsEditor.vue'
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { designOrderQuery } from '@/meta/runtime/productDesignNavigation.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import { pdeApi } from '@/api/pde.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import { findPdePageDefinition } from './pdePageDefinitions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { readPceFactLoadEnvelope } from '@/meta/runtime/pceFactLoadContract.js'
import {
  assertCompleteProductDesignRangeSource,
  createProductDesignRangeSnapshot,
  filterProductDesignRange,
  PRODUCT_DESIGN_INPUT_FIELDS,
  assertProductDesignFieldContract,
  productDesignSelectionKey,
  reconcileProductDesignTargets,
  resolveProductDesignTargets,
  summarizeProductDesignSelection,
} from '@/meta/runtime/productDesignComprehensiveRuntime.js'

const definition = findPdePageDefinition('definitions')
const governance = definition.governance
const route = useRoute()
const router = useRouter()
const orderOptions = ref([])
const selectedOrderNo = computed(() => String(route.query.orderNo || orderContext.value.orderNo || ''))
function selectDesignOrder(event) { router.push({ path: route.path, query: designOrderQuery(route.query, event.target.value) }) }
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const rows = ref([])
const groups = ref([])
const orderContext = ref({})
const sourceContext = ref({})
const reviewContext = ref({})
const designerOptions = ref([])
const masterOptions = ref({})
const listFieldContract = ref([])
const strictFacts = ref({})
const loadError = ref('')
const refreshStatus = ref('idle')
const lastRefreshTime = ref('')
const saving = ref(false)
const activeSection = ref(route.query.orderEngineeringInstanceId ? 'design' : 'plan')
const evidenceVisible = ref(false)
const evidenceRow = ref(null)
const selectedDesignGroups = ref([])
const planForm = reactive({ designerEmployeeId: null, plannedStartDate: '', plannedFinishDate: '', planType: 'FORMAL', adjustmentReason: '' })
const designForm = reactive({ productCategoryId: null, productDefinitionId: null, physicalUomId: null, designUomId: null, designLength: '', designWidth: '', designThickness: '', materialId: null, processConfigurationId: null, paintProcessTypeId: null, edgeMethodId: null, colorVersionOptionId: null, visibleConditionCode: null, configurationNotes: '', designNotes: '', hardware: '', glass: '', documentReferences: [] })
const batchFieldOptions = PRODUCT_DESIGN_INPUT_FIELDS.filter(field => field.batch || field.inputKey === 'productDefinitionId').map(field => ({ value: field.inputKey, label: field.label, section: field.section, singleOnly: !field.batch }))
const batchSelectedFields = ref([])
const mixedFieldKeys = ref([])
const targetCategoryFilter = ref('')
const targetGroupFilter = ref('')
const rangeConfirmVisible = ref(false)
const rangeSnapshot = ref(null)
const rangePreviewPage = ref(1)
const rangePreviewPageSize = 20
const comprehensiveDrafts = new Map()
let syncingTargetSelection = false
const designNature = ref(route.query.orderEngineeringInstanceId ? 'SIMULATED_FOR_TEST' : 'FORMAL')
const designReason = ref('')
const approvalFacts = ref({})
const approvalReason = ref('')
async function loadDesignApprovals() {
  const target=singleComprehensiveTarget.value
  const revisionId=target?.designRevision?.id
  if (!revisionId) return
  const sequence=factReadSequence
  try { const payload=unwrap(await pdeApi.designRevisionApprovals(revisionId)); if(sequence===factReadSequence) approvalFacts.value=payload }
  catch(error) { ElMessage.error(explainDesignError(error,'批准事实读取失败。')) }
}
async function runDesignApproval(action,entry=null) {
  await ElMessageBox.confirm('确认执行所选精确修订资料动作？不自动办理基线、发布或制造输出。','资料批准动作',{type:'warning'})
  const body=action==='submit' ? {action,instanceContext:instanceContext.value,revisionId:approvalFacts.value.sourceRevisionId,contentHash:approvalFacts.value.contentHash} : {action,approvalId:entry.id,...(action==='successor' ? {} : {contentHash:entry.contentHash,reason:approvalReason.value})}
  try { await pdeApi.designRevisionApprovalAction(body,`design-approval-${action}-${Date.now()}`); await refresh();await loadDesignApprovals() }
  catch(error) { ElMessage.error(explainDesignError(error,'资料批准动作失败。')) }
}
const rowDesignVisible = ref(false)
const rowDesignItem = ref(null)
const rowDesignReason = ref('')
const rowDesignBaseline = ref({})
const rowDesignForm = reactive({ productCategoryId: null, productDefinitionId: null, physicalUomId: null, designUomId: null, designLength: '', designWidth: '', designThickness: '', materialId: null, processConfigurationId: null, paintProcessTypeId: null, edgeMethodId: null, colorVersionOptionId: null, visibleConditionCode: null, configurationNotes: '', designNotes: '', hardware: '', glass: '', documentReferences: [] })
const completionForm = reactive({ completionNature: 'HISTORICAL_EVIDENCE', actualCompletionDate: '', designerEmployeeId: null, completionBasis: '' })
const rowCompletionVisible = ref(false)
const rowCompletionItem = ref(null)
const rowCompletionForm = reactive({ completionNature: 'HISTORICAL_EVIDENCE', actualCompletionDate: '', designerEmployeeId: null, completionBasis: '' })
const lastPlanSaveSummary = ref(null)
const addItemVisible = ref(false)
const addItemForm = reactive({ orderLineNo: null, itemName: '', installationPosition: '', physicalQuantity: '', physicalUomId: null, productCategoryId: null, designLength: '', designWidth: '', designThickness: '', designUomId: null, dimensionSemantic: '', reason: '' })
const importFileInput = ref(null)
const importFile = ref(null)
const importPreview = ref({ rows: [], validCount: 0, errorCount: 0, previewFingerprint: '' })
const importVisible = ref(false)

const designStatusOptions = ['待安排', '已安排', '已有设计资料带入', '已形成设计修订'].map(value => ({ label: value, value }))
const completionStatusOptions = ['未完成', '已有完成事实·日期待补', '已完成', '返工/变更中'].map(value => ({ label: value, value }))
const filterSchema = [
  { field: 'designGroup', label: '设计分组', filterType: 'text' },
  { field: 'productName', label: '产品名称', filterType: 'text' },
  { field: 'installationPosition', label: '空间/安装位置', filterType: 'text' },
  { field: 'designer', label: '设计负责人', filterType: 'text' },
  { field: 'designStatus', label: '设计状态', filterType: 'select', options: designStatusOptions },
  { field: 'completionStatus', label: '完成状态', filterType: 'select', options: completionStatusOptions },
]
const enterpriseListContract = createPceEnterpriseListContract({ pageCode: 'pde-product-definitions', pageType: 'list', title: '产品设计', moduleCode: 'PDE' })
const runtime = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'pde-product-definitions',
  searchFields: ['productIdentifier', 'orderLine', 'designGroup', 'productName', 'installationPosition', 'sourcePosition', 'materialCode', 'materialName', 'processConfigurationCode', 'processConfigurationName', 'designer'],
})
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef, activeFilterCount, sortText, filteredRows, clearFilters, clearSort, handleSort } = runtime
const selectedDesignItemIds = computed(() => selectedRows.value.map(row => row.id))
const rangeCandidateRows = computed(() => filterProductDesignRange(rows.value, {
  productCategoryId: targetCategoryFilter.value,
  designGroup: targetGroupFilter.value,
}))
const targetRowsForPicker = rangeCandidateRows
const rangeScopeLabel = computed(() => {
  if (!targetCategoryFilter.value && !targetGroupFilter.value) return `当前订单 ${orderContext.value.orderNo || '—'} · 全部设计项`
  return `${rangeCategoryLabel(targetCategoryFilter.value)} · ${targetGroupFilter.value || '全部设计分组'}（交集范围）`
})
const rangePreviewRows = computed(() => {
  if (!rangeSnapshot.value) return []
  const start = (rangePreviewPage.value - 1) * rangePreviewPageSize
  return rangeSnapshot.value.targets.slice(start, start + rangePreviewPageSize)
})
const singleComprehensiveTarget = computed(() => selectedRows.value.length === 1 ? selectedRows.value[0] : null)
const comprehensiveProductOptions = computed(() => (masterOptions.value.products || []).filter(option => (
  String(option.category_id || '') === String(designForm.productCategoryId || '')
)))
const comprehensiveProductNotice = computed(() => {
  if (selectedRows.value.length !== 1) return '正式产品关联只允许单项明确维护；多项选择时保持原关联不变。'
  if (!designForm.productCategoryId) return '当前未明确产品分类；仍可维护其它订单工程设计字段。'
  return comprehensiveProductOptions.value.length ? '仅显式选择才会关联正式产品定义。' : '当前分类暂无正式产品定义；可继续完成客户订单工程设计。'
})
function aggregateSelectedListValue(key) {
  if (!selectedRows.value.length) return '未选择'
  const values = [...new Set(selectedRows.value.map(row => String(row.listValues?.[key] || '未维护')))]
  return values.length === 1 ? values[0] : '多个值'
}
const comprehensiveMaterialFacts = computed(() => {
  const material = (masterOptions.value.materials || []).find(option => String(option.id) === String(designForm.materialId))
  if (material) return {
    code: material.code || '未维护',
    name: material.name || '未维护',
    specification: material.specification || '未维护',
  }
  return {
    code: aggregateSelectedListValue('materialCode'),
    name: aggregateSelectedListValue('materialName'),
    specification: aggregateSelectedListValue('materialSpecification'),
  }
})
const standardListColumns = computed(() => listFieldContract.value.slice(1))
const standardColumnWidths = { orderLine: 190, designGroup: 140, productName: 180, installationPosition: 190, sourcePosition: 150, physicalQuantity: 110, commercialQuantity: 110, physicalUnit: 110, productCategory: 150, materialCode: 150, materialName: 170, materialSpecification: 170, processConfigurationCode: 170, processConfigurationName: 190, paintProcessCode: 150, paintProcessName: 170, edgeMethod: 130, visibleCondition: 130, designDimensionUnit: 140, designLength: 120, designWidth: 120, thirdDimension: 120, thirdDimensionSemantic: 130, configurationNotes: 180, designNotes: 180, hardware: 160, glass: 160, documentReferences: 200, designDataNatureLabel: 160, currentRevisionReason: 190, designer: 130, plannedStartDate: 150, plannedFinishDate: 150, designStatus: 160, designRevisionLabel: 130, completionStatus: 170 }
function standardColumnWidth(key) { return standardColumnWidths[key] || 150 }
function displayListValue(row, key) {
  const value = row?.listValues?.[key]
  if (value !== null && value !== undefined && value !== '') return value
  return ['plannedStartDate', 'plannedFinishDate'].includes(key) ? '未安排' : '未维护'
}
function fieldHasMixedValues(key) { return mixedFieldKeys.value.includes(key) }
function targetOptionLabel(row) { return `${row.itemNo} · ${row.productName} · ${row.installationPosition || row.spaceLabel || '位置未维护'}` }
function rangeCategoryLabel(categoryId) {
  if (!categoryId) return '全部产品分类'
  const category = (masterOptions.value.productCategories || []).find(option => String(option.id) === String(categoryId))
  return category ? `${category.code} · ${category.name}` : `分类ID ${categoryId}`
}
function openRangeSelectionConfirmation() {
  try {
    assertCompleteProductDesignRangeSource(rows.value, {
      expectedRecordCount: strictFacts.value.recordCount,
      orderNo: orderContext.value.orderNo,
    })
    const snapshot = createProductDesignRangeSnapshot({
      rows: rows.value,
      selectedRows: selectedRows.value,
      productCategoryId: targetCategoryFilter.value,
      designGroup: targetGroupFilter.value,
      orderNo: orderContext.value.orderNo,
    })
    if (!snapshot.matchedCount) {
      ElMessage.info('当前订单在所选分类/分组下无可加入的设计项。')
      return
    }
    rangeSnapshot.value = snapshot
    rangePreviewPage.value = 1
    rangeConfirmVisible.value = true
  } catch (error) {
    ElMessage.error(error?.message || '当前范围事实不完整，已阻断整批加入。')
  }
}
function confirmRangeSelection() {
  const snapshot = rangeSnapshot.value
  if (!snapshot) return
  const { missingIds } = resolveProductDesignTargets(rows.value, snapshot.targetIds)
  if (missingIds.length) {
    ElMessage.error(`确认快照中的稳定目标已不完整（缺少ID：${missingIds.join('、')}），未加入任何设计项。`)
    return
  }
  selectComprehensiveTargets(snapshot.finalIds)
  rangeConfirmVisible.value = false
  ElMessage.success(snapshot.newCount
    ? `已追加 ${snapshot.newCount} 项，去重后共选择 ${snapshot.finalCount} 项；尚未保存。`
    : `本范围 ${snapshot.matchedCount} 项已全部在目标集合中，选择数量保持 ${snapshot.finalCount} 项。`)
}
function normalizeComprehensiveForm(form, selected) {
  const next = { ...form }
  if (selected.length === 1) {
    const row = selected[0]
    const revision = row.designRevision || {}
    const existing = row.existingDesign || {}
    const visible = (masterOptions.value.visibleConditions || []).find(option => option.code === next.visibleConditionCode || option.name === (revision.visibleCondition ?? existing.visibleCondition))
    const colorValue = revision.finishOrColor ?? existing.finishOrColor
    const color = (masterOptions.value.colorVersionOptions || []).find(option => option.id === next.colorVersionOptionId || option.name === colorValue)
    next.visibleConditionCode = visible?.code || null
    next.colorVersionOptionId = color?.id || null
  }
  return next
}
function saveComprehensiveDraft() {
  const key = productDesignSelectionKey(selectedRows.value)
  if (!key) return
  comprehensiveDrafts.set(key, {
    form: {
      ...designForm,
      documentReferences: [...(designForm.documentReferences || [])],
    },
    fields: [...batchSelectedFields.value], reason: designReason.value,
    nature: designNature.value, mixed: [...mixedFieldKeys.value],
  })
}
function loadComprehensiveDraft(nextRows) {
  const key = productDesignSelectionKey(nextRows)
  const saved = comprehensiveDrafts.get(key)
  if (saved) {
    Object.assign(designForm, {
      ...saved.form,
      documentReferences: [...(saved.form.documentReferences || [])],
    })
    batchSelectedFields.value = [...saved.fields]
    designReason.value = saved.reason
    designNature.value = saved.nature
    mixedFieldKeys.value = [...saved.mixed]
    return
  }
  const summary = summarizeProductDesignSelection(nextRows)
  Object.assign(designForm, normalizeComprehensiveForm(summary.form, nextRows))
  mixedFieldKeys.value = summary.mixedFields
  batchSelectedFields.value = []
  designReason.value = ''
  const persistedNatures = [...new Set(nextRows.map(row => row.designRevision?.designNature || row.designDataNature).filter(Boolean))]
  designNature.value = persistedNatures.length === 1 && ['FORMAL', 'SIMULATED_FOR_TEST'].includes(persistedNatures[0]) ? persistedNatures[0] : ''
}
function handleDesignSelectionChange(nextRows) {
  if (syncingTargetSelection) { selectedRows.value = nextRows; return }
  saveComprehensiveDraft()
  selectedRows.value = nextRows
  loadComprehensiveDraft(nextRows)
}
function selectComprehensiveTargets(ids) {
  const { targets: nextRows } = resolveProductDesignTargets(rows.value, ids)
  const changes = reconcileProductDesignTargets(selectedRows.value, ids)
  saveComprehensiveDraft()
  syncingTargetSelection = true
  changes.remove.forEach(row => tableRef.value?.toggleRowSelection?.(row, false))
  changes.add.forEach(id => {
    const row = rows.value.find(candidate => String(candidate.id) === String(id))
    if (row) tableRef.value?.toggleRowSelection?.(row, true)
  })
  selectedRows.value = nextRows
  loadComprehensiveDraft(nextRows)
  queueMicrotask(() => { selectedRows.value = nextRows; syncingTargetSelection = false })
}

async function rebindComprehensiveTargets(ids, { discardDraft = false } = {}) {
  const { targets: nextRows, missingIds } = resolveProductDesignTargets(rows.value, ids)
  if (missingIds.length) {
    const error = new Error(`服务端回读缺少原选择目标（稳定ID：${missingIds.join('、')}），未以其它可见行替代。`)
    error.code = 'PRODUCT_DESIGN_TARGET_READBACK_MISMATCH'
    throw error
  }
  if (discardDraft) comprehensiveDrafts.delete([...new Set(ids.map(String))].sort().join('|'))
  syncingTargetSelection = true
  try {
    selectedRows.value = nextRows
    loadComprehensiveDraft(nextRows)
    await nextTick()
    nextRows.forEach(row => tableRef.value?.toggleRowSelection?.(row, true))
    selectedRows.value = nextRows
  } finally {
    await nextTick()
    syncingTargetSelection = false
  }
}
function clearDesignSelection() {
  saveComprehensiveDraft()
  loadComprehensiveDraft([])
}
function clearAllDesignTargets() {
  selectComprehensiveTargets([])
}
function invalidPositiveNumber(source) {
  return ['designLength', 'designWidth', 'designThickness'].find(key => (
    Object.hasOwn(source, key)
    && source[key] !== ''
    && source[key] !== null
    && source[key] !== undefined
    && (!Number.isFinite(Number(source[key])) || Number(source[key]) <= 0)
  ))
}
const plannedImpactCount = computed(() => groups.value
  .filter(group => selectedDesignGroups.value.includes(group.designGroup))
  .reduce((total, group) => total + Number(group.productItemCount || 0), 0))
const planSaveBlocker = computed(() => !selectedDesignGroups.value.length ? '请选择需要安排计划的产品设计分组' : !planForm.designerEmployeeId ? '请选择设计负责人。' : !planForm.plannedStartDate ? '请填写计划开始日期。' : !planForm.plannedFinishDate ? '请填写计划完成日期。' : planForm.plannedFinishDate < planForm.plannedStartDate ? '计划完成日期不得早于开始日期。' : '')
const selectedDesignPatch = computed(() => Object.fromEntries(
  batchSelectedFields.value
    .map(key => [key, designForm[key]])
    .filter(([key, value]) => key === 'productDefinitionId' || (value !== '' && value !== null && (!Array.isArray(value) || value.length))),
))
const selectedFieldWithoutValue = computed(() => batchSelectedFields.value.find(key => !Object.hasOwn(selectedDesignPatch.value, key)))
const designSaveBlocker = computed(() => !selectedRows.value.length ? '未选择产品设计项。' : !batchSelectedFields.value.length ? '未选择要修改的字段。' : selectedRows.value.length !== 1 && batchSelectedFields.value.includes('productDefinitionId') ? '正式产品定义关联只允许单项明确维护。' : selectedFieldWithoutValue.value ? `已选择“${batchFieldOptions.find(row => row.value === selectedFieldWithoutValue.value)?.label}”，但尚未填写新值。` : !designReason.value.trim() ? '未填写修订原因。' : mixedDimensionSemantics.value && (batchSelectedFields.value.includes('designThickness') || batchSelectedFields.value.includes('designUomId')) ? '所选产品第三尺寸语义不同，请按实际适用范围分组操作。' : designUnitImpact.value.blocker ? designUnitImpact.value.blocker : invalidPositiveNumber(selectedDesignPatch.value) ? `${invalidPositiveNumber(selectedDesignPatch.value)} 当前值“${selectedDesignPatch.value[invalidPositiveNumber(selectedDesignPatch.value)]}”必须是大于0的数字。` : '')
const completionSaveBlocker = computed(() => !selectedRows.value.length ? '未选择产品设计项。' : !completionForm.completionBasis.trim() ? '未填写完成依据/说明。' : !completionForm.actualCompletionDate && !['HISTORICAL_EVIDENCE', 'REWORK'].includes(completionForm.completionNature) ? '当前完成性质必须填写实际完成日期。' : '')
const canSavePlan = computed(() => !planSaveBlocker.value)
const canSaveDesign = computed(() => !designSaveBlocker.value)
const canSaveCompletion = computed(() => !completionSaveBlocker.value)
function dimensionSemantic(row) { return row?.dimensionSemantic || '实际厚度' }
const selectedDimensionSemantics = computed(() => [...new Set(selectedRows.value.map(dimensionSemantic))])
const selectedOrderLines = computed(() => [...new Set(selectedRows.value.map(row => `${row.orderNo} / ${row.orderLineNo}`))])
const mixedDimensionSemantics = computed(() => selectedDimensionSemantics.value.length > 1)
const designUnitImpact = computed(() => {
  if (!batchSelectedFields.value.includes('designUomId') || !designForm.designUomId) return { rows: [], blocker: '' }
  const target = (masterOptions.value.uoms || []).find(unit => String(unit.id) === String(designForm.designUomId))
  if (!target || target.dimension !== 'length') return { rows: [], blocker: '设计尺寸单位必须选择正式长度单位。' }
  const impacts = []
  for (const row of selectedRows.value) {
    const current = row.designRevision || row.existingDesign || {}
    const sourceId = current.designUomId
    const source = (masterOptions.value.uoms || []).find(unit => String(unit.id) === String(sourceId))
    const dimensions = ['designLength', 'designWidth', 'designThickness'].filter(key => current[key] !== null && current[key] !== undefined && current[key] !== '')
    if (!source && dimensions.some(key => !batchSelectedFields.value.includes(key))) {
      return { rows: impacts, blocker: `${row.itemNo} 的现有尺寸单位未维护；必须同时明确填写全部已有尺寸值，不能只指定单位标签。` }
    }
    if (source && String(source.id) !== String(target.id)) {
      const sourceRoot = source.conversion_base_id || source.id
      const targetRoot = target.conversion_base_id || target.id
      if (source.dimension !== 'length' || String(sourceRoot) !== String(targetRoot)) {
        return { rows: impacts, blocker: `${row.itemNo} 的 ${source.name} 与 ${target.name} 缺少正式同维度换算关系。` }
      }
      const converted = dimensions.map(key => {
        if (batchSelectedFields.value.includes(key)) return `${key}=用户明确输入`
        return `${key}=${Number(current[key]) * Number(source.conversion_factor) / Number(target.conversion_factor)}`
      })
      impacts.push(`${row.itemNo}：${source.name} → ${target.name}；${converted.join('，')}`)
    }
  }
  return { rows: impacts, blocker: '' }
})
const rowDimensionSemantic = computed(() => `第三尺寸（${dimensionSemantic(rowDesignItem.value)}）`)
const designPatchLabels = computed(() => {
  const labels = Object.fromEntries(PRODUCT_DESIGN_INPUT_FIELDS.map(field => [field.inputKey, field.label]))
  return Object.entries(selectedDesignPatch.value).map(([key]) => labels[key] || key).join('、')
})
function optionText(options, value, fields = ['code', 'name']) {
  const option = (options || []).find(row => String(row.id ?? row.code) === String(value))
  return option ? fields.map(field => option[field]).filter(Boolean).join(' · ') : String(value ?? '未维护')
}
function batchExistingValue(row, key) {
  const current = row.designRevision || {}
  const existing = row.existingDesign || {}
  if (key === 'productCategoryId') return row.productCategoryLabel || '未匹配'
  if (key === 'productDefinitionId') return row.productDefinitionLabel || '未关联'
  if (key === 'physicalUomId') return row.physicalUom || '未匹配'
  if (key === 'designUomId') return current.designUomLabel || existing.designUomLabel || '未维护'
  if (['designLength', 'designWidth', 'designThickness'].includes(key)) return current[key] ?? existing[key] ?? '未维护'
  if (key === 'materialId') return current.materialName || existing.materialProcessCode || '未匹配'
  if (key === 'processConfigurationId') return current.processConfigurationLabel || existing.routingProcessCode || '未匹配'
  if (key === 'paintProcessTypeId') return current.paintProcessLabel || existing.paintProcess || '未匹配'
  if (key === 'edgeMethodId') return current.edgeMethodLabel || existing.edgeMethod || '未维护'
  if (key === 'visibleConditionCode') return current.visibleCondition || existing.visibleCondition || '未维护'
  if (key === 'colorVersionOptionId') return current.finishOrColor || existing.finishOrColor || '未维护'
  if (key === 'designNotes') return current.designNotes || existing.designNotes || '未维护'
  if (['configurationNotes', 'hardware', 'glass', 'documentReferences'].includes(key)) return current[key] || existing[key] || '未维护'
  return current[key] ?? existing[key] ?? '未维护'
}
function batchNewValue(key, value) {
  if (key === 'productCategoryId') return optionText(masterOptions.value.productCategories, value)
  if (key === 'productDefinitionId') return optionText(masterOptions.value.products, value, ['product_code', 'product_name'])
  if (key === 'physicalUomId') return optionText(masterOptions.value.uoms, value)
  if (key === 'designUomId') return optionText(masterOptions.value.uoms, value)
  if (key === 'materialId') return optionText(masterOptions.value.materials, value)
  if (key === 'processConfigurationId') return optionText(masterOptions.value.processConfigurations, value)
  if (key === 'paintProcessTypeId') return optionText(masterOptions.value.paintProcessTypes, value)
  if (key === 'edgeMethodId') return optionText(masterOptions.value.edgeMethods, value)
  if (key === 'visibleConditionCode') return optionText(masterOptions.value.visibleConditions, value, ['name', 'statusLabel'])
  if (key === 'colorVersionOptionId') return optionText(masterOptions.value.colorVersionOptions, value, ['name', 'statusLabel'])
  return String(value ?? '未填写')
}
const batchChangePreview = computed(() => batchSelectedFields.value.map(key => {
  const field = batchFieldOptions.find(row => row.value === key)
  const beforeValues = [...new Set(selectedRows.value.map(row => String(batchExistingValue(row, key))))]
  return {
    key, label: field?.label || key,
    before: beforeValues.length > 3 ? `${beforeValues.slice(0, 3).join('、')} 等${beforeValues.length}种` : beforeValues.join('、') || '未维护',
    after: Object.hasOwn(selectedDesignPatch.value, key) ? batchNewValue(key, selectedDesignPatch.value[key]) : '尚未填写',
  }
}))
const rowDesignPatch = computed(() => Object.fromEntries(Object.entries(rowDesignForm).filter(([key, value]) => JSON.stringify(value ?? null) !== JSON.stringify(rowDesignBaseline.value[key] ?? null))))
const rowDesignRequiresFullSnapshot = computed(() => Boolean(rowDesignItem.value) && rowDesignItem.value.designRevision?.designNature !== 'FORMAL')
const rowDesignSaveBlocker = computed(() => !rowDesignItem.value ? '未指定产品设计项。' : !rowDesignRequiresFullSnapshot.value && !Object.keys(rowDesignPatch.value).length ? '尚未修改本行设计字段。' : !rowDesignReason.value.trim() ? '未填写修订原因。' : invalidPositiveNumber(rowDesignForm) ? `${invalidPositiveNumber(rowDesignForm)} 当前值“${rowDesignForm[invalidPositiveNumber(rowDesignForm)]}”必须是大于0的数字。` : '')
const rowCompletionSaveBlocker = computed(() => !rowCompletionItem.value ? '未指定产品。' : !rowCompletionForm.completionBasis.trim() ? '未填写完成依据/说明。' : !rowCompletionForm.actualCompletionDate && !['HISTORICAL_EVIDENCE', 'REWORK'].includes(rowCompletionForm.completionNature) ? '当前完成性质必须填写实际完成日期。' : '')
const canAddItem = computed(() => addItemForm.orderLineNo && addItemForm.itemName.trim() && addItemForm.physicalQuantity && addItemForm.physicalUomId && addItemForm.productCategoryId && addItemForm.designLength && addItemForm.designWidth && addItemForm.designThickness && addItemForm.designUomId && addItemForm.dimensionSemantic && addItemForm.reason.trim())

function unwrap(response, fallback = '服务端请求失败。') {
  if (response?.success === false) {
    const payload = typeof response.error === 'object' ? response.error : { message: response.error }
    const error = new Error(payload?.message || fallback)
    error.response = { data: { error: payload } }
    throw error
  }
  if (response?.data?.success === false) {
    const payload = typeof response.data.error === 'object' ? response.data.error : { message: response.data.error }
    const error = new Error(payload?.message || fallback)
    error.response = { data: { error: payload } }
    throw error
  }
  return response?.data?.data ?? response?.data ?? response
}
function designValue(row, field) { return row.designRevision?.[field] ?? row.existingDesign?.[field] }
function expectedVersions() { return Object.fromEntries(selectedRows.value.map(row => [String(row.id), row.version])) }
function isRowSelected(row) { return selectedRows.value.some(selected => String(selected.id) === String(row.id)) }
function toggleBatchSelection(row) {
  tableRef.value?.toggleRowSelection?.(row, !isRowSelected(row))
}
function applyPayload(payload) {
  const currentById = new Map(rows.value.map(row => [String(row.id), row]))
  rows.value = (payload.rows || []).map(row => {
    const nextRow = {
      ...row,
      colorVersionLabel: row.designRevision?.finishOrColor || row.existingDesign?.finishOrColor || '待匹配',
      edgeMethodLabel: row.designRevision?.edgeMethodLabel || row.existingDesign?.edgeMethod || '未知',
      visibleConditionLabel: row.designRevision?.visibleCondition || row.existingDesign?.visibleCondition || '未知',
    }
    const current = currentById.get(String(row.id))
    if (!current) return nextRow
    Object.assign(current, nextRow)
    return current
  })
  groups.value = payload.groups || []
  orderContext.value = payload.orderContext || {}
  sourceContext.value = payload.sourceContext || {}
  reviewContext.value = payload.reviewContext || {}
  designerOptions.value = payload.designerOptions || []
  masterOptions.value = payload.masterOptions || {}
  listFieldContract.value = payload.listFieldContract || []
  assertProductDesignFieldContract(listFieldContract.value)
  strictFacts.value = payload.strictFacts || payload
}
const instanceContext = computed(() => Object.fromEntries(['companyId', 'orderEngineeringInstanceId', 'salesOrderId', 'salesOrderItemId', 'sourceRecordId', 'sourceVersion', 'authorizationId'].map(key => [key, route.query[key]])))
async function scopedDesignAction(body, key) {
  const sequence = factReadSequence
  const response = await pdeApi.productDesignAction({ ...body, ...(route.query.orderEngineeringInstanceId ? { instanceContext: instanceContext.value } : {}) }, key)
  if (sequence !== factReadSequence) throw new Error('订单上下文已切换，原保存响应已失效，请刷新目标订单核对。')
  return response
}
async function prepareItems() {
  saving.value = true
  const sequence = factReadSequence
  try {
    await scopedDesignAction({ action: 'INITIALIZE_ITEMS', instanceContext: instanceContext.value }, `design-prepare-${Date.now()}`)
    if (sequence === factReadSequence) await refresh()
  } catch (error) { ElMessage.error(explainDesignError(error, '首次准备失败。')) }
  finally { saving.value = false }
}
let factReadSequence = 0
async function refresh() {
  const sequence = ++factReadSequence
  const selectedIds = selectedRows.value.map(row => row.id)
  refreshStatus.value = 'refreshing'; loadError.value = ''
  try {
    const optionResponse = await pdeApi.facts('product-definitions', { mode: 'orders' })
    const { data: optionData } = readPceFactLoadEnvelope(optionResponse, '/api/pde/product-definitions/', 'pde-product-definitions')
    if (sequence !== factReadSequence) return
    orderOptions.value = optionData.orderOptions || []
    if (!route.query.orderNo && !route.query.orderEngineeringInstanceId) {
      orderContext.value = {}; sourceContext.value = {}; reviewContext.value = {}
      rows.value = []; groups.value = []; strictFacts.value = {}
      refreshStatus.value = 'awaiting-order'
      return
    }
    const response = await pdeApi.facts('product-definitions', {
      readAt: Date.now(),
      ...(route.query.orderEngineeringInstanceId ? instanceContext.value : {}),
      ...(route.query.orderNo ? { orderNo: String(route.query.orderNo) } : {}),
    })
    const { data } = readPceFactLoadEnvelope(response, '/api/pde/product-definitions/', 'pde-product-definitions')
    if (sequence !== factReadSequence) return
    applyPayload(data)
    refreshStatus.value = 'success'
    await nextTick()
    if (selectedIds.length) await rebindComprehensiveTargets(selectedIds)
    lastRefreshTime.value = new Date().toLocaleString('zh-CN')
  } catch (error) {
    if (sequence !== factReadSequence) return
    if (route.query.orderNo || !route.query.orderEngineeringInstanceId) {
      orderContext.value = {}
      sourceContext.value = {}
      reviewContext.value = {}
      rows.value = []
      groups.value = []
      strictFacts.value = {}
      tableRef.value?.clearSelection?.()
    }
    refreshStatus.value = 'error'
    loadError.value = error?.response?.data?.error?.message || error?.message || '产品设计服务端事实读取失败。'
  }
}
async function submit(action, body, label) {
  const targetIds = selectedRows.value.map(row => row.id)
  const ids = selectedRows.value.map(row => row.itemNo).join('、')
  await ElMessageBox.confirm(`将对明确选择的 ${selectedRows.value.length} 项执行“${label}”：${ids}。未选产品和未提交字段不会改变。`, `确认${label}`, { type: 'warning' })
  saving.value = true
  try {
    const payload = unwrap(await scopedDesignAction({ instanceContext: instanceContext.value, action, designItemIds: targetIds, expectedVersions: expectedVersions(), ...body }, `product-design-${action.toLowerCase()}-${Date.now()}`), `${label}失败。`)
    applyPayload(payload)
    await rebindComprehensiveTargets(targetIds, { discardDraft: true })
    ElMessage.success(`${label}成功；原选择目标已按稳定ID从服务端回读。`)
    return payload
  } catch (error) {
    if (error !== 'cancel') {
      const fallback = error?.code === 'PRODUCT_DESIGN_TARGET_READBACK_MISMATCH'
        ? `${label}已提交，但目标回读一致性校验失败；页面没有改选其它产品。`
        : `${label}失败。`
      ElMessage.error(explainDesignError(error, fallback))
    }
  } finally { saving.value = false }
}
async function savePlan() {
  const designGroups = [...selectedDesignGroups.value]
  const designer = designerOptions.value.find(row => row.employeeId === planForm.designerEmployeeId)
  const summary = { groupCount: designGroups.length, itemCount: plannedImpactCount.value, designer: designer?.fullName || '未识别', start: planForm.plannedStartDate, finish: planForm.plannedFinishDate }
  await ElMessageBox.confirm(`将为订单 ${orderContext.value.orderNo} 的 ${designGroups.join('、')} 保存设计计划，共影响 ${plannedImpactCount.value} 个设计项。`, '确认保存设计计划', { type: 'warning' })
  saving.value = true
  try {
    const payload = unwrap(await scopedDesignAction({ action: 'SAVE_PLAN', designGroups, ...planForm }, `product-design-save-plan-${orderContext.value.orderId}-${Date.now()}`), '保存计划失败。')
    applyPayload(payload)
    lastPlanSaveSummary.value = summary
    ElMessage.success('设计计划保存成功并已从服务端回读。')
    return payload
  } catch (error) {
    if (error !== 'cancel') ElMessage.error(explainDesignError(error, '保存计划失败。'))
    return null
  } finally { saving.value = false }
}
function nonEmptyDesignPatch(source) { return Object.fromEntries(Object.entries(source).filter(([, value]) => value !== '' && value !== null && (!Array.isArray(value) || value.length))) }
function saveDesign() {
  if (mixedDimensionSemantics.value && (batchSelectedFields.value.includes('designThickness') || batchSelectedFields.value.includes('designUomId'))) {
    ElMessage.warning('所选产品包含不同第三尺寸语义，请按墙厚、部件厚或实际厚度分组操作。')
    return
  }
  return submit('SAVE_DESIGN', { designNature: route.query.orderEngineeringInstanceId ? 'SIMULATED_FOR_TEST' : designNature.value, designData: selectedDesignPatch.value, reason: designReason.value }, '保存设计')
}
function saveCompletion() { return submit('RECORD_COMPLETION', { ...completionForm }, completionForm.completionNature === 'HISTORICAL_EVIDENCE' ? '登记历史完成' : '完成设计') }
function showEvidence(row) { evidenceRow.value = row; evidenceVisible.value = true }
function openAddItem() {
  Object.assign(addItemForm, { orderLineNo: null, itemName: '', installationPosition: '', physicalQuantity: '', physicalUomId: null, productCategoryId: null, designLength: '', designWidth: '', designThickness: '', designUomId: null, dimensionSemantic: '', reason: '' })
  addItemVisible.value = true
}
async function saveAddItem() {
  await ElMessageBox.confirm(`将在订单第${addItemForm.orderLineNo}行新增“${addItemForm.itemName}”，不会建立永久物料。`, '确认新增设计项', { type: 'warning' })
  saving.value = true
  try {
    const payload = unwrap(await scopedDesignAction({ action: 'ADD_ITEM', ...addItemForm }, `product-design-add-${Date.now()}`))
    applyPayload(payload); addItemVisible.value = false; ElMessage.success('设计项已新增并从服务端回读。')
  } catch (error) { if (error !== 'cancel') ElMessage.error(error?.response?.data?.error?.message || error?.message || '新增失败。') }
  finally { saving.value = false }
}
async function deleteRow(row) {
  try {
    const { value } = await ElMessageBox.prompt(`系统将先检查 ${row.itemNo} 的来源、计划、修订和完成引用。已有历史的记录会拒绝物理删除。`, '删除或保护检查', { inputPlaceholder: '请输入删除原因', inputValidator: value => Boolean(String(value || '').trim()) || '必须填写原因', type: 'warning' })
    const payload = unwrap(await scopedDesignAction({ action: 'DELETE_ITEM', designItemIds: [row.id], expectedVersions: { [String(row.id)]: row.version }, reason: value }, `product-design-delete-${row.id}-${Date.now()}`))
    applyPayload(payload); ElMessage.success('未引用设计项已删除并从服务端回读。')
  } catch (error) { if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.response?.data?.error?.message || error?.message || '该记录受历史保护，未删除。') }
}
async function downloadImportTemplate() {
  try {
    const payload = unwrap(await pdeApi.productDesignImportTemplate())
    const blob = payload instanceof Blob ? payload : new Blob([payload], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = '产品设计导入模板.xlsx'; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch (error) { ElMessage.error(error?.message || '模板下载失败。') }
}
function chooseImportFile() { importFileInput.value?.click() }
async function previewImportFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importFile.value = file
  saving.value = true
  try {
    importPreview.value = unwrap(await pdeApi.previewProductDesignImport(file))
    importVisible.value = true
  } catch (error) { ElMessage.error(error?.response?.data?.error?.message || error?.message || '导入预览失败。') }
  finally { saving.value = false }
}
async function commitImport() {
  await ElMessageBox.confirm(`将按预览提交 ${importPreview.value.validCount} 行；更新使用产品标识，新增进入所选订单行。`, '确认正式导入', { type: 'warning' })
  saving.value = true
  try {
    const result = unwrap(await pdeApi.commitProductDesignImport(importFile.value, importPreview.value.previewFingerprint, `product-design-import-${Date.now()}`))
    applyPayload(result.readback || result); importVisible.value = false; ElMessage.success(`已导入 ${result.committedCount} 行并回读。`)
  } catch (error) { if (error !== 'cancel') ElMessage.error(error?.response?.data?.error?.message || error?.message || '导入提交失败。') }
  finally { saving.value = false }
}
const colorVersionOptionsForRow = computed(() => {
  const options = [...(masterOptions.value.colorVersionOptions || [])]
  const value = rowDesignItem.value?.designRevision?.finishOrColor || rowDesignItem.value?.existingDesign?.finishOrColor || ''
  if (value && !options.some(option => option.name === value)) options.push({ id: `CURRENT-${rowDesignItem.value.id}`, name: value, statusLabel: '本行历史快照' })
  return options
})
const batchProcessConfigurationOptions = computed(() => {
  const selectedIds = selectedRows.value.map(row => row.id)
  return (masterOptions.value.processConfigurations || []).filter(option => !selectedIds.length || selectedIds.every(id => option.compatibleItemIds?.includes(id)))
})
const rowProcessConfigurationOptions = computed(() => (masterOptions.value.processConfigurations || []).filter(option => option.compatibleItemIds?.includes(rowDesignItem.value?.id)))
const rowProductOptions = computed(() => (masterOptions.value.products || []).filter(option => (
  String(option.category_id || '') === String(rowDesignForm.productCategoryId || '')
)))
const rowProductSelectionNotice = computed(() => {
  if (!rowDesignForm.productCategoryId) return '请先选择产品分类；已有设计仍可直接修改其它字段。'
  return rowProductOptions.value.length ? '' : '当前分类暂无正式产品定义；可继续完成客户订单工程设计，不会自动创建产品定义。'
})
const rowSelectedMaterial = computed(() => (masterOptions.value.materials || []).find(option => String(option.id) === String(rowDesignForm.materialId)) || null)
const rowSelectedProcessConfiguration = computed(() => rowProcessConfigurationOptions.value.find(option => String(option.id) === String(rowDesignForm.processConfigurationId)) || null)
const rowSelectedPaintProcess = computed(() => (masterOptions.value.paintProcessTypes || []).find(option => String(option.id) === String(rowDesignForm.paintProcessTypeId)) || null)
const rowMaterialIdentityNotice = computed(() => {
  const match = rowDesignItem.value?.matchResults?.material
  const material = rowSelectedMaterial.value
  if (match?.status !== 'IDENTITY_MATCH' || !material) return ''
  const payload = [material.code, material.name, material.specification].filter(Boolean).join(' · ')
  return `材料来源码“${match.sourceValue}”已通过稳定来源身份匹配正式材料${payload ? `“${payload}”` : ''}；名称和规格显示当前正式主数据。`
})
const rowProcessConfigurationNotice = computed(() => {
  const option = rowProcessConfigurationOptions.value.find(row => String(row.id) === String(rowDesignForm.processConfigurationId))
  return option?.selectable === false ? '未匹配正式工艺路线，保留来源值' : ''
})
const rowUnmatchedSourceFacts = computed(() => {
  const row = rowDesignItem.value
  if (!row) return []
  const results = []
  const add = (label, matchKey, sourceValue) => {
    const match = row.matchResults?.[matchKey]
    if (sourceValue && !match?.matchedId) results.push(`${label}“${sourceValue}”`)
  }
  add('材料', 'material', row.existingDesign?.materialProcessCode)
  if (row.listValues?.processConfigurationCode && row.listValues?.processConfigurationName === '未匹配正式工艺路线，保留来源值') results.push(`工艺配置“${row.listValues.processConfigurationCode}”：未匹配正式工艺路线，保留来源值`)
  add('油漆工艺', 'paintProcess', row.existingDesign?.paintProcess)
  add('封边方式', 'edgeMethod', row.existingDesign?.edgeMethod)
  return results
})
function applyBatchProcessConfiguration(configurationId) {
  const option = (masterOptions.value.processConfigurations || []).find(row => row.id === configurationId)
  if (option?.paintProcessTypeId) designForm.paintProcessTypeId = option.paintProcessTypeId
}
function applyRowProcessConfiguration(configurationId) {
  const option = (masterOptions.value.processConfigurations || []).find(row => row.id === configurationId)
  if (option?.paintProcessTypeId) rowDesignForm.paintProcessTypeId = option.paintProcessTypeId
}
function handleRowProductCategoryChange() {
  if (!rowProductOptions.value.some(option => String(option.id) === String(rowDesignForm.productDefinitionId))) {
    rowDesignForm.productDefinitionId = null
  }
}
function openRowDesign(row) {
  rowDesignItem.value = row
  const revision = row.designRevision || {}
  const existing = row.existingDesign || {}
  const currentValue = key => revision[key] ?? existing[key] ?? ''
  const visible = (masterOptions.value.visibleConditions || []).find(option => option.code === currentValue('visibleConditionCode') || option.name === currentValue('visibleCondition'))
  const color = (masterOptions.value.colorVersionOptions || []).find(option => option.id === currentValue('colorVersionOptionId') || option.name === currentValue('finishOrColor'))
  const nextForm = {
    productCategoryId: row.productCategoryId || null,
    productDefinitionId: row.productDefinitionId || null,
    physicalUomId: row.physicalUomId || null, designUomId: currentValue('designUomId') || null,
    designLength: currentValue('designLength'), designWidth: currentValue('designWidth'), designThickness: currentValue('designThickness'),
    materialId: currentValue('materialId') || row.matchResults?.material?.matchedId || null,
    processConfigurationId: currentValue('processConfigurationId') || row.matchResults?.processConfiguration?.matchedId || (masterOptions.value.processConfigurations || []).find(option => option.code === currentValue('routingProcessCode'))?.id || null,
    paintProcessTypeId: currentValue('paintProcessTypeId') || row.matchResults?.paintProcess?.matchedId || null,
    edgeMethodId: currentValue('edgeMethodId') || row.matchResults?.edgeMethod?.matchedId || null,
    visibleConditionCode: visible?.code || null, colorVersionOptionId: color?.id || (currentValue('finishOrColor') ? `CURRENT-${row.id}` : null),
    configurationNotes: currentValue('configurationNotes'), designNotes: currentValue('designNotes'),
    hardware: currentValue('hardware'), glass: currentValue('glass'),
    documentReferences: currentValue('documentReferences') || [],
  }
  Object.assign(rowDesignForm, nextForm)
  rowDesignBaseline.value = structuredClone(nextForm)
  rowDesignReason.value = ''
  rowDesignVisible.value = true
}
function openRowCompletion(row) {
  rowCompletionItem.value = row
  Object.assign(rowCompletionForm, {
    completionNature: row.completion?.actualCompletionDate ? row.completion.completionNature : 'HISTORICAL_EVIDENCE',
    actualCompletionDate: row.completion?.actualCompletionDate || '',
    designerEmployeeId: row.completion?.completedDesigner?.employeeId || null,
    completionBasis: '',
  })
  rowCompletionVisible.value = true
}
async function saveRowCompletion() {
  const row = rowCompletionItem.value
  if (!row || rowCompletionSaveBlocker.value) return
  saving.value = true
  try {
    const payload = unwrap(await scopedDesignAction({ action: 'RECORD_COMPLETION', designItemIds: [row.id], expectedVersions: { [String(row.id)]: row.version }, ...rowCompletionForm }, `product-design-row-completion-${row.id}-${Date.now()}`))
    applyPayload(payload); rowCompletionVisible.value = false; ElMessage.success('本行完成记录已保存并从服务端回读。')
  } catch (error) { ElMessage.error(error?.response?.data?.error?.message || error?.message || '本行完成登记失败。') }
  finally { saving.value = false }
}
async function saveRowDesign() {
  const row = rowDesignItem.value
  if (!row) return
  await ElMessageBox.confirm(`只保存 ${row.itemNo} 的当前设计并新增修订；其它设计项不改变。`, '确认保存本行设计', { type: 'warning' })
  saving.value = true
  try {
    const requiresFullSnapshot = row.designRevision?.designNature !== 'FORMAL'
    // The first formal revision is a complete snapshot of the visible form.
    // Source/master-data prefills are part of that snapshot even when the user
    // did not change them after opening the editor. Later formal revisions keep
    // the existing patch semantics so untouched values are inherited.
    const data = requiresFullSnapshot ? structuredClone(rowDesignForm) : nonEmptyDesignPatch(rowDesignPatch.value)
    if (requiresFullSnapshot || Object.hasOwn(rowDesignPatch.value, 'productDefinitionId')) {
      data.productDefinitionId = rowDesignForm.productDefinitionId
    }
    // The three visible dimensions are always submitted from this row form.
    // This makes the request body identical to what the user is validating on screen.
    for (const key of ['designLength', 'designWidth', 'designThickness']) data[key] = rowDesignForm[key]
    if (String(data.colorVersionOptionId || '').startsWith('CURRENT-')) {
      delete data.colorVersionOptionId
      data.finishOrColor = row.designRevision?.finishOrColor || row.existingDesign?.finishOrColor || ''
    }
    const payload = unwrap(await scopedDesignAction({ instanceContext: instanceContext.value, action: 'SAVE_DESIGN', designItemIds: [row.id], expectedVersions: { [String(row.id)]: row.version }, designNature: route.query.orderEngineeringInstanceId ? 'SIMULATED_FOR_TEST' : 'FORMAL', designData: data, reason: rowDesignReason.value }, `product-design-row-${row.id}-${Date.now()}`))
    applyPayload(payload); rowDesignVisible.value = false; ElMessage.success('本行设计已保存并从服务端回读。')
  } catch (error) { if (error !== 'cancel') ElMessage.error(explainDesignError(error, '本行设计保存失败。')) }
  finally { saving.value = false }
}
function explainDesignError(error, fallback) {
  const payload = error?.response?.data?.error || error?.response?.data || {}
  const details = payload.details || {}
  if (details.field) return `${details.field}：当前值“${details.currentValue ?? '空'}”；${details.reason || payload.message || fallback}；${details.suggestedAction || '请更正后重试。'}`
  return payload.message || error?.message || fallback
}
async function exportProductDesignExcel() {
  if (!filteredRows.value.length) { ElMessage.warning('当前筛选结果为0条，未生成空导出文件。'); return }
  try {
    const response = await pdeApi.exportProductDesign({
      designItemIds: filteredRows.value.map(row => row.id),
      expectedVersions: Object.fromEntries(filteredRows.value.map(row => [String(row.id), row.version])),
      filterSummary: { quickSearch: appliedSearch.value, ...Object.fromEntries(Object.entries(filters).filter(([, value]) => value && (!Array.isArray(value) || value.length))) },
      sortSummary: sortText.value,
    })
    const blob = unwrap(response, '产品设计Excel导出失败。')
    if (!(blob instanceof Blob)) throw new Error('导出接口未返回XLSX二进制文件。')
    const signature = new Uint8Array(await blob.slice(0, 4).arrayBuffer())
    if (signature[0] !== 0x50 || signature[1] !== 0x4B) throw new Error('导出接口返回的不是有效XLSX文件，已阻止下载错误对象。')
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a'); link.href = url; link.download = `产品设计当前结果-${new Date().toISOString().slice(0, 19).replaceAll(':', '')}.xlsx`; link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    ElMessage.success(`已导出当前筛选结果 ${filteredRows.value.length} 项，文件来自服务端当前事实。`)
  } catch (error) { ElMessage.error(explainDesignError(error, '产品设计Excel导出失败。')) }
}
function diagnostics() {
  return {
    pageCode: 'pde-product-definitions', factSource: 'server', orderContext: orderContext.value,
    sourceContext: sourceContext.value, reviewContext: reviewContext.value, strictFacts: strictFacts.value,
    selectedDesignItemCount: selectedRows.value.length, activeSection: activeSection.value,
    expectedSourceCounts: strictFacts.value.expectedSourceCounts,
    actualSourceCounts: strictFacts.value.actualSourceCounts,
    legacyD1Count: strictFacts.value.legacyD1Count,
    permanentProductCreated: false, productVersionCreated: false,
    orderEngineeringInstanceCreated: false, publishedDownstreamObjectCount: 0,
  }
}
let provider
onMounted(async () => { provider = { factOwner: 'pde-product-definitions', refresh, buildDiagnostics: diagnostics }; observability?.register?.(provider); await refresh(); observability?.register?.(provider) })
watch(() => JSON.stringify(route.query), () => {
  factReadSequence += 1
  approvalFacts.value = {}; approvalReason.value = ''
  rowDesignVisible.value = false; rowCompletionVisible.value = false
  addItemVisible.value = false; importVisible.value = false; evidenceVisible.value = false
  rangeConfirmVisible.value = false; rowDesignItem.value = null; rowCompletionItem.value = null
  selectedRows.value = []; selectedDesignGroups.value = []
  targetCategoryFilter.value = null; targetGroupFilter.value = ''
  designNature.value = route.query.orderEngineeringInstanceId ? 'SIMULATED_FOR_TEST' : 'FORMAL'
  activeSection.value = route.query.orderEngineeringInstanceId ? 'design' : 'plan'
  orderContext.value = {}; sourceContext.value = {}; reviewContext.value = {}
  comprehensiveDrafts.clear(); designReason.value = ''; rowDesignReason.value = ''
  rows.value = []; groups.value = []; strictFacts.value = {}
  tableRef.value?.clearSelection?.()
  refresh()
})
onBeforeUnmount(() => { factReadSequence += 1; observability?.unregister?.(provider) })
</script>

<style scoped>
.batch-steps,.batch-field-selector{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:10px 0;padding:10px 12px;border-radius:8px;background:#f8fafc}
.design-page{display:grid;gap:18px;min-width:0}.card{min-width:0;padding:20px;border:1px solid #dce4ed;border-radius:12px;background:#fff}.section-heading,.operation-intro{display:flex;align-items:center;justify-content:space-between;gap:16px}.section-heading h2{margin:4px 0 0}.section-heading small,.context-grid small,.group-grid small{color:#64748b}.nature{padding:6px 10px;border-radius:999px;background:#e8f5ee;color:#256044;font-weight:700}.context-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}.context-grid article,.group-grid article{display:grid;gap:5px;padding:12px;border-radius:8px;background:#f6f8fb}.quantity-definition{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px;padding:12px;border-radius:8px;background:#eef6ff;color:#27435f}.quantity-definition small{width:100%;color:#64748b}.boundary-note{margin:14px 0 0;color:#466252}.error-card{display:flex;gap:12px;align-items:center}.group-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:14px}.operation-intro{margin-bottom:14px;padding:10px 12px;border-radius:8px;background:#f8fafc}.batch-preview{display:grid;gap:4px;margin:10px 0;padding:10px 12px;border:1px solid #bfdbfe;border-radius:8px;background:#eff6ff;color:#1e3a5f}.operation-form,.row-design-form{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;align-items:end}.operation-form.design-fields{grid-template-columns:repeat(5,minmax(0,1fr))}.operation-form .wide,.row-design-form .wide{grid-column:span 2}.operation-form :deep(.el-select),.operation-form :deep(.el-date-editor),.row-design-form :deep(.el-select){width:100%}.operation-form :deep(.el-form-item),.row-design-form :deep(.el-form-item){margin-bottom:0}.row-edit-context{display:flex;justify-content:space-between;gap:16px;margin-bottom:16px;padding:12px;border-radius:8px;background:#f1f5f9}.design-tools{display:flex;gap:8px;flex-wrap:wrap}.hidden-file{display:none}.list-card{overflow:hidden}.list-card>.section-heading{margin-bottom:12px}pre{max-height:360px;overflow:auto;padding:12px;border-radius:8px;background:#0f172a;color:#dbeafe;font-size:12px;white-space:pre-wrap}@media(max-width:1200px){.context-grid,.group-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.operation-form,.operation-form.design-fields,.row-design-form{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:720px){.context-grid,.group-grid,.operation-form,.operation-form.design-fields,.row-design-form{grid-template-columns:1fr}.operation-form .wide,.row-design-form .wide{grid-column:auto}.section-heading,.operation-intro,.row-edit-context{align-items:flex-start;flex-direction:column}}
.save-action{display:grid;gap:5px}.save-blocker{color:#9a3412}.field-notice{display:block;margin-top:5px;color:#9a3412;line-height:1.45}
.target-selector{display:grid;grid-template-columns:1fr 1fr 2fr;gap:12px;padding:14px;border:1px solid #cbd5e1;border-radius:10px;background:#f8fafc}.target-selector .wide{grid-column:span 1}.target-selector :deep(.el-select){width:100%}.target-count,.unit-impact{display:grid;gap:5px;grid-column:1/-1;padding:10px 12px;border-radius:8px;background:#fff}.target-count span{font-size:12px;color:#475569}.current-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0;padding:12px;border-radius:8px;background:#eef6ff}.unit-impact{margin:10px 0;border:1px solid #facc15;background:#fefce8;color:#713f12}.unit-impact span{font-size:12px}.error-text{color:#b91c1c}
.range-target-action{display:flex;align-items:center;justify-content:space-between;gap:16px;grid-column:1/-1;padding:12px;border:1px solid #bfdbfe;border-radius:8px;background:#eff6ff}.range-target-action>div{display:grid;gap:4px}.range-target-action span,.range-target-action small{color:#475569}.range-summary{margin:14px 0}.range-preview-table{margin-bottom:12px}.range-confirm-note{margin:14px 0 0;color:#475569;line-height:1.6}
@media(max-width:1200px){.target-selector,.current-facts{grid-template-columns:repeat(2,minmax(0,1fr))}.target-selector .wide{grid-column:span 2}}
@media(max-width:720px){.target-selector,.current-facts{grid-template-columns:1fr}.target-selector .wide{grid-column:auto}.range-target-action{align-items:flex-start;flex-direction:column}}
</style>
