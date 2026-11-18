<template>
  <main class="payment-execution-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.1 付款执行草稿页面原型</p>
        <h1>{{ detail ? '付款执行草稿详情' : '付款执行草稿' }}</h1>
        <p>本页只维护付款执行草稿、线下付款结果草稿和复核提交，不执行真实付款，不连接银行，不生成银行流水，不生成财务凭证，不写总账。</p>
        <p class="finance-current-module-badge">当前操作模块：付款执行草稿</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-order-drafts">正式付款单草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-risk-reviews">真实付款风险评审</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-executions">付款执行草稿<span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-record-reviews">付款记录复核</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款执行草稿流程：真实付款风险评审通过 -> 付款执行草稿 -> 等待线下付款 -> 线下付款结果草稿 -> 付款记录待复核</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>维护付款执行草稿和线下结果草稿。</span>
          <span><b>本页做什么</b>确认执行意图、标记等待线下付款、登记线下付款结果草稿、提交复核。</span>
          <span><b>下一步做什么</b>后续阶段再做付款记录复核和真实付款范围确认。</span>
          <span><b>本页不做什么</b>不执行真实付款、不连接银行、不生成银行流水、不生成凭证、不写总账。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.paymentExecutionNo }}</h2>
              <span>{{ detail.sourceRiskReviewNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-executions')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-risk-review/${detail.sourceRiskReviewId}`)">查看风险评审</el-button>
              <el-button v-if="detail.sourcePaymentOrderDraftId" @click="router.push(`/finance/payment-order-draft/${detail.sourcePaymentOrderDraftId}`)">查看付款单草稿</el-button>
              <el-button v-if="detail.paymentExecutionStatus === 'draft'" class="app-next-action-button" type="primary" @click="handleConfirm(detail)">确认付款执行<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="detail.paymentExecutionStatus === 'confirmed'" class="app-next-action-button" type="warning" @click="handleWaiting(detail)">标记等待线下付款<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="detail.paymentExecutionStatus === 'waitingOfflinePayment'" class="app-next-action-button" type="success" @click="handleRecordOffline(detail)">登记线下付款结果草稿<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="detail.paymentExecutionStatus === 'offlinePaymentRecorded'" class="app-next-action-button" type="primary" @click="handleSubmitReview(detail)">提交付款记录复核<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="canCreateRecordReview(detail)" class="app-next-action-button" type="primary" @click="handleCreateRecordReview(detail)">生成付款记录复核<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="canViewRecordReview(detail)" type="success" @click="viewRecordReview(detail)">查看付款记录复核</el-button>
              <el-button v-if="canCancel(detail)" type="danger" @click="handleCancel(detail)">取消草稿</el-button>
            </div>
          </div>
        </template>
        <div class="boundary-note">当前状态说明：{{ statusLabel(detail.paymentExecutionStatus) }}。线下付款结果草稿不是银行回单，也不代表真实付款完成。</div>
        <div :class="nextStepGuideClass(detail.paymentExecutionStatus)">
          <strong>{{ nextStepTitle(detail.paymentExecutionStatus) }}</strong>
          <span>{{ nextStepDescription(detail.paymentExecutionStatus) }}</span>
        </div>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>来源追踪</h2></template>
        <div class="source-chain">
          <article v-for="item in sourceChain" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value || '-' }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>付款执行明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="260">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="itemName" label="明细说明" min-width="180" />
          <el-table-column prop="sourceNo" label="来源单号" min-width="180" />
          <el-table-column prop="executionAmount" label="执行金额" width="140" sortable />
          <el-table-column prop="remark" label="备注" min-width="220" />
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>离线付款记录草稿区</h2></template>
        <div class="offline-panel">
          <p>本区只登记线下付款结果草稿，用于后续付款记录复核；不是银行流水，不是银行回单，不生成凭证。</p>
          <div class="form-grid">
            <label>线下记录草稿号<input v-model="offlineForm.offlinePaymentRecordNo" placeholder="为空时自动生成" /></label>
            <label>实际线下日期<input v-model="offlineForm.actualPayDate" type="date" /></label>
            <label>备注<input v-model="offlineForm.offlinePaymentRemark" placeholder="线下付款结果草稿说明" /></label>
          </div>
        </div>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款执行草稿原型边界</strong>
        <div class="plain-flow-grid">
          <span><b>确认付款执行</b>仅确认内部执行意图，不是银行付款。</span>
          <span><b>等待线下付款</b>表示可以进入人工线下处理，不是已经付款。</span>
          <span><b>线下付款结果草稿</b>只是登记草稿，不是银行回单。</span>
          <span><b>提交复核</b>进入后续复核，不生成凭证、不写总账。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源风险评审区</h2>
              <span>只允许从“评审通过 / 低风险”的风险评审生成付款执行草稿。</span>
            </div>
            <div class="button-row">
              <el-button @click="refresh">刷新</el-button>
              <el-button @click="router.push('/finance/payment-risk-reviews')">查看风险评审</el-button>
            </div>
          </div>
        </template>
        <StandardListToolbar
          page-id="payment-execution"
          table-id="payment-execution-source"
          v-model:quick-search="sourceQuickSearch"
          :advanced-visible="isAdvancedFilterExpanded"
          :result-count="sortedSources.length"
          :selected-count="selectedSourceRows.length"
          :active-filter-count="sourceActiveFilterCount"
          :sort-text="sourceSortText"
          :export-disabled="sortedSources.length === 0"
          @search="clearSourceSelection"
          @toggle-advanced="isAdvancedFilterExpanded = !isAdvancedFilterExpanded"
          @clear-filters="resetSourceFilters"
          @clear-sort="clearSourceSort"
          @export-current="exportSourceRows"
          @clear-selection="clearSourceSelection"
        />
        <section v-show="isAdvancedFilterExpanded" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-execution-source">
          <label>风险评审号<PceResultFilterSelect v-model="sourceFilters.riskReviewNo" :rows="sortedSources" :fields="['riskReviewNo']" /></label>
          <label>付款单草稿号<PceResultFilterSelect v-model="sourceFilters.sourcePaymentOrderDraftNo" :rows="sortedSources" :fields="['sourcePaymentOrderDraftNo']" /></label>
          <label>供应商<PceResultFilterSelect v-model="sourceFilters.supplierName" :rows="sortedSources" :fields="['supplierName']" /></label>
          <label>评审状态<select v-model="sourceFilters.riskReviewStatus"><option value="">全部</option><option value="passed">评审通过</option><option value="blocked">评审阻断</option><option value="warning">有警告</option></select></label>
          <label>生成状态<select v-model="sourceFilters.generatedState"><option value="">全部</option><option value="ready">可生成草稿</option><option value="generated">已生成付款执行草稿</option><option value="blocked">暂不可生成</option></select></label>
        </section>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span class="batch-action-title">当前模块操作（生成草稿）</span>
          <span class="batch-action-tip">批量生成付款执行草稿：只生成草稿，不执行真实付款。</span>
          <el-button type="primary" size="small" :disabled="!sourceIds.length" @click="handleBatchCreate">批量生成付款执行草稿</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="batchResultType(sourceBatchResult)" @close="sourceBatchResult = null" />
        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-execution-source" page-id="payment-execution" table-id="payment-execution-source" min-width="100%">
        <el-table ref="sourceTableRef" class="pce-baseline-table-shell global-sort-arrow" :data="sortedSources" border stripe height="420" @selection-change="selectedSourceRows = $event" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="riskReviewNo" label="风险评审号" min-width="170" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentOrderDraftNo" label="付款单草稿号" min-width="180" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="paymentAccountName" label="付款账户" min-width="160" />
          <el-table-column prop="supplierBankAccountName" label="收款账户" min-width="160" />
          <el-table-column prop="checkPayAmount" label="检查使用付款金额" width="160" sortable="custom" />
          <el-table-column prop="checkUnpaidAmount" label="检查使用未付款金额" width="170" sortable="custom" />
          <el-table-column prop="riskReviewStatus" label="评审状态" width="130">
            <template #default="{ row }"><el-tag :type="row.riskReviewStatus === 'passed' ? 'success' : 'warning'">{{ riskReviewStatusLabel(row.riskReviewStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="生成状态" width="170">
            <template #default="{ row }"><el-tag :type="row.paymentExecutionGenerated ? 'success' : (row.canGeneratePaymentExecution ? 'primary' : 'info')">{{ row.paymentExecutionGenerated ? '已生成付款执行草稿' : (row.canGeneratePaymentExecution ? '可生成草稿' : '暂不可生成') }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="disabledReason" label="限制原因" min-width="220" />
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="row.paymentExecutionGenerated" class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-execution/${row.paymentExecutionId}`)">查看付款执行草稿</el-button>
                <span v-if="row.paymentExecutionGenerated" class="app-current-step-tip">已进入下一阶段</span>
                <el-button v-else class="app-action-button-lg app-next-action-button" size="small" type="primary" :disabled="!row.canGeneratePaymentExecution" @click="handleCreate(row)">生成付款执行草稿<span class="app-next-action-badge">下一步</span></el-button>
                <el-button class="app-action-button-md" size="small" @click="router.push(`/finance/payment-risk-review/${row.id}`)">查看评审</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>付款执行草稿列表</h2>
              <span>草稿流转到“付款记录待复核”为本轮终点。</span>
            </div>
            <div class="button-row">
              <el-button @click="quickSearchOpen = !quickSearchOpen">{{ quickSearchOpen ? '收起快速搜索' : '展开快速搜索' }}</el-button>
              <el-button @click="clearSort">清除排序</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </div>
          </div>
        </template>
        <StandardListToolbar
          page-id="payment-execution"
          table-id="payment-execution-main"
          v-model:quick-search="quickSearch"
          :advanced-visible="isAdvancedFilterExpanded"
          :show-advanced-filter-toggle="false"
          :result-count="sortedExecutions.length"
          :selected-count="selectedExecutionRows.length"
          :active-filter-count="activeFilterCount"
          :sort-text="sortText"
          :export-disabled="sortedExecutions.length === 0"
          @search="clearExecutionSelection"
          @clear-filters="resetFilters"
          @clear-sort="clearSort"
          @export-current="exportExecutionRows"
          @clear-selection="clearExecutionSelection"
        />

        <section v-show="isAdvancedFilterExpanded" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-execution-main">
          <label>付款执行草稿号<PceResultFilterSelect v-model="filters.paymentExecutionNo" :rows="sortedExecutions" :fields="['paymentExecutionNo']" /></label>
          <label>来源风险评审号<PceResultFilterSelect v-model="filters.sourceRiskReviewNo" :rows="sortedExecutions" :fields="['sourceRiskReviewNo']" /></label>
          <label>来源付款单草稿号<PceResultFilterSelect v-model="filters.sourcePaymentOrderDraftNo" :rows="sortedExecutions" :fields="['sourcePaymentOrderDraftNo']" /></label>
          <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :rows="sortedExecutions" :fields="['supplierName']" /></label>
          <label>付款账户<PceResultFilterSelect v-model="filters.paymentAccount" :rows="sortedExecutions" :fields="['paymentAccount']" /></label>
          <label>供应商账户<PceResultFilterSelect v-model="filters.supplierBankAccount" :rows="sortedExecutions" :fields="['supplierBankAccount']" /></label>
          <label>金额下限<input v-model="filters.amountMin" type="number" /></label>
          <label>金额上限<input v-model="filters.amountMax" type="number" /></label>
          <label>付款方式<PceResultFilterSelect v-model="filters.paymentMethod" :rows="sortedExecutions" :fields="['paymentMethod']" /></label>
          <label>执行状态<select v-model="filters.paymentExecutionStatus"><option value="">全部</option><option v-for="item in statusOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>真实付款状态<select v-model="filters.realPaymentStatus"><option value="">全部</option><option value="notPaid">未执行真实付款</option><option value="offlineRecorded">已登记线下付款结果草稿</option></select></label>
          <label>凭证状态<select v-model="filters.voucherStatus"><option value="">全部</option><option value="notGenerated">未生成凭证</option></select></label>
          <label>预计付款起<input v-model="filters.expectedStart" type="date" /></label>
          <label>预计付款止<input v-model="filters.expectedEnd" type="date" /></label>
          <label>实际线下起<input v-model="filters.actualStart" type="date" /></label>
          <label>实际线下止<input v-model="filters.actualEnd" type="date" /></label>
          <label>是否登记线下结果<select v-model="filters.offlinePaymentRecorded"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否提交复核<select v-model="filters.submittedForReview"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        </section>

        <div class="batch-bar">
          <span>已选择 {{ selectedExecutionRows.length }} 条</span>
          <span class="sort-help">{{ sortText }}</span>
          <span class="batch-action-title">当前模块操作（会立即修改草稿状态）</span>
          <span class="batch-action-tip">所有操作都不会执行真实付款、不会连接银行、不会生成凭证。</span>
          <span :class="batchRecommendationClass">{{ batchRecommendationText }}</span>
          <el-button size="small" type="primary" :disabled="!executionIds.length" @click="handleBatchConfirm">批量确认付款执行</el-button>
          <el-button size="small" type="warning" :disabled="!executionIds.length" @click="handleBatchWaiting">批量标记等待线下付款</el-button>
          <el-button size="small" type="success" :disabled="!executionIds.length" @click="handleBatchRecord">批量登记线下付款结果草稿</el-button>
          <el-button size="small" type="primary" :disabled="!executionIds.length" @click="handleBatchSubmit">批量提交付款记录复核</el-button>
          <el-button size="small" type="danger" :disabled="!executionIds.length" @click="handleBatchCancel">批量取消草稿</el-button>
        </div>
        <BatchResult v-if="executionBatchResult" :result="executionBatchResult" :type="batchResultType(executionBatchResult)" @close="executionBatchResult = null" />

        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-execution-main" page-id="payment-execution" table-id="payment-execution-main" min-width="100%">
        <el-table ref="executionTableRef" class="pce-baseline-table-shell global-sort-arrow" :data="sortedExecutions" border stripe height="520" @selection-change="selectedExecutionRows = $event" @sort-change="handleSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="paymentExecutionNo" label="付款执行草稿号" min-width="180" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceRiskReviewNo" label="来源风险评审号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePaymentOrderDraftNo" label="来源付款单草稿号" min-width="180" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="executionAmount" label="执行金额" width="130" sortable="custom" />
          <el-table-column prop="paymentMethod" label="付款方式" width="130" />
          <el-table-column prop="paymentAccountName" label="付款账户" min-width="160" />
          <el-table-column prop="supplierBankAccountName" label="供应商账户" min-width="160" />
          <el-table-column prop="paymentExecutionStatus" label="执行状态" width="170" sortable="custom">
            <template #default="{ row }"><el-tag :type="statusType(row.paymentExecutionStatus)">{{ statusLabel(row.paymentExecutionStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="realPaymentStatus" label="真实付款状态" width="160">
            <template #default="{ row }">{{ realPaymentStatusLabel(row.realPaymentStatus) }}</template>
          </el-table-column>
          <el-table-column prop="voucherStatus" label="凭证状态" width="130">
            <template #default="{ row }">{{ voucherStatusLabel(row.voucherStatus) }}</template>
          </el-table-column>
          <el-table-column label="付款记录复核" width="170">
            <template #default="{ row }"><el-tag :type="canViewRecordReview(row) ? 'success' : (canCreateRecordReview(row) ? 'primary' : 'info')">{{ recordReviewStateLabel(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="expectedPayDate" label="预计付款日期" width="140" sortable="custom" />
          <el-table-column prop="actualPayDate" label="实际线下日期" width="140" />
          <el-table-column label="操作" fixed="right" :width="executionActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button class="app-action-button-sm" size="small" @click="router.push(`/finance/payment-execution/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.paymentExecutionStatus === 'draft'" class="app-action-button-md app-next-action-button" size="small" type="primary" @click="handleConfirm(row)">确认付款执行<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="row.paymentExecutionStatus === 'confirmed'" class="app-action-button-lg app-next-action-button" size="small" type="warning" @click="handleWaiting(row)">等待线下付款<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="row.paymentExecutionStatus === 'waitingOfflinePayment'" class="app-action-button-xl app-next-action-button" size="small" type="success" @click="handleRecordOffline(row)">登记线下付款结果草稿<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="row.paymentExecutionStatus === 'offlinePaymentRecorded'" class="app-action-button-xl app-next-action-button" size="small" type="primary" @click="handleSubmitReview(row)">提交付款记录复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="canCreateRecordReview(row)" class="app-action-button-lg app-next-action-button" size="small" type="primary" @click="handleCreateRecordReview(row)">生成付款记录复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="canViewRecordReview(row)" class="app-action-button-lg" size="small" type="success" @click="viewRecordReview(row)">查看付款记录复核</el-button>
                <el-button v-if="canCancel(row)" class="app-action-button-sm" size="small" type="danger" @click="handleCancel(row)">取消草稿</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
        </BusinessTableScrollContainer>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import PceResultFilterSelect from '../components/PceResultFilterSelect.vue'
import { useRoute, useRouter } from 'vue-router'
import {
  batchCancelPaymentExecutions,
  batchConfirmPaymentExecutions,
  batchCreatePaymentExecutions,
  batchMarkWaitingOfflinePayment,
  batchRecordOfflinePaymentDraft,
  batchSubmitPaymentRecordReview,
  cancelPaymentExecution,
  confirmPaymentExecution,
  createPaymentExecutionFromRiskReview,
  getLedgerStatusLabel,
  getPaymentExecutionById,
  getPaymentExecutionSourcesFromRiskReviews,
  getPaymentExecutionStatusLabel,
  getPaymentExecutionStatusType,
  getRealPaymentStatusLabel,
  getVoucherStatusLabel,
  listPaymentExecutions,
  markWaitingOfflinePayment,
  recordOfflinePaymentDraft,
  submitPaymentRecordReview,
} from '../finance/paymentExecutionStore.js'
import {
  createPaymentRecordReviewFromPaymentExecution,
  getPaymentRecordReviewByPaymentExecutionId,
} from '../finance/paymentRecordReviewStore.js'
import { getActionColumnWidthForRows } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import StandardListToolbar from '../components/StandardListToolbar.vue'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', props.result.operationName || '批量操作完成'),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `成功：${props.result.successCount} 条`),
      h('span', `已达成：${props.result.alreadyDoneCount} 条`),
      h('span', `失败：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      h('span', `下一步建议：${props.result.nextSuggestion || '按当前状态进入下一步。'}`),
      h('span', '边界说明：本批量结果不代表真实付款完成，不生成银行流水、财务凭证或总账记录。'),
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sources = ref([])
const executions = ref([])
const selectedSourceRows = ref([])
const selectedExecutionRows = ref([])
const sourceTableRef = ref(null)
const executionTableRef = ref(null)
const sourceBatchResult = ref(null)
const executionBatchResult = ref(null)
const quickSearchOpen = ref(false)
const isAdvancedFilterExpanded = ref(false)
const quickSearch = ref('')
const sourceQuickSearch = ref('')
const sortState = ref({ key: '', direction: 'asc' })
const sourceSortState = ref({ key: '', direction: 'asc' })
const message = ref('')
const messageType = ref('success')
const offlineForm = reactive({ offlinePaymentRecordNo: '', actualPayDate: '', offlinePaymentRemark: '' })
const filters = reactive(defaultFilters())
const sourceFilters = reactive({
  riskReviewNo: '',
  sourcePaymentOrderDraftNo: '',
  supplierName: '',
  riskReviewStatus: '',
  generatedState: '',
})

const detail = computed(() => route.params.id ? getPaymentExecutionById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const executionIds = computed(() => selectedExecutionRows.value.map((row) => row.id).filter(Boolean))
const filteredSources = computed(() => {
  const rows = route.query.sourceRiskReviewId
    ? sources.value.filter((row) => String(row.id) === String(route.query.sourceRiskReviewId))
    : sources.value
  return rows.filter((row) => {
    const haystack = [
      row.riskReviewNo,
      row.sourcePaymentOrderDraftNo,
      row.supplierName,
      row.paymentAccountName,
      row.supplierBankAccountName,
      riskReviewStatusLabel(row.riskReviewStatus),
    ].join(' ').toLowerCase()
    const keywordOk = !sourceQuickSearch.value || haystack.includes(sourceQuickSearch.value.trim().toLowerCase())
    const generatedOk = !sourceFilters.generatedState
      || (sourceFilters.generatedState === 'generated' && row.paymentExecutionGenerated)
      || (sourceFilters.generatedState === 'ready' && row.canGeneratePaymentExecution && !row.paymentExecutionGenerated)
      || (sourceFilters.generatedState === 'blocked' && !row.canGeneratePaymentExecution && !row.paymentExecutionGenerated)
    return keywordOk
      && includesText(row.riskReviewNo, sourceFilters.riskReviewNo)
      && includesText(row.sourcePaymentOrderDraftNo, sourceFilters.sourcePaymentOrderDraftNo)
      && includesText(row.supplierName, sourceFilters.supplierName)
      && (!sourceFilters.riskReviewStatus || row.riskReviewStatus === sourceFilters.riskReviewStatus)
      && generatedOk
  })
})
const filteredExecutions = computed(() => {
  return executions.value.filter((row) => {
    const haystack = [
      row.paymentExecutionNo,
      row.sourceRiskReviewNo,
      row.sourcePaymentOrderDraftNo,
      row.supplierName,
      row.paymentAccount,
      row.paymentAccountName,
      row.supplierBankAccount,
      row.supplierBankAccountName,
      statusLabel(row.paymentExecutionStatus),
    ].join(' ').toLowerCase()
    const keywordOk = !quickSearch.value || haystack.includes(quickSearch.value.trim().toLowerCase())
    const amount = Number(row.executionAmount || 0)
    return keywordOk
      && includesText(row.paymentExecutionNo, filters.paymentExecutionNo)
      && includesText(row.sourceRiskReviewNo, filters.sourceRiskReviewNo)
      && includesText(row.sourcePaymentOrderDraftNo, filters.sourcePaymentOrderDraftNo)
      && includesText(row.supplierName, filters.supplierName)
      && includesText(`${row.paymentAccount} ${row.paymentAccountName}`, filters.paymentAccount)
      && includesText(`${row.supplierBankAccount} ${row.supplierBankAccountName}`, filters.supplierBankAccount)
      && (!filters.amountMin || amount >= Number(filters.amountMin))
      && (!filters.amountMax || amount <= Number(filters.amountMax))
      && includesText(row.paymentMethod, filters.paymentMethod)
      && (!filters.paymentExecutionStatus || row.paymentExecutionStatus === filters.paymentExecutionStatus)
      && (!filters.realPaymentStatus || row.realPaymentStatus === filters.realPaymentStatus)
      && (!filters.voucherStatus || row.voucherStatus === filters.voucherStatus)
      && inDateRange(row.expectedPayDate, filters.expectedStart, filters.expectedEnd)
      && inDateRange(row.actualPayDate, filters.actualStart, filters.actualEnd)
      && boolFilter(row.offlinePaymentRecorded, filters.offlinePaymentRecorded)
      && boolFilter(row.submittedForReview, filters.submittedForReview)
  })
})
const sortColumns = [
  { key: 'paymentExecutionNo', sortType: 'string' },
  { key: 'sourceRiskReviewNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'executionAmount', sortType: 'amount' },
  { key: 'paymentExecutionStatus', sortType: 'status' },
  { key: 'expectedPayDate', sortType: 'date' },
]
const sourceSortColumns = [
  { key: 'riskReviewNo', sortType: 'string' },
  { key: 'sourcePaymentOrderDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'checkPayAmount', sortType: 'amount' },
  { key: 'checkUnpaidAmount', sortType: 'amount' },
  { key: 'riskReviewStatus', sortType: 'status' },
]
const sortedSources = computed(() => sortRecords(filteredSources.value, sourceSortState.value, sourceSortColumns))
const sortedExecutions = computed(() => sortRecords(filteredExecutions.value, sortState.value, sortColumns))
const sourceSortText = computed(() => sourceSortState.value.key ? `当前排序：${sourceSortState.value.key} / ${sourceSortState.value.direction === 'desc' ? '降序' : '升序'}` : '默认业务顺序')
const activeFilterCount = computed(() => Object.values(filters).filter((value) => String(value || '').trim()).length + (quickSearch.value.trim() ? 1 : 0))
const sourceActiveFilterCount = computed(() => Object.values(sourceFilters).filter((value) => String(value || '').trim()).length + (sourceQuickSearch.value.trim() ? 1 : 0))
const sortText = computed(() => sortState.value.key ? `当前排序：${sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}` : '排序：点击表头可排序，点击清除排序恢复默认顺序。')
const batchRecommendationText = computed(() => {
  if (!selectedExecutionRows.value.length) return '推荐下一步：请先选择同一状态的付款执行草稿。'
  const statuses = [...new Set(selectedExecutionRows.value.map((row) => row.paymentExecutionStatus))]
  if (statuses.length > 1) return '所选记录包含多个状态，请按状态分别批量处理，避免误操作。'
  const action = nextActionConfig(statuses[0])
  if (action.terminal) return '所选记录已到本轮终点，无需继续推进。'
  return `推荐下一步：批量${action.label}`
})
const batchRecommendationClass = computed(() => {
  if (!selectedExecutionRows.value.length) return 'app-current-step-tip'
  const statuses = [...new Set(selectedExecutionRows.value.map((row) => row.paymentExecutionStatus))]
  if (statuses.length > 1 || nextActionConfig(statuses[0]).terminal) return 'app-terminal-step-tip'
  return 'app-current-step-tip'
})
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedSources.value, sourceActions, ['生成付款执行草稿', '查看付款执行草稿', '查看评审']))
const executionActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedExecutions.value, executionActions, ['查看详情', '确认付款执行', '等待线下付款', '登记线下付款结果草稿', '提交付款记录复核', '生成付款记录复核', '查看付款记录复核', '取消草稿']))
const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'confirmed', label: '已确认付款执行' },
  { value: 'waitingOfflinePayment', label: '等待线下付款' },
  { value: 'offlinePaymentRecorded', label: '已登记线下付款结果草稿' },
  { value: 'recordReviewPending', label: '付款记录待复核' },
  { value: 'cancelled', label: '已取消' },
]
const detailFields = computed(() => detail.value ? [
  { label: '付款执行草稿号', value: detail.value.paymentExecutionNo },
  { label: '执行状态', value: statusLabel(detail.value.paymentExecutionStatus) },
  { label: '真实付款状态', value: realPaymentStatusLabel(detail.value.realPaymentStatus) },
  { label: '凭证状态', value: voucherStatusLabel(detail.value.voucherStatus) },
  { label: '总账状态', value: getLedgerStatusLabel(detail.value.ledgerStatus) },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '执行金额', value: amountText(detail.value.executionAmount) },
  { label: '未付款金额', value: amountText(detail.value.unpaidAmount) },
  { label: '付款方式', value: detail.value.paymentMethod || '-' },
  { label: '付款银行', value: detail.value.paymentBankName || '-' },
  { label: '付款账户', value: detail.value.paymentAccountName || detail.value.paymentAccount || '-' },
  { label: '供应商开户行', value: detail.value.supplierBankName || '-' },
  { label: '供应商账户', value: detail.value.supplierBankAccountName || detail.value.supplierBankAccount || '-' },
  { label: '预计付款日期', value: detail.value.expectedPayDate || '-' },
  { label: '实际线下日期', value: detail.value.actualPayDate || '-' },
  { label: '线下记录草稿号', value: detail.value.offlinePaymentRecordNo || '-' },
] : [])
const sourceChain = computed(() => detail.value ? [
  { label: '真实付款风险评审', value: detail.value.sourceRiskReviewNo },
  { label: '正式付款单草稿', value: detail.value.sourcePaymentOrderDraftNo },
  { label: '正式付款单预备', value: detail.value.sourcePaymentPrepareNo },
  { label: '供应商付款草稿', value: detail.value.sourcePaymentDraftNo },
  { label: '应付账款草稿', value: detail.value.sourceApDraftNo },
  { label: '发票预备', value: detail.value.sourceInvoicePrepareNo },
  { label: '应付核对', value: detail.value.sourcePayableCheckNo },
  { label: '应付预备', value: detail.value.sourcePayablePrepareNo },
  { label: '库存流水', value: (detail.value.sourceInventoryTransactionNos || []).join('，') },
  { label: '来料检验单', value: detail.value.sourceInspectionNo },
  { label: '采购收货单', value: detail.value.sourceReceiveNo },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo },
  { label: '原始请购单', value: detail.value.rootRequestNo },
] : [])

function defaultFilters() {
  return {
    paymentExecutionNo: '',
    sourceRiskReviewNo: '',
    sourcePaymentOrderDraftNo: '',
    supplierName: '',
    paymentAccount: '',
    supplierBankAccount: '',
    amountMin: '',
    amountMax: '',
    paymentMethod: '',
    paymentExecutionStatus: '',
    realPaymentStatus: '',
    voucherStatus: '',
    expectedStart: '',
    expectedEnd: '',
    actualStart: '',
    actualEnd: '',
    offlinePaymentRecorded: '',
    submittedForReview: '',
  }
}

function refresh() {
  sources.value = getPaymentExecutionSourcesFromRiskReviews()
  executions.value = listPaymentExecutions()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2600)
}

function includesText(value, keyword) {
  return !keyword || String(value || '').toLowerCase().includes(String(keyword).trim().toLowerCase())
}

function inDateRange(value, start, end) {
  if (!start && !end) return true
  if (!value) return false
  return (!start || value >= start) && (!end || value <= end)
}

function boolFilter(value, flag) {
  if (!flag) return true
  return flag === 'yes' ? Boolean(value) : !value
}

function amountText(value) {
  return Number(value || 0).toFixed(2)
}

function nextActionConfig(status) {
  return {
    draft: {
      label: '确认付款执行',
      description: '当前应先确认付款执行意图；该操作不是银行付款。',
    },
    confirmed: {
      label: '标记等待线下付款',
      description: '当前应标记等待线下付款；仍不会连接银行或生成银行流水。',
    },
    waitingOfflinePayment: {
      label: '登记线下付款结果草稿',
      description: '当前应登记线下付款结果草稿；这不是银行回单，也不是付款完成。',
    },
    offlinePaymentRecorded: {
      label: '提交付款记录复核',
      description: '当前应提交付款记录复核；提交后进入本轮终点，不生成凭证、不写总账。',
    },
    recordReviewPending: {
      label: '生成付款记录复核',
      description: '当前应进入付款记录复核页面，生成复核任务；该动作不执行真实付款。',
    },
  }[status] || {
    label: '',
    description: '当前状态暂无推荐推进动作，请查看详情或返回列表核对。',
    terminal: true,
  }
}

function nextStepTitle(status) {
  const action = nextActionConfig(status)
  return action.terminal ? '当前阶段终点' : `推荐下一步：${action.label}`
}

function nextStepDescription(status) {
  return nextActionConfig(status).description
}

function nextStepGuideClass(status) {
  return nextActionConfig(status).terminal ? 'app-terminal-step-tip app-step-guide' : 'app-current-step-tip app-step-guide'
}

function handleOutcome(outcome, successText) {
  if (!outcome?.success) return notify(outcome?.error || '操作失败。', 'warning')
  refresh()
  notify(outcome.alreadyDone ? (outcome.message || '当前状态已达成，无需重复操作。') : successText)
}

function handleCreate(row) {
  const outcome = createPaymentExecutionFromRiskReview(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/payment-execution/${outcome.execution.id}`)
}

