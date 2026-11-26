<template>
 <section class="office-home" data-office-version="PCE-OFFICE-HOME-20261115-B4-R1" :data-office-mounted-ms="routeMountedMs" :data-order-read-timing="JSON.stringify(orderReadTiming)" :aria-label="roleLabel+'工作摘要'">
  <h3>{{roleLabel}} · 授权记录与原入口</h3>
  <p>记录数来自原服务本次返回的完整授权目录，分页和筛选不改变总记录数；记录数不表示待办或完成数。</p>
  <nav aria-label="岗位原模块"><router-link v-for="link in links" :key="link.url" :to="link.url">{{link.label}}</router-link></nav>
  <p v-if="!facts" role="status">正在读取原服务授权范围，数量尚未取得。</p>
  <template v-for="resource in facts?.results||[]" :key="resource.key">
   <section class="resource" :data-resource="resource.key" :data-load-state="resource.state">
    <h4>{{resource.title}}</h4>
    <p v-if="resource.state!=='loaded'" role="alert">{{stateText(resource.state)}}：{{resource.message}} 数量未知，不显示为0。</p>
    <template v-else>
     <nav aria-label="选择记录类型"><button v-for="category in categories(resource)" :key="category.key" type="button" :aria-pressed="selectedKind(resource)===category.key" @click="selectKind(resource,category.key)">{{category.label}} {{count(resource,category.key)}} 条</button></nav>
     <p>{{kindLabel(resource)}}共 {{count(resource,selectedKind(resource))}} 条（原服务授权记录，非待办总数）。</p>
     <OfficeRecordTable :key="resource.key+':'+selectedKind(resource)" :record-kind="selectedKind(resource)" :rows="records(resource)" @inspect="inspectRecord" />
    </template>
    <details><summary>读取范围与核验信息</summary><p>原接口：{{resource.url}}</p><p>本次读取：{{facts.readAt}}；按原服务授权范围。</p><p v-if="role==='system'">系统基础目录包含原管理员可见主体及历史配置，不作为当前企业人员总数。</p><p v-if="resource.errorCode">错误标识：{{resource.errorCode}}；未发起业务写入。</p></details>
   </section>
  </template>
  <p v-if="orderLocator && orderResource?.state==='loaded' && !selectedRecord" role="status">当前授权订单目录未找到所选记录。请选择目录中的订单。</p>
  <section v-if="selectedRecord" aria-label="所选原记录依据">
   <h4>{{selectedRecord.no}} · 原记录依据</h4><dl><template v-for="(value,key) in selectedRecord.original" :key="key"><dt>{{key}}</dt><dd>{{value}}</dd></template></dl>
   <router-link :to="selectedRecord.pageUrl">打开此记录原页面</router-link>
   <button v-if="orderLocator" type="button" :disabled="completionLoading" @click="readSelectedOrder">读取本单完成依据（只读）</button>
   <p v-if="completionLoading" role="status">正在读取本单完成依据及生产进度。</p>
   <p v-if="completionError" role="alert">{{completionError}}；完成依据未知。</p>
   <p v-if="progressError" role="alert">{{progressError}}；订单进度未知。</p>
   <OrderProgressEvidence v-if="progress" :progress="progress" :completion="completion" />
   <section v-if="completion" aria-label="订单完成依据">
    <h4>订单 {{completionOrder}} · 原服务完成依据</h4><p>正式订单状态：<PceBusinessStatus :status-label="completion.formalStatusLabel" /></p>
    <p>完成条件：{{completion.factLoadStatus==='read_failed'?'读取失败，未知':completion.ready===true?'服务核验满足条件':completion.ready===false?'服务核验条件未齐':'尚未提供'}}。本页不办理完成或关闭。</p>
    <p>现场实际完成时间：{{completion.physicalCompletedAtStatus==='NOT_COLLECTED'?'尚未采集':completion.physicalCompletedAt||'未提供'}}。订单完成、审核及入库事件时间不能替代。</p>
    <ul v-if="orderReasons.length"><li v-for="(reason,i) in orderReasons" :key="i">{{reason.message}}</li></ul>
    <article v-for="line in completionLines" :key="line.id" class="coverage-line" :data-order-line-id="line.id">
     <h5>订单行 {{line.fact.lineNo}}<span v-if="line.item.materialName"> · {{line.item.materialName}}</span></h5>
     <p>供应承接：<PceBusinessStatus :status-label="line.fact.supplySource?.statusLabel || '未提供'" /></p>
     <p>供应覆盖：{{line.status}}</p>
     <dl class="coverage-quantities">
      <div v-for="[field,label] in coverageFields" :key="field"><dt>{{label}}</dt><dd :data-coverage-field="field">{{quantityText(line.coverage,field)}}</dd></div>
     </dl>
     <p>本行完成条件：{{booleanText(line.fact.ready)}}<template v-if="line.coverage?.manufacturingCompletionStatusLabel">。{{line.coverage.manufacturingCompletionStatusLabel}}</template>。</p>
     <ul v-if="line.fact.blockingReasons?.length"><li v-for="(reason,i) in line.fact.blockingReasons" :key="i">{{reason.message}}</li></ul>
     <p v-for="order in line.fact.workOrders||[]" :key="order.workOrderId">{{order.workOrderNo}} · {{order.statusLabel||'原状态标签未提供'}}；执行完工：{{booleanText(order.executionCompleted)}}；物理闭合：{{booleanText(order.mesClosed)}}。按原服务分别判定。</p>
    </article>
    <details><summary>完成依据技术追溯</summary><p>合同：{{completion.contractVersion}}；原订单版本：{{completion.salesOrderVersion}}；读取：{{completion.loadedAt||'未提供'}}。</p><p>各工序、工单、订单完成条件均由原服务核验，首页不重新计算；没有跨单位合计。</p></details>
   </section>
  </section>
  <section><h4>尚未提供的事实</h4><p v-if="role==='system'" data-field-contract="role-state">{{ ROLE_STATE_NOTICE }}</p>
   <p v-if="role==='planning'">完整缺料、延期、资源占用与偏差汇总尚未提供。按具体生产计划进入原排程及工单核对，不用要求日期自行推算延期。</p>
   <p v-if="role==='management'">本岗跨订单进度、异常及待办汇总尚未提供。授权订单可逐单查看生产进度及完成依据。</p>
   <p v-if="role==='system'">运行监测与健康指标合同尚未提供，不展示“正常”或健康分数。当前只展示原服务可读取的组织、账号及权限配置记录。</p>
  </section>
  <details><summary>本岗位操作说明</summary><p v-if="role==='system'">{{ ROLE_STATE_TRACE }}</p><p>用途：找到职责内记录，查看依据并进入现有正式页面。适用人员：当前{{roleLabel}}授权账号。</p><p>前置条件：本人有效登录、当前公司与原服务读取授权。步骤：选择记录类型，搜索原编号，查看依据，进入原页面，返回本人首页并刷新。结果：仅查询，不创建、审核、下达或修改任何业务与系统配置。</p><p>读取失败、未提供与无权限分别显示；结果未知时先刷新，不据旧数量办理。业务流程中心仍是完整办理主线。</p></details>
 </section>
