<template>
  <section class="custody-directory" aria-label="来料异常保管目录">
    <h3>来料异常保管目录</h3>
    <button type="button" :aria-expanded="open" @click="toggleDirectory">
      {{ open ? '收起保管目录' : '查看待保管异常' }}
    </button>
    <template v-if="open">
      <form class="custody-search" @submit.prevent="applySearch">
        <label>采购单号、收货单号、检验单号或物料
          <input v-model.trim="input" maxlength="100" />
        </label>
        <label><span id="incoming-custody-category-label">核对状态</span>
          <select v-model="categoryInput" aria-labelledby="incoming-custody-category-label">
            <option v-for="[value, label] in categories" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <button type="submit">查询保管目录</button>
      </form>
      <p v-if="loading" role="status">正在读取仓管授权的保管目录。</p>
      <p v-else-if="error" role="alert">{{ error }}</p>
      <template v-else-if="directory">
        <p v-if="directory.count===0" role="status">本次查询无匹配的异常登记。</p>
        <template v-else>
          <p role="status">匹配 {{ directory.count }} 笔异常登记</p>
          <ul class="custody-results">
            <li v-for="row in directory.results" :key="row.registrationId">
              <strong>{{ row.inspectionNo }} · {{ row.materialName }} · {{ row.unit }}</strong>
              <p>采购订单 {{ row.purchaseOrderNo }} · 收货单 {{ row.receiptNo }}</p>
              <p>采购来源 {{ requestLine(row) }} · 采购订单行号 {{ shown(row.purchaseOrderLineNo) }}</p>
              <p>异常登记 {{ shown(row.registrationOccurredAt) }}</p>
              <PceBusinessStatus :status-label="row.statusLabel" />
              <p v-if="row.currentSourceStatus==='SOURCE_UNKNOWN'">
                {{ row.blockingReason?.message || '当前保管来源待核。' }} 以下为原登记及历史核对。
              </p>
              <dl class="custody-quantities">
                <div><dt>登记不合格量</dt><dd>{{ quantity(row.custodySummary.registeredRejectedQuantity, row.unit) }}</dd></div>
                <div><dt>{{ row.custodySummary.historicalObservationOnly ? '历史实点确认量' : '最近核对确认保管量' }}</dt><dd>{{ quantity(row.custodySummary.confirmedCustodyQuantity, row.unit) }}</dd></div>
                <div><dt>尚待完整确认的登记范围</dt><dd>{{ quantity(row.custodySummary.pendingConfirmationQuantity, row.unit) }}</dd></div>
                <div><dt>最近核对差异量</dt><dd>{{ quantity(row.custodySummary.differenceQuantity, row.unit) }}</dd></div>
                <template v-if="row.custodySummary.historicalObservationOnly">
                  <div><dt>原仓管当前剩余责任范围</dt><dd>{{ quantity(row.currentSourceStatus==='PROVIDED' ? row.custodySummary.currentWarehouseResponsibilityQuantity : null, row.unit) }}</dd></div>
                  <div><dt>当前仓管核实量</dt><dd>{{ quantity(row.currentSourceStatus==='PROVIDED' ? row.custodySummary.currentWarehouseVerifiedQuantity : null, row.unit) }}</dd></div>
                </template>
              </dl>
              <button type="button" :aria-current="isCurrent(row) ? 'true' : undefined"
                @click="openDetail(row)">查看保管明细</button>
            </li>
          </ul>
          <el-pagination
            v-if="directory.count>Math.min(...sizes)"
            :current-page="page"
            :page-size="pageSize"
            :page-sizes="sizes"
            :total="directory.count"
            :pager-count="3"
            layout="prev, pager, next, sizes"
            @current-change="changePage"
            @size-change="changeSize"
          />
        </template>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/api/request.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import { getTabAuthEpoch } from '@/meta/runtime/tabAuthenticationContext.js'

const emit = defineEmits(['open-detail'])
const route = useRoute(), router = useRouter(), epoch = getTabAuthEpoch()
const endpoint = '/api/procurement/incoming-exceptions/custody-directory/'
const categories = [
  ['all', '全部待办'],
  ['waiting', '待仓管确认'],
  ['difference', '有差异待核'],
  ['confirmed', '已完整确认'],
  ['registered', '全部登记（含历史）'],
]
const sizes = [10, 20, 50, 100]
const open = computed(() => route.query.a10CustodyDirectory === '1')
const query = computed(() => typeof route.query.a10CustodySearch === 'string' ? route.query.a10CustodySearch : '')
const category = computed(() => categories.some(([value]) => value === route.query.a10CustodyCategory) ? route.query.a10CustodyCategory : 'all')
const positive = value => Number.isSafeInteger(value) && value > 0
const page = computed(() => positive(Number(route.query.a10CustodyPage)) ? Number(route.query.a10CustodyPage) : 1)
const pageSize = computed(() => sizes.includes(Number(route.query.a10CustodySize)) ? Number(route.query.a10CustodySize) : 20)
const input = ref(''), categoryInput = ref('all'), directory = ref(null), loading = ref(false), error = ref('')
let readCycle = 0

