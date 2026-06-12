<template>
    <div class="system-permission">
        <el-card>
            <h2>权限管理</h2>

            <el-table v-loading="loading" :data="permissions" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="code" label="权限编码" />
                <el-table-column prop="name" label="权限名称" />
                <el-table-column prop="module" label="所属模块" />
            </el-table>

            <div v-if="!loading && permissions.length === 0" class="empty">
                暂无权限数据
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getPermissions } from '../api/system'

const permissions = ref([])
const loading = ref(false)

const fetchPermissions = async () => {
    loading.value = true

    try {
        const res = await getPermissions()

        if (res.success) {
            permissions.value = res.data
        } else {
            ElMessage.error('获取权限列表失败')
        }
    } catch (error) {
        console.error('获取权限列表失败:', error)
        ElMessage.error('获取权限列表失败')
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchPermissions()
})
</script>

<style scoped>
.system-permission {
    padding: 20px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>