<template>
  <section class="sales-order-workbench" data-page-code="sales-orders" data-page-template="PceListPageShell" data-enterprise-list-contract="PCE-ENTERPRISE-LIST-CONTRACT-V1.1" data-order-operating-system="V1" data-ui-read-version="B4-ORDER-READ-R1" :data-request-read-ms="readDuration" :data-visible-read-ms="visibleDuration" :data-fact-load-status="factLoadStatus" :aria-busy="loading" :data-source-intake-mode="previewMode || engineeringFormalizationMode || developmentContractMode">
    <NewOrderSource v-if="route.query.mode === 'new-order-source'" />
    <DevelopmentContractSamplePage v-else-if="developmentContractMode" />
    <EngineeringSourceFormalizationPreview v-else-if="engineeringFormalizationMode" />
    <WholeHouseOrderPreview v-else-if="previewMode" />
    <template v-else>
    <section class="summary-card" aria-label="订单事实摘要">
      <div><p class="eyebrow">ORDER OPERATING SYSTEM / V1</p><h2>销售订单工作台</h2><p>订单 → 订单明细 → 工程准备 → 制造准备。页面只显示服务端正式事实。</p></div>
      <div class="summary-actions"><el-button @click="router.push({ query: { mode: 'new-order-source' } })">新建接单来源</el-button><el-button @click="openHistoricalSource">历史来源办理</el-button><el-button :loading="loading" @click="loadFacts">刷新</el-button><el-button v-if="can('sales.order.create')" type="primary" @click="openCreate">新建订单</el-button></div>
    </section>
    <section class="development-entry-card" aria-label="开发合同与报价入口">
      <div>
        <p class="eyebrow">开发联调样本</p>
        <h3>开发合同与报价</h3>
        <template v-if="developmentEntry">
          <p>{{ developmentEntry.customerName }}；{{ developmentEntry.projectName }}；{{ developmentEntry.sourceOrderNo }}；{{ developmentEntry.purposeLabel }}</p>
          <p>{{ developmentEntry.contractNo }}；{{ developmentEntry.commercialLineCount }}条商业行；{{ developmentEntry.sourceRowCount }}条工程来源；含税合计 {{ money(developmentEntry.grossAmount) }} 元。</p>
          <p v-if="!developmentEntry.viewDecision?.allowed" class="entry-permission">当前身份查看门禁：{{ developmentEntry.viewDecision?.reason }}</p>
        </template>
        <p v-else-if="developmentEntryError" class="entry-permission">{{ developmentEntryError }}</p>
        <p v-else>正在解析已配置的开发合同来源。</p>
      </div>
      <el-button type="primary" :loading="developmentEntryLoading" :disabled="!developmentEntry" @click="openDevelopmentContract">开发合同与报价</el-button>
    </section>
    <div v-if="errorMessage" class="read-failure-actions">
      <el-alert :title="errorMessage" :type="authenticationRequired ? 'warning' : 'error'" show-icon :closable="false" />
      <div>
        <el-button v-if="authenticationRequired" type="primary" @click="goToLogin">正常登录并返回本页</el-button>
        <el-button :loading="loading" @click="loadFacts">重新读取</el-button>
      </div>
    </div>
    <section class="metric-grid">
      <article><span>订单总数</span><strong>{{ factCount(orders.length) }}</strong></article><article><span>待审批</span><strong>{{ factCount(orders.filter(x => x.status === 'submitted').length) }}</strong></article>
      <article><span>工程准备中</span><strong>{{ factCount(orders.filter(x => x.status === 'engineering').length) }}</strong></article><article><span>制造已就绪</span><strong>{{ factCount(orders.filter(x => x.engineeringReadiness?.ready).length) }}</strong></article>
      <article><span>生产数据写入</span><strong>{{ factCount(strictFacts.productionWriteCount) }}</strong></article>
    </section>
    <section v-if="loading" class="list-card loading-facts" role="status" aria-live="polite" data-fact-load-result="loading"><strong>正在读取授权订单</strong><p>正在等待订单服务返回，数量尚未取得；无需重复刷新。</p></section>
    <section v-else-if="factsAvailable" class="list-card">
      <PceEnterpriseListTable ref="tableRef" :contract="listContract" page-id="sales-orders" table-id="sales-order-table" :rows="orders" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length" :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="orderNo" primary-label="销售订单编号" :primary-width="180" min-width="1900px" :show-refresh="true" :refreshing="loading" :action-width="310" @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch" @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection" @update-filter="updateFilter" @selection-change="selectedRows=$event" @sort-change="handleSort" @refresh="loadFacts">
        <template #primary="{ row }"><el-button link type="primary" @click="showDetail(row)">{{ row.orderNo }}</el-button></template>
        <template #columns>
          <el-table-column prop="customerName" label="客户名称" width="180" sortable show-overflow-tooltip/><el-table-column prop="orderTypeLabel" label="订单类型" width="110"/><el-table-column prop="projectReference" label="项目" width="150" show-overflow-tooltip/><el-table-column prop="departmentName" label="销售部门名称" width="140"/><el-table-column prop="salesOwnerName" label="销售负责人" width="120"/>
          <el-table-column prop="orderDate" label="订单日期" width="120" sortable/><el-table-column prop="requiredDate" label="客户要求交期" width="135" sortable/><el-table-column prop="deliveryFacts.committedDeliveryDate" label="企业承诺交期" width="135"><template #default="{ row }">{{ dateText(row.deliveryFacts?.committedDeliveryDate) }}</template></el-table-column><el-table-column prop="totalAmount" label="订单金额" width="130" align="right" sortable/><el-table-column prop="currency" label="币种" width="80"/>
          <el-table-column prop="statusLabel" label="销售订单状态" width="130"><template #default="{ row }"><PceBusinessStatus :status-label="row.statusLabel" :status-code="row.status" source="server"/></template></el-table-column><el-table-column prop="engineeringStatus" label="工程状态" width="130"/><el-table-column prop="manufacturingReadinessStatus" label="制造准备" width="110"/><el-table-column prop="deliveryStatus" label="交付状态" width="100"/><el-table-column prop="settlementStatus" label="结算状态" width="100"/>
        </template>
        <template #actions="{ row }"><el-button link type="primary" @click="showDetail(row)">查看</el-button><el-button v-if="row.status==='draft' && can('sales.order.update')" link @click="openEdit(row)">编辑</el-button><el-button v-for="action in actionsFor(row)" :key="action.code" link :type="action.type" @click="executeAction(row, action)">{{ action.label }}</el-button></template>
      </PceEnterpriseListTable>
    </section>
    <section v-else class="list-card unavailable-facts" data-fact-load-result="unavailable">
      <strong>未取得订单数据</strong>
      <p>当前结果数量未知；请先处理上方明确原因后刷新。此状态不能解释为真实订单为 0 条。</p>
    </section>
    <el-drawer v-model="detailVisible" size="78%" :title="detailOrder ? `订单详情 / ${detailOrder.orderNo}` : '订单详情'">
      <template v-if="detailOrder">
        <section class="detail-facts"><span>客户名称：<strong>{{ detailOrder.customerName }}</strong></span><span>销售订单状态：<strong>{{ detailOrder.statusLabel }}</strong></span><span>金额：<strong>{{ detailOrder.currency }} {{ detailOrder.totalAmount }}</strong></span><span>客户要求交期：<strong>{{ dateText(detailOrder.deliveryFacts?.customerRequiredDate) }}</strong></span><span>企业承诺交期：<strong>{{ dateText(detailOrder.deliveryFacts?.committedDeliveryDate) }}</strong></span><span>计划完成时间：<strong>{{ predictionText(detailOrder.deliveryFacts?.plannedCompletionDate) }}</strong></span><span>实际交付时间：<strong>{{ dateText(detailOrder.deliveryFacts?.actualDeliveryDate) }}</strong></span></section>
        <el-tabs>
          <el-tab-pane label="01 基本信息"><p>订单编号：{{ detailOrder.orderNo }}；订单日期：{{ detailOrder.orderDate }}；类型：{{ detailOrder.orderTypeLabel }}；来源：{{ detailOrder.orderSourceLabel }}</p><p>销售组织：{{ detailOrder.departmentName }}；负责人：{{ detailOrder.salesOwnerName || '未指定' }}</p>
            <section v-for="link in detailOrder.reviewLinks || []" :key="link.reviewId">
              <p>关联来源 {{ link.sourceRecordId }}／版本 {{ link.sourceVersion }}</p>
              <p>关联评审 {{ link.reviewId }}／V{{ link.reviewVersion }} · 订单行 {{ link.lineNos.join('、') }}</p>
              <p v-if="!link.risk" role="alert">原评审风险内容未返回，请刷新或联系管理员核对详情接口。</p>
              <p v-else>以下为原评审 {{ link.reviewId }}／V{{ link.reviewVersion }} 的意见和审批记录。</p>
              <article v-for="item in link.risk?.disagreements || []" :key="item.itemCode">
                <p>第 {{ item.itemCode }} 项 · 判定 不同意 · 责任人 {{ item.responsibleName }} · 签认时间 {{ dateText(item.signedAt) }}</p>
                <p>{{ item.itemText }}</p>
                <p>原因 {{ item.reason }} {{ item.reasonText }}</p>
                <p style="white-space: pre-wrap">补充说明 {{ item.evidence }}</p>
              </article>
              <article v-if="link.risk?.finalDecision">
                <p>原审批人 {{ link.risk.finalDecision.approver.name }}（{{ link.risk.finalDecision.approver.username }}） · 时间 {{ dateText(link.risk.finalDecision.approvedAt) }}</p>
                <p>原审批意见 {{ link.risk.finalDecision.approvalOpinion || '未填写' }}</p>
                <p style="white-space: pre-wrap">风险处理说明 {{ link.risk.finalDecision.riskHandling || '未填写' }}</p>
              </article>
              <router-link :to="{ path: '/sales/order-reviews', query: { sourceRecord: link.sourceRecordId } }">查看原评审记录</router-link>
              <router-link :to="{ path: '/pde/product-requirement-reviews', query: { sourceRecord: link.sourceRecordId, salesOrderId: detailOrder.id, crmOrderRelationId: link.relationId } }">进入本单生产可行性评审</router-link>
            </section>
          </el-tab-pane>
          <el-tab-pane label="02 客户与商务"><p>客户：{{ detailOrder.customerCode }} / {{ detailOrder.customerName }}</p><p>项目：{{ detailOrder.projectReference || '未填写' }}；合同：{{ detailOrder.contractReference || '未填写' }}；币种：{{ detailOrder.currency }}</p></el-tab-pane>
          <el-tab-pane label="03 订单明细"><el-table :data="detailOrder.items" border><el-table-column prop="lineNo" label="行" width="60"/><el-table-column prop="statusLabel" label="有效/取消" width="110"/><el-table-column prop="spaceName" label="空间/房间" width="130"/><el-table-column prop="materialCode" label="物料编码" width="130"/><el-table-column prop="materialName" label="物料名称" min-width="170"/><el-table-column prop="specification" label="规格" min-width="150"><template #default="{ row }">{{ row.specification || '未维护' }}</template></el-table-column><el-table-column prop="engineeringModeLabel" label="工程模式" width="140"/><el-table-column prop="quantity" label="数量" width="100"/><el-table-column prop="uomCode" label="单位" width="80"/><el-table-column prop="unitPrice" label="单价" width="110"/><el-table-column label="计价口径" width="110"><template #default="{ row }">{{ priceModeLabel(row.priceTaxMode) }}</template></el-table-column><el-table-column label="税率" width="90"><template #default="{ row }">{{ taxRateLabel(row.taxRate) }}</template></el-table-column><el-table-column label="税率维护" width="120"><template #default="{ row }"><el-button v-if="detailOrder.status === 'draft' && can('sales.order.update')" link type="primary" @click="openTaxEdit(row)">编辑税率</el-button></template></el-table-column><el-table-column label="供应承接" width="150"><template #default="{ row }"><el-button link type="primary" @click="supplyItemId=row.id; supplyVisible=true">供应承接确认</el-button></template></el-table-column><el-table-column prop="amount" label="金额" width="120"/><el-table-column prop="requiredDate" label="客户要求交期" width="135"/></el-table></el-tab-pane>
          <el-tab-pane label="04 空间/产品结构"><el-table :data="detailOrder.items" border><el-table-column prop="spaceCode" label="空间编码"/><el-table-column prop="spaceName" label="空间名称"/><el-table-column prop="installationArea" label="安装区域"/><el-table-column prop="componentCategory" label="构成分类"/><el-table-column prop="productCode" label="产品编码"/><el-table-column prop="productConfigurationNo" label="产品配置"/></el-table></el-tab-pane>
          <el-tab-pane label="05 工程结构"><el-table :data="detailOrder.engineeringReadiness?.lines || []" border><el-table-column prop="lineNo" label="订单行" width="90"/><el-table-column prop="engineeringMode" label="工程模式" width="160"/><el-table-column label="准备结果" width="110"><template #default="{ row }">{{ row.ready ? '已就绪' : '未就绪' }}</template></el-table-column><el-table-column label="阻断原因" min-width="260"><template #default="{ row }">{{ row.blockers.join('；') || '无' }}</template></el-table-column><el-table-column prop="manufacturingOutputStatus" label="制造输出" width="140"/></el-table></el-tab-pane>
          <el-tab-pane label="06 BOM/用料"><p class="not-integrated">NOT YET INTEGRATED（尚未接入详情投影）；正式事实仍由 PDE BOM / Material Requirement 持有。</p></el-tab-pane>
          <el-tab-pane label="07 Routing"><p class="not-integrated">NOT YET INTEGRATED（尚未接入详情投影）；正式事实仍由 PDE Routing 持有。</p></el-tab-pane>
          <el-tab-pane label="08 制造准备"><p>制造准备状态：<strong>{{ detailOrder.manufacturingReadinessStatus }}</strong>；正式制造输出来自 PDE ProductManufacturingOutput。</p><el-table :data="detailOrder.planningChain?.lines || []" border><el-table-column prop="salesOrderItemId" label="订单行ID" width="100"/><el-table-column label="供应计划类型" min-width="150"><template #default="{row}">{{ supplyPlanTypeText(row) }}</template></el-table-column><el-table-column prop="planNo" label="供应计划编号" min-width="205"><template #default="{row}">{{ supplyPlanNumberText(row) }}</template></el-table-column><el-table-column label="来源选择提示" min-width="260"><template #default="{row}">{{ sourceSelectionText(row) }}</template></el-table-column><el-table-column prop="demandNo" label="需求编号"><template #default="{ row }">{{ row.demandNo || '尚未生成' }}</template></el-table-column><el-table-column prop="requiredQty" label="需求数量"/><el-table-column prop="inventorySnapshotQty" label="库存计算快照（未分配）" width="170"><template #default="{ row }">{{ row.inventorySnapshotQty ?? '尚未计算' }}</template></el-table-column><el-table-column prop="effectivePlanQty" label="有效计划量"/><el-table-column prop="pendingNetPlanQty" label="净需求待计划"/><el-table-column label="订单未覆盖"><template #default="{ row }">{{ row.uncoveredDemandQty ?? '未确认' }}</template></el-table-column><el-table-column label="数量校验" width="145"><template #default="{ row }">{{ planningQuantityText(row) }}</template></el-table-column><el-table-column prop="supplyTypeLabel" label="供应方式"><template #default="{ row }">{{ row.supplyTypeLabel || '尚未判定' }}</template></el-table-column><el-table-column label="当前阻断" min-width="240"><template #default="{ row }">{{ planningBlocker(row) }}</template></el-table-column></el-table><el-button class="trace-link" type="primary" plain @click="openPlanning(detailOrder)">打开订单计划工作台</el-button></el-tab-pane>
          <el-tab-pane label="09 采购/生产"><p>计划类型与编号对应同一原供应计划；多来源待选择保留原提示，不表示无计划，类型说明不替代办理资格。</p><el-table :data="detailOrder.planningChain?.lines || []" border><el-table-column prop="salesOrderItemId" label="订单行ID" width="100"/><el-table-column label="供应计划类型" min-width="150"><template #default="{row}">{{ supplyPlanTypeText(row) }}</template></el-table-column><el-table-column prop="planNo" label="供应计划编号" min-width="205"><template #default="{row}">{{ supplyPlanNumberText(row) }}</template></el-table-column><el-table-column label="来源选择提示" min-width="260"><template #default="{row}">{{ sourceSelectionText(row) }}</template></el-table-column><el-table-column prop="mpsRunNo" label="MPS建议"><template #default="{ row }">{{ row.mpsRunNo || '尚未生成' }}</template></el-table-column><el-table-column prop="mpsQty" label="MPS数量"/><el-table-column prop="mrpRunNo" label="MRP建议"><template #default="{ row }">{{ row.mrpRunNo || '尚未生成' }}</template></el-table-column><el-table-column label="MRP物料建议" min-width="260"><template #default="{ row }">{{ row.mrpProposals?.map(item => `${item.materialCode}:${item.netRequirement}/${item.supplyType}`).join('；') || '尚未生成' }}</template></el-table-column></el-table><p class="not-integrated">正式生产任务与资源排程尚未接入；没有工序、资源、工时、日历和占用事实时不生成排产日期。</p></el-tab-pane>
          <el-tab-pane label="10 交付"><p>当前交付状态：{{ detailOrder.deliveryStatus }}</p><el-alert v-if="detailOrder.deliveryFacts?.associationConflictCount" title="存在未匹配、重复或单位冲突的交付批次；冲突批次不计入已交付数量。" type="error" show-icon :closable="false"/><el-table :data="detailOrder.deliveryFacts?.lines || []" border><el-table-column prop="lineNo" label="订单行" width="90"/><el-table-column prop="orderedQty" label="订单数量"/><el-table-column prop="deliveredQty" label="已交付"/><el-table-column prop="remainingQty" label="待交付"/><el-table-column label="数量校验" width="125"><template #default="{ row }">{{ deliveryQuantityText(row) }}</template></el-table-column><el-table-column prop="uomCode" label="单位"/><el-table-column prop="customerRequiredDate" label="客户要求交期" width="135"/><el-table-column label="企业承诺交期" width="135"><template #default="{ row }">{{ dateText(row.committedDeliveryDate) }}</template></el-table-column></el-table><h4>交付批次</h4><el-table :data="detailOrder.deliveryFacts?.batches || []" border empty-text="未维护交付批次"><el-table-column prop="batchNo" label="批次"/><el-table-column prop="lineNo" label="订单行"/><el-table-column prop="quantity" label="数量"/><el-table-column prop="uomCode" label="单位"/><el-table-column label="归属校验" min-width="190"><template #default="{ row }">{{ row.associationIssues?.join('；') || '匹配有效' }}</template></el-table-column><el-table-column prop="customerRequiredDate" label="客户要求交期" width="135"/><el-table-column prop="committedDeliveryDate" label="企业承诺交期" width="135"><template #default="{ row }">{{ dateText(row.committedDeliveryDate) }}</template></el-table-column><el-table-column prop="plannedCompletionDate" label="计划完成时间" width="135"><template #default="{ row }">{{ predictionText(row.plannedCompletionDate) }}</template></el-table-column><el-table-column prop="actualDeliveryDate" label="实际交付时间" width="135"><template #default="{ row }">{{ dateText(row.actualDeliveryDate) }}</template></el-table-column><el-table-column prop="statusLabel" label="交付批次状态"/></el-table><h4 v-if="detailOrder.deliveryFacts?.unmatchedBatches?.length">未匹配交付批次</h4><el-table v-if="detailOrder.deliveryFacts?.unmatchedBatches?.length" :data="detailOrder.deliveryFacts.unmatchedBatches" border><el-table-column prop="batchNo" label="批次"/><el-table-column prop="salesOrderItemId" label="订单行ID"/><el-table-column prop="lineNo" label="行号"/><el-table-column prop="reason" label="未匹配原因" min-width="260"/></el-table></el-tab-pane>
          <el-tab-pane label="11 财务/结算"><p>当前结算状态：{{ detailOrder.settlementStatus }}</p><p class="not-integrated">应收、成本与结算尚未接入。</p></el-tab-pane>
          <el-tab-pane label="12 Audit/Timeline"><el-timeline><el-timeline-item v-for="x in detailOrder.statusTransitionHistory" :key="x.version" :timestamp="x.timestamp">{{ x.source_state }} → {{ x.target_state }}（{{ x.action_code }}）</el-timeline-item></el-timeline></el-tab-pane>
        </el-tabs>
      </template>
    </el-drawer>
    <el-dialog v-model="createVisible" title="新建销售订单" width="92%" top="4vh">
      <section v-if="linkedCandidate" aria-label="关联评审依据">
        <p>来源 {{ linkedCandidate.sourceOrderNo }} · 版本 {{ linkedCandidate.sourceVersion }} · 评审 V{{ linkedCandidate.reviewVersion }}</p>
        <p>验收数据：测试交付日期 2026-12-15，请在交付日期栏核对后填写。</p>
        <p v-if="linkedReviewItem">第05项交期异议：{{ linkedReviewItem.disagreementReasonCode }}。{{ linkedReviewItem.evidenceNote }}</p>
        <p v-if="linkedRisk">审批风险说明：{{ linkedRisk }}</p>
        <router-link :to="{ path: '/sales/order-reviews', query: { sourceRecord: linkedCandidate.sourceRecordId } }">查看完整订单评审</router-link>
      </section>
      <el-form label-width="110px">
        <div class="form-grid"><el-form-item label="客户"><el-select v-model="form.customerId" filterable><el-option v-for="x in customers" :key="x.id" :label="`${x.code} / ${x.name}`" :value="x.id"/></el-select></el-form-item><el-form-item label="销售组织"><el-select v-model="form.departmentId"><el-option v-for="x in departments" :key="x.id" :label="`${x.code} / ${x.name}`" :value="x.id"/></el-select></el-form-item><el-form-item label="负责人"><el-select v-model="form.salesOwnerId" clearable><el-option v-for="x in employees" :key="x.id" :label="`${x.employeeNo} / ${x.name}`" :value="x.id"/></el-select></el-form-item><el-form-item label="订单类型"><el-select v-model="form.orderType"><el-option label="标准订单" value="standard"/><el-option label="项目订单" value="project"/><el-option label="样品订单" value="sample"/><el-option label="服务订单" value="service"/></el-select></el-form-item><el-form-item label="订单来源"><el-select v-model="form.orderSource"><el-option label="手工录入" value="manual"/><el-option label="CRM" value="crm"/><el-option label="EDI" value="edi"/><el-option label="导入" value="import"/></el-select></el-form-item><el-form-item label="订单日期"><el-date-picker v-model="form.orderDate" value-format="YYYY-MM-DD"/></el-form-item><el-form-item label="要求交期"><el-date-picker v-model="form.requiredDate" value-format="YYYY-MM-DD"/></el-form-item><el-form-item label="币种"><el-input v-model="form.currency"/></el-form-item><el-form-item label="项目引用"><el-input v-model="form.projectReference"/></el-form-item><el-form-item label="合同引用"><el-input v-model="form.contractReference"/></el-form-item></div>
        <div class="section-title"><h3>订单明细</h3><el-button @click="addItem">新增明细</el-button></div>
        <div v-for="(item,index) in form.items" :key="index" class="item-card"><div class="item-heading"><strong>第 {{ index + 1 }} 行</strong><el-button v-if="form.items.length>1" link type="danger" @click="form.items.splice(index,1)">移除</el-button></div><div class="form-grid three"><el-form-item label="空间编码"><el-input v-model="item.spaceCode"/></el-form-item><el-form-item label="空间名称"><el-input v-model="item.spaceName"/></el-form-item><el-form-item label="安装区域"><el-input v-model="item.installationArea"/></el-form-item><el-form-item label="部件分类"><el-input v-model="item.componentCategory"/></el-form-item><el-form-item label="工程模式"><el-select v-model="item.engineeringMode"><el-option label="标准产品" value="STANDARD"/><el-option label="模板辅助配置" value="TEMPLATE_ASSISTED"/><el-option label="按单工程" value="ORDER_ENGINEERED"/></el-select></el-form-item><el-form-item label="物料"><el-select v-model="item.materialId" filterable><el-option v-for="x in materials" :key="x.id" :label="`${x.code} / ${x.name}`" :value="x.id"/></el-select></el-form-item><el-form-item label="产品定义"><el-select v-model="item.productDefinitionId" clearable filterable><el-option v-for="x in products" :key="x.id" :label="`${x.code} / ${x.name}`" :value="x.id"/></el-select></el-form-item><el-form-item v-if="item.engineeringMode==='TEMPLATE_ASSISTED'" label="产品配置"><el-select v-model="item.productConfigurationId" clearable><el-option v-for="x in productConfigurations" :key="x.id" :label="`${x.configurationNo} / ${x.templateName}`" :value="x.id"/></el-select></el-form-item><el-form-item label="制造输出"><el-select v-model="item.manufacturingOutputId" clearable><el-option v-for="x in outputsFor(item)" :key="x.id" :label="`#${x.id} / ${x.releaseStatus}`" :value="x.id"/></el-select></el-form-item><el-form-item label="数量"><el-input-number v-model="item.quantity" :min="0.0001" :precision="4"/></el-form-item><el-form-item label="单位"><el-select v-model="item.uomId" clearable><el-option v-for="x in units" :key="x.id" :label="x.code" :value="x.id"/></el-select></el-form-item><el-form-item label="单价"><el-input-number v-model="item.unitPrice" :min="0" :precision="4"/></el-form-item><el-form-item label="计价口径"><el-select v-model="item.priceTaxMode"><el-option label="未税单价" value="tax_exclusive"/><el-option label="含税单价" value="tax_inclusive"/></el-select></el-form-item><el-form-item label="税率（%）"><el-input-number v-model="item.taxRatePercent" :min="0" :max="100" :precision="4"/></el-form-item><el-form-item label="行交期"><el-date-picker v-model="item.requiredDate" value-format="YYYY-MM-DD"/></el-form-item></div><el-form-item label="客户描述"><el-input v-model="item.customerProductDescription" type="textarea"/></el-form-item><el-form-item label="工程要求"><el-input v-model="item.engineeringRequirements" type="textarea"/></el-form-item><el-form-item label="质量要求"><el-input v-model="item.qualityRequirements" type="textarea"/></el-form-item></div>
      </el-form><template #footer><el-button @click="createVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="createOrder">保存草稿</el-button></template>
    </el-dialog>
    <OrderLineSupplyAdmission v-if="detailOrder" v-model="supplyVisible" :order-id="detailOrder.id" :item-id="supplyItemId" @saved="showDetail({ id: detailOrder.id })" />
    <el-dialog v-model="taxEditVisible" title="编辑草稿行税率" width="480px">
      <el-form label-width="110px">
        <p>第 {{ taxEdit.lineNo }} 行。百分比输入13表示13%，保存的小数税率为0.13。</p>
        <el-form-item label="税率（%）"><el-input-number v-model="taxEdit.percent" :min="0" :max="100" :precision="4"/></el-form-item>
      </el-form>
      <template #footer><el-button @click="taxEditVisible=false">取消</el-button><el-button :loading="taxSaving" type="primary" @click="saveTaxEdit">保存税率</el-button></template>
    </el-dialog>
    <el-dialog v-model="editVisible" title="编辑订单草稿" width="680px"><el-form label-width="110px"><el-form-item label="订单类型"><el-select v-model="editForm.orderType"><el-option label="标准订单" value="standard"/><el-option label="项目订单" value="project"/></el-select></el-form-item><el-form-item label="要求交期"><el-date-picker v-model="editForm.requiredDate" value-format="YYYY-MM-DD"/></el-form-item><el-form-item label="项目引用"><el-input v-model="editForm.projectReference"/></el-form-item><el-form-item label="合同引用"><el-input v-model="editForm.contractReference"/></el-form-item><el-form-item label="备注"><el-input v-model="editForm.remark" type="textarea"/></el-form-item></el-form><template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" @click="saveEdit">保存</el-button></template></el-dialog>
    </template>
  </section>