</template>
<script setup>
import {ROLE_STATE_NOTICE,ROLE_STATE_TRACE} from '@/meta/runtime/authoritativeFieldPresentation.js'
import {computed,ref,watch,onBeforeUnmount} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {OFFICE_ROLES,officeOrderReadTiming,projectOfficeRecords} from '@/meta/runtime/enterpriseOfficeHome.js'
import request from '@/api/request.js'
import {getTabAuthEpoch} from '@/meta/runtime/tabAuthenticationContext.js'
import PceBusinessStatus from '@/meta/components/PceBusinessStatus.vue'
import OfficeRecordTable from '@/meta/components/OfficeRecordTable.vue'
import OrderProgressEvidence from '@/meta/components/OrderProgressEvidence.vue'
const props=defineProps({role:{type:String,required:true},facts:{type:Object,default:null}})
const roleLabel=computed(()=>OFFICE_ROLES.find(x=>x.key===props.role)?.label||'岗位')
const route=useRoute(),router=useRouter()
const routeMountedMs=performance.now(),orderReadTiming=ref(null)
const kinds=ref({}),localRecord=ref(null),completion=ref(null),completionOrder=ref(''),completionError=ref(''),completionLoading=ref(false)
const progress=ref(null),progressError=ref('')
const orderResource=computed(()=>props.facts?.results.find(resource=>resource.key==='orders'))
const orderLocator=computed(()=>props.role==='management'&&route.path==='/home'&&route.query.officeOrder)
const selectedRecord=computed(()=>orderLocator.value
 ? orderResource.value&&projectOfficeRecords(orderResource.value,'orders').find(row=>row.id===`orders:${orderLocator.value}`)
 : localRecord.value)
