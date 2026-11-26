<template>
  <main class="trace-page">
    <header><div><h1>正式 P2P / 库存质量链追踪</h1><p>服务端外键事实；不读取浏览器演示状态。</p></div><el-button @click="load">刷新</el-button></header>
    <el-alert v-if="error" type="error" :title="error" :closable="false" />
    <section>
      <h2>PO → Receipt → Inspection</h2>
      <el-table :data="quality.inspections || []" stripe>
        <el-table-column prop="purchaseOrderNo" label="PO" min-width="160" />
        <el-table-column prop="receiptNo" label="Receipt" min-width="160" />
        <el-table-column prop="inspectionNo" label="Inspection" min-width="160" />
        <el-table-column prop="status" label="状态" width="120" />
      </el-table>
    </section>
    <section>
      <h2>Inspection → Inbound → InventoryTransaction</h2>
      <el-table :data="inventory.transactions || []" stripe>
        <el-table-column prop="sourceInboundNo" label="Inbound" min-width="160" />
        <el-table-column prop="transactionNo" label="InventoryTransaction" min-width="180" />
        <el-table-column prop="warehouseCode" label="仓库" width="120" />
        <el-table-column prop="locationCode" label="库位" width="120" />
        <el-table-column prop="lotNo" label="批号" width="140" />
        <el-table-column prop="quantity" label="数量" width="100" />
      </el-table>
    </section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { formalExecutionApi } from '@/api/formalExecution'

const inventory = ref({})
const quality = ref({})
const error = ref('')
async function load() {
  error.value = ''
  const [inventoryResponse, qualityResponse] = await Promise.all([
    formalExecutionApi.inventoryFacts(), formalExecutionApi.qualityFacts(),
  ])
  if (!inventoryResponse.success || !qualityResponse.success) {
    error.value = inventoryResponse.error?.message || qualityResponse.error?.message || '正式链路读取失败'
    return
  }
  inventory.value = inventoryResponse.data || {}
  quality.value = qualityResponse.data || {}
}
onMounted(load)
</script>

<style scoped>
.trace-page { padding: 24px; display: grid; gap: 18px; }
header { display: flex; justify-content: space-between; align-items: center; }
header p { color: #64748b; }
section { border: 1px solid #e2e8f0; border-radius: 12px; padding: 18px; background: #fff; }
</style>
