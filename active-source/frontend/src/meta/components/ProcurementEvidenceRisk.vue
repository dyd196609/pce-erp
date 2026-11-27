<template>
  <section class="risk-panel" aria-label="采购核对与风险闭环">
    <h2>按原采购单核对与回查风险</h2>
    <form class="evidence-form" @submit.prevent="search">
      <label class="evidence-field evidence-field--number">采购订单号 <input v-model.trim="searchNo" required maxlength="80"></label>
      <el-button size="large" native-type="submit" type="primary" :disabled="loading">查找</el-button>
    </form>
    <p v-if="loading" role="status">正在读取正式核对依据。</p>
    <p v-if="message" role="status">{{ message }}</p>
    <article v-if="data">
      <h3>{{ data.orderNo }}</h3>
      <div v-if="data.checks">
        <h4>收货与入库：{{ data.checks.quantity.statusLabel }}</h4>
        <p v-for="row in data.checks.quantity.rows" :key="row.purchaseLineId">
          采购行 {{ row.purchaseLineId }} · 收货 {{ row.received }} {{ row.unit }}，入库 {{ row.inbound }} {{ row.unit }}
        </p>
        <p v-if="data.checks.quantity.receiptNos?.length">收货单 {{ data.checks.quantity.receiptNos.join('、') }} · 入库单 {{ data.checks.quantity.inboundNos.join('、') }}</p>
        <p v-if="data.checks.quantity.reason">{{ data.checks.quantity.reason }}</p>
        <p>逐行质检放行：{{ data.checks.quality.statusLabel }}。{{ data.checks.quality.reason }}</p>
        <p v-if="data.checks.quality.inspectionNos?.length">检验单 {{ data.checks.quality.inspectionNos.join('、') }}</p>
        <p>应付金额：{{ data.checks.payable.statusLabel }}。{{ data.checks.payable.reason }}</p>
        <p v-for="row in data.checks.payable.documents || []" :key="row.payableNo">
          {{ row.payableNo }} · {{ row.amount }} {{ row.currency }}
        </p>
      </div>
      <h4>正式差异及处置</h4>
      <p v-if="!data.differences.length">当前范围没有可办理或回查的正式差异记录。</p>
      <div v-for="item in data.differences" :key="item.id" class="risk-row">
        <p>{{ item.sourceNo }} · 责任岗位 {{ item.department }} · 比对值 {{ item.expected }}／{{ item.actual }}</p>
        <p v-if="item.risk">{{ item.risk.statusLabel }} · 处理人 {{ item.risk.handler }}</p>
        <details class="evidence-disclosure" v-if="item.risk">
          <summary>查看受理、处理及复核历史</summary>
          <ol>
            <li v-for="row in item.risk.history" :key="row.at">
              {{ new Date(row.at).toLocaleString('zh-CN') }} · {{ row.actor }} · {{ row.after.status || '已受理' }} · {{ row.reason }}
              <span v-if="row.after.evidence"> · {{ row.after.evidence }}</span>
            </li>
          </ol>
        </details>
        <div v-if="actions(item).length" class="evidence-toolbar">
          <el-button size="large" v-for="act in actions(item)" :key="act.code" native-type="button" @click="select(item, act)">{{ act.label }}</el-button>
        </div>
        <form class="evidence-form evidence-subform" aria-label="采购风险办理" v-if="selected?.item.id === item.id" @submit.prevent="submit">
          <label class="evidence-field evidence-field--choice" v-if="selected.action.type === 'receive'">指定处理人
            <select v-model="handlerId" required>
              <option value="" disabled>请选择</option>
              <option v-for="handler in item.handlers" :key="handler.id" :value="handler.id">{{ handler.name }}</option>
            </select>
          </label>
          <label class="evidence-field evidence-field--wide">办理说明
          <textarea v-model.trim="reason" required maxlength="300" rows="2"></textarea>
        </label>
          <label class="evidence-field evidence-field--full" v-if="selected.action.type !== 'receive'">原单据及处置／复核证据
            <textarea v-model.trim="evidence" required maxlength="1800" rows="3"></textarea>
          </label>
          <div class="evidence-toolbar evidence-form-actions">
            <el-button size="large" native-type="submit" type="primary" :disabled="saving">提交</el-button>
            <el-button size="large" native-type="button" :disabled="saving" @click="selected = null">取消</el-button>
          </div>
        </form>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { evidenceRead, evidenceWrite, orderUrl, riskRoot } from '@/api/enterpriseEvidence'

const route = useRoute(), router = useRouter()
const no = computed(() => typeof route.query.riskOrder === 'string' ? route.query.riskOrder : '')
const searchNo = ref(''), data = ref(null), message = ref('')
const loading = ref(false), saving = ref(false), selected = ref(null)
const handlerId = ref(''), reason = ref(''), evidence = ref('')
let sequence = 0

async function load() {
  const active = ++sequence
  selected.value = null
  data.value = null
  message.value = ''
  if (!no.value) return
  searchNo.value = no.value
  loading.value = true
  const response = await evidenceRead(orderUrl(riskRoot, no.value))
  if (active !== sequence) return
  loading.value = false
  if (!response.success) {
    message.value = response.meta?.status === 403 ? '当前岗位没有采购核对或风险权限。'
      : response.meta?.status === 404 ? '当前范围没有可核对的这张采购单。'
        : response.error?.message || '正式依据读取失败，结果待核。'
    return
  }
  data.value = response.data
}

async function search() {
  if (no.value === searchNo.value) return load()
  await router.replace({ query: { ...route.query, riskOrder: searchNo.value } })
}

function actions(item) { return item.action ? [item.action] : item.risk?.actions || [] }

function select(item, action) {
  selected.value = { item, action }
  handlerId.value = ''
  reason.value = ''
  evidence.value = ''
}

async function submit() {
  const active = sequence
  const { item, action } = selected.value
  const base = orderUrl(riskRoot, no.value)
  const receiving = action.type === 'receive'
  saving.value = true
  const result = await evidenceWrite(receiving ? base : base + item.risk.id + '/' + action.type + '/',
    receiving ? { differenceId: item.id, handlerId: handlerId.value, reason: reason.value }
      : { expectedVersion: item.risk.version, reason: reason.value, evidence: evidence.value })
  saving.value = false
  if (active !== sequence) return
  if (result.success) await load()
  else message.value = result.error?.message || '风险办理未完成。'
}

watch(no, load, { immediate: true })
</script>

<style scoped>
.risk-panel { border: 1px solid #d6e0ee; border-radius: 12px; padding: 18px; background: #fff; }
.risk-row { padding: 12px; border-top: 1px solid #d6e0ee; }
</style>
