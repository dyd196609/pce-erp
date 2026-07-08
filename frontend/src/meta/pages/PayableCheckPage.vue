<template>
  <main class="finance-flow-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.4 采购应付核对</p>
        <h1>{{ detail ? '应付核对详情' : '采购应付核对' }}</h1>
        <p>本页根据采购应付预备生成应付核对，只核对数量、单价、金额和来源链，不生成正式应付，不生成财务凭证。</p>
        <p class="finance-current-module-badge">当前操作模块：应付核对</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/finance/payable-prepares">应付预备</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payable-checks">应付核对 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/invoice-prepares">发票预备</router-link>
        <router-link class="finance-nav-button" to="/finance/ap-drafts">应付账款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-drafts">供应商付款草稿</router-link>
        <router-link class="finance-nav-button" to="/finance/payment-prepares">正式付款单预备</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="detail" class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 2 步：核对数量和金额</span>
          <span><b>本页要做</b>核对供应商、采购订单、收货单、检验单、物料、数量、单价和金额是否一致。</span>
          <span><b>下一步</b>核对通过后，生成发票预备，准备供应商开票或登记已收到发票。</span>
          <span><b>本页不会做</b>不生成正式应付账款、付款单或财务凭证。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>无差异：核对通过 -> 生成发票预备。存在差异：处理差异 -> 重新核对 -> 核对通过 -> 生成发票预备。</span>
        <el-button type="primary" @click="router.push('/finance/invoice-prepares')">进入发票预备</el-button>
      </section>
      <section class="difference-guide">
        <strong>应付核对差异处理流程：发现差异 -> 填写差异原因 -> 选择处理方式 -> 保存差异处理 -> 重新核对 -> 核对通过 -> 生成发票预备</strong>
        <span>如果数量、单价、金额或来源单据不一致，需要先处理差异。差异未处理前，不能生成发票预备；差异处理完成后，必须重新核对，核对通过后才能生成发票预备。</span>
      </section>
      <section class="flow-guide">
        <strong>作业流程：应付预备 -> 应付核对 -> 发票预备 -> 后续正式应付</strong>
        <span>本页只核对应付预备的供应商、数量、单价、金额和来源链；核对金额为本次确认的含税金额，用于后续发票预备。本页不生成正式应付、付款或财务凭证。</span>
      </section>
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.payableCheckNo }}</h2>
              <span>{{ detail.sourcePayablePrepareNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payable-checks')">返回列表</el-button>
              <el-button @click="router.push(`/finance/payable-prepare/${detail.sourcePayablePrepareId}`)">查看应付预备</el-button>
              <el-button v-if="getPayableCheckActions(detail).canStartChecking" type="warning" @click="markChecking(detail)">开始核对</el-button>
              <el-button v-if="getPayableCheckActions(detail).canMarkChecked" type="success" @click="markChecked(detail)">核对通过</el-button>
              <el-button v-if="getPayableCheckActions(detail).canMarkDifference" type="danger" @click="markDifference(detail)">标记差异</el-button>
              <el-button v-if="getPayableCheckActions(detail).canStartDifference" type="danger" @click="startDifference(detail)">处理差异</el-button>
              <el-button v-if="getPayableCheckActions(detail).canSaveDifference" type="primary" @click="saveDifference(detail)">保存差异处理</el-button>
              <el-button v-if="getPayableCheckActions(detail).canCancelDifference" @click="cancelDifference(detail)">取消处理</el-button>
              <el-button v-if="getPayableCheckActions(detail).canRecheck" type="warning" @click="recheckDifference(detail)">重新核对</el-button>
              <el-button v-if="getPayableCheckActions(detail).canViewDifference" @click="scrollToDifferenceForm">查看差异处理</el-button>
              <el-button v-if="getPayableCheckActions(detail).canCreateInvoice" type="primary" @click="createInvoice(detail)">生成发票预备</el-button>
              <el-button v-if="getPayableCheckActions(detail).canViewInvoice" type="success" @click="viewInvoicePrepare(detail)">查看发票预备</el-button>
              <el-button v-if="!['invoicePrepared', 'cancelled', 'closed'].includes(getPayableCheckNormalizedState(detail).checkStatus)" type="danger" @click="cancelCheck(detail)">取消</el-button>
            </div>
          </div>
        </template>
        <el-alert title="采购应付核对流程：应付预备 -> 应付核对 -> 发票预备 -> 后续正式应付。本页不生成正式应付或财务凭证。" type="info" show-icon :closable="false" />
        <section class="amount-guide">
          <strong>金额口径</strong>
          <span>核对金额 checkedAmount = 核对数量 * 核对单价，为含税金额；核对通过后用于发票预备。未税金额不在本页混用，后续在发票预备按税率拆分。</span>
        </section>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never" v-if="getPayableCheckNormalizedState(detail).checkStatus === 'difference' || getPayableCheckNormalizedState(detail).differenceStatus !== 'none'">
        <template #header>
          <div class="card-header">
            <div>
              <h2>差异处理区</h2>
              <span>请说明差异来源，并选择处理方式。保存后需要重新核对，核对通过后才能生成发票预备。</span>
            </div>
            <el-tag :type="differenceStatusType(getPayableCheckNormalizedState(detail).differenceStatus)">{{ differenceStatusLabel(getPayableCheckNormalizedState(detail).differenceStatus) }}</el-tag>
          </div>
        </template>
        <section class="difference-form">
          <p class="difference-hint wide-field">{{ differenceStatusHint(detail) }}</p>
          <label>
            <span>差异类型</span>
            <el-select v-model="differenceForm.differenceType" placeholder="请选择差异类型" :disabled="!getPayableCheckActions(detail).canEditDifference">
              <el-option v-for="item in differenceTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </label>
          <label>
            <span>差异原因</span>
            <el-input v-model="differenceForm.differenceReason" type="textarea" :rows="3" placeholder="请填写数量、单价、金额或来源单据不一致的原因" :disabled="!getPayableCheckActions(detail).canEditDifference" />
          </label>
          <label>
            <span>处理方式</span>
            <el-select v-model="differenceForm.differenceResolution" placeholder="请选择处理方式" :disabled="!getPayableCheckActions(detail).canEditDifference">
              <el-option v-for="item in differenceResolutionOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </label>
          <label>
            <span>处理人</span>
            <el-input v-model="differenceForm.differenceHandlerName" placeholder="处理人" :disabled="!getPayableCheckActions(detail).canEditDifference" />
          </label>
          <label>
            <span>处理时间</span>
            <el-input :model-value="detail.differenceHandledAt || '-'" disabled />
          </label>
          <label class="wide-field">
            <span>处理备注</span>
            <el-input v-model="differenceForm.remark" type="textarea" :rows="3" placeholder="本轮只记录处理说明，不生成调整单，不自动退回采购、仓库或供应商流程。" :disabled="!getPayableCheckActions(detail).canEditDifference" />
          </label>
          <div class="difference-actions wide-field">
            <el-button v-if="getPayableCheckActions(detail).canStartDifference" type="danger" @click="startDifference(detail)">处理差异</el-button>
            <el-button v-if="getPayableCheckActions(detail).canSaveDifference" type="primary" @click="saveDifference(detail)">保存差异处理</el-button>
            <el-button v-if="getPayableCheckActions(detail).canCancelDifference" @click="cancelDifference(detail)">取消处理</el-button>
            <el-button v-if="getPayableCheckActions(detail).canRecheck" type="warning" @click="recheckDifference(detail)">重新核对</el-button>
          </div>
        </section>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>应付核对明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="520">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="90" />
          <el-table-column prop="batchNo" label="批号" min-width="130" />
          <el-table-column prop="payableQty" label="应付数量" width="110" />
          <el-table-column prop="payablePrice" label="应付单价" width="110" />
          <el-table-column prop="payableAmount" label="应付金额" width="120" />
          <el-table-column prop="checkedQty" label="核对数量" width="110" />
          <el-table-column prop="checkedPrice" label="核对单价" width="110" />
          <el-table-column prop="checkedAmount" label="核对金额" width="120" />
          <el-table-column prop="quantityDifference" label="数量差异" width="110" />
          <el-table-column prop="amountDifference" label="金额差异" width="110" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="differenceReason" label="差异原因" min-width="180" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 2 步：核对数量和金额</span>
          <span><b>本页要做</b>核对供应商、采购订单、收货单、检验单、物料、数量、单价和金额是否一致。</span>
          <span><b>下一步</b>核对通过后，进入“发票预备”。</span>
          <span><b>本页不会做</b>不生成正式应付账款、付款单或财务凭证。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>无差异：核对通过 -> 生成发票预备。存在差异：处理差异 -> 重新核对 -> 核对通过 -> 生成发票预备。</span>
        <el-button type="primary" @click="router.push('/finance/invoice-prepares')">进入发票预备</el-button>
      </section>
      <section class="difference-guide">
        <strong>应付核对差异处理流程：发现差异 -> 填写差异原因 -> 选择处理方式 -> 保存差异处理 -> 重新核对 -> 核对通过 -> 生成发票预备</strong>
        <span>差异未处理前，不能生成发票预备；差异处理完成后显示“重新核对”，重新核对通过后才显示“生成发票预备”。</span>
      </section>
      <section class="flow-guide">
        <strong>作业流程：应付预备 -> 应付核对 -> 发票预备 -> 后续正式应付</strong>
        <span>本页只做应付预备核对，不生成正式应付、付款或财务凭证；核对通过后再生成发票预备。</span>
      </section>
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>应付核对来源</h2>
              <span>来源为 checked / payableReady 状态的采购应付预备。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/finance/payable-prepares')">查看应付预备</el-button>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span>可生成 {{ sourceBatchCounts.create }} 条</span>
          <span>跳过 {{ selectedSourceRows.length - sourceBatchCounts.create }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ sourceSortText }}</span>
          <el-button size="small" @click="resetSourceSorting">清除排序</el-button>
          <el-button size="small" @click="clearSourceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreateChecks">批量生成应付核对</el-button>
        </div>
        <BatchResult v-if="sourceBatchResult" :result="sourceBatchResult" :type="sourceBatchResultType" @close="sourceBatchResult = null" />
        <el-table ref="sourceTableRef" :data="sortedSourceRows" border stripe height="460" @selection-change="handleSourceSelectionChange" @sort-change="handleSourceSortChange">
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">{{ row.sourceRejectReason || '可生成应付核对' }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="payablePrepareNo" label="应付预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="totalPayableQty" label="应付预备数量" width="130" sortable="custom" />
          <el-table-column prop="totalPayableAmount" label="应付预备金额" width="130" sortable="custom" />
          <el-table-column prop="payableStatus" label="状态" width="120" sortable="custom">
            <template #default="{ row }"><el-tag :type="prepareStatusType(row.payableStatus)">{{ prepareStatusLabel(row.payableStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="是否已生成" width="120">
            <template #default="{ row }"><el-tag :type="row.payableCheckGenerated ? 'success' : 'info'">{{ row.payableCheckGeneratedText }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看应付预备', '生成核对'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-md" @click="router.push(`/finance/payable-prepare/${row.id}`)">查看应付预备</el-button>
                <el-button v-if="!row.payableCheckGenerated" size="small" class="app-action-button-sm" type="success" :disabled="!row.canCreatePayableCheck" @click="createCheck(row)">生成核对</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>应付核对列表</h2></template>
        <div class="batch-bar">
          <span>已选择 {{ selectedCheckRows.length }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ checkSortText }}</span>
          <el-button size="small" @click="resetCheckSorting">清除排序</el-button>
          <el-button size="small" @click="clearCheckSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="warning" :disabled="!selectedCheckRows.length" @click="runBatchChecking">批量开始核对</el-button>
          <el-button size="small" type="success" :disabled="!selectedCheckRows.length" @click="runBatchChecked">批量核对通过</el-button>
          <el-button size="small" type="danger" :disabled="!selectedCheckRows.length" @click="runBatchDifference">批量标记差异</el-button>
          <el-button size="small" type="success" :disabled="!selectedCheckRows.length" @click="runBatchReady">批量准备生成发票预备</el-button>
          <span class="sort-help">批量核对通过和批量生成发票预备会跳过未处理差异记录。</span>
        </div>
        <BatchResult v-if="checkBatchResult" :result="checkBatchResult" :type="checkBatchResultType" @close="checkBatchResult = null" />
        <el-table ref="checkTableRef" :data="sortedCheckRows" border stripe height="520" @selection-change="handleCheckSelectionChange" @sort-change="handleCheckSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="expand" width="44" fixed="left">
            <template #default="{ row }">差异原因：{{ row.differenceReason || '-' }}；来源：{{ row.sourcePayablePrepareNo }}</template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="payableCheckNo" label="应付核对单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePayablePrepareNo" label="来源应付预备" min-width="170" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="收货单" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="检验单" min-width="150" />
          <el-table-column prop="totalCheckedQty" label="核对数量" width="110" sortable="custom" />
          <el-table-column prop="totalCheckedAmount" label="核对金额" width="120" sortable="custom" />
          <el-table-column prop="amountDifference" label="差异金额" width="110" sortable="custom" />
          <el-table-column prop="checkStatus" label="状态" width="140" sortable="custom">
            <template #default="{ row }"><el-tag :type="checkStatusType(getPayableCheckNormalizedState(row).checkStatus)">{{ checkStatusLabel(getPayableCheckNormalizedState(row).checkStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="differenceStatus" label="差异处理" width="120" sortable="custom">
            <template #default="{ row }"><el-tag :type="differenceStatusType(getPayableCheckNormalizedState(row).differenceStatus)">{{ differenceStatusLabel(getPayableCheckNormalizedState(row).differenceStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看详情', '保存差异处理', '生成发票预备'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/payable-check/${row.id}`)">查看详情</el-button>
                <el-button v-if="getPayableCheckActions(row).canStartChecking" size="small" class="app-action-button-sm" type="warning" @click="markChecking(row)">开始核对</el-button>
                <el-button v-if="getPayableCheckActions(row).canMarkChecked" size="small" class="app-action-button-sm" type="success" @click="markChecked(row)">核对通过</el-button>
                <el-button v-if="getPayableCheckActions(row).canMarkDifference" size="small" class="app-action-button-sm" type="danger" @click="markDifference(row)">标记差异</el-button>
                <el-button v-if="getPayableCheckActions(row).canStartDifference" size="small" class="app-action-button-sm" type="danger" @click="startDifference(row)">处理差异</el-button>
                <el-button v-if="getPayableCheckActions(row).canSaveDifference" size="small" class="app-action-button-md" type="primary" @click="router.push(`/finance/payable-check/${row.id}`)">保存差异处理</el-button>
                <el-button v-if="getPayableCheckActions(row).canCancelDifference" size="small" class="app-action-button-sm" @click="cancelDifference(row)">取消处理</el-button>
                <el-button v-if="getPayableCheckActions(row).canRecheck" size="small" class="app-action-button-sm" type="warning" @click="recheckDifference(row)">重新核对</el-button>
                <el-button v-if="getPayableCheckActions(row).canViewDifference" size="small" class="app-action-button-md" @click="router.push(`/finance/payable-check/${row.id}`)">查看差异处理</el-button>
                <el-button v-if="getPayableCheckActions(row).canCreateInvoice" size="small" class="app-action-button-md" type="primary" @click="createInvoice(row)">生成发票预备</el-button>
                <el-button v-if="getPayableCheckActions(row).canViewInvoice" size="small" class="app-action-button-md" type="success" @click="viewInvoicePrepare(row)">查看发票预备</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, defineComponent, h, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  batchCreatePayableChecksFromPayablePrepares,
  batchMarkInvoicePrepareReady,
  batchMarkPayableCheckChecked,
  batchMarkPayableCheckChecking,
  batchMarkPayableCheckDifference,
  cancelPayableCheck,
  cancelPayableCheckDifferenceHandling,
  createPayableCheckFromPayablePrepare,
  getPayableCheckById,
  getPayableCheckSourcesFromPayablePrepares,
  listPayableChecks,
  markInvoicePrepareReady,
  markPayableCheckChecked,
  markPayableCheckChecking,
  markPayableCheckDifference,
  recheckPayableCheckAfterDifference,
  savePayableCheckDifferenceHandling,
  startPayableCheckDifferenceHandling,
} from '../finance/payableCheckStore.js'
import { createInvoicePrepareFromPayableCheck, listInvoicePrepares } from '../finance/invoicePrepareStore.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const BatchResult = defineComponent({
  props: { result: { type: Object, required: true }, type: { type: String, default: 'success' } },
  emits: ['close'],
  setup(props, { emit }) {
    return () => h('div', { class: ['batch-result', props.type] }, [
      h('button', { type: 'button', onClick: () => emit('close') }, '关闭'),
      h('strong', '批量操作完成'),
      h('span', `操作名称：${props.result.operationName}`),
      h('span', `已选择：${props.result.total} 条`),
      h('span', `成功：${props.result.successCount} 条`),
      props.result.writeBackCount != null ? h('span', `已回写状态：${props.result.writeBackCount} 条`) : null,
      h('span', `失败/跳过：${props.result.failedCount} 条`),
      props.result.failedReason?.length ? h('ol', props.result.failedReason.map((reason) => h('li', { key: reason }, reason))) : null,
      props.result.failedReason?.length ? h('span', `下一步建议：${props.result.nextSuggestion}`) : null,
    ])
  },
})

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const checkRows = ref([])
const selectedSourceRows = ref([])
const selectedCheckRows = ref([])
const sourceSortState = ref({ key: '', direction: 'asc' })
const checkSortState = ref({ key: '', direction: 'asc' })
const sourceTableRef = ref(null)
const checkTableRef = ref(null)
const message = ref('')
const messageType = ref('success')
const sourceBatchResult = ref(null)
const sourceBatchResultType = ref('success')
const checkBatchResult = ref(null)
const checkBatchResultType = ref('success')
const refreshVersion = ref(0)
const invoicePrepareRows = ref([])
const differenceForm = ref({
  differenceType: '',
  differenceReason: '',
  differenceResolution: '',
  differenceHandlerName: '当前处理人',
  remark: '',
})

