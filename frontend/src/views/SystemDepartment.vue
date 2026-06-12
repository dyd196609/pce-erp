<template>
    <div class="system-department">
        <el-card>
            <h2>部门管理</h2>
            <el-table v-if="departments.length" :data="departments" style="width: 100%" :loading="loading">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="name" label="部门名称" />
                <el-table-column prop="code" label="部门编码" />
            </el-table>
            <div v-else-if="!loading" class="empty">
                暂无部门数据
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getDepartments } from '../api/system';
import { ElMessage } from 'element-plus';

const departments = ref([]);
const loading = ref(false);

const fetchDepartments = async () => {
    loading.value = true;
    try {
        const res = await getDepartments();
        departments.value = res;
    } catch (error) {
        console.error('获取部门列表失败:', error);
        ElMessage.error('获取部门列表失败');
    } finally {
        loading.value = false;
    }
};

onMounted(() => {
    fetchDepartments();
});
</script>

<style scoped>
.system-department {
    padding: 20px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>