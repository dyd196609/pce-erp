<template>
  <div style="padding: 20px">
    <h2>采购订单管理</h2>

    <!-- 工具栏 -->
    <div style="margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center">
      <el-button type="primary" @click="handleAdd">新增订单</el-button>
      <el-button type="success" @click="downloadTemplate">下载导入模板</el-button>
      <el-upload
        :action="uploadUrl"
        :headers="uploadHeaders"
        :on-success="handleUploadSuccess"
        :on-error="handleUploadError"
        :before-upload="beforeUpload"
        :show-file-list="false"
      >
        <el-button type="warning">导入Excel</el-button>
      </el-upload>
      <el-button type="info" @click="exportData">导出Excel</el-button>
      <el-button type="danger" plain @click="batchDelete">批量删除</el-button>
      <el-button type="primary" plain @click="batchSubmit">批量提交</el-button>

      <!-- 排序按钮 -->
      <el-button type="primary" plain @click="sortByField('po_no')">
        按订单号排序 {{ sortField === 'po_no' ? (sortOrder === 'asc' ? '↑' : '↓') : '' }}
      </el-button>
      <el-button type="primary" plain @click="sortByField('total_amount')">
        按金额排序 {{ sortField === 'total_amount' ? (sortOrder === 'asc' ? '↑' : '↓') : '' }}
      </el-button>
      <el-button type="primary" plain @click="sortByField('expected_date')">
        按预计到货日期排序 {{ sortField === 'expected_date' ? (sortOrder === 'asc' ? '↑' : '↓') : '' }}
      </el-button>
      <el-button type="primary" plain @click="sortByField('order_date')">
        按下单日期排序 {{ sortField === 'order_date' ? (sortOrder === 'asc' ? '↑' : '↓') : '' }}
      </el-button>

      <el-input
        v-model="searchKeyword"
        placeholder="全局搜索订单号/供应商"
        clearable
        style="width: 250px; margin-left: auto"
        @clear="loadOrders"
        @keyup.enter="loadOrders"
      />
      <el-button @click="loadOrders">搜索</el-button>
    </div>

    <!-- 表格（横向滚动） -->
    <div class="table-scroll-container" ref="tableScrollContainer" @mousemove="onTableMouseMove" @mouseleave="onTableMouseLeave">
      <el-table
        ref="multipleTable"
        :data="orderList"
        border
        stripe
        style="min-width: 1400px"
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="50" />
        <el-table-column type="index" label="序号" width="60" fixed="left" :index="indexMethod" />

        <el-table-column prop="po_no" label="订单号" min-width="160" sortable="custom" show-overflow-tooltip>
          <template #header>
            <div>
              <div>订单号</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.po_no" placeholder="输入筛选" size="small" clearable @input="handleTextFilter" />
                <el-popover placement="bottom" width="200" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <div style="max-height: 200px; overflow-y: auto">
                      <el-checkbox-group v-model="batch.po_nos">
                        <el-checkbox v-for="item in poNoOptions" :key="item" :value="item">{{ item }}</el-checkbox>
                      </el-checkbox-group>
                    </div>
                    <div style="margin-top: 10px; text-align: center">
                      <el-button size="small" @click="batch.po_nos = []">重置</el-button>
                      <el-button size="small" type="primary" @click="applyBatchFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="supplier_name" label="供应商" min-width="150" sortable="custom" show-overflow-tooltip>
          <template #header>
            <div>
              <div>供应商</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.supplier_name" placeholder="输入筛选" size="small" clearable @input="handleTextFilter" />
                <el-popover placement="bottom" width="200" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <div style="max-height: 200px; overflow-y: auto">
                      <el-checkbox-group v-model="batch.suppliers">
                        <el-checkbox v-for="item in supplierOptions" :key="item" :value="item">{{ item }}</el-checkbox>
                      </el-checkbox-group>
                    </div>
                    <div style="margin-top: 10px; text-align: center">
                      <el-button size="small" @click="batch.suppliers = []">重置</el-button>
                      <el-button size="small" type="primary" @click="applyBatchFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="buyer" label="采购员" min-width="100" sortable="custom">
          <template #header>
            <div>
              <div>采购员</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="filters.buyer" placeholder="输入筛选" size="small" clearable @input="handleTextFilter" />
                <el-popover placement="bottom" width="200" trigger="click">
                  <template #reference>
                    <el-button size="small">批量</el-button>
                  </template>
                  <div>
                    <div style="max-height: 200px; overflow-y: auto">
                      <el-checkbox-group v-model="batch.buyers">
                        <el-checkbox v-for="item in buyerOptions" :key="item" :value="item">{{ item }}</el-checkbox>
                      </el-checkbox-group>
                    </div>
                    <div style="margin-top: 10px; text-align: center">
                      <el-button size="small" @click="batch.buyers = []">重置</el-button>
                      <el-button size="small" type="primary" @click="applyBatchFilter">确认</el-button>
                    </div>
                  </div>
                </el-popover>
              </div>
            </div>
          </template>
        </el-table-column>
        
        <!-- 下单日期范围 -->
        <el-table-column prop="order_date" label="下单日期" width="260" sortable="custom">
          <template #header>
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>下单日期</span>
                <el-button size="small" text @click="sortByField('order_date')">
                  {{ sortField === 'order_date' ? (sortOrder === 'asc' ? '▲' : '▼') : '⇅' }}
                </el-button>
              </div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-date-picker
                  v-model="dateRange.order_date"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  value-format="YYYY-MM-DD"
                  :unlink-panels="true"
                  :default-value="new Date()" 
                  @change="handleDateRangeFilter"
                  style="flex: 1"
                />
                <el-button size="small" @click="clearDateRange('order_date')">清除</el-button>
              </div>
            </div>
          </template>
        </el-table-column>
 
        <!-- 预计到货日期范围 -->
        <el-table-column prop="expected_date" label="预计到货日期" width="260" sortable="custom">
          <template #header>
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>预计到货日期</span>
                <el-button size="small" text @click="sortByField('expected_date')">
                  {{ sortField === 'expected_date' ? (sortOrder === 'asc' ? '▲' : '▼') : '⇅' }}
                </el-button>
              </div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-date-picker
                  v-model="dateRange.expected_date"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  value-format="YYYY-MM-DD"
                  :unlink-panels="true"
                  :default-value="new Date()"  
                  @change="handleDateRangeFilter"
                  style="flex: 1"
                />
                <el-button size="small" @click="clearDateRange('expected_date')">清除</el-button>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 实际到货日期范围 -->
        <el-table-column prop="actual_receive_date" label="实际到货日期" width="260" sortable="custom">
          <template #header>
            <div>
              <div style="display: flex; justify-content: space-between; align-items: center;">
                <span>实际到货日期</span>
                <el-button size="small" text @click="sortByField('actual_receive_date')">
                  {{ sortField === 'actual_receive_date' ? (sortOrder === 'asc' ? '▲' : '▼') : '⇅' }}
                </el-button>
              </div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-date-picker
                  v-model="dateRange.actual_receive_date"
                  type="daterange"
                  range-separator="至"
                  start-placeholder="开始日期"
                  end-placeholder="结束日期"
                  size="small"
                  value-format="YYYY-MM-DD"
                  :unlink-panels="true"
                  :default-value="new Date()"  
                  @change="handleDateRangeFilter"
                  style="flex: 1"
                />
                <el-button size="small" @click="clearDateRange('actual_receive_date')">清除</el-button>
              </div>
            </div>
          </template>
        </el-table-column>

        <!-- 总金额列（带重置按钮） -->
        <el-table-column prop="total_amount" label="总金额" width="150" sortable="custom">
          <template #header>
            <div>
              <div>总金额</div>
              <div style="display: flex; gap: 4px; margin-top: 4px">
                <el-input v-model="amountMin" placeholder="最低" size="small" style="width: 45%" @input="handleAmountFilter" />
                <span>-</span>
                <el-input v-model="amountMax" placeholder="最高" size="small" style="width: 45%" @input="handleAmountFilter" />
                <el-button type="text" size="small" @click="resetAmount">重置</el-button>
              </div>
            </div>
          </template>
          <template #default="{ row }">
            ¥{{ Number(row.total_amount || 0).toFixed(2) }}
          </template>
        </el-table-column>

        <!-- 状态列（带重置按钮） -->
        <el-table-column prop="status" label="状态" width="120" sortable="custom">
          <template #header>
            <div>
              <div>状态</div>
              <div style="margin-top: 4px; display: flex; gap: 4px; align-items: center;">
                <el-select v-model="filters.status" placeholder="选择状态" size="small" clearable @change="handleSelectFilter" style="flex: 1;">
                  <el-option label="草稿" value="draft" />
                  <el-option label="已提交" value="submitted" />
                  <el-option label="已审核" value="approved" />
                  <el-option label="已收货" value="received" />
                  <el-option label="已完成" value="completed" />
                  <el-option label="已取消" value="cancelled" />
                </el-select>
                <el-button type="text" size="small" @click="resetStatus">重置</el-button>
              </div>
              <div style="font-size: 12px; color: #909399; margin-top: 4px;">
                流程：草稿 → 提交 → 审核 → 复核 → 审批 → 收货 → 检验 → 入库 → 结案
              </div>              
            </div>
          </template>
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)">{{ statusMap[row.status] || row.status_display || row.status }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" fixed="right" width="200">
          <template #default="{ row }">
            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
              <el-button link type="primary" @click="handleEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="handleDelete(row)">删除</el-button>
              <el-button link @click="viewDetail(row)">查看</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-pagination
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[10,20,50,100]"
      layout="total, sizes, prev, pager, next, jumper"
      @current-change="onPageChange"
      @size-change="onSizeChange"
      style="margin-top: 20px; justify-content: flex-end"
    />

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="900px" @closed="resetForm">
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="订单号" prop="po_no">
              <el-input v-model="form.po_no" placeholder="留空自动生成" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier_id" required>
              <el-select v-model="form.supplier_id" filterable placeholder="请选择供应商" style="width: 100%">
                <el-option v-for="s in supplierAll" :key="s.id" :label="`${s.code} - ${s.name}`" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="采购员" prop="buyer_id">
              <el-select v-model="form.buyer_id" filterable placeholder="请选择采购员" style="width: 100%">
                <el-option v-for="emp in employeeList" :key="emp.id" :label="emp.full_name" :value="emp.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="下单日期" prop="order_date">
              <el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="预计到货日期" prop="expected_date">
              <el-date-picker v-model="form.expected_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="实际到货日期" prop="actual_receive_date">
              <el-date-picker v-model="form.actual_receive_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 商品明细表格 -->
        <div style="margin: 20px 0">
          <div style="display: flex; justify-content: space-between; margin-bottom: 10px">
            <strong>商品明细</strong>
            <el-button type="primary" size="small" @click="addItemRow">添加商品</el-button>
          </div>
          <el-table :data="form.items" border>
            <el-table-column label="物料" width="200">
              <template #default="{ row, $index }">
                <el-select v-model="row.material_id" filterable placeholder="请选择物料" @change="onMaterialChange($index)">
                  <el-option v-for="m in materialList" :key="m.id" :label="`${m.name} (${m.code})`" :value="m.id" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="规格" width="120">
              <template #default="{ row }">{{ row.specification || '-' }}</template>
            </el-table-column>
            <el-table-column label="数量" width="100">
              <template #default="{ row, $index }">
                <el-input-number v-model="row.quantity" :min="1" size="small" @change="calcItemAmount($index)" style="width: 100%" />
              </template>
            </el-table-column>
            <el-table-column label="单价" width="100">
              <template #default="{ row }">¥{{ Number(row.unit_price || 0).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="金额" width="100">
              <template #default="{ row }">¥{{ Number(row.amount || 0).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="60">
              <template #default="{ $index }">
                <el-button link type="danger" @click="removeItemRow($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>

    <!-- 查看详情弹窗 -->
    <el-dialog v-model="viewDialogVisible" title="订单详情" width="800px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="订单号">{{ viewData.po_no }}</el-descriptions-item>
        <el-descriptions-item label="供应商">{{ viewData.supplier_name }}</el-descriptions-item>
        <el-descriptions-item label="采购员">{{ viewData.buyer }}</el-descriptions-item>
        <el-descriptions-item label="下单日期">{{ viewData.order_date }}</el-descriptions-item>
        <el-descriptions-item label="预计到货日期">{{ viewData.expected_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际到货日期">{{ viewData.actual_receive_date || '-' }}</el-descriptions-item>
        <el-descriptions-item label="总金额">¥{{ Number(viewData.total_amount || 0).toFixed(2) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ statusMap[viewData.status] || viewData.status_display || viewData.status }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">{{ viewData.remark || '-' }}</el-descriptions-item>
      </el-descriptions>
      <div style="margin-top: 20px">
        <strong>商品明细</strong>
        <el-table :data="viewData.items" border>
          <el-table-column label="物料名称" prop="material_name" />
          <el-table-column label="规格型号" prop="specification" />
          <el-table-column label="数量" prop="quantity" />
          <el-table-column label="单价" prop="unit_price" />
          <el-table-column label="金额" prop="amount" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="viewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '../api/request'

// ---------- 状态映射 ----------
const statusMap = {
  draft: '草稿',
  submitted: '已提交',
  approved: '已审核',
  approved: '已审核',
  reviewed: '已复核',
  final_approved: '已审批',
  received: '已收货',
  completed: '已完成',
  cancelled: '已取消'
}

// ---------- 列表数据 ----------
const orderList = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const searchKeyword = ref('')
const selectedRows = ref([])

// ---------- 筛选条件 ----------
const filters = reactive({ po_no: '', supplier_name: '', buyer: '', status: '' })
const amountMin = ref('')
const amountMax = ref('')
const dateRange = reactive({ order_date: [], expected_date: [], actual_receive_date: [] })
const batch = reactive({ po_nos: [], suppliers: [], buyers: [] })

const poNoOptions = computed(() => [...new Set(orderList.value.map(i => i.po_no).filter(Boolean))])
const supplierOptions = computed(() => [...new Set(orderList.value.map(i => i.supplier_name).filter(Boolean))])
const buyerOptions = computed(() => [...new Set(orderList.value.map(i => i.buyer).filter(Boolean))])

// ---------- 下拉数据 ----------
const supplierAll = ref([])
const employeeList = ref([])
const materialList = ref([])

// ---------- 排序 ----------
const sortField = ref('')
const sortOrder = ref('asc')
const handleSortChange = ({ prop, order }) => {
  sortField.value = prop
  sortOrder.value = order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : ''
  loadOrders()
}
const sortByField = (field) => {
  if (sortField.value === field) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortOrder.value = 'asc'
  }
  loadOrders()
}

// ---------- 弹窗 ----------
const dialogVisible = ref(false)
const viewDialogVisible = ref(false)
const dialogTitle = ref('')
const submitting = ref(false)
const formRef = ref(null)
const viewData = ref({ items: [] })

const form = ref({
  id: null,
  po_no: '',
  supplier_id: null,
  buyer_id: null,
  order_date: '',
  expected_date: '',
  actual_receive_date: '',
  total_amount: 0,
  status: 'draft',
  remark: '',
  items: []
})

const rules = {
  supplier_id: [{ required: true, message: '请选择供应商' }]
}

// ---------- 辅助函数 ----------
const indexMethod = idx => (currentPage.value - 1) * pageSize.value + idx + 1
const statusTagType = (status) => {
  const map = { draft: 'info', submitted: 'warning', approved: 'primary', received: 'success', completed: 'success', cancelled: 'danger' }
  return map[status] || 'info'
}

// ---------- 清除日期范围 ----------
const clearDateRange = (field) => {
  dateRange[field] = []
  loadOrders()
}

// ---------- 加载数据 ----------
const loadOrders = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      search: searchKeyword.value,
      po_no: filters.po_no,
      supplier_name: filters.supplier_name,
      buyer: filters.buyer,
      status: filters.status,
      total_amount_min: amountMin.value,
      total_amount_max: amountMax.value,
      order_date_start: dateRange.order_date?.[0],
      order_date_end: dateRange.order_date?.[1],
      expected_date_start: dateRange.expected_date?.[0],
      expected_date_end: dateRange.expected_date?.[1],
      actual_receive_date_start: dateRange.actual_receive_date?.[0],
      actual_receive_date_end: dateRange.actual_receive_date?.[1],
      po_no__in: batch.po_nos.join(','),
      supplier_name__in: batch.suppliers.join(','),
      buyer__in: batch.buyers.join(','),
      ordering: sortOrder.value ? `${sortOrder.value === 'asc' ? '' : '-'}${sortField.value}` : ''
    }
    Object.keys(params).forEach(k => {
      if (params[k] === undefined || params[k] === '') delete params[k]
      if (k.endsWith('__in') && !params[k]) delete params[k]
    })
    const res = await request.get('/procurement/purchase_orders/', { params })
    orderList.value = res.results || []
    total.value = res.count || 0
  } catch (e) {
    ElMessage.error('加载订单列表失败')
  }
}