const detail = computed(() => {
  refreshVersion.value
  return route.params.id ? getPayableCheckById(route.params.id) : null
})
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const checkIds = computed(() => selectedCheckRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'payablePrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalPayableQty', sortType: 'number' },
  { key: 'totalPayableAmount', sortType: 'amount' },
  { key: 'payableStatus', sortType: 'status' },
]
const checkSortColumns = [
  { key: 'payableCheckNo', sortType: 'string' },
  { key: 'sourcePayablePrepareNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalCheckedQty', sortType: 'number' },
  { key: 'totalCheckedAmount', sortType: 'amount' },
  { key: 'amountDifference', sortType: 'amount' },
  { key: 'checkStatus', sortType: 'status' },
  { key: 'differenceStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedCheckRows = computed(() => sortRecords(checkRows.value, checkSortState.value, checkSortColumns))
const sourceBatchCounts = computed(() => ({ create: selectedSourceRows.value.filter((row) => row.canCreatePayableCheck).length }))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  payablePrepareNo: '应付预备单号',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  totalPayableQty: '应付预备数量',
  totalPayableAmount: '应付预备金额',
  payableStatus: '状态',
}))
const checkSortText = computed(() => currentSortText(checkSortState.value, {
  payableCheckNo: '应付核对单号',
  sourcePayablePrepareNo: '来源应付预备',
  supplierName: '供应商',
  sourcePurchaseOrderNo: '采购订单',
  totalCheckedQty: '核对数量',
  totalCheckedAmount: '核对金额',
  amountDifference: '差异金额',
  checkStatus: '状态',
  differenceStatus: '差异处理',
}))
const differenceTypeOptions = [
  { label: '数量差异', value: 'quantity' },
  { label: '单价差异', value: 'price' },
  { label: '金额差异', value: 'amount' },
  { label: '供应商差异', value: 'supplier' },
  { label: '来源单据差异', value: 'sourceDocument' },
  { label: '其他差异', value: 'other' },
]
const differenceResolutionOptions = [
  { label: '按应付预备数据调整', value: 'adjustToPayablePrepare' },
  { label: '按发票/核对数据调整', value: 'adjustToInvoice' },
  { label: '记录调整说明', value: 'createAdjustmentNote' },
  { label: '退回采购处理', value: 'returnToPurchase' },
  { label: '退回仓库处理', value: 'returnToWarehouse' },
  { label: '退回供应商处理', value: 'returnToSupplier' },
  { label: '人工确认无误', value: 'manualConfirmed' },
  { label: '取消本次核对', value: 'cancelPayableCheck' },
  { label: '其他', value: 'other' },
]
const detailFields = computed(() => detail.value ? [
  { label: '应付核对单号', value: detail.value.payableCheckNo },
  { label: '来源应付预备', value: detail.value.sourcePayablePrepareNo || '-' },
  { label: '采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '收货单', value: detail.value.sourceReceiveNo || '-' },
  { label: '检验单', value: detail.value.sourceInspectionNo || '-' },
  { label: '原始请购单', value: detail.value.rootRequestNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '核对数量', value: detail.value.totalCheckedQty },
  { label: '核对金额', value: detail.value.totalCheckedAmount },
  { label: '数量差异', value: detail.value.quantityDifference },
  { label: '金额差异', value: detail.value.amountDifference },
  { label: '状态', value: checkStatusLabel(getPayableCheckNormalizedState(detail.value).checkStatus) },
  { label: '差异处理', value: differenceStatusLabel(getPayableCheckNormalizedState(detail.value).differenceStatus) },
  { label: '处理方式', value: differenceResolutionLabel(detail.value.differenceResolution) },
  { label: '目标发票预备', value: generatedInvoicePrepare(detail.value)?.invoicePrepareNo || detail.value.targetInvoicePrepareNo || '-' },
] : [])

function refresh() {
  sourceRows.value = getPayableCheckSourcesFromPayablePrepares()
  checkRows.value = listPayableChecks()
  invoicePrepareRows.value = listInvoicePrepares()
  refreshVersion.value += 1
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2400)
}

