<template>
    <div class="system-menu">
        <el-card>
            <h2>菜单管理</h2>

            <el-tree v-loading="loading" :data="menus" node-key="id" default-expand-all :props="treeProps">
                <template #default="{ data }">
                    <span>
                        <strong>{{ data.name }}</strong>

                        <span style="margin-left:10px;color:#909399">
                            {{ data.code }}
                        </span>

                        <span style="margin-left:10px;color:#67c23a">
                            {{ data.path }}
                        </span>
                    </span>
                </template>
            </el-tree>
        </el-card>
    </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getMenus } from '../api/system'

const menus = ref([])
const loading = ref(false)

const treeProps = {
    children: 'children',
    label: 'name'
}

const loadMenus = async () => {
    loading.value = true

    try {
        const res = await getMenus()

        if (res.success) {
            menus.value = res.data
        }
    } catch (e) {
        console.error(e)
        ElMessage.error('菜单加载失败')
    } finally {
        loading.value = false
    }
}

onMounted(() => {
    loadMenus()
})
</script>

<style scoped>
.system-menu {
    padding: 20px;
}
</style>