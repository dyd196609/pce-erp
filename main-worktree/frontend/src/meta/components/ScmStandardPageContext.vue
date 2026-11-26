<template>
  <div class="scm-standard-page-context" data-acceptance-id="scm-standard-page-context">
    <section
      class="context-card diagnostic-card"
      data-acceptance-id="scm-server-facts"
      data-diagnostic-visibility="authorized-disclosure"
      :data-diagnostic-expanded="String(diagnosticExpanded)"
    >
      <div class="diagnostic-heading">
        <div>
          <h2>服务端持久事实</h2>
          <p>管理员 / 开发验收诊断，普通业务视图默认折叠。</p>
        </div>
        <button
          type="button"
          class="diagnostic-toggle"
          data-acceptance-id="scm-diagnostic-toggle"
          :aria-expanded="diagnosticExpanded"
          @click="diagnosticExpanded = !diagnosticExpanded"
        >{{ diagnosticExpanded ? '收起诊断信息' : '查看诊断信息' }}</button>
      </div>
      <div v-show="diagnosticExpanded" data-acceptance-id="scm-diagnostic-content">
      <div class="facts-grid">
        <span>事实来源：<strong>{{ facts.factSource }}</strong></span>
        <span>API：<strong>{{ facts.apiUrl || contract.apiEndpoint }}</strong></span>
        <span>记录数量：<strong>{{ facts.recordCount }}</strong></span>
        <span>状态：<strong>{{ facts.status }}</strong></span>
        <span>危险动作：<strong>{{ contract.dangerousActionCount }}</strong></span>
        <span>业务推进写入：<strong>{{ contract.businessProgressWriteCount }}</strong></span>
      </div>
      <p v-if="facts.error" role="alert">服务端事实读取失败：{{ facts.error }}</p>
      <div v-if="facts.objects.length" class="trace-table-wrap">
        <table>
          <thead><tr><th>业务编号</th><th>状态</th><th>数量</th><th>金额</th><th>来源对象</th><th>目标对象</th><th>受控动作</th></tr></thead>
          <tbody>
            <tr v-for="row in facts.objects" :key="`${row.objectType}-${row.objectId}`">
              <td>{{ row.objectNo }}</td>
              <td>{{ row.statusLabel }}</td>
              <td>{{ row.quantity }}</td>
              <td>{{ row.amount }}</td>
              <td>{{ row.sourceObject?.objectNo || '无上游对象' }}</td>
              <td>{{ row.targetObject?.objectNo || '尚未形成' }}</td>
              <td>
                <button
                  v-for="action in actionsFor(row)"
                  :key="action.code"
                  type="button"
                  class="runtime-action"
                  :disabled="actionRunning"
                  :data-scm-action="action.code"
                  @click="runAction(action, row)"
                >{{ action.label }}</button>
                <span v-if="!actionsFor(row).length">无可执行动作</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      </div>
    </section>

    <section class="context-card" data-acceptance-id="scm-business-trace">
      <h2>SCM Business Trace</h2>
      <div class="facts-grid">
        <span>来源对象：<strong>{{ contract.sourceObjectType }}</strong></span>
        <span>目标对象：<strong>{{ contract.targetObjectType }}</strong></span>
        <span>关系状态：<strong>{{ contract.traceStatus || '可追踪' }}</strong></span>
        <span v-if="contract.traceAuthority">Trace Authority：<strong>{{ contract.traceAuthority }}</strong></span>
        <span>当前节点：<strong>{{ contract.workflowNode }}</strong></span>
      </div>
    </section>

    <section class="context-card boundary" data-acceptance-id="scm-business-boundary-protection">
      <h2>业务边界保护</h2>
      <div class="facts-grid">
        <span>自动补数据：<strong>否</strong></span>
        <span>无用户动作自动修改状态：<strong>否</strong></span>
        <span>绕过审批生成订单：<strong>否</strong></span>
        <span>付款执行：<strong>否</strong></span>
        <span>银行发送：<strong>否</strong></span>
        <span>财务影响：<strong>0</strong></span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import { getScmStandardPageFacts, runScmRuntimeAction } from '@/api/scmStandardPageFacts.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { loadEnterpriseListCanaryFacts, resolveEnterpriseListCanaryQuery } from '@/meta/runtime/enterpriseListCanaryDataProvider.js'
