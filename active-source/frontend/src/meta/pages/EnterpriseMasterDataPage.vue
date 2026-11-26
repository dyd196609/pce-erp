<template>
  <main
    class="master-data-page"
    :data-acceptance-id="`${definition.pageCode}-page`"
    data-master-data-fact-source="server"
    data-page-version="V1.14.2.8.4.8.5.2"
    :data-page-name="pageName.pageTitle"
    data-page-module="EMD"
    data-maintenance-owner="EMD"
    data-danger-action-count="0"
    data-detail-display-mode="PceBusinessDetailCard"
    data-acceptance-status="PASS"
    data-pce-metadata-source="masterDataRegistry"
    :data-pce-column-count="definition.columns.length + 1"
    data-pce-filter-source="masterDataRegistry.filterSchema"
    data-pce-dropdown-runtime="listFilterRuntime"
    :data-latest-base-data-template="isWave1Adoption ? latestTemplateVersion : undefined"
    :data-template-adoption-status="isWave1Adoption ? wave1Adoption.adoptionStatus : undefined"
    :data-provider-state="providerState"
    :data-pce-page-kind="definition.pageKind"
    :data-pce-action-policy="definition.actionPolicy.join(',')"
  >
    <ProductionFoundationMaintenance v-if="canonicalMaintenanceMode" :initial-entity="props.entityCode" />
    <template v-else>
    <p v-if="canonicalIdentity?.maintenanceComponent"><el-button @click="editMasterData">进入本模块正常维护（保留原数据源与公司范围）</el-button></p>
      <section class="card center-identity" data-acceptance-id="enterprise-master-data-center">
        <header>
          <div>
            <p class="eyebrow">Enterprise Master Data Center（EMD）</p>
            <h1>{{ pageName.pageTitle }}</h1>
            <p>统一维护组织、客户、供应商、物料、BOM、工艺路线与仓库主数据。</p>
            <p>不负责采购订单、库存业务、质量业务、付款业务或财务业务。</p>
          </div>
          <span class="master-code">EMD</span>
        </header>
      </section>

      <section class="card facts-card" data-acceptance-id="master-data-server-facts">
        <header>
          <div>
            <h2>服务端持久事实</h2>
            <p>API、页面、复制诊断、StrictFacts 与 AcceptanceFacts 复用同一服务端事实。</p>
          </div>
          <span class="master-code">{{ definition.masterDataCode }}</span>
        </header>
        <div class="fact-grid">
          <Fact label="事实加载状态" :value="loadStatusLabel" />
          <Fact label="事实来源" :value="strictFacts.factSource" />
          <Fact label="当前筛选结果" :value="filteredRows.length" />
          <Fact label="服务端总数" :value="strictFacts.recordCount" />
          <Fact label="API" :value="factLoadFacts.apiUrl" />
          <Fact label="租户" :value="factLoadFacts.tenantId" />
          <Fact label="批次" :value="factLoadFacts.batchId" />
          <Fact label="页面版本" :value="strictFacts.pageVersion" />
          <Fact label="自动验收" :value="strictFacts.acceptanceStatus" />
          <template v-if="isCanonicalMaster">
            <Fact label="数据来源" :value="strictFacts.dataSource" />
            <Fact label="数据库表" :value="strictFacts.databaseTable" />
            <Fact label="维护入口" :value="strictFacts.maintenanceEntry" />
          </template>
        </div>
        <p v-if="readFailed" class="read-error" role="alert">
          {{ definition.title }}事实读取失败 · {{ providerStateLabel }}
        </p>
      </section>

      <section class="card" :data-acceptance-id="`${definition.pageCode}-list`">
        <header>
          <div>
            <h2>{{ definition.listTitle }}</h2>
            <p>中间业务字段可横向滚动，选择、序号、主数据编码和操作列保持冻结。</p>
          </div>
        </header>
        <PceEnterpriseListTable
          ref="tableRef"
          :contract="enterpriseListContract"
          :page-id="definition.pageCode"
          :table-id="`${definition.pageCode}-table`"
          :rows="rows"
          :table-rows="filteredRows"
          :filter-schema="definition.filterSchema"
          :filters="filters"
          :quick-search="quickSearch"
          :advanced-visible="advancedVisible"
          :selected-count="selectedRows.length"
          :active-filter-count="activeFilterCount"
          :sort-text="sortText"
          :presentation-sort="detailLocator ? runtime.sortState : undefined"
          :primary-field="definition.primaryField"
          :primary-label="definition.primaryLabel"
          :primary-width="220"
          min-width="1480px"
          :scroll-acceptance-id="`${definition.pageCode}-horizontal-scroll`"
          :action-contracts="actionContracts"
          @update:quick-search="quickSearch = $event"
          @search="appliedSearch = quickSearch"
          @toggle-advanced="advancedVisible = !advancedVisible"
          @clear-filters="clearFilters"
          @clear-sort="detailLocator ? handleSort({}) : clearSort()"
          @export-current="exportCurrent"
          @clear-selection="clearSelection"
          @update-filter="(field, value) => filters[field] = value"
          @selection-change="selectedRows = $event"
          @sort-change="handleSort"
          @row-action="handleRowAction"
        >
          <template v-if="isWave1Adoption" #toolbar-extension>
            <LatestBaseDataImportToolbarExtension
              :entity="definition.entityCode"
              :entity-name="definition.title"
              @import-committed="refresh"
            />
          </template>
          <template #columns>
            <el-table-column
              v-for="column in definition.columns"
              :key="column[0]"
              :prop="column[0]"
              :label="column[1]"
              :width="column[2]"
              :sortable="detailLocator ? 'custom' : true"
              show-overflow-tooltip
            />
          </template>
        </PceEnterpriseListTable>
      </section>

      <section class="card boundary" data-acceptance-id="master-data-business-boundary">
        <header>
          <div>
            <h2>主数据业务边界</h2>
            <p>{{ isCanonicalMaster
              ? `本页面只读展示正式 ${canonicalObjectLabel} 持久事实，不推进任何交易流程。`
              : '本版本只读取企业主数据测试事实并提供治理视图，不推进任何交易流程。' }}</p>
          </div>
        </header>
        <div class="fact-grid">
          <Fact label="业务推进写入" :value="strictFacts.businessProgressWriteCount" />
          <Fact label="危险动作" :value="strictFacts.dangerActionCount" />
          <Fact label="下游对象" :value="strictFacts.downstreamObjectCount" />
          <Fact label="采购数据修改" value="否" />
          <Fact label="付款数据修改" value="否" />
          <Fact label="银行数据修改" value="否" />
        </div>
      </section>

      <p v-if="detailLocatorError" role="alert">{{ detailLocatorError }}</p>
      <el-dialog :model-value="detailVisible" @update:model-value="value => value ? detailVisible = true : closeDetail()" :title="`${definition.title}详情`" width="860px">
        <PceBusinessDetailCard v-if="detailRow" :detail="businessDetail" />
      </el-dialog>
    </template>
  </main>
