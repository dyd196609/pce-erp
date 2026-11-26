<template>
  <section class="po-detail-runtime" data-version="V1.14.2.8.4.27.2.28"
    data-active-runtime-component="PurchaseOrderDetailRuntimeViewV1142842727"
    data-runtime-rule="PURCHASE-ORDER-DETAIL-RUNTIME-002"
    data-migration-rule="PAGE-MIGRATION-002"
    data-detail-structure="basic-information+material-detail">
    <header class="business-hero" data-detail-region="business-view">
      <div>
        <span class="eyebrow">SCM · PURCHASE ORDER</span>
        <h2>采购订单业务视图</h2>
        <strong data-acceptance-id="purchase-order-canonical-number">采购订单编号：{{ numberViewModel.purchaseOrderNumber }}</strong>
        <p>订单执行、来源、物料、状态与输出统一视图</p>
      </div>
      <div class="hero-status">
        <span>{{ businessView.baseInfo.statusLabel }}</span>
        <small>数据更新时间：{{ dataUpdatedAt || '加载中' }}</small>
        <el-button :loading="refreshLoading" data-acceptance-id="purchase-order-refresh-button"
          @click="emit('reload-page-data')">{{ refreshButtonLabel }}</el-button>
        <small data-acceptance-id="purchase-order-refresh-feedback" aria-live="polite"
          :data-refresh-status="refreshStatus" :data-last-refresh-time="lastRefreshTime">
          刷新状态：{{ refreshStatusLabel }} · 最近刷新时间：{{ lastRefreshTime || '尚未手工刷新' }}
        </small>
      </div>
    </header>

    <article class="business-card" data-detail-region="order-number-card">
      <header><div><span class="section-index">身份</span><h3>采购订单编号与来源编号</h3></div>
        <span class="source-count">来源 {{ sourceDocumentCount }} 项</span></header>
      <div class="number-card-grid" data-number-view-model="PurchaseOrderBusinessNumberViewModel"
        :data-canonical-number-source="numberViewModel.purchaseOrderNumberField">
        <div v-for="item in numberCards" :key="item.label" class="number-card">
          <span>{{ item.label }}</span>
          <ul><li v-for="value in item.values" :key="value" :title="value">{{ value }}</li></ul>
          <button type="button" :aria-label="`复制${item.label}`" @click="copyNumber(item)">复制</button>
        </div>
      </div>
    </article>

    <article class="business-card" data-detail-region="material-source-trace">
      <header><div><span class="section-index">来源</span><h3>物料来源与主数据绑定</h3></div>
        <el-button link type="primary" @click="router.push('/master-data/materials')">
          企业基础数据 → 物料数据
        </el-button>
      </header>
      <div class="material-source-list">
        <div v-for="row in materialRows" :key="`source-${row.id}`" class="material-source-row"
          :data-purchase-request-item-id="row.purchaseRequestItemId"
          :data-material-master-id="row.materialMasterId">
          <strong>{{ row.materialCode }} · {{ row.materialName }}</strong>
          <span>采购申请：{{ row.sourcePurchaseRequestNo || '来源未解析' }}</span>
          <span>采购申请明细：{{ row.purchaseRequestItemId || '来源未解析' }}</span>
          <span>规格：{{ row.specification || '未维护' }}</span>
          <span>单位：{{ row.unit || '未维护' }}</span>
          <PceBusinessStatus
            :status-code="row.materialMasterBound ? 'maintained' : 'missing'"
            :status-label="row.materialMaintenanceStatus || (row.materialMasterBound ? '已维护' : '物料主数据未维护')"
            source="server" />
        </div>
      </div>
    </article>

    <article class="business-card" data-detail-region="supplier-information"
      data-acceptance-id="purchase-order-supplier-information">
      <header><div><span class="section-index">供应商</span><h3>供应商信息</h3></div>
        <span data-schema-source="PurchaseOrder Supplier Schema">
          字段来源：{{ supplierInformationSchemaView.factSource }}
        </span></header>
      <dl class="supplier-grid">
        <div v-for="field in supplierInformationSchemaView.fields" :key="field.key"
          :data-schema-field="field.key" :data-business-field="field.businessField">
          <dt>{{ field.label }}</dt><dd>{{ field.value }}</dd>
        </div>
      </dl>
    </article>

    <article class="business-card" data-detail-region="basic-information">
      <header><div><span class="section-index">01</span><h3>采购订单基本信息</h3></div>
        <span data-schema-source="PurchaseOrder Schema">字段来源：PurchaseOrder Schema</span></header>
      <dl class="basic-grid" :data-schema-field-count="headerSchemaView.fields.length">
        <div v-for="(field, index) in headerSchemaView.fields" :key="field.key"
          :data-schema-field="field.key" :data-basic-field-index="index + 1">
          <span class="basic-field-index">{{ index + 1 }}</span>
          <dt>{{ field.label }}</dt><dd>{{ field.value }}</dd>
        </div>
      </dl>
    </article>

    <article class="business-card material-card" data-detail-region="material-detail"
      :data-current-purchase-order-id="purchaseOrder.id">
      <header><div><span class="section-index">02</span><h3>物料明细</h3></div>
        <span data-schema-source="PurchaseOrderItem Schema">字段来源：PurchaseOrderItem Schema · 当前 {{ currentPurchaseOrderItemCount }} · 过滤 {{ filteredItemCount }} · 渲染 {{ materialRows.length }}</span></header>
      <div class="material-wide-table" data-table-layout="sticky-header-horizontal-scroll">
        <table>
          <thead><tr><th v-for="column in materialColumns" :key="column.key">{{ column.label }}</th></tr></thead>
          <tbody :data-render-update="refreshActionTrace">
            <tr v-for="row in materialRows" :key="row.id || row.lineNo"
              data-purchase-order-item-row :data-purchase-order-item-id="row.id"
              :data-purchase-order-id="row.purchaseOrderId" :data-material-code="row.materialCode">
              <td v-for="column in materialColumns" :key="column.key">
                {{ materialCell(row, column.key) }}
              </td>
            </tr>
            <tr v-if="!materialRows.length"><td :colspan="materialColumns.length">暂无采购物料</td></tr>
          </tbody>
        </table>
      </div>
    </article>

    <article class="business-card" data-detail-region="source-relations">
      <header><div><span class="section-index">03</span><h3>来源关系</h3></div>
        <span>{{ businessView.sourceTrace.traceable ? '来源可追溯' : '历史数据不可追溯' }}</span></header>
      <div class="source-chain" aria-label="采购订单来源关系流程链">
        <template v-for="(group, index) in businessView.sourceTrace.groups" :key="group.nodeCode">
          <div class="source-chain-node">
            <span>{{ index + 1 }}</span><strong>{{ sourceNodeLabel(group.label) }}</strong>
            <small :title="group.fullEvidence">{{ group.summary }}</small>
          </div>
          <i v-if="index < businessView.sourceTrace.groups.length - 1">→</i>
        </template>
      </div>
    </article>

    <article class="business-card" data-detail-region="lifecycle">
      <header><div><span class="section-index">04</span><h3>生命周期状态</h3></div>
        <strong>{{ businessView.lifecycle.lifecycleStatusLabel }}</strong></header>
      <div class="lifecycle-rail">
        <div v-for="step in businessView.lifecycle.steps" :key="step.status"
          :class="['lifecycle-node', `is-${String(step.result).toLowerCase()}`]">
          <span></span><strong>{{ step.label }}</strong><small>{{ lifecycleResult(step.result) }}</small>
        </div>
      </div>
    </article>

    <article class="business-card operation-card" data-detail-region="operations">
      <header><div><span class="section-index">05</span><h3>操作区域</h3></div>
        <small>只读操作，不改变采购订单业务状态</small></header>
      <div class="operation-buttons">
        <el-button type="primary" @click="openPrintPreview">打印采购订单</el-button>
        <el-button @click="router.push('/scm/purchase-order')">返回列表</el-button>
        <el-button @click="router.back()">返回上一步</el-button>
      </div>
      <p class="refresh-proof" aria-live="polite" data-acceptance-id="refresh-real-data-result">
        {{ refreshResult || `Provider重新加载 ${providerReloadCount} 次 · 数据时间 ${dataUpdatedAt || '-'}` }}
      </p>
      <p class="refresh-proof item-source-proof" data-acceptance-id="purchase-order-item-isolation-count">
        Server Item Count {{ currentPurchaseOrderItemCount }} · DOM Item Count {{ materialRows.length }}
      </p>
      <p class="refresh-proof" data-acceptance-id="purchase-order-item-code-match">
        Server Item Codes {{ JSON.stringify(serverItemCodes) }} · DOM Item Codes {{ JSON.stringify(domItemCodes) }}
      </p>
      <p class="refresh-proof" data-acceptance-id="purchase-order-refresh-action-trace">{{ refreshActionTrace }}</p>
    </article>

    <el-dialog v-model="printPreviewVisible" title="采购订单打印预览" width="96%"
      class="purchase-order-print-preview-dialog" destroy-on-close
      data-acceptance-id="purchase-order-print-preview">
      <div class="print-preview-workspace">
        <aside class="print-settings-panel" aria-label="打印设置区域">
          <h3>打印设置</h3>
          <el-form label-position="top">
            <el-form-item label="输出用途">
              <el-select v-model="printSettings.outputClassification" aria-label="打印输出用途"
                @change="refreshPrintPreview">
                <el-option v-for="item in outputClassifications" :key="item.code"
                  :label="item.label" :value="item.code" />
              </el-select>
            </el-form-item>
            <p class="template-description">用途：{{ currentOutputDefinition.purpose }} · 字段：{{ currentOutputDefinition.fields }}</p>
            <el-form-item label="纸张"><el-select v-model="printSettings.paperSize" aria-label="打印纸张">
              <el-option label="A4" value="A4" /></el-select></el-form-item>
            <el-form-item label="方向"><el-radio-group v-model="printSettings.orientation" aria-label="打印方向">
              <el-radio-button value="portrait">竖向</el-radio-button>
              <el-radio-button value="landscape">横向</el-radio-button>
            </el-radio-group></el-form-item>
            <el-form-item label="缩放"><el-select v-model="printSettings.scale" aria-label="打印缩放">
              <el-option v-for="scale in [80, 90, 100, 110]" :key="scale" :label="`${scale}%`" :value="scale" />
            </el-select></el-form-item>
            <el-form-item label="页边距"><el-radio-group v-model="printSettings.margin" aria-label="打印页边距">
              <el-radio-button value="standard">标准</el-radio-button>
              <el-radio-button value="compact">紧凑</el-radio-button>
            </el-radio-group></el-form-item>
            <el-button type="primary" plain class="full-button" @click="refreshPrintPreview">刷新预览</el-button>
          </el-form>
        </aside>
        <iframe ref="printPreviewFrame" class="print-preview-frame" title="采购订单分类打印预览"
          :srcdoc="printPreviewHtml" />
      </div>
      <template #footer><el-button @click="printPreviewVisible = false">关闭</el-button>
        <el-button type="primary" @click="executePreviewPrint">打印</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PceBusinessStatus from './PceBusinessStatus.vue'