import {
  beginScmPagePerformanceDiagnostic,
  finishScmPagePerformanceDiagnostic,
  markScmPagePerformance,
} from '@/meta/runtime/scmPagePerformanceDiagnostic.js'

const props = defineProps({ contract: { type: Object, required: true } })
const route = useRoute()
const canaryMode = computed(() => resolveEnterpriseListCanaryQuery(route.query).isCanaryMode)
const facts = reactive({ factSource: 'server', apiUrl: '', recordCount: '-', status: '加载中', error: '', objects: [], isCanaryMode: false })
const actionRunning = ref(false)
const diagnosticExpanded = ref(false)
const observabilityRegistry = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
let performanceToken = ''
let activeRequest = 0
const observabilityProvider = {
  factOwner: 'SCM',
  refresh: loadFacts,
  buildDiagnostics: () => ({
    moduleCode: 'SCM',
    pageFactOwner: 'SCM',
    pageFactOwnerGuard: 'instance-owned',
    pageCode: props.contract.pageCode,
    factSource: facts.factSource,
    resultCount: Number(facts.recordCount || 0),
    status: facts.status,
    strictServerFacts: {
      factSource: facts.factSource,
      resultCount: Number(facts.recordCount || 0),
      rows: facts.objects,
      sourceObjects: facts.objects.map(item => item.sourceObject).filter(Boolean),
    },
  }),
}

function actionsFor(row) {
  if (facts.isCanaryMode) return []
  const status = row.statusCode || row.status
  if (row.objectType === 'PriceApproval' && status === 'approved' && !row.targetObject) {
    return [{ code: 'create-purchase-order', label: '生成采购订单' }]
  }
  if (row.objectType === 'PurchaseOrder' && status === 'final_approved') {
    return [{ code: 'confirm-receipt', label: '确认收货', quantity: true }]
  }
  if (row.objectType === 'PurchaseReceipt' && status === 'received' && !row.targetObject) {
    return [{ code: 'create-inspection', label: '创建质量检验' }]
  }
  if (row.objectType === 'PurchaseInspection' && status === 'pending') {
    return [{ code: 'transition-inspection', label: '开始检验', data: { targetStatus: 'inspecting' } }]
  }
  if (row.objectType === 'PurchaseInspection' && status === 'inspecting') {
    return [
      { code: 'transition-inspection', label: '检验合格', qualifiedQuantity: true },
      { code: 'transition-inspection', label: '检验不合格', data: { targetStatus: 'rejected' } },
    ]
  }
  if (row.objectType === 'PurchaseInspection' && status === 'qualified') {
    return [{ code: 'confirm-inbound', label: '确认入库', quantity: true }]
  }
  return []
}

async function requestQuantity(title, initialValue) {
  const result = await ElMessageBox.prompt('请输入本次业务数量', title, {
    inputValue: String(initialValue || ''),
    inputPattern: /^(?:0|[1-9]\d*)(?:\.\d{1,4})?$/,
    inputErrorMessage: '请输入大于0且最多4位小数的数量',
    confirmButtonText: '确认',
    cancelButtonText: '取消',
  })
  if (Number(result.value) <= 0) throw new Error('数量必须大于0')
  return result.value
}

async function runAction(action, row) {
  actionRunning.value = true
  try {
    const data = { ...(action.data || {}) }
    if (action.quantity) data.quantity = await requestQuantity(action.label, row.quantity)
    if (action.qualifiedQuantity) {
      data.targetStatus = 'qualified'
      data.qualifiedQuantity = await requestQuantity(action.label, row.quantity)
    }
    const response = await runScmRuntimeAction(action.code, row.objectId, data)
    if (!response?.success) throw new Error(response?.error?.message || '动作执行失败')
    ElMessage.success(`${action.label}成功：${response.data?.objectNo || ''}`)
    await loadFacts()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(error?.message || '动作已取消')
  } finally {
    actionRunning.value = false
  }
}

