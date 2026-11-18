<template>
  <section class="catalog-panel">
    <header class="panel-heading"><div><h2>岗位等级管理</h2><p>维护正式岗位等级目录；关联岗位数量实时根据服务端岗位事实计算。</p></div><div class="panel-actions"><el-button type="primary" @click="openForm()">新增岗位等级</el-button><el-button :loading="loading" @click="$emit('refresh')">刷新</el-button><el-button @click="clearFilters">清空筛选</el-button></div></header>
    <PceEnterpriseListTable ref="tableRef" :presentation-sort="runtime.sortState" @sort-change="handleSort" :contract="contract" page-id="erp-job-level-management" table-id="erp-job-level-table" :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters" :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length" :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="code" primary-label="岗位等级编码" :primary-width="180" min-width="1240px" :show-refresh="true" :refreshing="loading" action-width="210" @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch" @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters" @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection" @update-filter="updateFilter" @selection-change="selectedRows=$event" @refresh="$emit('refresh')">
      <template #columns><el-table-column type="index" label="序号" width="70" /><el-table-column prop="name" label="岗位等级名称" width="190" /><el-table-column prop="rank" label="等级顺序" width="120" sortable /><el-table-column prop="description" label="岗位等级说明" min-width="280" show-overflow-tooltip /><el-table-column label="关联岗位数量" width="140"><template #default="{row}"><el-button link type="primary" @click="$emit('view-positions',row.id)">{{ positionCount(row.id) }}</el-button></template></el-table-column><el-table-column prop="statusLabel" label="岗位等级启用状态" width="100" /></template>
      <template #actions="{row}"><el-button link type="primary" @click="openForm(row)">编辑</el-button><el-button link type="warning" @click="toggle(row)">{{ row.isActive===false?'启用':'停用' }}</el-button><el-button link type="success" @click="$emit('view-positions',row.id)">查看关联岗位</el-button></template>
    </PceEnterpriseListTable>
    <el-dialog v-model="visible" :title="`${form.id?'编辑':'新增'}岗位等级`" width="min(620px, 95vw)" destroy-on-close><el-form label-width="110px"><el-form-item label="岗位等级编码"><el-input :model-value="form.id ? form.code : '系统自动生成'" disabled /><small class="code-hint">新增时统一发号；编辑不重新编号。</small></el-form-item><el-form-item label="岗位等级名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="等级顺序" required><el-input-number v-model="form.rank" :min="1" /></el-form-item><el-form-item label="岗位等级说明"><el-input v-model="form.description" type="textarea" /></el-form-item><el-form-item label="状态"><el-switch v-model="form.active" active-text="启用" inactive-text="停用" /></el-form-item><el-form-item label="修改原因" required><el-input v-model="form.reason" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存并回读</el-button></template></el-dialog>
  </section>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { accessControlApi } from '@/api/accessControl.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
const props=defineProps({facts:{type:Object,required:true},loading:Boolean})
const emit=defineEmits(['refresh','view-positions'])
const rows=computed(()=>[...(props.facts.jobLevels||[])].sort((a,b)=>Number(a.rank)-Number(b.rank)||String(a.code).localeCompare(String(b.code))))
const filterSchema=computed(()=>[{field:'code',label:'岗位等级编码',filterType:'text'},{field:'name',label:'岗位等级名称',filterType:'text'},{field:'isActive',label:'岗位等级启用状态',filterType:'select',options:[{label:'启用',value:true},{label:'停用',value:false}]}])
const contract=createPceEnterpriseListContract({pageCode:'erp-job-level-management',pageType:'list',title:'岗位等级管理',moduleCode:'SYSTEM'})
const runtime=usePceEnterpriseListRuntime({rows,filterSchema:filterSchema.value,pageCode:'erp-job-level-management',searchFields:['code','name','description'],exportFileName:'岗位等级管理.csv',exportColumns:[{field:'code',label:'岗位等级编码'},{field:'name',label:'岗位等级名称'},{field:'rank',label:'等级顺序'}]})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,filteredRows,clearFilters,handleSort,clearSort,clearSelection,exportCurrent}=runtime
function updateFilter(field,value){filters[field]=value}
function positionCount(id){return (props.facts.positions||[]).filter(row=>String(row.jobLevelId)===String(id)).length}
const visible=ref(false),saving=ref(false),form=reactive({})
function reset(row={}){Object.assign(form,{id:row.id||null,code:row.code||'',name:row.name||'',rank:row.rank||1,description:row.description||'',active:row.isActive!==false,reason:''})}
function openForm(row={}){reset(row);visible.value=true}
async function save(){saving.value=true;try{const response=await accessControlApi.saveEnterpriseOrganizationModel('SAVE_JOB_LEVEL',form);if(!response?.success)throw new Error(response?.error?.message||'保存失败');ElMessage.success('岗位等级已保存并完成服务端回读');visible.value=false;emit('refresh')}catch(error){ElMessage.error(error.message||String(error))}finally{saving.value=false}}
function toggle(row){openForm({...row,isActive:row.isActive===false});form.active=row.isActive===false;form.reason=`${form.active?'启用':'停用'}岗位等级`}
</script>
<style scoped>.catalog-panel{display:grid;gap:14px}.panel-heading{display:flex;justify-content:space-between;gap:16px;align-items:center}.panel-heading h2,.panel-heading p{margin:0}.panel-heading p,.code-hint{color:#64748b}.panel-actions{display:flex;gap:8px;flex-wrap:wrap}@media(max-width:720px){.panel-heading{align-items:flex-start;flex-direction:column}}</style>
