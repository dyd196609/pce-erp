<template>
  <main class="payment-record-review-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.13.2 付款记录复核页面原型</p>
        <h1>{{ detail ? '付款记录复核详情' : '付款记录复核' }}</h1>
        <p>本页只复核人工登记的线下付款结果草稿，不执行真实付款，不连接银行，不生成银行流水，不生成财务凭证，不写总账。</p>
        <p class="finance-current-module-badge">当前操作模块：付款记录复核</p>
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
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payment-record-reviews">付款记录复核<span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payment-voucher-drafts">付款凭证草稿</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款记录复核流程：付款执行草稿 -> 付款记录待复核 -> 付款记录复核 -> 复核通过</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>复核线下付款结果草稿。</span>
          <span><b>本页做什么</b>开始复核、复核通过、复核退回或取消复核。</span>
          <span><b>下一步做什么</b>后续阶段再评审凭证草稿或真实付款闭环范围。</span>
          <span><b>本页不做什么</b>不真实付款、不连接银行、不生成流水、不生成凭证、不写总账。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.paymentRecordReviewNo }}</h2>
              <span>{{ detail.sourcePaymentExecutionNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payment-record-reviews')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payment-execution/${detail.sourcePaymentExecutionId}`)">查看付款执行草稿</el-button>
              <el-button v-if="canStart(detail)" class="app-next-action-button" type="primary" @click="handleStart(detail)">{{ startReviewButtonLabel(detail) }}<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="canPass(detail)" class="app-next-action-button" type="success" @click="handlePass(detail)">复核通过<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="canEnterVoucherDraft(detail)" class="app-next-action-button" type="primary" @click="enterVoucherDraft(detail)">{{ voucherDraftButtonLabel(detail) }}<span class="app-next-action-badge">下一步</span></el-button>
              <el-button v-if="canReject(detail)" type="warning" @click="handleReject(detail)">复核退回</el-button>
              <el-button v-if="canCancel(detail)" type="danger" @click="handleCancel(detail)">取消复核</el-button>
            </div>
          </div>
        </template>
        <div class="boundary-note">当前状态：{{ reviewStatusLabel(detail.reviewStatus) }}。复核通过不等于银行付款成功，不生成凭证，不写总账。</div>
        <div :class="nextStepGuideClass(detail.reviewStatus)">
          <strong>{{ nextStepTitle(detail.reviewStatus) }}</strong>
          <span>{{ nextStepDescription(detail.reviewStatus) }}</span>
        </div>
        <div class="form-grid">
          <label>复核人<input v-model="reviewForm.reviewer" placeholder="默认复核员" /></label>
          <label>复核意见<input v-model="reviewForm.reviewOpinion" placeholder="填写复核意见" /></label>
        </div>
        <div class="reviewer-source-panel">
          <strong>复核人信息</strong>
          <span>当前复核人：{{ reviewerInfo.currentReviewerName || '-' }}</span>
          <span>复核角色：{{ reviewerInfo.currentReviewerRole || '-' }}</span>
          <span>复核来源：{{ reviewerSourceLabel(reviewerInfo.currentReviewerSource) }}</span>
          <span>开始复核时间：{{ reviewerInfo.reviewStartedAt || '-' }}</span>
          <span>最终复核人：{{ reviewerInfo.reviewerName || '-' }}</span>
          <span>复核时间：{{ reviewerInfo.reviewedAt || '-' }}</span>
          <span>复核意见：{{ reviewerInfo.reviewOpinion || '-' }}</span>
        </div>
        <div v-if="showLocalReviewerTip" class="local-reviewer-tip">
          当前复核人为本地演示操作人，后续应接入正式登录用户、岗位权限和审批流。
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
        <template #header><h2>付款记录复核明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="170" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="payableAmount" label="应付金额" width="120" sortable />
          <el-table-column prop="paidAmount" label="已登记金额" width="120" sortable />
          <el-table-column prop="unpaidAmount" label="未复核金额" width="120" sortable />
          <el-table-column prop="executionAmount" label="执行金额" width="120" sortable />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="sourceInventoryTransactionNo" label="库存流水" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="180" fixed="right" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>付款记录复核边界</strong>
        <div class="plain-flow-grid">
          <span><b>复核对象</b>只复核已经提交的线下付款结果草稿。</span>
          <span><b>复核通过</b>只表示线下付款记录草稿已通过人工复核。</span>
          <span><b>不会付款</b>不连接银行、不生成银行流水、不代表银行付款成功。</span>
          <span><b>不会入账</b>不生成财务凭证、不写总账、不做付款核销。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源付款执行草稿区</h2>
              <span>只允许从“付款记录待复核”的付款执行草稿生成复核任务。</span>
            </div>
            <div class="button-row">
              <el-button @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payment-executions')">查看付款执行草稿</el-button>
            </div>
          </div>
        </template>
        <StandardListToolbar
          page-id="payment-record-review"
          table-id="payment-record-review-source"
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
        <section v-show="isAdvancedFilterExpanded" class="advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-record-review-source">
          <label>付款执行草稿号<PceResultFilterSelect v-model="sourceFilters.paymentExecutionNo" :rows="sortedSources" :fields="['paymentExecutionNo']" /></label>
          <label>供应商<PceResultFilterSelect v-model="sourceFilters.supplierName" :rows="sortedSources" :fields="['supplierName']" /></label>
          <label>执行状态<select v-model="sourceFilters.paymentExecutionStatus"><option value="">全部</option><option value="recordReviewPending">付款记录待复核</option></select></label>
          <label>生成状态<select v-model="sourceFilters.generatedState"><option value="">全部</option><option value="ready">可生成复核任务</option><option value="generated">已生成复核任务</option><option value="blocked">暂不可生成</option></select></label>
        </section>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span class="batch-action-title">当前模块操作（生成复核任务）</span>
          <span class="batch-action-tip">批量生成付款记录复核任务：只生成复核任务，不执行真实付款。</span>
          <el-button type="primary" size="small" :disabled="!sourceIds.length" @click="handleBatchCreate">批量生成付款记录复核</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="batchResultType(sourceBatchResult)" @close="sourceBatchResult = null" />
        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-record-review-source" page-id="payment-record-review" table-id="payment-record-review-source" min-width="100%">
        <el-table ref="sourceTableRef" class="pce-baseline-table-shell global-sort-arrow" :data="sortedSources" border stripe height="420" @selection-change="selectedSourceRows = $event" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="paymentExecutionNo" label="付款执行草稿号" min-width="180" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="paymentAccountName" label="付款账户" min-width="160" />
          <el-table-column prop="supplierBankAccountName" label="收款账户" min-width="170" />
          <el-table-column prop="executionAmount" label="执行金额" width="130" sortable="custom" />
          <el-table-column prop="actualPayDate" label="实际线下日期" width="140" sortable="custom" />
          <el-table-column prop="offlinePaymentRecordNo" label="线下记录草稿号" min-width="170" />
          <el-table-column prop="paymentExecutionStatus" label="执行状态" width="150">
            <template #default="{ row }"><el-tag :type="row.paymentExecutionStatus === 'recordReviewPending' ? 'warning' : 'info'">{{ row.paymentExecutionStatus === 'recordReviewPending' ? '付款记录待复核' : row.paymentExecutionStatus }}</el-tag></template>
          </el-table-column>
          <el-table-column label="复核任务" width="170">
            <template #default="{ row }"><el-tag :type="row.paymentRecordReviewGenerated ? 'success' : (row.canGeneratePaymentRecordReview ? 'primary' : 'info')">{{ row.paymentRecordReviewGenerated ? '已生成复核任务' : (row.canGeneratePaymentRecordReview ? '可生成复核任务' : '暂不可生成') }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="disabledReason" label="限制原因" min-width="240" />
          <el-table-column label="操作" fixed="right" :width="sourceActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="row.paymentRecordReviewGenerated" class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-record-review/${row.targetPaymentRecordReviewId}`)">查看付款记录复核</el-button>
                <span v-if="row.paymentRecordReviewGenerated" class="app-current-step-tip">已进入复核阶段</span>
                <el-button v-else class="app-action-button-lg app-next-action-button" size="small" type="primary" :disabled="!row.canGeneratePaymentRecordReview" @click="handleCreate(row)">生成付款记录复核<span class="app-next-action-badge">下一步</span></el-button>
                <el-button class="app-action-button-lg" size="small" @click="router.push(`/finance/payment-execution/${row.id}`)">查看付款执行草稿</el-button>
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
              <h2>付款记录复核列表</h2>
              <span>本轮终点为“付款记录复核通过”，但不代表银行付款成功。</span>
            </div>
            <div class="button-row">
              <el-button @click="quickSearchOpen = !quickSearchOpen">{{ quickSearchOpen ? '收起快速搜索' : '展开快速搜索' }}</el-button>
              <el-button @click="clearSort">清除排序</el-button>
              <el-button @click="resetFilters">重置</el-button>
            </div>
          </div>
        </template>
        <StandardListToolbar
          page-id="payment-record-review"
          table-id="payment-record-review-main"
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

        <section v-show="isAdvancedFilterExpanded" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="payment-record-review-main">
          <label>复核单号<PceResultFilterSelect v-model="filters.paymentRecordReviewNo" :options="filterSuggestions.paymentRecordReviewNo" /></label>
          <label>来源付款执行草稿号<PceResultFilterSelect v-model="filters.sourcePaymentExecutionNo" :options="filterSuggestions.sourcePaymentExecutionNo" /></label>
          <label>供应商<PceResultFilterSelect v-model="filters.supplierName" :options="filterSuggestions.supplierName" /></label>
          <label>付款账户<PceResultFilterSelect v-model="filters.paymentAccount" :options="filterSuggestions.paymentAccount" /></label>
          <label>收款账户<PceResultFilterSelect v-model="filters.supplierBankAccount" :options="filterSuggestions.supplierBankAccount" /></label>
          <label>执行金额下限<input v-model="filters.amountMin" type="number" /></label>
          <label>执行金额上限<input v-model="filters.amountMax" type="number" /></label>
          <label>线下记录草稿号<PceResultFilterSelect v-model="filters.offlinePaymentRecordNo" :options="filterSuggestions.offlinePaymentRecordNo" /></label>
          <label>实际线下日期起<input v-model="filters.actualStart" type="date" /></label>
          <label>实际线下日期止<input v-model="filters.actualEnd" type="date" /></label>
          <label>复核状态<select v-model="filters.reviewStatus"><option value="">全部</option><option v-for="item in reviewStatusOptions" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>复核结果<select v-model="filters.reviewResult"><option value="">全部</option><option value="notReviewed">未复核</option><option value="passed">通过</option><option value="rejected">退回</option></select></label>
          <label>复核人<PceResultFilterSelect v-model="filters.reviewer" :options="filterSuggestions.reviewer" /></label>
          <label>复核角色<PceResultFilterSelect v-model="filters.reviewerRole" :options="filterSuggestions.reviewerRole" /></label>
          <label>是否已通过<select v-model="filters.passed"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已退回<select v-model="filters.rejected"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
          <label>是否已取消<select v-model="filters.cancelled"><option value="">全部</option><option value="yes">是</option><option value="no">否</option></select></label>
        </section>

        <div class="batch-bar">
          <span>已选择 {{ selectedReviewRows.length }} 条</span>
          <span class="sort-help">{{ sortText }}</span>
          <span class="batch-action-title">当前模块操作（只修改复核状态）</span>
          <span class="batch-action-tip">复核通过不等于付款成功，不生成银行流水、凭证或总账。</span>
          <span :class="batchRecommendationClass">{{ batchRecommendationText }}</span>
          <el-button size="small" type="primary" :disabled="!reviewIds.length" @click="handleBatchStart">批量开始复核</el-button>
          <el-button size="small" type="success" :disabled="!reviewIds.length" @click="handleBatchPass">批量复核通过</el-button>
          <el-button size="small" type="warning" :disabled="!reviewIds.length" @click="handleBatchReject">批量复核退回</el-button>
          <el-button size="small" type="danger" :disabled="!reviewIds.length" @click="handleBatchCancel">批量取消复核</el-button>
        </div>
        <BatchResult v-if="reviewBatchResult" :result="reviewBatchResult" :type="batchResultType(reviewBatchResult)" @close="reviewBatchResult = null" />

        <BusinessTableScrollContainer class="pce-baseline-table-shell" acceptance-id="business-table-scroll-payment-record-review-main" page-id="payment-record-review" table-id="payment-record-review-main" min-width="100%">
        <el-table ref="reviewTableRef" class="pce-baseline-table-shell global-sort-arrow" :data="sortedReviews" border stripe height="520" @selection-change="selectedReviewRows = $event" @sort-change="handleSortChange">
          <el-table-column type="selection" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" label-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" label-class-name="pce-fixed-index-column" />
          <el-table-column prop="paymentRecordReviewNo" label="复核单号" min-width="180" sortable="custom" fixed="left" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" label-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourcePaymentExecutionNo" label="来源付款执行草稿" min-width="180" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="executionAmount" label="执行金额" width="130" sortable="custom" />
          <el-table-column prop="offlinePaymentRecordNo" label="线下记录草稿号" min-width="170" />
          <el-table-column prop="actualPayDate" label="实际线下日期" width="140" sortable="custom" />
          <el-table-column prop="reviewStatus" label="复核状态" width="130" sortable="custom">
            <template #default="{ row }"><el-tag :type="reviewStatusType(row.reviewStatus)">{{ reviewStatusLabel(row.reviewStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="reviewerName" label="复核人" width="130" sortable="custom">
            <template #default="{ row }">{{ row.reviewerName || row.reviewer || row.currentReviewerName || '-' }}</template>
          </el-table-column>
          <el-table-column prop="reviewerRole" label="复核角色" width="140">
            <template #default="{ row }">{{ reviewerRoleText(row) || '-' }}</template>
          </el-table-column>
          <el-table-column prop="reviewedAt" label="复核时间" width="170" sortable="custom">
            <template #default="{ row }">{{ row.reviewedAt || row.reviewStartedAt || '-' }}</template>
          </el-table-column>
          <el-table-column prop="realPaymentStatus" label="真实付款状态" width="160">
            <template #default="{ row }">{{ realPaymentStatusLabel(row.realPaymentStatus) }}</template>
          </el-table-column>
          <el-table-column prop="voucherStatus" label="凭证状态" width="130">
            <template #default="{ row }">{{ voucherStatusLabel(row.voucherStatus) }}</template>
          </el-table-column>
          <el-table-column label="付款凭证草稿" width="170">
            <template #default="{ row }"><el-tag :type="voucherDraftStateType(row)">{{ voucherDraftStateLabel(row) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="reviewActionColumnWidth" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column" label-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button class="app-action-button-sm" size="small" @click="router.push(`/finance/payment-record-review/${row.id}`)">查看详情</el-button>
                <el-button v-if="canStart(row)" class="app-action-button-md app-next-action-button" size="small" type="primary" @click="handleStart(row)">{{ startReviewButtonLabel(row) }}<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="canPass(row)" class="app-action-button-md app-next-action-button" size="small" type="success" @click="handlePass(row)">复核通过<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="canEnterVoucherDraft(row)" class="app-action-button-lg app-next-action-button" size="small" type="primary" @click="enterVoucherDraft(row)">{{ voucherDraftButtonLabel(row) }}<span class="app-next-action-badge">下一步</span></el-button>
                <el-button v-if="canReject(row)" class="app-action-button-md" size="small" type="warning" @click="handleReject(row)">复核退回</el-button>
                <el-button v-if="canCancel(row)" class="app-action-button-md" size="small" type="danger" @click="handleCancel(row)">取消复核</el-button>
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
  isPaymentVoucherDraftGenerated,
} from '../finance/paymentVoucherDraftStore.js'
import {
  batchCancelPaymentRecordReviews,
  batchCreatePaymentRecordReviewsFromPaymentExecutions,
  batchPassPaymentRecordReviews,
  batchRejectPaymentRecordReviews,
  batchStartPaymentRecordReviews,
  cancelPaymentRecordReview,
  createPaymentRecordReviewFromPaymentExecution,
  getPaymentRecordLedgerStatusLabel,
  getPaymentRecordRealPaymentStatusLabel,
  getPaymentRecordReviewById,
  getPaymentRecordReviewResultLabel,
  getPaymentRecordReviewSourcesFromPaymentExecutions,
  getPaymentRecordReviewStatusLabel,
  getPaymentRecordReviewStatusType,
  getPaymentRecordReviewerSourceLabel,
  getPaymentRecordVoucherStatusLabel,
  listPaymentRecordReviews,
  passPaymentRecordReview,
  rejectPaymentRecordReview,
  resolveCurrentReviewer,
  startPaymentRecordReview,
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
      h('span', `失败 / 跳过：${props.result.failedCount} 条`),
      props.result.reviewerName ? h('span', `复核人：${props.result.reviewerName}`) : null,
      props.result.reviewerSourceLabel ? h('span', `复核来源：${props.result.reviewerSourceLabel}`) : null,
      props.result.reviewerSourceRemark ? h('span', `说明：${props.result.reviewerSourceRemark}`) : null,
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      h('span', `下一步建议：${props.result.nextSuggestion || '按当前复核状态处理下一步。'}`),
      h('span', '边界说明：本批量结果不代表真实付款完成，不生成银行流水、财务凭证或总账记录。'),
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
const defaultReviewer = resolveCurrentReviewer({ silent: true })
const reviewForm = reactive({ reviewer: defaultReviewer.reviewerName, reviewOpinion: '' })
const filters = reactive(defaultFilters())
const sourceFilters = reactive({
  paymentExecutionNo: '',
  supplierName: '',
  paymentExecutionStatus: '',
  generatedState: '',
})

const detail = computed(() => route.params.id ? getPaymentRecordReviewById(route.params.id) : null)
const reviewerInfo = computed(() => {
  const row = detail.value || {}
  const current = resolveCurrentReviewer({ reviewer: reviewForm.reviewer, silent: true })
  return {
    currentReviewerName: row.currentReviewerName || current.reviewerName,
    currentReviewerRole: row.currentReviewerRole || row.reviewRole || row.roleName || current.reviewerRole,
    currentReviewerSource: row.currentReviewerSource || current.reviewerSource,
    reviewerName: row.reviewerName || row.reviewer || current.reviewerName,
    reviewerRole: row.reviewerRole || row.reviewRole || row.roleName || current.reviewerRole,
    reviewerSource: row.reviewerSource || current.reviewerSource,
    reviewedAt: row.reviewedAt || '',
    reviewStartedAt: row.reviewStartedAt || '',
    reviewOpinion: row.reviewOpinion || '',
  }
})
const showLocalReviewerTip = computed(() => reviewerInfo.value.reviewerSource === 'localDemo' || reviewerInfo.value.currentReviewerSource === 'localDemo')
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const reviewIds = computed(() => selectedReviewRows.value.map((row) => row.id).filter(Boolean))
const filterSuggestions = computed(() => ({
  paymentRecordReviewNo: uniqueValues(reviews.value.map((row) => row.paymentRecordReviewNo)),
  sourcePaymentExecutionNo: uniqueValues(reviews.value.map((row) => row.sourcePaymentExecutionNo)),
  supplierName: uniqueValues(reviews.value.map((row) => row.supplierName)),
  paymentAccount: uniqueValues(reviews.value.map(paymentAccountText)),
  supplierBankAccount: uniqueValues(reviews.value.map(supplierBankAccountText)),
  offlinePaymentRecordNo: uniqueValues(reviews.value.map((row) => row.offlinePaymentRecordNo)),
  reviewer: uniqueValues(reviews.value.flatMap((row) => [row.reviewerName, row.reviewer, row.currentReviewerName])),
  reviewerRole: reviewerRoleSuggestions(reviews.value),
}))
const filteredSources = computed(() => {
  const rows = route.query.sourcePaymentExecutionId
    ? sources.value.filter((row) => String(row.id) === String(route.query.sourcePaymentExecutionId))
    : sources.value
  return rows.filter((row) => {
    const haystack = [
      row.paymentExecutionNo,
      row.supplierName,
      row.paymentAccountName,
      row.supplierBankAccountName,
      row.offlinePaymentRecordNo,
      row.paymentExecutionStatus,
    ].join(' ').toLowerCase()
    const keywordOk = !sourceQuickSearch.value || haystack.includes(sourceQuickSearch.value.trim().toLowerCase())
    const generatedOk = !sourceFilters.generatedState
      || (sourceFilters.generatedState === 'generated' && row.paymentRecordReviewGenerated)
      || (sourceFilters.generatedState === 'ready' && row.canGeneratePaymentRecordReview && !row.paymentRecordReviewGenerated)
      || (sourceFilters.generatedState === 'blocked' && !row.canGeneratePaymentRecordReview && !row.paymentRecordReviewGenerated)
    return keywordOk
      && includesText(row.paymentExecutionNo, sourceFilters.paymentExecutionNo)
      && includesText(row.supplierName, sourceFilters.supplierName)
      && (!sourceFilters.paymentExecutionStatus || row.paymentExecutionStatus === sourceFilters.paymentExecutionStatus)
      && generatedOk
  })
})
const filteredReviews = computed(() => {
  return reviews.value.filter((row) => {
    const haystack = [
      row.paymentRecordReviewNo,
      row.sourcePaymentExecutionNo,
      row.supplierName,
      row.paymentAccount,
      row.paymentAccountName,
      row.supplierBankAccount,
      row.supplierBankAccountName,
      row.offlinePaymentRecordNo,
      row.reviewer,
      row.reviewerName,
      row.currentReviewerName,
      reviewerRoleText(row),
      getPaymentRecordReviewerSourceLabel(row.reviewerSource || row.currentReviewerSource),
      reviewStatusLabel(row.reviewStatus),
    ].join(' ').toLowerCase()
    const amount = Number(row.executionAmount || 0)
    return (!quickSearch.value || haystack.includes(quickSearch.value.trim().toLowerCase()))
      && includesText(row.paymentRecordReviewNo, filters.paymentRecordReviewNo)
      && includesText(row.sourcePaymentExecutionNo, filters.sourcePaymentExecutionNo)
      && includesText(row.supplierName, filters.supplierName)
      && includesText(paymentAccountText(row), filters.paymentAccount)
      && includesText(supplierBankAccountText(row), filters.supplierBankAccount)
      && (!filters.amountMin || amount >= Number(filters.amountMin))
      && (!filters.amountMax || amount <= Number(filters.amountMax))
      && includesText(row.offlinePaymentRecordNo, filters.offlinePaymentRecordNo)
      && inDateRange(row.actualPayDate, filters.actualStart, filters.actualEnd)
      && (!filters.reviewStatus || row.reviewStatus === filters.reviewStatus)
      && (!filters.reviewResult || row.reviewResult === filters.reviewResult)
      && includesText(`${row.reviewer} ${row.reviewerName} ${row.currentReviewerName} ${row.reviewerRole} ${row.currentReviewerRole}`, filters.reviewer)
      && includesText(reviewerRoleText(row), filters.reviewerRole)
      && boolStatus(row.reviewStatus === 'passed', filters.passed)
      && boolStatus(row.reviewStatus === 'rejected', filters.rejected)
      && boolStatus(row.reviewStatus === 'cancelled', filters.cancelled)
  })
})
const sortColumns = [
  { key: 'paymentRecordReviewNo', sortType: 'string' },
  { key: 'sourcePaymentExecutionNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'executionAmount', sortType: 'amount' },
  { key: 'actualPayDate', sortType: 'date' },
  { key: 'reviewStatus', sortType: 'status' },
  { key: 'reviewerName', sortType: 'string' },
  { key: 'reviewedAt', sortType: 'date' },
]
const sourceSortColumns = [
  { key: 'paymentExecutionNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'executionAmount', sortType: 'amount' },
  { key: 'actualPayDate', sortType: 'date' },
  { key: 'paymentExecutionStatus', sortType: 'status' },
]
const sortedSources = computed(() => sortRecords(filteredSources.value, sourceSortState.value, sourceSortColumns))
const sortedReviews = computed(() => sortRecords(filteredReviews.value, sortState.value, sortColumns))
const sourceSortText = computed(() => sourceSortState.value.key ? `当前排序：${sourceSortState.value.key} / ${sourceSortState.value.direction === 'desc' ? '降序' : '升序'}` : '默认业务顺序')
const activeFilterCount = computed(() => Object.values(filters).filter((value) => String(value || '').trim()).length + (quickSearch.value.trim() ? 1 : 0))
const sourceActiveFilterCount = computed(() => Object.values(sourceFilters).filter((value) => String(value || '').trim()).length + (sourceQuickSearch.value.trim() ? 1 : 0))
const sortText = computed(() => sortState.value.key ? `当前排序：${sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}` : '排序：点击表头可排序，点击清除排序恢复默认顺序。')
const sourceActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedSources.value, sourceActions, ['生成付款记录复核', '查看付款记录复核', '查看付款执行草稿']))
const reviewActionColumnWidth = computed(() => getActionColumnWidthForRows(sortedReviews.value, reviewActions, ['查看详情', '开始复核', '重新复核', '复核通过', '生成付款凭证草稿', '查看付款凭证草稿', '复核退回', '取消复核']))
const batchRecommendationText = computed(() => {
  if (!selectedReviewRows.value.length) return '推荐下一步：请先选择同一状态的复核任务。'
  const statuses = [...new Set(selectedReviewRows.value.map((row) => row.reviewStatus))]
  if (statuses.length > 1) return '所选记录包含多个复核状态，请按状态分别批量处理。'
  const action = nextActionConfig(statuses[0])
  if (action.terminal) return '所选记录已到本轮终点，无需继续推进。'
  return `推荐下一步：批量${action.label}`
})
const batchRecommendationClass = computed(() => {
  if (!selectedReviewRows.value.length) return 'app-current-step-tip'
  const statuses = [...new Set(selectedReviewRows.value.map((row) => row.reviewStatus))]
  if (statuses.length > 1 || nextActionConfig(statuses[0]).terminal) return 'app-terminal-step-tip'
  return 'app-current-step-tip'
})
const reviewStatusOptions = [
  { value: 'pending', label: '待复核' },
  { value: 'reviewing', label: '复核中' },
  { value: 'passed', label: '复核通过' },
  { value: 'rejected', label: '复核退回' },
  { value: 'cancelled', label: '取消' },
]
const detailFields = computed(() => detail.value ? [
  { label: '复核单号', value: detail.value.paymentRecordReviewNo },
  { label: '来源付款执行草稿', value: detail.value.sourcePaymentExecutionNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '付款账户', value: detail.value.paymentAccountName || detail.value.paymentAccount || '-' },
  { label: '付款银行', value: detail.value.paymentBankName || '-' },
  { label: '收款开户行', value: detail.value.supplierBankName || '-' },
  { label: '收款账户', value: detail.value.supplierBankAccountName || detail.value.supplierBankAccount || '-' },
  { label: '执行金额', value: amountText(detail.value.executionAmount) },
  { label: '实际线下日期', value: detail.value.actualPayDate || '-' },
  { label: '线下记录草稿号', value: detail.value.offlinePaymentRecordNo || '-' },
  { label: '线下结果说明', value: detail.value.offlinePaymentRemark || '-' },
  { label: '复核状态', value: reviewStatusLabel(detail.value.reviewStatus) },
  { label: '复核结果', value: reviewResultLabel(detail.value.reviewResult) },
  { label: '复核意见', value: detail.value.reviewOpinion || '-' },
  { label: '复核人', value: detail.value.reviewer || '-' },
  { label: '复核时间', value: detail.value.reviewedAt || '-' },
  { label: '真实付款状态', value: realPaymentStatusLabel(detail.value.realPaymentStatus) },
  { label: '凭证状态', value: voucherStatusLabel(detail.value.voucherStatus) },
  { label: '付款凭证草稿', value: voucherDraftStateLabel(detail.value) },
  { label: '总账状态', value: ledgerStatusLabel(detail.value.ledgerStatus) },
] : [])
const sourceChain = computed(() => detail.value ? [
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
    paymentRecordReviewNo: '',
    sourcePaymentExecutionNo: '',
    supplierName: '',
    paymentAccount: '',
    supplierBankAccount: '',
    amountMin: '',
    amountMax: '',
    offlinePaymentRecordNo: '',
    actualStart: '',
    actualEnd: '',
    reviewStatus: '',
    reviewResult: '',
    reviewer: '',
    reviewerRole: '',
    passed: '',
    rejected: '',
    cancelled: '',
  }
}

function refresh() {
  sources.value = getPaymentRecordReviewSourcesFromPaymentExecutions()
  reviews.value = listPaymentRecordReviews()
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

function boolStatus(value, flag) {
  if (!flag) return true
  return flag === 'yes' ? Boolean(value) : !value
}

function amountText(value) {
  return Number(value || 0).toFixed(2)
}

function compactText(parts = []) {
  return parts.map((part) => String(part || '').trim()).filter(Boolean).join(' / ')
}

function uniqueValues(values = []) {
  return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
}

function reviewerRoleText(row = {}) {
  const baseRoles = compactText([row.reviewerRole, row.currentReviewerRole, row.reviewRole, row.roleName])
  if (baseRoles) return baseRoles
  if (row.reviewerSource === 'localDemo' || row.currentReviewerSource === 'localDemo') return '付款记录复核 / 财务复核人 / 当前复核人'
  if (row.reviewer || row.reviewerName || row.currentReviewerName) return '付款记录复核'
  return ''
}

function reviewerRoleSuggestions(rows = []) {
  const roles = uniqueValues(rows.flatMap((row) => reviewerRoleText(row).split('/')))
  if (!roles.length && rows.length) return ['付款记录复核', '财务复核人', '当前复核人']
  return roles
}

function paymentAccountText(row = {}) {
  return compactText([row.paymentAccountName, row.paymentAccount, row.paymentBankName])
}

function supplierBankAccountText(row = {}) {
  return compactText([row.supplierBankAccountName, row.supplierBankAccount, row.supplierBankName])
}

function nextActionConfig(status) {
  return {
    pending: {
      label: '开始复核',
      description: '当前应开始复核线下付款记录草稿；本操作不执行真实付款。',
    },
    reviewing: {
      label: '复核通过 / 复核退回',
      description: '当前应根据线下记录核对结果选择通过或退回；通过也不代表银行付款成功。',
    },
    rejected: {
      label: '重新复核',
      description: '当前应补充或核对信息后重新复核。',
    },
    passed: {
      label: '',
      description: '当前阶段已到本轮终点：付款记录复核通过。',
      terminal: true,
    },
    cancelled: {
      label: '',
      description: '该复核任务已取消，只能查看详情。',
      terminal: true,
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
  const outcome = createPaymentRecordReviewFromPaymentExecution(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  router.push(`/finance/payment-record-review/${outcome.review.id}`)
}

function handleBatchCreate() { showSourceBatch(batchCreatePaymentRecordReviewsFromPaymentExecutions(sourceIds.value)) }
function handleBatchStart() { showReviewBatch(batchStartPaymentRecordReviews(reviewIds.value)) }
function handleBatchPass() { showReviewBatch(batchPassPaymentRecordReviews(reviewIds.value)) }
function handleBatchReject() { showReviewBatch(batchRejectPaymentRecordReviews(reviewIds.value)) }
function handleBatchCancel() { showReviewBatch(batchCancelPaymentRecordReviews(reviewIds.value)) }
function handleStart(row) { handleOutcome(startPaymentRecordReview(row.id, { ...reviewForm }), '已开始付款记录复核；仍未执行真实付款。') }
function handlePass(row) { handleOutcome(passPaymentRecordReview(row.id, { ...reviewForm }), '付款记录复核通过；不是银行付款成功，不生成凭证。') }
function handleReject(row) { handleOutcome(rejectPaymentRecordReview(row.id, { ...reviewForm }), '付款记录复核已退回。') }
function handleCancel(row) { handleOutcome(cancelPaymentRecordReview(row.id, { ...reviewForm }), '付款记录复核已取消。') }

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
    paymentExecutionNo: '',
    supplierName: '',
    paymentExecutionStatus: '',
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
  downloadCsv('payment-record-review-sources.csv', [
    { label: '付款执行草稿号', value: 'paymentExecutionNo' },
    { label: '供应商', value: 'supplierName' },
    { label: '付款账户', value: 'paymentAccountName' },
    { label: '收款账户', value: 'supplierBankAccountName' },
    { label: '执行金额', value: 'executionAmount' },
    { label: '实际线下日期', value: 'actualPayDate' },
    { label: '线下记录草稿号', value: 'offlinePaymentRecordNo' },
    { label: '执行状态', value: 'paymentExecutionStatus' },
    { label: '限制原因', value: 'disabledReason' },
  ], sortedSources.value)
}

function exportReviewRows() {
  downloadCsv('payment-record-reviews.csv', [
    { label: '复核单号', value: 'paymentRecordReviewNo' },
    { label: '来源付款执行草稿', value: 'sourcePaymentExecutionNo' },
    { label: '供应商', value: 'supplierName' },
    { label: '执行金额', value: 'executionAmount' },
    { label: '线下记录草稿号', value: 'offlinePaymentRecordNo' },
    { label: '实际线下日期', value: 'actualPayDate' },
    { label: '复核状态', value: (row) => reviewStatusLabel(row.reviewStatus) },
    { label: '复核人', value: (row) => row.reviewerName || row.reviewer || row.currentReviewerName || '-' },
    { label: '真实付款状态', value: (row) => realPaymentStatusLabel(row.realPaymentStatus) },
    { label: '凭证状态', value: (row) => voucherStatusLabel(row.voucherStatus) },
  ], sortedReviews.value)
}

function sourceActions(row = {}) {
  return [
    { label: '查看付款记录复核', visible: row.paymentRecordReviewGenerated },
    { label: '生成付款记录复核', visible: !row.paymentRecordReviewGenerated },
    '查看付款执行草稿',
  ]
}

function reviewActions(row = {}) {
  return [
    '查看详情',
    { label: startReviewButtonLabel(row), visible: canStart(row) },
    { label: '复核通过', visible: canPass(row) },
    { label: voucherDraftButtonLabel(row), visible: canEnterVoucherDraft(row) },
    { label: '复核退回', visible: canReject(row) },
    { label: '取消复核', visible: canCancel(row) },
  ]
}

function startReviewButtonLabel(row = {}) {
  return row.reviewStatus === 'rejected' ? '重新复核' : '开始复核'
}

function canStart(row = {}) {
  return ['pending', 'rejected'].includes(row.reviewStatus)
}

function canPass(row = {}) {
  return row.reviewStatus === 'reviewing'
}

function canReject(row = {}) {
  return row.reviewStatus === 'reviewing'
}

function canCancel(row = {}) {
  return ['pending', 'reviewing', 'rejected'].includes(row.reviewStatus)
}

function canEnterVoucherDraft(row = {}) {
  return row.reviewStatus === 'passed' && row.reviewResult === 'passed'
}

function voucherDraftTarget(row = {}) {
  const target = isPaymentVoucherDraftGenerated(row.id)
  if (target) return target
  if (
    row.paymentVoucherDraftGenerated
    && row.targetPaymentVoucherDraftId
    && ['draft', 'readyForReview', 'reviewed'].includes(row.paymentVoucherDraftStatus)
  ) {
    return {
      id: row.targetPaymentVoucherDraftId,
      voucherDraftNo: row.targetPaymentVoucherDraftNo,
      voucherStatus: row.paymentVoucherDraftStatus,
      reviewStatus: row.voucherReviewStatus,
    }
  }
  return null
}

function voucherDraftButtonLabel(row = {}) {
  return voucherDraftTarget(row) ? '查看付款凭证草稿' : '生成付款凭证草稿'
}

function enterVoucherDraft(row = {}) {
  const target = voucherDraftTarget(row)
  if (target?.id) return router.push(`/finance/payment-voucher-draft/${target.id}`)
  return router.push(`/finance/payment-voucher-drafts?sourcePaymentRecordReviewId=${row.id}`)
}

function voucherDraftStateLabel(row = {}) {
  const target = voucherDraftTarget(row)
  const status = target?.voucherStatus || row.paymentVoucherDraftStatus
  if (status === 'readyForReview') return '凭证草稿待复核'
  if (status === 'draft') return '已生成付款凭证草稿'
  if (status === 'reviewed') return '凭证草稿已复核'
  if (status === 'cancelled') return '凭证草稿已取消'
  return '未生成付款凭证草稿'
}

function voucherDraftStateType(row = {}) {
  const target = voucherDraftTarget(row)
  const status = target?.voucherStatus || row.paymentVoucherDraftStatus
  return {
    draft: 'primary',
    readyForReview: 'warning',
    reviewed: 'success',
    cancelled: 'info',
  }[status] || 'info'
}

function reviewStatusLabel(status) {
  return getPaymentRecordReviewStatusLabel(status)
}

function reviewStatusType(status) {
  return getPaymentRecordReviewStatusType(status)
}

function reviewResultLabel(result) {
  return getPaymentRecordReviewResultLabel(result)
}

function realPaymentStatusLabel(status) {
  return getPaymentRecordRealPaymentStatusLabel(status)
}

function voucherStatusLabel(status) {
  return getPaymentRecordVoucherStatusLabel(status)
}

function ledgerStatusLabel(status) {
  return getPaymentRecordLedgerStatusLabel(status)
}

function reviewerSourceLabel(source) {
  return getPaymentRecordReviewerSourceLabel(source)
}

watch(() => route.fullPath, () => {
  refresh()
  if (detail.value) {
    reviewForm.reviewer = detail.value.reviewerName || detail.value.reviewer || detail.value.currentReviewerName || defaultReviewer.reviewerName
    reviewForm.reviewOpinion = detail.value.reviewOpinion || ''
  }
}, { immediate: true })
</script>

<style scoped>
.payment-record-review-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
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
.form-grid { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; margin: 0 0 12px; background: #fff; }
.reviewer-source-panel { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; margin: 0 0 10px; background: #eff6ff; color: #1e3a8a; }
.reviewer-source-panel strong { grid-column: 1 / -1; color: #172033; }
.local-reviewer-tip { border: 1px solid #fbbf24; border-radius: 8px; padding: 10px 12px; margin: 0 0 12px; background: #fffbeb; color: #92400e; font-weight: 800; }
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
