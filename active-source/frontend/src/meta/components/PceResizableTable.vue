<template>
  <div
    class="pce-resizable-table"
    :data-pce-column-width-user="userKey || 'unavailable'"
    :data-pce-column-width-page="pageId"
    :data-pce-column-width-table="tableId"
    data-pce-column-width-contract="PCE-COLUMN-WIDTH-PREFERENCE-V1"
  >
    <div v-if="showReset" class="pce-column-width-actions">
      <el-button
        size="small"
        plain
        :disabled="!userKey"
        :data-acceptance-id="`${tableId}-restore-default-widths`"
        @click="resetWidths"
      >恢复默认列宽</el-button>
    </div>
    <el-table
      ref="tableRef"
      v-bind="$attrs"
      :fit="false"
      :allow-drag-last-column="true"
      @header-dragend="handleHeaderDragend"
    >
      <slot />
    </el-table>
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { createColumnWidthPreferenceRuntime } from '@/meta/runtime/columnWidthPreferences.js'

defineOptions({ inheritAttrs: false })

const props = defineProps({
  userKey: { type: [String, Number], default: '' },
  pageId: { type: String, required: true },
  tableId: { type: String, required: true },
  showReset: { type: Boolean, default: true },
})

const emit = defineEmits(['header-dragend'])
const tableRef = ref(null)
let runtime = null
let runtimeSignature = ''

function ensureRuntime() {
  const signature = `${props.userKey}|${props.pageId}|${props.tableId}`
  if (runtime && signature === runtimeSignature) return runtime
  runtimeSignature = signature
  runtime = createColumnWidthPreferenceRuntime({
    storage: globalThis.localStorage,
    userKey: props.userKey,
    pageId: props.pageId,
    tableId: props.tableId,
  })
  return runtime
}

async function applyWidths() {
  await nextTick()
  ensureRuntime().apply(tableRef.value)
}

function handleHeaderDragend(newWidth, oldWidth, column, event) {
  ensureRuntime().persist(newWidth, column)
  tableRef.value?.doLayout?.()
  emit('header-dragend', newWidth, oldWidth, column, event)
}

function resetWidths() {
  ensureRuntime().reset(tableRef.value)
}

onMounted(applyWidths)
watch(() => [props.userKey, props.pageId, props.tableId], applyWidths)

defineExpose({ tableRef, applyWidths, resetWidths })
</script>

<style scoped>
.pce-resizable-table { min-width: 0; width: 100%; }
.pce-column-width-actions { display: flex; justify-content: flex-end; margin: 0 0 8px; }
</style>
