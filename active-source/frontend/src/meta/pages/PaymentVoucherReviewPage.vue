<template>
  <main class="payment-voucher-review-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.5.1 付款凭证复核页面原型</p>
        <h1>{{ detail ? '付款凭证复核详情' : '付款凭证复核' }}</h1>
        <p>本页只复核付款凭证草稿，不生成正式财务凭证，不写总账，不过账，不做付款核销。</p>
        <p class="finance-current-module-badge">当前操作模块：付款凭证复核</p>
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
        <router-link class="finance-nav-button" to="/finance/payment-executions">付款执行草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-record-reviews">付款记录复核</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-voucher-drafts">付款凭证草稿</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-voucher-reviews">付款凭证复核<span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/formal-payment-vouchers">正式付款凭证</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款凭证复核流程：付款凭证草稿待复核 -> 生成复核任务 -> 开始复核 -> 复核通过 / 退回</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>人工复核付款凭证草稿。</span>
          <span><b>本页做什么</b>检查来源、金额、借贷、科目、期间、权限和过账边界。</span>
          <span><b>下一步做什么</b>复核通过后才可进入后续正式凭证生成范围评审。</span>
          <span><b>本页不做什么</b>不生成正式凭证、不写总账、不过账、不核销。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.voucherReviewNo }}</h2>
              <span>{{ detail.sourceVoucherDraftNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-voucher-reviews')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-voucher-draft/${detail.sourceVoucherDraftId}`)">查看来源凭证草稿</el-button>
              <el-button v-if="detail.voucherReviewStatus === 'pending'" class="app-next-action-button" type="primary" @click="handleStart(detail)">开始复核<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="detail.voucherReviewStatus === 'reviewing'" class="app-next-action-button" type="success" @click="handlePass(detail)">复核通过<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="detail.voucherReviewStatus === 'reviewing'" type="warning" @click="handleReject(detail)">复核退回</el-button>
              <el-button v-if="['pending', 'reviewing', 'rejected'].includes(detail.voucherReviewStatus)" type="danger" @click="handleCancel(detail)">取消复核</el-button>
              <el-button v-if="showFormalVoucherEntry(detail)" :class="{ 'app-next-action-button': !formalVoucherTarget(detail) }" type="success" @click="handleFormalVoucherEntry(detail)">{{ formalVoucherEntryLabel(detail) }}<span v-if="!formalVoucherTarget(detail)" class="app-next-action-badge">下一步</span></el-button>
            </div>
          </div>
        </template>
        <div class="boundary-note">当前状态：{{ reviewStatusLabel(detail.voucherReviewStatus) }}。复核通过不是正式凭证，不代表过账、写总账或付款核销完成。</div>
        <div :class="nextStepGuideClass(detail.voucherReviewStatus)">
          <strong>{{ nextStepTitle(detail.voucherReviewStatus) }}</strong>
          <span>{{ nextStepDescription(detail.voucherReviewStatus) }}</span>
        </div>
        <div v-if="detail.reviewerSource === 'localDemo'" class="reviewer-demo-note">当前复核人为本地演示操作人，后续应接入正式登录用户、岗位权限和审批流。</div>
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
        <template #header><h2>风险检查项</h2></template>
        <el-table :data="detail.riskItems || []" border stripe height="320">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="itemName" label="检查项" min-width="180" />
          <el-table-column prop="result" label="结果" width="120">
            <template #default="{ row }"><el-tag :type="riskItemType(row.level)">{{ riskItemLabel(row.result) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="message" label="说明" min-width="360" />
          <el-table-column prop="level" label="级别" width="120" fixed="right">
            <template #default="{ row }">{{ riskItemLabel(row.level) }}</template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>凭证分录草稿</h2></template>
        <el-table :data="detail.lines || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="direction" label="借贷方向" width="110">
            <template #default="{ row }">{{ row.direction === 'debit' ? '借方' : '贷方' }}</template>
          </el-table-column>
          <el-table-column prop="accountCode" label="科目编码" width="120" />
          <el-table-column prop="accountName" label="科目名称" min-width="150" />
          <el-table-column prop="amount" label="金额" width="130" sortable />
          <el-table-column prop="cashFlowItem" label="现金流量项目" min-width="200" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="260" fixed="right" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款凭证复核边界</strong>
        <div class="plain-flow-grid">
          <span><b>来源</b>只允许从“待凭证复核”的付款凭证草稿生成复核任务。</span>
          <span><b>复核</b>只做人工确认，不生成正式凭证号。</span>
          <span><b>终点</b>本轮终点是“凭证复核通过”。</span>
          <span><b>财务边界</b>不写总账、不过账、不做付款核销。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源付款凭证草稿区</h2>
              <span>只允许从“待凭证复核”的付款凭证草稿生成复核任务。</span>
            </div>
            <div class="button-row">
              <el-button @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-voucher-drafts')">查看付款凭证草稿</el-button>
            </div>
          </div>
        </template>
        <StandardListToolbar
          page-id="payment-voucher-review"
          table-id="payment-voucher-review-source"
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
        <section v-show="isAdvancedFilterExpanded" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-voucher-review-source">
          <label>付款凭证草稿号<PceResultFilterSelect v-model="sourceFilters.voucherDraftNo" :rows="sortedSources" :fields="['voucherDraftNo']" /></label>
          <label>来源付款记录复核<PceResultFilterSelect v-model="sourceFilters.sourcePaymentRecordReviewNo" :rows="sortedSources" :fields="['sourcePaymentRecordReviewNo']" /></label>
          <label>供应商<PceResultFilterSelect v-model="sourceFilters.supplierName" :rows="sortedSources" :fields="['supplierName']" /></label>
          <label>风险等级<select v-model="sourceFilters.riskLevel"><option value="">全部</option><option value="low">低风险</option><option value="warning">有警告</option><option value="blocked">阻断</option></select></label>
          <label>生成状态<select v-model="sourceFilters.generatedState"><option value="">全部</option><option value="ready">可生成复核任务</option><option value="generated">已生成复核任务</option><option value="blocked">暂不可生成</option></select></label>
        </section>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span class="batch-action-title">当前模块操作（生成复核任务）</span>
          <span class="batch-action-tip">只生成付款凭证复核任务，不生成正式财务凭证、不写总账。</span>
          <el-button type="primary" size="small" :disabled="!sourceIds.length" @click="handleBatchCreate">批量生成付款凭证复核</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="batchResultType(sourceBatchResult)" @close="sourceBatchResult = null" />
        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-voucher-review-source" page-id="payment-voucher-review" table-id="payment-voucher-review-source" min-width="100%">
        <el-table ref="sourceTableRef" class="pce-baseline-table-shell global-sort-arrow" :data="sortedSources" border stripe height="420" @selection-change="selectedSourceRows = $event" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="voucherDraftNo" label="付款凭证草稿号" min-width="180" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentRecordReviewNo" label="来源付款记录复核" min-width="180" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="accountingPeriod" label="会计期间" width="120" />
          <el-table-column prop="debitAmount" label="借方金额" width="130" sortable="custom" />
          <el-table-column prop="creditAmount" label="贷方金额" width="130" sortable="custom" />
          <el-table-column prop="differenceAmount" label="差异金额" width="130" />
          <el-table-column prop="riskLevel" label="风险等级" width="120">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.riskLevel)">{{ riskLevelLabel(row.riskLevel) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="复核任务" width="170">
            <template #default="{ row }"><el-tag :type="row.paymentVoucherReviewGenerated ? 'success' : (row.canGeneratePaymentVoucherReview ? 'primary' : 'info')">{{ row.paymentVoucherReviewGenerated ? '已生成复核任务' : (row.canGeneratePaymentVoucherReview ? '可生成复核任务' : '暂不可生成') }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="disabledReason" label="限制原因" min-width="260" />
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="row.paymentVoucherReviewGenerated" class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-voucher-review/${row.targetPaymentVoucherReviewId}`)">查看付款凭证复核</el-button>
                <el-button v-else class="app-action-button-lg app-next-action-button" size="small" type="primary" :disabled="!row.canGeneratePaymentVoucherReview" @click="handleCreate(row)">生成付款凭证复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-voucher-draft/${row.id}`)">查看付款凭证草稿</el-button>
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
              <h2>付款凭证复核列表</h2>
              <span>复核通过只表示草稿凭证通过人工复核，不代表正式凭证、过账或总账。</span>
            </div>
            <div class="button-row">
              <el-button @click="quickSearchOpen = !quickSearchOpen">{{ quickSearchOpen ? '收起快速搜索' : '展开快速搜索' }}</el-button>
              <el-button @click="clearSort">清除排序</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </div>
          </div>
        </template>
        <StandardListToolbar
          page-id="payment-voucher-review"
          table-id="payment-voucher-review-main"
          v-model:quick-search="quickSearch"
          :advanced-visible="isAdvancedFilterExpanded"
          :show-advanced-filter-toggle="false"
          :result-count="sortedReviews.length"
          :selected-count="selectedReviewRows.length"
          :active-filter-count="activeFilterCount"
          :sort-text="sortText"
          :export-disabled="sortedReviews.length === 0"
          @search="clearReviewSelection"
          @clear-filters="resetFilters"
          @clear-sort="clearSort"
          @export-current="exportReviewRows"
          @clear-selection="clearReviewSelection"
        />

        <section v-if="quickSearchOpen" class="filter-line">
          <label>快速搜索<input v-model="quickSearch" placeholder="复核单号 / 草稿号 / 供应商 / 状态 / 复核人" /></label>
        </section>

        <section v-show="isAdvancedFilterExpanded" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-voucher-review-main">
          <label>凭证复核单号<PceResultFilterSelect v-model="filters.voucherReviewNo" :options="filterSuggestions.voucherReviewNo" /></label>
          <label>来源凭证草稿号<PceResultFilterSelect v-model="filters.sourceVoucherDraftNo" :options="filterSuggestions.sourceVoucherDraftNo" /></label>
          <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :options="filterSuggestions.supplierName" /></label>
          <label>会计期间<PceResultFilterSelect v-model="filters.accountingPeriod" :options="filterSuggestions.accountingPeriod" /></label>
          <label>借方金额下限<input v-model="filters.debitMin" type="number" /></label>
          <label>借方金额上限<input v-model="filters.debitMax" type="number" /></label>
          <label>贷方金额下限<input v-model="filters.creditMin" type="number" /></label>
          <label>贷方金额上限<input v-model="filters.creditMax" type="number" /></label>
          <label>差异金额上限<input v-model="filters.diffMax" type="number" /></label>
          <label>复核状态<select v-model="filters.voucherReviewStatus"><option value="">全部</option><option value="pending">待复核</option><option value="reviewing">复核中</option><option value="passed">复核通过</option><option value="rejected">复核退回</option><option value="cancelled">取消复核</option></select></label>
          <label>复核结果<select v-model="filters.voucherReviewResult"><option value="">全部</option><option value="notReviewed">未复核</option><option value="passed">通过</option><option value="rejected">退回</option></select></label>
          <label>总账状态<select v-model="filters.ledgerStatus"><option value="">全部</option><option value="notPosted">未过账</option></select></label>
          <label>风险等级<select v-model="filters.riskLevel"><option value="">全部</option><option value="low">低风险</option><option value="warning">有警告</option><option value="blocked">阻断</option></select></label>
          <label>复核人<PceResultFilterSelect v-model="filters.reviewerName" :options="filterSuggestions.reviewerName" /></label>
          <label>是否已通过<select v-model="filters.passed"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已退回<select v-model="filters.rejected"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已取消<select v-model="filters.cancelled"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        </section>

        <div class="batch-bar">
          <span>已选择 {{ selectedReviewRows.length }} 条</span>
          <span class="sort-help">{{ sortText }}</span>
          <span class="batch-action-title">当前模块操作（只修改复核任务状态）</span>
          <span class="batch-action-tip">复核通过不是正式凭证，不写总账、不过账、不核销。</span>
          <span :class="batchRecommendationClass">{{ batchRecommendationText }}</span>
          <el-button size="small" type="primary" :disabled="!reviewIds.length" @click="handleBatchStart">批量开始复核</el-button>
          <el-button size="small" type="success" :disabled="!reviewIds.length" @click="handleBatchPass">批量复核通过</el-button>
          <el-button size="small" type="warning" :disabled="!reviewIds.length" @click="handleBatchReject">批量复核退回</el-button>
          <el-button size="small" type="danger" :disabled="!reviewIds.length" @click="handleBatchCancel">批量取消复核</el-button>
        </div>
        <BatchResult v-if="reviewBatchResult" :result="reviewBatchResult" :type="batchResultType(reviewBatchResult)" @close="reviewBatchResult = null" />

        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-voucher-review-main" page-id="payment-voucher-review" table-id="payment-voucher-review-main" min-width="100%">
        <el-table ref="reviewTableRef" class="pce-baseline-table-shell global-sort-arrow" :data="sortedReviews" border stripe height="520" @selection-change="selectedReviewRows = $event" @sort-change="handleSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="voucherReviewNo" label="凭证复核单号" min-width="170" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceVoucherDraftNo" label="来源凭证草稿" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="accountingPeriod" label="会计期间" width="120" />
          <el-table-column prop="debitAmount" label="借方金额" width="130" sortable="custom" />
          <el-table-column prop="creditAmount" label="贷方金额" width="130" sortable="custom" />
          <el-table-column prop="differenceAmount" label="差异金额" width="130" />
          <el-table-column prop="voucherReviewStatus" label="复核状态" width="130" sortable="custom">
            <template #default="{ row }"><el-tag :type="reviewStatusType(row.voucherReviewStatus)">{{ reviewStatusLabel(row.voucherReviewStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="voucherReviewResult" label="复核结果" width="120">
            <template #default="{ row }">{{ reviewResultLabel(row.voucherReviewResult) }}</template>
          </el-table-column>
          <el-table-column prop="ledgerStatus" label="总账状态" width="120">
            <template #default="{ row }">{{ ledgerStatusLabel(row.ledgerStatus) }}</template>
          </el-table-column>
          <el-table-column prop="riskLevel" label="风险等级" width="120">
            <template #default="{ row }"><el-tag :type="riskLevelType(row.riskLevel)">{{ riskLevelLabel(row.riskLevel) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="正式凭证" width="160">
            <template #default="{ row }"><el-tag :type="formalVoucherTarget(row) ? 'success' : (row.voucherReviewStatus === 'passed' ? 'primary' : 'info')">{{ formalVoucherTarget(row) ? '已生成正式付款凭证' : (row.voucherReviewStatus === 'passed' ? '可生成正式付款凭证' : '暂不可生成') }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="reviewerName" label="复核人" min-width="130">
            <template #default="{ row }">{{ row.reviewerName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="reviewerRole" label="复核角色" min-width="140">
            <template #default="{ row }">{{ row.reviewerRole || '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="reviewActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button class="app-action-button-sm" size="small" @click="router.push(`/finance/payment-voucher-review/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.voucherReviewStatus === 'pending'" class="app-action-button-lg app-next-action-button" size="small" type="primary" @click="handleStart(row)">开始复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="row.voucherReviewStatus === 'reviewing'" class="app-action-button-lg app-next-action-button" size="small" type="success" @click="handlePass(row)">复核通过<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="row.voucherReviewStatus === 'reviewing'" class="app-action-button-sm" size="small" type="warning" @click="handleReject(row)">复核退回</el-button>
                <el-button v-if="row.voucherReviewStatus === 'rejected'" class="app-action-button-lg app-next-action-button" size="small" type="primary" @click="handleStart(row)">重新复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="['pending', 'reviewing', 'rejected'].includes(row.voucherReviewStatus)" class="app-action-button-sm" size="small" type="danger" @click="handleCancel(row)">取消复核</el-button>
                <el-button v-if="showFormalVoucherEntry(row)" class="app-action-button-lg" :class="{ 'app-next-action-button': !formalVoucherTarget(row) }" size="small" type="success" @click="handleFormalVoucherEntry(row)">{{ formalVoucherEntryLabel(row) }}<span v-if="!formalVoucherTarget(row)" class="app-next-action-badge">下一步</span></el-button>
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
  batchCancelPaymentVoucherReviews,
  batchCreatePaymentVoucherReviewsFromVoucherDrafts,
  batchPassPaymentVoucherReviews,
  batchRejectPaymentVoucherReviews,
  batchStartPaymentVoucherReviews,
  cancelPaymentVoucherReview,
  createPaymentVoucherReviewFromVoucherDraft,
  getPaymentVoucherReviewById,
  getPaymentVoucherReviewResultLabel,
  getPaymentVoucherReviewRiskLevelLabel,
  getPaymentVoucherReviewRiskLevelType,
  getPaymentVoucherReviewSourcesFromVoucherDrafts,
  getPaymentVoucherReviewStatusLabel,
  getPaymentVoucherReviewStatusType,
  listPaymentVoucherReviews,
  passPaymentVoucherReview,
  rejectPaymentVoucherReview,
  startPaymentVoucherReview,
} from '../finance/paymentVoucherReviewStore.js'
import {
  createFormalVoucherFromVoucherReview,
  isFormalVoucherGenerated,
} from '../finance/formalPaymentVoucherStore.js'
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
      h('span', `失败 / 跳过：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      h('span', `下一步建议：${props.result.nextSuggestion || '按当前复核状态继续处理。'}`),
      h('span', '边界说明：本批量结果不代表正式凭证已生成，不写总账，不过账，不做付款核销。'),
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sources = ref([])
const reviews = ref([])
const selectedSourceRows = ref([])
const selectedReviewRows = ref([])
const sourceTableRef = ref(null)
const reviewTableRef = ref(null)
const sourceBatchResult = ref(null)
const reviewBatchResult = ref(null)
const quickSearchOpen = ref(false)
const isAdvancedFilterExpanded = ref(false)
const quickSearch = ref('')
const sourceQuickSearch = ref('')
const sortState = ref({ key: '', direction: 'asc' })
const sourceSortState = ref({ key: '', direction: 'asc' })
const message = ref('')
const messageType = ref('success')
const filters = reactive(defaultFilters())
const sourceFilters = reactive({
  voucherDraftNo: '',
  sourcePaymentRecordReviewNo: '',
  supplierName: '',
  riskLevel: '',
  generatedState: '',
})

const detail = computed(() => route.params.id ? getPaymentVoucherReviewById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const reviewIds = computed(() => selectedReviewRows.value.map((row) => row.id).filter(Boolean))
const filterSuggestions = computed(() => ({
  voucherReviewNo: uniqueValues(reviews.value.map((row) => row.voucherReviewNo)),
  sourceVoucherDraftNo: uniqueValues(reviews.value.map((row) => row.sourceVoucherDraftNo)),
  supplierName: uniqueValues(reviews.value.map((row) => row.supplierName)),
  accountingPeriod: uniqueValues(reviews.value.map((row) => row.accountingPeriod)),
  reviewerName: uniqueValues(reviews.value.map((row) => row.reviewerName)),
}))
const filteredSources = computed(() => {
  const rows = route.query.sourceVoucherDraftId
    ? sources.value.filter((row) => String(row.id) === String(route.query.sourceVoucherDraftId))
    : sources.value
  return rows.filter((row) => {
    const haystack = [
      row.voucherDraftNo,
      row.sourcePaymentRecordReviewNo,
      row.supplierName,
      row.accountingPeriod,
      riskLevelLabel(row.riskLevel),
    ].join(' ').toLowerCase()
    const keywordOk = !sourceQuickSearch.value || haystack.includes(sourceQuickSearch.value.trim().toLowerCase())
    const generatedOk = !sourceFilters.generatedState
      || (sourceFilters.generatedState === 'generated' && row.paymentVoucherReviewGenerated)
      || (sourceFilters.generatedState === 'ready' && row.canGeneratePaymentVoucherReview && !row.paymentVoucherReviewGenerated)
      || (sourceFilters.generatedState === 'blocked' && !row.canGeneratePaymentVoucherReview && !row.paymentVoucherReviewGenerated)
    return keywordOk
      && includesText(row.voucherDraftNo, sourceFilters.voucherDraftNo)
      && includesText(row.sourcePaymentRecordReviewNo, sourceFilters.sourcePaymentRecordReviewNo)
      && includesText(row.supplierName, sourceFilters.supplierName)
      && (!sourceFilters.riskLevel || row.riskLevel === sourceFilters.riskLevel)
      && generatedOk
  })
})
const filteredReviews = computed(() => reviews.value.filter((row) => {
  const haystack = [
    row.voucherReviewNo,
    row.sourceVoucherDraftNo,
    row.supplierName,
    row.accountingPeriod,
    row.reviewerName,
    reviewStatusLabel(row.voucherReviewStatus),
    riskLevelLabel(row.riskLevel),
  ].join(' ').toLowerCase()
  return (!quickSearch.value || haystack.includes(quickSearch.value.trim().toLowerCase()))
    && includesText(row.voucherReviewNo, filters.voucherReviewNo)
    && includesText(row.sourceVoucherDraftNo, filters.sourceVoucherDraftNo)
    && includesText(row.supplierName, filters.supplierName)
    && includesText(row.accountingPeriod, filters.accountingPeriod)
    && inAmountRange(row.debitAmount, filters.debitMin, filters.debitMax)
    && inAmountRange(row.creditAmount, filters.creditMin, filters.creditMax)
    && (!filters.diffMax || Number(row.differenceAmount || 0) <= Number(filters.diffMax))
    && (!filters.voucherReviewStatus || row.voucherReviewStatus === filters.voucherReviewStatus)
    && (!filters.voucherReviewResult || row.voucherReviewResult === filters.voucherReviewResult)
    && (!filters.ledgerStatus || row.ledgerStatus === filters.ledgerStatus)
    && (!filters.riskLevel || row.riskLevel === filters.riskLevel)
    && includesText(row.reviewerName, filters.reviewerName)
    && boolStatus(row.voucherReviewStatus === 'passed', filters.passed)
    && boolStatus(row.voucherReviewStatus === 'rejected', filters.rejected)
    && boolStatus(row.voucherReviewStatus === 'cancelled', filters.cancelled)
}))
const sortColumns = [
  { key: 'voucherReviewNo', sortType: 'string' },
  { key: 'sourceVoucherDraftNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'debitAmount', sortType: 'amount' },
  { key: 'creditAmount', sortType: 'amount' },
  { key: 'voucherReviewStatus', sortType: 'status' },
]
const sourceSortColumns = [
  { key: 'voucherDraftNo', sortType: 'string' },
  { key: 'sourcePaymentRecordReviewNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'debitAmount', sortType: 'amount' },
  { key: 'creditAmount', sortType: 'amount' },
  { key: 'riskLevel', sortType: 'status' },
]
const sortedSources = computed(() => sortRecords(filteredSources.value, sourceSortState.value, sourceSortColumns))
const sortedReviews = computed(() => sortRecords(filteredReviews.value, sortState.value, sortColumns))
const sourceSortText = computed(() => sourceSortState.value.key ? `当前排序：${sourceSortState.value.key} / ${sourceSortState.value.direction === 'desc' ? '降序' : '升序'}` : '默认业务顺序')
const activeFilterCount = computed(() => Object.values(filters).filter((value) => String(value || '').trim()).length + (quickSearch.value.trim() ? 1 : 0))
const sourceActiveFilterCount = computed(() => Object.values(sourceFilters).filter((value) => String(value || '').trim()).length + (sourceQuickSearch.value.trim() ? 1 : 0))
const sortText = computed(() => sortState.value.key ? `当前排序：${sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}` : '排序：点击表头可排序，点击清除排序恢复默认顺序。')
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedSources.value, sourceActions, ['生成付款凭证复核', '查看付款凭证复核', '查看付款凭证草稿']))
const reviewActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedReviews.value, reviewActions, ['查看详情', '开始复核', '重新复核', '复核通过', '复核退回', '取消复核', '生成正式付款凭证', '查看正式付款凭证']))
const batchRecommendationText = computed(() => {
  if (!selectedReviewRows.value.length) return '推荐下一步：请选择复核任务后再批量处理。'
  const statuses = [...new Set(selectedReviewRows.value.map((row) => row.voucherReviewStatus))]
  if (statuses.length > 1) return '所选记录包含多个状态，请按状态分别批量处理。'
  if (statuses[0] === 'pending') return '推荐下一步：批量开始复核。'
  if (statuses[0] === 'reviewing') return '推荐下一步：批量复核通过或退回。'
  if (statuses[0] === 'rejected') return '推荐下一步：批量重新复核或取消复核。'
  return '所选记录已到终点或已取消，只建议查看。'
})
const batchRecommendationClass = computed(() => selectedReviewRows.value.some((row) => ['pending', 'reviewing', 'rejected'].includes(row.voucherReviewStatus)) ? 'app-current-step-tip' : 'app-terminal-step-tip')
const detailFields = computed(() => detail.value ? [
  { label: '凭证复核单号', value: detail.value.voucherReviewNo },
  { label: '来源凭证草稿', value: detail.value.sourceVoucherDraftNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '凭证日期', value: detail.value.voucherDate || '-' },
  { label: '会计期间', value: detail.value.accountingPeriod || '-' },
  { label: '复核状态', value: reviewStatusLabel(detail.value.voucherReviewStatus) },
  { label: '复核结果', value: reviewResultLabel(detail.value.voucherReviewResult) },
  { label: '总账状态', value: ledgerStatusLabel(detail.value.ledgerStatus) },
  { label: '借方金额', value: amountText(detail.value.debitAmount) },
  { label: '贷方金额', value: amountText(detail.value.creditAmount) },
  { label: '差异金额', value: amountText(detail.value.differenceAmount) },
  { label: '风险等级', value: riskLevelLabel(detail.value.riskLevel) },
  { label: '复核人', value: detail.value.reviewerName || '-' },
  { label: '复核角色', value: detail.value.reviewerRole || '-' },
  { label: '复核来源', value: reviewerSourceLabel(detail.value.reviewerSource) },
  { label: '复核时间', value: formatDateTime(detail.value.reviewedAt) },
  { label: '复核意见', value: detail.value.voucherReviewOpinion || '-' },
] : [])
const sourceChain = computed(() => detail.value ? [
  { label: '付款凭证草稿', value: detail.value.sourceVoucherDraftNo },
  { label: '付款记录复核', value: detail.value.sourcePaymentRecordReviewNo },
  { label: '付款执行草稿', value: detail.value.sourcePaymentExecutionNo },
  { label: '真实付款风险评审', value: detail.value.sourceRiskReviewNo },
  { label: '正式付款单草稿', value: detail.value.sourcePaymentOrderDraftNo },
  { label: '正式付款单预备', value: detail.value.sourcePaymentPrepareNo },
  { label: '供应商付款草稿', value: detail.value.sourcePaymentDraftNo },
  { label: '应付账款草稿', value: detail.value.sourceApDraftNo },
  { label: '发票预备', value: detail.value.sourceInvoicePrepareNo },
  { label: '应付核对', value: detail.value.sourcePayableCheckNo },
  { label: '应付预备', value: detail.value.sourcePayablePrepareNo },
  { label: '库存流水', value: (detail.value.sourceInventoryTransactionNos || []).join('；') },
  { label: '检验单', value: detail.value.sourceInspectionNo },
  { label: '收货单', value: detail.value.sourceReceiveNo },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo },
  { label: '原始请购单', value: detail.value.rootRequestNo },
] : [])

function defaultFilters() {
  return {
    voucherReviewNo: '',
    sourceVoucherDraftNo: '',
    supplierName: '',
    accountingPeriod: '',
    debitMin: '',
    debitMax: '',
    creditMin: '',
    creditMax: '',
    diffMax: '',
    voucherReviewStatus: '',
    voucherReviewResult: '',
    ledgerStatus: '',
    riskLevel: '',
    reviewerName: '',
    passed: '',
    rejected: '',
    cancelled: '',
  }
}

function refresh() {
  sources.value = getPaymentVoucherReviewSourcesFromVoucherDrafts()
  reviews.value = listPaymentVoucherReviews()
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

function inAmountRange(value, min, max) {
  const amount = Number(value || 0)
  return (!min || amount >= Number(min)) && (!max || amount <= Number(max))
}

function boolStatus(value, flag) {
  if (!flag) return true
  return flag === 'yes' ? Boolean(value) : !value
}

function amountText(value) {
  return Number(value || 0).toFixed(2)
}

function formatDateTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ').replace(/\.\d{3}Z$/, '').replace(/Z$/, '')
}

function reviewerSourceLabel(source) {
  return {
    currentUser: '当前登录用户',
    organization: '组织人员档案',
    workflow: '审批流配置',
    localDemo: '本地演示复核人',
  }[source] || source || '-'
}

function uniqueValues(values = []) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function handleOutcome(outcome, successText) {
  if (!outcome?.success) {
    refresh()
    return notify(outcome?.error || '操作失败。', 'warning')
  }
  refresh()
  notify(outcome.alreadyDone ? (outcome.message || '当前状态已达成，无需重复操作。') : successText)
}

function handleCreate(row) {
  const outcome = createPaymentVoucherReviewFromVoucherDraft(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/payment-voucher-review/${outcome.review.id}`)
}

