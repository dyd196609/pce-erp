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
            <!-- 侧边栏菜单，根据折叠状态改变宽度 -->
            <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
                <el-menu :default-active="activeMenu" @select="handleMenuSelect" :collapse="sidebarCollapsed"
                    :collapse-transition="false">
                    <el-menu-item index="employees">
                        <el-icon>
                            <User />
                        </el-icon>
                        <span>员工管理</span>
                    </el-menu-item>
                    <el-menu-item index="shifts">
                        <el-icon>
                            <Clock />
                        </el-icon>
                        <span>班次管理</span>
                    </el-menu-item>
                    <el-menu-item index="material-categories">
                        <el-icon>
                            <Folder />
                        </el-icon>
                        <span>物料分类</span>
                    </el-menu-item>
                    <el-menu-item index="materials">
                        <el-icon>
                            <Goods />
                        </el-icon>
                        <span>物料管理</span>
                    </el-menu-item>
                    <el-menu-item index="suppliers">
                        <el-icon>
                            <ShoppingCart />
                        </el-icon>
                        <span>供应商管理</span>
                    </el-menu-item>
                    <el-menu-item index="purchase-orders">
                        <el-icon>
                            <Document />
                        </el-icon>
                        <span>采购订单</span>
                    </el-menu-item>
                    <el-menu-item index="reports">
                        <el-icon>
                            <DataAnalysis />
                        </el-icon>
                        <span>采购报表</span>
                    </el-menu-item>
                </el-menu>
            </div>

            <div class="content">
                <router-view />
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
    User, Clock, Folder, Goods, Document, DataAnalysis, ShoppingCart,
    ArrowLeft, ArrowRight
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

const sidebarCollapsed = ref(false)  // 侧边栏折叠状态

const userInfo = ref(JSON.parse(localStorage.getItem('user') || '{}'))

const activeMenu = computed(() => {
    const path = route.path
    if (path.includes('employees')) return 'employees'
    if (path.includes('shifts')) return 'shifts'
    if (path.includes('material-categories')) return 'material-categories'
    if (path.includes('materials')) return 'materials'
    if (path.includes('suppliers')) return 'suppliers'
    if (path.includes('purchase-orders')) return 'purchase-orders'
    if (path.includes('reports')) return 'reports'
    return 'employees'
})

const handleMenuSelect = (index) => {
    router.push(`/${index}`)
}

const handleLogout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    router.push('/login')
    ElMessage.success('已退出登录')
}
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
    gap: 15px;
}

.menu-toggle {
    cursor: pointer;
    font-size: 20px;
    color: white;
    display: inline-block;
    width: 30px;
    text-align: center;
}

.menu-toggle:hover {
    opacity: 0.8;
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
    width: 220px;
    background: #f5f5f5;
    border-right: 1px solid #e4e7ed;
    overflow-y: auto;
    flex-shrink: 0;
    transition: width 0.3s ease;
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
</style>