function shown(value) {
  return value == null || value === '' ? '未提供' : String(value)
}
function quantity(value, unit) {
  return value == null || value === '' ? '未提供' : `${value} ${shown(unit)}`
}
function requestLine(row) {
  return row.sourcePurchaseRequestNo && row.sourcePurchaseRequestLineNo != null
    ? `${row.sourcePurchaseRequestNo} · 申请第 ${row.sourcePurchaseRequestLineNo} 行`
    : '未提供'
}
function validRow(row) {
  return positive(row?.inspectionId) && positive(row?.registrationId)
    && row.detailUrl === `/api/procurement/incoming-exceptions/${row.inspectionId}/custody/?registrationId=${row.registrationId}`
    && row.requiresExactContextReload === true && row.directoryGrantsExecution === false
    && Boolean(row.custodySummary) && typeof row.statusLabel === 'string'
}
function isCurrent(row) {
  return route.query.a10Inspection === String(row.inspectionId) && route.query.a10Registration === String(row.registrationId)
}
function openDetail(row) {
  if (directory.value?.results.includes(row) && validRow(row)) {
    emit('open-detail', row)
  }
}
function changeQuery(patch) {
  return router.push({ query: { ...route.query, ...patch } })
}
function toggleDirectory() {
  return changeQuery({ a10CustodyDirectory: open.value ? undefined : '1' })
}
async function applySearch() {
  const same = page.value === 1 && query.value === input.value && category.value === categoryInput.value
  if (same) return load()
  return changeQuery({
    a10CustodySearch: input.value || undefined,
    a10CustodyCategory: categoryInput.value === 'all' ? undefined : categoryInput.value,
    a10CustodyPage: undefined,
  })
}
function changePage(value) {
  return changeQuery({ a10CustodyPage: value > 1 ? String(value) : undefined })
}
function changeSize(value) {
  return changeQuery({ a10CustodySize: String(value), a10CustodyPage: undefined })
}
function fail(response) {
  const status = response?.meta?.status
  const label = status === 401 ? '请登录后读取保管目录'
    : status === 403 ? '无权读取保管目录' : '保管目录读取失败'
  error.value = response?.error?.message ? `${label}：${response.error.message}` : label
}
async function load() {
  const ticket = ++readCycle
  directory.value = null
  loading.value = false
  error.value = ''
  if (!open.value || getTabAuthEpoch() !== epoch) return
  const params = { q: query.value, category: category.value, page: page.value, pageSize: pageSize.value }
  input.value = params.q
  categoryInput.value = params.category
  loading.value = true
  const response = await request({ url: endpoint, params, meta: { module: 'WMS', readOnly: true, factLoad: true } }).catch(() => null)
  if (ticket !== readCycle || getTabAuthEpoch() !== epoch) return
  loading.value = false
  const data = response?.data
  if (!response?.success || data?.currentStateSource !== 'server' || data.scope !== 'ORIGINAL_CUSTODY_AUTHORIZATION'
    || data.page !== params.page || data.pageSize !== params.pageSize
    || !Number.isSafeInteger(data.count) || data.count < 0 || !Array.isArray(data.results)
    || data.factLoadStatus !== (data.count === 0 ? 'empty_valid' : 'loaded')
    || data.results.some(row => !validRow(row))) {
    fail(response)
    return
  }
  if (params.page > 1 && !data.results.length) {
    return router.replace({ query: { ...route.query, a10CustodyPage: undefined } })
  }
  directory.value = data
}
watch([open, query, category, page, pageSize], load, { immediate: true })
onBeforeUnmount(() => { readCycle++ })
</script>

<style scoped>
.custody-directory { border: 1px solid #d6e0ee; border-radius: 9px; margin-top: 12px; min-width: 0; padding: 12px; overflow-wrap: anywhere; }
.custody-search { display: grid; grid-template-columns: minmax(180px, 2fr) minmax(130px, 1fr) auto; gap: 8px; align-items: end; margin-top: 12px; }
.custody-search label { display: grid; gap: 4px; min-width: 0; }
.custody-directory :is(button, input, select) { min-height: 44px; max-width: 100%; padding: 6px 8px; box-sizing: border-box; }
.custody-results { padding: 0; list-style: none; margin: 12px 0; }
.custody-results li { border-block-start: 1px solid #d6e0ee; padding: 10px 0; }
.custody-results p { margin: 4px 0; }
.custody-quantities { display: grid; grid-template-columns: repeat(4,minmax(0,1fr)); gap: 8px; }
.custody-quantities dd { font-weight: 600; margin: 0; }
.custody-directory :deep(.el-pagination) { flex-wrap: wrap; }
@media (max-width: 600px) {
  .custody-search { grid-template-columns: minmax(0,1fr); }
  .custody-quantities { grid-template-columns: repeat(2,minmax(0,1fr)); }
}
</style>
