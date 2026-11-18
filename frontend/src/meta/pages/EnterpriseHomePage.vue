<template>
  <PceListPageShell ref="homeScrollRef" :class="{'enterprise-home-document-scroll':officeRole==='management'}" module-id="enterprise-home" :compact-employee-view="true" :show-compact-page-actions="true" :governance="governance" :page-refresh-handler="refresh" :page-refresh-status="refreshStatus">
    <section class="enterprise-home" data-page-version="PCE-OFFICE-HOME-20261115-B4-R1.2" :data-visible-read-ms="visibleReadMs" :data-api-read-ms="apiReadMs" :data-read-cycle="readCycle" :data-identity-read-ms="identityReadMs" :data-resource-reads="JSON.stringify(resourceReads)" :aria-busy="refreshStatus === 'refreshing'">
      <header><button type="button" :disabled="refreshStatus === 'refreshing'" @click="refresh">刷新工作摘要</button><h2>{{ workMode ? '我的岗位工作' : '本人首页' }}</h2><p>核对当前企业及本人职责，再进入原业务页面办理。</p></header>
      <nav aria-label="首页工作视图"><router-link to="/home">本人首页</router-link><router-link to="/home?view=work">岗位工作</router-link><router-link to="/process-center">业务流程中心</router-link></nav>
      <p v-if="refreshStatus === 'refreshing'" role="status">正在读取当前企业、授权身份和职责目录。</p>
      <section v-if="profile"><h3>当前企业与授权身份</h3><p>{{ profile.organization?.name || '企业名称未提供' }} · {{ profile.identity?.realName || profile.identity?.username }}</p><p v-if="profile.employee">岗位资料：{{ profile.employee.departmentName || '未提供部门' }} / {{ profile.employee.positionName || '未提供岗位' }}</p><p>仅使用当前账号已获授权的工作范围；切换视图不会切换身份或增加权限。</p></section>
      <p v-if="profileError" role="alert">身份读取失败：{{ profileError }}。请刷新；登录失效时重新登录。</p>
      <router-link v-if="error || profileError" :to="{path:'/system-login',query:{redirect:route.fullPath}}">重新登录并返回当前工作位置</router-link>
      <nav aria-label="计划管理与维护视图"><router-link v-for="role in OFFICE_ROLES" :key="role.key" :to="roleRoute(role.key)" :aria-current="officeRole===role.key?'page':undefined">{{role.label}}</router-link><router-link :to="roleRoute('production')">现场岗位视图</router-link></nav>
      <EnterpriseOfficeHome v-if="officeRole" :role="officeRole" :facts="officeFacts"/>
      <section v-if="!officeRole" aria-label="岗位待办范围">
        <h3>本人岗位待办</h3>
        <p v-if="error" role="alert">{{ error }}；工作数量未知，请刷新或重新登录。</p>
        <template v-if="facts">
          <p class="environment">{{ facts.environmentLabel }} · 按原服务授权读取，不代表企业试点放行</p>
          <p>按职责分别查看；工序任务、工序交接单、成品单不合成一个总数。同一对象在不同职责下出现时，不跨岗位相加。</p>
          <nav class="role-grid" aria-label="选择岗位范围">
            <router-link v-for="group in facts.roleGroups" :key="group.key" :to="roleRoute(group.key)" :aria-current="activeGroup?.key === group.key ? 'page' : undefined">
              <strong>{{ group.label }}</strong><span>{{ countLabel(group) }}</span>
            </router-link>
          </nav>
        </template>
      </section>
      <section v-if="activeGroup" :aria-label="activeGroup.label + '工作摘要'">
        <header><h3>{{ activeGroup.label }}</h3><p>{{ activeGroup.scopeLabel }}</p></header>
        <p v-if="activeGroup.message" :role="activeGroup.loadStatus === 'read_failed' ? 'alert' : 'note'">{{ activeGroup.message }}</p>
        <dl v-if="activeGroup.loadStatus !== 'permission_denied' && activeGroup.loadStatus !== 'read_failed'" class="metrics"><div v-for="metric in activeGroup.metrics" :key="metric.label"><dt>{{ metric.label }}</dt><dd>{{ metric.value === null ? '未提供' : metric.value }}<small v-if="metric.value !== null"> {{ metric.unit }}</small></dd></div></dl>
        <p v-if="activeGroup.loadStatus === 'empty_valid'" role="status">当前没有服务端确认的该范围待处理事项；历史记录另列。</p>
        <p v-if="activeGroup.loadStatus === 'read_failed'" role="alert">读取失败，数量未知；请使用刷新重新核对，不据旧记录办理。</p>
        <nav aria-label="岗位原业务入口"><router-link v-for="link in activeGroup.links" :key="link.pageUrl" :to="link.pageUrl">{{ link.label }}</router-link></nav>
        <nav aria-label="待办与历史分开查看" v-if="activeGroup.loadStatus !== 'permission_denied' && activeGroup.loadStatus !== 'read_failed'">
          <router-link :to="roleRoute(activeGroup.key, 'pending')">待处理 {{ activeGroup.total === null ? '数量未提供' : activeGroup.total + ' 项／单（按本岗口径）' }}</router-link>
          <router-link :to="roleRoute(activeGroup.key, 'records')">授权记录 {{ activeGroup.recordCount === null ? '数量未知' : activeGroup.recordCount + ' 条' }}（非待办）</router-link>
          <router-link v-if="activeGroup.key === 'production'" :to="roleRoute(activeGroup.key, 'handovers')">工序交接单 {{ activeGroup.relatedTodos.length }} 单</router-link>
        </nav>
        <template v-if="activeGroup.recordCount !== null && (recordMode || route.query.list === 'handovers' || activeGroup.total !== null)">
          <h4>{{ recordMode ? '授权原记录' : route.query.list === 'handovers' ? '职责内工序交接单' : '当前待处理明细' }}</h4><p>{{ activeGroup.countBasis }} {{ recordMode ? '已审核、已入库记录不计入待办。' : '原动作是否可办，以详情页当次服务核验为准。' }}</p>
          <PceEnterpriseListTable :key="activeGroup.key + ':' + recordMode" :ref="element => table.tableRef = element" :contract="listContract" page-id="enterprise-home"
            :table-id="'enterprise-home-' + activeGroup.key + (recordMode ? '-records' : '-pending')" :rows="rows" :table-rows="table.filteredRows" :filter-schema="homeFilters"
            :filters="table.filters" :quick-search="table.quickSearch" :advanced-visible="table.advancedVisible" :selected-count="table.selectedRows.length"
            :active-filter-count="table.activeFilterCount" :sort-text="table.sortText" row-key="id" primary-field="no" primary-label="单据／任务编号" :primary-width="210"
            compact-freeze-primary min-width="760px" :action-width="140"
            @update:quick-search="table.quickSearch = $event" @search="table.appliedSearch = table.quickSearch" @toggle-advanced="table.advancedVisible = !table.advancedVisible"
            @clear-filters="table.clearFilters" @clear-sort="table.handleSort()" @export-current="table.exportCurrent" @clear-selection="table.selectedRows = []"
            @update-filter="table.updateFilter" @selection-change="table.selectedRows = $event" @sort-change="table.handleSort">
            <template #columns><el-table-column prop="recordTypeLabel" label="记录类型" min-width="150" /><el-table-column v-for="column in HOME_CONTEXT_COLUMNS" :key="column.field" :prop="column.field" :label="column.label" :min-width="column.width" /><el-table-column prop="contextLabel" label="原服务对象说明" min-width="230" /><el-table-column prop="statusLabel" label="单据／任务状态" width="210" /><el-table-column prop="reason" label="办理限制／查看说明" min-width="250" /></template>
            <template #actions="{row}"><router-link :to="row.pageUrl">进入原详情</router-link></template>
          </PceEnterpriseListTable>
        </template>
        <p>工单编号、工序名称及成品品名按原服务独立字段显示；独立工单名称和未提供的产品名称显示“未提供”。成品品名沿用原成品冻结口径。“原服务对象说明”保留原文，不拆解反造字段。</p><p v-if="activeGroup.key === 'production'">剩余数量为0不等于完工；必经非计量工序沿用实际经过登记与独立审核，不作为普通欠数任务。</p>
        <p v-if="activeGroup.key === 'workshop'">未提供完整计划与完成判定时，不生成延期天数或延期状态。已获授权的车间记录和原人员安排继续可查。</p>
        <p v-if="activeGroup.key === 'warehouse'">接收与入库沿用原成品单的一次正式动作，不新增审批；只读身份仍不能执行。</p>
      </section>
      <details v-if="facts" class="home-trace"><summary>摘要范围、原职责入口与追溯</summary><p>读取时间：{{ facts.observedAt }}</p><p>{{ facts.scopeLabel }}</p><p>授权工序任务记录：{{ facts.historyRecordCount }} 条（不含成品单与入库单，不作为待办）。</p><ul><li v-for="link in facts.links" :key="link.pageUrl"><router-link :to="link.pageUrl">{{ link.label }}</router-link></li></ul><p v-for="note in facts.unsupportedAlertTypes" :key="note">{{ note }}</p></details>
      <section><h3>操作说明与异常处理</h3><details><summary>按岗位办理与结果核对</summary>
        <p>生产员工：进入本人任务，核对工单、来源、单位、余额及前置条件，再开工或分次报工；提交后读取原记录。</p>
        <p>交接责任人：从本人产出及交接历史核对来源批次、可交数量和接收人，再交出或接收。短收不得自动补齐。</p>
        <p>独立审核人员：进入服务端提供的审核入口，核对依据和职责分离，办理后查询审核记录。</p>
        <p>仓管：进入本人指定的成品交接，核对原交接与仓库，接收后回读入库单、流水和余额。当前环境仍为测试用途。</p>
        <p>车间负责人、计划及管理人员：通过业务流程中心的既有授权入口办理工单、派工、计划和查询；首页不授予额外职责。</p>
        <p>提交结果未知或网络中断：保留原意图，先查询办理记录；重新登录后重读权限、状态和余额，不自动重复提交。</p>
      </details></section>
    </section>
  </PceListPageShell>
