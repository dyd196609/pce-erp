<template>
  <main class="page" :data-acceptance-id="`${kind}-v83-content`">
    <section class="card" :data-acceptance-id="`${kind}-server-facts`">
      <Heading title="服务端持久事实" note="页面、API、复制诊断、StrictFacts 与验收报告复用同一服务端事实。" />
      <div class="grid">
        <Fact label="事实来源" value="server" />
        <Fact label="记录数量" :value="facts.recordCount" />
        <Fact label="事实加载状态" value="加载成功" />
        <Fact label="危险动作" :value="facts.dangerActionCount" />
        <Fact label="业务推进写入" :value="facts.businessProgressWriteCount" />
        <Fact label="下游对象" :value="facts.downstreamObjectCount" />
      </div>
    </section>

    <section class="card flow" data-acceptance-id="v83-business-flow">
      <Heading title="供应商结算业务链" note="对账、差异关闭与供应商确认构成应付确认依据；付款申请不代表已经付款。" />
      <div class="flow-line">
        <span>供应商对账</span><b>→</b><span>差异关闭</span><b>→</b><span>供应商确认</span>
        <b>→</b><span>应付确认</span><b>→</b><span>付款申请</span>
      </div>
    </section>

    <section class="card statistics" :data-acceptance-id="`${kind}-statistics`">
      <Heading :title="kind === 'payable' ? '应付确认统计' : '付款申请统计'" note="所有金额与数量均来自服务端事实。" />
      <div v-if="kind === 'payable'" class="grid">
        <Fact label="供应商数量" :value="facts.supplierCount" />
        <Fact label="应付确认数量" :value="facts.confirmationCount" />
        <Fact label="最终应付金额" :value="facts.confirmedAmount" />
        <Fact label="待确认数量" :value="facts.pendingCount" />
        <Fact label="已确认数量" :value="facts.confirmedCount" />
      </div>
      <div v-else class="grid">
        <Fact label="供应商数量" :value="facts.supplierCount" />
        <Fact label="付款申请数量" :value="facts.requestCount" />
        <Fact label="申请金额" :value="facts.requestAmount" />
        <Fact label="待后续付款" :value="facts.paymentPendingCount" />
      </div>
    </section>

    <section v-if="kind === 'request'" class="card warning" data-acceptance-id="payment-not-executed">
      <strong>付款申请完成 ≠ 已付款</strong>
      <p>当前对象仅记录付款申请及审批状态，不执行付款、不扣减资金、不生成银行流水。</p>
    </section>

    <section class="card operations" :data-acceptance-id="`${kind}-business-operation-region`">
      <Heading title="业务操作区域" note="动作由当前状态、服务端角色权限与 PCE Business Action Registry 共同决定。" />
      <div class="grid operation-facts">
        <Fact label="工作流动作数量" :value="facts.workflowActionCount" />
        <Fact label="当前可执行动作" :value="facts.availableActionCount" />
        <Fact label="已执行动作" :value="facts.executedActionCount" />
        <Fact label="审计记录" :value="facts.auditRecordCount" />
      </div>
      <div class="operation-list">
        <article
          v-for="item in workflowCards"
          :key="`${item.row.id}-${item.action.actionCode}`"
          class="operation-item"
          :data-action-code="item.action.actionCode"
          data-pce-action-source="PCE Business Action Registry"
        >
          <div>
            <span>当前状态：<strong>{{ item.row.statusLabel }}</strong></span>
            <span>当前角色：<strong>{{ item.action.roleLabel }}</strong></span>
            <span>可执行：<strong>{{ actionLabel(item.action) }}</strong></span>
          </div>
          <el-button type="primary" plain @click="executeAction(item.row, item.action)">
            {{ actionLabel(item.action) }}
          </el-button>
        </article>
      </div>
    </section>

    <section class="card" :data-acceptance-id="`${kind}-list`">
      <Heading :title="definition.listTitle" note="支持搜索、高级筛选、冻结列、横向滚动和当前结果导出。" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        :page-id="`v83-${kind}`"
        :table-id="`v83-${kind}-table`"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="definition.filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        :primary-field="definition.primaryField"
        :primary-label="definition.primaryLabel"
        :primary-width="240"
        min-width="1700px"
        :scroll-acceptance-id="`${kind}-horizontal-scroll`"
        :action-width="520"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event"
        @sort-change="handleSort"
      >
        <template #columns>
          <template v-if="kind === 'payable'">
            <el-table-column prop="supplierName" label="供应商" width="180" />
            <el-table-column prop="reconciliationNo" label="来源对账编号" width="220" />
            <el-table-column prop="period" label="对账期间" width="120" />
            <el-table-column prop="confirmedAmount" label="确认金额" width="150" />
            <el-table-column prop="qualifiedAmount" label="质量合格金额" width="160" />
            <el-table-column prop="deductionAmount" label="扣减金额" width="140" />
            <el-table-column prop="finalPayableAmount" label="最终应付金额" width="160" />
            <el-table-column prop="statusLabel" label="业务状态" width="170" />
          </template>
          <template v-else>
            <el-table-column prop="supplierName" label="供应商" width="180" />
            <el-table-column prop="payableConfirmationNo" label="来源应付确认编号" width="230" />
            <el-table-column prop="period" label="申请期间" width="120" />
            <el-table-column prop="requestAmount" label="申请金额" width="150" />
            <el-table-column prop="requestReason" label="申请原因" width="320" show-overflow-tooltip />
            <el-table-column prop="requestedBy" label="申请人" width="180" />
            <el-table-column prop="statusLabel" label="业务状态" width="190" />
          </template>
        </template>
        <template #actions="{ row }">
          <el-button size="small" plain @click="showRow(row)">查看详情</el-button>
          <el-button size="small" plain @click="showHistory(row)">状态历史</el-button>
          <el-button size="small" type="primary" plain @click="showOperations(row)">业务操作</el-button>
          <el-button v-if="kind === 'payable' && row.statusCode === 'ready_for_payment_request'" size="small" type="success" plain @click="executeFormal('scm.supplier_payment_request.create', row.id)">创建付款申请</el-button>
          <template v-if="kind === 'request'">
            <el-button v-if="row.statusCode === 'draft'" size="small" type="primary" plain @click="executeFormal('scm.supplier_payment_request.submit', row.id)">提交申请</el-button>
            <el-button v-if="row.statusCode === 'submitted'" size="small" type="primary" plain @click="executeFormal('scm.supplier_payment_request.approve', row.id)">批准申请</el-button>
            <el-button v-if="row.statusCode === 'approved'" size="small" type="primary" plain @click="executeFormal('scm.supplier_payment_request.release', row.id)">转待付款处理</el-button>
            <el-button v-if="row.statusCode === 'payment_pending'" size="small" type="success" plain @click="executeFormal('scm.supplier_payment_status.record', row.id)">记录付款状态</el-button>
          </template>
        </template>
      </PceEnterpriseListTable>
    </section>

    <section class="card boundary" :data-acceptance-id="`${kind}-security-boundary`">
      <Heading title="业务边界保护" note="本版本只建设供应商结算确认与付款申请记录，不产生财务执行影响。" />
      <div class="grid">
        <Fact label="付款执行" value="否" />
        <Fact label="银行发送" value="否" />
        <Fact label="资金扣减" value="否" />
        <Fact label="银行流水" value="0" />
        <Fact label="总账处理" value="0" />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="企业业务详情" width="900px">
      <PceBusinessDetailCard
        v-if="dialogRow?.businessDetail"
        :detail="dialogRow.businessDetail"
      />
    </el-dialog>
    <el-dialog v-model="historyVisible" title="状态历史与操作记录" width="900px">
      <PceBusinessDetailCard
        v-if="historyRow?.businessDetail"
        :detail="historyRow.businessDetail"
      />
    </el-dialog>
    <el-dialog v-model="operationVisible" title="业务操作" width="760px">
      <p>当前状态：<strong>{{ operationRow?.statusLabel }}</strong></p>
      <div class="dialog-actions">
        <el-button
          v-for="action in operationRow?.availableActions || []"
          :key="action.actionCode"
          type="primary"
          plain
          @click="executeAction(operationRow, action)"
        >
          {{ actionLabel(action) }}
        </el-button>
        <el-empty v-if="!(operationRow?.availableActions || []).length" description="当前状态无可执行动作" />
      </div>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { supplierPayableV83Api } from '@/api/supplierPayableV83.js'
