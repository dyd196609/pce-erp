<template>
  <PceListPageShell module-id="group3a-operation-targeted-revalidation" :governance="governance" :page-refresh-handler="load" :page-refresh-status="refreshStatus">
    <div class="page" data-acceptance-id="group3a-operation-targeted-revalidation" data-read-only="true">
      <FoundationBreadcrumb :show-acceptance-center="false" group="制造资源" module="工序 · 人工验收" show-return return-to="/foundation/master-data/operations" return-label="返回工序正式维护" />
      <section class="hero">
        <div><p>第3组 · 工序最终单项复验</p><h1>试装转序方式人工复核</h1><span>此前排序、核算方式、计量单位、检验工序、拉丝映射与中文显示均已冻结，本页只核对“试装”。</span></div>
        <strong>正式业务写入已停止</strong>
      </section>
      <section v-if="loading" class="card">正在读取正式回读事实……</section>
      <section v-else-if="error" class="card error">{{ error }}</section>
      <template v-else>
        <section class="summary">
          <article><span>正式工序</span><strong>{{ facts.formalOperationCount }}</strong></article>
          <article class="good"><span>唯一待确认项</span><strong>试装</strong></article>
          <article class="kitting"><span>齐套工序</span><strong>{{ facts.kitting?.count }}</strong></article>
          <article><span>一般工序</span><strong>{{ facts.general?.count }}</strong></article>
          <article class="good"><span>拉丝别名解析</span><strong>{{ facts.alias?.resolvedOccurrenceCount }}/{{ facts.alias?.sourceOccurrenceCount }}</strong></article>
          <article><span>正式BOM/路线/步骤写入</span><strong>0</strong></article>
        </section>

        <section class="card sequence" data-acceptance-id="trial-assembly-transition-readback">
          <header><div><h2>唯一待确认项：试装</h2><p>值直接回读自正式 system.Process.default_transition_mode。</p></div><PceBusinessStatus status-code="AWAITING_FINAL_CONFIRMATION" status-label="等待最终单项确认" /></header>
          <div class="flow"><strong>试装</strong><span>=</span><strong>{{ facts.finalTarget?.transitionMode }}</strong></div>
          <p>正式编码：<strong>{{ facts.finalTarget?.operationCode }}</strong></p>
          <p>Data Provenance：<strong>{{ facts.finalTarget?.dataProvenance?.join(' / ') }}</strong></p>
          <p>该值是 Operation 默认配置；具体路线仍允许由 RoutingStep.effective_transition_mode 覆盖。</p>
        </section>

        <section class="card">
          <header><div><h2>试装正式字段回读</h2><p>本表只有一个待确认对象；此前项目无需重复验收。</p></div><span>{{ rows.length }} 个待确认项</span></header>
          <PceEnterpriseListTable
            ref="tableRef" :contract="enterpriseListContract" page-id="group3a-operation-targeted-revalidation"
            table-id="group3a-operation-targeted-revalidation-main" :rows="rows" :table-rows="filteredRows"
            :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
            :advanced-visible="advancedVisible" :selected-count="selectedRows.length" :active-filter-count="activeFilterCount"
            :sort-text="sortText" primary-field="operationCode" primary-label="工序编码" :primary-width="190"
            min-width="1600px" :action-width="140"
            @update:quick-search="quickSearch = $event" @search="appliedSearch = quickSearch"
            @toggle-advanced="advancedVisible = !advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort"
            @export-current="exportCurrent" @clear-selection="clearSelection"
            @update-filter="(field, value) => filters[field] = value" @selection-change="selectedRows = $event" @sort-change="handleSort"
          >
            <template #columns>
              <el-table-column prop="operationName" label="工序名称" width="180" />
              <el-table-column prop="calculationMethod" label="核算方式" width="150" />
              <el-table-column prop="calculationUom" label="计量单位" width="230" />
              <el-table-column prop="transitionMode" label="转序方式" width="150" />
              <el-table-column prop="enabledLabel" label="启用状态" width="120" />
              <el-table-column prop="source" label="来源" width="270" />
              <el-table-column prop="acceptanceStatus" label="验收状态" width="160"><template #default="{ row }"><PceBusinessStatus status-code="AWAITING_RECHECK" :status-label="row.acceptanceStatus" /></template></el-table-column>
              <el-table-column prop="acceptanceFocus" label="本次复验重点" width="360" />
            </template>
            <template #actions><span>只读回看</span></template>
          </PceEnterpriseListTable>
        </section>

        <section class="card config">
          <h2>已冻结配置摘要（无需重复确认）</h2>
          <div class="config-grid"><article><strong>齐套工序（{{ facts.kitting?.count }}）</strong><p>{{ kittingDisplay }}</p></article><article><strong>一般工序（其余 {{ facts.general?.count }}）</strong><p>{{ facts.general?.names?.join('、') }}</p></article></div>
          <p>工序提供默认值；未来具体路线步骤的有效转序方式可以覆盖默认值，无需修改代码。</p>
        </section>

        <section class="card boundary"><strong>GROUP 3A：等待“试装 = 齐套工序”最终确认</strong><span>GROUP 3B 未进入 · GROUP 4 未进入 · Planning 未生产部署</span></section>
      </template>
    </div>
  </PceListPageShell>
