<template>
  <PceListPageShell
    module-id="master-data-executor-preview"
    :governance="governance"
    :page-refresh-handler="load"
    :page-refresh-status="refreshStatus"
    :page-last-refresh-time="lastRefreshTime"
  >
    <div
      class="executor-preview"
      data-acceptance-id="master-data-executor-preview"
      data-read-only="true"
      data-production-business-write-count="0"
    >
      <section class="hero">
        <div>
          <p>EMPLOYEE → POSITION → RESPONSIBILITY</p>
          <h2>基础资料执行人确认</h2>
          <span>选择仅保存在当前页面，不会绑定账号、创建职责或写入正式数据。</span>
        </div>
        <strong>{{ facts.status || '正在读取……' }}</strong>
      </section>

      <section v-if="loading" class="panel">正在读取正式员工、岗位、账号与职责事实……</section>
      <section v-else-if="error" class="panel error">{{ error }}</section>
      <template v-else>
        <section class="summary-grid">
          <article><span>可用在职员工</span><strong>{{ facts.summary.eligibleEmployeeCount }}</strong></article>
          <article><span>已有实名业务账号</span><strong>{{ facts.summary.activeBusinessAccountCount }}</strong></article>
          <article class="warn"><span>BUSINESS ACCOUNT MISSING</span><strong>{{ facts.summary.missingBusinessAccountCount }}</strong></article>
          <article class="danger"><span>等价正式职责</span><strong>{{ facts.summary.existingEquivalentResponsibilityCount }}</strong></article>
          <article><span>正式业务写入</span><strong>0</strong></article>
        </section>

        <section class="panel technical-account">
          <div>
            <h3>admin 保持技术账号</h3>
            <p>{{ facts.technicalAdministrator.accountType }}</p>
          </div>
          <PceBusinessStatus
            :status-code="facts.technicalAdministrator.keptUnlinked ? 'UNLINKED' : 'REVIEW'"
            :status-label="facts.technicalAdministrator.keptUnlinked ? '未绑定员工' : '需复核'"
          />
        </section>

        <section class="panel">
          <header>
            <div>
              <h3>MASTER_DATA_EXECUTOR_CANDIDATES</h3>
              <p>仅含在职、正式部门启用、正式岗位启用、当前有效且未命中测试/验收标识的员工。</p>
            </div>
            <strong>PENDING USER DECISION</strong>
          </header>
          <PceEnterpriseListTable
            ref="tableRef"
            :contract="enterpriseListContract"
            page-id="master-data-executor-preview"
            table-id="master-data-executor-candidates-table"
            :rows="rows"
            :table-rows="filteredRows"
            row-key="id"
            primary-field="employeeCode"
            primary-label="员工编号"
            :primary-width="150"
            :quick-search="quickSearch"
            :advanced-visible="advancedVisible"
            :filter-schema="filterSchema"
            :filters="filters"
            :selected-count="selectedRows.length"
            :active-filter-count="activeFilterCount"
            :sort-text="sortText"
            :show-refresh="true"
            :refreshing="loading"
            :show-action-column="true"
            :action-width="150"
            min-width="1460px"
            @update:quick-search="quickSearch = $event"
            @search="appliedSearch = quickSearch"
            @toggle-advanced="advancedVisible = !advancedVisible"
            @clear-filters="clearFilters"
            @clear-sort="clearSort"
            @clear-selection="clearSelection"
            @export-current="exportCurrent"
            @update-filter="updateFilter"
            @selection-change="selectedRows = $event"
            @refresh="load"
          >
            <template #columns>
              <el-table-column prop="employeeName" label="员工姓名" width="130" show-overflow-tooltip />
              <el-table-column prop="departmentName" label="部门" width="150" show-overflow-tooltip />
              <el-table-column prop="positionName" label="当前有效岗位" width="150" show-overflow-tooltip />
              <el-table-column prop="employmentStatus" label="在职状态" width="100" />
              <el-table-column prop="businessUsername" label="现有业务账号" width="170">
                <template #default="{ row }">{{ row.businessUsername || '无' }}</template>
              </el-table-column>
              <el-table-column prop="businessAccountStatus" label="账号状态" width="190">
                <template #default="{ row }">
                  <span :class="['pill', row.businessAccountStatus === 'ACTIVE' ? 'ok' : 'warn']">
                    {{ row.businessAccountStatus }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column prop="responsibilityText" label="现有岗位职责" min-width="260" show-overflow-tooltip />
              <el-table-column prop="businessAccountPreview" label="账号方案 Preview" width="190" show-overflow-tooltip />
              <el-table-column prop="proposedResponsibility" label="拟职责" width="180" />
            </template>
            <template #actions="{ row }">
              <el-button link type="primary" @click="selectCandidate(row)">选择为本地预览</el-button>
            </template>
          </PceEnterpriseListTable>
        </section>

        <section v-if="selectedCandidate" class="panel selected-preview">
          <header><div><h3>当前本地选择</h3><p>尚未提交，刷新页面即清除。</p></div><strong>PREVIEW ONLY</strong></header>
          <div class="decision-grid">
            <span>员工：<strong>{{ selectedCandidate.employeeCode }} / {{ selectedCandidate.employeeName }}</strong></span>
            <span>部门：<strong>{{ selectedCandidate.departmentName }}</strong></span>
            <span>岗位：<strong>{{ selectedCandidate.positionName }}</strong></span>
            <span>业务账号：<strong>{{ selectedCandidate.businessAccountPreview }}</strong></span>
            <span>拟职责：<strong>{{ selectedCandidate.proposedResponsibility }}</strong></span>
          </div>
        </section>

        <section class="panel responsibility-preview">
          <header>
            <div><h3>{{ responsibility.code }}</h3><p>{{ responsibility.name }}</p></div>
            <strong>{{ responsibility.status }}</strong>
          </header>
          <p><b>正式关系：</b>{{ responsibility.bindingModel }}</p>
          <div class="scope-columns">
            <article><h4>允许维护对象</h4><ul><li v-for="item in responsibility.allowedBusinessObjects" :key="item">{{ item }}</li></ul></article>
            <article><h4>允许语义</h4><ul><li v-for="item in responsibility.allowedSemantics" :key="item">{{ item }}</li></ul></article>
            <article class="denied"><h4>明确禁止</h4><ul><li v-for="item in responsibility.explicitlyDenied" :key="item">{{ item }}</li></ul></article>
          </div>
          <details><summary>Authorization 动作编码就绪度</summary><ul><li v-for="item in responsibility.actionCodeReadiness" :key="item.code">{{ item.code }} — {{ item.status }}（{{ item.condition }}）</li></ul></details>
        </section>

        <section class="panel stop-point">
          <strong>本轮停止点</strong>
          <span>admin 绑定 0 · 业务账号创建 0 · 岗位职责写入 0 · Group 1 重试 0 · Product Category 写入 0</span>
        </section>
      </template>
    </div>
  </PceListPageShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { accessControlApi } from '@/api/accessControl.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import {
  createPceEnterpriseListContract,
  usePceEnterpriseListRuntime,
} from '@/meta/runtime/pceEnterpriseListContract.js'

