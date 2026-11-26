<template>
  <main class="supplier-quote-page" data-page-code="supplier-quote-workbench"
    :data-page-name="businessName.pageTitle" data-module-code="SCM" data-business-object="SupplierQuotation" :data-mode="dataMode">
    <header class="page-heading"><div><p class="eyebrow">SCM · 采购报价</p><h1>{{ businessName.pageTitle }}</h1>
      <p>所有询价报价准备按“物料 × 供应商”完整进入列表，只填写报价金额和备注。</p></div>
      <el-button @click="refreshFacts">刷新</el-button></header>

    <section class="panel mode-banner" data-acceptance-region="runtime-mode">
      <strong>运行模式：{{ dataMode }}</strong>
      <span v-if="dataMode==='canary_acceptance'">批次 {{ providerFacts.canaryBatchId }} · 场景 {{ providerFacts.scenarioCode }}</span>
      <span v-else>正式 SupplierQuotation 服务端事实</span>
    </section>

    <section class="panel" data-acceptance-region="page-operation-guide" data-guide-contract="GUIDE-001..010">
      <h2>页面操作指引</h2>
      <ol><li><b>用途：</b>接收供应商针对询价的报价。</li><li><b>第一步：</b>查看询价来源。</li>
        <li><b>第二步：</b>确认供应商。</li><li><b>第三步：</b>录入报价明细。</li>
        <li><b>第四步：</b>保存报价。</li><li><b>第五步：</b>提交报价。</li><li><b>第六步：</b>进入核价。</li></ol>
      <p>采购员可在正式模式录入；金丝雀模式只读。保存需要正数报价，提交要求同一供应商的全部询价物料均已报价。</p>
    </section>

    <section class="panel" data-acceptance-region="source-inquiry">
      <h2>来源询价</h2><div v-if="currentRow" class="source-grid">
        <span>询价编号<strong>{{ currentRow.sourceInquiryNo }}</strong></span>
        <span>报价编号<strong>{{ currentRow.quotationNo || '保存后生成' }}</strong></span>
        <span>供应商<strong>{{ currentRow.supplierName }}</strong></span>
        <span>报价状态<strong>{{ currentRow.quotationStatusLabel }}</strong></span>
      </div><el-empty v-else description="暂无可报价的来源询价" />
    </section>

    <section class="panel summary" data-acceptance-region="data-alignment">
      <div><span>询价报价准备明细</span><strong>{{ providerFacts.preparationRecordCount }}</strong></div>
      <div><span>供应商报价列表</span><strong>{{ providerFacts.recordCount }}</strong></div>
      <el-tag :type="providerFacts.dataAligned ? 'success' : 'danger'">
        {{ providerFacts.dataAligned ? '数量一致' : '数量不一致' }}
      </el-tag>
    </section>

    <section class="panel" data-acceptance-region="supplier-quote-list">
      <div class="section-heading"><div><h2>供应商报价列表</h2><p>不使用卡片，不要求交期、价格有效期、税率或复杂商务条件。</p></div></div>
      <ScmSupplierQuoteEnterpriseList :rows="providerFacts.records" @edit="openQuoteEditor" />
    </section>

    <section class="panel action-panel" data-acceptance-region="business-actions">
      <div><h2>完成报价收集</h2><p>仅当同一询价的全部报价金额均已保存时，才能进入报价比较。</p></div>
      <div class="actions"><el-button type="success" data-process-action="SUBMIT_SUPPLIER_QUOTATION"
        :disabled="dataMode!=='production'||!submittableQuotations.length" @click="submitSavedQuotations">提交已保存报价</el-button>
        <el-button type="primary" :disabled="!hasComparisonReady" @click="router.push('/scm/quote-comparisons')">进入报价比较</el-button>
        <el-button disabled title="必须先完成报价比较，本版本不进入核价开发">进入核价</el-button></div>
    </section>

    <el-dialog v-model="editorVisible" :title="editingRow?.quoted ? '修改报价' : '填写报价'" width="620px" destroy-on-close>
      <el-descriptions v-if="editingRow" :column="2" border>
        <el-descriptions-item label="询价编号">{{ editingRow.inquiryNo }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ editingRow.supplierName }}（{{ editingRow.supplierCode }}）</el-descriptions-item>
        <el-descriptions-item label="物料">{{ editingRow.materialName }}（{{ editingRow.materialCode }}）</el-descriptions-item>
        <el-descriptions-item label="数量">{{ editingRow.quantity }}</el-descriptions-item>
      </el-descriptions>
      <el-form class="quote-form" label-position="top">
        <el-form-item label="报价金额"><el-input-number v-model="quoteForm.quotePrice" :min="0.01" :precision="2" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="quoteForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editorVisible=false">取消</el-button>
        <el-button type="primary" data-process-action="SAVE_SUPPLIER_QUOTE" @click="saveQuote">保存报价</el-button></template>
    </el-dialog>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { resolveBusinessName } from '@/meta/governance/businessNameRegistry.js'
