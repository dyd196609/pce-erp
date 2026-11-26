<template>
  <main class="receive-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.9.3.1 WMS采购收货预备筛选修复</p>
        <h1 data-acceptance-id="page-business-title">{{ detail ? '采购收货预备单详情' : '采购收货预备' }}</h1>
        <p>本页只登记预计收货与待检信息，不直接增加库存、不生成库存入库流水、不生成应付。</p>
        <p class="app-current-module-badge" data-acceptance-id="page-breadcrumb-current-title">
          当前操作模块：<strong>采购收货预备</strong>
        </p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">WMS收货流程导航</span>
        <router-link class="app-nav-button" to="/wms">WMS库存管理</router-link>
        <router-link class="app-nav-button" to="/wms/inventory-balances">库存余额</router-link>
        <router-link class="app-nav-button" to="/wms/inventory-transactions">库存流水</router-link>
        <router-link class="app-nav-button" to="/wms/warehouse-tasks">仓库任务</router-link>
        <router-link class="app-nav-button" to="/wms/stock-warnings">库存预警</router-link>
        <router-link class="app-nav-button" to="/wms/purchase-receive-preview">采购到货预备</router-link>
        <router-link class="app-nav-button app-nav-button-active" to="/wms/purchase-receives">
          采购收货预备
          <span class="app-current-tag">当前</span>
        </router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />
    <RawIncomingLinePanel v-if="['/wms/purchase-receive-preview','/wms/purchase-receives'].includes(route.path)"
      mode="receipt" @changed="refresh" />

    <section v-if="detail" class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ detail.receiveNo }}</h2>
              <span>{{ sourceTypeLabel(detail.sourceType) }} / {{ detail.sourceOrderNo || '-' }}</span>
            </div>
            <div class="button-row">
              <el-button v-if="canEditDetail" type="primary" @click="beginEdit">编辑收货信息</el-button>
              <el-button v-if="editMode" type="success" @click="saveDraft">保存收货预备</el-button>
              <el-button v-if="canSubmitDetail" type="warning" @click="submitDraft">提交收货预备</el-button>
              <el-button @click="goList(router, 'wms', 'purchaseReceives')">返回列表</el-button>
              <el-button @click="goParent(router, 'wms')">返回上级</el-button>
              <el-button v-if="hasSourceRoute(sourceRecord)" type="primary" @click="goSource(router, sourceRecord, notify)">{{ getSourceButtonLabel(sourceRecord) }}</el-button>
              <el-button v-if="!detail.formalAuthority && detail.status === 'received'" type="primary" @click="createInspection(detail)">生成来料检验单</el-button>
              <el-button v-if="detail.status === 'inspectionPrepared'" type="primary" @click="goInspection(detail)">查看来料检验单</el-button>
              <el-button v-if="!detail.formalAuthority && detail.status !== 'cancelled'" type="warning" @click="cancelReceive(detail)">取消风险较高</el-button>
            </div>
          </div>
        </template>
        <div class="info-grid">
          <article v-for="item in detailFields" :key="item.label">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </el-card>

      <el-card v-if="editMode" shadow="never">
        <template #header><h2>收货实际信息</h2></template>
        <div class="edit-grid">
          <label>
            <span>实际到货日期</span>
            <el-date-picker v-model="editDraft.actualArrivalDate" type="date" value-format="YYYY-MM-DD" />
          </label>
          <label>
            <span>送货单号</span>
            <el-input v-model="editDraft.deliveryNoteNo" />
          </label>
          <label>
            <span>承运方</span>
            <el-input v-model="editDraft.carrierName" />
          </label>
          <label>
            <span>车牌号</span>
            <el-input v-model="editDraft.vehicleNo" />
          </label>
          <label>
            <span>包装状态</span>
            <el-select v-model="editDraft.packageStatus">
              <el-option label="正常" value="normal" />
              <el-option label="破损" value="damaged" />
              <el-option label="异常" value="exception" />
            </el-select>
          </label>
          <label>
            <span>收货备注</span>
            <el-input v-model="editDraft.receiveRemark" />
          </label>
        </div>
      </el-card>

      <el-card shadow="never">
        <template #header><h2>收货预备明细</h2></template>
        <el-table :data="detailLines" border stripe height="520">
          <el-table-column prop="lineNo" label="序号" width="70" fixed="left" />
          <el-table-column prop="sourceOrderNo" label="来源采购订单号" min-width="160" />
          <el-table-column prop="sourceOrderLineNo" label="来源订单行号" width="120" />
          <el-table-column prop="rootRequestNo" label="原始请购单号" min-width="150" />
          <el-table-column prop="materialCode" label="物料编码" min-width="130" />
          <el-table-column prop="materialName" label="物料名称" min-width="150" />
          <el-table-column prop="spec" label="规格型号" min-width="120" />
          <el-table-column prop="unit" label="单位" width="80" />
          <el-table-column prop="orderedQty" label="订单数量" width="100" />
          <el-table-column prop="planPrice" label="计划单价" width="100" />
          <el-table-column prop="planAmount" label="计划金额" width="110" />
          <el-table-column prop="actualReceiveQty" label="实际收货数量" min-width="150">
            <template #default="{ row }">
              <el-input-number v-if="editMode" v-model="row.actualReceiveQty" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.actualReceiveQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="actualReceiveDate" label="实际收货日期" min-width="150">
            <template #default="{ row }">
              <el-date-picker v-if="editMode" v-model="row.actualReceiveDate" type="date" value-format="YYYY-MM-DD" />
              <span v-else>{{ row.actualReceiveDate || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="actualPrice" label="实际单价" min-width="130">
            <template #default="{ row }">
              <el-input-number v-if="editMode" v-model="row.actualPrice" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.actualPrice }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="actualAmount" label="实际金额" width="110" />
          <el-table-column prop="shortageQty" label="短交数量" width="100" />
          <el-table-column prop="overQty" label="超交数量" width="100" />
          <el-table-column prop="damageQty" label="破损数量" min-width="130">
            <template #default="{ row }">
              <el-input-number v-if="editMode" v-model="row.damageQty" :min="0" :precision="2" @change="recalculateLine(row)" />
              <span v-else>{{ row.damageQty }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="pendingInspectQty" label="待检数量" width="100" />
          <el-table-column prop="batchNo" label="批号" min-width="140">
            <template #default="{ row }">
              <el-input v-if="editMode" v-model="row.batchNo" />
              <span v-else>{{ row.batchNo || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="locationName" label="库位" min-width="130">
            <template #default="{ row }">
              <el-input v-if="editMode" v-model="row.locationName" />
              <span v-else>{{ row.locationName || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="deliveryNoteNo" label="送货单号" min-width="140">
            <template #default="{ row }">
              <el-input v-if="editMode" v-model="row.deliveryNoteNo" />
              <span v-else>{{ row.deliveryNoteNo || detail.deliveryNoteNo || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="packageStatus" label="包装状态" min-width="120">
            <template #default="{ row }">
              <el-select v-if="editMode" v-model="row.packageStatus">
                <el-option label="正常" value="normal" />
                <el-option label="破损" value="damaged" />
                <el-option label="异常" value="exception" />
              </el-select>
              <span v-else>{{ packageStatusLabel(row.packageStatus) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="exceptionReason" label="异常原因" min-width="180">
            <template #default="{ row }">
              <el-input v-if="editMode" v-model="row.exceptionReason" />
              <span v-else>{{ row.exceptionReason || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="sourceLineId" label="来源行ID" min-width="170" />
          <el-table-column prop="expectedDeliveryDate" label="计划到货日期" />
          <el-table-column prop="remark" label="备注" min-width="160" />
        </el-table>
      </el-card>
    </section>

    <section v-else class="operation-shell">
      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>收货预备单列表</h2>
              <span>支持从仓库任务或 SCM 已审批采购订单生成</span>
            </div>
            <div class="button-row">
              <el-button type="primary" @click="createFromFirstTask">从仓库任务生成</el-button>
              <el-button type="primary" @click="createFromFirstOrder">从已审批采购订单生成</el-button>
            </div>
          </div>
        </template>
        <div class="summary-grid">
          <article>
            <span>收货预备单</span>
            <strong>{{ receives.length }}</strong>
            <p>仅记录预计收货</p>
          </article>
          <article>
            <span>可用仓库任务</span>
            <strong>{{ candidateTasks.length }}</strong>
            <p>采购收货类仓库任务</p>
          </article>
          <article>
            <span>SCM已审批采购订单</span>
            <strong>{{ candidateOrders.length }}</strong>
            <p>可直接生成收货预备</p>
          </article>
          <article>
            <span>已生成检验预备</span>
            <strong>{{ receives.filter((item) => item.status === 'inspectionPrepared').length }}</strong>
            <p>已进入 QMS 预备</p>
          </article>
        </div>
      </el-card>

      <el-card
        shadow="never"
        data-acceptance-id="standard-list-toolbar"
        data-pce-page-id="purchase-receive-preview"
        data-pce-toolbar-for="purchase-receive-preview-main"
      >
        <template #header><h2 data-acceptance-id="page-internal-subject-title"><PceBusinessNameConsumer page-code="purchase-receive-preview" /></h2></template>
        <div class="toolbar">
          <el-button @click="quickSearchVisible = !quickSearchVisible">
            {{ quickSearchVisible ? '收起快速搜索' : '展开快速搜索' }}
          </el-button>
          <span class="sort-help">快速搜索用于跨字段临时查找；精准查询请使用高级筛选。</span>
        </div>

        <div v-if="quickSearchVisible" class="toolbar">
          <span data-acceptance-id="list-fuzzy-search-input">
            <el-autocomplete
              v-model="keyword"
              :fetch-suggestions="querySearchSuggestions"
              placeholder="搜索收货单、供应商、物料、状态"
              clearable
              @select="handleSuggestionSelect"
            />
          </span>
          <el-button data-acceptance-id="list-fuzzy-search-button" @click="clearSelection">鎼滅储</el-button>
          <el-button @click="keyword = ''">重置快速搜索</el-button>
        </div>

        <div class="toolbar">
          <el-button data-acceptance-id="list-clear-sort-button" @click="resetSorting">清除排序</el-button>
          <el-button type="success" data-acceptance-id="list-export-current-result-button" data-pce-export-for="purchase-receive-preview-main" @click="exportCurrentResults">导出当前结果</el-button>
          <el-button type="primary" plain @click="copyDiagnosticData">复制诊断数据</el-button>
          <span class="sort-help">排序：点击表格表头字段可升序/降序排序；点击“清除排序”恢复默认顺序。</span>
          <span class="sort-help">{{ currentSortText }}</span>
          <span data-acceptance-id="list-result-count-visible">当前结果 {{ sortedReceives.length }} 条</span>
          <span data-acceptance-id="business-flow-selected-count">已选择 {{ selectedRows.length }} 条</span>
          <el-button data-acceptance-id="list-advanced-filter-toggle" data-pce-filter-toggle-for="purchase-receive-preview-main" :aria-expanded="String(advancedFilterVisible)" @click="advancedFilterVisible = !advancedFilterVisible">
            {{ advancedFilterVisible ? '收起高级筛选' : '展开高级筛选' }}
          </el-button>
          <el-button data-acceptance-id="list-clear-filter-button" @click="clearAdvancedFilters">清空筛选</el-button>
        </div>

        <div v-if="advancedFilterVisible" class="filter-grid advanced-filter-panel" data-acceptance-id="list-advanced-filter-panel" data-pce-filter-for="purchase-receive-preview-main">
          <label v-for="field in advancedFilterFields" :key="field.key">
            <span>{{ field.label }}</span>
            <el-date-picker
              v-if="field.type === 'date'"
              v-model="advancedFilters[field.key]"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
            />
            <el-select
              v-else-if="field.type === 'enum'"
              v-model="advancedFilters[field.key]"
              multiple
              filterable
              clearable
              collapse-tags
              placeholder="请选择"
            >
              <el-option v-for="option in filterOptions(field)" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
            <el-input v-else v-model="advancedFilters[field.key]" clearable placeholder="模糊筛选" />
          </label>
        </div>

        <el-alert
          title="采购收货预备流程：采购收货预备 -> 填写实际到货信息 -> 提交收货 -> QMS来料检验。提交前不改变库存，不生成应付。"
          type="info"
          show-icon
          :closable="false"
        />
        <div class="batch-bar" data-pce-section="purchase-receive-batch-actions">
          <span>已选择 {{ selectedRows.length }} 条</span>
          <span>可提交收货 {{ receiveBatchCounts.submit }} 条</span>
          <span>可生成来料检验 {{ receiveBatchCounts.inspection }} 条</span>
          <span>将跳过 {{ selectedRows.length - activeBatchExecutableCount }} 条</span>
          <el-button size="small" @click="clearSelection">清空选择</el-button>
          <el-button size="small" type="warning" data-pce-action-id="submit-purchase-receives" :disabled="!receiveBatchCounts.submit" :title="receiveBatchCounts.submit ? '' : '所选记录没有可提交收货预备。'" @click="runBatchSubmit">批量提交收货预备</el-button>
          <el-button size="small" type="success" data-pce-action-id="create-incoming-inspections" :disabled="!receiveBatchCounts.inspection" :title="receiveInspectionDisabledReason" @click="runBatchInspection">批量生成来料检验</el-button>
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
        <BusinessTableScrollContainer acceptance-id="business-table-scroll-purchase-receive-preview-main" page-id="purchase-receive-preview" table-id="purchase-receive-preview-main">
        <el-table ref="listTableRef" :data="sortedReceives" border stripe height="520" class="global-sort-arrow" scrollbar-always-on @selection-change="handleSelectionChange" @sort-change="handleSortChange">
          <el-table-column type="selection" :selectable="(row) => !row.formalAuthority" width="48" fixed="left" class-name="business-table-selection-column" header-class-name="business-table-selection-column" />
          <el-table-column type="index" label="序号" width="70" fixed="left" class-name="pce-fixed-index-column" header-class-name="pce-fixed-index-column" />
          <el-table-column prop="receiveNo" label="收货预备单号" min-width="170" fixed="left" sortable="custom" class-name="pce-fixed-primary-no-column" header-class-name="pce-fixed-primary-no-column" />
          <el-table-column prop="sourceType" label="来源类型" sortable="custom">
            <template #default="{ row }">{{ sourceTypeLabel(row.sourceType) }}</template>
          </el-table-column>
          <el-table-column prop="sourceOrderNo" label="来源采购订单号" min-width="150" sortable="custom" />
          <el-table-column prop="sourceTaskNo" label="来源仓库任务号" min-width="150" sortable="custom" />
          <el-table-column prop="rootRequestNo" label="原始请购单号" min-width="150" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商" sortable="custom" />
          <el-table-column prop="receiverName" label="收货人" sortable="custom" />
          <el-table-column prop="warehouseName" label="仓库" sortable="custom" />
          <el-table-column prop="locationNames" label="库位" min-width="130" sortable="custom" />
          <el-table-column prop="batchNos" label="批号" min-width="140" sortable="custom" />
          <el-table-column prop="materialCodes" label="物料编码" min-width="150" sortable="custom" />
          <el-table-column prop="materialNames" label="物料名称" min-width="170" sortable="custom" />
          <el-table-column prop="totalOrderQty" label="数量" width="100" sortable="custom" />
          <el-table-column prop="totalActualReceiveQty" label="收货数量" width="110" sortable="custom" />
          <el-table-column prop="plannedArrivalDate" label="计划到货日期" sortable="custom" />
          <el-table-column prop="actualReceiveDate" label="实际到货日期" sortable="custom" />
          <el-table-column prop="submitStatus" label="是否已提交收货" min-width="130" sortable="custom" />
          <el-table-column prop="inspectionStatus" label="是否已生成来料检验" min-width="150" sortable="custom" />
          <el-table-column prop="deliveryNoteNo" label="送货单号" min-width="140" sortable="custom" />
          <el-table-column prop="status" label="收货状态" sortable="custom">
            <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="createdAt" label="生成时间" min-width="150" sortable="custom" />
          <el-table-column prop="remark" label="备注" min-width="180" sortable="custom" />
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['详情', '生成检验预备', '查看来料检验', '取消'])" class-name="payment-fixed-action-column" header-class-name="payment-fixed-action-column">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="router.push(`/wms/purchase-receive/${row.id}`)">详情</el-button>
                <el-button v-if="!row.formalAuthority && row.status === 'received'" size="small" class="app-action-button-md" type="primary" @click="createInspection(row)">生成检验预备</el-button>
                <el-button v-if="row.status === 'inspectionPrepared'" size="small" class="app-action-button-md" @click="goInspection(row)">查看来料检验</el-button>
                <el-button v-if="!row.formalAuthority && row.status !== 'cancelled'" size="small" class="app-action-button-sm" @click="cancelReceive(row)">取消</el-button>
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
import PceBusinessNameConsumer from '../components/PceBusinessNameConsumer.vue'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BusinessTableScrollContainer from '../components/BusinessTableScrollContainer.vue'
import {
  beginEditPurchaseReceive,
  batchCreateIncomingInspectionsFromReceives,
  batchSubmitPurchaseReceives,
  cancelPurchaseReceive,
  createInspectionPreviewFromPurchaseReceive,
  createPurchaseReceiveFromScmPurchaseOrder,
  createPurchaseReceiveFromWarehouseTask,
  getPurchaseReceiveById,
  listPurchaseReceives,
  savePurchaseReceiveDraft,
  submitPurchaseReceive,
} from '../wms/purchaseReceiveStore.js'
import { getReceivableScmPurchaseOrders, getWarehouseTasks } from '../wms/wmsStore.js'
import { listIncomingInspections } from '../qms/qmsStore.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
import { buildMultiFieldSuggestions, filterSuggestions } from '../runtime/filterSuggestionEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'
import { exportRowsToCsv as exportRowsToCsvUtil } from '../manufacturing/foundationTableUtils.js'
import { formalExecutionApi } from '@/api/formalExecution.js'
import RawIncomingLinePanel from '@/meta/components/RawIncomingLinePanel.vue'
import {
  getSourceButtonLabel,
  goList,
  goParent,
  goSource,
  hasSourceRoute,
} from '../runtime/navigationRules.js'

const route = useRoute()
const router = useRouter()
const receives = ref([])
const keyword = ref('')
const message = ref('')
const messageType = ref('success')
const sortState = ref({ key: '', direction: 'asc' })
const selectedRows = ref([])
const listTableRef = ref(null)
const copyStatus = ref('')
const batchResult = ref(null)
const batchMessageType = ref('success')
const editMode = ref(false)
const editDraft = ref({ lines: [] })
const quickSearchVisible = ref(false)
const advancedFilterVisible = ref(false)
const advancedFilters = reactive(defaultAdvancedFilters())

const detail = computed(() => {
  const id = route.params.id
  if (!id) return null
  return receives.value.find((record) => String(record.id) === String(id)) || null
})
const sourceRecord = computed(() => detail.value ? {
  sourceType: detail.value.sourceType,
  sourceOrderId: detail.value.sourceOrderId,
  sourceOrderNo: detail.value.sourceOrderNo,
} : {})
const candidateTasks = computed(() => getWarehouseTasks().filter((item) => item.taskType === 'purchaseReceive' && item.status !== 'cancelled'))
const candidateOrders = computed(() => getReceivableScmPurchaseOrders())
const canEditDetail = computed(() => detail.value && !detail.value.formalAuthority && ['prepared', 'receiving'].includes(detail.value.status))
const canSubmitDetail = computed(() => detail.value && !detail.value.formalAuthority && ['prepared', 'receiving'].includes(detail.value.status))
const detailLines = computed(() => editMode.value ? editDraft.value.lines || [] : detail.value?.lines || [])
const displayReceives = computed(() => receives.value.map(enrichReceiveRow))
const filteredReceives = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return displayReceives.value.filter((row) => {
    const quickText = `${JSON.stringify(row)} ${sourceTypeLabel(row.sourceType)} ${statusLabel(row.status)}`.toLowerCase()
    return (!text || quickText.includes(text)) && matchAdvancedFilters(row)
  })
})
const receiveSortColumns = [
  { key: 'receiveNo', sortType: 'string' },
  { key: 'sourceType', sortType: 'string' },
  { key: 'sourceOrderNo', sortType: 'string' },
  { key: 'sourceTaskNo', sortType: 'string' },
  { key: 'rootRequestNo', sortType: 'string' },
  { key: 'supplierName', sortType: 'string' },
  { key: 'receiverName', sortType: 'string' },
  { key: 'warehouseName', sortType: 'string' },
  { key: 'locationNames', sortType: 'string' },
  { key: 'batchNos', sortType: 'string' },
  { key: 'materialCodes', sortType: 'string' },
  { key: 'materialNames', sortType: 'string' },
  { key: 'totalOrderQty', sortType: 'number' },
  { key: 'totalActualReceiveQty', sortType: 'number' },
  { key: 'plannedArrivalDate', sortType: 'date' },
  { key: 'actualReceiveDate', sortType: 'date' },
  { key: 'submitStatus', sortType: 'string' },
  { key: 'inspectionStatus', sortType: 'string' },
  { key: 'deliveryNoteNo', sortType: 'string' },
  { key: 'status', sortType: 'status' },
  { key: 'createdAt', sortType: 'date' },
  { key: 'remark', sortType: 'string' },
]
const sortedReceives = computed(() => sortRecords(filteredReceives.value, sortState.value, receiveSortColumns))
const currentSortText = computed(() => {
  if (!sortState.value.key) return '当前排序：默认顺序'
  const labels = {
    receiveNo: '收货预备单号',
    sourceType: '来源类型',
    sourceOrderNo: '来源采购订单号',
    sourceTaskNo: '来源仓库任务号',
    rootRequestNo: '原始请购单号',
    supplierName: '供应商',
    receiverName: '收货人',
    warehouseName: '仓库',
    locationNames: '库位',
    batchNos: '批号',
    materialCodes: '物料编码',
    materialNames: '物料名称',
    totalOrderQty: '数量',
    totalActualReceiveQty: '收货数量',
    plannedArrivalDate: '计划到货日期',
    actualReceiveDate: '实际到货日期',
    submitStatus: '是否已提交收货',
    inspectionStatus: '是否已生成来料检验',
    deliveryNoteNo: '送货单号',
    status: '收货状态',
    createdAt: '生成时间',
    remark: '备注',
  }
  return `当前排序：${labels[sortState.value.key] || sortState.value.key} / ${sortState.value.direction === 'desc' ? '降序' : '升序'}`
})
const selectedIds = computed(() => selectedRows.value.map((row) => row.id).filter(Boolean))
const receiveBatchCounts = computed(() => ({
  submit: selectedRows.value.filter((row) => ['prepared', 'receiving'].includes(row.status)).length,
  inspection: selectedRows.value.filter((row) => row.status === 'received').length,
}))
const activeBatchExecutableCount = computed(() => Math.max(receiveBatchCounts.value.submit, receiveBatchCounts.value.inspection, 0))
const receiveInspectionDisabledReason = computed(() => {
  if (receiveBatchCounts.value.inspection) return ''
  if (!selectedRows.value.length) return '请先选择记录。'
  if (selectedRows.value.every((row) => ['prepared', 'receiving'].includes(row.status))) return '请先批量提交收货预备。'
  if (selectedRows.value.every((row) => row.status === 'inspectionPrepared')) return '所选记录均已生成来料检验。'
  return '所选记录没有可生成来料检验的已收货单据。'
})
const advancedFilterFields = [
  { key: 'receiveNo', label: '收货预备单号', type: 'enum' },
  { key: 'sourceOrderNo', label: '来源采购订单号', type: 'enum' },
  { key: 'sourceTaskNo', label: '来源仓库任务号', type: 'enum' },
  { key: 'rootRequestNo', label: '原始请购单号', type: 'enum' },
  { key: 'supplierName', label: '供应商', type: 'enum' },
  { key: 'receiverName', label: '收货人', type: 'enum' },
  { key: 'warehouseName', label: '仓库', type: 'enum' },
  { key: 'locationNames', label: '库位', type: 'enum' },
  { key: 'batchNos', label: '批号', type: 'enum' },
  { key: 'materialCodes', label: '物料编码', type: 'enum' },
  { key: 'materialNames', label: '物料名称', type: 'enum' },
  { key: 'plannedArrivalDate', label: '计划到货日期范围', type: 'date' },
  { key: 'actualReceiveDate', label: '实际到货日期范围', type: 'date' },
  { key: 'status', label: '收货状态', type: 'enum' },
  { key: 'submitStatus', label: '是否已提交收货', type: 'enum' },
  { key: 'inspectionStatus', label: '是否已生成来料检验', type: 'enum' },
  { key: 'deliveryNoteNo', label: '送货单号', type: 'enum' },
  { key: 'remark', label: '备注', type: 'text' },
]
const exportColumns = [
  { key: 'sourceOrderNo', label: '采购订单号' },
  { key: 'rootRequestNo', label: '来源请购单号' },
  { key: 'supplierName', label: '供应商' },
  { key: 'materialCodes', label: '物料编码' },
  { key: 'materialNames', label: '物料名称' },
  { key: 'specs', label: '规格型号' },
  { key: 'units', label: '单位' },
  { key: 'totalOrderQty', label: '数量' },
  { key: 'totalActualReceiveQty', label: '收货数量' },
  { key: 'warehouseName', label: '仓库' },
  { key: 'statusText', label: '状态' },
  { key: 'arrivalDate', label: '到货日期 / 计划日期' },
  { key: 'remark', label: '备注' },
]
const sortableColumns = receiveSortColumns.map((item) => item.key)
const diagnosticData = computed(() => ({
  page: 'purchase-receive-preview',
  version: 'V1.13.29.3.2',
  filterState: {
    quickSearch: keyword.value,
    advancedFilters: { ...advancedFilters },
  },
  sortState: { ...sortState.value },
  resultCount: sortedReceives.value.length,
  selectedCount: selectedRows.value.length,
  exportEnabled: true,
  sortableColumns,
  sortArrowStyle: 'no-tail-bold-arrow',
  sortArrowShape: 'upright-triangle',
  timestamp: new Date().toISOString(),
}))
const detailFields = computed(() => detail.value ? [
  { label: '收货预备单号', value: detail.value.receiveNo },
  { label: '来源类型', value: sourceTypeLabel(detail.value.sourceType) },
  { label: '来源采购订单号', value: detail.value.sourceOrderNo || '-' },
  { label: '来源核价单号', value: detail.value.sourcePriceApprovalNo || '-' },
  { label: '原始请购单号', value: detail.value.rootRequestNo || '-' },
  { label: '请购部门', value: detail.value.requestDepartment || '-' },
  { label: '需求部门', value: detail.value.demandDepartment || '-' },
  { label: '采购部门', value: detail.value.purchaseDepartment || '-' },
  { label: '供应商', value: detail.value.supplierName || '-' },
  { label: '采购员', value: detail.value.buyerName || '-' },
  { label: '仓库', value: detail.value.warehouseName || '-' },
  { label: '收货人', value: detail.value.receiverName || '-' },
  { label: '计划到货日期', value: detail.value.plannedArrivalDate || detail.value.expectedReceiveDate || '-' },
  { label: '实际到货日期', value: detail.value.actualReceiveDate || detail.value.actualArrivalDate || '-' },
  { label: '送货单号', value: detail.value.deliveryNoteNo || '-' },
  { label: '承运方', value: detail.value.carrierName || '-' },
  { label: '车牌号', value: detail.value.vehicleNo || '-' },
  { label: '包装状态', value: packageStatusLabel(detail.value.packageStatus) },
  { label: '订单总数', value: detail.value.totalOrderQty ?? 0 },
  { label: '实际收货总数', value: detail.value.totalActualReceiveQty ?? 0 },
  { label: '短交总数', value: detail.value.totalShortageQty ?? 0 },
  { label: '超交总数', value: detail.value.totalOverQty ?? 0 },
  { label: '破损总数', value: detail.value.totalDamageQty ?? 0 },
  { label: '实际总金额', value: detail.value.totalActualAmount ?? 0 },
  { label: '结算预备', value: detail.value.settlementReady ? '是' : '否' },
  { label: '状态', value: statusLabel(detail.value.status) },
  { label: '备注', value: detail.value.remark || '-' },
] : [])

function defaultAdvancedFilters() {
  return {
    receiveNo: '',
    sourceOrderNo: '',
    sourceTaskNo: '',
    rootRequestNo: '',
    supplierName: '',
    receiverName: '',
    warehouseName: '',
    locationNames: '',
    batchNos: '',
    materialCodes: '',
    materialNames: '',
    plannedArrivalDate: [],
    actualReceiveDate: [],
    status: [],
    submitStatus: [],
    inspectionStatus: [],
    deliveryNoteNo: '',
    remark: '',
  }
}

function cloneDraft(value) {
  return JSON.parse(JSON.stringify(value || { lines: [] }))
}

function syncEditDraft() {
  editDraft.value = cloneDraft(detail.value)
}

function adaptFormalReceipt(row = {}) {
  const quantity = Number(row.quantity || 0)
  return {
    ...row,
    sourceType: 'formalPurchaseReceipt',
    plannedArrivalDate: row.receiptDate || '',
    actualReceiveDate: row.receiptDate || '',
    totalOrderQty: quantity,
    totalActualReceiveQty: quantity,
    totalPlanAmount: Number(row.amount || 0),
    totalActualAmount: Number(row.amount || 0),
    settlementReady: ['received', 'closed'].includes(row.status),
    inspectionPrepared: Number(row.inspectionCount || 0) > 0,
    lines: Array.isArray(row.lines) ? row.lines : [],
    formalAuthority: true,
    authoritySource: 'procurement.PurchaseReceipt',
  }
}

async function refresh() {
  const response = await formalExecutionApi.purchaseReceiptFacts()
  if (!response?.success) {
    receives.value = []
    notify(response?.error?.message || '正式采购收货事实读取失败', 'error')
    return
  }
  const formalRows = (response.data?.receipts || []).map(adaptFormalReceipt)
  const allowedDrafts = listPurchaseReceives()
    .filter((row) => ['prepared', 'receiving'].includes(row.status))
    .map((row) => ({ ...row, draftAuthority: 'DRAFT_ALLOWED', formalAuthority: false }))
  receives.value = [...formalRows, ...allowedDrafts]
}

function notify(text, type = 'success') {
  message.value = text
  messageType.value = type
  window.clearTimeout(notify.timer)
  notify.timer = window.setTimeout(() => {
    message.value = ''
  }, 2400)
}

function handleSelectionChange(rows) {
  selectedRows.value = rows || []
}

function clearSelection() {
  selectedRows.value = []
  listTableRef.value?.clearSelection?.()
}

function resetSorting() {
  sortState.value = { key: '', direction: 'asc' }
  clearSelection()
}

function handleSortChange({ prop, order }) {
  sortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' }
  clearSelection()
}

function nextBatchSuggestion(reasons = []) {
  const text = reasons.join('；')
  if (text.includes('请先提交收货预备')) return '建议先点击“批量提交收货预备”。'
  if (text.includes('已生成')) return '建议点击对应行的“查看来料检验”。'
  if (text.includes('状态')) return '建议检查当前状态后再执行批量操作。'
  return '请按失败原因处理后重新执行。'
}

function normalizeBatchResult(result = {}, operationName = '批量操作') {
  const failedReason = result.failedReason || []
  return {
    operationName,
    total: result.total ?? selectedIds.value.length,
    successCount: result.successCount || 0,
    failedCount: result.failedCount || 0,
    failedReason,
    nextSuggestion: nextBatchSuggestion(failedReason),
  }
}

function showBatchResult(result, operationName) {
  refresh()
  clearSelection()
  batchResult.value = normalizeBatchResult(result || {}, operationName)
  batchMessageType.value = result?.failedCount ? (result.successCount ? 'warning' : 'error') : 'success'
}

function runBatchSubmit() {
  if (!selectedIds.value.length) return notify('请先选择要批量处理的收货预备单。', 'warning')
  if (!receiveBatchCounts.value.submit) return notify('所选记录没有可提交收货预备。', 'warning')
  showBatchResult(batchSubmitPurchaseReceives(selectedIds.value), '批量提交收货预备')
}

function runBatchInspection() {
  if (!selectedIds.value.length) return notify('请先选择要批量处理的收货预备单。', 'warning')
  if (!receiveBatchCounts.value.inspection) return notify(receiveInspectionDisabledReason.value, 'warning')
  showBatchResult(batchCreateIncomingInspectionsFromReceives(selectedIds.value), '批量生成来料检验')
}

function sourceTypeLabel(type) {
  return {
    warehouseTask: '仓库任务',
    scmPurchaseOrder: 'SCM采购订单',
    formalPurchaseReceipt: '正式采购收货',
  }[type] || type || '-'
}

function statusLabel(status) {
  return {
    draft: '草稿',
    prepared: '已预备',
    receiving: '收货中',
    received: '已收货',
    inspectionPrepared: '已生成检验预备',
    closed: '关闭',
    cancelled: '取消',
  }[status] || status || '-'
}

function statusType(status) {
  return {
    prepared: 'primary',
    receiving: 'warning',
    received: 'success',
    inspectionPrepared: 'success',
    closed: 'info',
    cancelled: 'info',
  }[status] || 'info'
}

function packageStatusLabel(status) {
  return {
    normal: '正常',
    damaged: '破损',
    exception: '异常',
  }[status] || status || '-'
}

function uniqueJoin(values = []) {
  return [...new Set(values.filter(Boolean))].join('、')
}

function enrichReceiveRow(row = {}) {
  const lines = row.lines || []
  const actualDate = row.actualReceiveDate || row.actualArrivalDate || uniqueJoin(lines.map((line) => line.actualReceiveDate))
  return {
    ...row,
    sourceTaskNo: row.sourceType === 'warehouseTask' ? row.sourceOrderNo : '',
    rootRequestNo: row.rootRequestNo || lines.find((line) => line.rootRequestNo)?.rootRequestNo || '',
    plannedArrivalDate: row.plannedArrivalDate || row.expectedReceiveDate || uniqueJoin(lines.map((line) => line.expectedDeliveryDate)),
    actualReceiveDate: actualDate,
    deliveryNoteNo: row.deliveryNoteNo || uniqueJoin(lines.map((line) => line.deliveryNoteNo)),
    locationNames: uniqueJoin(lines.map((line) => line.locationName)),
    batchNos: uniqueJoin(lines.map((line) => line.batchNo)),
    materialCodes: uniqueJoin(lines.map((line) => line.materialCode)),
    materialNames: uniqueJoin(lines.map((line) => line.materialName)),
    specs: uniqueJoin(lines.map((line) => line.spec)),
    units: uniqueJoin(lines.map((line) => line.unit)),
    statusText: statusLabel(row.status),
    arrivalDate: actualDate || row.plannedArrivalDate || row.expectedReceiveDate || uniqueJoin(lines.map((line) => line.expectedDeliveryDate)),
    submitStatus: ['received', 'inspectionPrepared', 'closed'].includes(row.status) ? '已提交' : '未提交',
    inspectionStatus: row.status === 'inspectionPrepared' ? '已生成' : '未生成',
  }
}

function textMatches(value, text) {
  const target = String(text || '').trim().toLowerCase()
  if (!target) return true
  return String(value || '').toLowerCase().includes(target)
}

function dateInRange(value, range = []) {
  if (!Array.isArray(range) || !range.length) return true
  const [start, end] = range
  if (!start && !end) return true
  if (!value) return false
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return false
  if (start && date < new Date(start)) return false
  if (end && date > new Date(`${end}T23:59:59`)) return false
  return true
}

function matchAdvancedFilters(row) {
  return advancedFilterFields.every((field) => {
    const value = row[field.key]
    const filter = advancedFilters[field.key]
    if (field.type === 'date') return dateInRange(value, filter)
    if (field.type === 'enum') {
      const values = Array.isArray(filter) ? filter.filter(Boolean) : []
      return !values.length || values.includes(String(value))
    }
    return textMatches(value, filter)
  })
}

function filterOptions(field) {
  const values = [...new Set(displayReceives.value.map((row) => row[field.key]).filter((value) => value !== '' && value != null))]
  return values.map((value) => ({ label: field.key === 'status' ? statusLabel(value) : String(value), value: String(value) }))
}

function clearAdvancedFilters() {
  Object.assign(advancedFilters, defaultAdvancedFilters())
  keyword.value = ''
  currentPageToFirst()
}

function currentPageToFirst() {
  clearSelection()
}

function recalculateLine(row) {
  const orderQty = Number(row.orderedQty ?? row.orderQty ?? row.plannedReceiveQty) || 0
  const actualQty = Number(row.actualReceiveQty) || 0
  const actualPrice = Number(row.actualPrice ?? row.planPrice) || 0
  const damageQty = Number(row.damageQty) || 0
  row.actualAmount = Number((actualQty * actualPrice).toFixed(2))
  row.shortageQty = Math.max(orderQty - actualQty, 0)
  row.overQty = Math.max(actualQty - orderQty, 0)
  row.pendingInspectQty = Math.max(actualQty - damageQty, 0)
}

function buildDraftPayload() {
  return {
    ...editDraft.value,
    lines: (editDraft.value.lines || []).map((line) => {
      line.deliveryNoteNo = line.deliveryNoteNo || editDraft.value.deliveryNoteNo || ''
      line.carrierName = line.carrierName || editDraft.value.carrierName || ''
      line.vehicleNo = line.vehicleNo || editDraft.value.vehicleNo || ''
      line.packageStatus = line.packageStatus || editDraft.value.packageStatus || 'normal'
      recalculateLine(line)
      return line
    }),
  }
}

function querySearchSuggestions(queryString, callback) {
  const records = displayReceives.value.flatMap((row) => [
    {
      receiveNo: row.receiveNo,
      sourceOrderNo: row.sourceOrderNo,
      supplierName: row.supplierName,
      warehouseName: row.warehouseName,
      receiverName: row.receiverName,
      status: statusLabel(row.status),
    },
    ...(row.lines || []).map((line) => ({
      materialCode: line.materialCode,
      materialName: line.materialName,
      batchNo: line.batchNo,
      locationName: line.locationName,
    })),
  ])
  const suggestions = buildMultiFieldSuggestions(records, ['receiveNo', 'sourceOrderNo', 'supplierName', 'warehouseName', 'receiverName', 'status', 'materialCode', 'materialName', 'batchNo', 'locationName'])
  callback(filterSuggestions(queryString, suggestions))
}

function handleSuggestionSelect(item) {
  keyword.value = item.value
}

function todayStamp() {
  return new Date().toISOString().slice(0, 10).replaceAll('-', '')
}

function exportCurrentResults() {
  exportRowsToCsvUtil(sortedReceives.value, exportColumns, `purchase-receive-preview-${todayStamp()}.csv`)
  notify(`已导出当前筛选结果 ${sortedReceives.value.length} 条`)
}

async function copyDiagnosticData() {
  const text = JSON.stringify(diagnosticData.value, null, 2)
  try {
    if (navigator?.clipboard?.writeText) await navigator.clipboard.writeText(text)
    else fallbackCopy(text)
    copyStatus.value = '已复制诊断数据'
    notify('已复制诊断数据')
  } catch (error) {
    try {
      fallbackCopy(text)
      copyStatus.value = '已复制诊断数据'
      notify('已复制诊断数据')
    } catch (fallbackError) {
      copyStatus.value = '复制失败，请重试'
      notify('复制失败，请重试', 'warning')
    }
  }
}

function fallbackCopy(text) {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', 'readonly')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  document.body.appendChild(textarea)
  textarea.select()
  document.execCommand('copy')
  document.body.removeChild(textarea)
}

function createFromFirstTask() {
  const task = candidateTasks.value[0]
  if (!task) return notify('暂无可用仓库任务', 'warning')
  const outcome = createPurchaseReceiveFromWarehouseTask(task.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`${outcome.existed ? '已存在' : '已生成'}采购收货预备单 ${outcome.receiveNo}，库存余额不变`)
}

function createFromFirstOrder() {
  const order = candidateOrders.value[0]
  if (!order) return notify('暂无可用已审批采购订单', 'warning')
  const outcome = createPurchaseReceiveFromScmPurchaseOrder(order.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify(`${outcome.existed ? '已存在' : '已生成'}采购收货预备单 ${outcome.receiveNo}，库存余额不变`)
}

async function createInspection(row) {
  const outcome = createInspectionPreviewFromPurchaseReceive(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  await nextTick()
  const target = listIncomingInspections().find((item) => String(item.id) === String(outcome.inspectionId))
  if (!target || detail.value?.status !== 'inspectionPrepared') {
    return notify('来料检验单生成结果校验失败，请勿重复生成', 'error')
  }
  notify(`${outcome.status === 'already_exists' ? '已存在' : '已生成'}来料检验单 ${outcome.inspectionNo}，库存余额不变`)
}

function goInspection(row) {
  const inspection = listIncomingInspections().find((item) => String(item.sourceReceiveId) === String(row.id) && item.status !== 'cancelled')
  if (!inspection) return notify('未找到来料检验单', 'warning')
  router.push(`/qms/incoming-inspection/${inspection.id}`)
}

function beginEdit() {
  if (!detail.value) return
  const outcome = beginEditPurchaseReceive(detail.value.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  editMode.value = true
  editDraft.value = cloneDraft(outcome.receive)
  notify('已进入收货信息编辑')
}

function saveDraft() {
  if (!detail.value) return
  const outcome = savePurchaseReceiveDraft(detail.value.id, buildDraftPayload())
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  editDraft.value = cloneDraft(outcome.receive)
  notify('收货预备已保存')
}

async function submitDraft() {
  if (!detail.value) return
  const payload = editMode.value ? buildDraftPayload() : detail.value
  const outcome = submitPurchaseReceive(detail.value.id, payload)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  editMode.value = false
  editDraft.value = cloneDraft(outcome.receive)
  await nextTick()
  const refreshed = detail.value
  if (!refreshed || refreshed.status !== 'received' || Number(refreshed.totalActualReceiveQty) !== Number(outcome.actualReceivedQuantity)) {
    return notify('采购收货预备提交结果校验失败，请勿重复提交', 'error')
  }
  notify('收货预备已提交，库存余额不变')
}

function cancelReceive(row) {
  const outcome = cancelPurchaseReceive(row.id)
  if (!outcome.success) return notify(outcome.error, 'warning')
  refresh()
  notify('采购收货预备单已取消')
}

watch(() => route.fullPath, () => {
  refresh()
  editMode.value = false
  quickSearchVisible.value = true
  advancedFilterVisible.value = false
  syncEditDraft()
}, { immediate: true })

watch(detail, syncEditDraft)
</script>

<style scoped>
.receive-page {
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

.eyebrow,
.summary-grid span,
.info-grid span,
.card-header span,
.filter-grid span {
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

.page-tabs,
.button-row,
.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.toolbar {
  margin-bottom: 12px;
}

.sort-help {
  color: #64748b;
  font-size: 13px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid #d9e4f2;
  border-radius: 8px;
  background: #f8fbff;
}

.filter-grid label {
  display: flex;
  flex-direction: column;
  gap: 6px;
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

.operation-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.summary-grid,
.info-grid,
.edit-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-grid article,
.info-grid article,
.edit-grid label {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  padding: 12px;
}

.edit-grid label span {
  display: block;
  margin-bottom: 6px;
  color: #64748b;
  font-size: 13px;
}

.summary-grid strong,
.info-grid strong {
  display: block;
  margin-top: 6px;
  font-size: 18px;
}

@media (max-width: 900px) {
  .page-header,
  .card-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .info-grid,
  .edit-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