function handleBatchCreate() { showSourceBatch(batchCreatePaymentVoucherReviewsFromVoucherDrafts(sourceIds.value)) }
function handleBatchStart() { showReviewBatch(batchStartPaymentVoucherReviews(reviewIds.value)) }
function handleBatchPass() { showReviewBatch(batchPassPaymentVoucherReviews(reviewIds.value)) }
function handleBatchReject() { showReviewBatch(batchRejectPaymentVoucherReviews(reviewIds.value)) }
function handleBatchCancel() { showReviewBatch(batchCancelPaymentVoucherReviews(reviewIds.value)) }
function handleStart(row) { handleOutcome(startPaymentVoucherReview(row.id), '已开始付款凭证复核。') }
function handlePass(row) { handleOutcome(passPaymentVoucherReview(row.id), '已复核通过；仍未生成正式凭证，不写总账。') }
function handleReject(row) { handleOutcome(rejectPaymentVoucherReview(row.id), '已复核退回；不生成正式凭证、不写总账。') }
function handleCancel(row) { handleOutcome(cancelPaymentVoucherReview(row.id), '已取消付款凭证复核任务。') }

function formalVoucherTarget(row = {}) {
  const target = isFormalVoucherGenerated(row.id)
  if (target?.id) return target
  if (row.formalVoucherGenerated && row.targetFormalVoucherId && row.formalVoucherStatus !== 'cancelled') {
    return {
      id: row.targetFormalVoucherId,
      formalVoucherNo: row.targetFormalVoucherNo,
      formalVoucherStatus: row.formalVoucherStatus,
    }
  }
  return null
}