const loadSuppliers = async () => {
  try {
    const res = await request.get('/procurement/suppliers/?page_size=1000')
    supplierAll.value = res.results || []
  } catch (e) { console.error(e) }
}
const loadEmployees = async () => {
  try {
    const res = await request.get('/pfm/employees/?page_size=1000')
    employeeList.value = res.results || []
  } catch (e) { console.error(e) }
}
const loadMaterials = async () => {
  try {
    const res = await request.get('/masterdata/materials/?page_size=1000')
    materialList.value = res.results || []
  } catch (e) { console.error(e) }
}

// ---------- 筛选事件 ----------
const handleTextFilter = () => { currentPage.value = 1; loadOrders() }
const handleSelectFilter = () => { currentPage.value = 1; loadOrders() }
const handleAmountFilter = () => { currentPage.value = 1; loadOrders() }
const handleDateRangeFilter = () => { currentPage.value = 1; loadOrders() }
const applyBatchFilter = () => { currentPage.value = 1; loadOrders() }

// 重置总金额
const resetAmount = () => {
  amountMin.value = ''
  amountMax.value = ''
  handleAmountFilter()
}
// 重置状态
const resetStatus = () => {
  filters.status = ''
  handleSelectFilter()
}

// ---------- 分页 ----------
const onPageChange = (page) => { currentPage.value = page; loadOrders() }
const onSizeChange = (size) => { pageSize.value = size; currentPage.value = 1; loadOrders() }