import { stateManager } from '../runtime/stateManager.js'
import { buildPurchaseOrderViewModelV1142842724 } from
  '../viewModels/purchaseOrderViewModelV1142842724.js'
import { buildPurchaseOrderPrintViewModelV11428427243 } from
  '../viewModels/purchaseOrderPrintViewModelV11428427243.js'
import { buildPurchaseOrderBusinessNumberViewModelV1142842729 } from
  '../viewModels/purchaseOrderBusinessNumberViewModelV1142842729.js'
import {
  PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728,
  buildPurchaseOrderBusinessPrintDocumentV1142842728,
} from '../runtime/purchaseOrderPrintBusinessRuntimeV1142842728.js'
import {
  buildPurchaseOrderHeaderSchemaViewV11428427213,
  buildPurchaseOrderSupplierSchemaViewV11428427228,
  getPurchaseOrderItemSchemaColumnsV11428427213,
} from '../runtime/purchaseOrderSchemaViewRuntimeV11428427213.js'
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

const props = defineProps({
  purchaseOrder: { type: Object, default: () => ({}) },
  orderLines: { type: Array, default: () => [] },
  lifecycleDetailModel: { type: Object, required: true },
  refreshLoading: { type: Boolean, default: false },
  dataUpdatedAt: { type: String, default: '' },
  providerReloadCount: { type: Number, default: 0 },
  refreshResult: { type: String, default: '' },
  currentPurchaseOrderItemCount: { type: Number, default: 0 },
  filteredItemCount: { type: Number, default: 0 },
  refreshActionTrace: { type: String, default: '' },
  refreshStatus: { type: String, default: 'idle' },
  lastRefreshTime: { type: String, default: '' },
  serverItemCodes: { type: Array, default: () => [] },
})
const emit = defineEmits(['reload-page-data', 'print-audit'])
const router = useRouter()
const printPreviewVisible = ref(false)
const printPreviewHtml = ref('')
const printPreviewFrame = ref(null)
const printSettings = reactive({ outputClassification: 'buyer', paperSize: 'A4',
  orientation: 'portrait', scale: 100, margin: 'standard' })