function currentSortText(state = {}, labels = {}) {
  if (!state.key) return '当前排序：默认顺序'
  return `当前排序：${labels[state.key] || state.key} / ${state.direction === 'desc' ? '降序' : '升序'}`
}

function handleSourceSelectionChange(rows) { selectedSourceRows.value = rows || [] }
function handleCheckSelectionChange(rows) { selectedCheckRows.value = rows || [] }
function clearSourceSelection() { selectedSourceRows.value = []; sourceTableRef.value?.clearSelection?.() }
function clearCheckSelection() { selectedCheckRows.value = []; checkTableRef.value?.clearSelection?.() }
function sourceSelectable(row) { return row.canCreatePayableCheck }

function handleSourceSortChange({ prop, order }) {
  sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSourceSelection()
}

function handleCheckSortChange({ prop, order }) {
  checkSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearCheckSelection()
}

function resetSourceSorting() { sourceSortState.value = { key: '', direction: 'asc' }; clearSourceSelection() }
function resetCheckSorting() { checkSortState.value = { key: '', direction: 'asc' }; clearCheckSelection() }

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('重复') || text.includes('已生成')) return '建议查看已生成单据，避免重复生成。'
  if (text.includes('状态')) return '建议检查来源状态是否已达到可生成条件。'
  if (text.includes('差异')) return '建议先处理差异，再重新标记为已核对或可生成发票预备。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? 0,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    writeBackCount: result.writeBackCount,
    failedReason,
    nextSuggestion: nextBatchSuggestion(failedReason),
  }
}

