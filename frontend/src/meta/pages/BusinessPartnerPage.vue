<template>
  <main class="business-partner-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.12.8.3 业务伙伴基础资料</p>
        <h1>{{ pageTitle }}</h1>
        <p>本页只维护供应商、经销商和企业银行账户基础资料，不开发销售订单、应收账款、收款、真实付款或银行支付。</p>
        <p class="app-current-module-badge">当前操作模块：{{ pageTitle }}</p>
      </section>
      <nav class="page-tabs app-module-nav-zone">
        <span class="app-nav-zone-title">基础资料导航</span>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': activeTab === 'suppliers' }" to="/foundation/suppliers">
          供应商档案 <span v-if="activeTab === 'suppliers'" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': activeTab === 'dealers' }" to="/foundation/dealers">
          经销商档案 <span v-if="activeTab === 'dealers'" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" :class="{ 'app-nav-button-active': activeTab === 'banks' }" to="/foundation/company-bank-accounts">
          企业银行账户 <span v-if="activeTab === 'banks'" class="app-current-tag">当前</span>
        </router-link>
        <router-link class="app-nav-button" to="/foundation">第一期基础资料</router-link>
        <router-link class="app-nav-button" to="/reference">数据引用中心</router-link>
      </nav>
    </header>

    <el-alert v-if="message" :title="message" :type="messageType" show-icon :closable="false" />

    <section class="operation-shell">
      <section class="plain-flow-guide">
        <strong>业务伙伴基础资料：供应商档案 / 经销商档案 / 企业银行账户</strong>
        <div class="plain-flow-grid">
          <span><b>当前步骤</b>维护付款和后续销售收款所需基础资料。</span>
          <span><b>本页要做</b>新增、编辑、启停供应商/经销商，维护企业付款账户。</span>
          <span><b>下一步做什么</b>付款前检查优先从这里带出供应商银行信息和企业默认账户。</span>
          <span><b>本页不会做</b>不真实付款、不银行支付、不生成凭证、不开发销售/应收/收款。</span>
        </div>
      </section>

      <el-card shadow="never">
        <template #header>
          <div class="card-header">
            <div>
              <h2>{{ pageTitle }}</h2>
              <span>查询、排序、清除排序和启停操作均只作用于当前基础资料。</span>
            </div>
            <div class="button-row">
              <el-input v-model="keyword" placeholder="搜索编码、名称、银行、联系人" clearable />
              <el-button @click="clearSort">清除排序</el-button>
              <template v-if="activeTab === 'suppliers'">
                <el-button @click="runCollectSuppliers">归集历史供应商</el-button>
                <el-button @click="runEnrichBankInfo">补齐银行信息</el-button>
                <el-button type="warning" @click="runCollectAndEnrich">归集并补齐</el-button>
              </template>
              <el-button type="primary" @click="startCreate">新增{{ entityLabel }}</el-button>
            </div>
          </div>
        </template>

        <el-alert
          v-if="activeTab === 'suppliers'"
          class="supplier-bank-warning"
          title="自动补齐的银行信息为模拟数据，仅用于本地流程验证，请后续维护为真实资料。"
          type="warning"
          show-icon
          :closable="false"
        />
        <el-alert
          v-if="activeTab === 'suppliers' && syncResultText"
          class="supplier-sync-result"
          :title="syncResultText"
          type="success"
          show-icon
          :closable="false"
        />

        <el-table v-if="activeTab === 'suppliers'" :data="sortedSuppliers" border stripe height="520" @sort-change="handleSortChange">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="supplierCode" label="供应商编码" min-width="130" sortable="custom" />
          <el-table-column prop="supplierName" label="供应商名称" min-width="170" sortable="custom" />
          <el-table-column prop="supplierType" label="类型" width="120"><template #default="{ row }">{{ supplierTypeLabel(row.supplierType) }}</template></el-table-column>
          <el-table-column prop="bankName" label="开户行" min-width="190" />
          <el-table-column prop="bankAccount" label="银行账号" min-width="180" />
          <el-table-column prop="bankAccountName" label="账户名称" min-width="160" />
          <el-table-column prop="defaultPaymentMethod" label="默认付款方式" width="140"><template #default="{ row }">{{ paymentMethodLabel(row.defaultPaymentMethod) }}</template></el-table-column>
          <el-table-column label="资料完整度" width="130"><template #default="{ row }"><el-tag :type="supplierCompletenessType(row)">{{ supplierCompleteness(row).statusText }}</el-tag></template></el-table-column>
          <el-table-column label="银行信息状态" width="140"><template #default="{ row }">{{ supplierCompleteness(row).bankStatusText }}</template></el-table-column>
          <el-table-column label="是否自动补齐" width="130"><template #default="{ row }">{{ row.bankInfoMocked ? '已自动补齐' : '否' }}</template></el-table-column>
          <el-table-column label="来源类型" min-width="160"><template #default="{ row }">{{ supplierSourceText(row) }}</template></el-table-column>
          <el-table-column label="价格资料" width="120"><template #default="{ row }">{{ Number(row.linkedSupplierMaterialPriceCount || 0) > 0 ? '已有价格资料' : '-' }}</template></el-table-column>
          <el-table-column prop="enabled" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['编辑', '停用'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="startEdit(row)">编辑</el-button>
                <el-button v-if="row.enabled" size="small" class="app-action-button-sm" type="warning" @click="disableSupplier(row.id); refresh(); notify('供应商已停用')">停用</el-button>
                <el-button v-else size="small" class="app-action-button-sm" type="success" @click="enableSupplier(row.id); refresh(); notify('供应商已启用')">启用</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <el-table v-else-if="activeTab === 'dealers'" :data="sortedDealers" border stripe height="520" @sort-change="handleSortChange">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="dealerCode" label="经销商编码" min-width="130" sortable="custom" />
          <el-table-column prop="dealerName" label="经销商名称" min-width="170" sortable="custom" />
          <el-table-column prop="dealerType" label="类型" width="130"><template #default="{ row }">{{ dealerTypeLabel(row.dealerType) }}</template></el-table-column>
          <el-table-column prop="bankName" label="开户行" min-width="190" />
          <el-table-column prop="bankAccount" label="银行账号" min-width="180" />
          <el-table-column prop="bankAccountName" label="账户名称" min-width="160" />
          <el-table-column prop="salesRegion" label="销售区域" width="120" />
          <el-table-column prop="enabled" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['编辑', '停用'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="startEdit(row)">编辑</el-button>
                <el-button v-if="row.enabled" size="small" class="app-action-button-sm" type="warning" @click="disableDealer(row.id); refresh(); notify('经销商已停用')">停用</el-button>
                <el-button v-else size="small" class="app-action-button-sm" type="success" @click="enableDealer(row.id); refresh(); notify('经销商已启用')">启用</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>

        <el-table v-else :data="sortedBanks" border stripe height="520" @sort-change="handleSortChange">
          <el-table-column type="index" label="序号" width="70" fixed="left" />
          <el-table-column prop="accountCode" label="账户编码" min-width="130" sortable="custom" />
          <el-table-column prop="accountName" label="账户名称" min-width="190" sortable="custom" />
          <el-table-column prop="bankName" label="开户行" min-width="210" />
          <el-table-column prop="bankAccount" label="银行账号" min-width="180" />
          <el-table-column prop="currency" label="币种" width="90" />
          <el-table-column prop="accountType" label="账户类型" width="120"><template #default="{ row }">{{ accountTypeLabel(row.accountType) }}</template></el-table-column>
          <el-table-column prop="isDefault" label="默认" width="100"><template #default="{ row }"><el-tag :type="row.isDefault ? 'success' : 'info'">{{ row.isDefault ? '默认' : '否' }}</el-tag></template></el-table-column>
          <el-table-column prop="enabled" label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
          <el-table-column label="操作" fixed="right" :width="getActionColumnWidth(['编辑', '设为默认', '停用'])">
            <template #default="{ row }">
              <div class="app-action-cell">
                <el-button size="small" class="app-action-button-sm" @click="startEdit(row)">编辑</el-button>
                <el-button size="small" class="app-action-button-sm" type="primary" :disabled="row.isDefault || !row.enabled" @click="setDefaultBank(row)">设为默认</el-button>
                <el-button v-if="row.enabled" size="small" class="app-action-button-sm" type="warning" @click="disableCompanyBankAccount(row.id); refresh(); notify('企业银行账户已停用')">停用</el-button>
                <el-button v-else size="small" class="app-action-button-sm" type="success" @click="enableCompanyBankAccount(row.id); refresh(); notify('企业银行账户已启用')">启用</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card v-if="editorOpen" shadow="never">
        <template #header>
          <div class="card-header">
            <h2>{{ editingId ? '编辑' : '新增' }}{{ entityLabel }}</h2>
            <div class="button-row">
              <el-button @click="closeEditor">取消</el-button>
              <el-button type="success" @click="saveEditor">保存</el-button>
            </div>
          </div>
        </template>
        <el-form class="editor-form" label-width="120px">
          <template v-if="activeTab === 'suppliers'">
            <el-form-item label="供应商编码"><el-input v-model="form.supplierCode" /></el-form-item>
            <el-form-item label="供应商名称"><el-input v-model="form.supplierName" /></el-form-item>
            <el-form-item label="简称"><el-input v-model="form.supplierShortName" /></el-form-item>
            <el-form-item label="类型"><el-select v-model="form.supplierType"><el-option label="物料供应商" value="material" /><el-option label="服务供应商" value="service" /><el-option label="物流供应商" value="logistics" /><el-option label="其他" value="other" /></el-select></el-form-item>
            <el-form-item label="开户行"><el-input v-model="form.bankName" /></el-form-item>
            <el-form-item label="银行账号"><el-input v-model="form.bankAccount" /></el-form-item>
            <el-form-item label="账户名称"><el-input v-model="form.bankAccountName" /></el-form-item>
            <el-form-item label="默认付款方式"><el-select v-model="form.defaultPaymentMethod"><el-option label="银行转账" value="bankTransfer" /><el-option label="现金" value="cash" /><el-option label="承兑" value="acceptance" /></el-select></el-form-item>
          </template>
          <template v-else-if="activeTab === 'dealers'">
            <el-form-item label="经销商编码"><el-input v-model="form.dealerCode" /></el-form-item>
            <el-form-item label="经销商名称"><el-input v-model="form.dealerName" /></el-form-item>
            <el-form-item label="简称"><el-input v-model="form.dealerShortName" /></el-form-item>
            <el-form-item label="类型"><el-select v-model="form.dealerType"><el-option label="经销商" value="distributor" /><el-option label="直销客户" value="directCustomer" /><el-option label="项目客户" value="projectCustomer" /><el-option label="其他" value="other" /></el-select></el-form-item>
            <el-form-item label="开户行"><el-input v-model="form.bankName" /></el-form-item>
            <el-form-item label="银行账号"><el-input v-model="form.bankAccount" /></el-form-item>
            <el-form-item label="账户名称"><el-input v-model="form.bankAccountName" /></el-form-item>
            <el-form-item label="销售区域"><el-input v-model="form.salesRegion" /></el-form-item>
          </template>
          <template v-else>
            <el-form-item label="账户编码"><el-input v-model="form.accountCode" /></el-form-item>
            <el-form-item label="账户名称"><el-input v-model="form.accountName" /></el-form-item>
            <el-form-item label="开户行"><el-input v-model="form.bankName" /></el-form-item>
            <el-form-item label="银行账号"><el-input v-model="form.bankAccount" /></el-form-item>
            <el-form-item label="币种"><el-input v-model="form.currency" /></el-form-item>
            <el-form-item label="账户类型"><el-select v-model="form.accountType"><el-option label="基本户" value="basic" /><el-option label="一般户" value="general" /><el-option label="专用户" value="special" /><el-option label="其他" value="other" /></el-select></el-form-item>
            <el-form-item label="默认账户"><el-switch v-model="form.isDefault" /></el-form-item>
          </template>
          <el-form-item label="联系人"><el-input v-model="form.contactPerson" /></el-form-item>
          <el-form-item label="联系电话"><el-input v-model="form.contactPhone" /></el-form-item>
          <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
        </el-form>
      </el-card>
    </section>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  createCompanyBankAccount,
  createDealer,
  createSupplier,
  disableCompanyBankAccount,
  disableDealer,
  disableSupplier,
  enrichMissingSupplierBankInfo,
  enableCompanyBankAccount,
  enableDealer,
  enableSupplier,
  getSupplierProfileCompleteness,
  listCompanyBankAccounts,
  listDealers,
  listSuppliers,
  syncLegacySuppliersToSupplierProfiles,
  updateCompanyBankAccount,
  updateDealer,
  updateSupplier,
} from '../foundation/businessPartnerStore.js'
import { getActionColumnWidth } from '../runtime/tableActionColumnEngine.js'
import { sortRecords } from '../runtime/tableSortEngine.js'

const route = useRoute()
const keyword = ref('')
const suppliers = ref([])
const dealers = ref([])
const banks = ref([])
const sortState = ref({ key: '', direction: 'asc' })
const editorOpen = ref(false)
const editingId = ref('')
const form = ref({})
const message = ref('')
const messageType = ref('success')
const syncResult = ref(null)

const activeTab = computed(() => {
  if (route.path.includes('dealer')) return 'dealers'
  if (route.path.includes('company-bank')) return 'banks'
  return 'suppliers'
})
const pageTitle = computed(() => ({ suppliers: '供应商档案', dealers: '经销商档案', banks: '企业银行账户' }[activeTab.value]))
const entityLabel = computed(() => ({ suppliers: '供应商', dealers: '经销商', banks: '企业银行账户' }[activeTab.value]))
const filteredSuppliers = computed(() => filterRows(suppliers.value, ['supplierCode', 'supplierName', 'bankName', 'bankAccountName', 'contactPerson']))
const filteredDealers = computed(() => filterRows(dealers.value, ['dealerCode', 'dealerName', 'bankName', 'bankAccountName', 'contactPerson']))
const filteredBanks = computed(() => filterRows(banks.value, ['accountCode', 'accountName', 'bankName', 'bankAccount']))
const sortedSuppliers = computed(() => sortRecords(filteredSuppliers.value, sortState.value, [{ key: 'supplierCode', sortType: 'string' }, { key: 'supplierName', sortType: 'string' }]))
const sortedDealers = computed(() => sortRecords(filteredDealers.value, sortState.value, [{ key: 'dealerCode', sortType: 'string' }, { key: 'dealerName', sortType: 'string' }]))
const sortedBanks = computed(() => sortRecords(filteredBanks.value, sortState.value, [{ key: 'accountCode', sortType: 'string' }, { key: 'accountName', sortType: 'string' }]))
const syncResultText = computed(() => syncResult.value
  ? `发现供应商 ${syncResult.value.found || 0} 个，新增供应商 ${syncResult.value.created || 0} 个，更新供应商 ${syncResult.value.updated || 0} 个，补齐银行信息 ${syncResult.value.enriched || 0} 个，跳过重复 ${syncResult.value.skipped || 0} 个。`
  : '')

function filterRows(rows, keys) {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return rows
  return rows.filter((row) => keys.some((key) => String(row[key] || '').toLowerCase().includes(text)))
}
function refresh() { suppliers.value = listSuppliers(); dealers.value = listDealers(); banks.value = listCompanyBankAccounts() }
function notify(text, type = 'success') { message.value = text; messageType.value = type; window.clearTimeout(notify.timer); notify.timer = window.setTimeout(() => { message.value = '' }, 2200) }
function clearSort() { sortState.value = { key: '', direction: 'asc' } }
function handleSortChange({ prop, order }) { sortState.value = { key: prop || '', direction: order === 'descending' ? 'desc' : 'asc' } }
function emptyForm() {
  return activeTab.value === 'suppliers'
    ? { supplierCode: `SUP-${Date.now().toString().slice(-4)}`, supplierName: '', supplierType: 'material', defaultPaymentMethod: 'bankTransfer', enabled: true }
    : activeTab.value === 'dealers'
      ? { dealerCode: `CUS-${Date.now().toString().slice(-4)}`, dealerName: '', dealerType: 'distributor', enabled: true }
      : { accountCode: `BANK-${Date.now().toString().slice(-4)}`, accountName: '广东智造科技有限公司', currency: 'CNY', accountType: 'general', enabled: true, isDefault: false }
}
function startCreate() { editingId.value = ''; form.value = emptyForm(); editorOpen.value = true }
function startEdit(row) { editingId.value = row.id; form.value = { ...row }; editorOpen.value = true }
function closeEditor() { editorOpen.value = false; editingId.value = ''; form.value = {} }
function saveEditor() {
  if (activeTab.value === 'suppliers') editingId.value ? updateSupplier(editingId.value, form.value) : createSupplier(form.value)
  if (activeTab.value === 'dealers') editingId.value ? updateDealer(editingId.value, form.value) : createDealer(form.value)
  if (activeTab.value === 'banks') editingId.value ? updateCompanyBankAccount(editingId.value, form.value) : createCompanyBankAccount(form.value)
  closeEditor()
  refresh()
  notify(`${entityLabel.value}已保存`)
}
function setDefaultBank(row) { updateCompanyBankAccount(row.id, { isDefault: true }); refresh(); notify('默认企业银行账户已更新') }
function runCollectSuppliers() {
  syncResult.value = syncLegacySuppliersToSupplierProfiles({ enrichBank: false })
  refresh()
  notify('历史供应商归集完成')
}
function runEnrichBankInfo() {
  syncResult.value = enrichMissingSupplierBankInfo()
  refresh()
  notify('供应商银行信息补齐完成', 'warning')
}
function runCollectAndEnrich() {
  syncResult.value = syncLegacySuppliersToSupplierProfiles({ enrichBank: true })
  refresh()
  notify('历史供应商已归集并补齐银行信息', 'warning')
}
function supplierCompleteness(row) { return getSupplierProfileCompleteness(row) }
function supplierCompletenessType(row) {
  return { complete: 'success', mocked: 'warning', missingBank: 'danger', disabled: 'info' }[supplierCompleteness(row).status] || 'info'
}
function supplierSourceText(row) {
  if (row.sourceText) return row.sourceText
  if (row.sourceType === 'legacyImported' || row.sourceType === 'autoCollected') return '来源：历史业务归集'
  return '人工维护'
}
function supplierTypeLabel(type) { return { material: '物料', service: '服务', logistics: '物流', other: '其他' }[type] || type }
function dealerTypeLabel(type) { return { distributor: '经销商', directCustomer: '直销客户', projectCustomer: '项目客户', other: '其他' }[type] || type }
function accountTypeLabel(type) { return { basic: '基本户', general: '一般户', special: '专用户', other: '其他' }[type] || type }
function paymentMethodLabel(method) { return { bankTransfer: '银行转账', cash: '现金', acceptance: '承兑', other: '其他' }[method] || method }

watch(() => route.path, () => { clearSort(); closeEditor(); refresh() }, { immediate: true })
</script>

<style scoped>
.business-partner-page { display: flex; flex-direction: column; gap: 16px; min-height: 100%; padding: 22px; background: #f5f7fb; color: #172033; }
.page-header, .card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-header p { margin: 6px 0 0; color: #475467; line-height: 1.5; }
.eyebrow, .card-header span { color: #64748b; font-size: 13px; }
h1, h2 { margin: 0; }
.page-tabs, .button-row { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.operation-shell { display: flex; flex-direction: column; gap: 16px; }
.plain-flow-guide { display: grid; gap: 10px; border: 1px solid #a7f3d0; border-radius: 8px; padding: 14px; background: #ecfdf5; color: #064e3b; line-height: 1.6; }
.plain-flow-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
.plain-flow-grid span { display: grid; gap: 4px; border: 1px solid rgba(6, 78, 59, 0.14); border-radius: 8px; padding: 10px; background: #fff; }
.button-row .el-input { width: 260px; }
.editor-form { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 2px 12px; }
@media (max-width: 900px) {
  .page-header { align-items: flex-start; flex-direction: column; }
  .plain-flow-grid { grid-template-columns: 1fr; }
}
</style>