const completionItems=ref(new Map())
const coverageFields=[
 ['requiredQuantity','订单行需求量'],
 ['plannedManufacturingScopeQuantity','已计划制造量'],
 ['manufacturingCompletedQuantity','实际制造完成量'],
 ['confirmedStockCoverageQuantity','已确认库存覆盖量'],
]
let cycle=0
const links=computed(()=>props.role==='planning'?[{url:'/planning/requirements',label:'订单计划工作台'},{url:'/planning/requirements?section=formal-scheduling',label:'正式生产排程'},{url:'/planning/requirements?section=work-order-reception',label:'生产工单'}]:props.role==='management'?[{url:'/sales/orders',label:'订单查询'},{url:'/planning/requirements?section=work-order-reception',label:'原工单查询'}]:[{url:'/organization?tab=users',label:'用户与人员'},{url:'/organization?tab=roles',label:'角色权限'},{url:'/organization?tab=departments',label:'组织基础配置'}])
function categories(r){return r.key==='planning'?[{key:'demands',label:'订单与其他需求'},{key:'plans',label:'生产计划'}]:r.key==='system'?[{key:'users',label:'用户'},{key:'roles',label:'角色'},{key:'departments',label:'部门配置'}]:[{key:r.key,label:r.title}]}
const selectedKind=r=>kinds.value[r.key]||categories(r)[0].key
const records=r=>projectOfficeRecords(r,selectedKind(r))
const count=(r,k)=>projectOfficeRecords(r,k).length
const kindLabel=r=>categories(r).find(x=>x.key===selectedKind(r)).label
function selectKind(r,k){kinds.value={...kinds.value,[r.key]:k};inspectRecord(null)}
function inspectRecord(row){
 const id=props.role==='management'&&row?.id.startsWith('orders:') ? row.id.split(':')[1] : undefined
 if(id&&id===orderLocator.value)return
 localRecord.value=id ? null : row
 if(id||orderLocator.value)router.replace({query:{...route.query,officeOrder:id,officeProgress:undefined,officeOrderLine:undefined,officeProgressTask:undefined}})
}
function stateText(s){return {permission_denied:'无此读取权限',authentication_required:'请重新登录',read_failed:'读取失败',service_unavailable:'服务未提供'}[s]||'尚未读取'}
const booleanText=v=>v===true?'已满足':v===false?'未满足':'未提供'
const completionLines=computed(()=>(completion.value?.lines||[]).map(fact=>{
 const id=String(fact.salesOrderItemId)
 const item=completionItems.value.get(id)
 const supplied=fact.supplyCoverage
 const coverage=supplied?.contractVersion==='PCE-ORDER-SUPPLY-COVERAGE-V1'&&supplied.uomId===fact.uomId ? supplied : null
 const status=fact.completionStatus==='SOURCE_UNKNOWN' ? '供应来源待核' : coverage?.supplyCoverageStatusLabel||'未提供'
 return {id,item,fact,coverage,status}
}))
const orderReasons=computed(()=>(completion.value?.blockingReasons||[]).filter(reason=>
 !completionLines.value.some(line=>line.fact.blockingReasons?.some(entry=>
  entry.code===reason.code&&entry.scope===reason.scope&&entry.objectId===reason.objectId&&entry.message===reason.message))))