function showSourceBatchResult(result, operationName) {
  refresh()
  clearSourceSelection()
  sourceBatchResult.value = normalizeBatchResult(result, operationName)
  sourceBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function showCheckBatchResult(result, operationName) {
  refresh()
  clearCheckSelection()
  checkBatchResult.value = normalizeBatchResult(result, operationName)
  checkBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function runBatchCreateChecks() {
  if (!sourceIds.value.length) return notify('请先选择可生成应付核对的应付预备', 'warning')
  showSourceBatchResult(batchCreatePayableChecksFromPayablePrepares(sourceIds.value), '批量生成应付核对')
}

function runBatchChecking() { showCheckBatchResult(batchMarkPayableCheckChecking(checkIds.value), '批量开始核对') }
function runBatchChecked() { showCheckBatchResult(batchMarkPayableCheckChecked(checkIds.value), '批量核对通过') }
function runBatchDifference() { showCheckBatchResult(batchMarkPayableCheckDifference(checkIds.value), '批量标记差异') }
function runBatchReady() { showCheckBatchResult(batchMarkInvoicePrepareReady(checkIds.value), '批量准备生成发票预备') }

function getPayableCheckNormalizedState(row = {}) {
  const generated = generatedInvoicePrepare(row)
  const hasGeneratedInvoice = row.checkStatus === 'invoicePrepared'
    || row.invoicePrepareGenerated
    || row.targetInvoicePrepareId
    || row.targetInvoicePrepareNo
    || generated
  const differenceStatus = row.differenceStatus || (row.checkStatus === 'difference' ? 'pending' : 'none')
  let checkStatus = row.checkStatus || ''
  if (hasGeneratedInvoice) {
    return {
      ...row,
      checkStatus: 'invoicePrepared',
      differenceStatus,
      invoicePrepareGenerated: true,
      targetInvoicePrepareId: row.targetInvoicePrepareId || generated?.id || '',
      targetInvoicePrepareNo: row.targetInvoicePrepareNo || generated?.invoicePrepareNo || '',
    }
  }
  if (['pending', 'processing'].includes(differenceStatus) && ['checked', 'invoicePrepared', 'invoicePrepareReady'].includes(checkStatus)) {
    checkStatus = 'difference'
  }
  if (checkStatus === 'checked' && row.recheckRequired === true) {
    checkStatus = row.differenceResolved ? 'difference' : checkStatus
  }
  return { ...row, checkStatus, differenceStatus }
}

function getPayableCheckActions(row = {}) {
  const normalized = getPayableCheckNormalizedState(row)
  const checkStatus = normalized.checkStatus || ''
  const differenceStatus = normalized.differenceStatus
  return {
    canStartChecking: checkStatus === 'draft',
    canMarkChecked: ['draft', 'checking'].includes(checkStatus),
    canMarkDifference: ['draft', 'checking'].includes(checkStatus),
    canStartDifference: checkStatus === 'difference' && differenceStatus === 'pending',
    canSaveDifference: checkStatus === 'difference' && differenceStatus === 'processing',
    canCancelDifference: checkStatus === 'difference' && differenceStatus === 'processing',
    canEditDifference: checkStatus === 'difference' && differenceStatus === 'processing',
    canRecheck: checkStatus === 'difference' && differenceStatus === 'resolved',
    canViewDifference: checkStatus === 'difference' && differenceStatus === 'resolved',
    canCreateInvoice: ['checked', 'invoicePrepareReady'].includes(checkStatus),
    canViewInvoice: checkStatus === 'invoicePrepared',
  }
}

function generatedInvoicePrepare(row = {}) {
  if (!row?.id) return null
  return invoicePrepareRows.value.find((prepare) => String(prepare.sourcePayableCheckId) === String(row.id)) || null
}

function createCheck(row) {
  const outcome = createPayableCheckFromPayablePrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成应付核对 ${outcome.payableCheckNo}`)
}

function markChecking(row) { const outcome = markPayableCheckChecking(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已开始核对') }
function markChecked(row) { const outcome = markPayableCheckChecked(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('核对已通过') }
function markDifference(row) { const outcome = markPayableCheckDifference(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已标记差异') }
function markReady(row) { const outcome = markInvoicePrepareReady(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('已准备生成发票预备') }
function cancelCheck(row) { const outcome = cancelPayableCheck(row.id); if (!outcome.success) return notify(outcome.error, 'warning'); refresh(); notify('应付核对已取消') }

function syncDifferenceForm(row = {}) {
  differenceForm.value = {
    differenceType: row.differenceType || '',
    differenceReason: row.differenceReason || '',
    differenceResolution: row.differenceResolution || '',
    differenceHandlerName: row.differenceHandlerName || '当前处理人',
    remark: row.remark || '',
  }
}

function differenceStatusHint(row = {}) {
  const normalized = getPayableCheckNormalizedState(row)
  if (normalized.checkStatus === 'checked') return '核对已通过，可以生成发票预备。'
  const differenceStatus = normalized.differenceStatus
  if (differenceStatus === 'processing') return '当前差异处理中，请填写差异原因和处理方式。保存差异处理后，需要点击“重新核对”；重新核对通过后，才能生成发票预备。'
  if (differenceStatus === 'pending') return '请先点击“处理差异”，进入差异处理。'
  if (differenceStatus === 'resolved') return '差异已处理，请点击“重新核对”。'
  return '无差异时，核对通过后可以生成发票预备。'
}

function scrollToDifferenceForm() {
  document.querySelector('.difference-form')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function startDifference(row) {
  const outcome = startPayableCheckDifferenceHandling(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  syncDifferenceForm(outcome.payableCheck)
  refresh()
  if (!route.params.id) router.push(`/finance/payable-check/${row.id}`)
  notify('已进入差异处理，请填写差异原因和处理方式')
}

function saveDifference(row) {
  const outcome = savePayableCheckDifferenceHandling(row.id, differenceForm.value)
  if (!outcome.success) return notify(outcome.error, 'warning')
  syncDifferenceForm(outcome.payableCheck)
  refresh()
  notify('差异处理已保存，请重新核对')
}

function cancelDifference(row) {
  const outcome = cancelPayableCheckDifferenceHandling(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  syncDifferenceForm(outcome.payableCheck)
  refresh()
  notify('已取消差异处理')
}

function recheckDifference(row) {
  const outcome = recheckPayableCheckAfterDifference(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已重新进入核对，请核对通过后生成发票预备')
}

function createInvoice(row) {
  const outcome = createInvoicePrepareFromPayableCheck(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成发票预备 ${outcome.invoicePrepareNo}`)
  router.push(`/finance/invoice-prepare/${outcome.invoicePrepareId}`)
}

function viewInvoicePrepare(row) {
  const normalized = getPayableCheckNormalizedState(row)
  const targetId = normalized.targetInvoicePrepareId
  const targetNo = normalized.targetInvoicePrepareNo
  if (targetId) return router.push(`/finance/invoice-prepare/${targetId}`)
  notify(targetNo ? `已生成发票预备 ${targetNo}，请在列表中查看。` : '已生成发票预备，请在列表中查看。')
  router.push('/finance/invoice-prepares')
}

function prepareStatusLabel(status) {
  return { prepared: '已预备', checking: '核对中', checked: '已核对', payableReady: '可生成应付', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function prepareStatusType(status) {
  return { prepared: 'primary', checking: 'warning', checked: 'success', payableReady: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}
function checkStatusLabel(status) {
  return { draft: '草稿', checking: '核对中', checked: '可生成发票预备', difference: '存在差异', invoicePrepareReady: '可生成发票预备', invoicePrepared: '已生成发票预备', cancelled: '取消', closed: '关闭' }[status] || status || '-'
}
function checkStatusType(status) {
  return { draft: 'info', checking: 'warning', checked: 'success', difference: 'danger', invoicePrepareReady: 'success', invoicePrepared: 'success', cancelled: 'info', closed: 'info' }[status] || 'info'
}

function differenceStatusLabel(status) {
  return { none: '无差异', pending: '待处理', processing: '处理中', resolved: '已处理', rejected: '无法处理' }[status] || status || '无差异'
}
function differenceStatusType(status) {
  return { none: 'info', pending: 'danger', processing: 'warning', resolved: 'success', rejected: 'danger' }[status] || 'info'
}
function differenceResolutionLabel(status) {
  return differenceResolutionOptions.find((item) => item.value === status)?.label || status || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
watch(detail, (row) => syncDifferenceForm(row || {}), { immediate: true })
</script>

<style scoped>
.finance-flow-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.eyebrow, .card-header span, .info-grid span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row, .batch-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.finance-flow-nav { align-items: stretch; border: 1px solid #dbeafe; border-radius: 8px; padding: 10px; background: #f8fbff; }
.finance-nav-title { display: flex; align-items: center; color: #475467; font-size: 13px; font-weight: 700; margin-right: 4px; }
.page-tabs a, .finance-nav-button { border: 1px solid #bfdbfe; border-radius: 6px; padding: 8px 12px; background: #fff; color: #1d4ed8; font-weight: 700; text-decoration: none; white-space: nowrap; }
.page-tabs a.finance-nav-button-active { border-color: #0f766e; background: #0f766e; color: #fff; box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18); }
.finance-current-tag { display: inline-flex; align-items: center; margin-left: 6px; border-radius: 999px; padding: 2px 7px; background: rgba(255, 255, 255, 0.22); color: inherit; font-size: 12px; }
.finance-current-module-badge { display: inline-flex; width: fit-content; border: 1px solid #99f6e4; border-radius: 999px; padding: 5px 10px; background: #ecfdf5; color: #0f766e !important; font-weight: 800; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide, .next-step-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.next-step-guide { grid-template-columns: auto 1fr auto; align-items: center; border-color: #fde68a; background: #fffbeb; color: #78350f; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.flow-guide, .amount-guide, .difference-guide { display: grid; gap: 6px; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px; background: #eff6ff; color: #1e3a8a; line-height: 1.6; }
.amount-guide { margin-top: 12px; border-color: #dbe3ef; background: #f8fafc; color: #334155; }
.difference-guide { border-color: #fecaca; background: #fff7ed; color: #7c2d12; }
.difference-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.difference-form label { display: grid; gap: 6px; color: #475569; font-size: 13px; font-weight: 700; }
.wide-field { grid-column: 1 / -1; }
.info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 14px; }
.info-grid article { border: 1px solid #dbe3ef; border-radius: 8px; padding: 12px; background: #fff; }
.info-grid strong { display: block; margin-top: 4px; }
.batch-bar { border: 1px solid #dbe3ef; border-radius: 8px; padding: 10px; margin-bottom: 12px; background: #f8fafc; }
.button-row .el-button, .batch-bar .el-button { min-width: 96px; white-space: nowrap; }
.button-row .el-button--small, .batch-bar .el-button--small { min-width: 86px; }
.button-row .el-button--primary, .button-row .el-button--success, .button-row .el-button--warning,
.batch-bar .el-button--primary, .batch-bar .el-button--success, .batch-bar .el-button--warning { min-width: 132px; }
.button-row .el-button--danger, .batch-bar .el-button--danger { min-width: 86px; }
.sort-help { color: #64748b; font-size: 13px; }
.batch-result { position: relative; display: grid; gap: 6px; margin-bottom: 12px; border-radius: 8px; padding: 12px; background: #ecfdf5; color: #065f46; }
.batch-result.warning { background: #fffbeb; color: #92400e; }
.batch-result.error { background: #fef2f2; color: #991b1b; }
.batch-result button { position: absolute; top: 8px; right: 8px; border: 0; background: transparent; color: inherit; cursor: pointer; }
@media (max-width: 900px) {
  .plain-flow-grid, .next-step-guide { grid-template-columns: 1fr; }
  .difference-form { grid-template-columns: 1fr; }
}
</style>