const outputClassifications = PURCHASE_ORDER_PRINT_BUSINESS_CLASSIFICATIONS_V1142842728
const businessView = computed(() => buildPurchaseOrderViewModelV1142842724({
  purchaseOrder: props.purchaseOrder,
  orderLines: props.orderLines,
  lifecycleDetail: props.lifecycleDetailModel,
  viewRole: 'management',
}))
const currentOutputDefinition = computed(() => outputClassifications.find(
  item => item.code === printSettings.outputClassification) || outputClassifications[0])
const sourceDocumentCount = computed(() => (businessView.value.sourceTrace.groups || [])
  .filter(group => group.nodeCode !== 'purchase_order')
  .reduce((sum, group) => sum + (group.values?.length || 0), 0))
const numberViewModel = computed(() => buildPurchaseOrderBusinessNumberViewModelV1142842729({
  purchaseOrder: props.purchaseOrder,
  businessView: businessView.value,
}))
const numberCards = computed(() => numberViewModel.value.cards)
const headerSchemaView = computed(() => buildPurchaseOrderHeaderSchemaViewV11428427213({
  purchaseOrder: props.purchaseOrder,
  baseInfo: businessView.value.baseInfo,
}))
const supplierInformationSchemaView = computed(() =>
  buildPurchaseOrderSupplierSchemaViewV11428427228({ purchaseOrder: props.purchaseOrder }))