import ScmSupplierQuoteEnterpriseList from '@/meta/components/ScmSupplierQuoteEnterpriseList.vue'
import { supplierQuoteProvider } from '@/meta/providers/supplierQuoteProviderV114289.js'

const businessName = resolveBusinessName('supplier-quote')
const router = useRouter()
const route = useRoute()
const providerFacts = ref({ contexts: [], records: [], recordCount: 0, preparationRecordCount: 0, dataAligned: true, dataMode: 'production' })
const editorVisible = ref(false)
const editingRow = ref(null)
const quoteForm = reactive({ quotePrice: 0, remark: '' })
const dataMode = computed(() => providerFacts.value.dataMode || 'production')
const currentRow = computed(() => providerFacts.value.records.at(-1) || null)
const hasComparisonReady = computed(() => false)
const submittableQuotations = computed(() => [...new Set(providerFacts.value.records
  .filter(row => row.quotationId && row.quotationStatus === 'saved').map(row => row.quotationId))])

async function refreshFacts() { try { providerFacts.value = await supplierQuoteProvider.loadRuntime({ query: { ...route.query } }) }
  catch (error) { ElMessage.error(error?.message || '供应商报价读取失败') } }
function openQuoteEditor(row) {
  editingRow.value = row
  Object.assign(quoteForm, { quotePrice: Number(row.quotePrice ?? row.quote?.unitPrice ?? 0), remark: row.remark || row.quote?.remark || '' })
  editorVisible.value = true
}
async function saveQuote() {
  if (dataMode.value !== 'production') return ElMessage.warning('金丝雀模式只读。')
  try { await supplierQuoteProvider.saveQuotation(editingRow.value, quoteForm); editorVisible.value = false
    await refreshFacts(); ElMessage.success('供应商报价已保存') }
  catch (error) { ElMessage.error(error?.message || '请填写大于 0 的报价金额。') }
}
async function submitSavedQuotations() {
  try { for (const id of submittableQuotations.value) await supplierQuoteProvider.submitQuotation(id)
    await refreshFacts(); ElMessage.success('供应商报价已提交并接收') }
  catch (error) { ElMessage.error(error?.message || '仍有报价明细未完成。') }
}
onMounted(refreshFacts)
watch(() => [route.query.canaryBatchId, route.query.scenarioCode], refreshFacts)
</script>

<style scoped>
.supplier-quote-page{display:grid;gap:18px;padding:20px}.page-heading,.section-heading,.action-panel{display:flex;align-items:center;justify-content:space-between;gap:18px}.page-heading h1,.section-heading h2,.action-panel h2{margin:0}.page-heading p,.section-heading p,.action-panel p{margin:6px 0 0;color:#64748b}.eyebrow{font-weight:700;color:#2563eb!important}.panel{padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.summary{display:flex;align-items:center;gap:36px}.summary div{display:grid;gap:4px}.summary span{color:#64748b}.summary strong{font-size:24px}.actions{display:flex;gap:10px}.quote-form{display:grid;gap:10px;margin-top:18px}.quote-form :deep(.el-input-number){width:100%}@media(max-width:800px){.page-heading,.section-heading,.action-panel,.summary{align-items:flex-start;flex-direction:column}}
.mode-banner{display:flex;align-items:center;justify-content:space-between;gap:18px}.source-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}.source-grid span{display:grid;gap:5px;padding:12px;background:#f8fafc;border-radius:8px}
</style>
