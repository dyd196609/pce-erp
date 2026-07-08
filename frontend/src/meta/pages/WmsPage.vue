<template>
  <main class="wms-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.9.1.1 WMS中文显示修复</p>
        <h1>{{ pageTitle }}</h1>
        <p>本页维护库存余额、库存流水、仓库任务、库存预警、采购到货预备和采购收货预备；不直接生成应付、财务凭证或总账。</p>
        <p class="app-current-module-badge">当前操作模块：{{ currentWmsModuleName }}</p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">WMS库存流程导航</span>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isWmsNavActive(null) }" to="/wms">
          WMS库存管理
          <span v-if="isWmsNavActive(null)" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isWmsNavActive('balances') }" to="/wms/inventory-balances">
          库存余额
          <span v-if="isWmsNavActive('balances')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isWmsNavActive('transactions') }" to="/wms/inventory-transactions">
          库存流水
          <span v-if="isWmsNavActive('transactions')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isWmsNavActive('tasks') }" to="/wms/warehouse-tasks">
          仓库任务
          <span v-if="isWmsNavActive('tasks')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isWmsNavActive('warnings') }" to="/wms/stock-warnings">
          库存预警
          <span v-if="isWmsNavActive('warnings')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isWmsNavActive('receive') }" to="/wms/purchase-receive-preview">
          采购到货预备
          <span v-if="isWmsNavActive('receive')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/wms/purchase-receives">采购收货预备</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="route.path === '/wms'" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>库存总览</h2>
              <span>库存台账数据保存在 localStorage：wms-state-v1</span>
            </div>
            <el-button type="primary" @click="resetDemo">恢复演示数据</el-button>
          </div>
        </template>
        <div class="summary-grid">
          <el-card v-for="card in overviewCards" :key="card.title" shadow="never">
            <span>{{ card.title }}</span>
            <strong>{{ card.count }}</strong>
            <p>{{ card.desc }}</p>
            <el-button type="primary" @click="router.push(card.to)">进入</el-button>
          </el-card>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>功能入口</h2></template>
        <div class="button-row">
          <el-button type="primary" @click="router.push('/wms/inventory-balances')">库存余额</el-button>
          <el-button type="primary" @click="router.push('/wms/inventory-transactions')">库存流水</el-button>
          <el-button type="primary" @click="router.push('/wms/warehouse-tasks')">仓库任务</el-button>
          <el-button type="primary" @click="router.push('/wms/stock-warnings')">库存预警</el-button>
          <el-button type="primary" @click="router.push('/wms/purchase-receive-preview')">采购到货预备</el-button>
          <el-button type="primary" @click="router.push('/wms/purchase-receives')">采购收货预备</el-button>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>后续财务入口</h2></template>
        <p class="source-note">WMS 只负责到货、收货、库存和仓库任务；应付、核对、发票、应付账款草稿属于财务前置模块。</p>
        <div class="button-row">
          <el-button @click="router.push('/finance/payable-prepares')">采购应付预备</el-button>
          <el-button @click="router.push('/finance/payable-checks')">采购应付核对</el-button>
          <el-button @click="router.push('/finance/invoice-prepares')">采购发票预备</el-button>
          <el-button @click="router.push('/finance/ap-drafts')">采购应付账款草稿</el-button>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>数据来源说明</h2></template>
        <p class="source-note">WMS 当前物料、仓库、库位均来自制造业基础资料，不在本页新建基础资料。</p>
      </el-card>
    </section>

    <section v-else-if="currentDetailRecord" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ currentList.title }}详情</h2>
              <span>{{ detailRecordTitle }}</span>
            </div>
            <div class="button-row">
              <el-button @click="goCurrentList">返回列表</el-button>
              <el-button @click="goCurrentParent">返回上级</el-button>
              <el-button v-if="hasCurrentSource" type="primary" @click="goCurrentSource">{{ currentSourceButtonLabel }}</el-button>
            </div>
          </div>
        </template>
        <div class="info-grid">
          <article v-for="column in listColumns" :key="column.key">
            <span>{{ column.label }}</span>
            <strong>{{ formatCell(currentDetailRecord, column.key) }}</strong>
          </article>
        </div>
      </el-card>

      <el-card v-if="currentType === 'receive' && currentDetailRecord.items?.length" shadow="never">
        <template #header><h2>采购订单明细</h2></template>
        <el-table :data="currentDetailRecord.items" border stripe height="460">
          <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
          <el-table-column prop="sourceOrderNo" label="来源采购订单号" min-width="160" />
          <el-table-column prop="sourceOrderLineNo" label="来源订单行号" width="120" />
          <el-table-column prop="rootRequestNo" label="原始请购单号" min-width="150" />
          <el-table-column prop="purchaseDepartment" label="采购部门" min-width="130" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="160" />
          <el-table-column prop="specification" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="quantity" label="订单数量" width="100" />
          <el-table-column prop="pendingQty" label="待收货数量" width="110" />
          <el-table-column prop="planPrice" label="计划单价" width="100" />
          <el-table-column prop="planAmount" label="计划金额" width="110" />
          <el-table-column prop="sourceLineId" label="来源行ID" min-width="170" />
        </el-table>
      </el-card>
    </section>

    <section v-else-if="currentList" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ currentList.title }}</h2>
              <span>{{ currentList.subtitle }}</span>
            </div>
            <div class="button-row">
              <el-button v-if="currentType === 'balances'" type="primary" @click="openOpeningDialog">手工初始化库存</el-button>
              <el-button v-if="currentType === 'warnings'" type="primary" @click="generateWarnings">生成库存预警</el-button>
            </div>
          </div>
        </template>

        <div class="toolbar">
          <el-button @click="quickSearchVisible = !quickSearchVisible">
            {{ quickSearchVisible ? '收起快速搜索' : '展开快速搜索' }}
          </el-button>
          <span class="sort-help">快速搜索用于跨字段临时查找；精准查询请使用高级筛选。</span>
        </div>

        <div v-if="quickSearchVisible" class="toolbar">
          <el-autocomplete
            v-model="keyword"
            :fetch-suggestions="querySearchSuggestions"
            placeholder="搜索单号、供应商、物料、部门、状态"
            clearable
            @select="handleSuggestionSelect"
          />
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
            <el-option v-for="item in currentList.statuses" :key="item" :label="statusLabel(item)" :value="item" />
          </el-select>
          <el-button @click="clearFilters">重置</el-button>
        </div>

        <div class="toolbar">
          <el-button @click="resetSorting">清除排序</el-button>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ currentSortText }}</span>
          <el-button @click="advancedFilterVisible = !advancedFilterVisible">
            {{ advancedFilterVisible ? '收起高级筛选' : '展开高级筛选' }}
          </el-button>
          <el-button type="success" @click="exportCurrentList">导出当前结果</el-button>
        </div>

        <el-alert
          v-if="processDescription"
          :title="processDescription"
          type="info"
          show-icon
          :closable="false"
        />

        <div v-if="batchActions.length" class="batch-bar">
          <span>已选择 {{ selectedRows.length }} 条</span>
          <span v-if="currentType === 'receive'">可生成仓库收货任务 {{ wmsBatchCounts.task }} 条</span>
          <span v-if="currentType === 'receive'">可生成采购收货预备单 {{ wmsBatchCounts.receive }} 条</span>
          <span v-if="currentType === 'tasks'">可执行 {{ activeBatchExecutableCount }} 条</span>
          <span>将跳过 {{ selectedRows.length - activeBatchExecutableCount }} 条</span>
          <el-button size="small" @click="clearSelection">清空选择</el-button>
          <el-button
            v-for="action in batchActions"
            :key="action.label"
            size="small"
            :type="action.type || 'primary'"
            :disabled="action.disabled"
            :title="action.disabledReason || ''"
            @click="runBatchAction(action)"
          >
            {{ action.label }}
          </el-button>
        </div>

        <div v-if="batchResult" class="batch-result" :class="batchMessageType">
          <button type="button" @click="batchResult = null">关闭</button>
          <strong>批量操作完成：</strong>
          <span>操作名称：{{ batchResult.operationName }}</span>
          <span>已选择：{{ batchResult.total }} 条</span>
          <span>成功：{{ batchResult.successCount }} 条</span>
          <span>失败/跳过：{{ batchResult.failedCount }} 条</span>
          <template v-if="batchResult.failedReason?.length">
            <span>失败原因：</span>
            <ol>
              <li v-for="reason in batchResult.failedReason" :key="reason">{{ reason }}</li>
            </ol>
            <span>下一步建议：{{ batchResult.nextSuggestion }}</span>
          </template>
        </div>

        <div v-if="advancedFilterVisible" class="filter-grid">
          <div v-for="column in listColumns" :key="column.key" class="filter-item">
            <label>{{ column.label }}</label>
            <el-input
              v-if="columnFilterType(column) === 'text'"
              v-model="columnFilters[column.key].text"
              clearable
              placeholder="模糊筛选"
            />
            <el-date-picker
              v-else-if="columnFilterType(column) === 'date'"
              v-model="columnFilters[column.key].range"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              @change="handleDateFilterChange(column.key)"
            />
            <div v-else-if="columnFilterType(column) === 'number'" class="range-row">
              <el-input-number v-model="columnFilters[column.key].min" :precision="2" placeholder="最小" />
              <el-input-number v-model="columnFilters[column.key].max" :precision="2" placeholder="最大" />
            </div>
            <el-select
              v-else
              v-model="columnFilters[column.key].values"
              multiple
              filterable
              clearable
              collapse-tags
              placeholder="请选择"
            >
              <el-option v-for="option in columnFilterOptions(column)" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </div>
        </div>

        <el-alert
          v-if="currentType === 'receive' && !listRows.length"
          title="没有可收货采购订单：可能没有已审批或已下达采购订单，或订单没有明细，或订单已关闭/已取消/已完全收货。"
          type="warning"
          show-icon
          :closable="false"
        />
        <el-empty v-if="!pagedRows.length" description="暂无符合条件的数据" />
        <el-table v-else ref="listTableRef" :data="pagedRows" border stripe height="520" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column v-if="currentType === 'receive'" type="expand" width="48" fixed="left">
            <template #default="{ row }">
              <el-table :data="row.items || []" border size="small" class="nested-table" height="320">
                <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
                <el-table-column prop="sourceOrderNo" label="来源采购订单号" min-width="160" />
                <el-table-column prop="sourceOrderLineNo" label="来源订单行号" width="120" />
                <el-table-column prop="rootRequestNo" label="原始请购单号" min-width="150" />
                <el-table-column prop="purchaseDepartment" label="采购部门" min-width="130" />
                <el-table-column prop="materialCode" label="物料编码" min-width="130" />
                <el-table-column prop="materialName" label="物料名称" min-width="160" />
                <el-table-column prop="specification" label="规格型号" min-width="120" />
                <el-table-column prop="unit" label="单位" width="80" />
                <el-table-column prop="quantity" label="订单数量" width="100" />
                <el-table-column prop="pendingQty" label="待收货数量" width="110" />
                <el-table-column prop="planPrice" label="计划单价" width="100" />
                <el-table-column prop="planAmount" label="计划金额" width="110" />
                <el-table-column prop="actualPrice" label="实际单价" width="100" />
                <el-table-column prop="actualAmount" label="实际金额" width="110" />
                <el-table-column prop="sourceLineId" label="来源行ID" min-width="170" />
                <el-table-column prop="expectedDeliveryDate" label="期望交期" width="120" />
              </el-table>
            </template>
          </el-table-column>
          <el-table-column label="序号" width="70" fixed="left">
            <template #default="{ $index }">{{ globalIndex($index) }}</template>
          </el-table-column>
          <el-table-column v-for="column in listColumns" :key="column.key" :label="column.label" :min-width="column.width || 120">
            <template #header>
              <button class="sort-button" type="button" title="点击表头字段可升序/降序排序" @click="toggleSort(column.key)">
                {{ column.label }} {{ sortIcon(column.key) }}
              </button>
            </template>
            <template #default="{ row }">
              <el-tag v-if="column.key === 'status'" :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
              <el-tag v-else-if="column.key === 'level'" :type="row.level === 'red' ? 'danger' : 'warning'">{{ levelLabel(row.level) }}</el-tag>
              <el-tag v-else-if="column.key === 'deliveryUrgency'" :type="getUrgencyTagType(row.deliveryUrgency)" :style="getUrgencyStyle(row.deliveryUrgency)">
                {{ getUrgencyLabel(row.deliveryUrgency) }}
              </el-tag>
              <span v-else>{{ formatCell(row, column.key) }}</span>
            </template>
          </el-table-column>
          <el-table-column v-if="currentType === 'receive'" label="仓库收货任务" min-width="150">
            <template #default="{ row }">
              <el-tag :type="rowHasReceiveTask(row) ? 'success' : 'info'">{{ rowHasReceiveTask(row) ? '已生成' : '未生成' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column v-if="currentType === 'receive'" label="采购收货预备单" min-width="160">
            <template #default="{ row }">
              <el-tag :type="rowPurchaseReceive(row) ? 'success' : 'info'">{{ rowPurchaseReceive(row) ? '已生成' : '未生成' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(wmsActionColumnLabels)">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button v-if="currentType === 'balances'" size="small" class="app-action-button-sm" @click="router.push(`/wms/inventory-transactions?balance=${row.id}`)">查看流水</el-button>
                <el-button v-if="currentType === 'tasks' && row.status === 'pending'" size="small" class="app-action-button-sm" type="primary" @click="completeTask(row)">完成任务</el-button>
                <el-button v-if="currentType === 'tasks' && row.taskType === 'purchaseReceive'" size="small" class="app-action-button-lg" type="success" @click="createPurchaseReceiveFromTask(row)">由任务生成采购收货预备单</el-button>
                <el-button v-if="currentType === 'tasks' && row.status === 'pending'" size="small" class="app-action-button-sm" @click="cancelTask(row)">取消任务</el-button>
                <el-button v-if="currentType === 'warnings' && row.status === 'open'" size="small" class="app-action-button-sm" type="primary" @click="handleWarning(row)">处理预警</el-button>
                <el-button v-if="currentType === 'warnings' && row.status === 'open'" size="small" class="app-action-button-sm" @click="ignoreWarning(row)">忽略预警</el-button>
                <el-button v-if="detailRoute(row)" size="small" class="app-action-button-sm" @click="router.push(detailRoute(row))">详情</el-button>
                <el-button v-if="currentType === 'receive'" size="small" class="app-action-button-lg" @click="goSource(router, sourceRecordForRow(row), notify)">查看来源采购订单</el-button>
                <el-button v-if="currentType === 'receive' && !rowHasReceiveTask(row)" size="small" class="app-action-button-lg" type="primary" @click="createReceiveTask(row)">生成仓库收货任务</el-button>
                <el-button v-if="currentType === 'receive' && rowHasReceiveTask(row)" size="small" class="app-action-button-lg" @click="goWarehouseTask(row)">查看仓库收货任务</el-button>
                <el-button v-if="currentType === 'receive' && !rowPurchaseReceive(row)" size="small" class="app-action-button-lg" type="success" @click="createPurchaseReceive(row)">直接生成采购收货预备单</el-button>
                <el-button v-if="currentType === 'receive' && rowPurchaseReceive(row)" size="small" class="app-action-button-lg" @click="goPurchaseReceive(row)">查看采购收货预备单</el-button>
                <span v-if="!hasRowAction(row)" class="muted">只读</span>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-row">
          <span>共 {{ sortedRows.length }} 条</span>
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            layout="sizes, prev, pager, next"
            :total="sortedRows.length"
          />
        </div>
      </el-card>
    </section>

    <el-dialog v-model="openingDialogVisible" title="手工初始化库存" width="640px">
      <el-form :model="openingForm" label-width="120px">
        <el-form-item label="物料" required>
          <el-select v-model="openingForm.materialId" filterable @change="handleOpeningMaterialChange">
            <el-option v-for="item in materialOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="仓库" required>
          <el-select v-model="openingForm.warehouseId" filterable @change="handleOpeningWarehouseChange">
            <el-option v-for="item in warehouseOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="库位" required>
          <el-select v-model="openingForm.locationId" filterable>
            <el-option v-for="item in locationOptions" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="批号">
          <el-input v-model="openingForm.batchNo" />
        </el-form-item>
        <el-form-item label="初始化数量" required>
          <el-input-number v-model="openingForm.quantity" :min="0" :precision="2" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="openingForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="openingDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitOpening">保存并写入流水</el-button>
      </template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getEmployeeOptions,
  getEnabledMaterials,
  getEnabledWarehouses,
  getLocationOptions,
} from '../manufacturing/manufacturingReferenceService.js'
import {
  applyPagination,
  applySorting,
  buildFilterOptions,
  exportRowsToCsv as exportRowsToCsvUtil,
} from '../manufacturing/foundationTableUtils.js'
import { buildMultiFieldSuggestions, filterSuggestions } from '../runtime/filterSuggestionEngine.js'
import {
  formatBusinessDateTime,
  getInventoryStatusLabel,
  getQualityStatusLabel,
  getTransactionTypeLabel,
  matchBusinessLabelOrValue,
} from '../runtime/businessValueLabelEngine.js'
import {
  getSourceButtonLabel,
  goList,
  goParent,
  goSource,
  hasSourceRoute,
} from '../runtime/navigationRules.js'
import {
  applyInventoryTransaction,
  batchCancelWarehouseTasks,
  batchCompleteWarehouseTasks,
  batchCreateWarehouseTasksFromPurchaseOrders,
  batchPostInboundFromWarehouseTasks,
  cancelWarehouseTask,
  completeWarehouseTask,
  createPurchaseReceiveTaskFromScmPurchaseOrder,
  generateStockWarnings,
  getReceivableScmPurchaseOrders,
  getInventoryBalanceById,
  getInventoryTransactionById,
  getWarehouseTaskById,
  getWarehouseTaskBusinessType,
  getWmsState,
  handleStockWarning,
  ignoreStockWarning,
  resetWmsState,
} from '../wms/wmsStore.js'
import {
  batchCreatePurchaseReceivesFromPurchaseOrders,
  createPurchaseReceiveFromScmPurchaseOrder,
  createPurchaseReceiveFromWarehouseTask,
  listPurchaseReceives,
} from '../wms/purchaseReceiveStore.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
import {
  calculateDeliveryUrgency,
  getUrgencyLabel,
  getUrgencyTagType,
  getUrgencyStyle,
} from '../runtime/urgencyEngine.js'

const route = useRoute()
const router = useRouter()
const wmsState = ref(getWmsState())
const keyword = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const message = ref('')
const messageType = ref('success')
const selectedRows = ref([])
const listTableRef = ref(null)
const batchResult = ref(null)
const batchMessageType = ref('success')
const openingDialogVisible = ref(false)
const advancedFilterVisible = ref(false)
const quickSearchVisible = ref(false)
const columnFilters = reactive({})
const sortState = reactive({ key: '', direction: 'asc' })
const openingForm = reactive({
  materialId: '',
  warehouseId: '',
  locationId: '',
  batchNo: 'BATCH-OPENING',
  quantity: 0,
  remark: '',
})

const configs = {
  balances: {
    path: '/wms/inventory-balances',
    title: '库存余额',
    subtitle: '库存余额只由库存流水或初始化动作更新，采购订单不会直接修改库存。',
    statuses: ['normal', 'lowStock', 'overStock', 'locked', 'disabled'],
    rows: () => wmsState.value.inventoryBalances,
    columns: [
      { key: 'materialCode', label: '物料编码' },
      { key: 'materialName', label: '物料名称', width: 160 },
      { key: 'specification', label: '规格型号' },
      { key: 'unit', label: '单位' },
      { key: 'warehouseName', label: '仓库' },
      { key: 'locationName', label: '库位' },
      { key: 'batchNo', label: '批号' },
      { key: 'qualityStatus', label: '质量状态', filterType: 'enum' },
      { key: 'quantity', label: '当前库存', filterType: 'number' },
      { key: 'availableQuantity', label: '可用数量', filterType: 'number' },
      { key: 'lockedQuantity', label: '锁定数量', filterType: 'number' },
      { key: 'safetyStock', label: '安全库存', filterType: 'number' },
      { key: 'maxStock', label: '最高库存', filterType: 'number' },
      { key: 'sourceInspectionNo', label: '来源检验单', width: 150 },
      { key: 'sourceReceiveNo', label: '来源收货单', width: 150 },
      { key: 'sourcePurchaseOrderNo', label: '来源采购订单', width: 150 },
      { key: 'rootRequestNo', label: '原始请购单', width: 150 },
      { key: 'status', label: '状态', filterType: 'enum' },
      { key: 'lastTransactionAt', label: '最近交易时间', filterType: 'date', width: 180 },
    ],
  },
  transactions: {
    path: '/wms/inventory-transactions',
    title: '库存流水',
    subtitle: '所有库存变更必须通过库存流水记录变动前后数量。',
    statuses: [],
    rows: () => wmsState.value.inventoryTransactions,
    columns: [
      { key: 'transactionNo', label: '流水号', width: 170 },
      { key: 'transactionDate', label: '交易日期', filterType: 'date' },
      { key: 'transactionType', label: '类型', filterType: 'enum' },
      { key: 'materialName', label: '物料' },
      { key: 'warehouseName', label: '仓库' },
      { key: 'locationName', label: '库位' },
      { key: 'batchNo', label: '批号' },
      { key: 'qualityStatus', label: '质量状态', filterType: 'enum' },
      { key: 'quantity', label: '变动数量', filterType: 'number' },
      { key: 'beforeQuantity', label: '变动前数量', filterType: 'number' },
      { key: 'afterQuantity', label: '变动后数量', filterType: 'number' },
      { key: 'sourceModule', label: '来源模块', filterType: 'enum' },
      { key: 'sourceInspectionNo', label: '来源检验单', width: 150 },
      { key: 'sourceReceiveNo', label: '来源收货单', width: 150 },
      { key: 'sourcePurchaseOrderNo', label: '来源采购订单', width: 150 },
      { key: 'rootRequestNo', label: '原始请购单', width: 150 },
      { key: 'operator', label: '操作人', filterType: 'enum' },
      { key: 'remark', label: '备注', width: 180 },
    ],
  },
  tasks: {
    path: '/wms/warehouse-tasks',
    title: '仓库任务',
    subtitle: '本页只做基础任务流转，不做复杂 PDA 作业。',
    statuses: ['pending', 'processing', 'done', 'cancelled'],
    rows: () => wmsState.value.warehouseTasks,
    columns: [
      { key: 'taskNo', label: '任务号', width: 170 },
      { key: 'taskType', label: '任务类型', filterType: 'enum' },
      { key: 'businessType', label: '业务类型', filterType: 'enum', width: 170 },
      { key: 'businessStatus', label: '业务阶段', width: 150 },
      { key: 'sourceTaskNo', label: '仓库任务号', width: 170 },
      { key: 'sourceNo', label: '来源单据' },
      { key: 'sourceInspectionNo', label: '来源检验单', width: 150 },
      { key: 'sourceReceiveNo', label: '来源收货单', width: 150 },
      { key: 'sourcePurchaseOrderNo', label: '来源采购订单', width: 150 },
      { key: 'rootRequestNo', label: '原始请购单', width: 150 },
      { key: 'supplierName', label: '供应商' },
      { key: 'materialName', label: '物料' },
      { key: 'warehouseName', label: '仓库' },
      { key: 'locationName', label: '库位' },
      { key: 'plannedQuantity', label: '计划数量', filterType: 'number' },
      { key: 'completedQuantity', label: '完成数量', filterType: 'number' },
      { key: 'status', label: '状态', filterType: 'enum' },
      { key: 'operatorId', label: '操作人', filterType: 'enum' },
      { key: 'plannedExecutionDate', label: '计划执行日期', filterType: 'date', width: 180 },
      { key: 'createdAt', label: '创建时间', filterType: 'date', width: 180 },
      { key: 'completedAt', label: '完成时间', filterType: 'date', width: 180 },
      { key: 'isDone', label: '是否已完成', filterType: 'enum' },
      { key: 'isCancelled', label: '是否已取消', filterType: 'enum' },
    ],
  },
  warnings: {
    path: '/wms/stock-warnings',
    title: '库存预警',
    subtitle: '根据库存余额、安全库存、最高库存生成预警。',
    statuses: ['open', 'handled', 'ignored'],
    rows: () => wmsState.value.stockWarnings,
    columns: [
      { key: 'warningNo', label: '预警单号', width: 170 },
      { key: 'materialCode', label: '物料编码' },
      { key: 'materialName', label: '物料名称', width: 160 },
      { key: 'warehouseName', label: '仓库' },
      { key: 'locationName', label: '库位' },
      { key: 'batchNo', label: '批号' },
      { key: 'warningType', label: '预警类型', filterType: 'enum' },
      { key: 'level', label: '预警级别', filterType: 'enum' },
      { key: 'currentQuantity', label: '当前库存', filterType: 'number' },
      { key: 'safetyStock', label: '安全库存', filterType: 'number' },
      { key: 'maxStock', label: '最高库存', filterType: 'number' },
      { key: 'title', label: '预警标题', width: 180 },
      { key: 'content', label: '预警内容', width: 220 },
      { key: 'status', label: '状态', filterType: 'enum' },
      { key: 'createdAt', label: '创建时间', filterType: 'date', width: 180 },
      { key: 'handledAt', label: '处理时间', filterType: 'date', width: 180 },
      { key: 'handlerId', label: '处理人', filterType: 'enum' },
      { key: 'isHandled', label: '是否已处理', filterType: 'enum' },
      { key: 'isIgnored', label: '是否已忽略', filterType: 'enum' },
    ],
  },
  receive: {
    path: '/wms/purchase-receive-preview',
    title: '采购到货预备',
    subtitle: '读取 SCM 已下达采购订单，可生成仓库收货任务或采购收货预备单；两种方式都不直接增加库存。',
    statuses: ['approved'],
    rows: () => getReceivableScmPurchaseOrders(),
    columns: [
      { key: 'poNo', label: '采购订单号', width: 170 },
      { key: 'rootRequestNo', label: '原始请购单号', width: 160 },
      { key: 'supplierName', label: '供应商' },
      { key: 'buyerName', label: '采购员' },
      { key: 'requestDepartment', label: '请购部门' },
      { key: 'demandDepartment', label: '需求部门' },
      { key: 'purchaseDepartment', label: '采购部门' },
      { key: 'materialCodes', label: '物料编码', width: 160 },
      { key: 'materialNames', label: '物料名称', width: 180 },
      { key: 'specifications', label: '规格型号', width: 160 },
      { key: 'lineCount', label: '明细行数', filterType: 'number' },
      { key: 'totalQuantity', label: '总数量', filterType: 'number' },
      { key: 'receivableQty', label: '可收货数量', filterType: 'number' },
      { key: 'planAmount', label: '计划金额', filterType: 'number' },
      { key: 'actualAmount', label: '实际金额', filterType: 'number' },
      { key: 'plannedArrivalDate', label: '计划到货日期', filterType: 'date' },
      { key: 'deliveryUrgency', label: '交期紧急程度', filterType: 'enum', sortType: 'urgency', width: 140 },
      { key: 'hasReceiveTask', label: '是否已生成仓库收货任务', filterType: 'enum', width: 190 },
      { key: 'hasPurchaseReceive', label: '是否已生成采购收货预备单', filterType: 'enum', width: 210 },
      { key: 'receiveStage', label: '收货阶段', width: 150 },
      { key: 'status', label: '状态', filterType: 'enum' },
      { key: 'sourceTypeLabel', label: '来源类型', filterType: 'enum' },
    ],
  },
}

const currentType = computed(() => {
  if (route.path.includes('inventory-transaction')) return 'transactions'
  if (route.path.includes('warehouse-task')) return 'tasks'
  if (route.path.includes('stock-warning')) return 'warnings'
  if (route.path.includes('purchase-receive-preview')) return 'receive'
  if (route.path.includes('inventory-balance')) return 'balances'
  return ''
})
const currentList = computed(() => configs[currentType.value] || null)
const pageTitle = computed(() => currentList.value?.title || 'WMS库存管理')
const currentWmsModuleName = computed(() => currentList.value?.title || 'WMS库存管理')
const wmsActionColumnLabels = computed(() => {
  if (currentType.value === 'balances') return ['查看流水']
  if (currentType.value === 'tasks') return ['完成任务', '由任务生成采购收货预备单', '取消任务', '详情']
  if (currentType.value === 'warnings') return ['处理预警', '忽略预警']
  if (currentType.value === 'receive') return ['查看来源采购订单', '生成仓库收货任务', '直接生成采购收货预备单']
  return ['详情']
})

function isWmsNavActive(type) {
  if (!type) return !currentType.value
  return currentType.value === type
}
const listRows = computed(() => currentList.value ? currentList.value.rows().map(enrichWmsRow) : [])
const listColumns = computed(() => currentList.value?.columns || [])
const currentPageType = computed(() => ({
  balances: 'inventoryBalances',
  transactions: 'inventoryTransactions',
  tasks: 'warehouseTasks',
  receive: 'purchaseReceivePreview',
  warnings: 'stockWarnings',
}[currentType.value] || ''))
const currentDetailRecord = computed(() => {
  if (!route.params.id || !currentType.value) return null
  const id = route.params.id
  if (currentType.value === 'balances') return getInventoryBalanceById(id)
  if (currentType.value === 'transactions') return getInventoryTransactionById(id)
  if (currentType.value === 'tasks') return getWarehouseTaskById(id)
  if (currentType.value === 'receive') return getReceivableScmPurchaseOrders().find((item) => String(item.id) === String(id)) || null
  return null
})
const detailRecordTitle = computed(() => {
  const row = currentDetailRecord.value
  return row?.poNo || row?.taskNo || row?.transactionNo || row?.materialName || row?.id || '-'
})
const currentSourceRecord = computed(() => sourceRecordForRow(currentDetailRecord.value))
const hasCurrentSource = computed(() => hasSourceRoute(currentSourceRecord.value))
const currentSourceButtonLabel = computed(() => getSourceButtonLabel(currentSourceRecord.value))

const overviewCards = computed(() => {
  const todayCount = wmsState.value.inventoryTransactions.filter((item) => item.transactionDate === today()).length
  const warnings = wmsState.value.stockWarnings.filter((item) => item.status === 'open')
  return [
    { title: '物料库存项数量', count: wmsState.value.inventoryBalances.length, desc: '当前库存余额行数', to: '/wms/inventory-balances' },
    { title: '当前总库存数量', count: wmsState.value.inventoryBalances.reduce((sum, item) => sum + Number(item.quantity || 0), 0), desc: '全部库存余额数量汇总', to: '/wms/inventory-balances' },
    { title: '低库存预警数量', count: warnings.filter((item) => item.warningType === 'lowStock').length, desc: '低于安全库存的预警', to: '/wms/stock-warnings' },
    { title: '超库存预警数量', count: warnings.filter((item) => item.warningType === 'overStock').length, desc: '高于最高库存的预警', to: '/wms/stock-warnings' },
    { title: '近效期预警数量', count: warnings.filter((item) => item.warningType === 'nearExpiry').length, desc: '临近有效期的预警', to: '/wms/stock-warnings' },
    { title: '待处理仓库任务', count: wmsState.value.warehouseTasks.filter((item) => ['pending', 'processing'].includes(item.status)).length, desc: '未完成的仓库任务', to: '/wms/warehouse-tasks' },
    { title: '今日库存流水', count: todayCount, desc: '今日形成的库存流水', to: '/wms/inventory-transactions' },
    { title: 'SCM待收货采购订单', count: getReceivableScmPurchaseOrders().length, desc: '已下达，待生成仓库收货任务或采购收货预备单', to: '/wms/purchase-receive-preview' },
    { title: '采购收货预备单', count: '预备', desc: '记录预计收货，不直接入库', to: '/wms/purchase-receives' },
  ]
})

const filteredRows = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const quickFiltered = listRows.value.filter((row) => {
    const matchStatus = !statusFilter.value || row.status === statusFilter.value
    const searchable = listColumns.value.map((column) => formatCell(row, column.key)).join(' ')
    return matchStatus && (!text || `${JSON.stringify(row)} ${searchable}`.toLowerCase().includes(text))
  })
  return applyWmsColumnFilters(quickFiltered)
})
const sortedRows = computed(() => applySorting(filteredRows.value, sortState, listColumns.value))
const pagedRows = computed(() => applyPagination(sortedRows.value, currentPage.value, pageSize.value))
const selectedIds = computed(() => selectedRows.value.map((row) => row.id).filter(Boolean))
const currentSortText = computed(() => {
  if (!sortState.key) return '当前排序：默认顺序'
  const column = listColumns.value.find((item) => item.key === sortState.key)
  return `当前排序：${column?.label || sortState.key} / ${sortState.direction === 'desc' ? '降序' : '升序'}`
})
const purchaseReceives = computed(() => listPurchaseReceives())
const processDescription = computed(() => ({
  receive: '采购到货预备流程：采购订单已下达 -> 生成仓库收货任务 / 直接生成采购收货预备单 -> 提交收货 -> QMS 来料检验。本页只安排到货和收货预备，不直接入库、不生成应付。',
  tasks: '仓库任务流程：任务生成 -> 仓库执行 -> 完成任务 -> 进入下一业务动作。',
  balances: '库存余额流程：库存流水 -> 库存余额 -> 库存查询 / 库存分析。库存余额只反映现存量和可用量，不生成应付或财务凭证。',
  transactions: '库存流水流程：检验合格入库 / 让步接收入库 -> 库存流水 -> 库存余额 -> 应付预备。库存流水是库存变动记录，不是应付单或财务凭证。',
  warnings: '库存预警流程：库存余额 -> 库存预警 -> 处理 / 忽略 / 关闭预警。',
})[currentType.value] || '')
const wmsBatchCounts = computed(() => {
  if (currentType.value === 'receive') {
    return {
      task: selectedRows.value.filter((row) => !rowHasReceiveTask(row)).length,
      receive: selectedRows.value.filter((row) => !rowPurchaseReceive(row)).length,
    }
  }
  if (currentType.value === 'tasks') {
    return {
      complete: selectedRows.value.filter((row) => ['pending', 'processing'].includes(row.status)).length,
      cancel: selectedRows.value.filter((row) => !['done', 'cancelled'].includes(row.status)).length,
      inbound: selectedRows.value.filter((row) => getWarehouseTaskBusinessType(row) === 'qualifiedInboundPrepare').length,
    }
  }
  return { task: 0, receive: 0, complete: 0, cancel: 0, inbound: 0 }
})

function applyWmsColumnFilters(rows = []) {
  return rows.filter((row) => listColumns.value.every((column) => {
    const filter = columnFilters[column.key] || {}
    const type = columnFilterType(column)
    const rawValue = row[column.key]
    const displayValue = formatCell(row, column.key)
    if (type === 'number') {
      const min = filter.min === '' || filter.min == null ? null : Number(filter.min)
      const max = filter.max === '' || filter.max == null ? null : Number(filter.max)
      const number = Number(rawValue ?? 0)
      if (min != null && number < min) return false
      if (max != null && number > max) return false
      return true
    }
    if (type === 'date') {
      const start = filter.start ? new Date(filter.start) : null
      const end = filter.end ? new Date(`${filter.end}T23:59:59`) : null
      if (!start && !end) return true
      const date = rawValue ? new Date(rawValue) : null
      if (!date || Number.isNaN(date.getTime())) return false
      if (start && date < start) return false
      if (end && date > end) return false
      return true
    }
    if (type === 'enum') {
      const values = Array.isArray(filter.values) ? filter.values.filter(Boolean) : []
      if (!values.length) return true
      return values.some((value) => (
        String(value) === String(rawValue)
        || String(value) === String(displayValue)
        || matchBusinessLabelOrValue(rawValue, value, businessDictionaryForColumn(column.key))
      ))
    }
    const text = String(filter.text || '').trim().toLowerCase()
    return !text || `${rawValue ?? ''} ${displayValue}`.toLowerCase().includes(text)
  }))
}
const batchActions = computed(() => {
  if (currentType.value === 'receive') {
    return [
      { label: '批量生成仓库收货任务', executableCount: wmsBatchCounts.value.task, disabled: !wmsBatchCounts.value.task, disabledReason: selectedRows.value.length ? '所选记录均已生成仓库收货任务。' : '请先选择记录。', handler: () => batchCreateWarehouseTasksFromPurchaseOrders(selectedIds.value) },
      { label: '批量生成采购收货预备单', type: 'success', executableCount: wmsBatchCounts.value.receive, disabled: !wmsBatchCounts.value.receive, disabledReason: selectedRows.value.length ? '所选记录均已生成采购收货预备单。' : '请先选择记录。', handler: () => batchCreatePurchaseReceivesFromPurchaseOrders(selectedIds.value) },
    ]
  }
  if (currentType.value === 'tasks') {
    return [
      { label: '批量完成任务', executableCount: wmsBatchCounts.value.complete, disabled: !wmsBatchCounts.value.complete, disabledReason: '所选任务没有可完成记录。', handler: () => batchCompleteWarehouseTasks(selectedIds.value) },
      { label: '批量取消任务', type: 'warning', executableCount: wmsBatchCounts.value.cancel, disabled: !wmsBatchCounts.value.cancel, disabledReason: '所选任务没有可取消记录。', handler: () => batchCancelWarehouseTasks(selectedIds.value) },
      { label: '批量确认入库', type: 'success', executableCount: wmsBatchCounts.value.inbound, disabled: !wmsBatchCounts.value.inbound, disabledReason: '所选任务没有检验合格入库预备任务。', handler: () => batchPostInboundFromWarehouseTasks(selectedIds.value) },
    ]
  }
  return []
})

function enrichWmsRow(row = {}) {
  if (currentType.value === 'tasks') {
    return {
      ...row,
      sourceTaskNo: row.taskNo,
      supplierName: row.supplierName || row.sourceSupplierName || '',
      plannedExecutionDate: row.plannedExecutionDate || row.planExecutionDate || row.createdAt || '',
      isDone: row.status === 'done' ? '是' : '否',
      isCancelled: row.status === 'cancelled' ? '是' : '否',
    }
  }
  if (currentType.value === 'warnings') {
    return {
      ...row,
      warningNo: row.warningNo || row.id,
      currentQuantity: row.currentQuantity ?? row.quantity ?? row.availableQuantity ?? 0,
      isHandled: row.status === 'handled' ? '是' : '否',
      isIgnored: row.status === 'ignored' ? '是' : '否',
    }
  }
  if (currentType.value !== 'receive') return row
  const lines = row.items || row.lines || []
  return {
    ...row,
    materialCodes: [...new Set(lines.map((item) => item.materialCode).filter(Boolean))].join('、'),
    materialNames: [...new Set(lines.map((item) => item.materialName).filter(Boolean))].join('、'),
    specifications: [...new Set(lines.map((item) => item.specification || item.spec).filter(Boolean))].join('、'),
    hasReceiveTask: rowHasReceiveTask(row) ? '是' : '否',
    hasPurchaseReceive: rowPurchaseReceive(row) ? '是' : '否',
    sourceTypeLabel: 'SCM采购订单',
    deliveryUrgency: calculateDeliveryUrgency({
      ...row,
      expectedDeliveryDate: row.expectedDeliveryDate || row.plannedArrivalDate,
      planDeliveryDate: row.planDeliveryDate || row.plannedArrivalDate,
    }),
  }
}
const activeBatchExecutableCount = computed(() => Math.max(...batchActions.value.map((action) => action.executableCount || 0), 0))

function handleSelectionChange(rows) {
  selectedRows.value = rows || []
}

function clearSelection() {
  selectedRows.value = []
  listTableRef.value?.clearSelection?.()
}

function rowReceiveTask(row) {
  return (wmsState.value.warehouseTasks || []).find((task) => task.sourceType === 'scmPurchaseOrder' && String(task.sourceId) === String(row.id) && task.status !== 'cancelled')
}

function rowHasReceiveTask(row) {
  return Boolean(rowReceiveTask(row))
}

function rowPurchaseReceive(row) {
  return purchaseReceives.value.find((item) => item.sourceType === 'scmPurchaseOrder' && String(item.sourceOrderId) === String(row.id) && item.status !== 'cancelled')
}

function goWarehouseTask(row) {
  const task = rowReceiveTask(row)
  if (!task) return notify('未找到仓库收货任务。', 'warning')
  router.push(`/wms/warehouse-task/${task.id}`)
}

function goPurchaseReceive(row) {
  const receive = rowPurchaseReceive(row)
  if (!receive) return notify('未找到采购收货预备单。', 'warning')
  router.push(`/wms/purchase-receive/${receive.id}`)
}

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('收货预备')) return '建议先处理收货预备，再重新执行批量操作。'
  if (text.includes('已生成')) return '建议点击对应行查看已生成单据或任务。'
  if (text.includes('状态')) return '建议检查当前状态后再执行批量操作。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, action = {}) {
  const failedReason = result.failedReason || []
  return {
    operationName: action.label || result.operationName || '批量操作',
    total: result.total ?? selectedIds.value.length,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    failedReason,
    nextSuggestion: nextBatchSuggestion(failedReason),
  }
}