const domItemCodes = computed(() => materialRows.value.map(row => row.materialCode))
const refreshStatusLabel = computed(() => ({ idle: '刷新', refreshing: '刷新中',
  success: '刷新成功', error: '刷新失败' }[props.refreshStatus] || '刷新'))
const refreshButtonLabel = computed(() => props.refreshLoading ? '刷新中'
  : props.refreshStatus === 'success' ? '刷新成功' : '刷新')
const materialColumns = getPurchaseOrderItemSchemaColumnsV11428427213()
const materialRows = computed(() => businessView.value.materialDetail.rows || [])

function money(value) { return Number(value || 0).toFixed(2) }
function materialCell(row, key) {
  return ['unitPrice', 'amount'].includes(key) ? money(row[key]) : (row[key] ?? '-')
}
function sourceNodeLabel(label) { return label === '采购订单准入Gate' ? 'PurchaseOrderGate' : label }
function lifecycleResult(result) {
  return result === 'CURRENT' ? '当前' : result === 'COMPLETED' ? '已完成' : '待推进'
}
function fallbackCopy(value) {
  const textarea = document.createElement('textarea'); textarea.value = value
  textarea.style.position = 'fixed'; textarea.style.left = '-9999px'; document.body.appendChild(textarea)
  textarea.select(); document.execCommand('copy'); document.body.removeChild(textarea)
}
async function copyNumber(item) {
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(item.copyValue)
    else fallbackCopy(item.copyValue)
    ElMessage.success(`${item.label}已复制`)
  } catch { fallbackCopy(item.copyValue); ElMessage.success(`${item.label}已复制`) }
}
function buildPrintView() {
  const model = buildPurchaseOrderPrintViewModelV11428427243({
    purchaseOrderViewModel: businessView.value, companyName: stateManager.getTenant()?.name,
  })
  return {
    ...model,
    basicInfo: {
      ...model.basicInfo,
      fields: [
        ...(model.basicInfo?.fields || []),
        { key: 'receiptRequirement', label: '收货要求',
          value: props.purchaseOrder.receiptRequirement || '按采购订单收货要求执行' },
        { key: 'deliveryRequirement', label: '交付要求',
          value: props.purchaseOrder.deliveryRequirement || '按采购订单约定交付' },
        { key: 'paymentTerms', label: '付款相关信息',
          value: props.purchaseOrder.paymentTerms || '按采购订单付款条款执行' },
      ],
    },
  }
}
function refreshPrintPreview() {
  printPreviewHtml.value = buildPurchaseOrderBusinessPrintDocumentV1142842728(
    buildPrintView(), printSettings)
}
function openPrintPreview() { refreshPrintPreview(); printPreviewVisible.value = true }
function executePreviewPrint() {
  const frameWindow = printPreviewFrame.value?.contentWindow
  if (!frameWindow) return ElMessage.error('打印预览尚未就绪，请重试。')
  frameWindow.focus(); frameWindow.print()
  emit('print-audit', { outputClassification: printSettings.outputClassification,
    objectNo: getPurchaseOrderNumber(props.purchaseOrder), businessWriteCount: 0 })
}
</script>

