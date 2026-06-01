<template>
    <div>
        <h2>采购报表</h2>

        <!-- 筛选栏 -->
        <div class="filter-bar">
            <el-date-picker v-model="dateRange" type="daterange" range-separator="至" start-placeholder="开始日期"
                end-placeholder="结束日期" @change="loadData" />
            <el-select v-model="filters.supplier_id" placeholder="供应商" clearable filterable @change="loadData">
                <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id" />
            </el-select>
            <el-select v-model="filters.buyer" placeholder="采购员" clearable @change="loadData">
                <el-option v-for="b in buyerList" :key="b" :label="b" :value="b" />
            </el-select>
            <el-select v-model="filters.department_id" placeholder="部门" clearable @change="loadData">
                <el-option v-for="d in departmentList" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-button type="primary" @click="loadData">查询</el-button>
            <el-button @click="resetFilters">重置</el-button>
        </div>

        <el-tabs v-model="activeTab">
            <el-tab-pane label="部门采购表" name="department">
                <el-table :data="departmentData" border stripe>
                    <el-table-column prop="department_name" label="部门名称" />
                    <el-table-column prop="total_amount" label="采购金额" />
                    <el-table-column prop="order_count" label="订单数量" />
                    <el-table-column prop="amount_diff_rate" label="金额差异率(%)" />
                    <el-table-column prop="percentage" label="占比(%)" />
                </el-table>
            </el-tab-pane>

            <el-tab-pane label="采购员绩效表" name="buyer">
                <el-table :data="buyerData" border stripe>
                    <el-table-column prop="buyer_name" label="采购员" />
                    <el-table-column prop="total_amount" label="采购金额" />
                    <el-table-column prop="order_count" label="订单数量" />
                    <el-table-column prop="avg_amount" label="平均金额" />
                    <el-table-column prop="on_time_rate" label="准交率(%)" />
                    <el-table-column prop="price_diff_rate" label="单价差异率(%)" />
                    <el-table-column prop="amount_diff_rate" label="金额差异率(%)" />
                    <el-table-column prop="percentage" label="占比(%)" />
                </el-table>
            </el-tab-pane>

            <el-tab-pane label="供应商绩效表" name="supplier">
                <el-table :data="supplierData" border stripe>
                    <el-table-column prop="supplier_name" label="供应商" />
                    <el-table-column prop="total_amount" label="采购金额" />
                    <el-table-column prop="order_count" label="订单数量" />
                    <el-table-column prop="avg_amount" label="平均金额" />
                    <el-table-column prop="on_time_rate" label="准交率(%)" />
                    <el-table-column prop="avg_delivery_days" label="平均交货周期(天)" />
                    <el-table-column prop="price_diff_rate" label="单价差异率(%)" />
                    <el-table-column prop="percentage" label="占比(%)" />
                </el-table>
            </el-tab-pane>
        </el-tabs>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import request from '../api/request'

const activeTab = ref('department')
const dateRange = ref([])
const filters = ref({ supplier_id: '', buyer: '', department_id: '' })

const supplierList = ref([])
const buyerList = ref([])
const departmentList = ref([])

const departmentData = ref([])
const buyerData = ref([])
const supplierData = ref([])

// 加载筛选选项
const loadOptions = async () => {
    try {
        const [suppliersRes, buyersRes] = await Promise.all([
            request.get('/api/procurement/suppliers/?page_size=1000'),
            request.get('/api/procurement/reports/buyer-performance/')
        ])
        supplierList.value = suppliersRes.results || []
        if (buyersRes.data) {
            buyerList.value = [...new Set(buyersRes.data.map(b => b.buyer_name))] // 去重
        }
        // 部门列表 - 修复路径
        const deptRes = await request.get('/api/pfm/departments/')  // 修改为正确路径
        departmentList.value = deptRes.results || []
    } catch (error) {
        console.error('加载选项失败:', error)
    }
}

const loadData = async () => {
    try {
        const formatDate = (date) => {
            if (!date) return ''
            const d = new Date(date)
            return d.toISOString().slice(0, 10)
        }

        const params = {}
        if (dateRange.value?.[0]) params.start_date = formatDate(dateRange.value[0])
        if (dateRange.value?.[1]) params.end_date = formatDate(dateRange.value[1])
        if (filters.value.supplier_id) params.supplier_id = filters.value.supplier_id
        if (filters.value.buyer) params.buyer = filters.value.buyer
        if (filters.value.department_id) params.department_id = filters.value.department_id

        console.log('查询参数:', params)  // 调试用

        const [deptRes, buyerRes, supplierRes] = await Promise.all([
            request.get('/api/procurement/reports/department-purchase/', { params }),
            request.get('/api/procurement/reports/buyer-performance/', { params }),
            request.get('/api/procurement/reports/supplier-performance/', { params })
        ])
        departmentData.value = deptRes.data || []
        buyerData.value = buyerRes.data || []
        supplierData.value = supplierRes.data || []
    } catch (error) {
        console.error('加载报表失败:', error)
        ElMessage.error('加载报表数据失败')
    }
}

const resetFilters = () => {
    dateRange.value = []
    filters.value = { supplier_id: '', buyer: '', department_id: '' }
    loadData()
}

onMounted(() => {
    loadOptions()
    loadData()
})
</script>

<style scoped>
.filter-bar {
    margin-bottom: 20px;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
}
</style>