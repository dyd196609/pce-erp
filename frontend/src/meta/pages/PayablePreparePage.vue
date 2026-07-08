<template>
  <main class="payable-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.3.1 采购应付预备</p>
        <h1>{{ detail ? '应付预备详情' : '采购应付预备' }}</h1>
        <p>本页只根据 QMS 确认入库后的 WMS 库存流水生成应付预备，不生成正式应付、发票、付款或财务凭证。</p>
        <p class="finance-current-module-badge">当前操作模块：应付预备</p>
      </section>
      <nav class="page-tabs finance-flow-nav" aria-label="财务前置流程导航">
        <span class="finance-nav-title">财务前置流程导航</span>
        <router-link class="finance-nav-button" to="/process-center">业务中心</router-link>
        <router-link class="finance-nav-button" to="/wms/inventory-transactions">库存流水</router-link>
        <router-link class="finance-nav-button finance-nav-button-active" to="/finance/payable-prepares">应付预备 <span class="finance-current-tag">当前</span></router-link>
        <router-link class="finance-nav-button" to="/finance/payable-checks">应付核对</router-link>
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
          <span><b>当前步骤</b>第 1 步：生成应付预备</span>
          <span><b>本页要做</b>把已入库的合格数量和让步接收数量整理成“准备付款的数据清单”。</span>
          <span><b>下一步</b>进入应付核对，核对数量、单价、金额和来源单据。</span>
          <span><b>本页不会做</b>不生成正式应付账款、付款单或财务凭证。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>选择已入库流水，点击“生成应付预备”；生成后进入“应付核对”。</span>
        <el-button type="primary" @click="router.push('/finance/payable-checks')">进入应付核对</el-button>
      </section>
      <section class="flow-guide">
        <strong>作业流程：库存入库 -> 应付预备 -> 应付核对 -> 发票预备 -> 后续正式应付</strong>
        <span>本页只根据采购检验合格入库和让步接收入库生成应付预备，不生成正式应付、付款或财务凭证。下一步：应付预备核对通过后，进入应付核对。</span>
      </section>
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.payablePrepareNo }}</h2>
              <span>{{ detail.sourcePurchaseOrderNo || '-' }} / {{ detail.supplierName || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button @click="router.push('/finance/payable-prepares')">返回列表</el-button>
              <el-button type="primary" @click="goInventoryTransaction(detail)">查看来源库存流水</el-button>
              <el-button @click="goPurchaseOrder(detail)">查看来源采购订单</el-button>
              <el-button @click="goReceive(detail)">查看来源收货单</el-button>
              <el-button @click="goInspection(detail)">查看来源检验单</el-button>
              <el-button v-if="detail.payableStatus === 'prepared'" type="warning" @click="markChecking(detail)">核对应付预备</el-button>
              <el-button v-if="detail.payableStatus === 'checking'" type="success" @click="markChecked(detail)">核对通过</el-button>
              <el-button v-if="['checked', 'invoicePending'].includes(detail.payableStatus)" type="success" @click="markReady(detail)">标记可生成应付</el-button>
              <el-button v-if="!['cancelled', 'closed'].includes(detail.payableStatus)" type="danger" @click="cancelPrepare(detail)">取消</el-button>
            </div>
          </div>
        </template>
        <el-alert
          title="采购订单 -> 收货 -> 来料检验 -> 确认入库 -> 库存流水 -> 应付预备。当前版本只做到应付预备。"
          type="info"
          show-icon
          :closable="false"
        />
        <section class="amount-guide">
          <strong>金额口径</strong>
          <span>应付预备金额根据合格入库 / 让步接收入库数量和采购价格计算，通常作为含税金额口径处理；totalPayableAmount 包含合格入库金额和让步接收入库金额。</span>
        </section>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>应付预备明细</h2></template>
        <el-table :data="detail.lines || []" border stripe height="520">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="batchNo" label="批号" min-width="130" />
          <el-table-column prop="warehouseName" label="仓库" min-width="120" />
          <el-table-column prop="locationName" label="库位" min-width="120" />
          <el-table-column prop="qualityStatus" label="质量状态" min-width="110">
            <template #default="{ row }">{{ qualityStatusLabel(row.qualityStatus) }}</template>
          </el-table-column>
          <el-table-column prop="payableQty" label="应付预备数量" width="130" />
          <el-table-column prop="payablePrice" label="应付预备单价" width="130" />
          <el-table-column prop="payableAmount" label="应付预备金额" width="130" />
          <el-table-column prop="sourceInventoryTransactionNo" label="来源流水" min-width="160" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单" min-width="150" />
          <el-table-column prop="remark" label="备注" min-width="220" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <section class="plain-flow-guide">
        <strong>财务前置总流程：采购入库完成 -> 生成应付预备 -> 核对数量和金额 -> 准备发票信息 -> 生成应付账款草稿 -> 确认应付 -> 等待后续付款</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>第 1 步：生成应付预备</span>
          <span><b>本页要做</b>根据检验合格入库、让步接收入库的库存流水，生成“准备付款的数据清单”。</span>
          <span><b>下一步</b>生成应付预备后，进入“应付核对”。</span>
          <span><b>本页不会做</b>不生成正式应付账款、付款单或财务凭证。</span>
        </div>
      </section>
      <section class="next-step-guide">
        <strong>下一步操作</strong>
        <span>选择已入库流水，点击“生成应付预备”；如果来源已生成，请查看应付预备并进入“应付核对”。</span>
        <el-button type="primary" @click="router.push('/finance/payable-checks')">进入应付核对</el-button>
      </section>
      <section class="flow-guide">
        <strong>作业流程：库存入库 -> 应付预备 -> 应付核对 -> 发票预备 -> 后续正式应付</strong>
        <span>采购检验合格入库和让步接收入库都会进入本页来源；退货、报废、返工、调整、调拨、未检验或未入库数据不会进入应付预备。</span>
      </section>
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>来源诊断</h2>
              <span>诊断读取 WMS 当前库存流水，不重置、不造数、不改原始单据。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="showDiagnostics = !showDiagnostics">{{ showDiagnostics ? '收起诊断' : '查看来源诊断' }}</el-button>
              <el-button @click="router.push('/wms/inventory-transactions')">查看库存流水</el-button>
              <el-button @click="router.push('/qms/incoming-inspections')">查看 QMS 来料检验</el-button>
            </div>
          </div>
        </template>

        <div class="diagnostic-grid">
          <article v-for="item in diagnosticItems" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>

        <div v-if="showDiagnostics || !sourceSummary.eligibleCount" class="diagnostic-detail">
          <strong>无数据原因</strong>
          <ol v-if="sourceSummary.reasons.length">
            <li v-for="reason in sourceSummary.reasons" :key="reason">{{ reason }}</li>
          </ol>
          <p v-else>当前存在可生成应付预备的入库流水。</p>
          <strong>请先检查</strong>
          <ol>
            <li>WMS 库存流水是否包含 purchaseInspectionIn 或 concessionIn。</li>
            <li>QMS 检验单是否已经确认入库。</li>
            <li>入库流水是否包含来源采购订单号和供应商信息。</li>
          </ol>
          <strong>PO2026070309004733 来源诊断</strong>
          <ol v-if="focusedPurchaseOrderDiagnostics.length">
            <li v-for="item in focusedPurchaseOrderDiagnostics" :key="item.id">
              {{ item.transactionNo || item.id }} / {{ transactionTypeLabel(item.transactionType) }} / {{ qualityStatusLabel(item.qualityStatus) }} / 数量 {{ item.quantity }}：
              {{ item.canCreatePayablePrepare ? '可进入应付预备' : item.rejectReason }}
            </li>
          </ol>
          <p v-else>未发现该采购订单号对应的 WMS 库存流水。</p>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>采购应付预备来源</h2>
              <span>仅采购检验合格入库和让步接收入库流水可进入应付预备。</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="refresh">刷新来源</el-button>
              <el-button @click="router.push('/wms/inventory-transactions')">查看库存流水</el-button>
            </div>
          </div>
        </template>
        <el-alert
          title="不进入应付预备：退货、报废、返工、调整、调拨、未检验、未确认入库。本页不生成正式应付或财务凭证。"
          type="warning"
          show-icon
          :closable="false"
        />
        <div class="batch-bar">
          <span>已选择 {{ selectedSourceRows.length }} 条</span>
          <span>可生成应付预备 {{ sourceBatchCounts.create }} 条</span>
          <span>将跳过 {{ selectedSourceRows.length - sourceBatchCounts.create }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ sourceSortText }}</span>
          <el-button size="small" @click="resetSourceSorting">清除排序</el-button>
          <el-button size="small" @click="clearSourceSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="success" :disabled="!sourceBatchCounts.create" @click="runBatchCreate">批量生成应付预备</el-button>
        </div>
        <div v-if="sourceBatchResult" class="batch-result" :class="sourceBatchResultType">
          <button type="button" @click="sourceBatchResult = null">关闭</button>
          <strong>批量操作完成</strong>
          <span>操作名称：{{ sourceBatchResult.operationName }}</span>
          <span>已选择：{{ sourceBatchResult.total }} 条</span>
          <span>成功：{{ sourceBatchResult.successCount }} 条</span>
          <span>失败/跳过：{{ sourceBatchResult.failedCount }} 条</span>
          <ol v-if="sourceBatchResult.failedReason?.length">
            <li v-for="reason in sourceBatchResult.failedReason" :key="reason">{{ reason }}</li>
          </ol>
          <span v-if="sourceBatchResult.failedReason?.length">下一步建议：{{ sourceBatchResult.nextSuggestion }}</span>
        </div>
        <el-empty v-if="!sourceRows.length" description="暂无可生成应付预备的入库流水">
          <div class="empty-actions">
            <el-button type="primary" @click="router.push('/wms/inventory-transactions')">查看库存流水</el-button>
            <el-button @click="router.push('/qms/incoming-inspections')">查看 QMS 来料检验</el-button>
            <el-button @click="refresh">刷新来源</el-button>
          </div>
        </el-empty>
        <el-table
          v-else
          ref="sourceTableRef"
          :data="sortedSourceRows"
          border
          stripe
          height="520"
          @selection-change="handleSourceSelectionChange"
          @sort-change="handleSourceSortChange"
        >
          <el-table-column type="selection" width="48" fixed="left" :selectable="sourceSelectable" />
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="transactionNo" label="库存流水号" min-width="170" sortable="custom" />
          <el-table-column prop="transactionType" label="流水类型" min-width="150" sortable="custom">
            <template #default="{ row }">{{ transactionTypeLabel(row.transactionType) }}</template>
          </el-table-column>
          <el-table-column prop="transactionDate" label="入库日期" width="120" sortable="custom" />
          <el-table-column prop="materialName" label="物料" min-width="150" />
          <el-table-column prop="batchNo" label="批号" min-width="130" />
          <el-table-column prop="warehouseName" label="仓库" min-width="120" />
          <el-table-column prop="locationName" label="库位" min-width="120" />
          <el-table-column prop="qualityStatus" label="质量状态" min-width="110" sortable="custom">
            <template #default="{ row }">{{ qualityStatusLabel(row.qualityStatus) }}</template>
          </el-table-column>
          <el-table-column prop="quantity" label="入库数量" width="110" sortable="custom" />
          <el-table-column prop="sourceInspectionNo" label="来源检验单" min-width="150" />
          <el-table-column prop="sourceReceiveNo" label="来源收货单" min-width="150" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单" min-width="150" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" sortable="custom" />
          <el-table-column prop="sourceWarning" label="来源提示" min-width="190" />
          <el-table-column label="是否已生成" width="120">
            <template #default="{ row }">
              <el-tag :type="row.payablePrepareGenerated ? 'success' : 'info'">{{ row.payablePrepareGenerated ? '已生成' : '未生成' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['生成应付预备'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="!row.payablePrepareGenerated" size="small" class="app-action-button-md" type="success" @click="createFromSource(row)">生成应付预备</el-button>
                <el-button v-else size="small" class="app-action-button-md" @click="goGeneratedPrepare(row)">查看应付预备</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>应付预备列表</h2>
              <span>只记录应付预备状态，不生成正式应付账款。</span>
            </div>
          </div>
        </template>
        <div class="batch-bar">
          <span>已选择 {{ selectedPrepareRows.length }} 条</span>
          <span>可批量流转 {{ selectedPrepareRows.length }} 条</span>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ prepareSortText }}</span>
          <el-button size="small" @click="resetPrepareSorting">清除排序</el-button>
          <el-button size="small" @click="clearPrepareSelection">清空选择</el-button>
          <span class="batch-action-title">当前模块操作（立即生效）</span>
          <span class="batch-action-tip">以下按钮会立即修改所选记录状态，请确认选择无误后再执行。</span>
          <el-button size="small" type="warning" :disabled="!selectedPrepareRows.length" @click="runBatchChecking">批量开始核对</el-button>
          <el-button size="small" type="success" :disabled="!selectedPrepareRows.length" @click="runBatchChecked">批量核对通过</el-button>
          <el-button size="small" type="success" :disabled="!selectedPrepareRows.length" @click="runBatchReady">批量准备进入应付核对</el-button>
        </div>
        <div v-if="prepareBatchResult" class="batch-result" :class="prepareBatchResultType">
          <button type="button" @click="prepareBatchResult = null">关闭</button>
          <strong>批量操作完成</strong>
          <span>操作名称：{{ prepareBatchResult.operationName }}</span>
          <span>已选择：{{ prepareBatchResult.total }} 条</span>
          <span>成功：{{ prepareBatchResult.successCount }} 条</span>
          <span>失败/跳过：{{ prepareBatchResult.failedCount }} 条</span>
          <ol v-if="prepareBatchResult.failedReason?.length">
            <li v-for="reason in prepareBatchResult.failedReason" :key="reason">{{ reason }}</li>
          </ol>
          <span v-if="prepareBatchResult.failedReason?.length">下一步建议：{{ prepareBatchResult.nextSuggestion }}</span>
        </div>
        <el-table ref="prepareTableRef" :data="sortedPrepareRows" border stripe height="520" @selection-change="handlePrepareSelectionChange" @sort-change="handlePrepareSortChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="payablePrepareNo" label="应付预备单号" min-width="170" sortable="custom" />
          <el-table-column prop="sourcePurchaseOrderNo" label="来源采购订单号" min-width="150" sortable="custom" />
          <el-table-column prop="sourceReceiveNo" label="来源收货单号" min-width="150" />
          <el-table-column prop="sourceInspectionNo" label="来源检验单号" min-width="150" />
          <el-table-column prop="rootRequestNo" label="原始请购单号" min-width="150" />
          <el-table-column prop="supplierName" label="供应商" min-width="150" />
          <el-table-column prop="buyerName" label="采购员" min-width="110" />
          <el-table-column prop="totalPayableQty" label="应付预备数量" width="130" sortable="custom" />
          <el-table-column prop="totalPayableAmount" label="应付预备金额" width="130" sortable="custom" />
          <el-table-column prop="payableStatus" label="状态" width="120" sortable="custom">
            <template #default="{ row }"><el-tag :type="statusType(row.payableStatus)">{{ statusLabel(row.payableStatus) }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['查看详情', '准备进入应付核对'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/finance/payable-prepare/${row.id}`)">查看详情</el-button>
                <el-button v-if="row.payableStatus === 'prepared'" size="small" class="app-action-button-sm" type="warning" @click="markChecking(row)">开始核对</el-button>
                <el-button v-if="row.payableStatus === 'checking'" size="small" class="app-action-button-sm" type="success" @click="markChecked(row)">核对通过</el-button>
                <el-button v-if="['checked', 'invoicePending'].includes(row.payableStatus)" size="small" class="app-action-button-lg" type="success" @click="markReady(row)">准备进入应付核对</el-button>
                <el-button v-if="!['cancelled', 'closed'].includes(row.payableStatus)" size="small" class="app-action-button-sm" type="danger" @click="cancelPrepare(row)">取消</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  batchCreatePayablePrepareFromInventoryTransactions,
  batchMarkPayablePrepareChecked,
  batchMarkPayablePrepareChecking,
  batchMarkPayablePrepareReady,
  cancelPayablePrepare,
  createPayablePrepareFromInventoryTransaction,
  diagnosePayablePrepareSourcesByPurchaseOrder,
  getPayablePrepareById,
  getPayablePrepareSourceSummary,
  getPayablePrepareSourcesFromInventory,
  listPayablePrepares,
  markPayablePrepareChecked,
  markPayablePrepareChecking,
  markPayablePrepareReady,
} from '../finance/payablePrepareStore.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const route = useRoute()
const router = useRouter()
const sourceRows = ref([])
const prepareRows = ref([])
const sourceSummary = ref(getPayablePrepareSourceSummary())
const selectedSourceRows = ref([])
const selectedPrepareRows = ref([])
const sourceSortState = ref({ key: '', direction: 'asc' })
const prepareSortState = ref({ key: '', direction: 'asc' })
const sourceTableRef = ref(null)
const prepareTableRef = ref(null)
const message = ref('')
const messageType = ref('success')
const showDiagnostics = ref(true)
const sourceBatchResult = ref(null)
const sourceBatchResultType = ref('success')
const prepareBatchResult = ref(null)
const prepareBatchResultType = ref('success')
const focusedPurchaseOrderNo = 'PO2026070309004733'

const detail = computed(() => route.params.id ? getPayablePrepareById(route.params.id) : null)
const sourceIds = computed(() => selectedSourceRows.value.map((row) => row.id).filter(Boolean))
const prepareIds = computed(() => selectedPrepareRows.value.map((row) => row.id).filter(Boolean))
const sourceSortColumns = [
  { key: 'transactionNo', sortType: 'string' },
  { key: 'transactionType', sortType: 'string' },
  { key: 'transactionDate', sortType: 'date' },
  { key: 'qualityStatus', sortType: 'string' },
  { key: 'quantity', sortType: 'number' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
]
const prepareSortColumns = [
  { key: 'payablePrepareNo', sortType: 'string' },
  { key: 'sourcePurchaseOrderNo', sortType: 'string' },
  { key: 'totalPayableQty', sortType: 'number' },
  { key: 'totalPayableAmount', sortType: 'amount' },
  { key: 'payableStatus', sortType: 'status' },
]
const sortedSourceRows = computed(() => sortRecords(sourceRows.value, sourceSortState.value, sourceSortColumns))
const sortedPrepareRows = computed(() => sortRecords(prepareRows.value, prepareSortState.value, prepareSortColumns))
const sourceSortText = computed(() => currentSortText(sourceSortState.value, {
  transactionNo: '库存流水号',
  transactionType: '流水类型',
  transactionDate: '入库日期',
  qualityStatus: '质量状态',
  quantity: '入库数量',
  sourcePurchaseOrderNo: '来源采购订单',
  supplierName: '供应商',
}))
const prepareSortText = computed(() => currentSortText(prepareSortState.value, {
  payablePrepareNo: '应付预备单号',
  sourcePurchaseOrderNo: '来源采购订单号',
  totalPayableQty: '应付预备数量',
  totalPayableAmount: '应付预备金额',
  payableStatus: '状态',
}))
const sourceBatchCounts = computed(() => ({
  create: selectedSourceRows.value.filter((row) => !row.payablePrepareGenerated).length,
}))
const focusedPurchaseOrderDiagnostics = computed(() => diagnosePayablePrepareSourcesByPurchaseOrder(focusedPurchaseOrderNo))
const diagnosticItems = computed(() => [
  { label: '库存流水总数', value: sourceSummary.value.totalInventoryTransactions },
  { label: 'QMS 入库流水数', value: sourceSummary.value.qmsInventoryTransactions },
  { label: '采购检验合格入库流水数', value: sourceSummary.value.purchaseInspectionInCount },
  { label: '让步接收入库流水数', value: sourceSummary.value.concessionInCount },
  { label: '已生成应付预备数', value: sourceSummary.value.alreadyPreparedCount },
  { label: '缺少供应商信息数', value: sourceSummary.value.missingSupplierCount },
  { label: '缺少采购订单号数', value: sourceSummary.value.missingPurchaseOrderCount },
  { label: '数量无效数', value: sourceSummary.value.missingQuantityCount },
  { label: '可生成应付预备数', value: sourceSummary.value.eligibleCount },
  { label: '被排除数', value: sourceSummary.value.rejectedCount },
])
const detailFields = computed(() => detail.value ? [
  { label: '应付预备单号', value: detail.value.payablePrepareNo },
  { label: '来源采购订单', value: detail.value.sourcePurchaseOrderNo || '-' },
  { label: '来源收货单', value: detail.value.sourceReceiveNo || '-' },
  { label: '来源检验单', value: detail.value.sourceInspectionNo || '-' },
  { label: '原始请购单', value: detail.value.rootRequestNo || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '采购员', value: detail.value.buyerName || '-' },
  { label: '请购部门', value: detail.value.requestDepartment || '-' },
  { label: '需求部门', value: detail.value.demandDepartment || '-' },
  { label: '采购部门', value: detail.value.purchaseDepartment || '-' },
  { label: '应付预备数量', value: detail.value.totalPayableQty },
  { label: '应付预备金额', value: detail.value.totalPayableAmount },
  { label: '结算依据', value: settlementBasisLabel(detail.value.settlementBasis) },
  { label: '状态', value: statusLabel(detail.value.payableStatus) },
] : [])

function refresh() {
  sourceRows.value = getPayablePrepareSourcesFromInventory()
  prepareRows.value = listPayablePrepares()
  sourceSummary.value = getPayablePrepareSourceSummary()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => { message.value = '' }, 2400)
}

function handleSourceSelectionChange(rows) {
  selectedSourceRows.value = rows || []
}

function handlePrepareSelectionChange(rows) {
  selectedPrepareRows.value = rows || []
}

function clearSourceSelection() {
  selectedSourceRows.value = []
  sourceTableRef.value?.clearSelection?.()
}

function clearPrepareSelection() {
  selectedPrepareRows.value = []
  prepareTableRef.value?.clearSelection?.()
}

function currentSortText(state = {}, labels = {}) {
  if (!state.key) return '当前排序：默认顺序'
  return `当前排序：${labels[state.key] || state.key} / ${state.direction === 'desc' ? '降序' : '升序'}`
}

function resetSourceSorting() {
  sourceSortState.value = { key: '', direction: 'asc' }
  clearSourceSelection()
}

function resetPrepareSorting() {
  prepareSortState.value = { key: '', direction: 'asc' }
  clearPrepareSelection()
}

function handleSourceSortChange({ prop, order }) {
  sourceSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSourceSelection()
}

function handlePrepareSortChange({ prop, order }) {
  prepareSortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearPrepareSelection()
}

function sourceSelectable(row) {
  return !row.payablePrepareGenerated
}

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('已生成')) return '建议查看已生成的应付预备单，避免重复生成。'
  if (text.includes('缺少')) return '建议回到来源单据补齐供应商、采购订单等来源信息。'
  if (text.includes('状态')) return '建议检查当前应付预备状态后再执行。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? 0,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
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

