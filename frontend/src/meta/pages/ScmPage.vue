<template>
  <main class="scm-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.11.4 SCM采购前端主从单据</p>
        <h1>{{ pageTitle }}</h1>
        <p>本轮只升级请购、询价、核价、采购订单的“单据头 + 明细行”结构，不接入收货、退货、对账、应付和WMS入库。</p>
        <p class="app-current-module-badge">当前操作模块：{{ currentScmModuleName }}</p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">SCM采购流程导航</span>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isScmNavActive(null) }" to="/scm">
          SCM采购管理
          <span v-if="isScmNavActive(null)" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isScmNavActive('request') }" to="/scm/purchase-requests">
          请购单
          <span v-if="isScmNavActive('request')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isScmNavActive('inquiry') }" to="/scm/purchase-inquiries">
          询价单
          <span v-if="isScmNavActive('inquiry')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isScmNavActive('approval') }" to="/scm/price-approvals">
          核价单
          <span v-if="isScmNavActive('approval')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': isScmNavActive('order') }" to="/scm/purchase-orders">
          采购订单
          <span v-if="isScmNavActive('order')" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/reference/master-data">引用源</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section v-if="route.path === '/scm'" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>SCM采购前端总览</h2>
              <span>数据保存到 localStorage：scm-state-v1，并兼容 V1.11.3 单物料旧数据迁移。</span>
            </div>
            <el-button type="primary" @click="resetDemo">恢复演示数据</el-button>
          </div>
        </template>
        <div class="summary-grid">
          <el-card v-for="card in scmOverviewCards" :key="card.title" shadow="never">
            <span>{{ card.title }}</span>
            <strong>{{ card.count }}</strong>
            <p>{{ card.desc }}</p>
            <el-button type="primary" @click="router.push(card.to)">进入</el-button>
          </el-card>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>待处理流程</h2>
              <span>请购审批、询价报价确认、核价审批后会在这里形成流程承接任务。</span>
            </div>
          </div>
        </template>
        <el-table :data="pendingRows" border stripe height="360">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="title" label="标题" min-width="260" />
          <el-table-column prop="sourceType" label="来源类型" width="150" />
          <el-table-column prop="sourceId" label="来源单据" width="160" />
          <el-table-column prop="createdAt" label="创建时间" width="210" />
          <el-table-column label="状态" width="110">
            <template #default="{ row }">
              <el-tag :type="row.status === 'pending' ? 'warning' : row.status === 'done' ? 'success' : 'info'">
                {{ pendingStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['去处理', '标记取消'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" type="primary" @click="handlePending(row)">去处理</el-button>
                <el-button size="small" class="app-action-button-md" @click="cancelPending(row)">标记取消</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>主从结构说明</h2></template>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="单据头">列表只显示单号、日期、人员、状态、汇总数量和金额。</el-descriptions-item>
          <el-descriptions-item label="明细行">具体物料、数量、价格、仓库、库位在详情页维护。</el-descriptions-item>
          <el-descriptions-item label="引用源">物料、供应商、人员、部门、仓库、库位均来自 manufacturingReferenceService。</el-descriptions-item>
          <el-descriptions-item label="转换规则">请购转询价、询价转核价、核价转采购订单时自动携带明细。</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </section>

    <section v-else-if="activeConfig && pageMode === 'list'" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ activeConfig.title }}</h2>
              <span>{{ activeConfig.subtitle }}</span>
            </div>
            <el-button v-if="activeType === 'request'" type="primary" @click="router.push(activeConfig.createPath)">新增请购单</el-button>
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
            placeholder="搜索单号、人员、供应商、物料、部门、状态"
            clearable
            @select="handleSuggestionSelect"
          />
          <el-select v-model="statusFilter" placeholder="状态筛选" clearable>
            <el-option v-for="item in activeConfig.statuses" :key="item" :label="statusLabel(item)" :value="item" />
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
          :title="scmProcessText"
          type="info"
          show-icon
          :closable="false"
        />

        <div class="batch-bar">
          <span>已选择 {{ selectedRows.length }} 条</span>
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
          <span v-if="selectedRows.length" class="batch-counts">可执行 {{ activeBatchExecutableCount }} 条，将跳过 {{ selectedRows.length - activeBatchExecutableCount }} 条</span>
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
              <el-option
                v-for="option in columnFilterOptions(column)"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
          </div>
        </div>

        <el-table ref="listTableRef" :data="pagedRows" border stripe height="520" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="48" fixed="left" />
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column
            v-for="column in listColumns"
            :key="column.key"
            :label="column.label"
            :min-width="column.width || 120"
          >
            <template #header>
              <button class="sort-button" type="button" title="点击表头字段可升序/降序排序" @click="toggleSort(column.key)">
                {{ column.label }} {{ sortIcon(column.key) }}
              </button>
            </template>
            <template #default="{ row }">
              <el-tag v-if="column.key === 'status'" :type="statusType(row.status)">
                {{ statusLabel(row.status) }}
              </el-tag>
              <el-tag v-else-if="column.key === 'deliveryUrgency'" :type="getUrgencyTagType(row.deliveryUrgency)" :style="getUrgencyStyle(row.deliveryUrgency)">
                {{ getUrgencyLabel(row.deliveryUrgency) }}
              </el-tag>
              <span v-else>{{ formatListCell(row, column.key) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="listActionColumnWidth">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="openDetail(row)">查看明细</el-button>
                <el-button size="small" class="app-action-button-sm" type="primary" :disabled="!canEditRowHeader(row)" :title="rowReadonlyReason(row)" @click="openDetail(row)">编辑</el-button>
                <el-button
                  v-for="action in visibleListActions(row)"
                  :key="action.label"
                  size="small"
                  :class="getActionButtonClass(actionButtonLabel(action, row))"
                  :disabled="!isActionAllowed(action, row)"
                  :title="!isActionAllowed(action, row) ? '当前状态不允许执行该操作' : ''"
                  @click="runAction(action, row.id)"
                >
                  {{ actionButtonLabel(action, row) }}
                </el-button>
                <el-button size="small" class="app-action-button-sm" type="danger" :disabled="!canEditRowHeader(row)" :title="rowReadonlyReason(row)" @click="deleteCurrent(row)">删除</el-button>
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

    <section v-else-if="isBlockedCreatePage" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ blockedCreateTitle }}</h2>
              <span>{{ blockedCreateMessage }}</span>
            </div>
            <div class="button-row">
              <el-button @click="goCurrentParent">返回 SCM</el-button>
              <el-button type="primary" @click="router.push(blockedCreateSourceRoute)">{{ blockedCreateSourceLabel }}</el-button>
            </div>
          </div>
        </template>
        <el-alert
          :title="blockedCreateMessage"
          type="warning"
          show-icon
          :closable="false"
        />
      </el-card>
    </section>

    <section v-else-if="activeConfig" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ pageTitle }}</h2>
              <span>先保存单据头，再维护多行明细；明细选择物料后自动带出编码、名称、规格和单位。</span>
            </div>
            <div class="button-row">
              <el-button @click="goCurrentList">返回列表</el-button>
              <el-button @click="goCurrentParent">返回上级</el-button>
              <el-button v-if="hasCurrentSource" type="primary" @click="goCurrentSource">{{ currentSourceButtonLabel }}</el-button>
            </div>
          </div>
        </template>

        <el-form :model="form" label-width="140px" class="detail-form">
          <el-alert
            v-if="documentReadonlyReason"
            :title="`当前状态：${statusLabel(form.status)}。业务规则：${documentReadonlyReason}`"
            type="warning"
            show-icon
            :closable="false"
          />
          <el-alert
            :title="flowPositionText"
            type="info"
            show-icon
            :closable="false"
          />
          <el-divider content-position="left">单据头信息</el-divider>
          <div class="form-grid">
            <el-form-item
              v-for="field in activeConfig.headerFields"
              :key="field.key"
              :label="field.label"
              :required="field.required"
            >
              <el-select
                v-if="field.type === 'select'"
                v-model="form[field.key]"
                filterable
                clearable
                @change="handleHeaderFieldChange(field.key)"
                :disabled="field.readonly || !headerEditable"
                :placeholder="`请选择${field.label}`"
              >
                <el-option
                  v-for="option in field.options()"
                  :key="option.id"
                  :label="option.name"
                  :value="option.id"
                />
              </el-select>
              <el-date-picker
                v-else-if="field.type === 'date'"
                v-model="form[field.key]"
                type="date"
                value-format="YYYY-MM-DD"
                :disabled="field.readonly || !headerEditable"
                :placeholder="`请选择${field.label}`"
              />
              <el-input
                v-else-if="field.type === 'textarea'"
                v-model="form[field.key]"
                type="textarea"
                :rows="3"
                :disabled="field.readonly || !headerEditable"
              />
              <el-input-number
                v-else-if="field.type === 'number'"
                v-model="form[field.key]"
                :min="0"
                :precision="field.precision || 0"
                :disabled="field.readonly || !headerEditable"
              />
              <el-input v-else v-model="form[field.key]" :disabled="field.readonly || !headerEditable" />
            </el-form-item>
          </div>

          <div class="detail-actions">
            <el-button type="primary" :disabled="!headerEditable" :title="documentReadonlyReason" @click="saveCurrent">保存单据头</el-button>
            <el-button
              v-for="action in visibleDetailActions(form)"
              :key="action.label"
              :disabled="!isActionAllowed(action, form)"
              :title="!isActionAllowed(action, form) ? '当前状态不允许执行该操作' : ''"
              @click="runAction(action, form.id)"
            >
              {{ actionButtonLabel(action, form) }}
            </el-button>
            <el-button @click="goCurrentList">返回列表</el-button>
            <el-button @click="goCurrentParent">返回上级</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card v-if="form.id || canCreateRequestDetail" shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>明细行</h2>
              <span>{{ detailSummaryText }}</span>
            </div>
            <el-button type="primary" :disabled="!lineAddable" :title="lineActionReason" @click="startAddDetail">添加明细</el-button>
          </div>
        </template>
        <el-alert
          :title="lineStateText"
          :type="lineAddable ? 'success' : 'warning'"
          show-icon
          :closable="false"
        />

        <el-table :data="detailRows" border stripe height="460">
          <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
          <el-table-column
            v-for="column in activeConfig.detailColumns"
            :key="column.key"
            :label="column.label"
            :min-width="column.width || 120"
          >
            <template #default="{ row }">
              {{ formatDetailCell(row, column.key) }}
            </template>
          </el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['编辑明细', '删除明细'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" type="primary" :disabled="!lineEditable" :title="documentReadonlyReason" @click="startEditDetail(row)">编辑明细</el-button>
                <el-button size="small" class="app-action-button-sm" type="danger" :disabled="!lineDeletable" :title="documentReadonlyReason" @click="deleteDetail(row)">删除明细</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <el-divider v-if="detailEditorVisible" content-position="left">{{ detailForm.id ? '编辑明细' : '添加明细' }}</el-divider>
        <el-form v-if="detailEditorVisible" :model="detailForm" label-width="140px" class="detail-form">
          <div class="form-grid">
            <el-form-item
              v-for="field in activeConfig.detailFields"
              :key="field.key"
              :label="field.label"
              :required="field.required"
            >
              <el-select
                v-if="field.type === 'select'"
                v-model="detailForm[field.key]"
                filterable
                clearable
                :placeholder="`请选择${field.label}`"
                @change="handleDetailFieldChange(field.key)"
              >
                <el-option
                  v-for="option in field.options()"
                  :key="option.id"
                  :label="option.name"
                  :value="option.id"
                />
              </el-select>
              <el-date-picker
                v-else-if="field.type === 'date'"
                v-model="detailForm[field.key]"
                type="date"
                value-format="YYYY-MM-DD"
                :placeholder="`请选择${field.label}`"
              />
              <el-input-number
                v-else-if="field.type === 'number'"
                v-model="detailForm[field.key]"
                :min="field.min ?? 0"
                :precision="field.precision || 0"
                @change="handleDetailFieldChange(field.key)"
              />
              <el-input
                v-else-if="field.type === 'textarea'"
                v-model="detailForm[field.key]"
                type="textarea"
                :rows="3"
              />
              <el-input v-else v-model="detailForm[field.key]" :disabled="isDetailFieldDisabled(field)" />
            </el-form-item>
          </div>
          <div class="detail-actions">
            <el-button type="primary" @click="saveDetail">保存明细</el-button>
            <el-button @click="cancelDetail">取消</el-button>
          </div>
        </el-form>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  addPriceApprovalItem,
  addPurchaseInquiryItem,
  addPurchaseRequestItem,
  addScmPurchaseOrderItem,
  batchApproveDocuments,
  batchConvertToNext,
  batchIssuePurchaseOrders,
  batchSubmitDocuments,
  approvePriceApproval,
  approvePurchaseRequest,
  approveScmPurchaseOrder,
  cancelPendingAction,
  closePurchaseInquiry,
  closePurchaseRequest,
  closeScmPurchaseOrder,
  createInquiryFromRequest,
  createPriceApproval,
  createPriceApprovalFromInquiry,
  createPurchaseInquiry,
  createPurchaseOrderFromPriceApproval,
  createPurchaseRequest,
  createScmPurchaseOrder,
  confirmInquiryQuote,
  deletePriceApproval,
  deletePriceApprovalItem,
  deletePurchaseInquiry,
  deletePurchaseInquiryItem,
  deletePurchaseRequest,
  deletePurchaseRequestItem,
  deleteScmPurchaseOrder,
  deleteScmPurchaseOrderItem,
  getPriceApprovalById,
  getPriceApprovalItems,
  getPurchaseInquiryById,
  getPurchaseInquiryItems,
  getPurchaseRequestById,
  getPurchaseRequestItems,
  getScmDisplayName,
  getScmPurchaseOrderById,
  getScmPurchaseOrderItems,
  getScmState,
  issueScmPurchaseOrder,
  processPendingAction,
  recalculateScmPurchaseOrderAmount,
  rejectPriceApproval,
  resetScmState,
  sendPurchaseInquiry,
  submitPriceApproval,
  submitPurchaseRequest,
  submitScmPurchaseOrder,
  updatePriceApproval,
  updatePriceApprovalItem,
  updatePurchaseInquiry,
  updatePurchaseInquiryItem,
  updatePurchaseRequest,
  updatePurchaseRequestItem,
  updateScmPurchaseOrder,
  updateScmPurchaseOrderItem,
} from '../scm/scmStore.js'
import {
  canAddLine,
  canDeleteLine,
  canEditHeader,
  canEditLines,
  canIssuePurchaseOrder,
  canSendToWms,
  getNextApprovalButtonLabel,
  getNextApprovalAction,
  getNextBusinessAction,
  getReadonlyReason,
  getStatusDisplayLabel,
} from '../scm/scmDocumentRules.js'
import {
  getDepartmentOptions,
  getEmployeeOptions,
  getMaterialOptions,
  getEnabledMaterials,
  getEnabledSuppliers,
  getEnabledWarehouses,
  getDefaultPrice,
  getLocationOptions,
  getRecommendedSuppliers,
  getSupplierOptions,
} from '../manufacturing/manufacturingReferenceService.js'
import { addOperationLog } from '../manufacturing/manufacturingFoundationStore.js'
import {
  applyColumnFilters,
  applyPagination,
  applySorting,
  buildFilterOptions,
  exportRowsToCsv as exportRowsToCsvUtil,
} from '../manufacturing/foundationTableUtils.js'
import { buildMultiFieldSuggestions, filterSuggestions } from '../runtime/filterSuggestionEngine.js'
import {
  getSourceButtonLabel,
  goList,
  goParent,
  goSource,
  hasSourceRoute,
} from '../runtime/navigationRules.js'
import {
  getActionButtonSize,
  getActionColumnWidth,
  getActionColumnWidthForRows,
} from '../runtime/tableActionColumnEngine.js'
import {
  calculateDeliveryUrgency,
  getUrgencyLabel,
  getUrgencyTagType,
  getUrgencyStyle,
} from '../runtime/urgencyEngine.js'

