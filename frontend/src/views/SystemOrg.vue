<template>
    <div class="system-org">
        <el-card>
            <h2>组织架构</h2>

            <el-tree v-loading="loading" :data="treeData" node-key="id" default-expand-all :props="treeProps">
                <template #default="{ data }">
                    <span class="tree-node">
                        <el-tag size="small" :type="getTagType(data.type)">
                            {{ getTypeName(data.type) }}
                        </el-tag>
                        <span class="node-label">{{ data.label }}</span>
                    </span>
                </template>
            </el-tree>

            <div v-if="!loading && treeData.length === 0" class="empty">
                暂无组织架构数据
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getOrgTree } from '../api/system'

const treeData = ref([])
const loading = ref(false)

const treeProps = {
    children: 'children',
    label: 'label'
}

const getTypeName = (type) => {
    const map = {
        company: '公司',
        department: '部门',
        workshop: '车间',
        team: '班组',
        process: '工序'
    }

    return map[type] || type
}

const getTagType = (type) => {
    const map = {
        company: 'primary',
        department: 'success',
        workshop: 'warning',
        team: 'info',
        process: 'danger'
    }

    return map[type] || 'info'
}

const fetchOrgTree = async () => {
    loading.value = true

    try {
        const res = await getOrgTree()

        if (res.success) {
            treeData.value = res.data
        } else {
            ElMessage.error('获取组织架构失败')
        }
    } catch (error) {
        console.error('获取组织架构失败:', error)
        ElMessage.error('获取组织架构失败')
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    fetchOrgTree()
})
</script>

<style scoped>
.system-org {
    padding: 20px;
}

.tree-node {
    display: flex;
    align-items: center;
    gap: 8px;
}

.node-label {
    font-size: 14px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>