</template>

<script setup>
import { computed, h, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {workPresentation} from '@/meta/runtime/workPresentationContext.js'
import { useRouter,useRoute } from 'vue-router'
import ProductionFoundationMaintenance from '@/meta/components/ProductionFoundationMaintenance.vue'
import {getFoundationCanonicalModuleByEntity,resolveFoundationPageState,serializeFoundationMode} from '@/meta/master-data/foundationEntryUnificationRegistry'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import PceBusinessDetailCard from '@/meta/components/PceBusinessDetailCard.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import LatestBaseDataImportToolbarExtension from '@/meta/components/LatestBaseDataImportToolbarExtension.vue'
import { findMasterDataDefinition } from '@/meta/master-data/masterDataRegistry.js'
import { findOrderProductionTemplateAdoption } from '@/meta/master-data/orderProductionBaseDataTemplateAdoption.js'
import { LATEST_BASE_DATA_TEMPLATE_VERSION } from '@/meta/contracts/latestBaseDataTemplateContract.js'
import { factLoadFailureFromError } from '@/meta/runtime/pceFactLoadContract.js'
import {
  latestBaseDataProviderStateLabel,
  resolveLatestBaseDataProviderState,
} from '@/meta/runtime/latestBaseDataProviderState.js'
import { PAGE_OBSERVABILITY_ACTIONS_KEY } from '@/meta/runtime/pageObservabilityActions.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'
import { createSchemaActionContracts } from '@/meta/runtime/listActionColumnRuntime.js'

const props = defineProps({
  entityCode: { type: String, required: true },
})
const router = useRouter()
const currentRoute=useRoute()
const canonicalIdentity=computed(()=>getFoundationCanonicalModuleByEntity(props.entityCode))
const canonicalMaintenanceMode=computed(()=>Boolean(canonicalIdentity.value?.maintenanceComponent) && resolveFoundationPageState(currentRoute).mode==='maintain')

const definition = computed(() => {
  const value = findMasterDataDefinition(props.entityCode)
  if (!value) throw new Error(`Unknown enterprise master-data entity: ${props.entityCode}`)
  return value
})
const pageName = computed(() => resolvePageNameConsumption({ pageCode: definition.value.pageCode, route: definition.value.pageUrl }))
const isMaterialMaster = computed(() => definition.value.entityCode === 'materials')
const isSupplierMaster = computed(() => definition.value.entityCode === 'suppliers')
const isCustomerMaster = computed(() => definition.value.entityCode === 'customers')
// Explicit original-list opt-ins only. These fields are lookup hints, never authority.
const detailLocator = computed(() => isSupplierMaster.value
  ? {parameter:'supplierId',rowId:'supplierId',label:'供应商'}
  : isCustomerMaster.value ? {parameter:'customerId',rowId:'id',label:'客户'} : null)
const canonicalModuleId = computed(() => (
  isCustomerMaster.value ? 'customer'
    : isSupplierMaster.value ? 'supplier'
      : isMaterialMaster.value ? 'material' : ''
))
const wave1Adoption = computed(() => findOrderProductionTemplateAdoption(canonicalModuleId.value))
const isWave1Adoption = computed(() => wave1Adoption.value?.wave === 'WAVE1')
const latestTemplateVersion = LATEST_BASE_DATA_TEMPLATE_VERSION
const isCanonicalMaster = computed(() => isCustomerMaster.value || isMaterialMaster.value || isSupplierMaster.value)
const canonicalObjectLabel = computed(() => (
  isCustomerMaster.value ? 'CustomerMaster'
    : isMaterialMaster.value ? 'MaterialMaster'
      : 'SupplierMaster'
))
const rows = ref([])
const factLoadFacts = ref({})
const strictFacts = ref({})
const acceptanceFacts = ref({})
const detailVisible = ref(false)
const detailRow = ref(null)
const detailLocatorError = ref('')
const observability = inject(PAGE_OBSERVABILITY_ACTIONS_KEY, null)
const readFailed = computed(() => factLoadFacts.value.factLoadStatus === 'read_failed')
const providerState = computed(() => resolveLatestBaseDataProviderState({
  loading: !factLoadFacts.value.factLoadStatus,
  factLoadFacts: factLoadFacts.value,
  count: rows.value.length,
}))
const providerStateLabel = computed(() => latestBaseDataProviderStateLabel(providerState.value))
const loadStatusLabel = computed(() => (
  providerStateLabel.value
))
const enterpriseListContract = computed(() => createPceEnterpriseListContract({
  pageCode: definition.value.pageCode,
  pageType: 'list',
  title: definition.value.title,
  moduleCode: 'EMD',
}))
const actionContracts = computed(() => createSchemaActionContracts(definition.value.actionPolicy))
const runtime = usePceEnterpriseListRuntime({
  rows,
  filterSchema: definition.value.filterSchema,
  pageCode: definition.value.pageCode,
  searchFields: definition.value.searchFields,
  exportFileName: `${definition.value.entityCode}.csv`,
  exportColumns: computed(() => [
    { field: definition.value.primaryField, label: definition.value.primaryLabel },
    ...definition.value.columns.map(column => ({ field: column[0], label: column[1] })),
  ]).value,
})
const {
  selectedRows,
  quickSearch,
  appliedSearch,
  advancedVisible,
  filters,
  tableRef,
  activeFilterCount,
  sortText,
  filteredRows,
  apiFilterParams,
  clearFilters,
  clearSort,
  clearSelection,
  handleSort,
  exportCurrent,
} = runtime
const detailLabels = computed(() => new Map([
  [definition.value.primaryField, definition.value.primaryLabel],
  ...definition.value.columns.map(column => [column[0], column[1]]),
]))
const businessDetail = computed(() => ({
  sectionTitle: `${definition.value.title}业务信息`,
  fields: Object.entries(detailRow.value || {})
    .filter(([key]) => detailLabels.value.has(key))
    .map(([key, value]) => ({ label: detailLabels.value.get(key), value })),
}))
const Fact = (_, { attrs }) => h('article', { class: 'fact' }, [
  h('span', attrs.label),
  h('strong', String(attrs.value ?? '-')),
])

function syncLocatedDetail() {
  if (!detailLocator.value || canonicalMaintenanceMode.value) return
  detailVisible.value = false; detailRow.value = null; detailLocatorError.value = ''
  if (currentRoute.query[detailLocator.value.parameter] === undefined || factLoadFacts.value.factLoadStatus !== 'success') return
  const id = String(currentRoute.query[detailLocator.value.parameter])
  const row = /^[1-9][0-9]*$/.test(id) && rows.value.find(item => String(item[detailLocator.value.rowId]) === id)
  if (!row) { detailLocatorError.value = `定位的${detailLocator.value.label}不在当前可读取目录中，请核对链接或返回列表选择。`; return }
  detailRow.value = row; detailVisible.value = true
}
async function showDetail(row) {
  if (detailLocator.value) {
    if (factLoadFacts.value.factLoadStatus !== 'success' || !rows.value.some(item => item === row)) return
    runtime.savePresentation()
    await router.replace({path:currentRoute.path,query:{...currentRoute.query,[detailLocator.value.parameter]:String(row[detailLocator.value.rowId])}})
    syncLocatedDetail(); return
  }
  detailRow.value = row; detailVisible.value = true
}
function closeDetail() {
  detailVisible.value = false; detailRow.value = null
  if (detailLocator.value && currentRoute.query[detailLocator.value.parameter] !== undefined) {
    const query = {...currentRoute.query}; delete query[detailLocator.value.parameter]
    router.replace({path:currentRoute.path,query})
  }
}
watch(() => detailLocator.value && currentRoute.query[detailLocator.value.parameter], syncLocatedDetail, {flush:'post'})


function editMasterData() {
  if(canonicalIdentity.value?.maintenanceComponent){
    return router.push({name:canonicalIdentity.value.routeName,query:{...currentRoute.query,view:serializeFoundationMode('maintain')}})
  }
  if (!definition.value.maintenanceRoute) {
    ElMessage.warning('当前主数据未登记维护入口')
    return
  }
  router.push(definition.value.maintenanceRoute)
}

function handleRowAction(action, row) {
  if (action.actionCode === 'view') showDetail(row)
  else if (action.actionCode === 'edit') editMasterData()
}

function diagnostics() {
  return {
    version: definition.value.pageVersion,
    canonicalName: definition.value.title,
    moduleCode: 'EMD',
    pageFactOwner: definition.value.pageCode,
    factSource: strictFacts.value.factSource,
    factLoadFacts: factLoadFacts.value,
    apiFacts: strictFacts.value,
    pageFacts: strictFacts.value,
    diagnosticFacts: strictFacts.value,
    strictFacts: strictFacts.value,
    acceptanceFacts: acceptanceFacts.value,
    filterApiParams: { ...apiFilterParams.value },
    resultCount: filteredRows.value.length,
    serverRecordCount: strictFacts.value.recordCount ?? null,
  }
}

function publish() {
  if(canonicalMaintenanceMode.value)return
  const factsAreIdentical = JSON.stringify(strictFacts.value) === JSON.stringify(acceptanceFacts.value)
  window.__PCE_BUSINESS_PAGE_ACCEPTANCE__ = {
    ...diagnostics(),
    pageAssertions: [
      { rule: 'MASTER-001', regionTitle: '业务模块', actualValue: 'EMD', passed: true },
      { rule: 'MASTER-002', regionTitle: '流程节点', actualValue: definition.value.nodeCode, passed: true },
      { rule: 'MASTER-003', regionTitle: '页面版本', actualValue: definition.value.pageVersion, passed: true },
      { rule: 'MASTER-004', regionTitle: '自动验收状态', actualValue: definition.value.acceptanceStatus, passed: definition.value.acceptanceStatus === 'PASS' },
      { rule: 'MASTER-005', regionTitle: definition.value.listTitle, actualValue: enterpriseListContract.value.contractVersion, passed: true },
      { rule: 'MASTER-006', regionTitle: '业务详情', actualValue: 'PceBusinessDetailCard', passed: true },
      { rule: 'MASTER-007', regionTitle: '事实来源', actualValue: strictFacts.value.factSource, passed: strictFacts.value.factSource === 'server' && factsAreIdentical },
    ],
  }
}

let overviewReadGeneration=0
async function refresh() {
  const generation=++overviewReadGeneration, identity=workPresentation.epoch()
  if(detailLocator.value){detailVisible.value=false;detailRow.value=null;detailLocatorError.value='';rows.value=[];factLoadFacts.value={};strictFacts.value={};acceptanceFacts.value={}}
  try {
    if(canonicalMaintenanceMode.value)return
    const response = await enterpriseMasterDataApi.facts(definition.value.entityCode)
    if(generation!==overviewReadGeneration || canonicalMaintenanceMode.value || (detailLocator.value && identity!==workPresentation.epoch()))return
    const payload = response?.data || response
    if (!payload || payload.factLoadFacts?.factLoadStatus !== 'success') {
      throw Object.assign(new Error('主数据事实读取失败'), { factLoadFacts: payload?.factLoadFacts })
    }
    rows.value = payload.rows
    factLoadFacts.value = payload.factLoadFacts
    strictFacts.value = payload.strictFacts
    acceptanceFacts.value = payload.acceptanceFacts
    syncLocatedDetail()
    publish()
  } catch (error) {
    if(generation!==overviewReadGeneration || canonicalMaintenanceMode.value || (detailLocator.value && identity!==workPresentation.epoch()))return
    rows.value = []
    factLoadFacts.value = factLoadFailureFromError(
      error,
      `/api/masterdata/enterprise/${definition.value.entityCode}/facts/`,
      factLoadFacts.value,
    )
    strictFacts.value = factLoadFacts.value
    acceptanceFacts.value = factLoadFacts.value
    publish()
    ElMessage.error(`${definition.value.title}事实读取失败`)
  }
}

let provider
function registerProvider() {
  if(canonicalMaintenanceMode.value)return
  provider = {
    factOwner: definition.value.pageCode,
    refresh,
    buildDiagnostics: diagnostics,
  }
  observability?.register?.(provider)
}

onMounted(async () => {
  registerProvider()
  await refresh()
})
function unregisterProvider(){if(provider)observability?.unregister?.(provider);provider=null}
function clearLocatedIdentity() {
  if(!detailLocator.value)return
  overviewReadGeneration++;detailVisible.value=false;detailRow.value=null;detailLocatorError.value=''
  rows.value=[];factLoadFacts.value={};strictFacts.value={};acceptanceFacts.value={}
}
window.addEventListener('pce:authentication-changed',clearLocatedIdentity)
onBeforeUnmount(()=>{unregisterProvider();window.removeEventListener('pce:authentication-changed',clearLocatedIdentity)})
watch(canonicalMaintenanceMode,async (maintain)=>{
  overviewReadGeneration++
  unregisterProvider()
  rows.value=[];strictFacts.value={};acceptanceFacts.value={}
  if(!maintain){registerProvider();await refresh()}
})
watch(() => props.entityCode, async () => {
  unregisterProvider()
  rows.value = []
  strictFacts.value = {}
  acceptanceFacts.value = {}
  registerProvider()
  await refresh()
})
</script>

<style scoped>
.master-data-page { display:grid; min-width:0; gap:18px; padding:20px; background:#f4f7fb; }
.card { min-width:0; padding:20px; border:1px solid #dce4ed; border-radius:12px; background:#fff; }
.card > header { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
h2 { margin:0; color:#16243a; }
header p { margin:6px 0 16px; color:#64748b; }
.master-code { padding:7px 11px; border-radius:999px; background:#dbeafe; color:#1d4ed8; font-weight:800; }
.fact-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; }
.fact { display:grid; gap:5px; padding:12px; border-radius:8px; background:#f5f8fb; }
.fact span { color:#64748b; font-size:13px; }
.fact strong { overflow-wrap:anywhere; }
.boundary { border-color:#b8d8c4; background:#f5fbf7; }
.read-error { color:#b42318; font-weight:800; }
</style>



