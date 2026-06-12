<template>
    <div class="purchase-order-v2">
        <el-card>
            <div class="page-header">
                <h2>采购订单 V2</h2>
                <el-button type="primary" @click="openCreateDialog">
                    新增采购订单
                </el-button>
            </div>

            <el-form :model="filterForm" class="filter-form" inline>
                <el-form-item label="供应商">
                    <el-select
                        v-model="filterForm.supplier_name"
                        placeholder="请选择供应商"
                        clearable
                        filterable
                        style="width: 180px"
                    >
                        <el-option
                            v-for="item in supplierOptions"
                            :key="item.id"
                            :label="item.label"
                            :value="item.value"
                        />
                    </el-select>
                </el-form-item>

                <el-form-item label="采购员">
                    <el-select
                        v-model="filterForm.buyer_name"
                        placeholder="请选择采购员"
                        clearable
                        filterable
                        style="width: 160px"
                    >
                        <el-option
                            v-for="item in employeeOptions"
                            :key="item.id"
                            :label="item.label"
                            :value="item.value"
                        />
                    </el-select>
                </el-form-item>

                <el-form-item label="单据状态">
                    <el-select
                        v-model="filterForm.document_status"
                        placeholder="请选择单据状态"
                        clearable
                        style="width: 150px"
                    >
                        <el-option label="草稿" value="draft" />
                        <el-option label="已提交" value="submitted" />
                        <el-option label="已审核" value="audited" />
                        <el-option label="已复核" value="reviewed" />
                        <el-option label="已审批" value="approved" />
                    </el-select>
                </el-form-item>

                <el-form-item label="执行进度">
                    <el-select
                        v-model="filterForm.progress_status"
                        placeholder="请选择执行进度"
                        clearable
                        style="width: 150px"
                    >
                        <el-option label="未开始" value="not_started" />
                        <el-option label="已到货" value="arrived" />
                        <el-option label="已检验" value="inspected" />
                        <el-option label="已入库" value="warehoused" />
                        <el-option label="已结算" value="settled" />
                    </el-select>
                </el-form-item>

                <el-form-item>
                    <el-button type="primary" @click="handleSearch">
                        查询
                    </el-button>
                    <el-button @click="handleReset">
                        重置
                    </el-button>
                </el-form-item>
            </el-form>

            <el-table v-loading="loading" :data="orders" style="width: 100%">
                <el-table-column prop="po_no" label="采购订单号" width="160" />
                <el-table-column prop="supplier_name" label="供应商" width="160" />
                <el-table-column prop="buyer_name" label="采购员" width="120" />
                <el-table-column prop="purchase_department" label="物料申购部门" width="150" />
                <el-table-column prop="require_department" label="物料需求部门" width="150" />
                <el-table-column prop="order_date" label="下单日期" width="120" />
                <el-table-column prop="expected_date" label="预计到货日期" width="130" />
                <el-table-column prop="total_plan_amount" label="计划总金额" width="120" />
                <el-table-column prop="total_actual_amount" label="实际总金额" width="120" />

                <el-table-column label="单据状态" width="110">
                    <template #default="scope">
                        {{ getDocumentStatusName(scope.row.document_status) }}
                    </template>
                </el-table-column>

                <el-table-column label="执行进度" width="110">
                    <template #default="scope">
                        {{ getProgressStatusName(scope.row.progress_status) }}
                    </template>
                </el-table-column>

                <el-table-column label="紧急程度" width="100">
                    <template #default="scope">
                        {{ getUrgencyName(scope.row.urgency_level) }}
                    </template>
                </el-table-column>

                <el-table-column label="准交达成" width="100">
                    <template #default="scope">
                        <el-tag :type="scope.row.is_on_time_delivery ? 'success' : 'info'">
                            {{ scope.row.is_on_time_delivery ? '达成' : '未达成' }}
                        </el-tag>
                    </template>
                </el-table-column>
                <el-table-column label="操作" width="260" fixed="right">
                    <template #default="scope">

                        <el-button size="small" type="primary" @click="handleView(scope.row)">
                            查看
                        </el-button>

                        <el-button size="small" type="warning" @click="handleEdit(scope.row)"
                            v-if="scope.row.document_status === 'draft'">
                            编辑
                        </el-button>

                        <el-button size="small" type="success" @click="handleSubmit(scope.row)"
                            v-if="scope.row.document_status === 'draft'">
                            提交
                        </el-button>

                        <el-button size="small" type="success" @click="handleAudit(scope.row)"
                            v-if="scope.row.document_status === 'submitted'">
                            审核
                        </el-button>

                        <el-button size="small" type="warning" @click="handleReview(scope.row)"
                            v-if="scope.row.document_status === 'audited'">
                            复核
                        </el-button>

                        <el-button size="small" type="success" @click="handleApprove(scope.row)"
                            v-if="scope.row.document_status === 'reviewed'">
                            审批
                        </el-button>

                        <el-button size="small" type="primary" @click="handleArrive(scope.row)" v-if="
                            scope.row.document_status === 'approved'
                            &&
                            scope.row.progress_status === 'not_started'
                        ">
                            到货
                        </el-button>

                        <el-button size="small" type="warning" @click="handleInspect(scope.row)"
                            v-if="scope.row.progress_status === 'arrived'">
                            检验
                        </el-button>

                        <el-button size="small" type="primary" @click="handleWarehouse(scope.row)"
                            v-if="scope.row.progress_status === 'inspected'">
                            入库
                        </el-button>

                        <el-button size="small" type="success" @click="handleSettle(scope.row)"
                            v-if="scope.row.progress_status === 'warehoused'">
                            结算
                        </el-button>

                        <el-button size="small" type="danger" @click="handleDelete(scope.row)">
                            删除
                            </el-button>

                    </template>
                </el-table-column>
            </el-table>

            <div class="pagination-wrapper">
                <el-pagination
                    background
                    layout="total, sizes, prev, pager, next, jumper"
                    :total="total"
                    :page-size="pageSize"
                    :current-page="currentPage"
                    :page-sizes="[10, 20, 50, 100]"
                    @current-change="handleCurrentChange"
                    @size-change="handleSizeChange"
                />
            </div>

            <div v-if="!loading && orders.length === 0" class="empty">
                暂无采购订单数据
            </div>
        </el-card>

        <el-dialog v-model="dialogVisible" :title="isEditMode ? '编辑采购订单' : '新增采购订单'" width="900px">
            <el-form :model="form" label-width="120px">
                <el-row :gutter="16">
                    <el-col :span="12">
                        <el-form-item label="供应商">

                            <el-select v-model="form.supplier_name" placeholder="请选择供应商" filterable clearable
                                style="width:100%">

                                <el-option v-for="item in supplierOptions" :key="item.id" :label="item.label"
                                    :value="item.value" />

                            </el-select>

                        </el-form-item>
                    </el-col>

                    <el-col :span="12">
                        <el-form-item label="采购员">
                            <el-select v-model="form.buyer_name" filterable clearable placeholder="请选择采购员"
                                style="width: 100%">
                                <el-option v-for="item in employeeOptions" :key="item.id" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                        </el-form-item>
                    </el-col>

                    <el-col :span="12">
                        <el-form-item label="物料申购部门">
                            <el-select v-model="form.purchase_department" filterable clearable placeholder="请选择申购部门"
                                style="width: 100%">
                                <el-option v-for="item in departmentOptions" :key="item.id" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                        </el-form-item>
                    </el-col>

                    <el-col :span="12">
                        <el-form-item label="物料需求部门">
                            <el-select v-model="form.require_department" filterable clearable placeholder="请选择需求部门"
                                style="width: 100%">
                                <el-option v-for="item in departmentOptions" :key="item.id" :label="item.label"
                                    :value="item.value" />
                            </el-select>
                        </el-form-item>
                    </el-col>

                    <el-col :span="12">
                        <el-form-item label="下单日期">
                            <el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD"
                                style="width: 100%" />
                        </el-form-item>
                    </el-col>

                    <el-col :span="12">
                        <el-form-item label="预计到货日期">
                            <el-date-picker v-model="form.expected_date" type="date" value-format="YYYY-MM-DD"
                                style="width: 100%" />
                        </el-form-item>
                    </el-col>

                    <el-col :span="12">
                        <el-form-item label="紧急程度">
                            <el-select v-model="form.urgency_level" style="width: 100%">
                                <el-option label="特急" value="very_urgent" />
                                <el-option label="紧急" value="urgent" />
                                <el-option label="一般" value="normal" />
                                <el-option label="宽松" value="loose" />
                                <el-option label="已完成" value="completed" />
                                <el-option label="未计划" value="no_plan" />
                            </el-select>
                        </el-form-item>
                    </el-col>

                    <el-col :span="24">
                        <el-form-item label="备注">
                            <el-input v-model="form.remark" type="textarea" :rows="3" />
                        </el-form-item>
                    </el-col>
                    <el-divider>采购物料明细</el-divider>

                    <el-button type="primary" @click="addItem" style="margin-bottom:10px">
                        新增物料
                    </el-button>

                    <el-table :data="form.items" border size="small">
                        <el-table-column label="物料名称" min-width="220">
                            <template #default="{ row }">
                                <el-select v-model="row.material_id" filterable clearable placeholder="请选择物料"
                                    style="width: 100%" @change="value => handleMaterialChange(row, value)">
                                    <el-option v-for="item in materialOptions" :key="item.id" :label="item.label"
                                        :value="item.id" />
                                </el-select>
                            </template>
                        </el-table-column>

                        <el-table-column label="物料编码" prop="material_code" width="120" />

                        <el-table-column label="规格型号" prop="specification" width="140" />

                        <el-table-column label="单位" prop="unit" width="80" />

                        <el-table-column label="计划数量" width="120">
                            <template #default="{ row }">
                                <el-input-number v-model="row.plan_quantity" :min="0" controls controls-position=""
                                    style="width: 120px" />
                            </template>
                        </el-table-column>

                        <el-table-column label="计划单价" width="120">
                            <template #default="{ row }">
                                <el-input-number v-model="row.plan_unit_price" :min="0" controls controls-position=""
                                    style="width: 120px" />
                            </template>
                        </el-table-column>

                        <el-table-column label="计划金额" width="140">
                            <template #default="{ row }">
                                {{ (Number(row.plan_quantity || 0) * Number(row.plan_unit_price || 0)).toFixed(2) }}
                            </template>
                        </el-table-column>

                        <el-table-column label="操作" width="100" fixed="right">
                            <template #default="{ $index }">
                                <el-button type="danger" size="small" @click="removeItem($index)">
                                    删除
                                </el-button>
                            </template>
                        </el-table-column>
                    </el-table>
                </el-row>
            </el-form>

            <template #footer>
                <el-button @click="dialogVisible = false">
                    取消
                </el-button>
                <el-button type="primary" @click="handleCreate">
                    保存
                </el-button>
            </template>
        </el-dialog>
        <el-dialog v-model="detailVisible" title="采购订单详情" width="1000px">
            <div v-if="currentOrder">
                <el-descriptions title="订单基本信息" :column="2" border>
                    <el-descriptions-item label="采购订单号">
                        {{ currentOrder.po_no }}
                    </el-descriptions-item>

                    <el-descriptions-item label="供应商">
                        {{ currentOrder.supplier_name }}
                    </el-descriptions-item>

                    <el-descriptions-item label="采购员">
                        {{ currentOrder.buyer_name }}
                    </el-descriptions-item>

                    <el-descriptions-item label="物料申购部门">
                        {{ currentOrder.purchase_department }}
                    </el-descriptions-item>

                    <el-descriptions-item label="物料需求部门">
                        {{ currentOrder.require_department }}
                    </el-descriptions-item>

                    <el-descriptions-item label="下单日期">
                        {{ currentOrder.order_date }}
                    </el-descriptions-item>

                    <el-descriptions-item label="预计到货日期">
                        {{ currentOrder.expected_date }}
                    </el-descriptions-item>

                    <el-descriptions-item label="实际到货日期">
                        {{ currentOrder.actual_receive_date }}
                    </el-descriptions-item>

                    <el-descriptions-item label="计划总金额">
                        {{ currentOrder.total_plan_amount }}
                    </el-descriptions-item>
                </el-descriptions>

                <h3 style="margin-top: 20px;">采购物料明细</h3>

                <el-table :data="currentOrder.items || []" border style="width: 100%">
                    <el-table-column prop="material_name" label="物料名称" width="180" />
                    <el-table-column prop="material_code" label="物料编码" width="120" />
                    <el-table-column prop="specification" label="规格型号" width="160" />
                    <el-table-column prop="unit" label="单位" width="80" />
                    <el-table-column prop="plan_quantity" label="计划数量" width="120" />
                    <el-table-column prop="plan_unit_price" label="计划单价" width="120" />
                    <el-table-column prop="plan_amount" label="计划金额" width="120" />
                </el-table>
            </div>

            <template #footer>
                <el-button @click="detailVisible = false">
                    关闭
                </el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
    getPurchaseOrders,
    createPurchaseOrder,
    updatePurchaseOrder,
    deletePurchaseOrder,
    getPurchaseBaseOptions
} from '../api/purchase'

