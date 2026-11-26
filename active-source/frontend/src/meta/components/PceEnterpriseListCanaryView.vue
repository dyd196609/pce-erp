<template>
  <section
    class="pce-enterprise-canary-view"
    data-acceptance-id="enterprise-canary-list-view"
    data-canary="true"
    :data-page-code="pageCode"
    :data-list-data-mode="facts?.dataMode || ''"
  >
    <header>
      <h2>{{ pageTitle }}业务列表</h2>
      <p>金丝雀模式使用独立只读 Provider；正式业务页面组件不会挂载，也不会调用普通业务 API。</p>
    </header>
    <p v-if="loading" data-acceptance-id="enterprise-canary-list-loading">正在加载金丝雀验收数据…</p>
    <p v-else-if="errorMessage" class="error" data-acceptance-id="enterprise-canary-list-error">{{ errorMessage }}</p>
    <template v-else-if="facts">
      <PceEnterpriseListCanaryCard :facts="facts" />
      <PceEnterpriseListTable
        ref="tableRef"
        :contract="enterpriseListContract"
        :page-id="`${pageCode}-canary`"
        :table-id="`${pageCode}-canary-table`"
        :rows="rows"
        :table-rows="filteredRows"
        :filter-schema="filterSchema"
        :filters="filters"
        :quick-search="quickSearch"
        :advanced-visible="advancedVisible"
        :selected-count="selectedRows.length"
        :active-filter-count="activeFilterCount"
        :sort-text="sortText"
        primary-field="objectNo"
        primary-label="对象编号"
        :primary-width="220"
        min-width="1320px"
        :show-action-column="false"
        data-source-mode="canary_acceptance"
        @update:quick-search="quickSearch = $event"
        @search="appliedSearch = quickSearch"
        @toggle-advanced="advancedVisible = !advancedVisible"
        @clear-filters="clearFilters"
        @clear-sort="clearSort"
        @export-current="exportCurrent"
        @clear-selection="clearSelection"
        @update-filter="(field, value) => filters[field] = value"
        @selection-change="selectedRows = $event"
        @sort-change="handleSort"
      >
        <template #columns>
          <el-table-column prop="scenarioCode" label="场景" width="200" />
          <el-table-column prop="currentNode" label="当前节点" width="180" />
          <el-table-column prop="nextNode" label="下一节点" width="180" />
          <el-table-column prop="sourceObjectNo" label="来源对象" width="190" />
          <el-table-column prop="targetObjectNo" label="目标对象" width="190" />
          <el-table-column label="业务状态" width="150">
            <template #default="{ row }">
              <PceBusinessStatus :status-code="row.statusCode" :status-label="row.statusLabel" source="server" />
            </template>
          </el-table-column>
          <el-table-column prop="dataType" label="数据来源" width="180" />
        </template>
      </PceEnterpriseListTable>
    </template>
  </section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PceBusinessStatus from './PceBusinessStatus.vue'
import PceEnterpriseListCanaryCard from './PceEnterpriseListCanaryCard.vue'
import PceEnterpriseListTable from './PceEnterpriseListTable.vue'
import { loadEnterpriseListCanaryFacts } from '../runtime/enterpriseListCanaryDataProvider.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '../runtime/pceEnterpriseListContract.js'

const props = defineProps({
  pageCode: { type: String, required: true },
  pageTitle: { type: String, required: true },
})
const route = useRoute()
const facts = ref(null)
const rows = ref([])
const loading = ref(false)
const errorMessage = ref('')
const filterSchema = Object.freeze([
  { field: 'scenarioCode', label: '场景', filterType: 'text' },
  { field: 'currentNode', label: '当前节点', filterType: 'text' },
  { field: 'dataType', label: '数据来源', filterType: 'select', options: [{ label: '金丝雀验收', value: 'canary_acceptance' }] },
])
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: `${props.pageCode}-canary`,
  pageType: 'list',
  title: `${props.pageTitle}金丝雀验收列表`,
  moduleCode: 'SCM_CANARY_ACCEPTANCE',
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort,
  clearSelection, handleSort, exportCurrent,
} = usePceEnterpriseListRuntime({
  rows,
  filterSchema,
  pageCode: `${props.pageCode}-canary`,
  searchFields: ['objectNo', 'scenarioCode', 'currentNode', 'nextNode'],
  exportFileName: `${props.pageCode}-canary.csv`,
  exportColumns: [
    { field: 'objectNo', label: '对象编号' },
    { field: 'scenarioCode', label: '场景' },
    { field: 'currentNode', label: '当前节点' },
    { field: 'nextNode', label: '下一节点' },
    { field: 'statusLabel', label: '业务状态' },
  ],
})

async function load() {
  loading.value = true
  errorMessage.value = ''
  try {
    facts.value = await loadEnterpriseListCanaryFacts(props.pageCode, route.query)
    rows.value = facts.value?.objects || []
  } catch (error) {
    facts.value = null
    rows.value = []
    errorMessage.value = error?.message || '金丝雀验收数据加载失败'
  } finally {
    loading.value = false
  }
}

watch(
  () => [route.query.canaryBatchId, route.query.scenarioCode, props.pageCode],
  load,
  { immediate: true },
)
</script>

<style scoped>
.pce-enterprise-canary-view {
  display: grid;
  gap: 14px;
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
  background: #fff;
}
.pce-enterprise-canary-view h2,
.pce-enterprise-canary-view p { margin: 0; }
.pce-enterprise-canary-view header { display: grid; gap: 6px; }
.error { color: #b91c1c; }
</style>