</template>

<script setup>
import {supplyPlanTypeText,supplyPlanNumberText,sourceSelectionText} from '@/meta/runtime/authoritativeFieldPresentation.js'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { salesApi } from '@/api/sales'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { resolveSalesOrderActions } from '@/meta/runtime/salesOrderActionRegistry.js'
import { createReadFailedFactLoad } from '@/meta/runtime/pceFactLoadContract.js'
import OrderLineSupplyAdmission from './components/OrderLineSupplyAdmission.vue'
import NewOrderSource from './NewOrderSource.vue'
import WholeHouseOrderPreview from './WholeHouseOrderPreview.vue'
import EngineeringSourceFormalizationPreview from './EngineeringSourceFormalizationPreview.vue'
import DevelopmentContractSamplePage from './DevelopmentContractSamplePage.vue'

const route = useRoute()
const router = useRouter()
const previewMode = computed(() => route.query.mode === 'whole-house-read-only-preview')
const engineeringFormalizationMode = computed(() => route.query.mode === 'engineering-source-formalization')
const developmentContractMode = computed(() => route.query.mode === 'development-contract')

const orders=ref([]),customers=ref([]),departments=ref([]),employees=ref([]),materials=ref([]),units=ref([]),products=ref([]),productConfigurations=ref([]),manufacturingOutputs=ref([])
const developmentEntry=ref(null),developmentEntryLoading=ref(false),developmentEntryError=ref('')
const capabilities=ref({}),strictFacts=ref({}),factLoadFacts=ref(null),loading=ref(false),saving=ref(false),errorMessage=ref(''),detailVisible=ref(false),detailOrder=ref(null),createVisible=ref(false),editVisible=ref(false)
const readDuration=ref(null),visibleDuration=ref(null)
const factLoadStatus=computed(()=>loading.value?'loading':factLoadFacts.value?.factLoadStatus||'loading')
const factsAvailable=computed(()=>['loaded','empty_valid','success'].includes(factLoadStatus.value))
const authenticationRequired=computed(()=>Number(factLoadFacts.value?.httpStatus)===401||['not_authenticated','authentication_failed','AUTHENTICATION_CONTEXT_CHANGED'].includes(String(factLoadFacts.value?.errorCode||'')))
const listContract=createPceEnterpriseListContract({pageCode:'sales-orders',pageType:'list',title:'销售订单工作台',moduleCode:'SALES'})
const statusOptions=[['draft','草稿'],['submitted','已提交'],['approved','已批准'],['confirmed','已确认（兼容）'],['engineering','工程准备中'],['manufacturing_ready','制造准备完成'],['in_progress','执行中'],['delivering','交付中'],['completed','已完成'],['closed','已关闭'],['cancelled','已取消']].map(([value,label])=>({value,label}))
const filterSchema=[{field:'status',label:'销售订单状态',filterType:'select',options:statusOptions},{field:'customerName',label:'客户名称',filterType:'text'},{field:'departmentName',label:'销售部门名称',filterType:'text'},{field:'orderDate',label:'订单日期',filterType:'daterange'}]
const runtime=usePceEnterpriseListRuntime({rows:orders,filterSchema,pageCode:'sales-orders',searchFields:['orderNo','customerName','projectReference','materialCode','materialName'],exportFileName:'sales-orders.csv',exportColumns:[{field:'orderNo',label:'销售订单编号'},{field:'customerName',label:'客户名称'},{field:'orderTypeLabel',label:'订单类型'},{field:'requiredDate',label:'要求交期'},{field:'totalAmount',label:'订单金额'},{field:'statusLabel',label:'销售订单状态'},{field:'engineeringStatus',label:'工程状态'},{field:'manufacturingReadinessStatus',label:'制造准备'}]})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent,updateFilter}=runtime
const emptyItem=()=>({spaceCode:'',spaceName:'',installationArea:'',componentCategory:'',engineeringMode:'STANDARD',materialId:null,productDefinitionId:null,productVersionId:null,productConfigurationId:null,manufacturingOutputId:null,quantity:1,uomId:null,unitPrice:0,priceTaxMode:"tax_exclusive",taxRatePercent:0,requiredDate:'',customerProductDescription:'',engineeringRequirements:'',qualityRequirements:''})
const form=reactive({customerId:null,departmentId:null,salesOwnerId:null,orderType:'standard',orderSource:'manual',orderDate:'',requiredDate:'',currency:'CNY',projectReference:'',contractReference:'',items:[emptyItem()]})
const supplyVisible = ref(false), supplyItemId = ref(null)
const taxEditVisible = ref(false), taxSaving = ref(false)
const taxEdit = reactive({ id: null, lineNo: null, percent: 0 })
function openTaxEdit(row) {
  Object.assign(taxEdit, { id: row.id, lineNo: row.lineNo, percent: Number(row.taxRate) * 100 })
  taxEditVisible.value = true
}
async function saveTaxEdit() {
  taxSaving.value = true
  try {
    const result = await salesApi.updateOrderItem(detailOrder.value.id, taxEdit.id, {
      taxRate: (taxEdit.percent / 100).toFixed(6),
      reason: '用户核对并修正测试草稿税率',
    })
    if (!result.success) return ElMessage.error(result.error?.message || '税率保存失败')
    taxEditVisible.value = false
    await showDetail({ id: detailOrder.value.id })
    await loadFacts()
  } finally {
    taxSaving.value = false
  }
}
const editForm=reactive({id:null,version:null,orderType:'standard',requiredDate:'',projectReference:'',contractReference:'',remark:''})
const can=code=>Boolean(capabilities.value[code]);const actionsFor=row=>resolveSalesOrderActions(row.status,capabilities.value);const outputsFor=item=>manufacturingOutputs.value.filter(x=>!item.productDefinitionId||x.productId===item.productDefinitionId)
const priceModeLabel = mode => ({ tax_inclusive: '含税单价', tax_exclusive: '未税单价' })[mode] || '未保存'
const taxRateLabel = value => value == null || value === '' ? '未保存' : new Intl.NumberFormat('zh-CN', { style: 'percent', maximumFractionDigits: 4 }).format(Number(value))
const dateText=value=>value||'未维护'
const predictionText=value=>value||'尚无法预测'
const planningBlocker=row=>row.demandId?(row.requirementId?(row.planId?'无':'尚未形成供应计划'):'尚未计算计划需求'):'尚未生成订单需求'
const planningQuantityText=row=>row.planningQuantityStatus==='OVER_PLANNED'?`超计划 ${row.overPlannedQty}`:(row.planningQuantityStatus==='NET_REQUIREMENT_FULLY_PLANNED'?'净需求已足额计划':(row.planningQuantityStatus==='NOT_CALCULATED'?'尚未计算':'净需求仍待计划'))
const deliveryQuantityText=row=>row.deliveryQuantityStatus==='OVER_DELIVERED'?`超交付 ${row.overDeliveredQty}`:(row.deliveryQuantityStatus==='DELIVERED'?'已全部交付':'仍有待交付')
const factCount=value=>loading.value?'读取中':factsAvailable.value?Number(value??0):'未取得'
const money=value=>Number(value||0).toLocaleString('zh-CN',{minimumFractionDigits:2,maximumFractionDigits:2})
function readFailureMessage(response){const facts=response?.factLoadFacts||response?.data?.factLoadFacts||{};const code=String(response?.error?.code||facts.errorCode||'FACT_READ_FAILED');const detail=String(response?.error?.message||facts.errorMessage||'服务端事实读取失败');if(code==='not_authenticated'||Number(facts.httpStatus||response?.meta?.status)===401)return '未取得数据：当前未登录或会话已失效。请从正式系统登录入口登录后重试。';if(Number(facts.httpStatus||response?.meta?.status)===403||code.toLowerCase().includes('denied'))return `未取得数据：当前合法身份没有销售订单只读权限。${detail}`;return `未取得数据：销售订单读取失败。${detail}`}
function goToLogin(){router.push({path:'/system-login',query:{redirect:route.fullPath,reason:'sales-order-read-required'}})}
function openPlanning(order){router.push({path:'/planning/requirements',query:{orderNo:order.orderNo}})}
function openHistoricalSource(){router.push({path:'/sales/orders',query:{...route.query,mode:'whole-house-read-only-preview'}})}
function openDevelopmentContract(){if(developmentEntry.value?.target)router.push(developmentEntry.value.target)}
async function loadDevelopmentContractEntry(){developmentEntryLoading.value=true;developmentEntryError.value='';const r=await salesApi.developmentContractEntry();developmentEntryLoading.value=false;if(!r.success){developmentEntry.value=null;developmentEntryError.value=r.error?.message||'开发合同入口解析失败，未回退到历史来源。';return}developmentEntry.value=r.data.entry}
let loadSequence=0
async function loadFacts(){
 const current=++loadSequence,started=performance.now()
 loading.value=true;errorMessage.value='';factLoadFacts.value=null;readDuration.value=null;visibleDuration.value=null
 const r=await salesApi.facts().catch(error=>({success:false,error:{code:error.code||'FACT_READ_FAILED',message:error.message||'订单请求未能完成'},meta:{status:0}}))
 if(current!==loadSequence)return
 readDuration.value=performance.now()-started
 applyFactsResponse(r)
 loading.value=false
 await nextTick();await new Promise(resolve=>requestAnimationFrame(resolve))
 if(current===loadSequence)visibleDuration.value=performance.now()-started
}
function applyFactsResponse(r){if(!r.success){factLoadFacts.value=r.factLoadFacts||r.data?.factLoadFacts||createReadFailedFactLoad({apiUrl:'/api/sales/facts/',httpStatus:r.meta?.status,errorCode:r.error?.code,errorMessage:r.error?.message});errorMessage.value=readFailureMessage(r);orders.value=[];capabilities.value={};strictFacts.value={};return}const d=r.data||{};factLoadFacts.value=d.factLoadFacts||d.strictFacts?.factLoadFacts||null;if(!factLoadFacts.value){factLoadFacts.value=createReadFailedFactLoad({apiUrl:'/api/sales/facts/',httpStatus:r.meta?.status,errorCode:'FACT_LOAD_CONTRACT_INCOMPLETE',errorMessage:'销售订单接口未返回完整事实加载合同'});errorMessage.value=readFailureMessage({factLoadFacts:factLoadFacts.value,error:{message:factLoadFacts.value.errorMessage}});orders.value=[];return}orders.value=d.orders||[];customers.value=d.customers||[];departments.value=d.departments||[];employees.value=d.employees||[];materials.value=d.materials||[];units.value=d.units||[];products.value=d.products||[];productConfigurations.value=d.productConfigurations||[];manufacturingOutputs.value=d.manufacturingOutputs||[];capabilities.value=d.capabilities||{};strictFacts.value={...(d.strictFacts||{}),productionWriteCount:0}}