// ---------- 导入导出 ----------
const uploadUrl = 'http://127.0.0.1:8000/api/procurement/purchase_orders/import_excel/'
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token')}` }))

const beforeUpload = (file) => {
  const allowed = ['xlsx', 'xls', 'csv'].some(ext => file.name.endsWith(ext))
  if (!allowed) ElMessage.error('只能上传 Excel 或 CSV 文件')
  return allowed
}
const handleUploadSuccess = (res) => {
  if (res.success !== undefined) {
    ElMessage.success(`导入完成：成功 ${res.success} 条`)
    loadOrders()
  } else ElMessage.error(res.message || '导入失败')
}
const handleUploadError = () => ElMessage.error('导入失败')

const downloadTemplate = () => {
  const token = localStorage.getItem('token')
  fetch('http://127.0.0.1:8000/api/procurement/purchase_orders/export_template/', {
    headers: { Authorization: `Bearer ${token}` }
  }).then(res => res.blob()).then(blob => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'purchase_order_import_template.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  }).catch(() => ElMessage.error('下载模板失败'))
}

const exportData = () => {
  const token = localStorage.getItem('token')
  const selectedIds = selectedRows.value.map(row => row.id)
  let url = '/api/procurement/purchase_orders/export/'
  if (selectedIds.length > 0) url += `?ids=${selectedIds.join(',')}`
  fetch(url, { headers: { Authorization: `Bearer ${token}` } })
    .then(res => res.blob())
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `purchase_orders_${new Date().toISOString().slice(0,19)}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('导出成功')
    })
    .catch(() => ElMessage.error('导出失败'))
}

// ---------- 批量操作 ----------
const handleSelectionChange = (rows) => { selectedRows.value = rows }
const batchDelete = async () => {
  if (!selectedRows.value.length) return ElMessage.warning('请选择订单')
  await ElMessageBox.confirm(`删除 ${selectedRows.value.length} 条订单？`, '提示', { type: 'warning' })
  const ids = selectedRows.value.map(r => r.id)
  await request.post('/procurement/purchase_orders/batch_delete/', { ids })
  ElMessage.success('删除成功')
  loadOrders()
}
const batchSubmit = async () => {
  const draftRows = selectedRows.value.filter(r => r.status === 'draft')
  if (!draftRows.length) return ElMessage.warning('请选择草稿订单')
  await ElMessageBox.confirm(`提交 ${draftRows.length} 条订单？`, '提示', { type: 'info' })
  const ids = draftRows.map(r => r.id)
  await request.post('/procurement/purchase_orders/batch_submit/', { ids })
  ElMessage.success('提交成功')
  loadOrders()
}

// ---------- 单个订单操作 ----------
const handleDelete = async (row) => {
  await ElMessageBox.confirm(`确定删除订单 ${row.po_no} 吗？`, '提示', { type: 'warning' })
  await request.delete(`/procurement/purchase_orders/${row.id}/`)
  ElMessage.success('删除成功')
  loadOrders()
}

const viewDetail = async (row) => {
  const res = await request.get(`/procurement/purchase_orders/${row.id}/`)
  viewData.value = res
  viewDialogVisible.value = true
}

// ---------- 新增/编辑订单 ----------
const resetForm = () => {
  form.value = {
    id: null,
    po_no: '',
    supplier_id: null,
    buyer_id: null,
    order_date: '',
    expected_date: '',
    actual_receive_date: '',
    total_amount: 0,
    status: 'draft',
    remark: '',
    items: []
  }
}

const handleAdd = () => {
  dialogTitle.value = '新增订单'
  resetForm()
  dialogVisible.value = true
}

const handleEdit = async (row) => {
  dialogTitle.value = '编辑订单'
  const res = await request.get(`/procurement/purchase_orders/${row.id}/`)
  console.log('编辑获取的订单详情:', res)

  let supplierId = null
  if (typeof res.supplier === 'number') {
    supplierId = res.supplier
  } else if (res.supplier?.id) {
    supplierId = Number(res.supplier.id)
  } else if (res.supplier_id) {
    supplierId = Number(res.supplier_id)
  }

  let buyerId = null
  if (res.buyer_id) {
    buyerId = Number(res.buyer_id)
  } else if (res.buyer) {
    const matched = employeeList.value.find(emp => emp.full_name === res.buyer)
    buyerId = matched ? Number(matched.id) : null
  }

  const items = (res.items || []).map(item => {
    let mid = null
    if (typeof item.material === 'number') {
      mid = item.material
    } else if (item.material?.id) {
      mid = Number(item.material.id)
    } else if (item.material_id) {
      mid = Number(item.material_id)
    }
    return {
      material_id: mid,
      specification: item.specification || '',
      quantity: Number(item.quantity) || 1,
      unit_price: Number(item.unit_price) || 0,
      amount: Number(item.amount) || 0,
      material_name: item.material_name || ''
    }
  })

  form.value = {
    ...res,
    total_amount: Number(res.total_amount) || 0,
    supplier_id: supplierId,
    buyer_id: buyerId,
    items: items
  }

  await nextTick()
  console.log('编辑表单最终值:', form.value)
  dialogVisible.value = true
}

// 商品明细操作
const addItemRow = () => {
  form.value.items.push({ material_id: null, specification: '', quantity: 1, unit_price: 0, amount: 0 })
}
const removeItemRow = (idx) => {
  form.value.items.splice(idx, 1)
  calcTotalAmount()
}
const onMaterialChange = (idx) => {
  const item = form.value.items[idx]
  const material = materialList.value.find(m => m.id === item.material_id)
  if (material) {
    item.specification = material.specification || ''
    item.unit_price = Number(material.standard_cost) || Number(material.price) || 0
    calcItemAmount(idx)
  } else {
    item.specification = ''
    item.unit_price = 0
    calcItemAmount(idx)
  }
}
const calcItemAmount = (idx) => {
  const item = form.value.items[idx]
  const qty = Number(item.quantity) || 0
  const price = Number(item.unit_price) || 0
  item.amount = qty * price
  calcTotalAmount()
}
const calcTotalAmount = () => {
  form.value.total_amount = form.value.items.reduce((sum, i) => sum + (i.amount || 0), 0)
}

const submitForm = async () => {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    const submitData = {
      ...form.value,
      supplier_id: Number(form.value.supplier_id),
      company_id: 1,
      order_date: form.value.order_date ? form.value.order_date : new Date().toISOString().slice(0,10),
      expected_date: form.value.expected_date || null,
      actual_receive_date: form.value.actual_receive_date || null,
      buyer: form.value.buyer_id 
        ? employeeList.value.find(e => e.id === form.value.buyer_id)?.full_name 
        : form.value.buyer,
      items: form.value.items.map(i => ({
        material: i.material_id,
        quantity: i.quantity,
        unit_price: i.unit_price,
        amount: i.amount,
        specification: i.specification
      }))
    }
    if (submitData.supplier_id) {
      submitData.supplier = submitData.supplier_id
    }
    if (form.value.id) {
      await request.put(`/procurement/purchase_orders/${form.value.id}/`, submitData)
      ElMessage.success('编辑成功')
    } else {
      await request.post('/procurement/purchase_orders/', submitData)
      ElMessage.success('新增成功')
    }
    dialogVisible.value = false
    loadOrders()
  } catch (error) {
    console.error(error)
    ElMessage.error(form.value.id ? '编辑失败' : '新增失败')
  } finally {
    submitting.value = false
  }
}

// ---------- 横向滚动 ----------
const tableScrollContainer = ref(null)
let scrollTimer = null, scrollInterval = null
const onTableMouseMove = (e) => {
  const container = tableScrollContainer.value
  if (!container) return
  const rect = container.getBoundingClientRect()
  const x = e.clientX
  const threshold = 80
  clearTimeout(scrollTimer)
  clearInterval(scrollInterval)
  if (x > rect.right - threshold) {
    scrollTimer = setTimeout(() => {
      scrollInterval = setInterval(() => {
        if (container.scrollLeft < container.scrollWidth - container.clientWidth) {
          container.scrollBy({ left: 20, behavior: 'smooth' })
        } else clearInterval(scrollInterval)
      }, 50)
    }, 200)
  } else if (x < rect.left + threshold) {
    scrollTimer = setTimeout(() => {
      scrollInterval = setInterval(() => {
        if (container.scrollLeft > 0) {
          container.scrollBy({ left: -20, behavior: 'smooth' })
        } else clearInterval(scrollInterval)
      }, 50)
    }, 200)
  }
}
const onTableMouseLeave = () => {
  clearTimeout(scrollTimer)
  clearInterval(scrollInterval)
}

onMounted(() => {
  loadOrders()
  loadSuppliers()
  loadEmployees()
  loadMaterials()
})
</script>

<style scoped>
.table-scroll-container {
  overflow-x: auto;
  width: 100%;
  cursor: default;
  scroll-behavior: smooth;
}
.table-scroll-container::-webkit-scrollbar {
  height: 8px;
}
.table-scroll-container::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}
.table-scroll-container::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}
.table-scroll-container::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>