function showFormalVoucherEntry(row = {}) {
  return row.voucherReviewStatus === 'passed' || Boolean(formalVoucherTarget(row))
}

function formalVoucherEntryLabel(row = {}) {
  return formalVoucherTarget(row) ? '查看正式付款凭证' : '生成正式付款凭证'
}

function ledgerStatusLabel(status) {
  return {
    notPosted: '未过账',
    notWritten: '未写总账',
  }[status] || status || '-'
}

function handleFormalVoucherEntry(row = {}) {
  const target = formalVoucherTarget(row)
  if (target?.id) return router.push(`/finance/formal-payment-voucher/${target.id}`)
  const outcome = createFormalVoucherFromVoucherReview(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  return router.push(`/finance/formal-payment-voucher/${outcome.formalVoucher.id}`)
}

function showSourceBatch(result) {
  sourceBatchResult.value = result
  selectedSourceRows.value = []
  sourceTableRef.value?.clearSelection?.()
  refresh()
}

function showReviewBatch(result) {
  reviewBatchResult.value = result
  selectedReviewRows.value = []
  reviewTableRef.value?.clearSelection?.()
  refresh()
}

function batchResultType(result = {}) {
  if (result.failedCount && !result.successCount && !result.alreadyDoneCount) return 'error'
  if (result.failedCount) return 'warning'
  return 'success'
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
    voucherDraftNo: '',
    sourcePaymentRecordReviewNo: '',
    supplierName: '',
    riskLevel: '',
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

function clearReviewSelection() {
  selectedReviewRows.value = []
  reviewTableRef.value?.clearSelection?.()
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
  downloadCsv('payment-voucher-review-sources.csv', [
    { label: '付款凭证草稿号', value: 'voucherDraftNo' },
    { label: '来源付款记录复核', value: 'sourcePaymentRecordReviewNo' },
    { label: '供应商', value: 'supplierName' },
    { label: '会计期间', value: 'accountingPeriod' },
    { label: '借方金额', value: 'debitAmount' },
    { label: '贷方金额', value: 'creditAmount' },
    { label: '差异金额', value: 'differenceAmount' },
    { label: '风险等级', value: (row) => riskLevelLabel(row.riskLevel) },
    { label: '限制原因', value: 'disabledReason' },
  ], sortedSources.value)
}

function exportReviewRows() {
  downloadCsv('payment-voucher-reviews.csv', [
    { label: '凭证复核单号', value: 'voucherReviewNo' },
    { label: '来源凭证草稿', value: 'sourceVoucherDraftNo' },
    { label: '供应商', value: 'supplierName' },
    { label: '会计期间', value: 'accountingPeriod' },
    { label: '借方金额', value: 'debitAmount' },
    { label: '贷方金额', value: 'creditAmount' },
    { label: '复核状态', value: (row) => reviewStatusLabel(row.voucherReviewStatus) },
    { label: '复核结果', value: (row) => reviewResultLabel(row.voucherReviewResult) },
    { label: '总账状态', value: (row) => ledgerStatusLabel(row.ledgerStatus) },
    { label: '风险等级', value: (row) => riskLevelLabel(row.riskLevel) },
  ], sortedReviews.value)
}

function sourceActions(row = {}) {
  return [
    { label: '查看付款凭证复核', visible: row.paymentVoucherReviewGenerated },
    { label: '生成付款凭证复核', visible: !row.paymentVoucherReviewGenerated },
    '查看付款凭证草稿',
  ]
}

function reviewActions(row = {}) {
  return [
    '查看详情',
    { label: '开始复核', visible: row.voucherReviewStatus === 'pending' },
    { label: '重新复核', visible: row.voucherReviewStatus === 'rejected' },
    { label: '复核通过', visible: row.voucherReviewStatus === 'reviewing' },
    { label: '复核退回', visible: row.voucherReviewStatus === 'reviewing' },
    { label: '取消复核', visible: ['pending', 'reviewing', 'rejected'].includes(row.voucherReviewStatus) },
    { label: formalVoucherEntryLabel(row), visible: showFormalVoucherEntry(row) },
  ]
}

function nextStepTitle(status) {
  if (status === 'pending') return '推荐下一步：开始复核'
  if (status === 'reviewing') return '推荐下一步：复核通过或复核退回'
  if (status === 'rejected') return '推荐下一步：重新复核'
  if (status === 'passed') return '当前阶段终点：凭证复核通过'
  if (status === 'cancelled') return '当前复核任务已取消'
  return '当前状态只建议查看'
}

function nextStepDescription(status) {
  if (status === 'pending') return '开始后进入复核中，可继续通过、退回或取消。'
  if (status === 'reviewing') return '复核通过只表示草稿通过人工复核，不代表正式凭证或过账。'
  if (status === 'rejected') return '退回后可重新复核或取消复核。'
  if (status === 'passed') return '本轮到“复核通过”为止，不生成正式凭证、不写总账。'
  if (status === 'cancelled') return '该复核任务已取消，只保留查看。'
  return '请查看详情或返回列表。'
}

function nextStepGuideClass(status) {
  return ['pending', 'reviewing', 'rejected'].includes(status) ? 'app-current-step-tip app-step-guide' : 'app-terminal-step-tip app-step-guide'
}

function reviewStatusLabel(status) {
  return getPaymentVoucherReviewStatusLabel(status)
}

function reviewStatusType(status) {
  return getPaymentVoucherReviewStatusType(status)
}

function reviewResultLabel(result) {
  return getPaymentVoucherReviewResultLabel(result)
}

function riskLevelLabel(level) {
  return getPaymentVoucherReviewRiskLevelLabel(level)
}

function riskLevelType(level) {
  return getPaymentVoucherReviewRiskLevelType(level)
}

function riskItemType(level) {
  return { blocked: 'danger', warning: 'warning', info: 'success' }[level] || 'info'
}

function riskItemLabel(value) {
  return {
    passed: '通过',
    blocked: '阻断',
    warning: '警告',
    info: '提示',
  }[value] || value || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.payment-voucher-review-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
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
.reviewer-demo-note { border: 1px solid #facc15; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #fefce8; color: #854d0e; font-weight: 700; }
.info-grid, .source-chain, .filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }
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
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
