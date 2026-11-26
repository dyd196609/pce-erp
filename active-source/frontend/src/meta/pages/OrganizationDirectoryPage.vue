<template>
  <main class="organization-directory" data-page-code="organization-directory-v1"
    :data-action-code="ACTION_CODE" data-fact-source="server">
    <header class="directory-heading">
      <div>
        <p>PCE 公共组织身份权限核心 V1 · 低风险只读试点</p>
        <h1>组织目录</h1>
        <span>页面只声明业务动作并消费服务端 Permission Profile；不维护组织、不推进流程、不写采购数据。</span>
      </div>
      <PceBusinessStatus status-code="READ_ONLY" status-label="只读目录" source="server" />
    </header>

    <el-alert v-if="loadError" :title="loadError" type="error" :closable="false" show-icon />
    <el-alert v-else-if="!permissionFact.executable"
      :title="permissionFact.disabledReason" type="warning" :closable="false" show-icon />
    <el-alert v-else title="统一授权已通过；以下组织事实来自服务端正式 Company / Department / Position。"
      type="success" :closable="false" show-icon />

    <section class="authorization-chain" data-acceptance-id="authorization-chain">
      <h2>权限运行链</h2>
      <div>
        <span>业务动作：<strong>{{ ACTION_CODE }}</strong></span>
        <span>公共 Runtime：<strong>{{ runtimeVersion }}</strong></span>
        <span>角色：<strong>{{ profile.roles?.join('、') || '无' }}</strong></span>
        <span>Scope：<strong>{{ profile.scopeCodes?.join('、') || '无' }}</strong></span>
        <span>最终决定：<strong>{{ authorization.allowed ? 'ALLOW' : 'DENY' }}</strong></span>
      </div>
      <p>{{ authorization.reason || permissionFact.disabledReason }}</p>
    </section>

    <section class="directory-list">
      <PceEnterpriseListTable
        ref="tableRef" :contract="enterpriseListContract" page-id="organization-directory-v1"
        table-id="organization-directory-table" :rows="rows" :table-rows="filteredRows"
        :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch"
        :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount" :sort-text="sortText"
        primary-field="code" primary-label="部门编码" primary-width="190"
        min-width="1160px" :show-refresh="true" :refreshing="loading" :show-actions="false"
        @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
        @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
        @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
        @update-filter="updateFilter" @selection-change="selectedRows=$event" @refresh="refresh"
      >
        <template #columns>
          <el-table-column prop="name" label="部门名称" width="200" />
          <el-table-column prop="companyName" label="所属公司" width="240" />
          <el-table-column prop="parentName" label="上级部门" width="180" />
          <el-table-column prop="manager" label="负责人" width="160" />
          <el-table-column prop="positionCount" label="岗位数量" width="120" />
          <el-table-column prop="statusLabel" label="组织记录状态" width="110" />
        </template>
      </PceEnterpriseListTable>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { accessControlApi } from '@/api/accessControl.js'
import {
  PCE_PERMISSION_PROFILE_RUNTIME_VERSION,
  loadPermissionProfile,
  resolvePermissionFact,
} from '@/meta/runtime/permissionProfileRuntime.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'

const ACTION_CODE = 'system.organization_directory.view'
const runtimeVersion = PCE_PERMISSION_PROFILE_RUNTIME_VERSION
const loading = ref(false)
const loadError = ref('')
const rows = ref([])
const profile = reactive({ roles: [], scopeCodes: [], permissionCodes: [], actionFacts: {} })
const authorization = reactive({ allowed: false, reason: '尚未完成服务端授权判断。' })
const permissionFact = computed(() => resolvePermissionFact(profile, ACTION_CODE))
const filterSchema = [
  { field: 'code', label: '部门编码', filterType: 'text' },
  { field: 'name', label: '部门名称', filterType: 'text' },
  { field: 'companyName', label: '所属公司', filterType: 'text' },
  { field: 'parentName', label: '上级部门', filterType: 'text' },
]
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'organization-directory-v1', pageType: 'list',
  title: '组织目录', moduleCode: 'SYSTEM',
})
const listRuntime = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'organization-directory-v1',
  searchFields: ['code', 'name', 'companyName', 'parentName', 'manager'],
  exportFileName: 'organization-directory.csv',
  exportColumns: [
    { field: 'code', label: '部门编码' }, { field: 'name', label: '部门名称' },
    { field: 'companyName', label: '所属公司' }, { field: 'parentName', label: '上级部门' },
  ],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, exportCurrent,
} = listRuntime
function updateFilter(field, value) { filters[field] = value }

async function refresh() {
  loading.value = true
  loadError.value = ''
  rows.value = []
  try {
    const loadedProfile = await loadPermissionProfile({ force: true })
    Object.assign(profile, loadedProfile)
    if (!permissionFact.value.executable) {
      authorization.allowed = false
      authorization.reason = permissionFact.value.disabledReason
      return
    }
    const response = await accessControlApi.organizationDirectory()
    if (!response?.success) throw new Error(response?.error?.message || '组织目录读取失败。')
    Object.assign(authorization, response.data.authorization || {})
    rows.value = response.data.rows || []
  } catch (error) {
    loadError.value = error?.message || String(error)
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<style scoped>
.organization-directory{display:grid;gap:16px;padding:22px;background:#f4f7fb;min-width:0}
.directory-heading{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px;background:#fff;border:1px solid #dce5ef;border-radius:10px}
.directory-heading p,.directory-heading h1,.directory-heading span,.authorization-chain h2,.authorization-chain p{margin:0}
.directory-heading p{color:#2563eb;font-weight:800}.directory-heading h1{margin:6px 0;font-size:28px}
.directory-heading span,.authorization-chain p{color:#64748b}.authorization-chain,.directory-list{padding:16px;background:#fff;border:1px solid #dce5ef;border-radius:10px;min-width:0}
.authorization-chain{display:grid;gap:10px}.authorization-chain div{display:flex;flex-wrap:wrap;gap:12px}.authorization-chain span{padding:8px 10px;background:#f8fafc;border-radius:8px}
@media(max-width:720px){.directory-heading{align-items:flex-start;flex-direction:column}}
</style>
