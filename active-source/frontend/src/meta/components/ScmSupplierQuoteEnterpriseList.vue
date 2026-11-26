<template>
  <PceEnterpriseListTable ref="tableRef" :contract="enterpriseListContract"
    page-id="supplier-quote-workbench" table-id="supplier-quote-main"
    :rows="rows" :table-rows="filteredRows" :filter-schema="filterSchema" :filters="filters"
    :quick-search="quickSearch" :advanced-visible="advancedVisible" :selected-count="selectedRows.length"
    :active-filter-count="activeFilterCount" :sort-text="sortText" primary-field="inquiryNo"
    primary-label="询价编号" :primary-width="180" min-width="1280px"
    scroll-acceptance-id="supplier-quote-horizontal-scroll" :action-width="120"
    :action-contracts="SCM_SUPPLIER_QUOTE_LIST_ACTIONS" action-state-field="quoteStatus"
    :action-label-resolver="resolveActionLabel" @row-action="handleRowAction"
    @update:quick-search="quickSearch=$event" @search="appliedSearch=quickSearch"
    @toggle-advanced="advancedVisible=!advancedVisible" @clear-filters="clearFilters"
    @clear-sort="clearSort" @export-current="exportCurrent" @clear-selection="clearSelection"
    @update-filter="(field,value)=>filters[field]=value" @selection-change="selectedRows=$event"
    @sort-change="handleSort">
    <template #columns>
      <el-table-column label="供应商" min-width="190">
        <template #default="{ row }"><strong>{{ row.supplierName }}</strong><br><small>{{ row.supplierCode }}</small></template>
      </el-table-column>
      <el-table-column prop="materialCode" label="物料编码" min-width="150" />
      <el-table-column prop="materialName" label="物料名称" min-width="170" />
      <el-table-column prop="quantity" label="数量" width="100" />
      <el-table-column prop="quotePriceLabel" label="报价金额" width="130" />
      <el-table-column prop="quoteStatusLabel" label="报价状态" min-width="140" />
      <el-table-column prop="receivedAt" label="报价接收时间" min-width="190" />
    </template>
  </PceEnterpriseListTable>
</template>

<script setup>
import { computed } from 'vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import { createPceEnterpriseListContract, usePceEnterpriseListRuntime } from '@/meta/runtime/pceEnterpriseListContract.js'
import { SCM_SUPPLIER_QUOTE_LIST_ACTIONS } from '@/meta/process/scm/scmUnifiedListActionContractsV1142813.js'
import { createUnifiedFilterSchema } from '@/meta/runtime/unifiedFilterSchema.js'
import { createRemoteSelectOptionsProvider } from '@/meta/runtime/remoteSelectOptionsProvider.js'

const emit=defineEmits(['edit'])
const props=defineProps({rows:{type:Array,default:()=>[]}})
const sourceRows=computed(()=>(props.rows||[]).map(row=>({...row,
  quoteStatusLabel:row.quotationStatusLabel || (row.quoted?'报价已保存':'待填写报价'),
  quotePriceLabel:row.quoted?Number(row.quotePrice??row.quote?.unitPrice).toFixed(2):'-'})))
const optionsProvider=createRemoteSelectOptionsProvider({providerCode:'SCM_SUPPLIER_QUOTE_FILTER_OPTIONS'})
const filterFields=Object.freeze([
  {field:'inquiryNo',label:'询价编号',type:'remote-select',optionsProvider},
  {field:'materialCode',label:'物料编码',type:'remote-select',optionsProvider},
  {field:'supplierCode',label:'供应商编码',type:'remote-select',optionsProvider},
  {field:'quoted',label:'报价状态',type:'select',optionsSource:'SupplierQuoteStateContract',options:[{label:'待填写报价',value:false},{label:'报价已保存',value:true}]},
])
const filterSchema=createUnifiedFilterSchema({filterFields,optionsProvider})
const enterpriseListContract=createPceEnterpriseListContract({pageCode:'supplier-quote-workbench',pageType:'list',title:'供应商报价',moduleCode:'SCM_SUPPLIER_QUOTE'})
const {selectedRows,quickSearch,appliedSearch,advancedVisible,filters,tableRef,activeFilterCount,sortText,
  filteredRows,clearFilters,clearSort,clearSelection,handleSort,exportCurrent}=usePceEnterpriseListRuntime({rows:sourceRows,
  filterSchema,pageCode:'supplier-quote-workbench',searchFields:['inquiryNo','materialCode','materialName','supplierCode','supplierName'],
  exportFileName:'supplier-quotes.csv',exportColumns:[{field:'inquiryNo',label:'询价编号'},
    {field:'supplierName',label:'供应商'},{field:'materialCode',label:'物料编码'},
    {field:'materialName',label:'物料名称'},{field:'quantity',label:'数量'},
    {field:'quotePriceLabel',label:'报价金额'},{field:'quoteStatusLabel',label:'报价状态'}]})
function resolveActionLabel(row){return row.quoted?'修改报价':'填写报价'}
function handleRowAction(action,row){if(action.actionCode==='SAVE_SUPPLIER_QUOTE')emit('edit',row)}
</script>