function handleBatchCreate() { showSourceBatch(batchCreatePaymentExecutions(sourceIds.value)) }
function handleBatchConfirm() { showExecutionBatch(batchConfirmPaymentExecutions(executionIds.value)) }
function handleBatchWaiting() { showExecutionBatch(batchMarkWaitingOfflinePayment(executionIds.value)) }
function handleBatchRecord() { showExecutionBatch(batchRecordOfflinePaymentDraft(executionIds.value)) }
function handleBatchSubmit() { showExecutionBatch(batchSubmitPaymentRecordReview(executionIds.value)) }
function handleBatchCancel() { showExecutionBatch(batchCancelPaymentExecutions(executionIds.value)) }
function handleConfirm(row) { handleOutcome(confirmPaymentExecution(row.id), '已确认付款执行；这不是银行付款。') }
function handleWaiting(row) { handleOutcome(markWaitingOfflinePayment(row.id), '已标记等待线下付款；尚未完成付款。') }
function handleRecordOffline(row) { handleOutcome(recordOfflinePaymentDraft(row.id, { ...offlineForm }), '已登记线下付款结果草稿；不是银行回单。') }
function handleSubmitReview(row) { handleOutcome(submitPaymentRecordReview(row.id), '已提交付款记录复核；未生成凭证。') }
function handleCancel(row) { handleOutcome(cancelPaymentExecution(row.id), '已取消付款执行草稿。') }