async function showDetail(row){const r=await salesApi.order(row.id);if(!r.success)return ElMessage.error(r.error?.message||'订单详情读取失败');detailOrder.value=r.data.order;detailVisible.value=true}
const linkedCandidate = ref(null)
const linkedReviewItem = ref(null)
const linkedRisk = ref('')
function openCreate(){linkedCandidate.value=null;Object.assign(form,{customerId:customers.value[0]?.id||null,departmentId:departments.value[0]?.id||null,salesOwnerId:employees.value[0]?.id||null,orderType:'standard',orderSource:'manual',orderDate:'',requiredDate:'',currency:'CNY',projectReference:'',contractReference:'',items:[emptyItem()]});createVisible.value=true}
function addItem(){form.items.push({...emptyItem(),requiredDate:form.requiredDate})}
async function createOrder(){saving.value=true;const payload={...form,items:form.items.map((x,index)=>{const output=manufacturingOutputs.value.find(value=>value.id===x.manufacturingOutputId);const { taxRatePercent, ...line } = x;return {...line,taxRate:(taxRatePercent / 100).toFixed(6),lineNo:index+1,productVersionId:x.productVersionId||output?.productVersionId||null,requiredDate:x.requiredDate||form.requiredDate}})};const candidate=linkedCandidate.value
if(candidate) Object.assign(payload,{
  externalSourceNo:candidate.sourceOrderNo, orderSource:'crm', reviewScopeMode:'WHOLE_ORDER',
  deliveryInformation:{sourceRecordId:candidate.sourceRecordId,sourceVersion:candidate.sourceVersion,sourceContentHash:candidate.sourceContentHash},
  remark:'隔离验收测试价格及交付日期',
})
const r=await salesApi.createOrder(payload);saving.value=false;if(!r.success)return ElMessage.error(r.error?.message||'订单创建失败');createVisible.value=false;ElMessage.success(`订单 ${r.data.order.orderNo} 已保存为草稿`);await loadFacts()}
function openEdit(row){Object.assign(editForm,{id:row.id,version:row.version,orderType:row.orderType,requiredDate:row.requiredDate,projectReference:row.projectReference,contractReference:row.contractReference,remark:row.remark});editVisible.value=true}
async function saveEdit(){const r=await salesApi.updateOrder(editForm.id,{...editForm,reason:'用户编辑订单草稿'});if(!r.success)return ElMessage.error(r.error?.message||'订单保存失败');editVisible.value=false;ElMessage.success('订单草稿已更新');await loadFacts()}
async function executeAction(row,action){try{await ElMessageBox.confirm(`确认对订单 ${row.orderNo} 执行“${action.label}”？`,'确认业务动作',{type:action.type==='danger'?'warning':'info'})}catch{return}const requestId=crypto.randomUUID();const r=await salesApi.action(row.id,action.code,{requestId,idempotencyKey:requestId,source:'sales-order-workbench',reason:`用户执行：${action.label}`});if(!r.success)return ElMessage.error(r.error?.message||`${action.label}失败`);ElMessage.success(`${action.label}成功`);await loadFacts();if(detailVisible.value&&detailOrder.value?.id===row.id)await showDetail({id:row.id})}
watch(() => route.query.linkedSource, async id => {
  if (!id) return
  const result = await salesApi.facts()
  if (route.query.linkedSource !== id) return
  const candidate = result.data?.crmAdmissionCandidates?.find(row => String(row.sourceRecordId) === String(id))
  if (!candidate || !result.data?.capabilities?.['sales.order.create']) {
    ElMessage.error('当前账号无建单资格，或来源未取得有效评审和登记范围。')
    return
  }
  await loadFacts()
  if (route.query.linkedSource !== id) return
  const existing = orders.value.find(row => row.externalSourceNo === candidate.sourceOrderNo)
  if (existing) {
    await showDetail(existing)
    return
  }
  const review = await salesApi.orderReview(candidate.sourceRecordId)
  if (route.query.linkedSource !== id) return
  if (!review.success || review.data?.review?.latest?.id !== candidate.reviewId
      || review.data.review.latest.reviewVersion !== candidate.reviewVersion) {
    ElMessage.error('未能读取与建单候选一致的已审批评审，请刷新后重试。')
    return
  }
  linkedReviewItem.value = review.data.review.submittedItems?.find(row => row.itemCode === '05' && row.decision === 'DISAGREE')
  linkedRisk.value = review.data.approval?.finalDecision?.riskHandling || ''
  openCreate()
  linkedCandidate.value = candidate
  Object.assign(form, {
    customerId: candidate.customerId, departmentId: candidate.departmentId || 9, orderSource: 'crm',
    projectReference: candidate.projectReference, contractReference: candidate.contractReference,
    items: candidate.formalSalesOrderScope.items.map(item => ({
      ...emptyItem(), materialId: item.materialId, uomId: item.uomId, quantity: Number(item.quantity),
    })),
  })
}, { immediate: true })
onMounted(() => {
  if (previewMode.value || engineeringFormalizationMode.value || developmentContractMode.value) return
  const requestedOrder = String(route.query.search || '')
  if (requestedOrder) {
    quickSearch.value = requestedOrder
    appliedSearch.value = requestedOrder
  }
  loadDevelopmentContractEntry()
  loadFacts()
  window.addEventListener('pce:authentication-changed', handleAuthenticationChanged)
})
const handleAuthenticationChanged=event=>{if(event?.detail?.authenticated)loadFacts()}
onBeforeUnmount(()=>{loadSequence+=1;window.removeEventListener('pce:authentication-changed',handleAuthenticationChanged)})
</script>

