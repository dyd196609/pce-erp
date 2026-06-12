<template>
    <div class="system-user">
        <el-card>
            <h2>用户管理</h2>

            <el-table v-loading="loading" :data="users" style="width: 100%">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="username" label="登录账号" />
                <el-table-column prop="real_name" label="真实姓名" />
                <el-table-column prop="email" label="邮箱" />
                <el-table-column prop="mobile" label="手机号" />
                <el-table-column prop="company_id" label="公司ID" width="100" />
                <el-table-column label="状态" width="100">
                    <template #default="scope">
                        <el-tag :type="scope.row.is_active ? 'success' : 'danger'">
                            {{ scope.row.is_active ? '启用' : '禁用' }}
                        </el-tag>
                    </template>
                </el-table-column>
            </el-table>

            <div v-if="!loading && users.length === 0" class="empty">
                暂无用户数据
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getUsers } from '../api/system'

const users = ref([])
const loading = ref(false)

const fetchUsers = async () => {
    loading.value = true

    try {
        const res = await getUsers()

        if (res.success) {
            users.value = res.data
        } else {
            ElMessage.error('获取用户列表失败')
        }
    } catch (error) {
        console.error('获取用户列表失败:', error)
        ElMessage.error('获取用户列表失败')
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchUsers()
})
</script>

<style scoped>
.system-user {
    padding: 20px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>