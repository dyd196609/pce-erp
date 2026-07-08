<template>
  <div>
    <h2>采购单详情页</h2>

    <div v-if="order">
      <p>单号：{{ order.po_no }}</p>
      <p>供应商：{{ order.supplier_name }}</p>
      <p>采购员：{{ order.buyer_name }}</p>
      <p>日期：{{ order.order_date }}</p>
      <p>状态：{{ order.document_status }}</p>
    </div>

    <el-table :data="items" border style="width: 100%">
      <el-table-column prop="material_name" label="物料" />
      <el-table-column prop="quantity" label="数量" />
      <el-table-column prop="price" label="单价" />
      <el-table-column prop="amount" label="金额" />
    </el-table>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

// ✅ ❗这里修复（关键！！！）
import request from '../api/request'

const route = useRoute()

const order = ref(null)
const items = ref([])

const loadDetail = async () => {
  try {
    const id = route.params.id

    const res = await request.get(`/api/purchase/orders/${id}/`)

    order.value = res
    items.value = res?.items || []
  } catch (err) {
    console.error('详情加载失败:', err)
  }
}

onMounted(() => {
  loadDetail()
})
</script>