<style scoped>
.sales-order-workbench{display:grid;min-width:0;gap:16px;padding:18px;background:#f4f7fb}.summary-card,.development-entry-card,.list-card,.metric-grid article{border:1px solid #dce4ed;border-radius:12px;background:#fff}.summary-card,.development-entry-card{display:flex;justify-content:space-between;gap:20px;padding:20px}.summary-card h2,.development-entry-card h3{margin:4px 0 8px;color:#17233b}.summary-card p,.development-entry-card p{margin:0 0 6px;color:#64748b}.development-entry-card{align-items:center;border-color:#a7c6ff;background:linear-gradient(135deg,#fff,#f3f7ff)}.entry-permission{color:#9f1d1d!important}.eyebrow{color:#285ac7!important;font-size:12px;font-weight:700}.summary-actions{display:flex;align-items:center;gap:8px}.read-failure-actions{display:grid;gap:10px}.read-failure-actions>div{display:flex;gap:10px}.metric-grid{display:grid;grid-template-columns:repeat(5,minmax(130px,1fr));gap:10px}.metric-grid article{display:flex;justify-content:space-between;padding:15px;color:#475569}.metric-grid strong{font-size:22px;color:#1d4ed8}.list-card{min-width:0;padding:16px;overflow:hidden}.loading-facts{border-color:#b8ceeb;background:#f3f7ff;color:#24588b}.loading-facts p{margin:8px 0 0}.unavailable-facts{border-color:#f3c3c3;background:#fff7f7;color:#9f1d1d}.unavailable-facts p{margin:8px 0 0}.detail-facts{display:flex;flex-wrap:wrap;gap:18px;margin-bottom:16px;padding:14px;border-radius:8px;background:#f1f5f9}.not-integrated{padding:14px;border:1px dashed #cbd5e1;border-radius:8px;background:#f8fafc;color:#64748b}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.form-grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}.form-grid :deep(.el-select),.form-grid :deep(.el-date-editor),.form-grid :deep(.el-input-number){width:100%}.section-title,.item-heading{display:flex;align-items:center;justify-content:space-between}.item-card{margin:12px 0;padding:14px;border:1px solid #dbe4ef;border-radius:10px;background:#f8fafc}@media(max-width:900px){.summary-card,.development-entry-card{display:block}.development-entry-card .el-button{margin-top:12px}.metric-grid,.form-grid,.form-grid.three{grid-template-columns:1fr}}

/* Sales original page only. A bounded outer owner accepts wheel input over the
   summary as well as the list; the content layer must not consume that scroll. */
:global(.pce-list-page-shell:has(.sales-order-workbench)) {
  max-height:calc(100dvh - var(--pce-account-bookmark-height,52px) - var(--pce-system-bar-height,72px) - 20px);
  overflow-x:hidden; overflow-y:auto; min-height:0; grid-auto-rows:max-content;
  align-content:start; scrollbar-gutter:stable;
}
:global(.pce-list-page-content:has(> .sales-order-workbench)) { overflow-x:clip; overflow-y:visible; }
</style>