import {
    getDepartments,
    getUsers
} from '../api/system'

const loading = ref(false)
const orders = ref([])
const filterForm = ref({
    supplier_name: '',
    buyer_name: '',
    document_status: '',
    progress_status: ''
})
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const employeeOptions = ref([])
const supplierOptions = ref([])
const departmentOptions = ref([])
const materialOptions = ref([])
const departments = ref([])
const users = ref([])
const dialogVisible = ref(false)
const detailVisible = ref(false)
const currentOrder = ref(null)
const isEditMode = ref(false)
const editingOrderId = ref(null)

const handleInspect = async (row) => {
    try {
        const payload = {
            progress_status: 'inspected'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('检验完成')

        fetchOrders()
    } catch (error) {
        console.error(error)
        ElMessage.error('检验失败')
    }
}

const handleWarehouse = async (row) => {
    try {
        const payload = {
            progress_status: 'warehoused'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('入库完成')

        fetchOrders()
    } catch (error) {
        console.error(error)
        ElMessage.error('入库失败')
    }
}

const handleSettle = async (row) => {
    try {
        const payload = {
            progress_status: 'settled'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('结算完成')

        fetchOrders()
    } catch (error) {
        console.error(error)
        ElMessage.error('结算失败')
    }
}

const form = ref({
    po_no: '',
    supplier_name: '',
    buyer_name: '',
    purchase_department: '',
    require_department: '',
    order_date: '',
    expected_date: '',
    actual_receive_date: '',
    total_plan_amount: 0,
    total_actual_amount: 0,
    document_status: 'draft',
    progress_status: 'not_started',
    urgency_level: 'normal',
    is_on_time_delivery: false,
    remark: '',
    items: []
})

const getDocumentStatusName = (value) => {
    const map = {
        draft: '草稿',
        submitted: '已提交',
        audited: '已审核',
        reviewed: '已复核',
        approved: '已审批',
        rejected: '已驳回',
        cancelled: '已作废',
        closed: '已关闭',
        finished: '已结案'
    }
    return map[value] || value
}

const getProgressStatusName = (value) => {
    const map = {
        not_started: '未开始',
        arriving: '到货中',
        arrived: '已到货',
        inspecting: '检验中',
        inspected: '已检验',
        warehousing: '入库中',
        warehoused: '已入库',
        settling: '结算中',
        settled: '已结算',
        finished: '已结案'
    }
    return map[value] || value
}

const getUrgencyName = (value) => {
    const map = {
        very_urgent: '特急',
        urgent: '紧急',
        normal: '一般',
        loose: '宽松',
        completed: '已完成',
        no_plan: '未计划'
    }
    return map[value] || value
}

const resetForm = () => {
    form.value = {
        po_no: '',
        supplier_name: '',
        buyer_name: '',
        purchase_department: '',
        require_department: '',
        order_date: '',
        expected_date: '',
        actual_receive_date: '',
        total_plan_amount: 0,
        total_actual_amount: 0,
        document_status: 'draft',
        progress_status: 'not_started',
        urgency_level: 'normal',
        is_on_time_delivery: false,
        remark: '',
        items: []
    }
}

const fetchDepartments = async () => {
    try {
        const res = await getDepartments()

        if (res.success) {
            departments.value = res.data
        }
    } catch (e) {
        console.error(e)
    }
}

const fetchBaseOptions = async () => {
    try {
        const res = await getPurchaseBaseOptions()

        if (res.success) {
            employeeOptions.value = res.employees || []
            supplierOptions.value = res.suppliers || []
            departmentOptions.value = res.departments || []
            materialOptions.value = res.materials || []
        }
    } catch (error) {
        console.error('获取采购基础数据失败:', error)
        ElMessage.error('获取采购基础数据失败')
    }
}

const fetchOrders = async () => {
    loading.value = true

    try {
        const res = await getPurchaseOrders({
            page: currentPage.value,
            page_size: pageSize.value,
            supplier_name: filterForm.value.supplier_name,
            buyer_name: filterForm.value.buyer_name,
            document_status: filterForm.value.document_status,
            progress_status: filterForm.value.progress_status
        })

        if (res.results) {
            orders.value = res.results
            total.value = res.count || 0
        } else {
            orders.value = res || []
            total.value = Array.isArray(res) ? res.length : 0
        }
    } catch (error) {
        console.error('获取采购订单失败:', error)
        ElMessage.error('获取采购订单失败')
    } finally {
        loading.value = false
    }
}

const handleCurrentChange = (page) => {
    currentPage.value = page
    fetchOrders()
}

const handleSizeChange = (size) => {
    pageSize.value = size
    currentPage.value = 1
    fetchOrders()
}

const handleSearch = () => {
    currentPage.value = 1
    fetchOrders()
}

const handleReset = () => {
    filterForm.value = {
        supplier_name: '',
        buyer_name: '',
        document_status: '',
        progress_status: ''
    }

    currentPage.value = 1
    fetchOrders()
}

const handleMaterialChange = (row, materialId) => {
    const material = materialOptions.value.find(item => item.id === materialId)

    if (!material) {
        return
    }

    row.material_id = material.id
    row.material_code = material.code
    row.material_name = material.name
    row.specification = material.specification
    row.unit = material.unit
    row.plan_price = material.price
    row.plan_unit_price = material.price
}

const findMaterialIdForEdit = (item) => {
    const material = materialOptions.value.find(materialItem => {
        return (
            materialItem.code === item.material_code ||
            materialItem.name === item.material_name
        )
    })

    return material ? material.id : null
}

const addItem = () => {
    form.value.items.push({
        material_id: null,
        material_code: '',
        material_name: '',
        specification: '',
        unit: '',
        plan_quantity: 0,
        plan_unit_price: 0,
        plan_amount: 0,
        actual_quantity: 0,
        actual_unit_price: 0,
        actual_amount: 0,
        plan_delivery_date: '',
        actual_delivery_date: '',
        remark: ''
    })
}

const removeItem = (index) => {
    form.value.items.splice(index, 1)
}

const openCreateDialog = () => {
    resetForm()
    dialogVisible.value = true
}

const handleCreate = async () => {
    const payload = { ...form.value }

    delete payload.po_no

    if (!payload.order_date) {
        payload.order_date = null
    }

    if (!payload.expected_date) {
        payload.expected_date = null
    }

    if (!payload.actual_receive_date) {
        payload.actual_receive_date = null
    }

    payload.items = form.value.items.map(item => ({
        material_code: item.material_code,
        material_name: item.material_name,
        specification: item.specification,
        unit: item.unit,
        plan_quantity: item.plan_quantity || 0,
        plan_unit_price: item.plan_unit_price || 0,
        plan_amount: Number(item.plan_quantity || 0) * Number(item.plan_unit_price || 0),
        actual_quantity: item.actual_quantity || 0,
        actual_unit_price: item.actual_unit_price || 0,
        actual_amount: 0,
        plan_delivery_date: item.plan_delivery_date || null,
        actual_delivery_date: item.actual_delivery_date || null,
        remark: item.remark || ''
    }))

    try {
        if (isEditMode.value && editingOrderId.value) {
            await updatePurchaseOrder(editingOrderId.value, payload)
            ElMessage.success('采购订单编辑成功')
        } else {
            await createPurchaseOrder(payload)
            ElMessage.success('采购订单创建成功')
        }

        dialogVisible.value = false
        fetchOrders()
    } catch (error) {
        console.error('创建采购订单失败:', error)
        ElMessage.error('创建采购订单失败')
    }
}

const handleView = (row) => {
    currentOrder.value = row
    detailVisible.value = true
}

const handleEdit = (row) => {
    isEditMode.value = true
    editingOrderId.value = row.id

    form.value = {
        po_no: row.po_no || '',
        supplier_name: row.supplier_name || '',
        buyer_name: row.buyer_name || '',
        purchase_department: row.purchase_department || '',
        require_department: row.require_department || '',
        order_date: row.order_date || '',
        expected_date: row.expected_date || '',
        actual_receive_date: row.actual_receive_date || '',
        total_plan_amount: row.total_plan_amount || 0,
        total_actual_amount: row.total_actual_amount || 0,
        document_status: row.document_status || 'draft',
        progress_status: row.progress_status || 'not_started',
        urgency_level: row.urgency_level || 'normal',
        is_on_time_delivery: row.is_on_time_delivery || false,
        remark: row.remark || '',
        items: (row.items || []).map(item => ({
            material_id: item.material_id || findMaterialIdForEdit(item),
            material_code: item.material_code || '',
            material_name: item.material_name || '',
            specification: item.specification || '',
            unit: item.unit || '',
            plan_quantity: Number(item.plan_quantity || 0),
            plan_unit_price: Number(item.plan_unit_price || 0),
            plan_amount: Number(item.plan_amount || 0),
            actual_quantity: Number(item.actual_quantity || 0),
            actual_unit_price: Number(item.actual_unit_price || 0),
            actual_amount: Number(item.actual_amount || 0),
            plan_delivery_date: item.plan_delivery_date || '',
            actual_delivery_date: item.actual_delivery_date || '',
            remark: item.remark || ''
        }))
    }

    dialogVisible.value = true
}

const handleDelete = async (row) => {
    try {
        await ElMessageBox.confirm(
            `确定要删除采购订单【${row.po_no}】吗？删除后不可恢复。`,
            '删除确认',
            {
                confirmButtonText: '确定删除',
                cancelButtonText: '取消',
                type: 'warning'
            }
        )

        await deletePurchaseOrder(row.id)

        ElMessage.success('采购订单删除成功')
        fetchOrders()
    } catch (error) {
        if (error !== 'cancel') {
            console.error('删除采购订单失败:', error)
            ElMessage.error('删除采购订单失败')
        }
    }
}

const handleSubmit = async (row) => {
    try {
        const payload = {
            document_status: 'submitted'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('采购订单提交成功')

        fetchOrders()
    } catch (error) {
        console.error(error)
        ElMessage.error('采购订单提交失败')
    }
}

const handleAudit = async (row) => {
    try {
        const payload = {
            document_status: 'audited'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('采购订单审核成功')

        fetchOrders()
    } catch (error) {
        console.error(error)
        ElMessage.error('采购订单审核失败')
    }
}

const handleReview = async (row) => {
    try {

        const payload = {
            document_status: 'reviewed'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('采购订单复核成功')

        fetchOrders()

    } catch (error) {

        console.error(error)

        ElMessage.error('采购订单复核失败')

    }
}

const handleApprove = async (row) => {
    try {
        const payload = {
            document_status: 'approved',
            progress_status: 'not_started'
        }

        await updatePurchaseOrder(row.id, payload)

        ElMessage.success('采购订单审批成功')

        fetchOrders()
    } catch (error) {
        console.error(error)
        ElMessage.error('采购订单审批失败')
    }
}

const handleArrive = async (row) => {
    try {

        const today = new Date()

        const dateString =
            today.getFullYear()
            + '-'
            + String(today.getMonth() + 1).padStart(2, '0')
            + '-'
            + String(today.getDate()).padStart(2, '0')

        const payload = {
            progress_status: 'arrived',
            actual_receive_date: dateString
        }

        await updatePurchaseOrder(
            row.id,
            payload
        )

        ElMessage.success('到货登记成功')

        fetchOrders()

    } catch (error) {

        console.error(error)

        ElMessage.error('到货登记失败')

    }
}



onMounted(() => {
    fetchBaseOptions()
    fetchOrders()
})
</script>

<style scoped>
.filter-form {
    margin-bottom: 16px;
    padding: 12px;
    background: #f7f9fc;
    border-radius: 6px;
}

.pagination-wrapper {
    margin-top: 16px;
    display: flex;
    justify-content: flex-end;
}

.purchase-order-v2 {
    padding: 20px;
}

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>