async function loadFacts() {
  const requestId = ++activeRequest
  performanceToken = beginScmPagePerformanceDiagnostic(props.contract.route, props.contract.pageCode)
  const schemaStartedAt = globalThis.performance?.now?.() ?? Date.now()
  markScmPagePerformance(performanceToken, 'router', schemaStartedAt)
  markScmPagePerformance(performanceToken, 'schema', schemaStartedAt)
  const apiStartedAt = globalThis.performance?.now?.() ?? Date.now()
  facts.status = '加载中'
  facts.error = ''
  try {
    const response = canaryMode.value
      ? await loadEnterpriseListCanaryFacts(props.contract.pageCode, route.query)
      : await getScmStandardPageFacts(props.contract.pageCode)
    if (requestId !== activeRequest) return
    const data = canaryMode.value ? response : (response?.success ? response.data : response?.data || response)
    facts.factSource = data?.factSource || 'server'
    facts.apiUrl = data?.apiUrl || ''
    facts.recordCount = Number(data?.recordCount || 0)
    facts.objects = Array.isArray(data?.objects) ? data.objects : []
    facts.isCanaryMode = Boolean(data?.isCanaryMode)
    facts.status = data?.status === 'schema_not_deployed' ? '服务端结构未部署' : '加载成功'
  } catch (error) {
    if (requestId !== activeRequest) return
    facts.recordCount = 0
    facts.status = '加载失败'
    facts.error = error?.message || 'UNKNOWN'
  } finally {
    if (requestId === activeRequest) {
      markScmPagePerformance(performanceToken, 'api', apiStartedAt)
      await nextTick()
      markScmPagePerformance(performanceToken, 'render')
      finishScmPagePerformanceDiagnostic(performanceToken)
    }
  }
}

watch(() => [props.contract.pageCode, route.query.canaryBatchId, route.query.scenarioCode], loadFacts)
onMounted(() => {
  observabilityRegistry?.register(observabilityProvider)
  window.addEventListener('pce:scm-facts-changed', loadFacts)
  loadFacts()
})
onBeforeUnmount(() => {
  activeRequest += 1
  window.removeEventListener('pce:scm-facts-changed', loadFacts)
  observabilityRegistry?.unregister(observabilityProvider)
})
</script>

<style scoped>
.scm-standard-page-context { display:grid; gap:16px; }
.context-card { padding:18px; border:1px solid #dce4ed; border-radius:12px; background:#fff; }
.context-card h2 { margin:0 0 14px; color:#16243a; }
.diagnostic-heading { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.diagnostic-heading h2 { margin:0; }
.diagnostic-heading p { margin:4px 0 0; color:#64748b; font-size:13px; }
.diagnostic-toggle { padding:7px 12px; border:1px solid #94a3b8; border-radius:7px; background:#fff; color:#334155; cursor:pointer; white-space:nowrap; }
.facts-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:10px; }
.facts-grid span { padding:11px; border-radius:8px; background:#f5f8fb; color:#64748b; }
.facts-grid strong { color:#172033; }
.boundary { border-color:#b8d8c4; background:#f5fbf7; }
.trace-table-wrap { margin-top:14px; overflow:auto; }
table { width:100%; min-width:720px; border-collapse:collapse; }
th, td { padding:10px; border:1px solid #dce4ed; text-align:left; }
th { background:#f5f8fb; color:#334155; }
.runtime-action { margin:2px 6px 2px 0; padding:6px 9px; border:1px solid #2563eb; border-radius:6px; background:#eff6ff; color:#1d4ed8; cursor:pointer; }
.runtime-action:disabled { opacity:.5; cursor:not-allowed; }
</style>
