<template>
  <main class="runtime-operator" :data-page-code="metadata.pageCode" data-page-type="OPERATOR_PAGE" data-fact-source="server" data-legacy-formal-store-dependency="0" data-business-localstorage-write="0">
    <section class="identity">
      <div><p class="eyebrow">Server-backed Foundation Operator</p><h1>{{ metadata.title }}</h1><p>{{ responsibility }}</p></div>
      <div class="identity-actions"><router-link to="/foundation">返回企业基础资料</router-link><button type="button" :disabled="loading" @click="loadRuntime">{{ loading ? '正在刷新' : '刷新' }}</button></div>
    </section>

    <section class="facts" data-acceptance-id="FOUNDATION_RUNTIME_SERVER_FACTS">
      <span>正式事实源：{{ factSource }}</span><span>加载状态：{{ loadStatus }}</span><span>服务端记录：{{ rows.length }}</span><span>业务 localStorage 写入：0</span>
    </section>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

    <FoundationMetadataList :metadata="metadata" :rows="rows" :refreshing="loading" :can-toggle-status="false" @refresh="loadRuntime" @view="showDetail" @edit="startEdit" />

    <el-dialog v-model="detailVisible" :title="`${metadata.title}详情`" width="760px">
      <dl class="detail-grid"><template v-for="field in metadata.fields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ display(detailRow?.[field.key]) }}</dd></template></dl>
    </el-dialog>

    <el-dialog v-model="editVisible" :title="`维护${metadata.title}`" width="620px" :close-on-click-modal="false">
      <el-form label-width="150px">
        <template v-if="runtimeKind === 'price'">
          <el-form-item label="税率（%）"><el-select v-model="priceForm.taxRate"><el-option v-for="value in ['0','3','6','9','13']" :key="value" :label="`${value}%`" :value="value" /></el-select></el-form-item>
          <el-form-item label="生效日期"><el-date-picker v-model="priceForm.effectiveDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="失效日期"><el-date-picker v-model="priceForm.expiryDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
          <el-form-item label="修改原因"><el-input v-model="priceForm.modifyReason" type="textarea" :rows="3" /></el-form-item>
        </template>
        <el-form-item v-else label="交货周期（天）"><el-input-number v-model="relationForm.deliveryPeriod" :min="0" :max="3650" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editVisible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存到正式服务端</el-button></template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import FoundationMetadataList from '@/meta/components/FoundationMetadataList.vue'
import { findFoundationListMetadata } from '@/meta/master-data/masterDataRegistry.js'
import { MATERIAL_SUPPLIER_RELATION_LIST_METADATA } from '@/meta/runtime/materialSupplierRelationRuntime.js'
import { loadMaterialSupplierRelationRuntime, updateMaterialSupplierDeliveryPeriod } from '@/meta/providers/materialSupplierRelationRuntimeProvider.js'
import { loadSupplierMaterialPriceRuntime, updateSupplierMaterialPrice } from '@/meta/providers/supplierMaterialPriceRuntimeProvider.js'

const props = defineProps({ runtimeKind: { type: String, required: true, validator: value => ['relation', 'price'].includes(value) } })
const priceMetadata = findFoundationListMetadata('supplierMaterialPrices')
function withoutRemoteOptionLookup(field) {
  return field.filterType === 'remote-select' || (field.optionsProvider && typeof field.optionsProvider === 'object')
    ? { ...field, filterType: 'text', type: 'text', options: [], optionsProvider: undefined, optionsSource: undefined }
    : field
}
const metadata = computed(() => {
  const source = props.runtimeKind === 'relation' ? MATERIAL_SUPPLIER_RELATION_LIST_METADATA : priceMetadata
  return {
    ...source,
    fields: source.fields.map(withoutRemoteOptionLookup),
    filterSchema: source.filterSchema.map(withoutRemoteOptionLookup),
  }
})
const factSource = computed(() => props.runtimeKind === 'relation' ? 'MaterialSupplierRelationRuntime' : 'SupplierMaterialPriceRuntime')
const responsibility = computed(() => props.runtimeKind === 'relation' ? '维护正式物料供应关系；保存只调用现有服务端关系维护 API。' : '维护审批链管理的正式供应价格版本；保存只调用现有服务端价格维护 API。')
const rows = ref([])
const loading = ref(false)
const saving = ref(false)
const loadStatus = ref('loading')
const errorMessage = ref('')
const detailVisible = ref(false)
const detailRow = ref(null)
const editVisible = ref(false)
const editRow = ref(null)
const priceForm = reactive({ taxRate: '', effectiveDate: '', expiryDate: '', modifyReason: '' })
const relationForm = reactive({ deliveryPeriod: 0 })

