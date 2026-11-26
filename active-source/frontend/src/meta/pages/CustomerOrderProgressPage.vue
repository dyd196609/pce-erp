<template>
  <main class="customer-progress">
    <header>
      <h1>客户订单进度</h1>
      <button type="button" :disabled="loading" @click="load">刷新</button>
      <button type="button" @click="logout">退出登录</button>
    </header>
    <p v-if="loading" role="status">正在读取订单进度。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <div v-if="orderNo">
      <RouterLink :to="{ name: 'CustomerOrderProgress' }">返回订单列表</RouterLink>
      <article v-if="order">
        <h2>{{ order.orderNo }}</h2>
        <dl>
          <dt>承诺交期</dt><dd>{{ order.committedDeliveryDate || '尚未提供' }}</dd>
          <dt>正式发货状态</dt><dd>{{ order.shipmentStatus || '尚无可查的正式发货记录' }}</dd>
          <dt>正式签收状态</dt><dd>{{ order.receiptStatus || '尚无可查的正式签收记录' }}</dd>
        </dl>
        <h3>已发布的进度里程碑</h3>
        <ul v-if="order.milestones.length">
          <li v-for="item in order.milestones" :key="item.label + item.publishedAt">
            {{ item.label }} · {{ new Date(item.publishedAt).toLocaleString('zh-CN') }}
          </li>
        </ul>
        <p v-else>尚未发布进度里程碑。</p>
      </article>
    </div>
    <div v-else-if="orders">
      <p>本客户可见订单 {{ orders.length }} 张。</p>
      <ul>
        <li v-for="row in orders" :key="row.orderNo">
          <RouterLink :to="{ name: 'CustomerOrderProgress', query: { orderNo: row.orderNo } }">{{ row.orderNo }}</RouterLink>
          <span v-if="row.committedDeliveryDate"> · 承诺交期 {{ row.committedDeliveryDate }}</span>
        </li>
      </ul>
    </div>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/counter'
import { customerRoot, evidenceRead, orderUrl } from '@/api/enterpriseEvidence'
const route = useRoute(), router = useRouter(), userStore = useUserStore()
const orderNo = computed(() => typeof route.query.orderNo === 'string' ? route.query.orderNo : '')
const order = ref(null), orders = ref(null), error = ref(''), loading = ref(false)
let sequence = 0

async function load() {
  const active = ++sequence
  const no = orderNo.value
  loading.value = true
  order.value = null
  orders.value = null
  error.value = ''
  const result = await evidenceRead(no ? orderUrl(customerRoot, no) : customerRoot)
  if (active !== sequence) return
  loading.value = false
  if (!result.success) {
    error.value = result.meta?.status === 404 ? '当前账号没有可查询的该订单。'
      : result.meta?.status === 403 ? '当前账号未关联有效客户档案。' : '订单进度暂时无法读取。'
    return
  }
  order.value = result.data.order ?? null
  orders.value = result.data.orders ?? null
}

async function logout() {
  await userStore.logout()
  await router.replace('/system-login')
}

watch(orderNo, load, { immediate: true })
</script>

<style scoped>
.customer-progress { width: min(840px, 94vw); margin: 32px auto; font: inherit; }
header { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid #d8e2ef; }
header h1 { margin-right: auto; }
article { margin-top: 16px; }
dt { font-weight: 600; }
dd { margin: 3px 0 12px; }
button { min-height: 40px; }
</style>
