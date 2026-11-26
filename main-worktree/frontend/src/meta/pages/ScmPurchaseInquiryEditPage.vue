<template>
  <main class="inquiry-page" data-page-code="purchase-inquiry-edit" data-business-object="PurchaseInquiry"
    data-runtime-version="V1.14.2.8.18.7A">
    <header class="page-heading">
      <div><h1>{{ pageName.pageTitle }}</h1><p>{{ inquiryNo }} · 按物料完成供应商报价决策</p></div>
      <el-button @click="router.push('/scm/purchase-inquiry')">返回询价工作台</el-button>
    </header>
    <el-alert v-if="!draft" title="未找到可编辑的询价草稿运行上下文" type="error" :closable="false" show-icon />
    <template v-else>
      <section class="panel" data-acceptance-id="purchase-inquiry-edit-form">
        <h2>一、询价基本信息</h2>
        <el-descriptions :column="4" border>
          <el-descriptions-item label="询价编号">{{ draft.inquiryNo }}</el-descriptions-item>
          <el-descriptions-item label="来源采购申请">{{ draft.sourceRequestNo || '-' }}</el-descriptions-item>
          <el-descriptions-item label="业务状态">{{ pageState.businessStatusLabel }}</el-descriptions-item>
          <el-descriptions-item label="流程状态">{{ pageState.processStatusLabel }}</el-descriptions-item>
        </el-descriptions>
        <el-form label-position="top" class="basic-form">
          <div class="form-grid">
            <el-form-item label="询价主题"><el-input v-model="draft.inquiryTitle" /></el-form-item>
            <el-form-item label="询价日期"><el-date-picker v-model="draft.inquiryDate" type="date" value-format="YYYY-MM-DD" /></el-form-item>
            <el-form-item label="采购员"><el-input v-model="draft.buyer" /></el-form-item>
          </div>
        </el-form>
      </section>

      <section class="panel" data-acceptance-id="purchase-inquiry-material-supplier-decisions">
        <div class="section-heading"><div><h2>二、询价物料决策区</h2><p>每条物料独立决定参与报价的供应商。</p></div>
          <el-button data-line-action="add" @click="addLine">增加物料明细</el-button></div>
        <div class="material-decision-list">
          <article v-for="(line, index) in draft.materialLines" :key="`${line.materialCode}-${index}`"
            class="material-decision-card" data-material-supplier-decision>
            <div class="material-heading"><strong>物料 {{ index + 1 }} · {{ line.materialName || '待填写' }}</strong>
              <el-button link type="danger" data-line-action="remove" @click="removeLine(index)">删除物料</el-button></div>
            <div class="material-grid">
              <label>物料编码<el-input v-model="line.materialCode" /></label>
              <label>物料名称<el-input v-model="line.materialName" /></label>
              <label>规格<el-input v-model="line.specification" /></label>
              <label>数量<el-input-number v-model="line.quantity" :min="0.01" /></label>
              <label>需求日期<el-date-picker v-model="line.requiredDate" type="date" value-format="YYYY-MM-DD" /></label>
            </div>
            <div class="supplier-decision-region">
              <h3>该物料的供应商候选</h3>
              <MaterialSupplierCandidateSelector v-model="line.supplierCandidates"
                :material-code="line.materialCode" data-provider-code="SupplierCandidateProvider" />
            </div>
          </article>
        </div>
      </section>

      <section class="panel quote-preparation" data-acceptance-id="purchase-inquiry-quote-preparation">
        <div><h2>三、报价准备区</h2><p>已选择 {{ selectedSupplierCount }} 个供应商，形成 {{ materialDecisionCount }} 项物料—供应商决策。</p></div>
        <el-button type="success" data-process-action="PREPARE_SUPPLIER_QUOTE" :disabled="!canPrepareQuote" @click="prepareQuote">准备供应商报价</el-button>
      </section>

      <section class="panel" data-acceptance-id="purchase-inquiry-current-flow-position">
        <h2>四、流程导航区</h2>
        <PurchaseInquiryFlowNavigation :inquiry="navigationInquiry" />
      </section>

      <footer class="action-bar" data-acceptance-id="purchase-inquiry-edit-next-actions">
        <span>当前节点：{{ pageState.currentNode }} · 当前状态：{{ pageState.processStatusLabel }} · 下一步业务动作：{{ pageState.nextAction }}</span>
        <div><el-button type="primary" data-process-action="SAVE_PURCHASE_INQUIRY" @click="save">保存询价</el-button>
          <el-button data-process-action="PREPARE_SUPPLIER_QUOTE" :disabled="!canPrepareQuote" @click="prepareQuote">准备供应商报价</el-button>
          <el-button v-if="!canPrepareQuote" @click="router.push(`/scm/purchase-inquiry/acceptance/${encodeURIComponent(inquiryNo)}`)">进入供应商报价节点</el-button></div>
      </footer>
    </template>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import MaterialSupplierCandidateSelector from '@/meta/components/MaterialSupplierCandidateSelector.vue'