const route = useRoute()
const router = useRouter()
const scmState = ref(getScmState())
const form = reactive({})
const detailForm = reactive({})
const keyword = ref('')
const statusFilter = ref('')
const message = ref('')
const messageType = ref('success')
const advancedFilterVisible = ref(false)
const quickSearchVisible = ref(false)
const detailEditorVisible = ref(false)
const columnFilters = reactive({})
const sortState = reactive({ key: '', direction: 'asc' })
const currentPage = ref(1)
const pageSize = ref(10)
const selectedRows = ref([])
const listTableRef = ref(null)
const batchResult = ref(null)
const batchMessageType = ref('success')
const draftRequestDetails = ref([])

function today() {
  return new Date().toISOString().slice(0, 10)
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function resetObject(target, source = {}) {
  Object.keys(target).forEach((key) => delete target[key])
  Object.assign(target, clone(source))
}

function firstId(collection) {
  return collection[0]?.id || ''
}

function statusValue(item = {}) {
  return String(item.status || item.raw?.status || 'enabled').toLowerCase()
}

function isEnabledOption(item = {}) {
  const value = statusValue(item)
  return value !== 'disabled' && !value.includes('停用')
}

function optionDisplay(option = {}, parts = []) {
  const values = parts.map((key) => option.raw?.[key] || option[key]).filter(Boolean)
  return values.length ? `${values.join(' / ')}${isEnabledOption(option) ? '' : '（已停用）'}` : option.name
}

function logScmReference(action, detail = '') {
  addOperationLog({
    module: 'SCM采购前端',
    action,
    targetType: activeType.value || 'scm',
    targetId: form.id || detailForm.id || '',
    detail,
  })
}

function materialOptions() {
  return getEnabledMaterials().map((item) => ({
    ...item,
    name: optionDisplay(item, ['code', 'name', 'specification', 'unit']),
  }))
}

function supplierOptions() {
  const enabled = getEnabledSuppliers()
  const recommended = detailForm.materialId
    ? getRecommendedSuppliers(detailForm.materialId).map((item) => item.supplier).filter(Boolean)
    : []
  const merged = [...recommended, ...enabled.filter((item) => !recommended.some((supplier) => String(supplier.id) === String(item.id)))]
  return merged.map((item) => ({
    ...item,
    name: optionDisplay(item, ['code', 'name', 'supplierLevel']),
  }))
}

function employeeOptions() {
  return getEmployeeOptions()
    .filter((item) => isEnabledOption(item) && !['resigned', 'left'].includes(statusValue(item)))
    .map((item) => ({
      ...item,
      name: optionDisplay(item, ['employeeNo', 'name', 'departmentName', 'roleName']),
    }))
}

function departmentOptions() {
  return getDepartmentOptions()
}

function defaultPurchaseDepartmentId() {
  const departments = departmentOptions()
  return departments.find((item) => `${item.name || ''}${item.raw?.name || ''}`.includes('采购'))?.id || firstId(departments)
}

function warehouseOptions() {
  return getEnabledWarehouses().map((item) => ({
    ...item,
    name: optionDisplay(item, ['code', 'name']),
  }))
}

function locationOptions() {
  return getLocationOptions(detailForm.warehouseId || form.warehouseId || firstId(warehouseOptions()))
}

function requestOptions() {
  return scmState.value.purchaseRequests.map((item) => ({ id: item.id, name: item.requestNo }))
}

function inquiryOptions() {
  return scmState.value.purchaseInquiries.map((item) => ({ id: item.id, name: item.inquiryNo }))
}

function snapshotMaterial(materialId) {
  const item = materialOptions().find((option) => String(option.id) === String(materialId)) || {}
  const raw = item.raw || {}
  return {
    materialId: item.id || materialId || '',
    materialCode: item.code || raw.code || item.id || '',
    materialName: raw.name || item.name || '',
    specification: raw.specification || raw.model || raw.spec || '',
    unit: raw.unit || raw.unitName || raw.baseUnit || raw.purchaseUnit || '',
    materialType: raw.materialType || raw.type || '',
    safetyStock: Number(raw.safetyStock || 0),
    maxStock: Number(raw.maxStock || 0),
    defaultWarehouseId: raw.defaultWarehouseId || raw.defaultWarehouse || '',
    defaultLocationId: raw.defaultLocationId || raw.defaultLocation || '',
  }
}

function preferredSupplierId(materialId) {
  const recommended = getRecommendedSuppliers(materialId)
  return recommended.find((item) => item.isPrimary)?.supplierId || recommended[0]?.supplierId || firstId(supplierOptions())
}

function preferredLocationId(warehouseId, materialSnapshot = {}) {
  const locations = getLocationOptions(warehouseId)
  if (materialSnapshot.defaultLocationId && locations.some((item) => String(item.id) === String(materialSnapshot.defaultLocationId))) {
    return materialSnapshot.defaultLocationId
  }
  return firstId(locations)
}

function applyDefaultPriceToDetail() {
  if (!['inquiry', 'approval', 'order'].includes(activeType.value)) return
  if (!detailForm.materialId || !detailForm.supplierId && activeType.value !== 'order') return
  const supplierId = detailForm.supplierId || form.supplierId
  const price = getDefaultPrice(detailForm.materialId, supplierId)
  if (!price) {
    detailForm.priceMessage = '未找到该供应商的物料价格，请先维护供应商物料价格。'
    notify(detailForm.priceMessage, 'warning')
    return
  }
  detailForm.taxRate = Number(price.taxRate || 13)
  detailForm.deliveryDays = Number(price.deliveryDays || 0)
  detailForm.paymentTerms = price.paymentTerms || ''
  detailForm.currency = price.currency || 'CNY'
  detailForm.priceSourceId = price.id
  detailForm.priceMessage = ''
  if (activeType.value === 'inquiry' && !Number(detailForm.quotedPrice || 0)) {
    detailForm.quotedPrice = Number(price.price || 0)
  }
  if (activeType.value === 'approval') {
    if (!Number(detailForm.quotedPrice || 0)) detailForm.quotedPrice = Number(price.price || 0)
    if (!Number(detailForm.approvedPrice || 0)) detailForm.approvedPrice = Number(detailForm.quotedPrice || price.price || 0)
  }
  if (activeType.value === 'order' && !Number(detailForm.planPrice ?? detailForm.price ?? 0)) {
    detailForm.planPrice = Number(price.price || 0)
    detailForm.price = detailForm.planPrice
    detailForm.planAmount = Number((Number(detailForm.quantity || 0) * Number(detailForm.planPrice || 0)).toFixed(2))
    detailForm.amount = detailForm.planAmount
  }
  logScmReference('SCM自动带出供应商价格', `${detailForm.materialId || ''}/${supplierId || ''}`)
}

const configs = {
  request: {
    title: '请购单',
    subtitle: '请购单列表只显示单据头和汇总信息，物料明细在详情页维护。',
    listPath: '/scm/purchase-requests',
    createPath: '/scm/purchase-request/create',
    detailPath: (id) => `/scm/purchase-request/${id}`,
    collection: 'purchaseRequests',
    noField: 'requestNo',
    statuses: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted', 'issued', 'partiallyReceived', 'closed', 'cancelled'],
    columns: [
      { key: 'requestNo', label: '请购单号', width: 150 },
      { key: 'requestDate', label: '请购日期' },
      { key: 'requesterId', label: '请购人' },
      { key: 'requestDepartment', label: '请购部门' },
      { key: 'demandDepartment', label: '需求部门' },
      { key: 'purchaseDepartment', label: '采购部门' },
      { key: 'lineCount', label: '明细行数' },
      { key: 'totalQuantity', label: '总数量' },
      { key: 'earliestRequiredDate', label: '最早需求日期', width: 140 },
      { key: 'status', label: '状态' },
    ],
    headerFields: [
      { key: 'requestNo', label: '请购单号', readonly: true },
      { key: 'requestDate', label: '请购日期', type: 'date', required: true },
      { key: 'requesterId', label: '请购人', type: 'select', required: true, options: employeeOptions },
      { key: 'requestDepartment', label: '请购部门', type: 'select', required: true, options: departmentOptions },
      { key: 'demandDepartment', label: '需求部门', type: 'select', required: true, options: departmentOptions },
      { key: 'purchaseDepartment', label: '采购部门', type: 'select', required: true, options: departmentOptions },
      { key: 'requiredDate', label: '需求日期', type: 'date', required: true },
      { key: 'purpose', label: '用途' },
      { key: 'status', label: '状态', readonly: true },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    detailColumns: [
      { key: 'materialCode', label: '物料编码' },
      { key: 'materialName', label: '物料名称' },
      { key: 'specification', label: '规格型号' },
      { key: 'unit', label: '单位' },
      { key: 'quantity', label: '数量' },
      { key: 'requiredDate', label: '需求日期' },
      { key: 'suggestedSupplierId', label: '建议供应商', width: 150 },
      { key: 'purpose', label: '用途' },
      { key: 'remark', label: '备注' },
    ],
    detailFields: [
      { key: 'materialId', label: '物料', type: 'select', options: materialOptions },
      { key: 'materialCode', label: '物料编码', readonly: true },
      { key: 'materialName', label: '物料名称', readonly: true },
      { key: 'specification', label: '规格型号', readonly: true },
      { key: 'unit', label: '单位', readonly: true },
      { key: 'quantity', label: '数量', type: 'number', min: 1, required: true },
      { key: 'requiredDate', label: '需求日期', type: 'date', required: true },
      { key: 'suggestedSupplierId', label: '建议供应商', type: 'select', options: supplierOptions },
      { key: 'purpose', label: '用途' },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    defaults: () => ({
      requestDate: today(),
      requesterId: firstId(employeeOptions()),
      departmentId: firstId(departmentOptions()),
      requestDepartment: firstId(departmentOptions()),
      demandDepartment: firstId(departmentOptions()),
      purchaseDepartment: defaultPurchaseDepartmentId(),
      requiredDate: today(),
      purpose: '',
      status: 'draft',
      remark: '',
    }),
    detailDefaults: () => ({
      materialId: firstId(materialOptions()),
      quantity: 1,
      requiredDate: today(),
      suggestedSupplierId: firstId(supplierOptions()),
      purpose: '',
      remark: '',
      ...snapshotMaterial(firstId(materialOptions())),
    }),
    get: getPurchaseRequestById,
    create: createPurchaseRequest,
    update: updatePurchaseRequest,
    delete: deletePurchaseRequest,
    detailGet: getPurchaseRequestItems,
    detailAdd: addPurchaseRequestItem,
    detailUpdate: updatePurchaseRequestItem,
    detailDelete: deletePurchaseRequestItem,
    listActions: [
      { label: '提交', handler: submitPurchaseRequest },
      { label: '审批', handler: approvePurchaseRequest },
      { label: '转询价', handler: convertRequest },
      { label: '关闭', handler: closePurchaseRequest },
    ],
    detailActions: [
      { label: '提交', handler: submitPurchaseRequest },
      { label: '审批', handler: approvePurchaseRequest },
      { label: '转询价', handler: convertRequest },
      { label: '关闭', handler: closePurchaseRequest },
    ],
  },
  inquiry: {
    title: '询价单',
    subtitle: '询价单按单据头管理供应商报价过程，报价明细在详情页维护。',
    listPath: '/scm/purchase-inquiries',
    createPath: '/scm/purchase-inquiry/create',
    detailPath: (id) => `/scm/purchase-inquiry/${id}`,
    collection: 'purchaseInquiries',
    noField: 'inquiryNo',
    statuses: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'sent', 'quoted', 'converted', 'closed', 'cancelled'],
    columns: [
      { key: 'inquiryNo', label: '询价单号', width: 150 },
      { key: 'inquiryDate', label: '询价日期' },
      { key: 'sourceOrderNo', label: '来源请购单', width: 150 },
      { key: 'rootRequestDepartment', label: '请购部门', width: 130 },
      { key: 'rootDemandDepartment', label: '需求部门', width: 130 },
      { key: 'buyerId', label: '采购员' },
      { key: 'lineCount', label: '明细行数' },
      { key: 'supplierCount', label: '供应商数' },
      { key: 'status', label: '状态' },
    ],
    headerFields: [
      { key: 'inquiryNo', label: '询价单号', readonly: true },
      { key: 'inquiryDate', label: '询价日期', type: 'date', required: true },
      { key: 'requestId', label: '来源请购单', type: 'select', options: requestOptions },
      { key: 'sourceOrderNo', label: '来源单号', readonly: true },
      { key: 'rootRequestNo', label: '源请购单号', readonly: true },
      { key: 'rootRequestDepartment', label: '请购部门', readonly: true },
      { key: 'rootDemandDepartment', label: '需求部门', readonly: true },
      { key: 'buyerId', label: '采购员', type: 'select', required: true, options: employeeOptions },
      { key: 'status', label: '状态', readonly: true },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    detailColumns: [
      { key: 'supplierId', label: '供应商', width: 150 },
      { key: 'materialCode', label: '物料编码' },
      { key: 'materialName', label: '物料名称' },
      { key: 'specification', label: '规格型号' },
      { key: 'unit', label: '单位' },
      { key: 'quantity', label: '数量' },
      { key: 'rootRequestNo', label: '源请购单', width: 150 },
      { key: 'sourceOrderNo', label: '来源单号', width: 150 },
      { key: 'expectedDeliveryDate', label: '期望交期' },
      { key: 'quotedPrice', label: '报价' },
      { key: 'quotedAmount', label: '报价金额' },
      { key: 'quotedDeliveryDate', label: '报价交期' },
      { key: 'status', label: '明细状态' },
    ],
    detailFields: [
      { key: 'supplierId', label: '供应商', type: 'select', required: true, options: supplierOptions },
      { key: 'materialId', label: '物料', type: 'select', required: true, options: materialOptions },
      { key: 'materialCode', label: '物料编码', readonly: true },
      { key: 'materialName', label: '物料名称', readonly: true },
      { key: 'specification', label: '规格型号', readonly: true },
      { key: 'unit', label: '单位', readonly: true },
      { key: 'quantity', label: '数量', type: 'number', min: 1, required: true },
      { key: 'rootRequestNo', label: '源请购单', readonly: true },
      { key: 'sourceOrderNo', label: '来源单号', readonly: true },
      { key: 'sourceLineId', label: '来源行ID', readonly: true },
      { key: 'expectedDeliveryDate', label: '期望交期', type: 'date', required: true },
      { key: 'quotedPrice', label: '报价', type: 'number', precision: 2 },
      { key: 'quotedAmount', label: '报价金额', type: 'number', precision: 2 },
      { key: 'quotedDeliveryDate', label: '报价交期', type: 'date' },
      { key: 'quoteRemark', label: '报价备注', type: 'textarea' },
    ],
    defaults: () => ({
      inquiryDate: today(),
      requestId: '',
      buyerId: firstId(employeeOptions()),
      status: 'draft',
      remark: '',
    }),
    detailDefaults: () => ({
      supplierId: firstId(supplierOptions()),
      materialId: firstId(materialOptions()),
      quantity: 1,
      expectedDeliveryDate: today(),
      quotedPrice: 0,
      quotedDeliveryDate: today(),
      quoteRemark: '',
      status: 'draft',
      ...snapshotMaterial(firstId(materialOptions())),
    }),
    get: getPurchaseInquiryById,
    create: createPurchaseInquiry,
    update: updatePurchaseInquiry,
    delete: deletePurchaseInquiry,
    detailGet: getPurchaseInquiryItems,
    detailAdd: addPurchaseInquiryItem,
    detailUpdate: updatePurchaseInquiryItem,
    detailDelete: deletePurchaseInquiryItem,
    listActions: [
      { label: '发送', handler: sendPurchaseInquiry },
      { label: '确认报价', handler: confirmInquiryQuote },
      { label: '转核价', handler: convertInquiry },
      { label: '关闭', handler: closePurchaseInquiry },
    ],
    detailActions: [
      { label: '发送', handler: sendPurchaseInquiry },
      { label: '确认报价', handler: confirmInquiryQuote },
      { label: '转核价', handler: convertInquiry },
      { label: '关闭', handler: closePurchaseInquiry },
    ],
  },
  approval: {
    title: '核价单',
    subtitle: '核价单支持多物料核价，审批后完整生成一张采购订单。',
    listPath: '/scm/price-approvals',
    createPath: '/scm/price-approval/create',
    detailPath: (id) => `/scm/price-approval/${id}`,
    collection: 'priceApprovals',
    noField: 'approvalNo',
    statuses: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted', 'rejected', 'closed', 'cancelled'],
    columns: [
      { key: 'approvalNo', label: '核价单号', width: 150 },
      { key: 'sourceOrderNo', label: '来源询价单', width: 150 },
      { key: 'rootRequestNo', label: '源请购单', width: 150 },
      { key: 'rootRequestDepartment', label: '请购部门', width: 130 },
      { key: 'rootDemandDepartment', label: '需求部门', width: 130 },
      { key: 'buyerId', label: '采购员' },
      { key: 'lineCount', label: '明细行数' },
      { key: 'supplierCount', label: '供应商数' },
      { key: 'approvedTotal', label: '核准总金额', width: 130 },
      { key: 'status', label: '状态' },
    ],
    headerFields: [
      { key: 'approvalNo', label: '核价单号', readonly: true },
      { key: 'inquiryId', label: '来源询价单', type: 'select', options: inquiryOptions },
      { key: 'sourceOrderNo', label: '来源单号', readonly: true },
      { key: 'rootRequestNo', label: '源请购单号', readonly: true },
      { key: 'rootRequestDepartment', label: '请购部门', readonly: true },
      { key: 'rootDemandDepartment', label: '需求部门', readonly: true },
      { key: 'buyerId', label: '采购员', type: 'select', required: true, options: employeeOptions },
      { key: 'status', label: '状态', readonly: true },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    detailColumns: [
      { key: 'supplierId', label: '供应商', width: 150 },
      { key: 'materialCode', label: '物料编码' },
      { key: 'materialName', label: '物料名称' },
      { key: 'quantity', label: '数量' },
      { key: 'quotedPrice', label: '报价' },
      { key: 'approvedPrice', label: '核准价' },
      { key: 'approvedAmount', label: '核准金额' },
      { key: 'rootRequestNo', label: '源请购单', width: 150 },
      { key: 'sourceOrderNo', label: '来源单号', width: 150 },
      { key: 'taxRate', label: '税率%' },
      { key: 'deliveryDays', label: '交期天数' },
      { key: 'paymentTerms', label: '付款条件', width: 140 },
    ],
    detailFields: [
      { key: 'supplierId', label: '供应商', type: 'select', required: true, options: supplierOptions },
      { key: 'materialId', label: '物料', type: 'select', required: true, options: materialOptions },
      { key: 'materialCode', label: '物料编码', readonly: true },
      { key: 'materialName', label: '物料名称', readonly: true },
      { key: 'specification', label: '规格型号', readonly: true },
      { key: 'unit', label: '单位', readonly: true },
      { key: 'quantity', label: '数量', type: 'number', min: 1, required: true },
      { key: 'rootRequestNo', label: '源请购单', readonly: true },
      { key: 'sourceOrderNo', label: '来源单号', readonly: true },
      { key: 'sourceLineId', label: '来源行ID', readonly: true },
      { key: 'quotedPrice', label: '报价', type: 'number', precision: 2 },
      { key: 'approvedPrice', label: '核准价', type: 'number', precision: 2, required: true },
      { key: 'approvedAmount', label: '核准金额', type: 'number', precision: 2 },
      { key: 'taxRate', label: '税率%', type: 'number', precision: 2 },
      { key: 'deliveryDays', label: '交期天数', type: 'number' },
      { key: 'paymentTerms', label: '付款条件' },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    defaults: () => ({
      inquiryId: '',
      buyerId: firstId(employeeOptions()),
      status: 'draft',
      remark: '',
    }),
    detailDefaults: () => ({
      supplierId: firstId(supplierOptions()),
      materialId: firstId(materialOptions()),
      quantity: 1,
      quotedPrice: 0,
      approvedPrice: 0,
      taxRate: 13,
      deliveryDays: 7,
      paymentTerms: '月结30天',
      remark: '',
      ...snapshotMaterial(firstId(materialOptions())),
    }),
    get: getPriceApprovalById,
    create: createPriceApproval,
    update: updatePriceApproval,
    delete: deletePriceApproval,
    detailGet: getPriceApprovalItems,
    detailAdd: addPriceApprovalItem,
    detailUpdate: updatePriceApprovalItem,
    detailDelete: deletePriceApprovalItem,
    listActions: [
      { label: '提交', handler: submitPriceApproval },
      { label: '审批', handler: approvePriceApproval },
      { label: '驳回', handler: rejectPriceApproval },
      { label: '转采购订单', handler: convertApproval },
    ],
    detailActions: [
      { label: '提交', handler: submitPriceApproval },
      { label: '审批', handler: approvePriceApproval },
      { label: '驳回', handler: rejectPriceApproval },
      { label: '转采购订单', handler: convertApproval },
    ],
  },
  order: {
    title: '采购订单',
    subtitle: 'SCM模拟采购订单仅作为采购前端承接单据，不改动原采购管理核心 schema。',
    listPath: '/scm/purchase-orders',
    createPath: '/scm/purchase-order/create',
    detailPath: (id) => `/scm/purchase-order/${id}`,
    collection: 'purchaseOrders',
    noField: 'poNo',
    statuses: ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted', 'issued', 'released', 'ordered', 'partiallyReceived', 'receiving', 'received', 'fullyReceived', 'closed', 'cancelled'],
    columns: [
      { key: 'poNo', label: '采购订单号', width: 150 },
      { key: 'orderDate', label: '订单日期' },
      { key: 'supplierId', label: '供应商', width: 150 },
      { key: 'rootRequestNo', label: '源请购单', width: 150 },
      { key: 'requestDepartment', label: '请购部门', width: 130 },
      { key: 'demandDepartment', label: '需求部门', width: 130 },
      { key: 'buyerId', label: '采购员' },
      { key: 'lineCount', label: '明细行数' },
      { key: 'planAmount', label: '计划金额' },
      { key: 'actualAmount', label: '实际金额' },
      { key: 'earliestArrivalDate', label: '最早到货日', width: 130 },
      { key: 'deliveryUrgency', label: '交期紧急程度', filterType: 'enum', sortType: 'urgency', width: 140 },
      { key: 'actualArrivalDate', label: '实际到货日', width: 130 },
      { key: 'status', label: '状态' },
      { key: 'sourceType', label: '来源类型' },
    ],
    headerFields: [
      { key: 'poNo', label: '采购订单号', readonly: true },
      { key: 'orderDate', label: '订单日期', type: 'date', required: true },
      { key: 'supplierId', label: '供应商', type: 'select', required: true, options: supplierOptions },
      { key: 'buyerId', label: '采购员', type: 'select', required: true, options: employeeOptions },
      { key: 'sourceOrderNo', label: '来源核价单', readonly: true },
      { key: 'rootRequestNo', label: '源请购单号', readonly: true },
      { key: 'requestDepartment', label: '请购部门', readonly: true },
      { key: 'demandDepartment', label: '需求部门', readonly: true },
      { key: 'plannedArrivalDate', label: '计划到货日', type: 'date', required: true },
      { key: 'actualArrivalDate', label: '实际到货日', type: 'date', readonly: true },
      { key: 'deliveryUrgency', label: '交期紧急程度', readonly: true },
      { key: 'planAmount', label: '计划金额', type: 'number', precision: 2, readonly: true },
      { key: 'actualAmount', label: '实际金额', type: 'number', precision: 2, readonly: true },
      { key: 'totalAmount', label: '总金额', type: 'number', precision: 2, readonly: true },
      { key: 'status', label: '状态', readonly: true },
      { key: 'sourceType', label: '来源类型', readonly: true },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    detailColumns: [
      { key: 'materialCode', label: '物料编码' },
      { key: 'materialName', label: '物料名称' },
      { key: 'specification', label: '规格型号' },
      { key: 'unit', label: '单位' },
      { key: 'quantity', label: '数量' },
      { key: 'planPrice', label: '计划单价' },
      { key: 'planAmount', label: '计划金额' },
      { key: 'actualPrice', label: '实际单价' },
      { key: 'actualAmount', label: '实际金额' },
      { key: 'rootRequestNo', label: '源请购单', width: 150 },
      { key: 'sourceOrderNo', label: '来源核价单', width: 150 },
      { key: 'warehouseId', label: '仓库' },
      { key: 'locationId', label: '库位' },
      { key: 'expectedDeliveryDate', label: '期望交期' },
      { key: 'plannedArrivalDate', label: '计划到货日' },
      { key: 'actualDeliveryDate', label: '实际到货日' },
    ],
    detailFields: [
      { key: 'materialId', label: '物料', type: 'select', required: true, options: materialOptions },
      { key: 'materialCode', label: '物料编码', readonly: true },
      { key: 'materialName', label: '物料名称', readonly: true },
      { key: 'specification', label: '规格型号', readonly: true },
      { key: 'unit', label: '单位', readonly: true },
      { key: 'quantity', label: '数量', type: 'number', min: 1, required: true },
      { key: 'rootRequestNo', label: '源请购单', readonly: true },
      { key: 'sourceOrderNo', label: '来源核价单', readonly: true },
      { key: 'sourceLineId', label: '来源行ID', readonly: true },
      { key: 'planPrice', label: '计划单价', type: 'number', precision: 2, required: true },
      { key: 'planAmount', label: '计划金额', type: 'number', precision: 2 },
      { key: 'actualPrice', label: '实际单价', type: 'number', precision: 2, readonly: true },
      { key: 'actualAmount', label: '实际金额', type: 'number', precision: 2, readonly: true },
      { key: 'warehouseId', label: '仓库', type: 'select', required: true, options: warehouseOptions },
      { key: 'locationId', label: '库位', type: 'select', options: locationOptions },
      { key: 'expectedDeliveryDate', label: '期望交期', type: 'date', readonly: true },
      { key: 'plannedArrivalDate', label: '计划到货日', type: 'date', required: true },
      { key: 'actualDeliveryDate', label: '实际到货日', type: 'date', readonly: true },
      { key: 'remark', label: '备注', type: 'textarea' },
    ],
    defaults: () => ({
      orderDate: today(),
      supplierId: firstId(supplierOptions()),
      buyerId: firstId(employeeOptions()),
      plannedArrivalDate: today(),
      totalAmount: 0,
      status: 'draft',
      sourceType: 'manual',
      sourceId: '',
      remark: '',
    }),
    detailDefaults: () => ({
      materialId: firstId(materialOptions()),
      quantity: 1,
      price: 0,
      amount: 0,
      warehouseId: firstId(warehouseOptions()),
      locationId: firstId(locationOptions()),
      plannedArrivalDate: today(),
      remark: '',
      ...snapshotMaterial(firstId(materialOptions())),
    }),
    get: getScmPurchaseOrderById,
    create: createScmPurchaseOrder,
    update: updateScmPurchaseOrder,
    delete: deleteScmPurchaseOrder,
    detailGet: getScmPurchaseOrderItems,
    detailAdd: addScmPurchaseOrderItem,
    detailUpdate: updateScmPurchaseOrderItem,
    detailDelete: deleteScmPurchaseOrderItem,
    listActions: [
      { label: '提交', handler: submitScmPurchaseOrder },
      { label: '审批', handler: approveScmPurchaseOrder },
      { label: '下达', handler: issueScmPurchaseOrder },
      { label: '关闭', handler: closeScmPurchaseOrder },
    ],
    detailActions: [
      { label: '提交', handler: submitScmPurchaseOrder },
      { label: '审批', handler: approveScmPurchaseOrder },
      { label: '下达', handler: issueScmPurchaseOrder },
      { label: '进入WMS', handler: goToWmsReceivePreview },
      { label: '关闭', handler: closeScmPurchaseOrder },
    ],
  },
}

const activeType = computed(() => {
  if (route.path.includes('purchase-inquir')) return 'inquiry'
  if (route.path.includes('price-approval')) return 'approval'
  if (route.path.includes('purchase-order')) return 'order'
  if (route.path.includes('purchase-request')) return 'request'
  return null
})

const activeConfig = computed(() => (activeType.value ? configs[activeType.value] : null))
const pageMode = computed(() => (route.path.endsWith('/create') ? 'create' : route.params.id ? 'detail' : 'list'))
const isBlockedCreatePage = computed(() => pageMode.value === 'create' && activeType.value !== 'request')
const canCreateRequestDetail = computed(() => pageMode.value === 'create' && activeType.value === 'request')
const currentPageType = computed(() => ({
  request: 'purchaseRequests',
  inquiry: 'purchaseInquiries',
  approval: 'priceApprovals',
  order: 'purchaseOrders',
}[activeType.value] || ''))
const currentSourceRecord = computed(() => ({
  sourceModule: form.sourceModule,
  sourceType: form.sourceType,
  sourceOrderId: form.sourceOrderId || form.sourceId,
  sourceOrderNo: form.sourceOrderNo,
}))
const hasCurrentSource = computed(() => pageMode.value === 'detail' && hasSourceRoute(currentSourceRecord.value))
const currentSourceButtonLabel = computed(() => getSourceButtonLabel(currentSourceRecord.value))

const pageTitle = computed(() => {
  if (!activeConfig.value) return 'SCM采购管理'
  if (isBlockedCreatePage.value) return blockedCreateTitle.value
  if (pageMode.value === 'create') return `新增${activeConfig.value.title}`
  if (pageMode.value === 'detail') return `${activeConfig.value.title}明细`
  return activeConfig.value.title
})
const currentScmModuleName = computed(() => activeConfig.value?.title || 'SCM采购管理')

function isScmNavActive(type) {
  if (!type) return !activeType.value
  return activeType.value === type
}
const blockedCreateConfig = computed(() => ({
  inquiry: {
    title: '询价单来源生成提示',
    message: '询价单必须从已审批采购申请生成，不能直接空白新增。',
    route: '/scm/purchase-requests',
    label: '查看可生成询价的请购单',
  },
  approval: {
    title: '核价单来源生成提示',
    message: '核价单必须从询价单生成，不能直接空白新增。',
    route: '/scm/purchase-inquiries',
    label: '查看可生成核价的询价单',
  },
  order: {
    title: '采购订单来源生成提示',
    message: '采购订单必须从已审批核价单生成，不能直接空白新增。',
    route: '/scm/price-approvals',
    label: '查看可生成采购订单的核价单',
  },
}[activeType.value] || {}))
const blockedCreateTitle = computed(() => blockedCreateConfig.value.title || '来源生成提示')
const blockedCreateMessage = computed(() => blockedCreateConfig.value.message || '')
const blockedCreateSourceRoute = computed(() => blockedCreateConfig.value.route || '/scm')
const blockedCreateSourceLabel = computed(() => blockedCreateConfig.value.label || '查看来源单据')

function goCurrentList() {
  goList(router, 'scm', currentPageType.value)
}

function goCurrentParent() {
  goParent(router, 'scm')
}

function goCurrentSource() {
  goSource(router, currentSourceRecord.value, notify)
}

const documentModuleName = computed(() => ({
  request: 'purchaseRequest',
  inquiry: 'purchaseInquiry',
  approval: 'priceApproval',
  order: 'purchaseOrder',
})[activeType.value] || '')
const headerEditable = computed(() => pageMode.value === 'create' || canEditHeader(documentModuleName.value, form.status || 'draft'))
const lineEditable = computed(() => canEditLines(documentModuleName.value, form.status || 'draft'))
const lineAddable = computed(() => canAddLine(documentModuleName.value, form.status || 'draft'))
const lineDeletable = computed(() => canDeleteLine(documentModuleName.value, form.status || 'draft'))
const documentReadonlyReason = computed(() => getReadonlyReason(documentModuleName.value, form.status || 'draft'))
const lineActionReason = computed(() => {
  if (lineAddable.value) return '当前为草稿，可维护请购明细。'
  if (documentModuleName.value === 'purchaseRequest' && form.status === 'submitted') return '采购申请已提报，不能修改业务明细；如需修改，请撤回或作废后重新创建。'
  return documentReadonlyReason.value || '当前状态不能修改明细。'
})
const lineStateText = computed(() => {
  if (lineAddable.value) return '当前为草稿，可维护请购明细。'
  if (documentModuleName.value === 'purchaseRequest' && form.status === 'submitted') return '当前单据已提报，不能修改明细。'
  return lineActionReason.value
})
const scmProcessText = computed(() => ({
  request: '采购申请流程：业务部门提出采购申请 -> 审核/复核/审批 -> 转入询价或采购订单。采购申请是采购前端主入口，不直接触发收货、入库或应付。',
  inquiry: '采购询价流程：采购申请或采购需求 -> 供应商询价 -> 比价记录 -> 转入核价。询价用于价格采集，不代表采购承诺。',
  approval: '采购核价流程：询价结果 -> 核价审批 -> 形成可下单价格依据 -> 转入采购订单。核价只形成采购价格依据，不直接生成收货或应付。',
  order: '采购订单流程：核价/请购来源 -> 采购订单 -> 审核/复核/审批 -> 下达 -> WMS 采购到货预备。采购订单属于计划管控单据，必须展示交期紧急程度并参与排序。',
})[activeType.value] || '采购流程：采购申请 -> 询价 -> 核价 -> 采购订单 -> WMS 采购到货预备')
const flowPositionText = computed(() => {
  const flowText = scmProcessText.value
  if (!activeConfig.value) return flowText
  const next = getNextBusinessAction(documentModuleName.value, form.status || 'draft') || getNextApprovalButtonLabel(documentModuleName.value, form.status || 'draft') || '查看详情'
  const source = form.sourceOrderNo ? `来源单据：${form.sourceOrderNo}。` : ''
  const target = form.status === 'converted' && form.targetOrderNo ? `已生成下一单：${form.targetOrderNo}。` : ''
  return `${flowText}。当前流程位置：${activeConfig.value.title}${statusLabel(form.status || 'draft')}，下一步：${target || next}。${source}`
})

const summaryCards = computed(() => [
  { title: '请购单', count: scmState.value.purchaseRequests.length, desc: `${scmState.value.purchaseRequestItems.length} 行请购明细`, to: '/scm/purchase-requests' },
  { title: '询价单', count: scmState.value.purchaseInquiries.length, desc: `${scmState.value.purchaseInquiryItems.length} 行询价明细`, to: '/scm/purchase-inquiries' },
  { title: '核价单', count: scmState.value.priceApprovals.length, desc: `${scmState.value.priceApprovalItems.length} 行核价明细`, to: '/scm/price-approvals' },
  { title: '采购订单', count: scmState.value.purchaseOrders.length, desc: `${scmState.value.purchaseOrderItems.length} 行订单明细`, to: '/scm/purchase-orders' },
])
const pendingRows = computed(() => (scmState.value.pendingActions || []).filter((item) => item.status === 'pending'))

const scmOverviewCards = computed(() => [
  { title: '请购单数量', count: scmState.value.purchaseRequests.length, desc: `${scmState.value.purchaseRequestItems.length} 行请购明细`, to: '/scm/purchase-requests' },
  { title: '待审批请购', count: scmState.value.purchaseRequests.filter((item) => item.status === 'submitted').length, desc: '已提交但未审批的请购单', to: '/scm/purchase-requests' },
  { title: '待建询价', count: pendingRows.value.filter((item) => item.actionType === 'createInquiry').length, desc: '请购审批后等待生成询价', to: '/scm' },
  { title: '待确认报价', count: scmState.value.purchaseInquiries.filter((item) => item.status === 'sent').length, desc: '询价已发出等待报价确认', to: '/scm/purchase-inquiries' },
  { title: '待建核价', count: pendingRows.value.filter((item) => item.actionType === 'createPriceApproval').length, desc: '报价确认后等待生成核价', to: '/scm' },
  { title: '待建采购订单', count: pendingRows.value.filter((item) => item.actionType === 'createPurchaseOrder').length, desc: '核价审批后等待生成订单', to: '/scm' },
  { title: '已生成采购订单', count: scmState.value.purchaseOrders.length, desc: `${scmState.value.purchaseOrderItems.length} 行订单明细`, to: '/scm/purchase-orders' },
  { title: '采购订单金额', count: scmState.value.purchaseOrders.reduce((sum, item) => sum + Number(item.totalAmount || 0), 0).toFixed(2), desc: '当前采购订单总金额', to: '/scm/purchase-orders' },
])

const detailRows = computed(() => {
  if (canCreateRequestDetail.value && !form.id) return draftRequestDetails.value
  return form.id && activeConfig.value ? activeConfig.value.detailGet(form.id) : []
})
const detailSummaryText = computed(() => {
  const totalQty = detailRows.value.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
  const totalAmount = activeType.value === 'order'
    ? detailRows.value.reduce((sum, item) => sum + Number(item.amount || 0), 0)
    : 0
  return activeType.value === 'order'
    ? `${detailRows.value.length} 行，数量 ${totalQty}，金额 ${totalAmount.toFixed(2)}`
    : `${detailRows.value.length} 行，数量 ${totalQty}`
})

const listRows = computed(() => {
  if (!activeConfig.value) return []
  return scmState.value[activeConfig.value.collection].map((row) => enrichListRow({ ...row, ...buildSummary(row) }))
})

const listColumns = computed(() => {
  if (!activeConfig.value) return []
  return activeConfig.value.columns.map((column) => ({
    ...column,
    filterType: column.filterType || inferColumnFilterType(column.key),
  }))
})

const filteredRows = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  const quickFiltered = listRows.value.filter((row) => {
    const matchStatus = !statusFilter.value || row.status === statusFilter.value
    const searchable = listColumns.value.map((column) => formatListCell(row, column.key)).join(' ')
    const matchText = !text || `${JSON.stringify(row)} ${searchable}`.toLowerCase().includes(text)
    return matchStatus && matchText
  })
  return applyColumnFilters(quickFiltered, columnFilters, listColumns.value)
})

const sortedRows = computed(() => applySorting(filteredRows.value, sortState, listColumns.value))
const pagedRows = computed(() => applyPagination(sortedRows.value, currentPage.value, pageSize.value))
const selectedIds = computed(() => selectedRows.value.map((row) => row.id).filter(Boolean))
const listActionColumnWidth = computed(() => getActionColumnWidthForRows(pagedRows.value, scmListRowActions, ['查看明细', '编辑']))
const currentSortText = computed(() => {
  if (!sortState.key) return '当前排序：默认顺序'
  const column = listColumns.value.find((item) => item.key === sortState.key)
  return `当前排序：${column?.label || sortState.key} / ${sortState.direction === 'desc' ? '降序' : '升序'}`
})
const selectedRowsForBatch = computed(() => selectedRows.value || [])
const scmBatchCounts = computed(() => {
  const rows = selectedRowsForBatch.value
  const approvalAction = (row) => getNextApprovalAction(documentModuleName.value, row.status || 'draft')
  return {
    submit: rows.filter((row) => ['draft', 'rejected'].includes(row.status)).length,
    approve: rows.filter((row) => ['review', 'recheck', 'approve'].includes(approvalAction(row))).length,
    convert: rows.filter((row) => row.status === 'approved' || (activeType.value === 'inquiry' && ['quoted', 'completed'].includes(row.status))).length,
    issue: rows.filter((row) => row.status === 'approved').length,
    wms: rows.filter((row) => row.status === 'issued').length,
  }
})
const activeBatchExecutableCount = computed(() => Math.max(...batchActions.value.map((action) => action.executableCount || 0), 0))
const batchActions = computed(() => {
  if (!documentModuleName.value) return []
  const actions = []
  if (['request', 'inquiry', 'approval', 'order'].includes(activeType.value)) {
    actions.push({ label: activeType.value === 'order' ? '批量提报采购订单' : '批量提报', executableCount: scmBatchCounts.value.submit, disabled: !scmBatchCounts.value.submit, disabledReason: '所选记录没有可提报单据。', handler: () => batchSubmitDocuments(documentModuleName.value, selectedIds.value) })
  }
  if (['request', 'inquiry', 'approval', 'order'].includes(activeType.value)) {
    actions.push({ label: '批量审核/复核/审批', executableCount: scmBatchCounts.value.approve, disabled: !scmBatchCounts.value.approve, disabledReason: '所选记录没有待审核/待复核/待审批单据。', handler: () => batchApproveDocuments(documentModuleName.value, selectedIds.value) })
  }
  if (['request', 'inquiry', 'approval'].includes(activeType.value)) {
    const labels = { request: '批量生成询价单', inquiry: '批量生成核价单', approval: '批量生成采购订单' }
    actions.push({ label: labels[activeType.value], type: 'success', executableCount: scmBatchCounts.value.convert, disabled: !scmBatchCounts.value.convert, disabledReason: '所选记录没有可生成下一单的单据。', handler: () => batchConvertToNext(documentModuleName.value, selectedIds.value) })
  }
  if (activeType.value === 'order') {
    actions.push({ label: '批量下达采购订单', type: 'warning', executableCount: scmBatchCounts.value.issue, disabled: !scmBatchCounts.value.issue, disabledReason: '所选记录没有可下达采购订单。', handler: () => batchIssuePurchaseOrders(selectedIds.value) })
    actions.push({ label: '批量进入 WMS 到货预备', type: 'success', executableCount: scmBatchCounts.value.wms, disabled: !scmBatchCounts.value.wms, disabledReason: '所选记录没有已下达采购订单。', handler: batchGoToWmsReceivePreview })
  }
  return actions
})

function handleSelectionChange(rows) {
  selectedRows.value = rows || []
}

function clearSelection() {
  selectedRows.value = []
  listTableRef.value?.clearSelection?.()
}

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('请先提交收货预备')) return '建议先点击“批量提交收货预备”。'
  if (text.includes('已生成')) return '建议点击对应行的“查看来源单据”或“查看已生成单据”。'
  if (text.includes('状态')) return '建议检查当前单据状态后再执行批量操作。'
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

function batchGoToWmsReceivePreview() {
  const result = {
    total: selectedIds.value.length,
    successCount: 0,
    failedCount: 0,
    successItems: [],
    failedItems: [],
    failedReason: [],
  }
  selectedRows.value.forEach((row) => {
    const no = row.poNo || row.id
    if (row.status !== 'issued') {
      result.failedCount += 1
      result.failedItems.push({ id: row.id, no, reason: '采购订单未下达，不能进入 WMS 到货预备。' })
      result.failedReason.push(`${no}：采购订单未下达，不能进入 WMS 到货预备。`)
      return
    }
    result.successCount += 1
    result.successItems.push({ id: row.id, no })
  })
  addOperationLog({
    module: 'SCM',
    action: '批量进入 WMS 到货预备',
    targetType: 'purchaseOrder',
    targetId: selectedIds.value.join(','),
    targetNo: selectedRows.value.map((row) => row.poNo || row.id).join(','),
    detail: `成功 ${result.successCount} 条，失败 ${result.failedCount} 条；${result.failedReason.join('；')}`,
  })
  if (result.successCount) router.push('/wms/purchase-receive-preview')
  return result
}

function enrichListRow(row = {}) {
  if (activeType.value !== 'order') return row
  const deliveryUrgency = calculateDeliveryUrgency({
    ...row,
    expectedDeliveryDate: row.expectedDeliveryDate || row.earliestArrivalDate,
    planDeliveryDate: row.planDeliveryDate || row.plannedArrivalDate || row.earliestArrivalDate,
  })
  return { ...row, deliveryUrgency }
}

function displayHeaderRecord(row = {}) {
  if (activeType.value !== 'order') return row
  const enriched = enrichListRow(row)
  return {
    ...enriched,
    deliveryUrgency: getUrgencyLabel(enriched.deliveryUrgency),
  }
}

function runBatchAction(action) {
  if (!selectedIds.value.length) {
    notify('请先选择要批量处理的记录', 'warning')
    return
  }
  if (action.disabled) {
    notify(action.disabledReason || '所选记录没有可执行数据。', 'warning')
    addOperationLog({ module: 'SCM', action: '批量按钮禁用原因', targetType: documentModuleName.value, targetId: selectedIds.value.join(','), detail: action.disabledReason || '' })
    return
  }
  const result = action.handler()
  refresh()
  clearSelection()
  batchResult.value = normalizeBatchResult(result || {}, action)
  batchMessageType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function buildSummary(row) {
  const items = activeConfig.value.detailGet(row.id)
  const totalQuantity = items.reduce((sum, item) => sum + Number(item.quantity || 0), 0)
  const supplierCount = new Set(items.map((item) => item.supplierId).filter(Boolean)).size
  const approvedTotal = items.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.approvedPrice || 0), 0)
  const earliestRequiredDate = earliest(items.map((item) => item.requiredDate))
  const earliestArrivalDate = earliest(items.map((item) => item.planDeliveryDate || item.plannedArrivalDate || item.expectedDeliveryDate || item.requiredDate || item.demandDate || item.needDate || item.deliveryDate))
  return {
    lineCount: items.length,
    totalQuantity,
    supplierCount,
    approvedTotal: approvedTotal.toFixed(2),
    earliestRequiredDate,
    earliestArrivalDate,
  }
}

function earliest(values) {
  return values.filter(Boolean).sort()[0] || '-'
}

function statusLabel(status) {
  return getStatusDisplayLabel(documentModuleName.value, status) || {
    draft: '草稿',
    submitted: '已提交',
    approved: '已审批',
    closed: '已关闭',
    sent: '已发送',
    quoted: '已报价',
    rejected: '已驳回',
  }[status] || status || '草稿'
}

function statusType(status) {
  return {
    draft: 'info',
    submitted: 'warning',
    sent: 'warning',
    quoted: 'primary',
    approved: 'success',
    reviewed: 'primary',
    rechecked: 'primary',
    converted: 'success',
    issued: 'success',
    partiallyReceived: 'warning',
    fullyReceived: 'info',
    closed: 'info',
    rejected: 'danger',
  }[status] || 'info'
}

function isDepartmentField(key) {
  return [
    'departmentId',
    'department',
    'departmentName',
    'requestDepartment',
    'requestDepartmentName',
    'rootRequestDepartment',
    'requisitionDepartment',
    'requisitionDepartmentName',
    'demandDepartment',
    'demandDepartmentName',
    'rootDemandDepartment',
    'needDepartment',
    'purchaseDepartment',
    'purchaseDepartmentName',
    'rootPurchaseDepartment',
  ].includes(key)
}

function departmentDisplayValue(value) {
  if (!value) return '-'
  return getScmDisplayName('department', value) || value
}

function formatListCell(row, key) {
  if (key === 'deliveryUrgency') return getUrgencyLabel(row[key])
  if (['plannedArrivalDate', 'planDeliveryDate', 'expectedDeliveryDate', 'earliestArrivalDate'].includes(key) && !row[key]) return '未设日期'
  if (['requesterId', 'buyerId'].includes(key)) return getScmDisplayName('employee', row[key])
  if (isDepartmentField(key)) return departmentDisplayValue(row[key])
  if (key === 'supplierId') return getScmDisplayName('supplier', row[key])
  if (key === 'requestId') return scmState.value.purchaseRequests.find((item) => item.id === row[key])?.requestNo || '-'
  if (key === 'inquiryId') return scmState.value.purchaseInquiries.find((item) => item.id === row[key])?.inquiryNo || '-'
  if (key === 'totalAmount') return Number(row[key] || 0).toFixed(2)
  if (key === 'status') return getStatusDisplayLabel(rowModuleName(), row[key])
  return row[key] ?? '-'
}

function formatDetailCell(row, key) {
  if (key === 'supplierId') return getScmDisplayName('supplier', row[key])
  if (key === 'warehouseId') return getScmDisplayName('warehouse', row[key])
  if (key === 'locationId') return getScmDisplayName('location', row[key])
  if (key === 'suggestedSupplierId') return getScmDisplayName('supplier', row[key])
  if (key === 'status') return statusLabel(row[key])
  if (['amount', 'price', 'quotedPrice', 'approvedPrice'].includes(key)) return Number(row[key] || 0).toFixed(2)
  return row[key] ?? '-'
}

function inferColumnFilterType(key) {
  if (key === 'deliveryUrgency') return 'enum'
  if (key === 'status' || ['supplierId', 'buyerId', 'requesterId'].includes(key) || isDepartmentField(key)) return 'enum'
  if (key.toLowerCase().includes('date') || key.endsWith('At')) return 'date'
  if (['lineCount', 'totalQuantity', 'supplierCount', 'approvedTotal', 'totalAmount'].includes(key)) return 'number'
  return 'text'
}

function ensureColumnFilter(key) {
  if (!columnFilters[key]) {
    columnFilters[key] = {
      text: '',
      start: '',
      end: '',
      range: [],
      min: null,
      max: null,
      values: [],
    }
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
  const options = buildFilterOptions(listRows.value, column)
  return options.map((option) => {
    const sample = listRows.value.find((row) => String(row[column.key]) === String(option.value))
    return {
      ...option,
      label: sample ? formatListCell(sample, column.key) : option.label,
    }
  })
}

function handleDateFilterChange(key) {
  const filter = ensureColumnFilter(key)
  filter.start = filter.range?.[0] || ''
  filter.end = filter.range?.[1] || ''
}

function resetColumnFilters() {
  Object.keys(columnFilters).forEach((key) => {
    columnFilters[key] = {
      text: '',
      start: '',
      end: '',
      range: [],
      min: null,
      max: null,
      values: [],
    }
  })
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

function renumberDraftRequestDetails() {
  draftRequestDetails.value = draftRequestDetails.value.map((row, index) => ({ ...row, lineNo: index + 1 }))
}

function draftRequestDetailDefaults() {
  return {
    ...activeConfig.value.detailDefaults(),
    id: `draft-pr-line-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    lineNo: draftRequestDetails.value.length + 1,
    materialId: '',
    materialCode: '',
    materialName: '',
    specification: '',
    unit: '',
    quantity: 1,
    requiredDate: form.requiredDate || today(),
    suggestedSupplierId: '',
    purpose: '',
    remark: '',
  }
}

function saveDraftRequestDetail(payload = {}) {
  const next = { ...payload }
  if (!next.id) next.id = `draft-pr-line-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const index = draftRequestDetails.value.findIndex((row) => String(row.id) === String(next.id))
  if (index >= 0) {
    draftRequestDetails.value.splice(index, 1, { ...next, lineNo: index + 1 })
  } else {
    draftRequestDetails.value.push({ ...next, lineNo: draftRequestDetails.value.length + 1 })
  }
  renumberDraftRequestDetails()
}

function persistDraftRequestDetails(requestId) {
  draftRequestDetails.value.forEach((row) => {
    const { id, lineNo, ...payload } = row
    activeConfig.value.detailAdd(requestId, { ...payload, lineNo })
  })
  draftRequestDetails.value = []
}

function isDetailFieldDisabled(field = {}) {
  if (activeType.value === 'request' && ['materialCode', 'materialName', 'specification', 'unit'].includes(field.key)) return false
  return Boolean(field.readonly)
}

function sortIcon(key) {
  if (sortState.key !== key) return ''
  return sortState.direction === 'asc' ? '↑' : '↓'
}

function globalIndex(index) {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

function exportCurrentList() {
  const exportRows = sortedRows.value.map((row) => {
    const next = { ...row }
    listColumns.value.forEach((column) => {
      next[column.key] = formatListCell(row, column.key)
    })
    return next
  })
  exportRowsToCsvUtil(exportRows, listColumns.value, `scm-${activeType.value || 'list'}-${today()}.csv`)
  logScmReference('SCM导出筛选结果', `${exportRows.length} rows`)
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => {
    message.value = ''
  }, 2400)
}

function refresh() {
  scmState.value = getScmState()
}

function pendingStatusLabel(status) {
  return { pending: '待处理', done: '已完成', cancelled: '已取消' }[status] || status
}

function handlePending(row) {
  const outcome = processPendingAction(row.id)
  if (!outcome.success) {
    notify(outcome.error || '待处理流程执行失败', 'warning')
    return
  }
  refresh()
  notify('待处理流程已完成')
  if (outcome.targetPath) router.push(outcome.targetPath)
}

function cancelPending(row) {
  const outcome = cancelPendingAction(row.id)
  if (!outcome.success) {
    notify(outcome.error || '取消失败', 'warning')
    return
  }
  refresh()
  notify('待处理流程已取消')
}

function clearFilters() {
  keyword.value = ''
  statusFilter.value = ''
  resetColumnFilters()
  resetSorting()
  currentPage.value = 1
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

function suggestionRecords() {
  const rows = (keyword.value || statusFilter.value || hasActiveColumnFilters()) ? filteredRows.value : listRows.value
  return rows.flatMap((row) => {
    const items = activeConfig.value?.detailGet(row.id) || []
    return [
      {
        no: row[activeConfig.value.noField],
        supplier: formatListCell(row, 'supplierId'),
        buyer: formatListCell(row, 'buyerId'),
        requester: formatListCell(row, 'requesterId'),
        department: formatListCell(row, 'departmentId'),
        requestDepartment: formatListCell(row, 'requestDepartment'),
        rootRequestDepartment: formatListCell(row, 'rootRequestDepartment'),
        demandDepartment: formatListCell(row, 'demandDepartment'),
        rootDemandDepartment: formatListCell(row, 'rootDemandDepartment'),
        purchaseDepartment: formatListCell(row, 'purchaseDepartment'),
        rootPurchaseDepartment: formatListCell(row, 'rootPurchaseDepartment'),
        status: statusLabel(row.status),
      },
      ...items.map((item) => ({
        materialCode: item.materialCode,
        materialName: item.materialName,
        supplier: getScmDisplayName('supplier', item.supplierId || item.suggestedSupplierId),
        status: statusLabel(row.status),
      })),
    ]
  })
}

function querySearchSuggestions(queryString, callback) {
  const suggestions = buildMultiFieldSuggestions(suggestionRecords(), ['no', 'supplier', 'buyer', 'requester', 'department', 'requestDepartment', 'rootRequestDepartment', 'demandDepartment', 'rootDemandDepartment', 'purchaseDepartment', 'rootPurchaseDepartment', 'status', 'materialCode', 'materialName'])
  callback(filterSuggestions(queryString, suggestions))
}

function handleSuggestionSelect(item) {
  keyword.value = item.value
  currentPage.value = 1
}

function rowModuleName() {
  return documentModuleName.value
}

function canEditRowHeader(row) {
  return canEditHeader(rowModuleName(), row.status || 'draft')
}

function rowReadonlyReason(row) {
  return getReadonlyReason(rowModuleName(), row.status || 'draft')
}

function openDetail(row) {
  router.push(activeConfig.value.detailPath(row.id))
}

function deleteCurrent(row) {
  activeConfig.value.delete(row.id)
  refresh()
  notify(`${activeConfig.value.title}已删除`)
}

function isActionAllowed(action, row = {}) {
  const status = row.status || 'draft'
  const handler = action.handler
  const matrix = new Map([
    [submitPurchaseRequest, ['draft', 'rejected']],
    [approvePurchaseRequest, ['submitted', 'reviewed', 'rechecked']],
    [convertRequest, ['approved']],
    [closePurchaseRequest, ['draft', 'submitted', 'reviewed', 'rechecked', 'approved']],
    [sendPurchaseInquiry, ['draft']],
    [confirmInquiryQuote, ['sent']],
    [convertInquiry, ['sent', 'quoted', 'approved', 'completed']],
    [closePurchaseInquiry, ['draft', 'sent', 'quoted']],
    [submitPriceApproval, ['draft', 'rejected']],
    [approvePriceApproval, ['submitted', 'reviewed', 'rechecked']],
    [rejectPriceApproval, ['submitted', 'reviewed', 'rechecked']],
    [convertApproval, ['approved']],
    [submitScmPurchaseOrder, ['draft']],
    [approveScmPurchaseOrder, ['submitted', 'reviewed', 'rechecked']],
    [issueScmPurchaseOrder, ['approved', 'converted']],
    [goToWmsReceivePreview, ['issued', 'partiallyReceived']],
    [closeScmPurchaseOrder, ['draft', 'submitted', 'reviewed', 'rechecked', 'approved', 'converted', 'issued']],
  ])
  const allowed = matrix.get(handler)
  return !allowed || allowed.includes(status)
}

function actionButtonLabel(action, row = {}) {
  const status = row.status || 'draft'
  const moduleName = rowModuleName()
  if ([submitPurchaseRequest, submitPriceApproval, submitScmPurchaseOrder].includes(action.handler)) {
    return getNextApprovalButtonLabel(moduleName, status) || action.label
  }
  if ([approvePurchaseRequest, approvePriceApproval, approveScmPurchaseOrder].includes(action.handler)) {
    return getNextApprovalButtonLabel(moduleName, status) || action.label
  }
  if (action.handler === convertRequest) return getNextBusinessAction('purchaseRequest', status) || '生成询价单'
  if (action.handler === convertInquiry) return getNextBusinessAction('purchaseInquiry', status) || '生成核价单'
  if (action.handler === convertApproval) return getNextBusinessAction('priceApproval', status) || '生成采购订单'
  if (action.handler === issueScmPurchaseOrder) return getNextBusinessAction('purchaseOrder', status) || '下达采购订单'
  if (action.handler === goToWmsReceivePreview) return getNextBusinessAction('purchaseOrder', status) || '进入 WMS 收货预备'
  return action.label
}

function getActionButtonClass(label) {
  return `app-action-button-${getActionButtonSize(label)}`
}

function scmListRowActions(row = {}) {
  return [
    '查看明细',
    '编辑',
    ...visibleListActions(row).map((action) => actionButtonLabel(action, row)),
    '删除',
  ]
}

function visibleListActions(row) {
  const actions = activeConfig.value?.listActions || []
  return actions.filter((action) => isActionAllowed(action, row))
}

function visibleDetailActions(row) {
  const actions = activeConfig.value?.detailActions || []
  return actions.filter((action) => isActionAllowed(action, row))
}

function validateHeader() {
  const missing = activeConfig.value.headerFields.find((field) => field.required && !String(form[field.key] ?? '').trim())
  if (missing) {
    notify(`请填写必填项：${missing.label}`, 'warning')
    return false
  }
  return true
}

function validateDetail() {
  if (activeType.value === 'request' && !String(detailForm.materialId || detailForm.materialCode || detailForm.materialName || '').trim()) {
    notify('请填写物料编码或物料名称，或从物料引用源选择物料。', 'warning')
    return false
  }
  const missing = activeConfig.value.detailFields.find((field) => field.required && !String(detailForm[field.key] ?? '').trim())
  if (missing) {
    notify(`请填写明细必填项：${missing.label}`, 'warning')
    return false
  }
  if (Number(detailForm.quantity || 0) <= 0) {
    notify('明细数量必须大于0', 'warning')
    return false
  }
  if (activeType.value === 'approval' && Number(detailForm.approvedPrice || 0) <= 0) {
    notify('核准价格必须大于0', 'warning')
    return false
  }
  if (activeType.value === 'order' && Number(detailForm.planPrice ?? detailForm.price ?? 0) < 0) {
    notify('采购订单明细单价必须大于0', 'warning')
    return false
  }
  return true
}

function saveCurrent() {
  if (isBlockedCreatePage.value) {
    logScmReference(`拦截${activeConfig.value?.title || '单据'}空白新增`, blockedCreateMessage.value)
    notify(blockedCreateMessage.value, 'warning')
    return
  }
  if (!headerEditable.value) {
    notify(documentReadonlyReason.value || '当前状态不能编辑单据头', 'warning')
    return
  }
  if (!validateHeader()) return
  const payload = { ...form }
  if (pageMode.value === 'create' || !payload.id) {
    if (canCreateRequestDetail.value) {
      payload.status = 'draft'
      payload.targetModule = ''
      payload.targetOrderId = ''
      payload.targetOrderNo = ''
    }
    const id = activeConfig.value.create(payload)
    if (canCreateRequestDetail.value && draftRequestDetails.value.length) persistDraftRequestDetails(id)
    refresh()
    notify(`${activeConfig.value.title}已新增，请继续维护明细`)
    router.push(activeConfig.value.detailPath(id))
    return
  }
  activeConfig.value.update(payload.id, payload)
  refresh()
  syncForm()
  notify(`${activeConfig.value.title}已保存`)
}

function startAddDetail() {
  if (!lineAddable.value) {
    notify(lineActionReason.value || '当前状态不能新增明细', 'warning')
    return
  }
  resetObject(detailForm, canCreateRequestDetail.value && !form.id ? draftRequestDetailDefaults() : activeConfig.value.detailDefaults())
  handleDetailFieldChange('materialId')
  applyDefaultPriceToDetail()
  detailEditorVisible.value = true
}

function startEditDetail(row) {
  if (!lineEditable.value) {
    notify(documentReadonlyReason.value || '当前状态不能编辑明细', 'warning')
    return
  }
  resetObject(detailForm, row)
  detailEditorVisible.value = true
}

function cancelDetail() {
  detailEditorVisible.value = false
  resetObject(detailForm, {})
}

function saveDetail() {
  if (!form.id) {
    if (canCreateRequestDetail.value) {
      if (!validateDetail()) return
      saveDraftRequestDetail(detailForm)
      cancelDetail()
      notify('明细已加入当前草稿，请保存单据头后写入请购单。')
      return
    }
    if (!canCreateRequestDetail.value) {
      notify('请先保存单据头', 'warning')
      return
    }
    if (!validateHeader()) return
    const id = activeConfig.value.create({ ...form })
    refresh()
    resetObject(form, displayHeaderRecord(activeConfig.value.get(id) || { ...form, id }))
    router.push(activeConfig.value.detailPath(id))
  }
  if (detailForm.id && !lineEditable.value) {
    notify(documentReadonlyReason.value || '当前状态不能编辑明细', 'warning')
    return
  }
  if (!detailForm.id && !lineAddable.value) {
    notify(documentReadonlyReason.value || '当前状态不能新增明细', 'warning')
    return
  }
  if (!validateDetail()) return
  const payload = { ...detailForm }
  if (activeType.value === 'order') {
    const planPrice = Number(payload.planPrice ?? payload.price ?? 0)
    payload.price = planPrice
    payload.planAmount = Number((Number(payload.quantity || 0) * planPrice).toFixed(2))
    payload.amount = payload.planAmount
  }
  if (payload.id) {
    activeConfig.value.detailUpdate(payload.id, payload)
  } else {
    activeConfig.value.detailAdd(form.id, payload)
  }
  if (activeType.value === 'order') {
    recalculateScmPurchaseOrderAmount(form.id)
  }
  refresh()
  syncForm()
  cancelDetail()
  notify('明细已保存')
}

function deleteDetail(row) {
  if (!lineDeletable.value) {
    notify(lineActionReason.value || '当前状态不能删除明细', 'warning')
    return
  }
  if (canCreateRequestDetail.value && !form.id) {
    draftRequestDetails.value = draftRequestDetails.value.filter((item) => String(item.id) !== String(row.id))
    renumberDraftRequestDetails()
    notify('明细已删除')
    return
  }
  activeConfig.value.detailDelete(row.id)
  if (activeType.value === 'order') recalculateScmPurchaseOrderAmount(form.id)
  refresh()
  syncForm()
  notify('明细已删除')
}

function runAction(action, id) {
  if (!id) {
    notify('请先保存单据头', 'warning')
    return
  }
  const row = activeConfig.value?.get(id) || form
  if (!isActionAllowed(action, row)) {
    notify('当前状态不允许执行该操作', 'warning')
    logScmReference('SCM阻止非法状态操作', `${action.label}/${row.status || ''}`)
    return
  }
  const outcome = action.handler(id)
  if (outcome && outcome.success === false) {
    notify(outcome.error || `${action.label}失败`, 'warning')
    return
  }
  refresh()
  syncForm()
  notify(outcome?.message || `${action.label}完成`)
}

function convertRequest(id) {
  const newId = createInquiryFromRequest(id)
  if (newId?.success === false) {
    notify(newId.error, 'warning')
    if (newId.targetPath) router.push(newId.targetPath)
    return { success: false }
  }
  if (!newId) {
    notify('只有已审批且包含明细的请购单可以转询价', 'warning')
    return { success: false }
  }
  refresh()
  router.push(`/scm/purchase-inquiry/${newId}`)
  return { success: true }
}

function convertInquiry(id) {
  const newId = createPriceApprovalFromInquiry(id)
  if (newId?.success === false) {
    notify(newId.error, 'warning')
    if (newId.targetPath) router.push(newId.targetPath)
    return { success: false }
  }
  if (!newId) {
    notify('只有已发送/已报价且包含报价明细的询价单可以转核价', 'warning')
    return { success: false }
  }
  refresh()
  router.push(`/scm/price-approval/${newId}`)
  return { success: true }
}

function convertApproval(id) {
  const newIds = createPurchaseOrderFromPriceApproval(id)
  if (newIds?.success === false) {
    notify(newIds.error, 'warning')
    if (newIds.targetPath) router.push(newIds.targetPath)
    return { success: false }
  }
  if (!newIds?.length) {
    notify('只有已审批且包含明细的核价单可以转采购订单', 'warning')
    return { success: false }
  }
  refresh()
  router.push(`/scm/purchase-order/${newIds[0]}`)
  notify(`已按供应商生成 ${newIds.length} 张采购订单`)
  return { success: true }
}

function goToWmsReceivePreview() {
  router.push('/wms/purchase-receive-preview')
  return { success: true, message: '已进入 WMS 收货预备' }
}

function handleDetailFieldChange(key) {
  if (key === 'materialId') {
    const snapshot = snapshotMaterial(detailForm.materialId)
    Object.assign(detailForm, snapshot)
    if (activeType.value === 'request') detailForm.suggestedSupplierId = preferredSupplierId(detailForm.materialId)
    if (['inquiry', 'approval'].includes(activeType.value) && !detailForm.supplierId) {
      detailForm.supplierId = preferredSupplierId(detailForm.materialId)
    }
    if (activeType.value === 'order') {
      if (!detailForm.warehouseId && snapshot.defaultWarehouseId) detailForm.warehouseId = snapshot.defaultWarehouseId
      if (detailForm.warehouseId) detailForm.locationId = preferredLocationId(detailForm.warehouseId, snapshot)
    }
    logScmReference('SCM选择物料引用源', `${snapshot.materialCode || detailForm.materialId}`)
  }
  if (['materialId', 'supplierId'].includes(key)) {
    applyDefaultPriceToDetail()
  }
  if (key === 'warehouseId') {
    detailForm.locationId = preferredLocationId(detailForm.warehouseId, detailForm)
    logScmReference('SCM选择仓库库位引用源', `${detailForm.warehouseId || ''}/${detailForm.locationId || ''}`)
  }
  if (activeType.value === 'order' && ['quantity', 'price', 'planPrice'].includes(key)) {
    const planPrice = Number(detailForm.planPrice ?? detailForm.price ?? 0)
    detailForm.price = planPrice
    detailForm.planAmount = Number((Number(detailForm.quantity || 0) * planPrice).toFixed(2))
    detailForm.amount = detailForm.planAmount
  }
}

function handleHeaderFieldChange(key) {
  if (key === 'requesterId') {
    const employee = getEmployeeOptions().find((item) => String(item.id) === String(form.requesterId))
    const departmentId = employee?.raw?.departmentId
    const departmentName = employee?.raw?.departmentName || employee?.raw?.department
    const department = departmentOptions().find((item) => (
      String(item.id) === String(departmentId)
      || String(item.raw?.name || item.name) === String(departmentName)
    ))
    if (department) form.departmentId = department.id
    if (department) {
      form.requestDepartment = department.id
      if (!form.demandDepartment) form.demandDepartment = department.id
    }
    logScmReference('SCM选择请购人自动带部门', `${form.requesterId || ''}/${form.departmentId || ''}`)
  }
  if (key === 'supplierId' && activeType.value === 'order' && detailRows.value.length) {
    detailRows.value.forEach((row) => {
      const price = getDefaultPrice(row.materialId, form.supplierId)
      if (price) {
        updateScmPurchaseOrderItem(row.id, {
          ...row,
          price: Number(price.price || 0),
          planPrice: Number(price.price || 0),
          planAmount: Number((Number(row.quantity || 0) * Number(price.price || 0)).toFixed(2)),
          taxRate: Number(price.taxRate || 13),
          deliveryDays: Number(price.deliveryDays || 0),
          paymentTerms: price.paymentTerms || '',
          currency: price.currency || 'CNY',
          priceSourceId: price.id,
        })
      }
    })
    recalculateScmPurchaseOrderAmount(form.id)
    refresh()
    syncForm()
    logScmReference('SCM订单头供应商变更自动刷新价格', form.supplierId || '')
  }
}

function resetDemo() {
  resetScmState()
  refresh()
  notify('SCM演示数据已恢复')
}

function syncForm() {
  detailEditorVisible.value = false
  resetObject(detailForm, {})
  if (!activeConfig.value) return
  if (pageMode.value === 'create') {
    resetObject(form, activeConfig.value.defaults())
    draftRequestDetails.value = []
    return
  }
  draftRequestDetails.value = []
  if (pageMode.value === 'detail') {
    resetObject(form, displayHeaderRecord(activeConfig.value.get(route.params.id) || activeConfig.value.defaults()))
    return
  }
  resetObject(form, {})
}

watch(() => route.fullPath, () => {
  refresh()
  syncForm()
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
.scm-page {
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

.page-header p {
  margin: 6px 0 0;
  color: #475569;
}

.page-tabs,
.button-row,
.detail-actions,
.toolbar {
  display: flex;
  flex-wrap: wrap;
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

.batch-counts {
  color: #475569;
  font-size: 13px;
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
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-grid span,
.card-header span {
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
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 10px;
  margin: 0 0 14px;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.filter-item label {
  color: #475569;
  font-size: 12px;
}

.range-row,
.pagination-row {
  display: flex;
  align-items: center;
  gap: 8px;
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

.detail-form {
  max-width: 1280px;
}

.detail-actions {
  margin-top: 16px;
}

@media (max-width: 1200px) {
  .summary-grid,
  .form-grid,
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
  .form-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .toolbar .el-input,
  .toolbar .el-select {
    width: 100%;
  }
}
</style>
