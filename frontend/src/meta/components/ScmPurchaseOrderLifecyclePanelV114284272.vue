<template>
  <section class="purchase-order-business-detail" data-version="V1.14.2.8.4.27.2.6"
    data-detail-view="PurchaseOrderDetailView"
    data-detail-renderer="PurchaseOrderDetailPage"
    data-permission-rule="PURCHASE_ORDER_VIEW_PERMISSION-001">
    <nav class="detail-navigation" aria-label="采购订单详情导航"
      data-governance-rule="DETAIL-NAVIGATION-001">
      <el-button @click="router.push('/scm/purchase-order')">返回列表</el-button>
      <el-button @click="router.push('/scm')">返回上一级</el-button>
      <el-button @click="openPrintPreview">打印采购订单</el-button>
      <el-button type="primary" plain :loading="refreshLoading"
        data-acceptance-id="purchase-order-refresh-button"
        @click="emit('reload-page-data')">刷新</el-button>
    </nav>
    <el-card shadow="never" data-acceptance-id="purchase-order-role-view-region">
      <template #header>
        <div class="panel-header">
          <div>
            <h2>采购订单业务视图</h2>
            <span>当前字段与导出内容均继承角色权限。</span>
          </div>
          <el-tag type="info">PurchaseOrderDetailView</el-tag>
        </div>
      </template>
      <el-alert type="info" :closable="false" show-icon
        :title="`${businessView.roleLabel}：页面和导出使用同一字段权限投影。`" />
    </el-card>

    <el-card shadow="never" data-acceptance-id="purchase-order-identity-region">
      <template #header>
        <div class="panel-header">
          <div><h2>采购订单业务编号</h2><span>编号唯一读取 PurchaseOrder.objectNo。</span></div>
          <el-tag :type="businessView.identity.numberSeparated ? 'success' : 'danger'">
            {{ businessView.identity.numberSeparated ? '编号已分离' : '编号冲突待核对' }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="采购订单编号">
          <strong class="business-number">{{ canonicalPurchaseOrderNumber }}</strong>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" data-acceptance-id="purchase-order-basic-information-region"
      data-detail-region="basic">
      <template #header>
        <div class="panel-header">
          <div><h2>采购订单基础信息</h2><span>{{ businessView.baseInfo.orderTypeLabel }}</span></div>
          <el-tag>{{ businessView.baseInfo.statusLabel }}</el-tag>
        </div>
      </template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="采购订单编号">
          <strong class="business-number">{{ canonicalPurchaseOrderNumber }}</strong>
        </el-descriptions-item>
        <el-descriptions-item v-if="selectedRole !== 'warehouse'" label="供应商">{{ businessView.baseInfo.supplierName }}</el-descriptions-item>
        <el-descriptions-item v-if="['buyer', 'management'].includes(selectedRole)" label="采购员">{{ businessView.baseInfo.buyerName }}</el-descriptions-item>
        <el-descriptions-item label="采购日期">{{ businessView.baseInfo.orderDate }}</el-descriptions-item>
        <el-descriptions-item label="当前状态">{{ businessView.baseInfo.statusLabel }}</el-descriptions-item>
        <el-descriptions-item label="数量">{{ businessView.baseInfo.totalQuantity }}</el-descriptions-item>
        <el-descriptions-item v-if="businessView.permissions.price" label="订单金额">
          {{ businessView.baseInfo.totalAmount.toFixed(2) }} {{ businessView.baseInfo.currency }}
        </el-descriptions-item>
        <el-descriptions-item label="计划到货日期">{{ businessView.baseInfo.plannedDeliveryDate }}</el-descriptions-item>
        <el-descriptions-item label="紧急程度">
          <el-tag :type="urgencyTagType(businessView.urgency.code)">{{ businessView.urgency.label }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item v-if="businessView.permissions.internalRemark" label="备注" :span="4">
          {{ businessView.baseInfo.remark }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="businessView.sourceTrace.visible" shadow="never"
      data-acceptance-id="purchase-order-source-trace-region"
      data-detail-region="source-relations"
      data-source-relations="sourcePurchaseRequestIds">
      <template #header>
        <div class="panel-header">
          <div><h2>来源关系</h2><span>来源追踪：{{ businessView.sourceTrace.sourceLabel }}</span></div>
          <el-tag :type="businessView.sourceTrace.traceable ? 'success' : 'warning'">
            {{ businessView.sourceTrace.traceable ? '来源可追溯' : '历史数据不可追溯' }}
          </el-tag>
        </div>
      </template>
      <div class="source-flow" aria-label="采购订单来源业务流程链">
        <article v-for="(group, index) in businessView.sourceTrace.groups" :key="group.nodeCode"
          class="source-node">
          <span class="source-node-index">{{ index + 1 }}</span>
          <strong>{{ group.label }}</strong>
          <el-tooltip v-if="group.values.length" :content="group.fullEvidence" placement="right">
            <el-tag type="info">{{ group.summary }}</el-tag>
          </el-tooltip>
          <small v-else>{{ group.summary }}</small>
        </article>
      </div>
      <el-alert v-if="lifecycleDetail.legacyIsolated" class="price-boundary" type="warning"
        :closable="false" show-icon
        title="历史采购订单：来源不可追溯时仍允许查看详情，且不会补造来源关系。" />
    </el-card>

    <el-card shadow="never" data-acceptance-id="purchase-order-material-detail-region"
      data-detail-region="material-detail"
      data-item-source="PurchaseOrderItem[]">
      <template #header>
        <div class="panel-header">
          <div>
            <h2>采购物料明细</h2>
            <span>采购执行价格仅在有权限的角色视图显示。</span>
          </div>
          <div class="material-count-proof">
            <el-tag :type="businessView.materialDetail.countConsistent ? 'success' : 'danger'">
              {{ businessView.materialDetail.rows.length }} 行
            </el-tag>
            <small>来源：{{ businessView.materialDetail.source }}</small>
          </div>
        </div>
      </template>
      <el-table :data="businessView.materialDetail.rows" border stripe class="pce-compact-business-table"
        empty-text="暂无采购物料">
        <el-table-column v-for="column in businessView.materialDetail.columns" :key="column.key"
          :prop="column.key" :label="column.label" :min-width="column.width">
          <template #default="{ row }">
            <span v-if="['unitPrice', 'amount'].includes(column.key)">{{ Number(row[column.key] || 0).toFixed(2) }}</span>
            <span v-else>{{ row[column.key] }}</span>
          </template>
        </el-table-column>
      </el-table>
      <el-alert class="price-boundary" type="info" :closable="false" show-icon
        :title="businessView.priceBoundary.message" />
    </el-card>

    <el-card v-if="businessView.permissions.lifecycle" shadow="never"
      data-acceptance-id="purchase-order-lifecycle-region"
      data-detail-region="lifecycle">
      <template #header>
        <div class="panel-header">
          <div><h2>生命周期状态</h2><span>状态只读展示，本页面不推进采购订单状态。</span></div>
          <el-tag :type="businessView.lifecycle.validStatus ? 'success' : 'warning'">
            {{ businessView.lifecycle.lifecycleStatusLabel }}
          </el-tag>
        </div>
      </template>
      <div class="lifecycle-track">
        <div v-for="(step, index) in businessView.lifecycle.steps" :key="step.status"
          class="lifecycle-step" :data-result="step.result">
          <span>{{ index + 1 }}</span><strong>{{ step.label }}</strong>
          <small>{{ stepResultLabel(step.result) }}</small>
        </div>
      </div>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="当前状态">{{ businessView.lifecycle.lifecycleStatusLabel }}</el-descriptions-item>
        <el-descriptions-item label="下一允许动作">{{ businessView.lifecycle.nextAction.label }}</el-descriptions-item>
      </el-descriptions>
      <h3>状态历史</h3>
      <el-table :data="businessView.lifecycle.history" border stripe empty-text="暂无状态历史">
        <el-table-column prop="statusLabel" label="采购订单状态" min-width="130" />
        <el-table-column prop="changedBy" label="操作人" min-width="150" />
        <el-table-column prop="changedAt" label="操作时间" min-width="190" />
        <el-table-column prop="reason" label="说明" min-width="260" />
      </el-table>
    </el-card>

    <el-card v-if="businessView.approval.visible" shadow="never"
      data-acceptance-id="purchase-order-approval-region">
      <template #header><h2>审批信息</h2></template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="审批状态">{{ businessView.approval.statusLabel }}</el-descriptions-item>
        <el-descriptions-item label="审批人">{{ businessView.approval.approvedBy }}</el-descriptions-item>
        <el-descriptions-item label="审批日期">{{ businessView.approval.approvedAt }}</el-descriptions-item>
        <el-descriptions-item label="审批意见">{{ businessView.approval.opinion }}</el-descriptions-item>
      </el-descriptions>
      <el-table v-if="businessView.approval.history.length" :data="businessView.approval.history"
        border stripe class="approval-history">
        <el-table-column prop="resultLabel" label="审批结果" min-width="130" />
        <el-table-column prop="approvedBy" label="审批人" min-width="150" />
        <el-table-column prop="approvedAt" label="审批时间" min-width="190" />
        <el-table-column prop="opinion" label="审批意见" min-width="240" />
      </el-table>
    </el-card>

    <el-card shadow="never" data-acceptance-id="purchase-order-document-maker-region">
      <template #header><h2>制单信息</h2></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="制单人">{{ businessView.documentMaker.createdBy }}</el-descriptions-item>
        <el-descriptions-item label="制单日期">{{ businessView.documentMaker.createdAt }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card shadow="never" data-acceptance-id="purchase-order-operation-region"
      data-detail-region="operations">
      <template #header>
        <div class="panel-header">
          <div><h2>操作区域</h2><span>仅承接既有查看、导出与打印能力，不增加业务动作。</span></div>
          <el-tag type="success">零新增业务动作</el-tag>
        </div>
      </template>
      <div class="role-actions">
        <el-select v-model="selectedRole" aria-label="采购订单角色视图" class="role-select">
          <el-option v-for="role in allowedRoleOptions" :key="role.code"
            :label="role.label" :value="role.code" />
        </el-select>
        <el-dropdown @command="exportForRole">
          <el-button type="primary">导出<el-icon class="el-icon--right"><ArrowDown /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="role in allowedRoleOptions" :key="role.code"
                :command="role.code">导出{{ role.exportLabel }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button v-if="businessView.lifecycle.nextAction.code !== 'none'" type="primary" plain
          :disabled="businessView.lifecycle.nextAction.mode === 'controlled_action_pending'"
          @click="handleNextAction">{{ businessView.lifecycle.nextAction.label }}</el-button>
        <span v-if="businessView.lifecycle.nextAction.mode === 'controlled_action_pending'">
          当前版本只展示受控入口，不执行状态推进。
        </span>
      </div>
    </el-card>

    <el-dialog v-model="printPreviewVisible" title="采购订单打印预览" width="96%"
      class="purchase-order-print-preview-dialog" destroy-on-close
      data-acceptance-id="purchase-order-print-preview"
      data-governance-rule="PRINT-FORM-001">
      <el-alert type="info" :closable="false" show-icon
        title="打印预览使用独立PurchaseOrderPrintViewModel，不复制详情页面DOM；可编辑签字栏只作用于本次打印。" />
      <div class="print-preview-workspace">
        <aside class="print-settings-panel" aria-label="打印设置区域"
          data-acceptance-id="purchase-order-print-settings">
          <h3>打印设置</h3>
          <el-form label-position="top">
            <el-form-item label="纸张">
              <el-select v-model="printSettings.paperSize" aria-label="打印纸张">
                <el-option label="A4" value="A4" />
              </el-select>
            </el-form-item>
            <el-form-item label="方向">
              <el-radio-group v-model="printSettings.orientation" aria-label="打印方向">
                <el-radio-button value="portrait">竖向</el-radio-button>
                <el-radio-button value="landscape">横向</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item label="缩放">
              <el-select v-model="printSettings.scale" aria-label="打印缩放">
                <el-option v-for="scale in [{ value: 80, label: '80%' }, { value: 90, label: '90%' },
                  { value: 100, label: '100%' }, { value: 110, label: '110%' }]" :key="scale.value"
                  :label="scale.label" :value="scale.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="页边距">
              <el-radio-group v-model="printSettings.margin" aria-label="打印页边距">
                <el-radio-button value="standard">标准</el-radio-button>
                <el-radio-button value="compact">紧凑</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-button type="primary" plain class="refresh-preview-button"
              @click="refreshPrintPreview">刷新预览</el-button>
          </el-form>
          <p>默认：A4 / 竖向 / 100% / 标准页边距</p>
        </aside>
        <iframe ref="printPreviewFrame" class="purchase-order-print-preview-frame"
          title="采购订单标准打印预览" :srcdoc="printPreviewHtml" />
      </div>
      <template #footer>
        <el-button @click="printPreviewVisible = false">关闭</el-button>
        <el-button type="primary" @click="executePreviewPrint">打印</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { stateManager } from '../runtime/stateManager.js'
import { buildPurchaseOrderLifecycleDetailReadModelV114284272 } from
  '../providers/purchaseOrderLifecycleDetailProviderV114284272.js'
import {
  PURCHASE_ORDER_VIEW_ROLES_V1142842724,
  buildPurchaseOrderViewModelV1142842724,
  resolvePurchaseOrderViewAccessV1142842724,
} from '../viewModels/purchaseOrderViewModelV1142842724.js'
import {
  buildPurchaseOrderExportTemplateV1142842724,
  purchaseOrderExportCsvV1142842724,
} from '../viewModels/purchaseOrderExportTemplateV1142842724.js'
import { buildPurchaseOrderPrintViewModelV11428427243 } from
  '../viewModels/purchaseOrderPrintViewModelV11428427243.js'
import { buildPurchaseOrderPrintPreviewDocumentV1142842725 } from
  '../runtime/purchaseOrderPrintPreviewRuntimeV1142842725.js'
import { getPurchaseOrderNumber } from
  '../domain/scm/purchaseOrder/purchaseOrderCanonicalNumber.js'

const props = defineProps({
  purchaseOrder: { type: Object, default: () => ({}) },
  orderLines: { type: Array, default: () => [] },
  lifecycleDetailModel: { type: Object, default: null },
  refreshLoading: { type: Boolean, default: false },
})
const emit = defineEmits(['export-audit', 'print-audit', 'reload-page-data'])
const router = useRouter()
const printPreviewVisible = ref(false)
const printPreviewHtml = ref('')
const printPreviewFrame = ref(null)
const printSettings = reactive({ paperSize: 'A4', orientation: 'portrait', scale: 100,
  margin: 'standard' })
const access = computed(() => resolvePurchaseOrderViewAccessV1142842724(stateManager.getRole()))
const selectedRole = ref(access.value.activeRole)
const lifecycleDetail = computed(() => props.lifecycleDetailModel
  || buildPurchaseOrderLifecycleDetailReadModelV114284272({
    purchaseOrder: props.purchaseOrder,
    orderLines: props.orderLines,
  }))
const businessView = computed(() => buildPurchaseOrderViewModelV1142842724({
  purchaseOrder: props.purchaseOrder,
  orderLines: lifecycleDetail.value.purchaseOrderItems,
  lifecycleDetail: lifecycleDetail.value,
  viewRole: access.value.allowedRoles.includes(selectedRole.value)
    ? selectedRole.value : access.value.activeRole,
}))
const canonicalPurchaseOrderNumber = computed(() => getPurchaseOrderNumber(props.purchaseOrder))
const allowedRoleOptions = computed(() => access.value.allowedRoles
  .map(code => PURCHASE_ORDER_VIEW_ROLES_V1142842724[code]))

watch(access, value => {
  if (!value.allowedRoles.includes(selectedRole.value)) selectedRole.value = value.activeRole
})

function stepResultLabel(result) {
  return result === 'CURRENT' ? '当前状态' : result === 'COMPLETED' ? '已完成'
    : result === 'TERMINATED' ? '已终止' : '待推进'
}

function urgencyTagType(code) {
  return { normal: 'success', general: 'warning', warning: 'warning', urgent: 'warning',
    critical: 'danger', overdue: 'danger' }[code] || 'info'
}

function handleNextAction() {
  const action = businessView.value.lifecycle.nextAction
  if (action.mode === 'navigate' && action.route) return router.push(action.route)
  if (action.mode === 'focus_approval') {
    document.querySelector('[data-acceptance-id="purchase-order-approval-region"]')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return
  }
  ElMessage.warning('该动作由后续受控Action版本承接，本页面不会改变采购订单状态。')
}

function exportForRole(role) {
  if (!access.value.allowedRoles.includes(role)) {
    ElMessage.error('当前角色无权使用该导出模板。')
    return
  }
  const targetView = buildPurchaseOrderViewModelV1142842724({
    purchaseOrder: props.purchaseOrder,
    orderLines: lifecycleDetail.value.purchaseOrderItems,
    lifecycleDetail: lifecycleDetail.value,
    viewRole: role,
  })
  const template = buildPurchaseOrderExportTemplateV1142842724(targetView)
  const blob = new Blob([purchaseOrderExportCsvV1142842724(template)],
    { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${getPurchaseOrderNumber(props.purchaseOrder) || 'purchase-order'}-${template.templateLabel}.csv`
  anchor.click()
  URL.revokeObjectURL(url)
  emit('export-audit', { templateCode: template.templateCode,
    templateLabel: template.templateLabel, role, rowCount: template.rows.length })
  ElMessage.success(`已按${template.templateLabel}字段权限导出。`)
}

function buildCurrentPrintView() {
  return buildPurchaseOrderPrintViewModelV11428427243({
    purchaseOrderViewModel: businessView.value,
    companyName: stateManager.getTenant()?.name,
  })
}

function refreshPrintPreview() {
  const printView = buildCurrentPrintView()
  if (!printView.printMeta.numberSourceValid || !printView.printMeta.countConsistent) {
    ElMessage.error('采购订单编号或明细来源检查未通过，禁止打印。')
    return false
  }
  printPreviewHtml.value = buildPurchaseOrderPrintPreviewDocumentV1142842725(
    printView, printSettings)
  return true
}

function openPrintPreview() {
  if (!refreshPrintPreview()) return
  printPreviewVisible.value = true
}

function executePreviewPrint() {
  const frameWindow = printPreviewFrame.value?.contentWindow
  if (!frameWindow) {
    ElMessage.error('打印预览尚未就绪，请重试。')
    return
  }
  frameWindow.focus()
  frameWindow.print()
  emit('print-audit', { role: businessView.value.role,
    roleLabel: businessView.value.roleLabel,
    objectNo: getPurchaseOrderNumber(props.purchaseOrder),
    rowCount: businessView.value.materialDetail.rows.length,
    itemSource: 'PurchaseOrderItem[]' })
}
</script>

<style scoped>
.purchase-order-business-detail { display: grid; gap: 16px; width: 100%; min-width: 0; }
.detail-navigation { display: flex; justify-content: flex-end; gap: 10px; }
.panel-header, .role-actions, .source-tags, .lifecycle-track, .lifecycle-action {
  display: flex; align-items: center; gap: 12px;
}
.panel-header { justify-content: space-between; }
.panel-header h2 { margin: 0 0 4px; }
.role-select { width: 180px; }
.business-number { font-size: 16px; color: var(--el-color-primary); }
.source-flow { display: grid; gap: 18px; max-width: 520px; margin: 0 auto; padding: 4px 0 12px; }
.source-node { position: relative; display: grid; grid-template-columns: 32px minmax(120px, 1fr) auto;
  align-items: center; gap: 10px; min-height: 64px;
  padding: 12px; border: 1px solid var(--el-border-color); border-radius: 8px;
  background: var(--el-fill-color-light); }
.source-node:not(:last-child)::after { content: '↓'; position: absolute; left: 50%; bottom: -20px;
  z-index: 1; color: var(--el-color-primary); font-weight: 700; }
.source-node-index { width: 24px; height: 24px; display: inline-flex; align-items: center;
  justify-content: center; border-radius: 50%; color: #fff; background: var(--el-color-primary); }
.source-node small { color: #64748b; }
.material-count-proof { display: flex; align-items: center; gap: 10px; color: #64748b; }
.lifecycle-track { overflow-x: auto; padding: 8px 0 14px; }
.lifecycle-action { margin-top: 14px; }
.lifecycle-action span { color: #64748b; }
.lifecycle-step { display: grid; min-width: 132px; gap: 4px; padding: 12px;
  border: 1px solid var(--el-border-color); border-radius: 8px; background: var(--el-fill-color-light); }
.lifecycle-step[data-result='CURRENT'] { border-color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.lifecycle-step[data-result='COMPLETED'] { border-color: var(--el-color-success); }
.approval-history, .price-boundary, .source-identity { margin-top: 14px; }
.print-preview-workspace { display: grid; grid-template-columns: 220px minmax(0, 1fr);
  gap: 14px; align-items: start; margin-top: 14px; }
.print-settings-panel { padding: 14px; border: 1px solid var(--el-border-color);
  border-radius: 8px; background: var(--el-fill-color-light); }
.print-settings-panel h3 { margin: 0 0 12px; }
.print-settings-panel p { margin: 12px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.print-settings-panel :deep(.el-select), .refresh-preview-button { width: 100%; }
.purchase-order-print-preview-frame { width: 100%; height: 72vh;
  border: 1px solid var(--el-border-color); background: #fff; }
@media (max-width: 760px) {
  .panel-header { align-items: flex-start; flex-direction: column; }
  .role-actions { width: 100%; flex-wrap: wrap; }
  .print-preview-workspace { grid-template-columns: 1fr; }
}
</style>
