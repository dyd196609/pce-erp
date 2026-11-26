<template>
  <button type="button" class="master-data-field" :class="{ disabled }" :disabled="disabled"
    :aria-label="`${label}业务选择器`" :data-master-selector="selectorType" @click="openSelector">
    <span :class="{ placeholder: !displayValue }">{{ displayValue || placeholder }}</span>
    <strong>选择</strong>
  </button>

  <el-dialog v-model="visible" :title="dialogTitle" width="960px" append-to-body destroy-on-close>
    <section class="selector-shell" :data-selector-dialog="selectorType">
      <template v-if="selectorType === 'organization'">
        <p class="selector-help">按公司、部门、子部门层级选择使用部门。</p>
        <el-tree :data="organizationTree" node-key="key" default-expand-all
          :props="{ label: 'label', children: 'children' }" @node-click="selectOrganization" />
      </template>
      <template v-else>
        <div class="selector-toolbar">
          <el-input v-model="query" :placeholder="searchPlaceholder" clearable @keyup.enter="loadRows" />
          <el-button type="primary" :loading="loading" @click="loadRows">搜索</el-button>
        </div>
        <el-table :data="rows" max-height="460" border highlight-current-row @row-dblclick="selectRow">
          <el-table-column prop="code" label="编码" width="180" />
          <el-table-column prop="name" label="名称" min-width="200" />
          <template v-if="selectorType === 'project'">
            <el-table-column prop="owner" label="负责人" width="120" />
            <el-table-column prop="stage" label="阶段" width="130" />
            <el-table-column prop="status" label="状态" width="100" />
          </template>
          <el-table-column v-if="selectorType === 'cost-center'" prop="departmentName" label="所属组织" width="160" />
          <template v-if="selectorType === 'material'">
            <el-table-column prop="specification" label="规格" width="180" />
            <el-table-column prop="unit" label="单位" width="90" />
            <el-table-column prop="category" label="分类" width="140" />
            <el-table-column prop="purchaseAttribute" label="采购属性" width="110" />
          </template>
          <el-table-column label="操作" width="90" fixed="right">
            <template #default="{ row }"><el-button type="primary" link @click="selectRow(row)">选择</el-button></template>
          </el-table-column>
        </el-table>
        <p class="selector-tip">双击业务记录也可完成选择；数据来自服务端主数据。</p>
      </template>
    </section>
    <template #footer><el-button @click="visible=false">取消</el-button></template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { purchaseRequestApi } from '@/api/purchaseRequest.js'

defineOptions({ name: 'PceBusinessMasterDataSelector' })
const props=defineProps({selectorType:{type:String,required:true},label:{type:String,required:true},displayValue:{type:String,default:''},placeholder:{type:String,default:'点击选择业务数据'},disabled:{type:Boolean,default:false}})
const emit=defineEmits(['select'])
const visible=ref(false), query=ref(''), rows=ref([]), organizationRows=ref([]), loading=ref(false)
const endpointMap=Object.freeze({project:'projects','cost-center':'cost-centers',material:'materials','expense-category':'expense-categories','budget-category':'budget-categories'})
const defaultQuery=Object.freeze({project:'PRJ','cost-center':'CC',material:'MT','expense-category':'EXP','budget-category':'BUD'})
const dialogTitle=computed(()=>({project:'项目选择窗口',organization:'使用部门组织树','cost-center':'成本中心选择窗口',material:'物料选择窗口','expense-category':'费用类别选择窗口','budget-category':'预算类别选择窗口'}[props.selectorType]||`${props.label}选择窗口`))
const searchPlaceholder=computed(()=>props.selectorType==='material'?'搜索物料编码、名称或规格':'搜索编码或名称')
const organizationTree=computed(()=>buildOrganizationTree(organizationRows.value))

function extractResults(response){return response?.data?.results||response?.data?.data?.results||[]}
function buildOrganizationTree(values){const companies=new Map(),departments=new Map();values.forEach(row=>{if(!companies.has(row.companyId))companies.set(row.companyId,{key:`company-${row.companyId}`,label:row.companyName,nodeType:'company',children:[]});departments.set(row.id,{key:`department-${row.id}`,label:`${row.code} ${row.name}`,nodeType:'department',...row,children:[]})});values.forEach(row=>{const node=departments.get(row.id);if(row.parentId&&departments.has(row.parentId))departments.get(row.parentId).children.push(node);else companies.get(row.companyId)?.children.push(node)});return[...companies.values()]}
async function openSelector(){if(props.disabled)return;visible.value=true;if(props.selectorType==='organization'){loading.value=true;try{organizationRows.value=extractResults(await purchaseRequestApi.searchReference('organization-tree',''))}catch(error){ElMessage.error(error?.message||'组织主数据读取失败')}finally{loading.value=false}return}query.value=defaultQuery[props.selectorType]||'';await loadRows()}
async function loadRows(){const endpoint=endpointMap[props.selectorType];if(!endpoint)return;loading.value=true;try{rows.value=extractResults(await purchaseRequestApi.searchReference(endpoint,query.value))}catch(error){ElMessage.error(error?.message||`${props.label}主数据读取失败`)}finally{loading.value=false}}
function selectRow(row){emit('select',row);visible.value=false}
function selectOrganization(node){if(node.nodeType!=='department')return;emit('select',node);visible.value=false}
</script>

<style scoped>
.master-data-field{display:flex;width:100%;min-height:32px;align-items:center;justify-content:space-between;gap:12px;padding:0 12px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;color:#303133;cursor:pointer;text-align:left}.master-data-field:hover,.master-data-field:focus-visible{border-color:#409eff;box-shadow:0 0 0 2px #409eff1f;outline:none}.master-data-field strong{color:#409eff;font-size:13px}.master-data-field .placeholder{color:#a8abb2}.master-data-field.disabled{cursor:not-allowed;background:#f5f7fa;color:#c0c4cc}.selector-toolbar{display:flex;gap:10px;margin-bottom:14px}.selector-toolbar .el-input{flex:1}.selector-help,.selector-tip{color:#64748b}.selector-tip{margin:12px 0 0;font-size:13px}
</style>
