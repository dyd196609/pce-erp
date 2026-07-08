<template>
  <div>
    <!-- =========================
         表格
    ========================== -->
    <el-table :data="data" border>
      <!-- 动态列 -->
      <el-table-column v-for="col in columns" :key="col.prop" :label="col.label" :prop="col.prop" />

      <!-- 操作列 -->
      <el-table-column label="操作" width="320">
        <template #default="scope">
          <!-- =========================
               动态按钮（V24统一入口）
          ========================== -->
          <el-button
            v-for="act in visibleActions(scope.row)"
            :key="act.action"
            size="small"
            :type="act.type || 'primary'"
            @click="handleAction(act, scope.row)"
          >
            {{ act.label }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { computed } from 'vue'

/**
 * =========================
 * V24 runtime统一入口
 * =========================
 */
import { runWorkflow } from '@/meta/runtime/workflowEngine'

/**
 * props
 */
const props = defineProps({
  data: { type: Array, default: () => [] },
  meta: { type: Object, default: () => ({}) },
})

/**
 * columns
 */
const columns = computed(() => {
  return props.meta?.table?.columns || []
})

/**
 * actions
 */
const actions = computed(() => {
  return props.meta?.actions || []
})

/**
 * 可见 action（预留扩展）
 */
const visibleActions = (row) => {
  return actions.value.filter((a) => {
    if (typeof a.visible === 'function') {
      return a.visible(row)
    }
    return true
  })
}

/**
 * =========================
 * V24统一执行入口
 * =========================
 */
const handleAction = async (action, row) => {
  await runWorkflow({
    action,
    row,
    meta: props.meta,
  })
}
</script>
