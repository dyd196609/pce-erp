<template>
  <div class="layout">
    <!-- 左侧菜单 -->
    <div class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <el-menu :default-active="activeMenu" :collapse="sidebarCollapsed" router>
        <template v-for="menu in menus" :key="menu.id">
          <el-sub-menu
            v-if="menu.children && menu.children.length > 0"
            :index="menu.path || menu.code"
          >
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

    <!-- 右侧内容 -->
    <div class="main">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getMyMenus } from '../api/system'

import {
  DataBoard,
  Collection,
  ShoppingCart,
  UserFilled,
  TrendCharts,
  Setting,
  Menu as MenuIcon,
} from '@element-plus/icons-vue'

/* ========================
   1. 状态定义（必须唯一）
======================== */
const router = useRouter()
const route = useRoute()

const sidebarCollapsed = ref(false)
const menus = ref([])

/* 当前激活菜单 */
const activeMenu = computed(() => route.path)

/* ========================
   2. 图标映射
======================== */
const iconMap = {
  DataBoard,
  Collection,
  ShoppingCart,
  UserFilled,
  TrendCharts,
  Setting,
  MenuIcon,
}

const getIcon = (name) => {
  return iconMap[name] || MenuIcon
}

/* ========================
   3. 菜单加载（唯一版本）
======================== */
const fetchMenus = async () => {
  try {
    const res = await getMyMenus()

    menus.value = res.data || []

    localStorage.setItem('menus', JSON.stringify(menus.value))
  } catch (e) {
    console.error('菜单加载失败', e)
  }
}

/* ========================
   4. 生命周期
======================== */
onMounted(() => {
  const cached = localStorage.getItem('menus')

  if (cached) {
    menus.value = JSON.parse(cached)
  }

  fetchMenus()
})
</script>

<style scoped>
.layout {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 220px;
  background: #001529;
  transition: all 0.2s;
}

.sidebar.collapsed {
  width: 64px;
}

.main {
  flex: 1;
  padding: 16px;
  background: #f5f5f5;
}
</style>