</template>
<script setup>
import {workPresentation} from '@/meta/runtime/workPresentationContext.js'
import {HOME_CONTEXT_COLUMNS,homeContextDisplay} from '@/meta/runtime/authoritativeFieldPresentation.js'
import {consumeHomeBootstrap} from "@/meta/runtime/homeReadTiming.js"
import {computed, reactive, watch, ref, inject, onMounted, onBeforeUnmount, nextTick} from 'vue'
import {useRoute} from 'vue-router'
import EnterpriseOfficeHome from '@/meta/components/EnterpriseOfficeHome.vue'
import {OFFICE_ROLES,isOfficeRole,defaultOfficeRole,loadOfficeFacts,homeRecordTypeLabel} from '@/meta/runtime/enterpriseOfficeHome.js'
import PceListPageShell from '@/meta/components/PceListPageShell.vue'
import {loadPermissionProfile} from '@/meta/runtime/permissionProfileRuntime.js'

import {PAGE_OBSERVABILITY_ACTIONS_KEY} from '@/meta/runtime/pageObservabilityActions.js'
import {getTabAuthEpoch} from '@/meta/runtime/tabAuthenticationContext.js'
import request from '@/api/request.js'
import PceEnterpriseListTable from '@/meta/components/PceEnterpriseListTable.vue'
import {createPceEnterpriseListContract, usePceEnterpriseListRuntime} from '@/meta/runtime/pceEnterpriseListContract.js'