function runBatchAction(action) {
  if (!selectedIds.value.length) {
    notify('请先选择要批量处理的记录。', 'warning')
    return
  }
  if (action.disabled) {
    notify(action.disabledReason || '所选记录没有可执行数据。', 'warning')
    return
  }
  const result = action.handler()
  refresh()
  clearSelection()
  batchResult.value = normalizeBatchResult(result || {}, action)
  batchMessageType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

const materialOptions = computed(() => getEnabledMaterials().map((item) => ({ ...item, name: `${item.code || item.id} / ${item.raw?.name || item.name}` })))
const warehouseOptions = computed(() => getEnabledWarehouses().map((item) => ({ ...item, name: `${item.code || item.id} / ${item.raw?.name || item.name}` })))
const locationOptions = computed(() => getLocationOptions(openingForm.warehouseId))

function today() {
  return new Date().toISOString().slice(0, 10)
}

function employeeName(id) {
  const employee = getEmployeeOptions().find((item) => String(item.id) === String(id))
  return employee?.name || id || '-'
}

function statusLabel(status) {
  if (currentType.value === 'balances') return getInventoryStatusLabel(status)
  return {
    normal: '正常',
    lowStock: '低库存',
    overStock: '超库存',
    locked: '已锁定',
    disabled: '已停用',
    pending: '待处理',
    processing: '处理中',
    done: '已完成',
    cancelled: '已取消',
    open: '待处理',
    handled: '已处理',
    ignored: '已忽略',
    approved: '已审批',
    converted: '已转单',
    issued: '已下达',
    released: '已释放',
    ordered: '已订购',
    partiallyReceived: '部分收货',
    fullyReceived: '完全收货',
  }[status] || status || '-'
}

function statusType(status) {
  return {
    normal: 'success',
    lowStock: 'danger',
    overStock: 'warning',
    locked: 'warning',
    disabled: 'info',
    pending: 'warning',
    processing: 'primary',
    done: 'success',
    cancelled: 'info',
    open: 'danger',
    handled: 'success',
    ignored: 'info',
    approved: 'success',
    converted: 'success',
    issued: 'success',
    partiallyReceived: 'warning',
    fullyReceived: 'info',
  }[status] || 'info'
}

function levelLabel(level) {
  return { yellow: '黄色', red: '红色' }[level] || level || '-'
}

function transactionTypeLabel(type) {
  return getTransactionTypeLabel(type)
}

function taskTypeLabel(type) {
  return {
    purchaseReceive: '采购收货',
    qualifiedInboundPrepare: '检验合格入库预备',
    move: '移库',
    count: '盘点',
    adjust: '调整',
  }[type] || type || '-'
}

function businessTypeLabel(type) {
  return {
    purchaseReceivePrepare: '采购收货预备',
    incomingInspection: '来料检验',
    qualifiedInboundPrepare: '检验合格入库预备',
    inventoryPosting: '库存入库',
  }[type] || type || '-'
}

function warningTypeLabel(type) {
  return {
    lowStock: '低库存',
    overStock: '超库存',
    expired: '已过期',
    nearExpiry: '近效期',
    negativeStock: '负库存',
    locked: '锁定异常',
    other: '其他',
  }[type] || type || '-'
}

function formatCell(row, key) {
  if (key === 'deliveryUrgency') return getUrgencyLabel(row[key])
  if (['plannedArrivalDate', 'planDeliveryDate', 'expectedDeliveryDate', 'expectedReceiveDate'].includes(key) && !row[key]) return '未设日期'
  if (key.toLowerCase().includes('date') || key.endsWith('At')) return formatBusinessDateTime(row[key])
  if (key === 'status') return statusLabel(row[key])
  if (key === 'level') return levelLabel(row[key])
  if (key === 'transactionType') return transactionTypeLabel(row[key])
  if (key === 'qualityStatus') return qualityStatusLabel(row[key])
  if (key === 'taskType') return taskTypeLabel(row[key])
  if (key === 'businessType') return businessTypeLabel(getWarehouseTaskBusinessType(row))
  if (key === 'warningType') return warningTypeLabel(row[key])
  if (['operator', 'operatorId', 'handlerId'].includes(key)) return employeeName(row[key])
  if (key === 'materialId') return row.materialName || row.materialCode || row[key] || '-'
  if (key === 'warehouseId') return row.warehouseName || row[key] || '-'
  if (key === 'locationId') return row.locationName || row[key] || '-'
  if (['quantity', 'availableQuantity', 'lockedQuantity', 'safetyStock', 'maxStock', 'beforeQuantity', 'afterQuantity', 'plannedQuantity', 'completedQuantity', 'totalAmount', 'totalQuantity', 'receivableQuantity', 'receivableQty', 'planAmount', 'actualAmount', 'currentQuantity'].includes(key)) {
    return Number(row[key] || 0).toFixed(2)
  }
  return row[key] ?? '-'
}

function qualityStatusLabel(status) {
  return getQualityStatusLabel(status)
}

function businessDictionaryForColumn(key) {
  if (key === 'qualityStatus') {
    return {
      qualified: getQualityStatusLabel('qualified'),
      concession: getQualityStatusLabel('concession'),
      pending: getQualityStatusLabel('pending'),
      rejected: getQualityStatusLabel('rejected'),
      unqualified: getQualityStatusLabel('unqualified'),
      returnPending: getQualityStatusLabel('returnPending'),
      scrapped: getQualityStatusLabel('scrapped'),
      reworkPending: getQualityStatusLabel('reworkPending'),
      unknown: getQualityStatusLabel('unknown'),
    }
  }
  if (key === 'transactionType') {
    return {
      purchaseInspectionIn: getTransactionTypeLabel('purchaseInspectionIn'),
      concessionIn: getTransactionTypeLabel('concessionIn'),
      purchaseReceivePrepare: getTransactionTypeLabel('purchaseReceivePrepare'),
      incomingInspection: getTransactionTypeLabel('incomingInspection'),
      qualifiedInboundPrepare: getTransactionTypeLabel('qualifiedInboundPrepare'),
      inventoryPosting: getTransactionTypeLabel('inventoryPosting'),
      adjustment: getTransactionTypeLabel('adjustment'),
      adjust: getTransactionTypeLabel('adjust'),
      transfer: getTransactionTypeLabel('transfer'),
      lock: getTransactionTypeLabel('lock'),
      unlock: getTransactionTypeLabel('unlock'),
      manualInit: getTransactionTypeLabel('manualInit'),
      opening: getTransactionTypeLabel('opening'),
      manualIn: getTransactionTypeLabel('manualIn'),
      manualOut: getTransactionTypeLabel('manualOut'),
      other: getTransactionTypeLabel('other'),
    }
  }
  if (key === 'status' && currentType.value === 'balances') {
    return {
      normal: getInventoryStatusLabel('normal'),
      lowStock: getInventoryStatusLabel('lowStock'),
      overStock: getInventoryStatusLabel('overStock'),
      locked: getInventoryStatusLabel('locked'),
      zero: getInventoryStatusLabel('zero'),
      disabled: getInventoryStatusLabel('disabled'),
    }
  }
  return {}
}

function detailRoute(row) {
  if (!row?.id) return ''
  if (currentType.value === 'balances') return `/wms/inventory-balance/${row.id}`
  if (currentType.value === 'transactions') return `/wms/inventory-transaction/${row.id}`
  if (currentType.value === 'tasks') return `/wms/warehouse-task/${row.id}`
  if (currentType.value === 'receive') return `/wms/purchase-receive-preview/${row.id}`
  return ''
}

function sourceRecordForRow(row = {}) {
  if (!row) return {}
  if (currentType.value === 'receive' || row.poNo) {
    return { sourceType: 'scmPurchaseOrder', sourceOrderId: row.id, sourceOrderNo: row.poNo }
  }
  return row
}

function goCurrentList() {
  goList(router, 'wms', currentPageType.value)
}

function goCurrentParent() {
  goParent(router, 'wms')
}

function goCurrentSource() {
  goSource(router, currentSourceRecord.value, notify)
}

function querySearchSuggestions(queryString, callback) {
  const baseRows = (keyword.value || statusFilter.value || hasActiveColumnFilters()) ? filteredRows.value : listRows.value
  const records = baseRows.flatMap((row) => [
    {
      ...row,
      statusLabel: statusLabel(row.status),
      qualityStatusLabel: qualityStatusLabel(row.qualityStatus),
      transactionTypeLabel: transactionTypeLabel(row.transactionType),
      lastTransactionAtText: formatCell(row, 'lastTransactionAt'),
      transactionDateText: formatCell(row, 'transactionDate'),
    },
    ...(row.items || []).map((item) => ({
      sourceNo: row.poNo,
      supplierName: row.supplierName,
      departmentName: row.departmentName,
      status: statusLabel(row.status),
      materialCode: item.materialCode,
      materialName: item.materialName,
    })),
  ])
  const suggestions = buildMultiFieldSuggestions(records, ['poNo', 'sourceNo', 'supplierName', 'departmentName', 'status', 'statusLabel', 'qualityStatus', 'qualityStatusLabel', 'transactionType', 'transactionTypeLabel', 'materialCode', 'materialName', 'warehouseName'])
  callback(filterSuggestions(queryString, suggestions))
}

function handleSuggestionSelect(item) {
  keyword.value = item.value
  currentPage.value = 1
}

function inferColumnFilterType(key) {
  if (key === 'deliveryUrgency') return 'enum'
  if (['status', 'level', 'transactionType', 'taskType', 'businessType', 'warningType', 'sourceModule', 'operator', 'operatorId', 'handlerId', 'qualityStatus', 'hasReceiveTask', 'hasPurchaseReceive', 'sourceTypeLabel', 'isDone', 'isCancelled', 'isHandled', 'isIgnored'].includes(key)) return 'enum'
  if (key.toLowerCase().includes('date') || key.endsWith('At')) return 'date'
  if (['quantity', 'availableQuantity', 'availableQty', 'lockedQuantity', 'lockedQty', 'safetyStock', 'maxStock', 'beforeQuantity', 'afterQuantity', 'beforeQty', 'afterQty', 'plannedQuantity', 'completedQuantity', 'totalAmount', 'totalQuantity', 'lineCount', 'receivableQty'].includes(key)) return 'number'
  return 'text'
}

function ensureColumnFilter(key) {
  if (!columnFilters[key]) {
    columnFilters[key] = { text: '', start: '', end: '', range: [], min: null, max: null, values: [] }
  }
  return columnFilters[key]
}

function syncColumnFilters() {
  listColumns.value.forEach((column) => ensureColumnFilter(column.key))
  Object.keys(columnFilters).forEach((key) => {
    if (!listColumns.value.some((column) => column.key === key)) delete columnFilters[key]
  })
}

function columnFilterType(column) {
  ensureColumnFilter(column.key)
  return column.filterType || inferColumnFilterType(column.key)
}

function columnFilterOptions(column) {
  ensureColumnFilter(column.key)
  return buildFilterOptions(listRows.value.map((row) => ({ ...row, [column.key]: formatCell(row, column.key) })), column)
}

function handleDateFilterChange(key) {
  const filter = ensureColumnFilter(key)
  filter.start = filter.range?.[0] || ''
  filter.end = filter.range?.[1] || ''
}

function resetColumnFilters() {
  Object.keys(columnFilters).forEach((key) => {
    columnFilters[key] = { text: '', start: '', end: '', range: [], min: null, max: null, values: [] }
  })
}

function hasActiveColumnFilters() {
  return Object.values(columnFilters).some((filter) => (
    String(filter.text || '').trim()
    || String(filter.start || '').trim()
    || String(filter.end || '').trim()
    || (Array.isArray(filter.values) && filter.values.filter(Boolean).length)
    || filter.min != null
    || filter.max != null
  ))
}

function clearFilters() {
  keyword.value = ''
  statusFilter.value = ''
  resetColumnFilters()
  resetSorting()
  currentPage.value = 1
}

function resetSorting() {
  sortState.key = ''
  sortState.direction = 'asc'
  clearSelection()
}

function toggleSort(key) {
  if (sortState.key !== key) {
    sortState.key = key
    sortState.direction = 'asc'
    clearSelection()
    return
  }
  sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc'
  clearSelection()
}

function sortIcon(key) {
  if (sortState.key !== key) return ''
  return sortState.direction === 'asc' ? '↑' : '↓'
}

function globalIndex(index) {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

function exportCurrentList() {
  const rows = sortedRows.value.map((row) => {
    const next = { ...row }
    listColumns.value.forEach((column) => {
      next[column.key] = formatCell(row, column.key)
    })
    return next
  })
  exportRowsToCsvUtil(rows, listColumns.value, `wms-${currentType.value || 'list'}-${today()}.csv`)
}

function refresh() {
  wmsState.value = getWmsState()
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => {
    message.value = ''
  }, 2400)
}

function resetDemo() {
  resetWmsState()
  refresh()
  notify('WMS演示数据已恢复')
}

function openOpeningDialog() {
  openingForm.materialId = materialOptions.value[0]?.id || ''
  openingForm.warehouseId = warehouseOptions.value[0]?.id || ''
  openingForm.locationId = getLocationOptions(openingForm.warehouseId)[0]?.id || ''
  openingForm.batchNo = `BATCH-OPENING-${Date.now().toString().slice(-4)}`
  openingForm.quantity = 0
  openingForm.remark = ''
  openingDialogVisible.value = true
}

function handleOpeningMaterialChange() {
  const material = materialOptions.value.find((item) => String(item.id) === String(openingForm.materialId))
  if (material?.raw?.defaultWarehouseId) {
    openingForm.warehouseId = material.raw.defaultWarehouseId
    handleOpeningWarehouseChange()
  }
}

function handleOpeningWarehouseChange() {
  openingForm.locationId = getLocationOptions(openingForm.warehouseId)[0]?.id || ''
}

function submitOpening() {
  if (!openingForm.materialId || !openingForm.warehouseId || !openingForm.locationId) {
    notify('请先选择物料、仓库和库位。', 'warning')
    return
  }
  const outcome = applyInventoryTransaction({
    ...openingForm,
    transactionType: 'opening',
    sourceModule: 'wms',
    sourceType: 'manualOpening',
    sourceNo: openingForm.batchNo,
    remark: openingForm.remark || '手工初始化库存',
  })
  if (!outcome.success) {
    notify(outcome.error || '初始化失败', 'warning')
    return
  }
  openingDialogVisible.value = false
  refresh()
  notify('库存已初始化，并已写入库存流水')
}

function generateWarnings() {
  const rows = generateStockWarnings()
  refresh()
  notify(`已生成 ${rows.length} 条库存预警`)
}

function completeTask(row) {
  const outcome = completeWarehouseTask(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('仓库任务已完成')
}

function cancelTask(row) {
  const outcome = cancelWarehouseTask(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('仓库任务已取消')
}

function handleWarning(row) {
  const outcome = handleStockWarning(row.id, { handlerId: getEmployeeOptions()[0]?.id || '', remark: '页面处理库存预警' })
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('库存预警已处理')
}

function ignoreWarning(row) {
  const outcome = ignoreStockWarning(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('库存预警已忽略')
}

function createReceiveTask(row) {
  const outcome = createPurchaseReceiveTaskFromScmPurchaseOrder(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`已生成 ${outcome.taskIds.length} 条仓库收货任务，本步骤未增加库存`)
}

function createPurchaseReceive(row) {
  const outcome = createPurchaseReceiveFromScmPurchaseOrder(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`${outcome.existed ? '已存在' : '已生成'}采购收货预备单 ${outcome.receiveNo}，库存余额不变`)
}

function createPurchaseReceiveFromTask(row) {
  const outcome = createPurchaseReceiveFromWarehouseTask(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`${outcome.existed ? '已存在' : '已生成'}采购收货预备单 ${outcome.receiveNo}，库存余额不变`)
}

function hasRowAction(row) {
  if (detailRoute(row)) return true
  if (currentType.value === 'balances') return true
  if (currentType.value === 'tasks') return row.status === 'pending' || row.taskType === 'purchaseReceive' || getWarehouseTaskBusinessType(row) === 'qualifiedInboundPrepare'
  if (currentType.value === 'warnings') return row.status === 'open'
  if (currentType.value === 'receive') return true
  return false
}

watch(() => route.fullPath, () => {
  refresh()
  syncColumnFilters()
  advancedFilterVisible.value = false
  quickSearchVisible.value = false
  currentPage.value = 1
}, { immediate: true })

watch([filteredRows, pageSize], () => {
  const maxPage = Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value))
  if (currentPage.value > maxPage) currentPage.value = maxPage
})
</script>

<style scoped>
.wms-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header,
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

.page-header p,
.source-note,
.muted {
  color: #475569;
}

.page-tabs,
.button-row,
.toolbar,
.range-row,
.pagination-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.batch-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 12px 0;
  padding: 10px 12px;
  border: 1px solid #d9e4f2;
  border-radius: 8px;
  background: #f8fbff;
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
  color: #172033;
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

.page-tabs a {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
}

.page-tabs a.router-link-active {
  border-color: #2563eb;
  background: #dbeafe;
}

.operation-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-grid,
.filter-grid,
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.info-grid article {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.info-grid span {
  color: #64748b;
  font-size: 13px;
}

.info-grid strong {
  display: block;
  margin-top: 6px;
  word-break: break-word;
}

.summary-grid span,
.card-header span,
.filter-item label {
  color: #64748b;
  font-size: 12px;
}

.summary-grid strong {
  display: block;
  margin: 8px 0;
  font-size: 24px;
}

.toolbar {
  margin-bottom: 14px;
}

.toolbar .el-input,
.toolbar .el-select {
  width: 260px;
}

.filter-grid {
  margin-bottom: 14px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sort-button {
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
}

.pagination-row {
  justify-content: space-between;
  margin-top: 12px;
}

@media (max-width: 1200px) {
  .summary-grid,
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .page-header,
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .toolbar .el-input,
  .toolbar .el-select {
    width: 100%;
  }
}
</style>


