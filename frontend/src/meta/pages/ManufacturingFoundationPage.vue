<template>
  <main class="foundation-page">
    <header class="page-header">
      <section>
        <p class="eyebrow">V1.11.6 制造业基础资料标准化</p>
        <h1>{{ pageTitle }}</h1>
        <p>基础资料是 SCM、CRM、WMS、MRP、MPS、APS、MES、QMS、BI、KPI、FDM 的统一数据源。本页继续使用 localStorage，不接入后端 API。</p>
      </section>
      <nav class="page-tabs">
        <router-link to="/foundation">基础资料总览</router-link>
        <router-link to="/foundation/pfm/employees">员工档案</router-link>
        <router-link to="/foundation/erp/materials">物料档案</router-link>
        <router-link to="/foundation/sample-data">样例数据</router-link>
        <router-link to="/foundation/review-check">评审检查</router-link>
        <router-link to="/foundation/import-records">导入记录</router-link>
        <router-link to="/reference">数据引用中心</router-link>
        <router-link to="/manufacturing/modules">制造业模块蓝图</router-link>
      </nav>
    </header>

    <section v-if="message" class="notice">{{ message }}</section>

    <section v-if="route.path === '/foundation'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>基础资料总览</h2>
            <span>数据来源：manufacturing-foundation-state-v1</span>
          </div>
          <div class="button-row">
            <button type="button" @click="resetDemoData">恢复默认演示数据</button>
            <button type="button" @click="router.push('/foundation/review-check')">基础资料评审检查</button>
            <button type="button" @click="router.push('/foundation/import-records')">导入记录</button>
          </div>
        </header>
        <div class="summary-grid">
          <article v-for="card in summaryCards" :key="card.title">
            <span>{{ card.title }}</span>
            <strong>{{ card.value }}</strong>
            <p>{{ card.desc }}</p>
            <button type="button" @click="router.push(card.to)">进入维护</button>
          </article>
        </div>
      </section>

      <section class="panel">
        <header>
          <h2>常用基础资料入口</h2>
          <span>本轮只做基础资料能力收敛，不新增业务 CRUD。</span>
        </header>
        <div class="entry-grid">
          <button v-for="entry in foundationEntries" :key="entry.to" type="button" @click="router.push(entry.to)">
            {{ entry.label }}
          </button>
        </div>
      </section>
    </section>

    <section v-else-if="route.path === '/foundation/sample-data'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>样例数据管理</h2>
            <span>生成印刷行业与全屋定制/整木行业的大规模演示基础资料。</span>
          </div>
          <button type="button" @click="router.push('/foundation')">返回基础资料</button>
        </header>
        <div class="summary-grid">
          <article v-for="card in sampleDataCards" :key="card.title">
            <span>{{ card.title }}</span>
            <strong>{{ card.value }}</strong>
            <p>{{ card.desc }}</p>
          </article>
        </div>
        <div class="button-row">
          <button type="button" @click="generateSampleDataWithConfirm">生成制造业样例数据</button>
          <button type="button" @click="resetSampleDataWithConfirm">重置并重新生成样例数据</button>
        </div>
      </section>
    </section>

    <section v-else-if="route.path === '/foundation/review-check'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>基础资料评审检查</h2>
            <span>数据来源：manufacturing-foundation-state-v1</span>
          </div>
          <div class="button-row">
            <button type="button" @click="refresh">刷新检查结果</button>
            <button type="button" @click="exportReviewCsv">导出 CSV</button>
            <button type="button" @click="router.push('/foundation')">返回总览</button>
          </div>
        </header>
        <div class="table-card">
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th>评审项目</th>
                <th>检查标准</th>
                <th>当前结果</th>
                <th>验收结果</th>
                <th>建议处理页面</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in reviewRows" :key="row.index">
                <td>{{ row.index }}</td>
                <td>{{ row.item }}</td>
                <td>{{ row.standard }}</td>
                <td>{{ row.result }}</td>
                <td><span :class="['status-pill', row.acceptance === '通过' ? 'is-enabled' : 'is-disabled']">{{ row.acceptance }}</span></td>
                <td><button type="button" @click="router.push(row.page)">{{ row.page }}</button></td>
                <td>{{ row.remark }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section v-else-if="route.path === '/foundation/import-records'" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>基础资料导入记录</h2>
            <span>查看 CSV 导入预览、确认导入、取消和失败记录。</span>
          </div>
          <button type="button" @click="router.push('/foundation')">返回总览</button>
        </header>
        <section class="toolbar">
          <input v-model="importRecordKeyword" type="search" placeholder="按资料类型、文件名、状态查询" />
          <select v-model="importRecordStatus">
            <option value="">全部状态</option>
            <option value="preview">预览</option>
            <option value="imported">已导入</option>
            <option value="cancelled">已取消</option>
            <option value="failed">失败</option>
          </select>
          <button type="button" @click="refresh">刷新</button>
        </section>
        <div class="table-card">
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th>基础资料类型</th>
                <th>文件名</th>
                <th>总行数</th>
                <th>成功</th>
                <th>警告</th>
                <th>错误</th>
                <th>状态</th>
                <th>操作人</th>
                <th>创建时间</th>
                <th>导入时间</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="filteredImportRecords.length === 0">
                <td colspan="12" class="empty-state">暂无导入记录。</td>
              </tr>
              <tr v-for="(record, index) in filteredImportRecords" :key="record.id">
                <td>{{ index + 1 }}</td>
                <td>{{ record.entityName }}</td>
                <td>{{ record.fileName }}</td>
                <td>{{ record.totalRows }}</td>
                <td>{{ record.successRows }}</td>
                <td>{{ record.warningRows }}</td>
                <td>{{ record.errorRows }}</td>
                <td>{{ record.status }}</td>
                <td>{{ record.operator }}</td>
                <td>{{ record.createdAt }}</td>
                <td>{{ record.importedAt || '-' }}</td>
                <td>{{ record.remark }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section v-else-if="entityConfig" class="operation-shell">
      <section class="panel primary-panel">
        <header>
          <div>
            <h2>{{ entityConfig.title }}</h2>
            <span>{{ entityConfig.subtitle }}</span>
          </div>
          <div class="button-row">
            <button v-if="entityMode === 'list'" type="button" @click="createEntityFromHeader">新增</button>
            <button type="button" @click="router.push('/foundation')">返回基础资料</button>
          </div>
        </header>

        <div v-if="entityMode === 'list'" class="standard-list">
          <section class="toolbar">
            <div class="source-label">数据来源：manufacturing-foundation-state-v1</div>
            <input v-model="keyword" type="search" placeholder="请输入关键词查询" />
            <select v-model="statusFilter">
              <option value="">全部状态</option>
              <option value="enabled">启用</option>
              <option value="disabled">停用</option>
              <option v-if="entityConfig.collection === 'employees'" value="active">在职</option>
              <option v-if="entityConfig.collection === 'employees'" value="resigned">离职</option>
              <option v-if="entityConfig.collection === 'employees'" value="leave">休假</option>
              <option v-if="entityConfig.collection === 'employees'" value="borrowed">借调</option>
            </select>
            <select v-if="hasIndustryFilter" v-model="industryFilter">
              <option value="">全部行业</option>
              <option value="printing">印刷行业</option>
              <option value="wholeHouseWood">全屋定制/整木</option>
              <option value="general">通用制造</option>
            </select>
            <button type="button" @click="refresh">刷新</button>
            <button type="button" @click="exportCurrentList">导出 CSV</button>
            <button type="button" @click="clearAllFilters">清空筛选</button>
            <button type="button" @click="resetSorting">重置排序</button>
            <button type="button" @click="downloadCurrentTemplate">下载导入模板</button>
            <button type="button" @click="triggerImportFile">导入数据</button>
            <button type="button" @click="router.push('/foundation/import-records')">导入记录</button>
            <button type="button" @click="createEntityFromHeader">新增{{ entityConfig.itemName }}</button>
            <input ref="importFileInput" class="hidden-input" type="file" accept=".csv,text/csv" @change="handleImportFile" />
          </section>

          <section class="advanced-filter">
            <header>
              <strong>高级列筛选</strong>
              <span>每一列都可以筛选，多个条件会同时生效。</span>
            </header>
            <div class="filter-grid">
              <label v-for="field in entityConfig.fields" :key="field.key">
                {{ field.label }}
                <template v-if="columnFilterType(field) === 'number'">
                  <div class="range-inputs">
                    <input v-model="columnFilters[field.key].min" type="number" placeholder="最小值" />
                    <input v-model="columnFilters[field.key].max" type="number" placeholder="最大值" />
                  </div>
                </template>
                <template v-else-if="columnFilterType(field) === 'date'">
                  <div class="range-inputs">
                    <input v-model="columnFilters[field.key].start" type="date" />
                    <input v-model="columnFilters[field.key].end" type="date" />
                  </div>
                </template>
                <select v-else-if="columnFilterType(field) === 'enum'" v-model="columnFilters[field.key].values" multiple>
                  <option v-for="option in columnFilterOptions(field)" :key="option.value" :value="option.value">{{ option.label }}</option>
                </select>
                <input v-else v-model="columnFilters[field.key].text" type="search" placeholder="模糊筛选" />
              </label>
            </div>
          </section>

          <div class="table-card">
            <table>
              <thead>
                <tr>
                  <th class="index-cell">序号</th>
                  <th v-for="field in entityConfig.fields" :key="field.key" @click="toggleSort(field.key)">
                    {{ field.label }}
                    <span v-if="sortKey === field.key">{{ sortDirection === 'asc' ? '↑' : '↓' }}</span>
                  </th>
                  <th class="operation-cell">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="pagedEntityItems.length === 0">
                  <td :colspan="entityConfig.fields.length + 2" class="empty-state">暂无数据，请调整筛选条件或新增记录。</td>
                </tr>
                <tr v-for="(item, index) in pagedEntityItems" :key="item.id">
                  <td class="index-cell">{{ globalIndex(index) }}</td>
                  <td v-for="field in entityConfig.fields" :key="field.key">
                    <span v-if="field.key === 'status'" :class="['status-pill', isRecordEnabled(item) ? 'is-enabled' : 'is-disabled']">
                      {{ displayStatus(item) }}
                    </span>
                    <span v-else>{{ displayValue(item[field.key]) }}</span>
                  </td>
                  <td class="operation-cell">
                    <div class="button-row action-row">
                      <button type="button" @click="openEntity(item)">查看</button>
                      <button type="button" @click="editEntity(item)">编辑</button>
                      <button v-if="canToggleStatus" type="button" @click="toggleEntityStatus(item)">
                        {{ isRecordEnabled(item) ? '停用' : '启用' }}
                      </button>
                      <button type="button" @click="deleteEntity(item)">删除</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <footer class="pagination-bar">
            <span>共 {{ sortedEntityItems.length }} 条</span>
            <label>
              每页
              <select v-model.number="pageSize">
                <option :value="20">20</option>
                <option :value="50">50</option>
                <option :value="100">100</option>
              </select>
              条
            </label>
            <button type="button" :disabled="currentPage <= 1" @click="currentPage -= 1">上一页</button>
            <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
            <button type="button" :disabled="currentPage >= totalPages" @click="currentPage += 1">下一页</button>
          </footer>
        </div>

        <div v-else class="detail-layout">
          <div class="form-grid">
            <label v-for="field in entityConfig.editFields" :key="field.key">
              {{ field.label }}<span v-if="field.required"> *</span>
              <textarea v-if="field.type === 'textarea'" v-model="entityForm[field.key]" />
              <select v-else-if="field.type === 'select'" v-model="entityForm[field.key]">
                <option v-for="option in field.options || []" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
              <input v-else-if="field.type === 'checkbox'" v-model="entityForm[field.key]" type="checkbox" />
              <input v-else v-model="entityForm[field.key]" :type="field.type || 'text'" :readonly="entityMode === 'detail' && field.readonly" />
            </label>
          </div>
          <div class="button-row">
            <button type="button" @click="saveEntity">保存</button>
            <button v-if="entityMode === 'detail'" type="button" @click="deleteEntity(entityForm)">删除</button>
            <button type="button" @click="router.push(entityConfig.listPath)">返回列表</button>
          </div>

          <section v-if="entityConfig.collection === 'routings' && entityMode === 'detail'" class="panel editor-panel">
            <header>
              <h2>工艺步骤</h2>
              <button type="button" @click="startRoutingStep">新增步骤</button>
            </header>
            <div class="table-card">
              <table>
                <thead>
                  <tr><th>步骤号</th><th>工序</th><th>工作中心</th><th>标准工时</th><th>准备工时</th><th>转移/等待</th><th>质检点</th><th>操作</th></tr>
                </thead>
                <tbody>
                  <tr v-for="step in routingStepRows" :key="step.id">
                    <td>{{ step.stepNo }}</td>
                    <td>{{ step.processId }}</td>
                    <td>{{ step.workCenterId }}</td>
                    <td>{{ step.standardHours }}</td>
                    <td>{{ step.setupHours }}</td>
                    <td>{{ step.transferHours }}</td>
                    <td>{{ displayValue(step.qualityCheckPoint) }}</td>
                    <td>
                      <div class="button-row">
                        <button type="button" @click="editRoutingStep(step)">编辑步骤</button>
                        <button type="button" @click="removeRoutingStep(step)">删除步骤</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-if="routingStepEditorOpen" class="form-grid">
              <label v-for="field in routingStepFields" :key="field.key">
                {{ field.label }}
                <input v-model="routingStepForm[field.key]" :type="field.type || 'text'" />
              </label>
              <div class="button-row">
                <button type="button" @click="saveRoutingStep">保存步骤</button>
                <button type="button" @click="routingStepEditorOpen = false">取消</button>
              </div>
            </div>
          </section>
        </div>
      </section>

      <section v-if="inlineEditorOpen" class="panel editor-panel">
        <header>
          <h2>{{ entityForm.id ? '编辑' : '新增' }}{{ entityConfig.itemName }}</h2>
          <button type="button" @click="inlineEditorOpen = false">取消</button>
        </header>
        <div class="form-grid">
          <label v-for="field in entityConfig.editFields" :key="field.key">
            {{ field.label }}<span v-if="field.required"> *</span>
            <textarea v-if="field.type === 'textarea'" v-model="entityForm[field.key]" />
            <select v-else-if="field.type === 'select'" v-model="entityForm[field.key]">
              <option v-for="option in field.options || []" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
            <input v-else-if="field.type === 'checkbox'" v-model="entityForm[field.key]" type="checkbox" />
            <input v-else v-model="entityForm[field.key]" :type="field.type || 'text'" :readonly="Boolean(entityForm.id) && field.readonly" />
          </label>
        </div>
        <button type="button" @click="saveEntity">保存</button>
      </section>

      <section v-if="importPreviewOpen" class="panel editor-panel">
        <header>
          <div>
            <h2>{{ entityConfig.itemName }}导入预览</h2>
            <span>{{ importFileName }} / {{ importPreviewRows.length }} 行</span>
          </div>
          <button type="button" @click="cancelImportPreview">返回列表</button>
        </header>
        <div class="button-row">
          <button type="button" :disabled="importErrorRows.length > 0" @click="confirmImportPreview">确认导入</button>
          <button type="button" @click="cancelImportPreview">取消导入</button>
          <button type="button" @click="exportCurrentImportErrors">导出错误清单</button>
        </div>
        <div class="table-card">
          <table>
            <thead>
              <tr>
                <th>序号</th>
                <th>导入状态</th>
                <th>错误说明</th>
                <th>编码预览</th>
                <th>原始数据字段</th>
                <th>匹配到的基础资料</th>
                <th>操作建议</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in importPreviewRows" :key="row.rowNo">
                <td>{{ row.rowNo }}</td>
                <td>{{ row.status }}</td>
                <td>{{ row.message || '-' }}</td>
                <td>{{ row.codePreview }}</td>
                <td>{{ displayValue(row.raw) }}</td>
                <td>{{ displayValue(row.matched) }}</td>
                <td>{{ row.suggestion }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section v-else class="operation-shell">
      <section class="panel">
        <header>
          <h2>基础资料页面</h2>
          <button type="button" @click="router.push('/foundation')">返回总览</button>
        </header>
        <p>当前入口已接入，后续可在 V1.11.x 阶段继续扩展。</p>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  clearOperationLogs,
  createCertificate,
  createCodingRule,
  createCustomer,
  createDataDictionary,
  createEmployee,
  createEquipment,
  addRoutingStep,
  createMaterial,
  createMaterialSupplierRelation,
  createPermissionPoint,
  createProcess,
  createProductCategory,
  createRolePermission,
  createRouting,
  createShift,
  createSkill,
  createSupplier,
  createSupplierMaterialPrice,
  createSystemParameter,
  createUserRole,
  createWarehouse,
  createWarningRecord,
  createWarningRule,
  createWarningSubscriber,
  createWorkCenter,
  deleteCertificate,
  deleteCodingRule,
  deleteCustomer,
  deleteDataDictionary,
  deleteEmployee,
  deleteEquipment,
  deleteMaterial,
  deleteMaterialSupplierRelation,
  deletePermissionPoint,
  deleteProcess,
  deleteProductCategory,
  deleteRolePermission,
  deleteRouting,
  deleteRoutingStep,
  deleteShift,
  deleteSkill,
  deleteSupplier,
  deleteSupplierMaterialPrice,
  deleteSystemParameter,
  deleteUserRole,
  deleteWarehouse,
  deleteWarningRule,
  deleteWarningSubscriber,
  deleteWorkCenter,
  disableFoundationRecord,
  enableFoundationRecord,
  getCertificateById,
  getCustomerById,
  getEmployeeById,
  getEquipmentById,
  getFoundationReviewResults,
  getFoundationState,
  getImportRecords,
  getMaterialById,
  getProcessById,
  getRoutingById,
  getRoutingSteps,
  getSupplierById,
  previewNextCode,
  resetFoundationState,
  updateCertificate,
  updateCodingRule,
  updateCustomer,
  updateDataDictionary,
  updateEmployee,
  updateEquipment,
  updateMaterial,
  updateMaterialSupplierRelation,
  updatePermissionPoint,
  updateProcess,
  updateProductCategory,
  updateRolePermissions,
  updateRouting,
  updateRoutingStep,
  updateShift,
  updateSkill,
  updateSupplier,
  updateSupplierMaterialPrice,
  updateSystemParameter,
  updateUserRoles,
  updateWarehouse,
  updateWarningRecord,
  updateWarningRule,
  updateWarningSubscribers,
  updateWorkCenter,
  addImportRecord,
  updateImportRecord,
} from '../manufacturing/manufacturingFoundationStore.js'
import {
  generateManufacturingSampleData,
  resetAndGenerateSampleData,
} from '../manufacturing/manufacturingSampleDataFactory.js'
import {
  applyColumnFilters,
  applyKeywordFilter,
  applyPagination,
  applySorting,
  buildFilterOptions,
  exportRowsToCsv as exportRowsToCsvUtil,
  getColumnFilterType,
} from '../manufacturing/foundationTableUtils.js'
import {
  downloadImportTemplate,
  exportImportErrors,
  mapImportRowToPayload,
  parseCsvText,
  previewImportRows,
  validateImportRows,
} from '../manufacturing/foundationImportExportUtils.js'

const route = useRoute()
const router = useRouter()
const state = ref(getFoundationState())
const message = ref('')
const entityForm = reactive({})
const routingStepForm = reactive({})
const inlineEditorOpen = ref(false)
const routingStepEditorOpen = ref(false)
const keyword = ref('')
const statusFilter = ref('')
const industryFilter = ref('')
const columnFilters = reactive({})
const sortKey = ref('')
const sortDirection = ref('asc')
const currentPage = ref(1)
const pageSize = ref(20)
const importFileInput = ref(null)
const importPreviewOpen = ref(false)
const importPreviewRows = ref([])
const importRawRows = ref([])
const importValidation = ref({ errors: [], warnings: [] })
const importFileName = ref('')
const importRecordId = ref('')
const importRecordKeyword = ref('')
const importRecordStatus = ref('')

const statusOptions = [
  { value: 'enabled', label: '启用' },
  { value: 'disabled', label: '停用' },
]
const employeeStatusOptions = [
  { value: 'active', label: '在职' },
  { value: 'resigned', label: '离职' },
  { value: 'leave', label: '休假' },
  { value: 'borrowed', label: '借调' },
]
const industryOptions = [
  { value: 'printing', label: '印刷行业' },
  { value: 'wholeHouseWood', label: '全屋定制/整木' },
  { value: 'general', label: '通用制造' },
]

const employeeFields = [
  { key: 'employeeNo', label: '工号', required: true, readonly: true },
  { key: 'name', label: '姓名', required: true },
  { key: 'idCardNo', label: '身份证号' },
  { key: 'nativePlace', label: '籍贯' },
  { key: 'department', label: '部门', required: true },
  { key: 'role', label: '岗位', required: true },
  { key: 'jobGrade', label: '职等' },
  { key: 'jobLevel', label: '职级' },
  { key: 'hireDate', label: '入职日期', type: 'date' },
  { key: 'leaveDate', label: '离职日期', type: 'date' },
  { key: 'workYears', label: '工龄', type: 'number', readonly: true },
  { key: 'status', label: '人员状态', type: 'select', options: employeeStatusOptions },
  { key: 'phone', label: '电话' },
]
const materialFields = [
  { key: 'code', label: '物料编码', required: true, readonly: true },
  { key: 'name', label: '物料名称', required: true },
  { key: 'specification', label: '规格型号' },
  { key: 'materialType', label: '物料类型' },
  { key: 'productCategory', label: '产品类别' },
  { key: 'baseUnit', label: '基本单位' },
  { key: 'purchaseUnit', label: '采购单位' },
  { key: 'stockUnit', label: '库存单位' },
  { key: 'safetyStock', label: '安全库存', type: 'number' },
  { key: 'maxStock', label: '最高库存', type: 'number' },
  { key: 'defaultWarehouseId', label: '默认仓库' },
  { key: 'defaultLocationId', label: '默认库位' },
  { key: 'mrpEnabled', label: '启用 MRP', type: 'checkbox' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const customerFields = [
  { key: 'code', label: '客户编码', required: true, readonly: true },
  { key: 'name', label: '客户名称', required: true },
  { key: 'contact', label: '联系人' },
  { key: 'phone', label: '电话' },
  { key: 'creditLevel', label: '信用等级' },
  { key: 'creditLimit', label: '信用额度', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const supplierFields = [
  { key: 'code', label: '供应商编码', required: true, readonly: true },
  { key: 'name', label: '供应商名称', required: true },
  { key: 'contact', label: '联系人' },
  { key: 'phone', label: '电话' },
  { key: 'grade', label: '等级' },
  { key: 'onTimeRate', label: '准时率', type: 'number' },
  { key: 'leadTimeDays', label: '交货周期', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const workCenterFields = [
  { key: 'code', label: '工作中心编码', required: true, readonly: true },
  { key: 'name', label: '工作中心', required: true },
  { key: 'department', label: '部门' },
  { key: 'capacity', label: '产能', type: 'number' },
  { key: 'standardLaborCapacity', label: '标准人工产能', type: 'number' },
  { key: 'machineHours', label: '机器工时', type: 'number' },
  { key: 'laborCost', label: '单位人工成本', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const warehouseFields = [
  { key: 'code', label: '仓库编码', required: true, readonly: true },
  { key: 'name', label: '仓库名称', required: true },
  { key: 'owner', label: '负责人' },
  { key: 'locationCount', label: '库位数量', readonly: true },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const dictionaryFields = [
  { key: 'name', label: '字典名称', required: true },
  { key: 'values', label: '字典值' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const codingRuleFields = [
  { key: 'entityType', label: '对象类型' },
  { key: 'name', label: '规则名称', required: true },
  { key: 'prefix', label: '前缀' },
  { key: 'serialLength', label: '流水长度', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const parameterFields = [
  { key: 'key', label: '参数键', required: true },
  { key: 'name', label: '参数名称', required: true },
  { key: 'value', label: '参数值' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const permissionFields = [
  { key: 'code', label: '权限编码', required: true },
  { key: 'name', label: '权限名称', required: true },
  { key: 'module', label: '模块' },
  { key: 'action', label: '动作' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const supplierMaterialPriceFields = [
  { key: 'supplierMaterialCode', label: '价格记录编码', required: true, readonly: true },
  { key: 'supplierId', label: '供应商', required: true },
  { key: 'materialId', label: '物料', required: true },
  { key: 'minOrderQty', label: '最小采购量', type: 'number' },
  { key: 'price', label: '含税单价', type: 'number', required: true },
  { key: 'taxRate', label: '税率', type: 'number' },
  { key: 'currency', label: '币种' },
  { key: 'deliveryDays', label: '交货周期', type: 'number' },
  { key: 'isDefault', label: '默认价格', type: 'checkbox' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const materialSupplierRelationFields = [
  { key: 'relationCode', label: '关系编码', required: true, readonly: true },
  { key: 'materialId', label: '物料', required: true },
  { key: 'supplierId', label: '供应商', required: true },
  { key: 'priority', label: '优先级', type: 'number' },
  { key: 'isPrimary', label: '主供应商', type: 'checkbox' },
  { key: 'leadTimeDays', label: '交货周期', type: 'number' },
  { key: 'qualityLevel', label: '质量等级' },
  { key: 'onTimeRate', label: '准时率', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const processFields = [
  { key: 'processCode', label: '工序编码', required: true, readonly: true },
  { key: 'processName', label: '工序名称', required: true },
  { key: 'industryType', label: '行业类型', type: 'select', options: industryOptions },
  { key: 'workCenterId', label: '工作中心' },
  { key: 'standardHours', label: '标准工时', type: 'number' },
  { key: 'skillRequired', label: '技能要求' },
  { key: 'qualityCheckRequired', label: '质检要求', type: 'checkbox' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const routingFields = [
  { key: 'routingCode', label: '工艺路线编码', required: true, readonly: true },
  { key: 'routingName', label: '工艺路线名称', required: true },
  { key: 'industryType', label: '行业类型', type: 'select', options: industryOptions },
  { key: 'productCategory', label: '产品类别' },
  { key: 'materialId', label: '适用物料' },
  { key: 'version', label: '版本' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const equipmentFields = [
  { key: 'equipmentCode', label: '设备编码', required: true, readonly: true },
  { key: 'equipmentName', label: '设备名称', required: true },
  { key: 'industryType', label: '行业类型', type: 'select', options: industryOptions },
  { key: 'workCenterId', label: '工作中心', required: true },
  { key: 'equipmentType', label: '设备类型' },
  { key: 'capacityPerHour', label: '每小时产能', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const productCategoryFields = [
  { key: 'categoryCode', label: '类别编码', required: true, readonly: true },
  { key: 'categoryName', label: '类别名称', required: true },
  { key: 'industryType', label: '行业类型', type: 'select', options: industryOptions },
  { key: 'parentId', label: '父级类别' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const basicNameFields = [
  { key: 'name', label: '名称', required: true },
  { key: 'level', label: '等级/类型' },
  { key: 'ownerRole', label: '责任岗位' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const certificateFields = [
  { key: 'name', label: '证书名称', required: true },
  { key: 'type', label: '证书类型' },
  { key: 'owner', label: '持有人' },
  { key: 'expireDate', label: '到期日期', type: 'date' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const shiftFields = [
  { key: 'name', label: '班次名称', required: true },
  { key: 'startTime', label: '开始时间' },
  { key: 'endTime', label: '结束时间' },
  { key: 'capacity', label: '容量', type: 'number' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const warningRuleFields = [
  { key: 'name', label: '规则名称', required: true },
  { key: 'target', label: '对象' },
  { key: 'condition', label: '条件' },
  { key: 'level', label: '等级' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const warningRecordFields = [
  { key: 'ruleName', label: '规则' },
  { key: 'target', label: '对象', required: true },
  { key: 'level', label: '等级' },
  { key: 'status', label: '状态' },
  { key: 'owner', label: '负责人' },
]
const rolePermissionFields = [
  { key: 'role', label: '角色', required: true },
  { key: 'permissionCodes', label: '权限编码' },
]
const userRoleFields = [
  { key: 'userName', label: '用户', required: true },
  { key: 'roles', label: '角色' },
]
const subscriberFields = [
  { key: 'name', label: '订阅人', required: true },
  { key: 'channel', label: '渠道' },
  { key: 'scope', label: '范围' },
  { key: 'status', label: '状态', type: 'select', options: statusOptions },
]
const routingStepFields = [
  { key: 'stepNo', label: '步骤号', type: 'number' },
  { key: 'processId', label: '工序' },
  { key: 'workCenterId', label: '工作中心' },
  { key: 'standardHours', label: '标准工时', type: 'number' },
  { key: 'setupHours', label: '准备工时', type: 'number' },
  { key: 'transferHours', label: '转移/等待', type: 'number' },
  { key: 'qualityCheckPoint', label: '质检点' },
  { key: 'remark', label: '备注' },
]

function makeEntityConfig(title, subtitle, itemName, collection, fields, createPath, listPath, create, update, remove, detailGetter, entityType) {
  return { title, subtitle, itemName, collection, fields, editFields: fields, createPath, listPath, create, update, remove, detailGetter, entityType }
}

const entityConfigs = {
  '/foundation/pfm/employees': makeEntityConfig('员工档案', '员工工号、身份证、岗位、职等职级、人员状态与工龄维护', '员工', 'employees', employeeFields, '/foundation/pfm/employee/create', '/foundation/pfm/employees', createEmployee, updateEmployee, deleteEmployee, getEmployeeById, 'employee'),
  '/foundation/pfm/employee/create': makeEntityConfig('新增员工', '新增员工时自动生成员工工号', '员工', 'employees', employeeFields, null, '/foundation/pfm/employees', createEmployee, updateEmployee, deleteEmployee, getEmployeeById, 'employee'),
  '/foundation/pfm/skills': makeEntityConfig('技能标签', '维护人员技能基础资料', '技能', 'skills', basicNameFields, null, '/foundation/pfm/skills', createSkill, updateSkill, deleteSkill),
  '/foundation/pfm/certificates': makeEntityConfig('证书资质', '维护人员证书与有效期', '证书', 'certificates', certificateFields, null, '/foundation/pfm/certificates', createCertificate, updateCertificate, deleteCertificate, getCertificateById),
  '/foundation/pfm/shifts': makeEntityConfig('班次日历', '维护班次与容量', '班次', 'shifts', shiftFields, null, '/foundation/pfm/shifts', createShift, updateShift, deleteShift),
  '/foundation/erp/materials': makeEntityConfig('物料档案', '物料编码、库存上下限、默认仓库/库位与 MRP 控制', '物料', 'materials', materialFields, '/foundation/erp/material/create', '/foundation/erp/materials', createMaterial, updateMaterial, deleteMaterial, getMaterialById, 'material'),
  '/foundation/erp/material/create': makeEntityConfig('新增物料', '新增物料时自动生成物料编码', '物料', 'materials', materialFields, null, '/foundation/erp/materials', createMaterial, updateMaterial, deleteMaterial, getMaterialById, 'material'),
  '/foundation/erp/customers': makeEntityConfig('客户档案', '客户编码、联系人、信用等级与信用额度', '客户', 'customers', customerFields, '/foundation/erp/customer/create', '/foundation/erp/customers', createCustomer, updateCustomer, deleteCustomer, getCustomerById, 'customer'),
  '/foundation/erp/customer/create': makeEntityConfig('新增客户', '新增客户时自动生成客户编码', '客户', 'customers', customerFields, null, '/foundation/erp/customers', createCustomer, updateCustomer, deleteCustomer, getCustomerById, 'customer'),
  '/foundation/erp/suppliers': makeEntityConfig('供应商档案', '供应商编码、准时率、交货周期与启停控制', '供应商', 'suppliers', supplierFields, '/foundation/erp/supplier/create', '/foundation/erp/suppliers', createSupplier, updateSupplier, deleteSupplier, getSupplierById, 'supplier'),
  '/foundation/erp/supplier/create': makeEntityConfig('新增供应商', '新增供应商时自动生成供应商编码', '供应商', 'suppliers', supplierFields, null, '/foundation/erp/suppliers', createSupplier, updateSupplier, deleteSupplier, getSupplierById, 'supplier'),
  '/foundation/erp/work-centers': makeEntityConfig('工作中心', '制造资源、人工产能、机器工时与成本基础资料', '工作中心', 'workCenters', workCenterFields, null, '/foundation/erp/work-centers', createWorkCenter, updateWorkCenter, deleteWorkCenter, null, 'workCenter'),
  '/foundation/erp/warehouses': makeEntityConfig('仓库与库位', '仓库基础资料，库位随仓库维护并进入引用源', '仓库', 'warehouses', warehouseFields, null, '/foundation/erp/warehouses', createWarehouse, updateWarehouse, deleteWarehouse, null, 'warehouse'),
  '/foundation/erp/data-dictionaries': makeEntityConfig('数据字典', '维护基础资料枚举项', '数据字典', 'dataDictionaries', dictionaryFields, null, '/foundation/erp/data-dictionaries', createDataDictionary, updateDataDictionary, deleteDataDictionary),
  '/foundation/erp/coding-rules': makeEntityConfig('编码规则', '维护基础资料自动编码规则', '编码规则', 'codingRules', codingRuleFields, null, '/foundation/erp/coding-rules', createCodingRule, updateCodingRule, deleteCodingRule),
  '/foundation/erp/system-parameters': makeEntityConfig('系统参数', '配置默认入口与基础资料校验参数', '系统参数', 'systemParameters', parameterFields, null, '/foundation/erp/system-parameters', createSystemParameter, updateSystemParameter, deleteSystemParameter),
  '/foundation/erp/supplier-material-prices': makeEntityConfig('供应商物料价格', '维护供应商、物料、含税价格、税率、交期和默认价格', '供应商物料价格', 'supplierMaterialPrices', supplierMaterialPriceFields, null, '/foundation/erp/supplier-material-prices', createSupplierMaterialPrice, updateSupplierMaterialPrice, deleteSupplierMaterialPrice, null, 'supplierMaterialPrice'),
  '/foundation/erp/material-suppliers': makeEntityConfig('物料供应商关系', '维护主供应商、供应优先级、准时率和质量等级', '物料供应商关系', 'materialSupplierRelations', materialSupplierRelationFields, null, '/foundation/erp/material-suppliers', createMaterialSupplierRelation, updateMaterialSupplierRelation, deleteMaterialSupplierRelation, null, 'materialSupplierRelation'),
  '/foundation/erp/product-categories': makeEntityConfig('产品类别', '维护产品分类和父子级关系', '产品类别', 'productCategories', productCategoryFields, null, '/foundation/erp/product-categories', createProductCategory, updateProductCategory, deleteProductCategory, null, 'productCategory'),
  '/foundation/manufacturing/processes': makeEntityConfig('工序资料', '维护生产工序、标准工时、工作中心和质检要求', '工序', 'processes', processFields, null, '/foundation/manufacturing/processes', createProcess, updateProcess, deleteProcess, getProcessById, 'process'),
  '/foundation/manufacturing/routings': makeEntityConfig('工艺路线', '维护工艺路线主表，步骤可在路线详情页继续维护', '工艺路线', 'routings', routingFields, null, '/foundation/manufacturing/routings', createRouting, updateRouting, deleteRouting, getRoutingById, 'routing'),
  '/foundation/manufacturing/equipment': makeEntityConfig('设备资料', '维护设备、工作中心、设备类型、状态和产能', '设备', 'equipment', equipmentFields, null, '/foundation/manufacturing/equipment', createEquipment, updateEquipment, deleteEquipment, getEquipmentById, 'equipment'),
  '/foundation/security/permissions': makeEntityConfig('权限点', '基础资料权限点维护', '权限点', 'permissionPoints', permissionFields, null, '/foundation/security/permissions', createPermissionPoint, updatePermissionPoint, deletePermissionPoint),
  '/foundation/security/role-permissions': makeEntityConfig('角色权限', '按角色维护权限点编码，多个编码用逗号分隔', '角色权限', 'rolePermissions', rolePermissionFields, null, '/foundation/security/role-permissions', createRolePermission, updateRolePermissions, deleteRolePermission),
  '/foundation/security/user-roles': makeEntityConfig('用户角色', '按用户维护岗位角色，多个角色用逗号分隔', '用户角色', 'userRoles', userRoleFields, null, '/foundation/security/user-roles', createUserRole, updateUserRoles, deleteUserRole),
  '/foundation/warnings/rules': makeEntityConfig('预警规则', '预警引擎基础规则维护', '预警规则', 'warningRules', warningRuleFields, null, '/foundation/warnings/rules', createWarningRule, updateWarningRule, deleteWarningRule),
  '/foundation/warnings/records': makeEntityConfig('预警记录', '预警记录查看与处理', '预警记录', 'warningRecords', warningRecordFields, null, '/foundation/warnings/records', createWarningRecord, updateWarningRecord, null),
  '/foundation/warnings/subscribers': makeEntityConfig('预警订阅人', '维护接收预警的人员、渠道和范围', '预警订阅人', 'warningSubscribers', subscriberFields, null, '/foundation/warnings/subscribers', createWarningSubscriber, updateWarningSubscribers, deleteWarningSubscriber),
}

const detailPatterns = [
  { match: /^\/foundation\/pfm\/employee\/(.+)$/, base: '/foundation/pfm/employee/create', get: getEmployeeById, list: '/foundation/pfm/employees' },
  { match: /^\/foundation\/erp\/material\/(.+)$/, base: '/foundation/erp/material/create', get: getMaterialById, list: '/foundation/erp/materials' },
  { match: /^\/foundation\/erp\/customer\/(.+)$/, base: '/foundation/erp/customer/create', get: getCustomerById, list: '/foundation/erp/customers' },
  { match: /^\/foundation\/erp\/supplier\/(.+)$/, base: '/foundation/erp/supplier/create', get: getSupplierById, list: '/foundation/erp/suppliers' },
  { match: /^\/foundation\/manufacturing\/routing\/(.+)$/, base: '/foundation/manufacturing/routings', get: getRoutingById, list: '/foundation/manufacturing/routings' },
]

const entityConfig = computed(() => {
  const direct = entityConfigs[route.path]
  if (direct) return direct
  const detail = detailPatterns.find((item) => item.match.test(route.path))
  if (!detail) return null
  const config = { ...entityConfigs[detail.base] }
  config.title = config.title.replace('新增', '编辑')
  config.detailGetter = detail.get
  config.listPath = detail.list
  return config
})
const entityMode = computed(() => {
  if (!entityConfig.value) return ''
  if (route.path.includes('/create')) return 'create'
  if (detailPatterns.some((item) => item.match.test(route.path))) return 'detail'
  return 'list'
})
const entityItems = computed(() => {
  const items = entityConfig.value ? state.value[entityConfig.value.collection] || [] : []
  if (entityConfig.value?.collection === 'warehouses') {
    return items.map((item) => ({ ...item, locationCount: item.locations?.length || 0 }))
  }
  return items
})
const canToggleStatus = computed(() => entityConfig.value?.collection !== 'employees')
const hasIndustryFilter = computed(() => entityConfig.value?.fields?.some((field) => field.key === 'industryType'))
const reviewRows = computed(() => getFoundationReviewResults())
const filteredEntityItems = computed(() => {
  const keywordRows = applyKeywordFilter(entityItems.value, keyword.value, entityConfig.value?.fields || [])
  const statusRows = keywordRows.filter((item) => !statusFilter.value || String(item.status || '').toLowerCase() === statusFilter.value)
  const industryRows = statusRows.filter((item) => !industryFilter.value || item.industryType === industryFilter.value)
  return applyColumnFilters(industryRows, columnFilters, entityConfig.value?.fields || [])
})
const sortedEntityItems = computed(() => applySorting(filteredEntityItems.value, { key: sortKey.value, direction: sortDirection.value }))
const totalPages = computed(() => Math.max(1, Math.ceil(sortedEntityItems.value.length / pageSize.value)))
const pagedEntityItems = computed(() => applyPagination(sortedEntityItems.value, currentPage.value, pageSize.value))
const importErrorRows = computed(() => importValidation.value.errors || [])
const filteredImportRecords = computed(() => {
  const text = importRecordKeyword.value.trim().toLowerCase()
  return getImportRecords().filter((record) => {
    const matchText = !text || JSON.stringify(record).toLowerCase().includes(text)
    const matchStatus = !importRecordStatus.value || record.status === importRecordStatus.value
    return matchText && matchStatus
  })
})
const routingStepRows = computed(() => entityConfig.value?.collection === 'routings' && entityMode.value === 'detail' ? getRoutingSteps(routeDetailId()) : [])
const pageTitle = computed(() => entityConfig.value?.title || {
  '/foundation': '制造业基础资料',
  '/foundation/sample-data': '样例数据管理',
  '/foundation/review-check': '基础资料评审检查',
}[route.path] || '制造业基础资料')
const summaryCards = computed(() => [
  { title: '员工档案', value: `${state.value.employees.length} 人`, desc: '员工、技能、证书、班次', to: '/foundation/pfm/employees' },
  { title: '物料档案', value: `${state.value.materials.length} 个`, desc: '物料、客户、供应商、工作中心、仓库', to: '/foundation/erp/materials' },
  { title: '价格与供应关系', value: `${state.value.supplierMaterialPrices?.length || 0} 条`, desc: '供应商物料价格和物料供应商关系', to: '/foundation/erp/supplier-material-prices' },
  { title: '制造基础', value: `${state.value.processes?.length || 0} 道工序`, desc: '工序、工艺路线、设备、产品类别', to: '/foundation/manufacturing/processes' },
  { title: '权限与日志', value: `${state.value.permissionPoints.length} 个权限点`, desc: '权限点、角色权限、用户角色、操作日志', to: '/foundation/security/permissions' },
  { title: '预警基础', value: `${state.value.warningRules.length} 条规则`, desc: '规则、记录、订阅人', to: '/foundation/warnings/rules' },
])
const sampleDataCards = computed(() => [
  { title: '员工数量', value: state.value.employees?.length || 0, desc: '目标 >= 200' },
  { title: '物料数量', value: state.value.materials?.length || 0, desc: '目标 >= 300' },
  { title: '供应商数量', value: state.value.suppliers?.length || 0, desc: '目标 >= 100' },
  { title: '供应商物料价格', value: state.value.supplierMaterialPrices?.length || 0, desc: '目标 >= 500' },
  { title: '物料供应商关系', value: state.value.materialSupplierRelations?.length || 0, desc: '目标 >= 500' },
  { title: '工作中心', value: state.value.workCenters?.length || 0, desc: '目标 >= 30' },
  { title: '工序', value: state.value.processes?.length || 0, desc: '目标 >= 80' },
  { title: '工艺路线', value: state.value.routings?.length || 0, desc: '目标 >= 30' },
  { title: '设备', value: state.value.equipment?.length || 0, desc: '目标 >= 80' },
  { title: '仓库', value: state.value.warehouses?.length || 0, desc: '目标 >= 10' },
  { title: '库位', value: countLocations(state.value.warehouses), desc: '目标 >= 100' },
  { title: '客户', value: state.value.customers?.length || 0, desc: '目标 >= 100' },
])
const foundationEntries = [
  { label: '员工档案', to: '/foundation/pfm/employees' },
  { label: '物料档案', to: '/foundation/erp/materials' },
  { label: '供应商档案', to: '/foundation/erp/suppliers' },
  { label: '供应商物料价格', to: '/foundation/erp/supplier-material-prices' },
  { label: '物料供应商关系', to: '/foundation/erp/material-suppliers' },
  { label: '工序资料', to: '/foundation/manufacturing/processes' },
  { label: '工艺路线', to: '/foundation/manufacturing/routings' },
  { label: '设备资料', to: '/foundation/manufacturing/equipment' },
  { label: '样例数据管理', to: '/foundation/sample-data' },
  { label: '基础资料评审检查', to: '/foundation/review-check' },
  { label: '导入记录', to: '/foundation/import-records' },
]

function refresh() {
  state.value = getFoundationState()
}

function notify(text) {
  message.value = text
  window.setTimeout(() => { message.value = '' }, 1800)
}

function countLocations(warehouses = []) {
  return warehouses.reduce((sum, warehouse) => sum + (warehouse.locations?.length || 0), 0)
}

function displayValue(value) {
  if (Array.isArray(value)) return value.join('、')
  if (value && typeof value === 'object') return JSON.stringify(value)
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value ?? ''
}

function displayStatus(item) {
  const map = {
    enabled: '启用',
    disabled: '停用',
    active: '在职',
    resigned: '离职',
    leave: '休假',
    borrowed: '借调',
  }
  return map[String(item?.status || '')] || item?.status || '启用'
}

function isRecordEnabled(item) {
  return !['disabled', '停用'].includes(String(item?.status || '').toLowerCase())
}

function resetObject(target, source = {}) {
  Object.keys(target).forEach((key) => delete target[key])
  Object.assign(target, source)
}

function defaultEntityForm(config) {
  const result = config.editFields.reduce((next, field) => ({
    ...next,
    [field.key]: field.type === 'number' ? 0 : field.type === 'checkbox' ? false : '',
  }), { status: config.collection === 'employees' ? 'active' : 'enabled' })
  const codeMap = {
    employee: 'employeeNo',
    material: 'code',
    customer: 'code',
    supplier: 'code',
    workCenter: 'code',
    warehouse: 'code',
    process: 'processCode',
    routing: 'routingCode',
    equipment: 'equipmentCode',
    productCategory: 'categoryCode',
    supplierMaterialPrice: 'supplierMaterialCode',
    materialSupplierRelation: 'relationCode',
  }
  if (config.entityType && codeMap[config.entityType]) result[codeMap[config.entityType]] = previewNextCode(config.entityType)
  if (config.collection === 'materials') {
    result.mrpEnabled = true
    result.safetyStock = 0
    result.maxStock = 0
  }
  if (config.collection === 'supplierMaterialPrices') {
    result.currency = 'CNY'
    result.taxRate = 13
  }
  if (config.collection === 'materialSupplierRelations') result.priority = 1
  if (config.collection === 'routings') result.version = 'V1'
  return result
}

function routeDetailId() {
  const matched = detailPatterns.map((item) => route.path.match(item.match)).find(Boolean)
  return matched?.[1]
}

function syncForm() {
  inlineEditorOpen.value = false
  routingStepEditorOpen.value = false
  importPreviewOpen.value = false
  currentPage.value = 1
  resetColumnFilters()
  if (!entityConfig.value) return
  if (entityMode.value === 'create') {
    resetObject(entityForm, defaultEntityForm(entityConfig.value))
    return
  }
  if (entityMode.value === 'detail') {
    resetObject(entityForm, entityConfig.value.detailGetter?.(routeDetailId()) || defaultEntityForm(entityConfig.value))
  }
}

function validateForm(config) {
  const missing = config.editFields.find((field) => field.required && !String(entityForm[field.key] || '').trim())
  if (missing) {
    notify(`请填写必填项：${missing.label}`)
    return false
  }
  if (config.collection === 'employees' && entityForm.idCardNo && ![15, 18].includes(String(entityForm.idCardNo).length)) {
    notify('身份证号必须为 15 位或 18 位')
    return false
  }
  if (config.collection === 'materials' && Number(entityForm.maxStock || 0) < Number(entityForm.safetyStock || 0)) {
    notify('最高库存必须大于等于安全库存')
    return false
  }
  return true
}

function saveEntity() {
  const config = entityConfig.value
  if (!config || !validateForm(config)) return
  const payload = { ...entityForm }
  config.editFields.forEach((field) => {
    if (field.type === 'number') payload[field.key] = Number(payload[field.key] || 0)
  })
  try {
    if (entityMode.value === 'create' || !payload.id) {
      config.create(payload)
      notify(`${config.itemName}已新增`)
      refresh()
      router.push(config.listPath)
      return
    }
    config.update(payload.id, payload)
    notify(`${config.itemName}已保存`)
    inlineEditorOpen.value = false
    refresh()
    if (entityMode.value === 'detail') router.push(config.listPath)
  } catch (error) {
    notify(error.message || '保存失败')
  }
}

function startInlineEdit(item) {
  resetObject(entityForm, item)
  inlineEditorOpen.value = true
}

function openEntity(item) {
  const routes = {
    employees: `/foundation/pfm/employee/${item.id}`,
    materials: `/foundation/erp/material/${item.id}`,
    customers: `/foundation/erp/customer/${item.id}`,
    suppliers: `/foundation/erp/supplier/${item.id}`,
    routings: `/foundation/manufacturing/routing/${item.id}`,
  }
  if (routes[entityConfig.value.collection]) router.push(routes[entityConfig.value.collection])
  else startInlineEdit(item)
}

function editEntity(item) {
  openEntity(item)
}

function createEntityFromHeader() {
  if (entityConfig.value.createPath) {
    router.push(entityConfig.value.createPath)
    return
  }
  resetObject(entityForm, defaultEntityForm(entityConfig.value))
  inlineEditorOpen.value = true
}

function deleteEntity(item) {
  const config = entityConfig.value
  if (!config?.remove || !item?.id) return
  if (!window.confirm(`确认删除${config.itemName}？`)) return
  config.remove(item.id)
  notify(`${config.itemName}已删除`)
  inlineEditorOpen.value = false
  refresh()
  if (entityMode.value !== 'list') router.push(config.listPath)
}

function toggleEntityStatus(item) {
  const config = entityConfig.value
  if (!config || config.collection === 'employees') return
  const nextDisabled = isRecordEnabled(item)
  if (nextDisabled && !window.confirm(`确认停用${config.itemName}？停用后不会进入默认引用和推荐。`)) return
  try {
    if (nextDisabled) disableFoundationRecord(config.collection, item.id)
    else enableFoundationRecord(config.collection, item.id)
    refresh()
    notify(nextDisabled ? '已停用' : '已启用')
  } catch (error) {
    notify(error.message || '状态切换失败')
  }
}

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDirection.value = 'asc'
  }
}

function resetSorting() {
  sortKey.value = ''
  sortDirection.value = 'asc'
}

function columnFilterType(field) {
  return getColumnFilterType(field)
}

function ensureColumnFilters() {
  if (!entityConfig.value) return
  entityConfig.value.fields.forEach((field) => {
    if (columnFilters[field.key]) return
    const type = columnFilterType(field)
    if (type === 'number') columnFilters[field.key] = { min: '', max: '' }
    else if (type === 'date') columnFilters[field.key] = { start: '', end: '' }
    else if (type === 'enum') columnFilters[field.key] = { values: [] }
    else columnFilters[field.key] = { text: '' }
  })
}

function resetColumnFilters() {
  Object.keys(columnFilters).forEach((key) => delete columnFilters[key])
  ensureColumnFilters()
}

function clearAllFilters() {
  keyword.value = ''
  statusFilter.value = ''
  industryFilter.value = ''
  resetColumnFilters()
  currentPage.value = 1
}

function columnFilterOptions(field) {
  if (field.options?.length) return field.options
  if (field.key === 'status' && entityConfig.value?.collection === 'employees') return employeeStatusOptions
  if (field.key === 'status') return statusOptions
  return buildFilterOptions(entityItems.value, field)
}

function globalIndex(index) {
  return (currentPage.value - 1) * pageSize.value + index + 1
}

function exportCurrentList() {
  exportRowsToCsvUtil(sortedEntityItems.value.map((row, index) => ({ _index: index + 1, ...row })), [{ key: '_index', label: '序号' }, ...entityConfig.value.fields], `${entityConfig.value.collection}.csv`)
}

function exportReviewCsv() {
  exportRowsToCsvUtil(reviewRows.value, [
    { key: 'index', label: '序号' },
    { key: 'item', label: '评审项目' },
    { key: 'standard', label: '检查标准' },
    { key: 'result', label: '当前结果' },
    { key: 'acceptance', label: '验收结果' },
    { key: 'page', label: '建议处理页面' },
    { key: 'remark', label: '备注' },
  ], 'foundation-review-check.csv')
}

function downloadCurrentTemplate() {
  downloadImportTemplate(entityConfig.value.entityType || entityConfig.value.collection, entityConfig.value.fields, entityConfig.value.itemName)
}

function triggerImportFile() {
  importFileInput.value?.click()
}

function handleImportFile(event) {
  const file = event.target.files?.[0]
  if (!file || !entityConfig.value) return
  const reader = new FileReader()
  reader.onload = () => {
    importFileName.value = file.name
    importRawRows.value = parseCsvText(reader.result)
    const entityType = entityConfig.value.entityType || entityConfig.value.collection
    importValidation.value = validateImportRows(entityType, importRawRows.value, entityConfig.value.fields)
    importPreviewRows.value = previewImportRows(entityType, importRawRows.value, entityConfig.value.fields)
    importPreviewOpen.value = true
    importRecordId.value = addImportRecord({
      entityType,
      entityName: entityConfig.value.itemName,
      fileName: file.name,
      totalRows: importRawRows.value.length,
      successRows: importPreviewRows.value.filter((row) => row.status !== '错误').length,
      warningRows: importValidation.value.warnings.length,
      errorRows: importValidation.value.errors.length,
      status: 'preview',
      remark: '导入预校验完成，等待确认',
    })
    refresh()
  }
  reader.readAsText(file, 'utf-8')
  event.target.value = ''
}

function confirmImportPreview() {
  if (importErrorRows.value.length > 0) {
    notify('存在错误行，不能确认导入')
    return
  }
  if (!window.confirm('确认导入当前预览数据？')) return
  try {
    const entityType = entityConfig.value.entityType || entityConfig.value.collection
    importRawRows.value.forEach((row) => {
      entityConfig.value.create(mapImportRowToPayload(entityType, row, entityConfig.value.fields))
    })
    updateImportRecord(importRecordId.value, {
      status: 'imported',
      importedAt: new Date().toISOString(),
      successRows: importRawRows.value.length,
      remark: '导入成功，已写入 localStorage',
    })
    importPreviewOpen.value = false
    refresh()
    notify('导入成功')
  } catch (error) {
    updateImportRecord(importRecordId.value, { status: 'failed', remark: error.message || '导入失败' })
    refresh()
    notify(error.message || '导入失败')
  }
}

function cancelImportPreview() {
  if (importRecordId.value) updateImportRecord(importRecordId.value, { status: 'cancelled', remark: '用户取消导入' })
  importPreviewOpen.value = false
  importPreviewRows.value = []
  importRawRows.value = []
  importValidation.value = { errors: [], warnings: [] }
  refresh()
}

function exportCurrentImportErrors() {
  exportImportErrors(importValidation.value.errors || [], `${entityConfig.value.collection}-import-errors.csv`)
}

function defaultRoutingStepForm() {
  return {
    stepNo: (routingStepRows.value.length + 1) * 10,
    processId: state.value.processes?.[0]?.id || '',
    workCenterId: state.value.workCenters?.[0]?.id || '',
    standardHours: 1,
    setupHours: 0,
    transferHours: 0,
    qualityCheckPoint: false,
    remark: '',
  }
}

function startRoutingStep() {
  resetObject(routingStepForm, defaultRoutingStepForm())
  routingStepEditorOpen.value = true
}

function editRoutingStep(step) {
  resetObject(routingStepForm, step)
  routingStepEditorOpen.value = true
}

function saveRoutingStep() {
  const routingId = routeDetailId()
  const payload = { ...routingStepForm }
  routingStepFields.forEach((field) => {
    if (field.type === 'number') payload[field.key] = Number(payload[field.key] || 0)
  })
  payload.qualityCheckPoint = ['true', true, '是', '1'].includes(payload.qualityCheckPoint)
  try {
    if (payload.id) updateRoutingStep(routingId, payload.id, payload)
    else addRoutingStep(routingId, payload)
    routingStepEditorOpen.value = false
    refresh()
    notify('工艺步骤已保存')
  } catch (error) {
    notify(error.message || '工艺步骤保存失败')
  }
}

function removeRoutingStep(step) {
  if (!window.confirm('确认删除工艺步骤？')) return
  deleteRoutingStep(routeDetailId(), step.id)
  refresh()
  notify('工艺步骤已删除')
}

function generateSampleDataWithConfirm() {
  if (!window.confirm('确认生成制造业样例数据？已经生成过的数据不会重复生成。')) return
  const result = generateManufacturingSampleData()
  refresh()
  notify(result.message)
}

function resetSampleDataWithConfirm() {
  if (!window.confirm('确认重置并重新生成样例数据？当前基础资料会恢复为样例数据状态。')) return
  const result = resetAndGenerateSampleData()
  refresh()
  notify(result.message)
}

function resetDemoData() {
  resetFoundationState()
  refresh()
  notify('默认演示数据已恢复')
}

watch([keyword, statusFilter, industryFilter, pageSize, columnFilters], () => { currentPage.value = 1 }, { deep: true })
watch(sortedEntityItems, () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})
watch(() => route.fullPath, syncForm, { immediate: true })
watch(entityConfig, () => {
  resetColumnFilters()
  syncForm()
})
</script>

<style scoped>
.foundation-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 100%;
  padding: 22px;
  background: #f4f7fb;
  color: #172033;
}

.page-header,
.panel header,
.pagination-bar,
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  margin: 0 0 4px;
  color: #64748b;
  font-size: 13px;
}

h1,
h2 {
  margin: 0;
}

.page-tabs,
.button-row,
.entry-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.page-tabs a,
.panel a,
button {
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-weight: 700;
  text-decoration: none;
  cursor: pointer;
}

button {
  border-color: #0f766e;
  background: #f0fdfa;
  color: #0f766e;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.operation-shell,
.detail-layout,
.standard-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.panel,
.summary-grid article {
  border: 1px solid #dce5f2;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.primary-panel {
  border-color: #bfdbfe;
}

.editor-panel {
  border-color: #0f766e;
}

.notice {
  border: 1px solid #99f6e4;
  border-radius: 8px;
  padding: 10px 12px;
  background: #f0fdfa;
  color: #0f766e;
  font-weight: 700;
}

.summary-grid,
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-grid article {
  background: #f8fafc;
}

.summary-grid span,
.panel header span,
.source-label {
  color: #64748b;
  font-size: 12px;
}

.summary-grid strong {
  display: block;
  margin: 8px 0;
  color: #101828;
  font-size: 22px;
}

.toolbar {
  flex-wrap: wrap;
  justify-content: flex-start;
}

.advanced-filter {
  border: 1px dashed #cbd5e1;
  border-radius: 8px;
  padding: 12px;
  background: #f8fafc;
}

.advanced-filter header {
  justify-content: flex-start;
  margin-bottom: 10px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(180px, 1fr));
  gap: 12px;
}

.range-inputs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px;
}

.hidden-input {
  display: none;
}

.table-card {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  min-width: 920px;
}

th,
td {
  border-bottom: 1px solid #e2e8f0;
  padding: 10px;
  text-align: left;
  vertical-align: top;
}

th {
  background: #f8fafc;
  color: #334155;
  cursor: pointer;
  white-space: nowrap;
}

.index-cell {
  width: 64px;
  color: #64748b;
}

.operation-cell {
  min-width: 240px;
  text-align: right;
}

.action-row {
  justify-content: flex-end;
}

.empty-state {
  padding: 32px;
  text-align: center;
  color: #64748b;
}

.status-pill {
  display: inline-flex;
  border-radius: 999px;
  padding: 4px 10px;
  background: #fee2e2;
  color: #991b1b;
  font-weight: 700;
}

.status-pill.is-enabled {
  background: #dcfce7;
  color: #166534;
}

input,
textarea,
select {
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px 10px;
  background: #fff;
  color: #172033;
}

input,
textarea {
  width: 100%;
}

textarea {
  min-height: 88px;
}

label {
  display: grid;
  gap: 6px;
  color: #334155;
  font-weight: 700;
}

p {
  color: #475467;
  line-height: 1.55;
}

@media (max-width: 1100px) {
  .summary-grid,
  .form-grid,
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .page-header,
  .panel header,
  .pagination-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid,
  .form-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
