<template>
  <label
    class="pce-advanced-filter-field"
    :data-filter-field="field.field"
    :data-filter-type="field.filterType"
    :data-options-source="field.optionsSource"
  >
    <span>{{ field.label }}</span>
    <el-select
      v-if="field.filterType === 'remote-select'"
      :model-value="modelValue"
      clearable
      filterable
      :allow-create="Boolean(field.allowCustomValue)"
      :default-first-option="Boolean(field.allowCustomValue)"
      remote
      :remote-method="loadRemoteOptions"
      :loading="remoteLoading"
      :placeholder="field.placeholder || '输入编号搜索'"
      :loading-text="field.loadingText || '正在读取可选项…'"
      :no-match-text="field.noMatchText || '没有匹配项，可继续输入关键词'"
      :no-data-text="field.noDataText || '暂无可选项'"
      data-pce-rendered-control-type="remote-select"
      @visible-change="visible => visible && loadRemoteOptions('')"
      @update:model-value="emitValue"
    >
      <el-option v-for="option in remoteOptions" :key="String(option.value)"
        :label="option.label" :value="option.value" />
    </el-select>
    <el-select
      v-else-if="field.filterType === 'select'"
      :model-value="modelValue"
      clearable
      filterable
      :allow-create="Boolean(field.allowCustomValue)"
      :default-first-option="Boolean(field.allowCustomValue)"
      :placeholder="field.placeholder || '全部 / 不限'"
      :loading-text="field.loadingText || '正在读取可选项…'"
      :no-match-text="field.noMatchText || (field.allowCustomValue ? '没有匹配项，可继续输入关键词' : '没有匹配项')"
      :no-data-text="field.noDataText || '暂无可选项'"
      data-pce-rendered-control-type="select"
      @update:model-value="emitValue"
    >
      <el-option
        v-for="option in resolvedOptions"
        :key="String(option.value)"
        :label="option.label"
        :value="option.value"
      />
    </el-select>
    <div v-else-if="field.filterType === 'date'" data-pce-rendered-control-type="date">
      <el-date-picker
        :model-value="modelValue"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="选择日期"
        @update:model-value="emitValue"
      />
    </div>
    <div v-else-if="field.filterType === 'daterange'" data-pce-rendered-control-type="daterange">
      <el-date-picker
        :model-value="modelValue"
        type="daterange"
        value-format="YYYY-MM-DD"
        range-separator="至"
        start-placeholder="开始日期"
        end-placeholder="结束日期"
        @update:model-value="emitValue"
      />
    </div>
    <div
      v-else-if="field.filterType === 'numberRange'"
      class="pce-number-range"
      data-pce-rendered-control-type="numberRange"
    >
      <el-input-number
        :model-value="rangeValue[0]"
        controls-position="right"
        placeholder="最小值"
        @update:model-value="updateRange(0, $event)"
      />
      <span>至</span>
      <el-input-number
        :model-value="rangeValue[1]"
        controls-position="right"
        placeholder="最大值"
        @update:model-value="updateRange(1, $event)"
      />
    </div>
    <el-input-number
      v-else-if="field.filterType === 'number'"
      :model-value="modelValue"
      controls-position="right"
      :placeholder="field.label"
      data-pce-rendered-control-type="number"
      @update:model-value="emitValue"
    />
    <el-switch
      v-else-if="field.filterType === 'boolean'"
      :model-value="modelValue"
      inline-prompt
      active-text="是"
      inactive-text="否"
      data-pce-rendered-control-type="boolean"
      @update:model-value="emitValue"
    />
    <el-input
      v-else
      :model-value="modelValue"
      clearable
      :placeholder="field.label"
      data-pce-rendered-control-type="text"
      @update:model-value="emitValue"
    />
  </label>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { resolveListFilterOptions, resolveRemoteListFilterOptions } from '@/meta/runtime/listFilterRuntime.js'

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array], default: '' },
  rows: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])
const resolvedOptions = computed(() => resolveListFilterOptions(props.field, props.rows))
const remoteOptions = ref([])
const remoteLoading = ref(false)
const rangeValue = computed(() => Array.isArray(props.modelValue) ? props.modelValue : [])

function emitValue(value) {
  emit('update:modelValue', value ?? '')
}

function updateRange(index, value) {
  const next = [...rangeValue.value]
  next[index] = value ?? ''
  emitValue(next)
}

async function loadRemoteOptions(query = '') {
  remoteLoading.value = true
  try { remoteOptions.value = await resolveRemoteListFilterOptions(props.field, query, props.rows) }
  finally { remoteLoading.value = false }
}

watch(() => props.rows, () => loadRemoteOptions(''), { immediate: true })
</script>

<style scoped>
.pce-advanced-filter-field {
  display: grid;
  gap: 5px;
  min-width: 0;
  color: #334155;
  font-weight: 700;
}

.pce-advanced-filter-field :deep(.el-select),
.pce-advanced-filter-field :deep(.el-date-editor),
.pce-advanced-filter-field :deep(.el-input) {
  width: 100%;
}

.pce-number-range {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 6px;
  align-items: center;
}

.pce-number-range :deep(.el-input-number) {
  width: 100%;
}
</style>
