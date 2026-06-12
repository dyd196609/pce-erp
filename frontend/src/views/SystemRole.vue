<template>
    <div class="system-role">
        <el-card>
            <h2>角色管理</h2>

            <el-table v-loading="loading" :data="roles" style="width: 100%" highlight-current-row
                @row-click="handleRoleClick">
                <el-table-column prop="id" label="ID" width="80" />
                <el-table-column prop="name" label="角色名称" />
                <el-table-column prop="code" label="角色编码" />
                <el-table-column prop="description" label="描述" />
            </el-table>
        </el-card>

        <el-card class="menu-card">
            <h2>菜单权限配置</h2>

            <div v-if="!currentRole" class="empty">
                请先点击上方角色列表中的一个角色
            </div>

            <div v-else>
                <div class="current-role">
                    当前角色：{{ currentRole.name }}（{{ currentRole.code }}）
                </div>

                <el-tree ref="menuTreeRef" v-loading="menuLoading" :data="menus" node-key="id" show-checkbox
                    default-expand-all :check-strictly="false" :props="treeProps" />

                <div class="actions">
                    <el-button type="primary" @click="handleSaveMenus">
                        保存菜单权限
                    </el-button>
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import {
    getRoles,
    getMenus,
    getRoleMenuIds,
    saveRoleMenus
} from '../api/system'

const roles = ref([])
const menus = ref([])
const currentRole = ref(null)
const loading = ref(false)
const menuLoading = ref(false)
const menuTreeRef = ref(null)

const treeProps = {
    children: 'children',
    label: 'name'
}

const getLeafMenuIds = (nodes) => {
    const ids = []

    const walk = (items) => {
        items.forEach(item => {
            if (item.children && item.children.length > 0) {
                walk(item.children)
            } else {
                ids.push(item.id)
            }
        })
    }

    walk(nodes)
    return ids
}

const filterLeafIds = (ids) => {
    const leafIds = getLeafMenuIds(menus.value)
    return ids.filter(id => leafIds.includes(id))
}

const fetchRoles = async () => {
    loading.value = true

    try {
        const res = await getRoles()

        if (res.success) {
            roles.value = res.data
        } else {
            ElMessage.error('获取角色列表失败')
        }
    } catch (error) {
        console.error('获取角色列表失败:', error)
        ElMessage.error('获取角色列表失败')
    } finally {
        loading.value = false
    }
}

const fetchMenus = async () => {
    const res = await getMenus()

    if (res.success) {
        menus.value = res.data
    }
}

const handleRoleClick = async (row) => {
    currentRole.value = row
    menuLoading.value = true

    try {
        await fetchMenus()

        const res = await getRoleMenuIds(row.id)

        if (res.success) {
            await nextTick()
            const leafCheckedIds = filterLeafIds(res.data)
            menuTreeRef.value.setCheckedKeys(leafCheckedIds)
        }
    } catch (error) {
        console.error('获取角色菜单失败:', error)
        ElMessage.error('获取角色菜单失败')
    } finally {
        menuLoading.value = false
    }
}

const handleSaveMenus = async () => {
    if (!currentRole.value) {
        ElMessage.warning('请先选择角色')
        return
    }

    const checkedKeys = menuTreeRef.value.getCheckedKeys()
    const menuIds = filterLeafIds(checkedKeys)

    try {
        const res = await saveRoleMenus(currentRole.value.id, menuIds)

        if (res.success) {
            ElMessage.success('菜单权限保存成功')
        } else {
            ElMessage.error(res.error || '菜单权限保存失败')
        }
    } catch (error) {
        console.error('菜单权限保存失败:', error)
        ElMessage.error('菜单权限保存失败')
    }
}

onMounted(() => {
    fetchRoles()
})
</script>

<style scoped>
.system-role {
    padding: 20px;
}

.menu-card {
    margin-top: 20px;
}

.current-role {
    margin-bottom: 16px;
    font-weight: bold;
    color: #409eff;
}

.actions {
    margin-top: 20px;
}

.empty {
    padding: 24px;
    color: #909399;
    text-align: center;
}
</style>