const homeScrollRef=ref(null),homeScrollOwner=workPresentation.epoch()
const route=useRoute(), workMode=computed(()=>route.query.view==='work')
let homeScrollKey='home-scroll:'+route.fullPath
let managementScrollOwned=route.query.role==='management'
const officeRole=computed(()=>route.query.role?(isOfficeRole(route.query.role)?route.query.role:''):defaultOfficeRole(profile.value))
const officeFacts=ref(null)
const identityReadMs=ref(null),resourceReads=ref([])
const apiReadMs=ref(null),visibleReadMs=ref(null),readCycle=ref(0)
const profile=ref(null), facts=ref(null), surface=ref(null), error=ref(''), profileError=ref(''), refreshStatus=ref('idle')
const governance={pageCode:'enterprise-home',version:'PCE-OFFICE-HOME-20261115-B4-R1.2',frameworkVersion:'PCE-ENTERPRISE-LIST-CONTRACT-V1.1',purpose:'从本人授权职责进入同一业务对象及原页面。',allowed:['读取本人身份与授权入口'],forbidden:['切换呈现增加权限','用历史任务数量冒充待办','首页执行业务写入'],flowSteps:['本人首页','职责目录','原业务办理','结果回读'],currentFlowStep:'本人首页'}
let requestId=0,bootstrapStart=consumeHomeBootstrap()
const activeGroup=computed(()=>officeRole.value?null:(facts.value?.roleGroups?.find(x=>x.key===route.query.role) || facts.value?.roleGroups?.find(x=>x.loadStatus!=='permission_denied') || facts.value?.roleGroups?.[0]))
const recordMode=computed(()=>route.query.list==='records')
const rows=computed(()=>activeGroup.value ? (recordMode.value ? activeGroup.value.records : route.query.list==='handovers' ? activeGroup.value.relatedTodos : activeGroup.value.todos).map(row=>({...row,...homeContextDisplay(row),recordTypeLabel:homeRecordTypeLabel(row,{groupKey:activeGroup.value.key,recordMode:recordMode.value,handovers:route.query.list==='handovers'})})) : [])
const homeFilters=[{field:'no',label:'单据／任务编号',filterType:'text'},{field:'recordTypeLabel',label:'记录类型',filterType:'text'},...HOME_CONTEXT_COLUMNS.map(column=>({field:column.field,label:column.label,filterType:'text'})),{field:'contextLabel',label:'原服务对象说明',filterType:'text'},{field:'statusLabel',label:'单据／任务状态',filterType:'text'}]
const listContract=createPceEnterpriseListContract({pageCode:'enterprise-home',pageType:'list',title:'本人岗位待办',moduleCode:'MES'})
const table=reactive(usePceEnterpriseListRuntime({rows,filterSchema:homeFilters,pageCode:'enterprise-home',searchFields:['no','recordTypeLabel',...HOME_CONTEXT_COLUMNS.map(column=>column.field),'contextLabel','statusLabel','reason'],exportFileName:'本人岗位查看结果.csv',exportColumns:[{field:'no',label:'单据／任务编号'},{field:'recordTypeLabel',label:'记录类型'},...HOME_CONTEXT_COLUMNS.map(({field,label})=>({field,label})),{field:'contextLabel',label:'原服务对象说明'},{field:'statusLabel',label:'单据／任务状态'},{field:'reason',label:'办理限制／查看说明'}]}))
function roleRoute(role,list='pending'){return {path:'/home',query:{...route.query,role,list}}}
function countLabel(group){return {permission_denied:'无此岗位读取范围',read_failed:'读取失败 · 数量未知',service_unavailable:'部分接入 · 待办数未提供'}[group.loadStatus] || `待处理 ${group.total} ${group.key==='warehouse'?'单':'项'}`}
watch(()=>[route.query.role,route.query.list],()=>{table.clearFilters();table.clearSort();table.selectedRows=[]})

