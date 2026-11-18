<template>
  <main class="inquiry-create" data-page-code="purchase-inquiry-create" data-runtime-version="V1.14.2.8.6.0">
    <header class="page-heading"><div><h1>创建询价</h1><p>仅创建当前会话内存态询价对象，不写入数据库，也不触发下游业务。</p></div><el-button @click="router.push('/scm/purchase-inquiry')">返回工作台</el-button></header>
    <el-form ref="formRef" :model="form" label-position="top">
      <section class="panel" data-acceptance-id="basic-information">
        <h2>基本信息</h2>
        <div class="form-grid">
          <el-form-item label="询价主题" required><el-input v-model="form.inquiryTitle" placeholder="请输入询价主题" /></el-form-item>
          <el-form-item label="询价日期" required><el-date-picker v-model="form.inquiryDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="采购员" required><el-input v-model="form.buyerName" placeholder="请输入采购员" /></el-form-item>
          <el-form-item label="币种"><el-select v-model="form.currency"><el-option label="人民币" value="CNY" /><el-option label="美元" value="USD" /></el-select></el-form-item>
        </div>
      </section>

      <section class="panel" data-acceptance-id="supplier-selection">
        <h2>供应商选择</h2>
        <el-select v-model="form.suppliers" multiple filterable placeholder="请选择候选供应商" class="wide-select">
          <el-option v-for="supplier in supplierOptions" :key="supplier.value" :label="supplier.label" :value="supplier.value" />
        </el-select>
        <p class="hint">本页不调用 Supplier API，候选项来自页面初始化设计清单。</p>
      </section>

      <section class="panel" data-acceptance-id="inquiry-lines">
        <div class="section-heading"><h2>询价明细</h2><el-button @click="addLine">新增明细</el-button></div>
        <el-table :data="form.lines" border>
          <el-table-column type="index" label="序号" width="70" />
          <el-table-column label="物料编码" min-width="160"><template #default="{ row }"><el-input v-model="row.materialCode" /></template></el-table-column>
          <el-table-column label="物料名称" min-width="180"><template #default="{ row }"><el-input v-model="row.materialName" /></template></el-table-column>
          <el-table-column label="数量" width="140"><template #default="{ row }"><el-input-number v-model="row.quantity" :min="0.01" /></template></el-table-column>
          <el-table-column label="单位" width="120"><template #default="{ row }"><el-input v-model="row.unit" /></template></el-table-column>
          <el-table-column label="需求日期" width="180"><template #default="{ row }"><el-date-picker v-model="row.requiredDate" type="date" value-format="YYYY-MM-DD" /></template></el-table-column>
          <el-table-column label="操作" width="90" fixed="right"><template #default="{ $index }"><el-button link type="danger" @click="removeLine($index)">删除</el-button></template></el-table-column>
        </el-table>
      </section>
    </el-form>

    <footer class="action-bar"><span>禁止：采购订单、发送供应商、付款、库存动作</span><el-button type="primary" @click="createDraft">创建询价对象</el-button></footer>
    <el-alert v-if="createdObject" title="询价对象已在当前会话创建" type="success" :closable="false" show-icon>
      <template #default>{{ createdObject.inquiryNo }} · {{ createdObject.statusLabel }} · 未写入数据库</template>
    </el-alert>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import { createPurchaseInquiryRuntimeObject } from '@/meta/runtime/purchaseInquiryRuntime.js'

const router = useRouter()
const formRef = ref(null)
const createdObject = ref(null)
const supplierOptions = Object.freeze([
  { label: '候选供应商 A', value: 'SUPPLIER-A' }, { label: '候选供应商 B', value: 'SUPPLIER-B' }, { label: '候选供应商 C', value: 'SUPPLIER-C' },
])
const emptyLine = () => ({ materialCode: '', materialName: '', quantity: 1, unit: '件', requiredDate: '' })
const form = reactive({ inquiryTitle: '', inquiryDate: '', buyerName: '', currency: 'CNY', suppliers: [], lines: [emptyLine()] })
function addLine() { form.lines.push(emptyLine()) }
function removeLine(index) { if (form.lines.length > 1) form.lines.splice(index, 1) }
function createDraft() {
  try {
    if (form.lines.some((line) => !line.materialCode || !line.materialName || !line.requiredDate)) throw new Error('请完整填写询价明细')
    createdObject.value = createPurchaseInquiryRuntimeObject({ ...form, suppliers: [...form.suppliers], lines: form.lines.map((line) => ({ ...line })) })
    ElMessage.success('询价对象已创建（仅当前会话）')
  } catch (error) { ElMessage.warning(error?.message || '询价对象创建失败') }
}
</script>

<style scoped>
.inquiry-create{display:grid;gap:16px;max-width:1440px;margin:0 auto}.page-heading,.section-heading,.action-bar{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1,.panel h2{margin:0}.page-heading p,.hint{color:#64748b}.panel{padding:18px;border:1px solid #dce4ed;border-radius:10px;background:#fff}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(220px,1fr));gap:0 18px}.wide-select{width:100%}.action-bar{position:sticky;bottom:0;padding:14px 18px;border:1px solid #dce4ed;border-radius:10px;background:#fff;box-shadow:0 -4px 18px rgba(15,23,42,.08)}.action-bar span{color:#9a3412}@media(max-width:760px){.form-grid{grid-template-columns:1fr}}
</style>