import PurchaseInquiryFlowNavigation from '@/meta/components/PurchaseInquiryFlowNavigation.vue'
import { savePurchaseInquiryDraft } from '@/meta/runtime/purchaseInquiryRuntime.js'
import { addPurchaseInquiryEditLine, createPurchaseInquiryEditContext,
  removePurchaseInquiryEditLine, validatePurchaseInquiryEditContext } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryEditContext.js'
import { buildMaterialSupplierCandidates } from '@/meta/process/scm/purchaseInquiry/materialSupplierCandidateContext.js'
import { resolvePurchaseInquiryBusinessState } from '@/meta/process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import { executePurchaseInquiryAction, loadPurchaseInquiryActionExecutionContext } from '@/meta/runtime/purchaseInquiryActionExecutionRuntime.js'
import { advancePurchaseInquiryBatchRuntime } from '@/meta/runtime/purchaseInquiryBatchRuntime.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'

const route = useRoute()
const router = useRouter()
const pageName = resolvePageNameConsumption({ pageCode: 'purchase-inquiry-edit', route: route.path })
const inquiryNo = computed(() => String(route.params.inquiryNo || ''))
const context = computed(() => loadPurchaseInquiryActionExecutionContext(inquiryNo.value))
const inquiry = computed(() => context.value?.inquiry || null)
const draft = ref(inquiry.value ? createPurchaseInquiryEditContext(inquiry.value) : null)
const navigationInquiry = computed(() => ({ ...draft.value,
  runtimeState: draft.value?.sourceRuntimeState || 'inquiry_draft' }))
const pageState = computed(() => resolvePurchaseInquiryBusinessState(navigationInquiry.value))
const canPrepareQuote = computed(() => navigationInquiry.value.runtimeState === 'inquiry_draft')
const materialCandidates = computed(() => buildMaterialSupplierCandidates(draft.value?.materialLines || []))
const selectedSupplierCount = computed(() => new Set(materialCandidates.value.map(item => item.supplierCode)).size)
const materialDecisionCount = computed(() => materialCandidates.value.length)

function addLine() { addPurchaseInquiryEditLine(draft.value, { requiredDate: draft.value.inquiryDate }) }
function removeLine(index) {
  try { removePurchaseInquiryEditLine(draft.value, index) } catch (error) { ElMessage.warning(error.message) }
}
function persistDraft() {
  if (!validatePurchaseInquiryEditContext(draft.value).valid) throw new Error('每条物料必须完整并至少选择一个供应商候选')
  return savePurchaseInquiryDraft({ ...draft.value, buyerName: draft.value.buyer,
    runtimeState: 'inquiry_editing' })
}
function save() {
  try {
    const result = persistDraft()
    if (result.object.statusCode !== 'draft') throw new Error('PURCHASE_INQUIRY_DRAFT_STATE_REQUIRED')
    ElMessage.success('询价与物料级供应商决策已保存')
    const next = advancePurchaseInquiryBatchRuntime()
    if (next.complete) {
      const detail = executePurchaseInquiryAction({ inquiry: result.object, actionCode: 'VIEW_PURCHASE_INQUIRY' })
      router.push(detail.route)
    } else router.push(next.route)
  } catch (error) { ElMessage.error(error?.message || '保存失败') }
}
function prepareQuote() {
  try {
    const saved = persistDraft()
    const result = executePurchaseInquiryAction({ inquiry: saved.object, actionCode: 'PREPARE_SUPPLIER_QUOTE' })
    if (!result.allowed) throw new Error('PURCHASE_INQUIRY_QUOTE_PREPARATION_NOT_ALLOWED')
    router.push(result.route)
  } catch (error) { ElMessage.error(error?.message || '准备供应商报价失败') }
}
</script>

<style scoped>
.inquiry-page{display:grid;gap:16px;max-width:1400px;margin:0 auto}.page-heading,.action-bar,.section-heading,.quote-preparation,.material-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.page-heading h1,.panel h2,.supplier-decision-region h3{margin:0}.page-heading p,.panel p{color:#64748b}.panel,.action-bar{padding:20px;border:1px solid #dce4ed;border-radius:10px;background:#fff}.basic-form{margin-top:16px}.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.material-decision-list{display:grid;gap:18px;margin-top:16px}.material-decision-card{display:grid;gap:16px;padding:18px;border:1px solid #cbd5e1;border-radius:12px;background:#f8fafc}.material-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px}.material-grid label{display:grid;gap:7px;color:#475569}.supplier-decision-region{display:grid;gap:12px;padding-top:14px;border-top:1px solid #dce4ed}.action-bar{position:sticky;bottom:0;z-index:2}.action-bar span{color:#64748b}@media(max-width:1000px){.material-grid,.form-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.quote-preparation{align-items:flex-start;flex-direction:column}}
</style>