function handleCreateRecordReview(row = {}) {
  const outcome = createPaymentRecordReviewFromPaymentExecution(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/payment-record-review/${outcome.review.id}`)
}

function viewRecordReview(row = {}) {
  const target = getPaymentRecordReviewByPaymentExecutionId(row.id)
  const targetId = target?.id || row.targetPaymentRecordReviewId
  if (targetId) return router.push(`/finance/payment-record-review/${targetId}`)
  return router.push('/finance/payment-record-reviews')
}

function showSourceBatch(result) {
  sourceBatchResult.value = result
  selectedSourceRows.value = []
  sourceTableRef.value?.clearSelection?.()
  refresh()
}

function showExecutionBatch(result) {
  executionBatchResult.value = result
  selectedExecutionRows.value = []
  executionTableRef.value?.clearSelection?.()
  refresh()
}

function batchResultType(result = {}) {
  if (result.failedCount && !result.successCount && !result.alreadyDoneCount) return 'error'
  if (result.failedCount) return 'warning'
  return 'success'
}

function canCancel(row = {}) {
  return ['draft', 'confirmed', 'waitingOfflinePayment', 'offlinePaymentRecorded'].includes(row.paymentExecutionStatus)
}

function canCreateRecordReview(row = {}) {
  return row.paymentExecutionStatus === 'recordReviewPending' && !canViewRecordReview(row)
}

function canViewRecordReview(row = {}) {
  return Boolean(row.paymentRecordReviewGenerated || row.targetPaymentRecordReviewId || getPaymentRecordReviewByPaymentExecutionId(row.id))
}

function recordReviewStateLabel(row = {}) {
  if (canViewRecordReview(row)) return '已生成付款记录复核'
  if (canCreateRecordReview(row)) return '可生成付款记录复核'
  return '未生成付款记录复核'
}

function clearSort() {
  sortState.value = { key: '', direction: 'asc' }
}

function clearSourceSort() {
  sourceSortState.value = { key: '', direction: 'asc' }
}

function resetFilters() {
  Object.assign(filters, defaultFilters())
  quickSearch.value = ''
}

function resetSourceFilters() {
  Object.assign(sourceFilters, {
    riskReviewNo: '',
    sourcePaymentOrderDraftNo: '',
    supplierName: '',
    riskReviewStatus: '',
    generatedState: '',
  })
  sourceQuickSearch.value = ''
}

function handleSortChange({ prop, order }) {
  sortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
}

function handleSourceSortChange({ prop, order }) {
  sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
}

function clearSourceSelection() {
  selectedSourceRows.value = []
  sourceTableRef.value?.clearSelection?.()
}

function clearExecutionSelection() {
  selectedExecutionRows.value = []
  executionTableRef.value?.clearSelection?.()
}

function csvValue(value) {
  const text = Array.isArray(value) ? value.join(';') : String(value ?? '')
  return `"${text.replace(/"/g, '""')}"`
}

