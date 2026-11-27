<template>
  <section class="followup-card" aria-label="生产跟单">
    <h2>生产跟单</h2>
    <el-button size="large" native-type="button" :disabled="loading" @click="load">刷新生产跟单</el-button>
    <form class="evidence-form" v-if="directory?.searchByOrderNo" @submit.prevent="findOrder">
      <label class="evidence-field evidence-field--number">按销售订单号查找 <input v-model.trim="search" required maxlength="80"></label>
      <el-button size="large" native-type="submit" type="primary" :disabled="loading">查找订单</el-button>
    </form>
    <p v-if="message" role="status">{{ message }}</p>
    <p v-if="directory && !directory.orders.length && !orderNo">当前没有本人负责的整单。</p>
    <ul v-if="directory?.orders.length">
      <li class="evidence-order-row" v-for="row in directory.orders" :key="row.orderNo">
        <el-button size="large" native-type="button" @click="openOrder(row.orderNo)">{{ row.orderNo }}</el-button>
        {{ row.approvalLabel }}
      </li>
    </ul>
    <article v-if="detail">
      <h3>{{ detail.orderNo }}</h3>
      <p>订单审批：{{ detail.approvalLabel }}。生产跟单负责人：{{ detail.assignment.owner || '尚未分派' }}。</p>
      <p v-if="detail.assignment.effectiveAt">生效时间：{{ timestamp(detail.assignment.effectiveAt) }}</p>
      <form class="evidence-form" aria-label="跟单分派与移交" v-if="detail.actions.length" @submit.prevent="assign">
        <label class="evidence-field evidence-field--choice">跟单负责人
          <select v-model="ownerId" required>
            <option value="" disabled>请选择跟单负责人</option>
            <option v-for="owner in directory?.candidates || []" :key="owner.id" :value="owner.id">{{ owner.name }}</option>
          </select>
        </label>
        <label class="evidence-field evidence-field--wide">办理原因
          <textarea v-model.trim="reason" required maxlength="300" rows="2"></textarea>
        </label>
        <el-button size="large" native-type="submit" type="primary" :disabled="busy">{{ detail.actions[0].label }}</el-button>
      </form>
      <details class="evidence-disclosure" v-if="detail.history?.length">
        <summary>查看分派与移交历史</summary>
        <ol>
          <li v-for="event in detail.history" :key="event.at">
            {{ timestamp(event.after.effectiveAt) }} · {{ event.before.owner || '未分派' }} → {{ event.after.owner }}
            · 办理人 {{ event.actor }} · {{ event.reason }}
          </li>
        </ol>
      </details>
      <el-button size="large" native-type="button" :disabled="busy" @click="showProgress">读取本单生产进度</el-button>
      <OrderProgressEvidence v-if="progress" :progress="progress.progress" :completion="progress.completion"
        :read-followup-task="readTask" />
    </article>
    <CustomerBinding />
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { evidenceRead, evidenceWrite, followupRoot, orderUrl } from '@/api/enterpriseEvidence'
import OrderProgressEvidence from './OrderProgressEvidence.vue'
import CustomerBinding from './CustomerBinding.vue'

const route = useRoute()
const router = useRouter()
const orderNo = computed(() => typeof route.query.followupOrder === 'string' ? route.query.followupOrder : '')
const directory = ref(null), detail = ref(null), progress = ref(null)
const search = ref(''), reason = ref(''), ownerId = ref('')
const message = ref(''), loading = ref(false), busy = ref(false)
let readSequence = 0

function timestamp(value) { return new Date(value).toLocaleString('zh-CN') }
function failed(result, fallback) { return result.meta?.status === 403 || result.meta?.status === 404 ? fallback : result.error?.message || fallback }

async function load() {
  const sequence = ++readSequence
  loading.value = true
  message.value = ''
  detail.value = null
  progress.value = null
  const data = await evidenceRead(followupRoot, orderNo.value ? { orderNo: orderNo.value } : {})
  if (sequence !== readSequence) return
  loading.value = false
  directory.value = data.success ? data.data : null
  if (!data.success) {
    message.value = failed(data, '当前岗位无权查看生产跟单目录。')
    return
  }
  if (!orderNo.value) return
  const result = await evidenceRead(orderUrl(followupRoot, orderNo.value))
  if (sequence !== readSequence) return
  if (!result.success) {
    message.value = failed(result, '当前没有可查看的该生产订单。')
    return
  }
  detail.value = result.data
  if (route.query.followupProgress === '1') await loadProgress(sequence)
}

async function openOrder(no) {
  if (orderNo.value === no) return load()
  await router.replace({ query: { ...route.query, followupOrder: no, followupProgress: undefined,
    officeOrderLine: undefined, officeProgressTask: undefined } })
}

function findOrder() { return openOrder(search.value) }

async function loadProgress(sequence) {
  busy.value = true
  const result = await evidenceRead(orderUrl(followupRoot, orderNo.value), { includeProgress: '1' })
  busy.value = false
  if (sequence !== readSequence) return
  if (!result.success) {
    message.value = failed(result, '当前无法读取正式生产进度。')
    return
  }
  progress.value = result.data
}

function readTask(taskId) {
  return evidenceRead(orderUrl(followupRoot, orderNo.value), { includeProgress: '1', progressTaskId: taskId })
}

async function showProgress() {
  if (route.query.followupProgress === '1') return loadProgress(readSequence)
  await router.replace({ query: { ...route.query, followupProgress: '1' } })
}

async function assign() {
  const sequence = readSequence
  busy.value = true
  const result = await evidenceWrite(orderUrl(followupRoot, orderNo.value), {
    ownerId: ownerId.value, expectedVersion: detail.value.assignment.version, reason: reason.value,
  })
  busy.value = false
  if (sequence !== readSequence) return
  if (!result.success) {
    message.value = failed(result, '当前不能办理跟单分派或移交。')
    return
  }
  reason.value = ''
  ownerId.value = ''
  await load()
}

watch([orderNo, () => route.query.followupProgress], load, { immediate: true })
</script>

<style scoped>
.followup-card { border: 1px solid #d6e0ee; border-radius: 12px; padding: 18px; background: #fff; }
</style>
