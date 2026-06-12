<template>
    <div class="system-position">
        <el-card>
            <h2>岗位管理</h2>

            <el-table v-loading="loading" :data="positions" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="name" label="岗位名称" />
                <el-table-column prop="code" label="岗位编码" />
                <el-table-column prop="department_name" label="所属部门" />
            </el-table>

            <div v-if="!loading && positions.length === 0" class="empty">
                暂无岗位数据
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPositions } from '../api/system'

const positions = ref([])
const loading = ref(false)

const fetchPositions = async () => {
    loading.value = true

    try {
        const res = await getPositions()

        if (res.success) {
            positions.value = res.data
        } else {
            ElMessage.error('获取岗位列表失败')
        }
    } catch (error) {
        console.error('获取岗位列表失败:', error)
        ElMessage.error('获取岗位列表失败')
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchPositions()
})
</script>

<style scoped>
.system-position {
    padding: 20px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>