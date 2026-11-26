<template>
  <main class="trace-page">
    <header><div><h1>正式 P2P / 库存质量链追踪</h1><p>服务端外键事实；不读取浏览器演示状态。</p></div><el-button :loading="loading" @click="load">刷新</el-button></header>
    <section v-if="isBusinessTrace">
      <h2>销售订单与生产进度</h2>
      <p>从授权订单读取原记录，查看计划、工单、工序和完成条件。</p>
      <RouterLink :to="{ path: '/home', query: { role: 'management' } }">查看授权订单及生产进度</RouterLink>
    </section>
    <ProductionFollowup v-if="isBusinessTrace" />
    <section v-if="isValidationCenter">
      <h2>采购事实核对</h2>
      <p>下方可核对采购订单、收货、检验与库存流水；应付依据从原页面查看。</p>
      <nav aria-label="采购核对原页面">
        <RouterLink to="/wms/purchase-receives">查看收货单</RouterLink>
        <RouterLink to="/finance/payable-checks">查看应付核对</RouterLink>
      </nav>
      <p>销售生产完成条件从业务链追踪的订单依据读取。</p>
    </section>
    <ProcurementEvidenceRisk v-if="isValidationCenter" />
    <section v-loading="loading">
      <h2>采购订单、收货与检验</h2>
      <el-alert v-if="qualityError" type="warning" :title="qualityError" :closable="false" />
      <el-table v-else :data="quality.inspections || []" stripe>
        <el-table-column prop="purchaseOrderNo" label="采购订单编号" min-width="160" />
        <el-table-column prop="receiptNo" label="采购收货单编号" min-width="160" />
        <el-table-column prop="inspectionNo" label="检验单编号" min-width="160" />
        <el-table-column prop="statusLabel" label="检验单状态" width="120" />
      </el-table>
    </section>
    <section v-loading="loading">
      <h2>检验、入库与库存流水</h2>
      <el-alert v-if="inventoryError" type="warning" :title="inventoryError" :closable="false" />
      <el-table v-else :data="inventory.transactions || []" stripe>
        <el-table-column prop="sourceInboundNo" label="来源入库单编号" min-width="160" />
        <el-table-column prop="transactionNo" label="库存流水编号" min-width="180" />
        <el-table-column prop="warehouseCode" label="仓库" width="120" />
        <el-table-column prop="locationCode" label="库位" width="120" />
        <el-table-column prop="lotNo" label="批号" width="140" />
        <el-table-column prop="quantity" label="数量" width="100" />
      </el-table>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { formalExecutionApi } from '@/api/formalExecution'
import ProductionFollowup from '@/meta/components/ProductionFollowup.vue'
import ProcurementEvidenceRisk from '@/meta/components/ProcurementEvidenceRisk.vue' 

const route = useRoute()
const isBusinessTrace = computed(() => route.path === '/business-trace')
const isValidationCenter = computed(() => route.path === '/finance/p2p-validation-center')
const inventory = ref({})
const quality = ref({})
const inventoryError = ref('')
const qualityError = ref('')
const loading = ref(false)

async function loadFacts(read, facts, error, fallback) {
  facts.value = {}
  error.value = ''
  try {
    const response = await read()
    if (response.success) {
      facts.value = response.data || {}
    } else {
      error.value = response.error?.message || fallback
    }
  } catch {
    error.value = fallback
  }
}

async function load() {
  loading.value = true
  await Promise.all([
    loadFacts(formalExecutionApi.inventoryFacts, inventory, inventoryError, '库存流水读取失败'),
    loadFacts(formalExecutionApi.qualityFacts, quality, qualityError, '检验记录读取失败'),
  ])
  loading.value = false
}
onMounted(load)
</script>

<style scoped>
.trace-page { padding: 24px; display: grid; gap: 18px; }
header { display: flex; justify-content: space-between; align-items: center; }
header p { color: #64748b; }
nav { display: flex; gap: 16px; flex-wrap: wrap; }
section { border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; background: #fff; }
</style>