async function loadRuntime() {
  loading.value = true
  errorMessage.value = ''
  try {
    const runtime = props.runtimeKind === 'relation' ? await loadMaterialSupplierRelationRuntime({ force: true }) : await loadSupplierMaterialPriceRuntime({ force: true })
    rows.value = [...runtime.rows]
    loadStatus.value = 'SERVER / LOADED'
  } catch (error) {
    rows.value = []
    loadStatus.value = 'SERVER / READ_FAILED'
    errorMessage.value = error?.message || '正式服务端事实读取失败。'
  } finally { loading.value = false }
}
function showDetail(row) { detailRow.value = row; detailVisible.value = true }
function startEdit(row) {
  editRow.value = row
  if (props.runtimeKind === 'price') Object.assign(priceForm, { taxRate: String(row.taxRate ?? ''), effectiveDate: row.effectiveDate || '', expiryDate: row.expiryDate || '', modifyReason: '' })
  else relationForm.deliveryPeriod = Number(row.deliveryPeriod || 0)
  editVisible.value = true
}
async function save() {
  if (props.runtimeKind === 'price' && !priceForm.modifyReason.trim()) { ElMessage.error('修改原因不能为空。'); return }
  if (props.runtimeKind === 'price' && priceForm.expiryDate && priceForm.effectiveDate && priceForm.expiryDate < priceForm.effectiveDate) { ElMessage.error('失效日期不能早于生效日期。'); return }
  saving.value = true
  try {
    const runtime = props.runtimeKind === 'price'
      ? await updateSupplierMaterialPrice(editRow.value?.priceNo || editRow.value?.priceId, { ...priceForm })
      : await updateMaterialSupplierDeliveryPeriod(editRow.value?.relationCode, relationForm.deliveryPeriod)
    rows.value = [...runtime.rows]
    editVisible.value = false
    ElMessage.success('服务端保存成功。')
  } catch (error) { ElMessage.error(error?.response?.data?.errorMessage || error?.message || '服务端保存失败。') }
  finally { saving.value = false }
}
function display(value) { if (value === undefined || value === null || value === '') return '—'; if (Array.isArray(value)) return value.join('、'); return String(value) }
onMounted(loadRuntime)
watch(() => props.runtimeKind, () => {
  detailVisible.value = false
  editVisible.value = false
  loadRuntime()
})
</script>

<style scoped>
.runtime-operator{width:100%;max-width:100%;min-width:0;padding:24px;overflow-x:hidden;box-sizing:border-box;color:#17233a}.identity,.facts{border:1px solid #d9e2f2;border-radius:14px;background:#fff;padding:20px 22px;margin-bottom:16px}.identity{display:flex;justify-content:space-between;align-items:center;gap:20px}.identity h1,.identity p{margin:0}.eyebrow{font-size:12px;color:#607089}.identity h1{margin:5px 0 8px}.identity-actions{display:flex;gap:10px;align-items:center}.identity-actions a,.identity-actions button{border:1px solid #3157d5;border-radius:9px;padding:9px 13px;background:#fff;color:#3157d5;text-decoration:none;font-weight:700}.facts{display:flex;gap:20px;flex-wrap:wrap;background:#f8faff}.error{color:#b42318}.detail-grid{display:grid;grid-template-columns:170px 1fr;gap:1px;background:#e4eaf3}.detail-grid dt,.detail-grid dd{margin:0;padding:10px 12px;background:#fff}.detail-grid dt{font-weight:700}@media(max-width:760px){.runtime-operator{padding:14px}.identity{align-items:flex-start;flex-direction:column}.detail-grid{grid-template-columns:1fr}}
</style>