<style scoped>
.po-detail-runtime { display: grid; gap: 18px; width: 100%; min-width: 0; color: #172033; }
.business-hero { display: flex; justify-content: space-between; align-items: center; padding: 26px 30px;
  border-radius: 16px; color: #fff; background: linear-gradient(135deg,#163b65,#1f6f78); box-shadow: 0 12px 30px #163b6526; }
.eyebrow { font-size: 12px; letter-spacing: .16em; opacity: .72; }.business-hero h2 { margin: 6px 0; font-size: 28px; }
.business-hero p,.hero-status small { margin: 0; opacity: .8; }.hero-status { display:grid; gap:8px; text-align:right; }
.hero-status span { font-size: 18px; font-weight: 700; }.business-card { padding: 22px 24px; border: 1px solid #dfe6ef;
  border-radius: 14px; background: #fff; box-shadow: 0 5px 18px #1d35570d; min-width: 0; }
.business-card>header { display:flex; align-items:center; justify-content:space-between; gap:16px; margin-bottom:18px; }
.business-card>header>div { display:flex; align-items:center; gap:10px; }.business-card h3 { margin:0; font-size:19px; }
.section-index { color:#1b7280; font-size:12px; font-weight:800; letter-spacing:.08em; }.classification-card { border-left:5px solid #1b7280; }
.classification-grid,.basic-grid,.supplier-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:0; }
.classification-grid :deep(.el-select) { width:100%; }
.basic-grid { grid-template-columns:repeat(4,minmax(0,1fr)); }
.classification-grid>div,.basic-grid>div,.supplier-grid>div { padding:14px 16px; border-radius:10px; background:#f6f8fb; }
.basic-grid>div { display:grid; grid-template-columns:28px minmax(0,1fr); grid-template-rows:auto auto; column-gap:8px; }
.basic-field-index { grid-column:1; grid-row:1 / 3; align-self:center; color:#1b7280; font-size:12px; font-weight:800; }
.basic-grid dt,.basic-grid dd { grid-column:2; }
dt { color:#6b7484; font-size:12px; } dd { margin:7px 0 0; font-weight:700; overflow-wrap:anywhere; }
.number-card-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; }.number-card { display:grid; gap:9px;
  min-width:0; padding:17px; border:1px solid #dce4ed; border-radius:12px; background:linear-gradient(180deg,#fff,#f7fafc); }
.number-card span { color:#6b7484; font-size:12px; }.number-card ul { display:grid; gap:6px; min-width:0; margin:0; padding:0; list-style:none; }
.number-card li { max-width:100%; overflow-wrap:anywhere; font-size:15px; font-weight:700; }
.number-card button { justify-self:start; border:0; padding:0; color:#176b78; background:transparent; cursor:pointer; }.source-count,.status-pill { padding:5px 10px; border-radius:999px; background:#e5f4f2; color:#176b78; }
.source-chain { display:flex; align-items:center; gap:9px; overflow-x:auto; padding:8px 2px 14px; }.source-chain-node { display:grid; gap:6px; min-width:150px;
  padding:14px; border:1px solid #dce4ed; border-radius:12px; background:#f8fafc; }.source-chain-node>span { color:#1b7280; font-size:12px; font-weight:800; }
.source-chain-node small { max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#727d8e; }.source-chain i { color:#1b7280; font-style:normal; }
.material-wide-table { max-width:100%; max-height:430px; overflow:auto; border:1px solid #dce4ed; border-radius:10px; }
.material-wide-table table { width:100%; min-width:1500px; border-collapse:separate; border-spacing:0; }.material-wide-table th { position:sticky; top:0; z-index:2;
  padding:13px 14px; text-align:left; white-space:nowrap; color:#415065; background:#eaf0f5; border-bottom:1px solid #cdd7e2; }
.material-wide-table td { padding:13px 14px; white-space:nowrap; border-bottom:1px solid #edf1f5; }.material-wide-table tbody tr:hover { background:#f4faf9; }
.material-source-list { display:grid; gap:10px; }.material-source-row { display:grid;
  grid-template-columns:minmax(180px,1.4fr) repeat(4,minmax(130px,1fr)) auto; align-items:center;
  gap:12px; padding:13px 15px; border:1px solid #e1e7ee; border-radius:10px; background:#f8fafc; }
.lifecycle-rail { display:grid; grid-template-columns:repeat(6,minmax(110px,1fr)); gap:0; overflow-x:auto; padding:10px 0; }.lifecycle-node { position:relative; display:grid; gap:5px;
  min-width:120px; padding:0 12px; text-align:center; }.lifecycle-node::before { content:''; position:absolute; top:8px; left:0; right:0; height:2px; background:#d6dee8; }
.lifecycle-node>span { z-index:1; width:18px; height:18px; margin:0 auto 7px; border:4px solid #fff; border-radius:50%; background:#b3bfcc; box-shadow:0 0 0 1px #b3bfcc; }
.lifecycle-node.is-current>span { background:#176b78; box-shadow:0 0 0 1px #176b78; }.lifecycle-node.is-completed>span { background:#39a07b; box-shadow:0 0 0 1px #39a07b; }
.lifecycle-node small,.operation-card small { color:#727d8e; }.operation-buttons { display:flex; gap:10px; flex-wrap:wrap; }.refresh-proof { margin:14px 0 0; color:#607083; font-size:13px; }
.print-preview-workspace { display:grid; grid-template-columns:240px minmax(0,1fr); gap:14px; margin-top:8px; }.print-settings-panel { padding:15px; border:1px solid #dce4ed; border-radius:10px; background:#f7f9fb; }
.print-settings-panel h3 { margin:0 0 12px; }.template-description { margin:-8px 0 14px; color:#607083; font-size:12px; }.print-settings-panel :deep(.el-select),.full-button { width:100%; }
.print-preview-frame { width:100%; height:72vh; border:1px solid #dce4ed; background:#fff; }
@media(max-width:900px){.classification-grid,.number-card-grid,.basic-grid,.supplier-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.business-hero{align-items:flex-start;flex-direction:column;gap:16px}.hero-status{text-align:left}}
@media(max-width:900px){.material-source-row{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.classification-grid,.number-card-grid,.basic-grid,.supplier-grid,.print-preview-workspace,.material-source-row{grid-template-columns:1fr}}
</style>
