<template>
 <PceEnterpriseListTable :ref="el=>table.tableRef=el" :contract="contract" page-id="enterprise-home" table-id="office-authorized-records"
  :rows="rows" :table-rows="table.filteredRows" :filter-schema="filters" :filters="table.filters" :quick-search="table.quickSearch"
  :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length" :active-filter-count="table.activeFilterCount" :sort-text="table.sortText"
  row-key="id" primary-field="no" :primary-label="columns[0].label" :primary-width="210" compact-freeze-primary min-width="760px" :action-width="240"
  @update:quick-search="table.quickSearch=$event" @search="table.appliedSearch=table.quickSearch" @toggle-advanced="table.advancedVisible=!table.advancedVisible"
  @clear-filters="table.clearFilters" @clear-sort="table.clearSort" @clear-selection="table.clearSelection" @export-current="table.exportCurrent"
  @update-filter="table.updateFilter" @selection-change="table.selectedRows=$event" @sort-change="table.handleSort">
  <template #columns><el-table-column v-for="column in columns.slice(1)" :key="column.field" :prop="column.field" :label="column.label" :min-width="column.width"><template #default="{row}"><PceBusinessStatus v-if="column.field==='statusLabel'" :status-label="row.statusLabel"/><span v-else>{{row[column.field] ?? '未提供'}}</span></template></el-table-column></template>
  <template #actions="{row}"><button type="button" @click="$emit('inspect',row)">查看依据</button><router-link :to="row.pageUrl">原页面</router-link></template>
 </PceEnterpriseListTable>
</template>
<script setup>
import {computed,reactive} from 'vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import {createPceEnterpriseListContract,usePceEnterpriseListRuntime} from '@/meta/runtime/pceEnterpriseListContract.js'
import {officeRecordColumns} from '@/meta/runtime/enterpriseOfficeHome.js'
const props=defineProps({rows:{type:Array,required:true},recordKind:{type:String,required:true}});defineEmits(['inspect'])
const rows=computed(()=>props.rows)
const columns=computed(()=>officeRecordColumns(props.recordKind))
const legacyContextColumn={field:'context',label:'关联说明（原组合）'}
const filters=[...columns.value.map(column=>({field:column.field,label:column.label,filterType:'text'})),{...legacyContextColumn,filterType:'text'}]
const contract=createPceEnterpriseListContract({pageCode:'enterprise-home',pageType:'list',title:'岗位授权原记录',moduleCode:'SYSTEM'})
const table=reactive(usePceEnterpriseListRuntime({rows,filterSchema:filters,pageCode:'enterprise-home',searchFields:[...columns.value.map(c=>c.field),'context'],exportFileName:'岗位授权记录.csv',exportColumns:()=>[...columns.value,legacyContextColumn]}))
</script>
<style scoped>button,a{min-height:44px;padding:6px 10px;display:inline-flex;align-items:center;cursor:pointer}a{color:#1757a1}</style>