const governance = Object.freeze({
  pageCode: 'master-data-executor-preview', version: 'V1', frameworkVersion: 'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',
  purpose: '只读展示可用实名员工、当前岗位、业务账号与最小职责定义，等待一次人工选择。',
  allowed: ['读取正式组织事实', '筛选和导出候选员工', '形成当前页面本地选择'],
  forbidden: ['绑定 admin', '创建业务账号', '创建或分配职责', '重试 Group 1', '进入 Group 2 / Group 3'],
  flowSteps: ['正式组织事实', '执行人候选 Preview', '用户人工确认', '后续最小正式关联'],
  currentFlowStep: '执行人候选 Preview',
  navigation: {
    previous: { label: '岗位与职责体系', pageCode: 'enterprise-position-model-v1', pageUrl: '/organization-model/positions' },
    current: { label: '基础资料执行人确认', pageCode: 'master-data-executor-preview', pageUrl: '/organization/master-data-executor-preview' },
    next: { label: '等待用户人工选择', pageCode: '', pageUrl: '' },
  },
  returnModuleCode: 'SYSTEM',
})
const loading = ref(true)
const error = ref('')
const refreshStatus = ref('idle')
const lastRefreshTime = ref('')
const facts = reactive({
  status: '', summary: {}, technicalAdministrator: {}, rows: [], responsibilityPreview: {}, strictFacts: {},
})
const rows = ref([])
const selectedCandidate = ref(null)
const responsibility = computed(() => facts.responsibilityPreview || {})
const filterSchema = [
  { field: 'employeeName', label: '员工姓名', filterType: 'text' },
  { field: 'departmentName', label: '部门', filterType: 'select' },
  { field: 'positionName', label: '岗位', filterType: 'select' },
  { field: 'businessAccountStatus', label: '业务账号状态', filterType: 'select', options: [
    { label: '已有启用账号', value: 'ACTIVE' },
    { label: '账号未启用', value: 'INACTIVE' },
    { label: '缺少业务账号', value: 'BUSINESS ACCOUNT MISSING' },
  ] },
  { field: 'hasResponsibility', label: '已有岗位职责', filterType: 'select', options: [
    { label: '有', value: true }, { label: '无', value: false },
  ] },
]
const enterpriseListContract = createPceEnterpriseListContract({
  pageCode: 'master-data-executor-preview', pageType: 'list', title: '基础资料执行人确认', moduleCode: 'SYSTEM',
})
const listRuntime = usePceEnterpriseListRuntime({
  rows, filterSchema, pageCode: 'master-data-executor-preview',
  searchFields: ['employeeCode', 'employeeName', 'departmentName', 'positionName', 'businessUsername', 'responsibilityText'],
  exportFileName: 'master-data-executor-candidates.csv',
  exportColumns: [
    { field: 'employeeCode', label: '员工编号' }, { field: 'employeeName', label: '员工姓名' },
    { field: 'departmentName', label: '部门' }, { field: 'positionName', label: '岗位' },
    { field: 'businessUsername', label: '现有业务账号' }, { field: 'businessAccountStatus', label: '账号状态' },
    { field: 'responsibilityText', label: '现有岗位职责' }, { field: 'proposedResponsibility', label: '拟职责' },
  ],
})
const {
  selectedRows, quickSearch, appliedSearch, advancedVisible, filters, tableRef,
  activeFilterCount, sortText, filteredRows, clearFilters, clearSort, clearSelection, exportCurrent,
} = listRuntime
function updateFilter(field, value) { filters[field] = value }
function selectCandidate(row) { selectedCandidate.value = row }

