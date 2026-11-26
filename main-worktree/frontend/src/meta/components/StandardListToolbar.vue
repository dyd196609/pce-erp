<template>
  <div
    class="standard-list-toolbar"
    data-acceptance-id="standard-list-toolbar"
    :data-pce-page-id="pageId || undefined"
    :data-pce-toolbar-for="tableId || undefined"
  >
    <span class="toolbar-search-wrapper" data-acceptance-id="list-fuzzy-search-input">
      <el-input
        :model-value="quickSearch"
        class="toolbar-search"
        clearable
        :placeholder="placeholder"
        @update:model-value="$emit('update:quickSearch', $event)"
        @keyup.enter="$emit('search')"
        @clear="$emit('search')"
      />
    </span>
    <el-button type="primary" plain data-acceptance-id="list-fuzzy-search-button" @click="$emit('search')">
      搜索
    </el-button>
    <el-button v-if="showRefresh" plain data-acceptance-id="list-refresh-button"
      :loading="refreshing" @click="$emit('refresh')">
      {{ refreshing ? '刷新中…' : '刷新' }}
    </el-button>
    <el-button
      v-if="showAdvancedFilterToggle"
      plain
      data-acceptance-id="list-advanced-filter-toggle"
      :data-pce-filter-toggle-for="tableId || undefined"
      :aria-expanded="String(advancedVisible)"
      @click="$emit('toggle-advanced')"
    >
      {{ advancedVisible ? '收起高级筛选' : '展开高级筛选' }}
    </el-button>
    <el-button plain data-acceptance-id="list-clear-filter-button" @click="$emit('clear-filters')">
      清空筛选
    </el-button>
    <el-button plain data-acceptance-id="list-clear-sort-button" @click="$emit('clear-sort')">
      清除排序
    </el-button>
    <el-button
      type="primary"
      plain
      data-acceptance-id="list-export-current-result-button"
      :data-pce-export-for="tableId || undefined"
      :disabled="exportDisabled"
      @click="$emit('export-current')"
    >
      导出当前结果
    </el-button>
    <span data-acceptance-id="list-result-count-visible">当前结果 {{ resultCount }} 条</span>
    <span data-acceptance-id="business-flow-selected-count">已选择 {{ selectedCount }} 条</span>
    <span>生效筛选 {{ activeFilterCount }} 项</span>
    <span>排序：{{ sortText }}</span>
    <slot name="batch-action" />
    <el-button plain :disabled="selectedCount === 0" @click="$emit('clear-selection')">
      清空选择
    </el-button>
  </div>
</template>

<script setup>
defineProps({
  pageId: { type: String, default: '' },
  tableId: { type: String, default: '' },
  quickSearch: { type: String, default: '' },
  placeholder: { type: String, default: '输入编号、来源单号、供应商或关键字' },
  advancedVisible: { type: Boolean, default: false },
  showAdvancedFilterToggle: { type: Boolean, default: true },
  resultCount: { type: Number, default: 0 },
  selectedCount: { type: Number, default: 0 },
  activeFilterCount: { type: Number, default: 0 },
  sortText: { type: String, default: '默认业务顺序' },
  exportDisabled: { type: Boolean, default: false },
  showRefresh: { type: Boolean, default: false },
  refreshing: { type: Boolean, default: false },
})

defineEmits([
  'update:quickSearch',
  'search',
  'toggle-advanced',
  'clear-filters',
  'clear-sort',
  'export-current',
  'clear-selection',
  'refresh',
])
</script>

<style scoped>
.standard-list-toolbar {
  display: flex;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 10px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.toolbar-search-wrapper,
.toolbar-search {
  width: min(360px, 100%);
}

.standard-list-toolbar span {
  color: #475569;
  font-size: 13px;
  font-weight: 700;
}
</style>
