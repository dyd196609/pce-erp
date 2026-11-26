<template>
  <main class="formal-execution-page">
    <header>
      <div>
        <h1 data-acceptance-id="page-business-title">{{ isQuality ? '来料检验' : '库存余额' }}</h1>
        <p>唯一来源：{{ facts.authoritySource || '正在读取正式服务端事实' }}</p>
      </div>
      <el-button :loading="loading" @click="loadFacts">刷新</el-button>
    </header>

    <el-alert
      v-if="error"
      type="error"
      :closable="false"
      :title="error"
      show-icon
    />
    <el-alert
      v-else
      type="success"
      :closable="false"
      title="当前正式路由只读取 Django Service/API；Demo fixture 与浏览器本地状态不参与正式事实。"
      show-icon
    />

    <section class="summary-grid">
      <article v-for="(value, key) in facts.summary || {}" :key="key">
        <span>{{ labels[key] || key }}</span><strong>{{ value }}</strong>
      </article>
    </section>

    <template v-if="isQuality">
      <h2>来料检验</h2>
      <el-table :data="facts.inspections || []" stripe>
        <el-table-column prop="inspectionNo" label="检验单号" min-width="160" />
        <el-table-column prop="purchaseOrderNo" label="采购订单" min-width="160" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column prop="qualifiedQuantity" label="合格数量" width="120" />
        <el-table-column prop="rejectedQuantity" label="不合格数量" width="120" />
      </el-table>
      <h2>正式入库回读</h2>
      <el-table :data="facts.inbounds || []" stripe>
        <el-table-column prop="inboundNo" label="入库单号" min-width="160" />
        <el-table-column prop="inspectionNo" label="来源检验" min-width="160" />
        <el-table-column prop="warehouseCode" label="仓库" width="130" />
        <el-table-column prop="locationCode" label="库位" width="130" />
        <el-table-column prop="quantity" label="数量" width="120" />
      </el-table>
    </template>

    <template v-else>
      <h2>库存余额</h2>
      <el-table :data="facts.balances || []" stripe>
        <el-table-column prop="warehouseCode" label="仓库" width="130" />
        <el-table-column prop="locationCode" label="库位" width="130" />
        <el-table-column prop="materialCode" label="物料编码" min-width="150" />
        <el-table-column prop="materialName" label="物料名称" min-width="180" />
        <el-table-column prop="lotNo" label="批号" width="150" />
        <el-table-column prop="quantity" label="数量" width="120" />
      </el-table>
      <h2>库存流水</h2>
      <el-table :data="facts.transactions || []" stripe>
        <el-table-column prop="transactionNo" label="流水号" min-width="160" />
        <el-table-column prop="sourceInboundNo" label="来源入库" min-width="160" />
        <el-table-column prop="materialCode" label="物料" width="150" />
        <el-table-column prop="locationCode" label="库位" width="120" />
        <el-table-column prop="lotNo" label="批号" width="140" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="afterQuantity" label="变动后" width="100" />
      </el-table>
      <section class="formal-trace-empty" data-acceptance-id="inventory-formal-trace-empty">
        <strong>业务追踪</strong>
        <span>暂无正式业务追踪关系</span>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { formalExecutionApi } from '@/api/formalExecution'

const route = useRoute()
const loading = ref(false)
const facts = ref({})
const error = ref('')
const isQuality = computed(() => route.path.startsWith('/qms'))
const labels = {
  warehouseCount: '仓库数', locationCount: '库位数', lotCount: '批号数',
  balanceCount: '余额行数', transactionCount: '流水数', totalQuantity: '库存总量',
  inspectionCount: '检验单数', inboundCount: '入库单数',
}

async function loadFacts() {
  loading.value = true
  error.value = ''
  const response = isQuality.value
    ? await formalExecutionApi.qualityFacts()
    : await formalExecutionApi.inventoryFacts()
  if (!response.success) {
    error.value = response.error?.message || '正式服务端事实读取失败'
    facts.value = {}
  } else {
    facts.value = response.data || {}
  }
  loading.value = false
}

onMounted(loadFacts)
watch(() => route.path, loadFacts)
</script>

<style scoped>
.formal-execution-page { padding: 24px; display: grid; gap: 18px; }
header { display: flex; justify-content: space-between; align-items: center; }
h1, h2, p { margin: 0; }
p { margin-top: 6px; color: #64748b; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
.summary-grid article { padding: 16px; border: 1px solid #dbeafe; border-radius: 10px; background: #f8fbff; }
.summary-grid span, .summary-grid strong { display: block; }
.summary-grid strong { margin-top: 8px; font-size: 24px; }
.formal-trace-empty { display: flex; gap: 12px; align-items: center; padding: 14px 16px; border: 1px dashed #94a3b8; border-radius: 8px; color: #475569; }
</style>
