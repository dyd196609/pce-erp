<template>
  <el-menu :default-active="active" :collapse="false" router>
    <template v-for="menu in menus" :key="menu.id">
      <!-- 有子菜单 -->
      <el-sub-menu v-if="menu.children && menu.children.length" :index="menu.id.toString()">
        <template #title>
          <span>{{ menu.name }}</span>
        </template>

        <el-menu-item v-for="child in menu.children" :key="child.id" :index="child.path">
          {{ child.name }}
        </el-menu-item>
      </el-sub-menu>

      <!-- 单菜单 -->
      <el-menu-item v-else :index="menu.path">
        {{ menu.name }}
      </el-menu-item>
    </template>
  </el-menu>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  menus: {
    type: Array,
    default: () => [],
  },
})

const active = ref('/purchase/order')
</script>