</template>

<script setup>
import { computed, ref } from 'vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import FoundationBreadcrumb from '@/meta/components/FoundationBreadcrumb.vue'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'

defineProps({ embedded: { type: Boolean, default: false } })

const facts = ref({}); const rows = ref([]); const loading = ref(false); const error = ref(''); const refreshStatus = ref('idle')
const filterSchema = [
  { field: 'operationName', label: '工序名称', filterType: 'text' },
  { field: 'transitionMode', label: '转序方式', filterType: 'select', options: [{ label: '一般工序', value: '一般工序' }, { label: '齐套工序', value: '齐套工序' }] },
]
const governance = {
  pageCode: 'group3a-operation-targeted-revalidation', version: 'GROUP3A-REVALIDATION-V1', frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
  purpose: '只读回看试装默认转序方式，等待最终单项人工确认。',
  allowed: ['查看正式工序回读', '核对核算方式与单位', '核对一般/齐套配置', '核对来源别名'],
  forbidden: ['再次批量写入', '写BOM/路线/路线步骤', '进入第4组', '部署计划生产'],
  flowSteps: ['试装定向整改', '最终单项复验', '用户确认'], currentFlowStep: '最终单项复验',
  navigation: { previous: { label: '工序正式维护', pageUrl: '/foundation/master-data/operations' }, current: { label: '工序定向复验', pageCode: 'group3a-operation-targeted-revalidation', pageUrl: '/foundation/master-data/operations?view=acceptance' }, next: { label: '等待用户确认' } },
}
const enterpriseListContract = createPceEnterpriseListContract({ pageCode: 'group3a-operation-targeted-revalidation', pageType: 'list', title: '工序定向复验', moduleCode: 'PDE_GROUP3A' })
const { selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef, activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection, handleSort, exportCurrent } = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'group3a-operation-targeted-revalidation', searchFields: ['operationCode', 'operationName', 'calculationMethod', 'calculationUom', 'transitionMode'],
  exportFileName: '工序定向复验.csv', exportColumns: [{ field: 'operationCode', label: '工序编码' }, { field: 'operationName', label: '工序名称' }, { field: 'calculationMethod', label: '核算方式' }, { field: 'calculationUom', label: '计量单位' }, { field: 'transitionMode', label: '转序方式' }],
})
const kittingDisplay = computed(() => (facts.value.kitting?.names || []).map(name => name === '成品检' ? '成品检验（正式名称：成品检）' : name).join('、'))
async function load() {
  loading.value = true; error.value = ''; refreshStatus.value = 'refreshing'
  try { const response = await enterpriseMasterDataApi.group3AOperationTargetedRevalidation(); facts.value = response?.data ?? response; rows.value = facts.value.focusRows || []; refreshStatus.value = 'success' }
  catch (reason) { error.value = reason?.message || '工序定向复验事实读取失败'; refreshStatus.value = 'error' }
  finally { loading.value = false }
}
load()
</script>

<style scoped>
.page{padding:20px;color:#18243a}.hero,.card{background:#fff;border:1px solid #dce4ef;border-radius:16px;padding:20px 22px;margin-bottom:18px}.hero{display:flex;justify-content:space-between;align-items:center;gap:18px;background:linear-gradient(135deg,#173c6a,#17676c);color:#fff}.hero p,.hero h1,.hero span,.card h2,.card p{margin:0}.hero h1{margin:5px 0 8px}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:18px}.summary article{display:grid;gap:6px;padding:14px;background:#fff;border:1px solid #dce4ef;border-left:5px solid #315bcf;border-radius:12px}.summary span{font-size:12px;color:#68758b}.summary strong{font-size:22px}.summary .good{border-left-color:#168357}.summary .kitting{border-left-color:#d48600}.card header{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:14px}.flow{display:flex;align-items:center;gap:14px;padding:17px;margin:14px 0;background:#edf8f7;border-radius:11px}.flow strong{font-size:20px;color:#126369}.flow em{font-style:normal;color:#5c6d80}.config{border-left:5px solid #d48600}.config-grid{display:grid;grid-template-columns:1fr 2fr;gap:12px;margin:14px 0}.config-grid article{padding:14px;background:#f6f8fc;border-radius:10px}.config-grid p{margin-top:8px;line-height:1.7}.alias{border-left:5px solid #168357}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e3e9f1;text-align:left}.boundary{display:flex;justify-content:space-between;background:#fff8e6}.error{color:#a6241c}@media(max-width:800px){.page{padding:10px}.hero,.card header,.boundary{align-items:flex-start;flex-direction:column}.config-grid{grid-template-columns:1fr}.flow{flex-wrap:wrap}}
</style>