function downloadCsv(fileName, headers, rows) {
  const csv = [
    headers.map((item) => csvValue(item.label)).join(','),
    ...rows.map((row) => headers.map((item) => csvValue(typeof item.value === 'function' ? item.value(row) : row[item.value])).join(',')),
  ].join('\n')
  const blob = new Blob([`\ufeff${csv}`], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = fileName
  link.click()
  URL.revokeObjectURL(link.href)
}

function exportSourceRows() {
  downloadCsv('payment-execution-sources.csv', [
    { label: '风险评审号', value: 'riskReviewNo' },
    { label: '付款单草稿号', value: 'sourcePaymentOrderDraftNo' },
    { label: '供应商', value: 'supplierName' },
    { label: '付款账户', value: 'paymentAccountName' },
    { label: '收款账户', value: 'supplierBankAccountName' },
    { label: '检查使用付款金额', value: 'checkPayAmount' },
    { label: '检查使用未付款金额', value: 'checkUnpaidAmount' },
    { label: '评审状态', value: (row) => riskReviewStatusLabel(row.riskReviewStatus) },
    { label: '限制原因', value: 'disabledReason' },
  ], sortedSources.value)
}

function exportExecutionRows() {
  downloadCsv('payment-executions.csv', [
    { label: '付款执行草稿号', value: 'paymentExecutionNo' },
    { label: '来源风险评审号', value: 'sourceRiskReviewNo' },
    { label: '来源付款单草稿号', value: 'sourcePaymentOrderDraftNo' },
    { label: '供应商', value: 'supplierName' },
    { label: '执行金额', value: 'executionAmount' },
    { label: '付款方式', value: 'paymentMethod' },
    { label: '执行状态', value: (row) => statusLabel(row.paymentExecutionStatus) },
    { label: '真实付款状态', value: (row) => realPaymentStatusLabel(row.realPaymentStatus) },
    { label: '凭证状态', value: (row) => voucherStatusLabel(row.voucherStatus) },
    { label: '预计付款日期', value: 'expectedPayDate' },
  ], sortedExecutions.value)
}

function sourceActions(row = {}) {
  return [
    { label: '查看付款执行草稿', visible: row.paymentExecutionGenerated },
    { label: '生成付款执行草稿', visible: !row.paymentExecutionGenerated },
    '查看评审',
  ]
}

function executionActions(row = {}) {
  return [
    '查看详情',
    { label: '确认付款执行', visible: row.paymentExecutionStatus === 'draft' },
    { label: '等待线下付款', visible: row.paymentExecutionStatus === 'confirmed' },
    { label: '登记线下付款结果草稿', visible: row.paymentExecutionStatus === 'waitingOfflinePayment' },
    { label: '提交付款记录复核', visible: row.paymentExecutionStatus === 'offlinePaymentRecorded' },
    { label: '生成付款记录复核', visible: canCreateRecordReview(row) },
    { label: '查看付款记录复核', visible: canViewRecordReview(row) },
    { label: '取消草稿', visible: canCancel(row) },
  ]
}

function statusLabel(status) {
  return getPaymentExecutionStatusLabel(status)
}

function statusType(status) {
  return getPaymentExecutionStatusType(status)
}

function realPaymentStatusLabel(status) {
  return getRealPaymentStatusLabel(status)
}

function voucherStatusLabel(status) {
  return getVoucherStatusLabel(status)
}

function riskReviewStatusLabel(status) {
  return { pending: '待评审', reviewing: '评审中', passed: '评审通过', blocked: '评审阻断', warning: '有警告', cancelled: '已取消' }[status] || status || '-'
}

watch(() => route.fullPath, () => {
  refresh()
  if (detail.value) {
    offlineForm.offlinePaymentRecordNo = detail.value.offlinePaymentRecordNo || ''
    offlineForm.actualPayDate = detail.value.actualPayDate || ''
    offlineForm.offlinePaymentRemark = detail.value.offlinePaymentRemark || ''
  }
}, { immediate: true })
</script>

<style scoped>
.payment-execution-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
.eyebrow, .card-header span, .info-grid span, .source-chain span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finance-flow-nav { align-items: stretch; border: 1px solid #dbeafe; border-radius: 8px; padding: 10px; background: #f8fbff; }
.finance-nav-title { display: flex; align-items: center; color: #475467; font-size: 13px; font-weight: 700; margin-right: 4px; }
.finance-nav-button { border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; background: #fff; color: #1d4ed8; font-weight: 700; text-decoration: none; white-space: nowrap; }
.finance-nav-button-active { border-color: #0f766e; background: #0f766e; color: #fff; box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18); }
.finance-current-tag { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; }
.finance-current-module-badge { display: inline-flex; width: fit-content; border: 1px solid #99f6e4; border-radius: 999px; padding: 5px 10px; background: #ecfdf5; color: #0f766e !important; font-weight: 800; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.boundary-note { border: 1px solid #fed7aa; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #fff7ed; color: #9a3412; font-weight: 700; }
.info-grid, .source-chain, .filter-grid, .form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
.info-grid article, .source-chain article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong, .source-chain strong { display: block; margin-top: 4px; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.button-row .el-button, .batch-bar .el-button { min-width: 96px; white-space: nowrap; }
.button-row .el-button--primary, .button-row .el-button--success, .button-row .el-button--warning,
.batch-bar .el-button--primary, .batch-bar .el-button--success, .batch-bar .el-button--warning { min-width: 132px; }
.batch-bar .el-button--danger, .button-row .el-button--danger { min-width: 96px; }
.batch-action-title { color: #172033; font-weight: 800; }
.batch-action-tip, .sort-help { color: #64748b; font-size: 13px; }
.app-step-guide { display: grid; gap: 6px; margin: 0 0 12px; line-height: 1.6; }
.app-current-step-tip, .app-terminal-step-tip { display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 5px 10px; font-size: 13px; font-weight: 800; }
.app-current-step-tip { border: 1px solid #99f6e4; background: #ecfdf5; color: #0f766e; }
.app-terminal-step-tip { border: 1px solid #cbd5e1; background: #f8fafc; color: #475467; }
.app-step-guide.app-current-step-tip, .app-step-guide.app-terminal-step-tip { display: grid; align-items: stretch; border-radius: 8px; padding: 10px 12px; }
.app-next-action-button { border-color: #0f766e !important; background: #0f766e !important; color: #fff !important; box-shadow: 0 8px 16px rgba(15, 118, 110, 0.2); }
.app-next-action-button.is-disabled, .app-next-action-button:disabled { border-color: #94a3b8 !important; background: #94a3b8 !important; box-shadow: none; }
.app-next-action-badge { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; font-weight: 900; }
.batch-result { position: relative; display: grid; gap: 6px; margin-bottom: 12px; border-radius: 8px; padding: 12px; background: #ecfdf5; color: #065f46; }
.batch-result.warning { background: #fffbeb; color: #92400e; }
.batch-result.error { background: #fef2f2; color: #991b1b; }
.batch-result button { position: absolute; top: 8px; right: 8px; border: 0; background: transparent; color: inherit; cursor: pointer; }
.filter-line, .filter-grid { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; margin-bottom: 12px; background: #fff; }
label { display: grid; gap: 6px; color: #334155; font-weight: 700; }
input, select { width: 100%; box-sizing: border-box; border: 1px solid #cbd5e1; border-radius: 6px; padding: 8px 10px; background: #fff; color: #172033; }
.offline-panel { display: grid; gap: 12px; }
.offline-panel p { margin: 0; color: #475467; line-height: 1.6; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