async function load() {
  loading.value = true
  refreshStatus.value = 'refreshing'
  error.value = ''
  selectedCandidate.value = null
  try {
    const response = await accessControlApi.masterDataExecutorPreview()
    if (!response?.success) throw new Error(response?.error?.message || '执行人候选读取失败。')
    Object.assign(facts, response.data || {})
    rows.value = response.data?.rows || []
    refreshStatus.value = 'success'
    lastRefreshTime.value = new Date().toLocaleString('zh-CN', { hour12: false })
  } catch (exception) {
    error.value = exception?.message || String(exception)
    refreshStatus.value = 'error'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.executor-preview{display:grid;gap:16px;color:#17233a}.hero,.panel{padding:18px 20px;border:1px solid #dbe3ef;border-radius:14px;background:#fff}.hero{display:flex;align-items:center;justify-content:space-between;gap:16px;color:#fff;background:linear-gradient(135deg,#173e6e,#2f62c6)}.hero p,.hero h2,.hero span,.panel h3,.panel p{margin:0}.hero h2{margin:5px 0}.hero>strong{max-width:380px;padding:8px 12px;border:1px solid #a8c4ff;border-radius:999px;text-align:center}.summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}.summary-grid article{display:grid;gap:7px;padding:14px;border:1px solid #dbe3ef;border-left:4px solid #2f62c6;border-radius:10px;background:#fff}.summary-grid article.warn{border-left-color:#d97706}.summary-grid article.danger{border-left-color:#c7352b}.summary-grid strong{font-size:22px}.panel header,.technical-account{display:flex;align-items:center;justify-content:space-between;gap:16px}.panel header{margin-bottom:14px}.panel header p{color:#64748b;margin-top:4px}.pill{display:inline-block;padding:3px 8px;border-radius:999px}.pill.ok{color:#12623b;background:#dcfce7}.pill.warn{color:#865700;background:#fff2d5}.selected-preview{border-color:#93c5fd;background:#eff6ff}.decision-grid{display:flex;flex-wrap:wrap;gap:12px}.decision-grid span{padding:8px 10px;border-radius:8px;background:#fff}.responsibility-preview>p{line-height:1.7}.scope-columns{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.scope-columns article{padding:14px;border:1px solid #dbe3ef;border-radius:10px;background:#f8fafc}.scope-columns article.denied{border-color:#fecaca;background:#fff7f7}.scope-columns h4{margin:0 0 8px}.scope-columns ul,details ul{margin:0;padding-left:20px;line-height:1.8}.responsibility-preview details{margin-top:14px}.stop-point{display:flex;justify-content:space-between;gap:14px;border-color:#f3c987;background:#fffaf0}.error{color:#a5221a}@media(max-width:850px){.hero,.panel header,.technical-account,.stop-point{align-items:flex-start;flex-direction:column}.scope-columns{grid-template-columns:1fr}}
</style>
