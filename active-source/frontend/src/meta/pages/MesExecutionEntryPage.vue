<template><PceListPageShell :module-id="P.moduleId" :governance="governance" :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
<section aria-label="MES职责及验收入口" data-page="mes-test-execution-entry" :data-visible-read-ms="visibleReadMs" :data-read-cycle="readCycle"><h2>当前账号及职责入口</h2><p role="alert" v-if="error">{{ error }}</p><p v-if="refreshStatus==='refreshing'">正在读取当前服务端职责，请等待。</p>
<template v-if="facts"><p>后台账号：{{ facts.currentActorEvidence.username }}；公司：{{ facts.companyId }}；{{ facts.scopeLabel }}</p><p>{{ facts.historyRule }}</p><p>本页及刷新只读。正式与TEST用途分别按真实父对象核验；历史代办身份以各记录原说明和审计为准，不表示用户本人点击；人工验收以用户裁决为准。</p>
<h3>{{ facts.directoryMode==='authorized_cross_order' ? '跨单授权执行任务目录（非工序主数据）' : '当前工单任务目录' }}</h3>
<label>本单工单<select aria-label="本单工单" :value="facts.selectedWorkOrder?.id || ''" @change="chooseOrder($event.target.value)"><option value="">请选择有权工单</option><option v-for="o in facts.workOrderOptions" :key="o.id" :value="o.id">{{ o.no }}</option></select></label>
<p v-if="facts.selectedWorkOrder">当前工单：{{ facts.selectedWorkOrder.no }}；<template v-if="facts.selectedWorkOrder.usagePurpose==='PRODUCTION_USE'">正式生产计划 {{ facts.selectedWorkOrder.productionPlanId }}</template><template v-else>订单执行安排 {{ facts.selectedWorkOrder.arrangementId }}／修订{{ facts.selectedWorkOrder.arrangementRevision }}</template>；冻结路线版本{{ facts.selectedWorkOrder.routingVersionId }}。{{ facts.selectedWorkOrder.sourceLabel }}</p>
<p>{{ facts.orderRuleLabel }}</p><p v-if="facts.omittedFrozenNodes?.length">冻结路线中本单不执行的节点：{{ facts.omittedFrozenNodes.map(x=>x.sequence+'（'+x.decisionLabel+'）').join('、') }}；保留原序号，不连续重编号。</p>
<MesExecutionContext :facts="facts" />
<router-link :to="{path:P.route,query:{directory:'all'}}">跨单授权目录（独立查看用途）</router-link>
<ul><li v-for="link in facts.links" :key="link.pageUrl+link.label"><router-link :to="link.pageUrl">{{ link.label }}</router-link></li></ul>
<p v-if="facts.selectionRequired">请选择上方本单工单，或点击“跨单授权目录”；尚未选择工单不表示没有执行职责。</p>
<p v-else-if="!facts.tasks.length">当前没有本人执行或授权独审任务。主任和仓管请从上方已核实职责的任务派工或成品接收入口进入。</p>
<p v-for="block in facts.dispatchSourceBlocks || []" :key="block.workOrderNo" role="alert">{{ block.workOrderNo }}来源核验未通过：{{ block.message }}</p>
<ul><li v-for="x in facts.transfers" :key="x.id"><router-link :to="'/planning/finished-goods-handovers?transferId='+x.id">{{ x.no }} · {{ x.workOrderNo }} · {{ x.statusLabel }}</router-link></li></ul>
</template></section>
<PceEnterpriseListTable v-show="!!facts" :ref="e=>table.tableRef=e" :contract="contract" :page-id="P.pageCode" table-id="mes-duty-history" :rows="facts?.tasks || []" :table-rows="table.filteredRows" :quick-search="table.quickSearch" :filter-schema="filters" :filters="table.filters" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length" :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="no" primary-label="工序任务编号" index-label="列表序号" min-width="1800px" :action-width="200" @update:quick-search="table.quickSearch=$event" @toggle-advanced="table.advancedVisible=!table.advancedVisible" @search="table.appliedSearch=table.quickSearch" @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @update-filter="table.updateFilter" @export-current="table.exportCurrent" @clear-selection="table.selectedRows=[]" @selection-change="table.handleSelectionChange" @sort-change="table.handleSort">
<template #columns><el-table-column prop="frozenSequence" label="冻结路线／计划工序序号" width="180"/><el-table-column prop="operationName" label="工序名称" width="140"/><el-table-column label="独审状态" width="270"><template #default="{row}"><PceBusinessStatus :status-label="row.reviewStatusLabel"/></template></el-table-column><el-table-column prop="actualReviewerName" label="实际审核人" width="130"/><el-table-column prop="workOrderNo" label="生产工单编号" width="220"/><el-table-column prop="employeeName" label="原获派人" width="110"/><el-table-column label="实际前置任务（条件穿透）" width="250"><template #default="{row}">{{ Array.isArray(row.actualPredecessorTaskNos) ? row.actualPredecessorTaskNos.join('、') || '首道／无前置' : '进入本单目录核对冻结前置' }}</template></el-table-column><el-table-column prop="startedAt" label="实际开工时间" width="230"/><el-table-column prop="reportCount" label="报工笔数" width="100"/></template>
<template #actions="{row}"><router-link v-if="row.reportUrl" :to="row.reportUrl">本人报工历史</router-link> <router-link :to="row.reviewUrl">完工审核记录</router-link></template></PceEnterpriseListTable>
</PceListPageShell></template>
<script setup>
import {ref,computed,reactive,inject,onMounted,onBeforeUnmount,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import MesExecutionContext from '@/meta/components/MesExecutionContext.vue'
import {mesReadContext,mesPageGovernance} from '@/meta/runtime/mesTestProcessNavigation.js'
import request from '@/api/request'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import {MES_ENTRY_PAGE as P,MES_ENTRY_GOVERNANCE,MES_ENTRY_FILTERS,MES_ENTRY_SEARCH,resolveMesExecutionEntryState} from '@/meta/runtime/mesExecutionEntryContract.js'
import {createPceEnterpriseListContract,usePceEnterpriseListRuntime} from '@/meta/runtime/pceEnterpriseListContract.js'
import {PAGE_OBSERVABILITY_ACTIONS_KEY} from '@/meta/runtime/pageObservabilityActions.js'
import {getTabAuthEpoch} from '@/meta/runtime/tabAuthenticationContext.js'
import {useMesReadTiming,timedMesRead} from '@/meta/runtime/mesReadTiming.js'
const facts=ref(null),surface=ref(null),error=ref(''),refreshStatus=ref('idle'),filters=reactive(MES_ENTRY_FILTERS.map(x=>({...x})))
const route=useRoute(),router=useRouter(),governance=computed(()=>mesPageGovernance(MES_ENTRY_GOVERNANCE,route,mesReadContext(facts.value)))
const {visibleReadMs,readCycle}=useMesReadTiming(()=>({refreshing:'loading',success:'loaded',error:'read_failed'})[refreshStatus.value])
const contract=createPceEnterpriseListContract({pageCode:P.pageCode,pageType:'list',title:P.title,moduleCode:'MES'})
const table=reactive(usePceEnterpriseListRuntime({rows:computed(()=>facts.value?.tasks||[]),filterSchema:filters,pageCode:P.pageCode,searchFields:MES_ENTRY_SEARCH,exportFileName:'本人职责MES历史.csv',exportColumns:[{field:'no',label:'工序任务编号'},{field:'operationName',label:'工序'},{field:'statusLabel',label:'历史状态'}]}))
let requestId=0
async function refresh(){const id=++requestId,epoch=getTabAuthEpoch();facts.value=null;surface.value=null;error.value='';refreshStatus.value='refreshing';try{const params=resolveMesExecutionEntryState(route).filters;const result=await timedMesRead(()=>request({url:P.apiUrl,method:'GET',params,meta:{module:'MES',readOnly:true}}),P.apiUrl);if(id!==requestId||epoch!==getTabAuthEpoch())return;const data=result.data;if(!result.success||!data?.entryFacts)throw Error(result.error?.message||'当前服务端职责读取失败，请核对完整错误诊断。');surface.value=data;facts.value=data.entryFacts;refreshStatus.value='success';if(!route.query.workOrderId&&!route.query.directory&&facts.value.selectedWorkOrder)await router.replace({path:P.route,query:{workOrderId:String(facts.value.selectedWorkOrder.id)}})}catch(e){if(id===requestId){error.value=e.message;refreshStatus.value='error'}}}
function chooseOrder(id){router.push({path:P.route,query:id?{workOrderId:String(id)}:{}})}
watch(()=>route.fullPath,()=>{if(facts.value?.selectedWorkOrder?.id===Number(route.query.workOrderId)&&!route.query.directory)return;refresh()})
const observability=inject(PAGE_OBSERVABILITY_ACTIONS_KEY,null),provider={factOwner:P.moduleId,refresh,buildDiagnostics:()=>({factOwner:P.moduleId,factSource:'server',strictFacts:surface.value,entryFacts:facts.value,passed:refreshStatus.value==='success'})}
function authChanged(){requestId++;facts.value=null;surface.value=null;refresh()}
onMounted(()=>{observability?.register?.(provider);window.addEventListener('pce:authentication-changed',authChanged);refresh()})
onBeforeUnmount(()=>{requestId++;observability?.unregister?.(provider);window.removeEventListener('pce:authentication-changed',authChanged)})
</script>