function showPrepareBatchResult(result, operationName) {
  refresh()
  clearPrepareSelection()
  prepareBatchResult.value = normalizeBatchResult(result, operationName)
  prepareBatchResultType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function runBatchCreate() {
  if (!sourceIds.value.length) return notify('请先选择可生成应付预备的库存流水', 'warning')
  if (!sourceBatchCounts.value.create) return notify('所选库存流水均已生成应付预备', 'warning')
  showSourceBatchResult(batchCreatePayablePrepareFromInventoryTransactions(sourceIds.value), '批量生成应付预备')
}

function runBatchChecking() {
  if (!prepareIds.value.length) return notify('请先选择应付预备单', 'warning')
  showPrepareBatchResult(batchMarkPayablePrepareChecking(prepareIds.value), '批量开始核对')
}

function runBatchChecked() {
  if (!prepareIds.value.length) return notify('请先选择应付预备单', 'warning')
  showPrepareBatchResult(batchMarkPayablePrepareChecked(prepareIds.value), '批量核对通过')
}

function runBatchReady() {
  if (!prepareIds.value.length) return notify('请先选择应付预备单', 'warning')
  showPrepareBatchResult(batchMarkPayablePrepareReady(prepareIds.value), '批量准备进入应付核对')
}

function createFromSource(row) {
  const outcome = createPayablePrepareFromInventoryTransaction(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成应付预备 ${outcome.payablePrepareNo}`)
}

function generatedPrepare(row) {
  return prepareRows.value.find((prepare) => (prepare.sourceInventoryTransactionIds || []).includes(row.id))
}

function goGeneratedPrepare(row) {
  const prepare = generatedPrepare(row)
  if (!prepare) return notify('未找到已生成应付预备', 'warning')
  router.push(`/finance/payable-prepare/${prepare.id}`)
}

function markChecking(row) {
  const outcome = markPayablePrepareChecking(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已开始核对')
}

function markChecked(row) {
  const outcome = markPayablePrepareChecked(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已核对通过')
}

function markReady(row) {
  const outcome = markPayablePrepareReady(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('已准备进入应付核对，本轮不生成正式应付')
}

function cancelPrepare(row) {
  const outcome = cancelPayablePrepare(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('应付预备已取消')
}

function goInventoryTransaction(row) {
  const id = row.sourceInventoryTransactionIds?.[0]
  router.push(id ? `/wms/inventory-transaction/${id}` : '/wms/inventory-transactions')
}

function goPurchaseOrder(row) {
  router.push(row.sourcePurchaseOrderId ? `/scm/purchase-order/${row.sourcePurchaseOrderId}` : '/scm/purchase-orders')
}

function goReceive(row) {
  router.push(row.sourceReceiveId ? `/wms/purchase-receive/${row.sourceReceiveId}` : '/wms/purchase-receives')
}

function goInspection(row) {
  router.push(row.sourceInspectionId ? `/qms/incoming-inspection/${row.sourceInspectionId}` : '/qms/incoming-inspections')
}

function statusLabel(status) {
  return {
    prepared: '已预备',
    checking: '核对中',
    checked: '已核对',
    invoicePending: '待发票',
    payableReady: '可生成应付',
    cancelled: '取消',
    closed: '关闭',
  }[status] || status || '-'
}

function transactionTypeLabel(type) {
  return {
    purchaseInspectionIn: '采购检验合格入库',
    concessionIn: '让步接收入库',
  }[type] || type || '-'
}

function qualityStatusLabel(status) {
  return {
    qualified: '合格',
    concession: '让步接收',
    returnPending: '退货待处理',
    scrapped: '已报废',
    reworkPending: '返工待处理',
    pending: '待检',
  }[status] || status || '-'
}

function statusType(status) {
  return {
    prepared: 'primary',
    checking: 'warning',
    checked: 'success',
    invoicePending: 'warning',
    payableReady: 'success',
    cancelled: 'info',
    closed: 'info',
  }[status] || 'info'
}

function settlementBasisLabel(value) {
  return {
    inventory: '按入库数量',
    receive: '按收货数量',
    inspectionQualified: '按检验合格数量',
    manual: '人工调整',
  }[value] || value || '-'
}

watch(() => route.fullPath, refresh, { immediate: true })
</script>

<style scoped>
.payable-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f5f7fb;
  color: #172033;
}

.page-header,
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow,
.card-header span,
.info-grid span,
.diagnostic-grid span {
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

.page-tabs,
.button-row,
.batch-bar,
.empty-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.finance-flow-nav {
  align-items: stretch;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  padding: 10px;
  background: #f8fbff;
}

.finance-nav-title {
  display: flex;
  align-items: center;
  color: #475467;
  font-size: 13px;
  font-weight: 700;
  margin-right: 4px;
}

.page-tabs a,
.finance-nav-button {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 8px 12px;
  background: #fff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
  white-space: nowrap;
}

.page-tabs a.finance-nav-button-active {
  border-color: #0f766e;
  background: #0f766e;
  color: #fff;
  box-shadow: 0 6px 14px rgba(15, 118, 110, 0.18);
}

.finance-current-tag {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
  border-radius: 999px;
  padding: 2px 7px;
  background: rgba(255, 255, 255, 0.22);
  color: inherit;
  font-size: 12px;
}

.finance-current-module-badge {
  display: inline-flex;
  width: fit-content;
  border: 1px solid #99f6e4;
  border-radius: 999px;
  padding: 5px 10px;
  background: #ecfdf5;
  color: #0f766e !important;
  font-weight: 800;
}

.operation-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.flow-guide {
  display: grid;
  gap: 6px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 12px;
  background: #eff6ff;
  color: #1e3a8a;
  line-height: 1.6;
}

.plain-flow-guide,
.next-step-guide {
  display: grid;
  gap: 10px;
  border: 1px solid #a7f3d0;
  border-radius: 8px;
  padding: 14px;
  background: #ecfdf5;
  color: #064e3b;
  line-height: 1.6;
}

.next-step-guide {
  grid-template-columns: auto 1fr auto;
  align-items: center;
  border-color: #fde68a;
  background: #fffbeb;
  color: #78350f;
}

.plain-flow-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.plain-flow-grid span {
  display: grid;
  gap: 4px;
  border: 1px solid rgba(6, 78, 59, 0.14);
  border-radius: 8px;
  padding: 10px;
  background: #fff;
}

.amount-guide {
  display: grid;
  gap: 6px;
  margin-top: 12px;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
  color: #334155;
  line-height: 1.6;
}

.batch-bar,
.diagnostic-detail {
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid #d9e4f2;
  border-radius: 8px;
  background: #f8fbff;
}

.button-row .el-button,
.batch-bar .el-button,
.empty-actions .el-button {
  min-width: 96px;
  white-space: nowrap;
}

.button-row .el-button--small,
.batch-bar .el-button--small {
  min-width: 86px;
}

.button-row .el-button--primary,
.button-row .el-button--success,
.button-row .el-button--warning,
.batch-bar .el-button--primary,
.batch-bar .el-button--success,
.batch-bar .el-button--warning {
  min-width: 132px;
}

.button-row .el-button--danger,
.batch-bar .el-button--danger {
  min-width: 86px;
}

.diagnostic-detail {
  line-height: 1.7;
}

.batch-result {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 12px 0;
  padding: 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  line-height: 1.6;
}

.batch-result.warning {
  border-color: #fde68a;
  background: #fffbeb;
}

.batch-result.error {
  border-color: #fecaca;
  background: #fef2f2;
}

.batch-result button {
  align-self: flex-end;
  border: 0;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
}

.info-grid,
.diagnostic-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.diagnostic-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.info-grid article,
.diagnostic-grid article {
  border: 1px solid #d8e2ef;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.info-grid strong,
.diagnostic-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
}

@media (max-width: 1100px) {
  .diagnostic-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .page-header,
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .info-grid,
  .diagnostic-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .plain-flow-grid,
  .next-step-guide {
    grid-template-columns: 1fr;
  }
}
</style>