async function refresh(){
 identityReadMs.value=null;resourceReads.value=[]
 const requestStarted=performance.now();const started=bootstrapStart ?? requestStarted;bootstrapStart=null;readCycle.value++;visibleReadMs.value=null;apiReadMs.value=null
 const id=++requestId,epoch=getTabAuthEpoch();officeFacts.value=null;profile.value=null;facts.value=null;surface.value=null;error.value='';profileError.value='';refreshStatus.value='refreshing'
 const valid=()=>id===requestId&&epoch===getTabAuthEpoch()
 await loadPermissionProfile({force:true}).then(p=>{if(valid())profile.value=p}).catch(e=>{if(valid())profileError.value=e.message})
 if(!valid())return
 identityReadMs.value=performance.now()-requestStarted
 const timedRequest=async config=>{const start=performance.now();try{const result=await request(config);if(valid())resourceReads.value.push({url:config.url,startMs:start-requestStarted,durationMs:performance.now()-start,status:result.meta?.status??null});return result}catch(e){if(valid())resourceReads.value.push({url:config.url,startMs:start-requestStarted,durationMs:performance.now()-start,status:e.response?.status??0});throw e}}
 if(profileError.value){refreshStatus.value='error';return}
 await (officeRole.value?loadOfficeFacts(officeRole.value,timedRequest).then(data=>({success:true,data:{office:data}})):request({url:'/api/planning/enterprise-work-summary/',timeout:120000,meta:{module:'MES',readOnly:true}})).then(r=>{if(!valid())return;apiReadMs.value=performance.now()-requestStarted;surface.value=r;if(r.data?.office){officeFacts.value=r.data.office;return}if(!r.success||!r.data?.summary)throw Error(r.error?.message||'职责读取失败');facts.value=r.data.summary}).catch(e=>{if(valid())error.value=e.message})
 if(valid()){refreshStatus.value=error.value||profileError.value||officeFacts.value?.results.some(r=>r.state==='read_failed')?'error':'success';await nextTick();await new Promise(resolve=>requestAnimationFrame(resolve));if(valid())visibleReadMs.value=performance.now()-started}
}
watch(()=>route.query.role,(role,previous)=>{
 // An explicit link to the already selected default view only changes the URL.
 if((role||defaultOfficeRole(profile.value))!==(previous||defaultOfficeRole(profile.value)))refresh()
})
const observability=inject(PAGE_OBSERVABILITY_ACTIONS_KEY,null),provider={factOwner:'enterprise-home',refresh,buildDiagnostics:()=>({factOwner:'enterprise-home',factSource:'server',strictFacts:surface.value,officeFacts:officeFacts.value,passed:refreshStatus.value==='success'&&!officeFacts.value?.results.some(r=>r.state==='read_failed')&&!facts.value?.roleGroups?.some(g=>g.loadStatus==='read_failed')})}
function authChanged(){requestId++;profile.value=null;facts.value=null;surface.value=null;refresh()}
watch(()=>[route.path,route.fullPath,officeRole.value],([path,fullPath,role])=>{if(path==='/home'&&role==='management'){managementScrollOwned=true;homeScrollKey='home-scroll:'+fullPath}})
onMounted(async()=>{observability?.register?.(provider);window.addEventListener('pce:authentication-changed',authChanged);await refresh();if(officeRole.value==='management'){managementScrollOwned=true;const saved=workPresentation.read(homeScrollKey);if(saved&&homeScrollOwner===workPresentation.epoch())homeScrollRef.value?.$el?.scrollTo({top:saved.top,left:0})}})
onBeforeUnmount(()=>{if(managementScrollOwned)workPresentation.save(homeScrollKey,{top:homeScrollRef.value?.$el?.scrollTop||0},homeScrollOwner);requestId++;observability?.unregister?.(provider);window.removeEventListener('pce:authentication-changed',authChanged)})
</script>
<style scoped>
.enterprise-home{max-width:1200px;margin:auto;color:#24344b;font-size:16px;line-height:1.65}.enterprise-home section{background:white;border:1px solid #d7e0eb;border-radius:10px;padding:20px;margin:16px 0}.enterprise-home nav,.entry-grid{display:flex;flex-wrap:wrap;gap:12px}.entry-grid{list-style:none;padding:0}.enterprise-home a{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;color:#1757a1}.enterprise-home button{min-height:44px;padding:8px 16px;cursor:pointer}.enterprise-home summary{cursor:pointer;min-height:44px}.enterprise-home a:focus-visible,.enterprise-home summary:focus-visible{outline:3px solid #1757a1;outline-offset:3px}@media(max-width:600px){.enterprise-home section{padding:12px}.entry-grid{display:block}.enterprise-home{font-size:16px}}

.enterprise-home{min-width:0;overflow-wrap:anywhere}.enterprise-home .role-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.role-grid a{display:flex;flex-direction:column;align-items:flex-start;padding:16px;border:1px solid #cfdaea;border-radius:8px;text-decoration:none}.role-grid a[aria-current="page"]{background:#edf4ff;border-color:#4378c7}.role-grid span{font-size:14px;color:#526780}.metrics{display:flex;flex-wrap:wrap;gap:16px}.metrics div{padding:12px 18px;background:#f4f7fc;border-radius:8px}.metrics dd{font-size:24px;margin:0;color:#173c68}.metrics small{font-size:16px}.home-trace{margin:16px 0}.enterprise-home header h3{margin:0}.enterprise-home h4{margin-bottom:6px}@media(max-width:760px){.enterprise-home .role-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.role-grid a{padding:12px;min-width:0}.enterprise-home section{min-width:0}.metrics{gap:8px}.metrics div{padding:8px 12px}.enterprise-home a{padding:0 8px}}

/* Management home has one bounded vertical owner, with the existing presentation return position. */
.enterprise-home-document-scroll { max-height:calc(100dvh - var(--pce-account-bookmark-height,52px) - var(--pce-system-bar-height,72px) - 20px); overflow-x:hidden; overflow-y:auto; scrollbar-gutter:stable; grid-auto-rows:max-content; align-content:start; min-height:0; }
.enterprise-home-document-scroll :deep(.pce-list-page-content) { overflow-x: clip; overflow-y: visible; }
</style>
