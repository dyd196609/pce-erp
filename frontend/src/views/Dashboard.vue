<template>
    <div class="dashboard">
        <div class="navbar">
            <div class="logo">
                <span class="menu-toggle" @click="sidebarCollapsed = !sidebarCollapsed">
                    {{ sidebarCollapsed ? '☰' : '◀' }}
                </span>
                掌云智造管理系统
            </div>

            <div class="user-info">
                <span>{{ userInfo?.real_name || userInfo?.username || '管理员' }}</span>
                <el-button type="text" @click="handleLogout">退出</el-button>
            </div>
        </div>

        <div class="layout">
            <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
                <el-menu :default-active="activeMenu" :collapse="sidebarCollapsed" :collapse-transition="false" router>
                    <template v-for="menu in menus" :key="menu.id">
                        <el-sub-menu v-if="menu.children && menu.children.length > 0" :index="menu.path || menu.code">
                            <template #title>
                                <el-icon>
                                    <component :is="getIcon(menu.icon)" />
                                </el-icon>
                                <span>{{ menu.name }}</span>
                            </template>

                            <el-menu-item v-for="child in menu.children" :key="child.id" :index="child.path">
                                {{ child.name }}
                            </el-menu-item>
                        </el-sub-menu>

                        <el-menu-item v-else :index="menu.path">
                            <el-icon>
                                <component :is="getIcon(menu.icon)" />
                            </el-icon>
                            <span>{{ menu.name }}</span>
                        </el-menu-item>
                    </template>
                </el-menu>
            </div>

            <div class="content">
                <router-view />
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
    DataBoard,
    Collection,
    ShoppingCart,
    UserFilled,
    TrendCharts,
    Setting,
    Menu as MenuIcon
} from '@element-plus/icons-vue'
import { getMyMenus } from '../api/system'

const router = useRouter()
const route = useRoute()

const sidebarCollapsed = ref(false)
const userInfo = ref(JSON.parse(localStorage.getItem('user') || '{}'))
const menus = ref([])

const activeMenu = computed(() => {
    return route.path
})

const iconMap = {
    dashboard: DataBoard,
    masterdata: Collection,
    purchase: ShoppingCart,
    hr: UserFilled,
    profit: TrendCharts,
    system: Setting
}

const getIcon = (icon) => {
    return iconMap[icon] || MenuIcon
}

const fetchMenus = async () => {
    try {
        const res = await getMyMenus()

        if (res.success) {
            menus.value = res.data
        } else {
            ElMessage.error('菜单加载失败')
        }
    } catch (error) {
        console.error('菜单加载失败:', error)
        ElMessage.error('菜单加载失败')
    }
}

const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
    ElMessage.success('已退出登录')
}

onMounted(() => {
    fetchMenus()
})
</script>

<style scoped>
.dashboard {
    height: 100vh;
    display: flex;
    flex-direction: column;
}

.navbar {
    height: 60px;
    background: #409eff;
    color: white;
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0 20px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    flex-shrink: 0;
}

.logo {
    font-size: 20px;
    font-weight: bold;
    display: flex;
    align-items: center;
    gap: 10px;
}

.menu-toggle {
    cursor: pointer;
    font-size: 20px;
    color: white;
    display: inline-block;
    width: 32px;
    text-align: center;
}

.user-info {
    display: flex;
    align-items: center;
    gap: 15px;
}

.user-info .el-button {
    color: white;
}

.layout {
    flex: 1;
    display: flex;
    overflow: hidden;
}

.sidebar {
    width: 240px;
    background: #f5f5f5;
    border-right: 1px solid #e4e7ed;
    overflow-y: auto;
    flex-shrink: 0;
}

.sidebar.collapsed {
    width: 64px;
}

.content {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    background: #f0f2f5;
}

.el-menu {
    border-right: none;
    background: #f5f5f5;
}

.el-menu-item.is-active {
    background: #e6f7ff;
    color: #409eff;
}

.el-menu-item:hover {
    background: #ecf5ff;
}

.sidebar {
    width: 240px !important;
}

.sidebar.collapsed {
    width: 64px !important;
}

.sidebar.collapsed :deep(.el-sub-menu__title span),
.sidebar.collapsed :deep(.el-menu-item span) {
    display: none !important;
}
</style>