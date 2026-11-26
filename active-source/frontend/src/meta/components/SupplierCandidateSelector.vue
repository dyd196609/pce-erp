<template>
  <section class="supplier-candidate-selector" data-provider-code="SupplierCandidateProvider"
    data-context-type="PurchaseInquirySupplierCandidateContext" data-allow-free-text="false">
    <div class="candidate-toolbar">
      <div>
        <strong>当前供应商候选（{{ candidates.length }}）</strong>
        <p>候选仅来自 Supplier Master，不允许自由文本录入。</p>
      </div>
      <div class="candidate-add">
        <el-select v-model="pendingSupplierCode" filterable clearable
          data-candidate-action="search" placeholder="搜索供应商编码或名称">
          <el-option v-for="supplier in availableOptions" :key="supplier.supplierCode"
            :label="supplier.label" :value="supplier.supplierCode" />
        </el-select>
        <el-button type="primary" data-candidate-action="add" :disabled="!pendingSupplierCode"
          @click="addCandidate">增加供应商</el-button>
      </div>
    </div>

    <div v-if="candidates.length" class="candidate-card-scroll" data-layout="independent-cards-horizontal-scroll">
      <article v-for="(candidate, index) in candidates" :key="`${candidate.supplierCode}-${index}`"
        class="candidate-card" data-candidate-record>
        <div class="candidate-card-heading">
          <strong>{{ candidate.supplierName }}</strong>
          <el-button link type="danger" data-candidate-action="remove"
            @click="removeCandidate(index)">删除供应商</el-button>
        </div>
        <dl>
          <div><dt>供应商编码</dt><dd>{{ candidate.supplierCode }}</dd></div>
          <div><dt>供应商状态</dt><dd>{{ businessDisplay(candidate).supplierStatusLabel }}</dd></div>
          <div><dt>供应商分类</dt><dd>{{ businessDisplay(candidate).supplierCategoryLabel }}</dd></div>
          <div><dt>数据来源</dt><dd>{{ businessDisplay(candidate).sourceLabel }}</dd></div>
        </dl>
        <el-select :model-value="candidate.supplierCode" filterable
          data-candidate-action="replace" placeholder="从主数据替换供应商"
          @change="replaceCandidate(index, $event)">
          <el-option v-for="supplier in options" :key="supplier.supplierCode"
            :label="supplier.label" :value="supplier.supplierCode" />
        </el-select>
      </article>
    </div>
    <el-empty v-else description="尚未选择供应商候选，请从供应商主数据增加" />
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { supplierCandidateProvider } from '@/meta/providers/supplierCandidateProvider.js'
import { createSupplierBusinessDisplay } from '@/meta/process/scm/purchaseInquiry/businessStatusDisplayMapping.js'
import { addPurchaseInquirySupplierCandidate, normalizePurchaseInquirySupplierCandidate,
  removePurchaseInquirySupplierCandidate, replacePurchaseInquirySupplierCandidate }
  from '@/meta/process/scm/purchaseInquiry/purchaseInquirySupplierCandidateContext.js'

const props = defineProps({ modelValue: { type: Array, default: () => [] } })
const emit = defineEmits(['update:modelValue'])
const options = supplierCandidateProvider.load().options
const pendingSupplierCode = ref('')
const candidates = computed(() => props.modelValue.map(normalizePurchaseInquirySupplierCandidate))
const availableOptions = computed(() => {
  const selected = new Set(candidates.value.map(candidate => candidate.supplierCode))
  return options.filter(option => !selected.has(option.supplierCode))
})
const findMaster = supplierCode => options.find(option => option.supplierCode === supplierCode)
const businessDisplay = candidate => createSupplierBusinessDisplay(candidate)

function addCandidate() {
  try {
    emit('update:modelValue', addPurchaseInquirySupplierCandidate(candidates.value,
      findMaster(pendingSupplierCode.value)))
    pendingSupplierCode.value = ''
  } catch (error) { ElMessage.warning(error.message) }
}
function removeCandidate(index) {
  emit('update:modelValue', removePurchaseInquirySupplierCandidate(candidates.value, index))
}
function replaceCandidate(index, supplierCode) {
  try {
    emit('update:modelValue', replacePurchaseInquirySupplierCandidate(candidates.value, index,
      findMaster(supplierCode)))
  } catch (error) { ElMessage.warning(error.message) }
}
</script>

<style scoped>
.supplier-candidate-selector{display:grid;gap:16px}.candidate-toolbar,.candidate-card-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.candidate-toolbar p{margin:4px 0 0;color:#64748b}.candidate-add{display:flex;gap:10px;min-width:440px}.candidate-add .el-select{flex:1}.candidate-card-scroll{display:flex;gap:14px;overflow-x:auto;padding:2px 2px 10px}.candidate-card{box-sizing:border-box;display:grid;flex:0 0 320px;gap:14px;padding:16px;border:1px solid #dce4ed;border-radius:10px;background:#f8fafc}.candidate-card dl{display:grid;gap:8px;margin:0}.candidate-card dl div{display:grid;grid-template-columns:90px 1fr;gap:8px}.candidate-card dt{color:#64748b}.candidate-card dd{margin:0;overflow-wrap:anywhere}@media (max-width:800px){.candidate-toolbar{align-items:stretch;flex-direction:column}.candidate-add{min-width:0}}
</style>
