<template>
  <div class="layout">
    <!-- header -->
    <div class="header">
      <div @click="toggle">☰ PCE-ERP</div>
    </div>

    <div class="body">
      <!-- sidebar -->
      <div class="sidebar" :class="{ collapsed }">
        <SideMenu :menus="menus" />
      </div>

      <div class="content">
        <RouterView />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import SideMenu from './components/SideMenu.vue'
import { Expand } from '@element-plus/icons-vue'

const collapsed = ref(false)

const toggle = () => {
  collapsed.value = !collapsed.value
}

/** 临时菜单（后面接后端） */
const menus = ref([
  {
    id: 1,
    name: '仪表盘',
    path: '/dashboard',
    icon: 'HomeFilled',
  },
  {
    id: 2,
    name: '采购管理',
    children: [
      {
        id: 21,
        name: '采购订单',
        path: '/purchase/order',
      },
    ],
  },
])
</script>

<style scoped>
.layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  height: 50px;
  background: linear-gradient(90deg, #5b8cff, #6aa8ff);
  color: white;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 16px;
}

.body {
  flex: 1;
  display: flex;
}

.sidebar {
  width: 220px;
  background: #0f172a;
  color: white;
  transition: 0.2s;
}

.sidebar.collapsed {
  width: 64px;
}

.content {
  flex: 1;
  background: #f5f6f8;
  padding: 16px;
}
</style>