import { supplierSettlementFormalApi } from '@/api/supplierSettlementFormal.js'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { normalizeV83Facts, SUPPLIER_PAYABLE_V83_VERSION, v83PageDefinitions } from '@/meta/runtime/supplierPayableV83Runtime.js'
import { getPceBusinessAction } from '@/meta/runtime/pceBusinessActionRegistry.js'

const props = defineProps({ kind: { type: String, required: true } })
const definition = computed(() => v83PageDefinitions[props.kind])
const rows = ref([])
const facts = reactive({})
const diagnosticFacts = ref({})
const strictFacts = ref({})
const acceptanceFacts = ref({})
const dialogVisible = ref(false)
const dialogRow = ref(null)
const historyVisible = ref(false)
const historyRow = ref(null)
const operationVisible = ref(false)
const operationRow = ref(null)
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)

const enterpriseListContract = computed(() => createPceEnterpriseListContract({
  pageCode: definition.value.pageCode,
  pageType: 'list',
  title: definition.value.title,
  moduleCode: definition.value.moduleCode,
}))
const runtime = usePceEnterpriseListRuntime({
  rows,
  filterSchema: definition.value.filterSchema,
  pageCode: definition.value.pageCode,
  searchFields: [
    'payableConfirmationNo', 'paymentRequestNo', 'reconciliationNo',
    'supplierName', 'statusLabel',
  ],
  exportFileName: `${definition.value.pageCode}.csv`,
  exportColumns: [
    { field: definition.value.primaryField, label: definition.value.primaryLabel },
    { field: 'supplierName', label: '供应商' },
    { field: 'statusLabel', label: '业务状态' },
  ],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = runtime

const Heading = (_, { attrs }) => h('div', { class: 'heading' }, [h('h2', attrs.title), h('p', attrs.note)])
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [h('span', attrs.label), h('strong', String(attrs.value ?? '-'))])
function showRow(row) { dialogRow.value = row; dialogVisible.value = true }
function showHistory(row) { historyRow.value = row; historyVisible.value = true }
function showOperations(row) { operationRow.value = row; operationVisible.value = true }
const workflowCards = computed(() => rows.value.flatMap(row => (
  (row.availableActions || []).map(action => ({ row, action }))
)))
function actionLabel(action) {
  return getPceBusinessAction(action?.actionCode)?.actionName || action?.actionLabel || action?.actionCode
}
async function executeAction(row, action) {
  if (action.testActor) {
    const session = await supplierPayableV83Api.canaryActor(action.testActor)
    if (session?.success === false) {
      ElMessage.error(session?.error?.message || '测试角色身份建立失败')
      return
    }
  }
  const permission = await supplierPayableV83Api.inspectWorkflowAction({
    objectId: row.id,
    actionCode: action.actionCode,
  })
  if (permission?.success === false) {
    ElMessage.error(permission?.error?.message || '当前角色无权执行该动作')
    return
  }
  const result = await supplierPayableV83Api.executeWorkflowAction({
    objectId: row.id,
    actionCode: action.actionCode,
    reason: `页面执行：${actionLabel(action)}`,
  })
  if (result?.success === false) {
    ElMessage.error(result?.error?.message || '业务动作执行失败')
    return
  }
  ElMessage.success(`${actionLabel(action)}已完成，审计已记录`)
  operationVisible.value = false
  await refresh()
}
async function executeFormal(actionCode, sourceId) {
  try {
    const inspection = await supplierSettlementFormalApi.inspect({ actionCode, sourceId })
    if (!inspection?.success) throw new Error(inspection?.error?.message || inspection?.error?.code || '正式业务动作不可执行')
    const result = await supplierSettlementFormalApi.execute({
      actionCode,
      sourceId,
      reason: '系统流程验收数据 / PCE采购结算与绩效闭环14—22 V1.0',
    })
    if (!result?.success) throw new Error(result?.error?.message || result?.error?.code || '正式业务动作执行失败')
    ElMessage.success(`${result?.data?.actionLabel || '正式业务动作'}已完成`)
    await refresh()
  } catch (error) {
    ElMessage.error(error?.message || '正式业务动作执行失败')
  }
}
function diagnostics() {
  return {
    version: SUPPLIER_PAYABLE_V83_VERSION,
    canonicalName: definition.value.title,
    moduleCode: definition.value.moduleCode,
    pageFactOwner: definition.value.moduleCode,
    factSource: 'server',
    pageFacts: { ...facts },
    diagnosticFacts: diagnosticFacts.value,
    strictFacts: strictFacts.value,
    acceptanceFacts: acceptanceFacts.value,
    resultCount: facts.recordCount ?? null,
    detailViewMode: facts.detailViewMode,
    dangerActionCount: 0,
    businessProgressWriteCount: 0,
  }
}
function publish() { window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = diagnostics() }
async function refresh() {
  try {
    const loaded = normalizeV83Facts(await supplierPayableV83Api[definition.value.apiKey](), props.kind)
    rows.value = loaded.rows
    Object.assign(facts, loaded.facts)
    diagnosticFacts.value = loaded.diagnosticFacts
    strictFacts.value = loaded.strictFacts
    acceptanceFacts.value = loaded.acceptanceFacts
    publish()
  } catch (error) {
    ElMessage.error(`${definition.value.title}事实读取失败：${error?.message || 'UNKNOWN'}`)
  }
}
const provider = { factOwner: definition.value.moduleCode, refresh, buildDiagnostics: diagnostics }
onMounted(async () => {
  observability?.register?.(provider)
  await refresh()
  observability?.register?.(provider)
})
onBeforeUnmount(() => observability?.unregister?.(provider))
</script>

<style scoped>
.page { display:grid; min-width:0; gap:18px; padding:20px; background:#f4f7fb; }
.card { min-width:0; padding:20px; border:1px solid #dce4ed; border-radius:12px; background:#fff; }
.statistics { border-color:#bfdbfe; background:#f8fbff; }
.flow { border-color:#ddd6fe; background:#faf9ff; }
.warning { border-color:#f5c46b; background:#fff8e8; color:#8a4b08; }
.warning strong { font-size:18px; }.warning p { margin:8px 0 0; }
.boundary { border-color:#b8d8c4; background:#f5fbf7; }
.operations { border-color:#93c5fd; background:#f8fbff; }
.operation-facts { margin-bottom:14px; }
.operation-list { display:grid; gap:10px; }
.operation-item { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:12px 14px; border:1px solid #dbeafe; border-radius:10px; background:#fff; }
.operation-item div { display:flex; flex-wrap:wrap; gap:18px; color:#475569; }
.dialog-actions { display:flex; flex-wrap:wrap; gap:10px; }
.heading h2 { margin:0; color:#16243a; }.heading p { margin:6px 0 16px; color:#64748b; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; }
.fact { display:grid; gap:5px; padding:12px; border-radius:8px; background:#f5f8fb; }
.fact span { color:#64748b; font-size:13px; }
.flow-line { display:flex; flex-wrap:wrap; align-items:center; gap:10px; }
.flow-line span { padding:8px 12px; border-radius:999px; background:#ede9fe; color:#4c1d95; }
</style>