function quantityText(coverage,field){
 const value=coverage?.[field]
 return value==null||value==='' ? '未提供' : `${value} ${coverage.uomLabel||'（单位未提供）'}`
}
function clearCompletion(){
 completion.value=null
 completionOrder.value=''
 completionItems.value=new Map()
 completionError.value=''
 completionLoading.value=false
 progress.value=null
 progressError.value=''
 orderReadTiming.value=null
}
watch([()=>props.role,()=>props.facts,()=>selectedRecord.value?.id,()=>route.query.officeProgress],()=>{
 cycle++
 clearCompletion()
 if(!props.facts)localRecord.value=null
 if(orderLocator.value&&selectedRecord.value&&route.query.officeProgress==='1')loadCompletion(selectedRecord.value)
},{immediate:true})
function readSelectedOrder(){
 if(!selectedRecord.value||!orderLocator.value)return
 if(route.query.officeProgress==='1')return loadCompletion(selectedRecord.value)
 return router.replace({query:{...route.query,officeProgress:'1'}})
}
async function loadCompletion(row){
 const id=++cycle,epoch=getTabAuthEpoch(),orderId=row.id.split(':')[1]
 clearCompletion()
 completionLoading.value=true
 const read=(params)=>request({url:`/api/sales/orders/${encodeURIComponent(orderId)}/`,params,meta:{module:'SALES',readOnly:true,factLoad:true},timeout:120000}).catch(()=>null)
 const started=performance.now()
 let response=await read({includeProgressFacts:1,includeCompletionFacts:1})
 if(id!==cycle||epoch!==getTabAuthEpoch())return
 if(!response?.success&&response?.error?.code==='A08_RECORD_READ_FAILED'){
  progressError.value=response.error.message||'原服务未能读取订单进度'
  response=await read({includeCompletionFacts:1})
 }
 if(id!==cycle)return
 completionLoading.value=false
 if(epoch!==getTabAuthEpoch())return
 const order=response?.data?.order
 const facts=order?.mesCompletionFacts
 if(!response?.success||!facts||facts.factLoadStatus==='read_failed'){
  completionError.value=response?.error?.message||'原服务未能读取完成依据'
  return
 }
 const items=new Map((order.items||[]).map(item=>[String(item.id),item]))
 if(String(order.id)!==orderId||String(facts.salesOrderId)!==orderId||order.orderNo!==row.no||facts.salesOrderVersion!==order.version||
    facts.contractVersion!=='PCE-ORDER-MES-COMPLETION-V1'||!Array.isArray(facts.lines)||
    new Set(facts.lines.map(line=>String(line.salesOrderItemId))).size!==facts.lines.length||
    facts.lines.some(line=>line.salesOrderItemId==null||!items.has(String(line.salesOrderItemId)))){
  completionError.value='原服务返回的订单、订单行或完成依据与本次选择不一致'
  return
 }
 completionItems.value=items
 completionOrder.value=order.orderNo
 completion.value=facts
 if(progressError.value)return
 const current=order.progressFacts
 const completionLineIds=new Set(facts.lines.map(line=>line.salesOrderItemId))
 if(current?.contractVersion!=='PCE-ORDER-INTERNAL-PROGRESS-V1'||current.factStatus!=='PROVIDED'||
    current.salesOrderId!==order.id||current.orderNo!==order.orderNo||current.salesOrderVersion!==facts.salesOrderVersion||current.companyId!==facts.companyId||
    !Array.isArray(current.lines)||new Set(current.lines.map(line=>line.salesOrderItemId)).size!==completionLineIds.size||
    current.lines.length!==completionLineIds.size||current.lines.some(line=>!completionLineIds.has(line.salesOrderItemId)||!Array.isArray(line.workOrders))){
  progressError.value='原服务未提供与所选订单、版本及订单行一致的进度事实'
  return
 }
 progress.value=current
 orderReadTiming.value=officeOrderReadTiming(orderId,started)
}
onBeforeUnmount(()=>{cycle++})
</script>
<style scoped>
.office-home{min-width:0;overflow-wrap:anywhere}.office-home section{padding:16px;margin:16px 0;border:1px solid #d6e0ee;border-radius:10px;background:#fff}.office-home nav{display:flex;flex-wrap:wrap;gap:10px}.office-home button,.office-home a{min-height:44px;padding:8px 12px;cursor:pointer}.office-home a{display:inline-flex;align-items:center;color:#1757a1}.office-home summary{min-height:44px;cursor:pointer}.office-home dl{display:grid;grid-template-columns:minmax(100px,1fr) 3fr;gap:8px}.office-home dd{margin:0}.office-home h4{margin:8px 0}button[aria-pressed=true]{background:#eaf2ff;border:1px solid #1757a1}@media(max-width:600px){.office-home section{padding:10px}.office-home dl{grid-template-columns:1fr}.office-home dd{padding-left:12px}}
.coverage-line{margin:12px 0;padding:12px;border:1px solid #d6e0ee;border-radius:8px}
.coverage-line h5{margin:0;font-size:inherit}
.office-home .coverage-quantities{grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.coverage-quantities dt{color:#41546a}
.office-home .coverage-quantities dd{padding:0;font-weight:600;font-variant-numeric:tabular-nums}
@media(max-width:600px){.office-home .coverage-quantities{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
