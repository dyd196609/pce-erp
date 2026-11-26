<template>
  <section class="card order-execution-panel" data-fact-source="server" data-order-execution-owner="order">
    <h2>订单工序执行安排</h2>
    <p>标准路线版本决定有哪些工序及顺序，只能在企业基础资料维护。这里选择固定标准版本，办理本订单已有工序的执行、不执行或待核定；材料不变时不增加物料清单版本，执行选择不增加路线版本。</p>
    <p>草稿直接保存并保留办理审计；已确认或被下游引用时，通过安排自身修订办理，不冒用标准路线版本号，也不新增审批。测试用途仍禁止制造。</p>
    <router-link :to="foundationRoute">标准模板缺项？前往企业基础资料→工艺路线</router-link>
    <p v-if="error" role="alert">{{ error }}</p>
    <el-button :loading="busy" @click="load">刷新订单安排</el-button>
    <p class="source-identity-note">查看已有安排时，以下选择器回填真实来源；改选但未显式固定时，已保存来源仍以下方安排身份为准。长选项可展开完整查看。</p>
    <div v-if="choices" class="selection">
      <label>来源物料清单版本（当前安排回填）
        <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-bom" v-model="bomId" :disabled="navigationLocked" @change="preview=null" placeholder="明确选择已有版本"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option v-for="b in choices.bomVersions" :key="b.id" :value="b.id" :label="`版本名称${b.bom_version}（记录ID ${b.id}）`" /></el-select>
      </label>
      <label>固定标准路线版本（当前安排回填）
        <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-routing" v-model="routeId" :disabled="navigationLocked" placeholder="选择准确版本，不自动取最新版" @change="preview=null"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option v-for="v in choices.standardVersions" :key="v.id" :value="v.id" :label="`${v['routing__routing_code']}／${v['routing__name']}｜版本名称${v.routing_version}｜修订号${v.revision}｜记录ID ${v.id}`" /></el-select>
      </label>
      <el-button :disabled="!bomId || !routeId || navigationLocked" @click="previewStandard">读取所选标准结构</el-button>
      <template v-if="preview"><span>标准结构 {{ preview.steps.length }} 步（只读）</span><el-input v-model="selectReason" placeholder="固定引用的图纸或业务依据" style="width:28em" /><el-checkbox v-model="resetExecution">草稿显式重新固定引用并重新安排（原依据保留审计）</el-checkbox><el-button :disabled="!selectReason.trim() || !choices.maintenanceAuthorization?.allowed || navigationLocked" @click="selectStandard">固定此标准版本</el-button></template>
    </div>
    <el-select size="default" popper-class="order-execution-select-options" v-if="arrangements.length" class="order-select order-select-arrangement" v-model="selectedId" placeholder="选择订单安排" :disabled="navigationLocked" @change="changeArrangement"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template>
      <el-option v-for="a in arrangements" :key="a.id" :value="a.id" :label="`${a.orderNo}｜安排记录ID ${a.id}｜自身修订号${a.arrangementRevision}｜物料清单记录ID ${a.bomVersionId}`" />
    </el-select>
    <article v-if="selected">
      <h3>{{ selected.orderNo }} · {{ selected.purposeLabel }}</h3>
      <p>物料清单版本名称：{{ selected.bomVersionName }}；记录ID：{{ selected.bomVersionId }}。标准路线：{{ selected.routingCode }}／{{ selected.routingName }}；版本名称：{{ selected.routingVersionName }}；修订号：{{ selected.routingVersionRevision }}；固定记录ID：{{ selected.routingVersionId }}。</p>
      <p>来源核算 {{ selected.sourceCalculationNo }}（记录{{ selected.sourceCalculationId }}），工程来源{{ selected.sourceId }}，冻结基线{{ selected.baselineId }}；来源均由服务端真实关联读取。</p>
      <p><strong>订单执行安排记录ID {{ selected.id }}／自身修订号{{ selected.arrangementRevision }}</strong>；{{ selected.statusLabel }}；编辑序号{{ selected.editVersion }}。编辑序号用于并发保存控制，与标准路线修订号、安排自身修订号及记录ID不同。</p>
      <div class="execution-save-toolbar" data-order-execution-save-toolbar>
        <div class="save-primary-row"><strong role="status" aria-live="polite">{{ saveStatusLabel }}</strong>
          <el-button type="primary" size="large" data-order-execution-save :loading="saving" :disabled="!action('save')?.executable || busy || saving || (!dirty && !retryPending)" @click="saveDraft">{{ retryPending && !saving ? '核对上次保存结果' : (action('save')?.displayName || '保存订单执行安排') }}</el-button>
          <span>{{ dirtyCount }}步有未保存修改；待核定步骤也可以保存草稿。</span></div>
        <label class="save-reason">本次办理说明<el-input ref="saveReasonInput" v-model="reason" aria-label="本次办理说明" :disabled="editingLocked" maxlength="300" show-word-limit placeholder="填写本次办理说明，再点击保存；不是确认或发布" /></label>
        <p v-if="!action('save')?.executable" class="save-error">不能保存：{{ action('save')?.disabledReason || '尚未取得服务端维护权限' }}</p>
        <p v-if="saveMessage" :class="saveStatus==='success' ? 'save-success' : 'save-error'" aria-live="polite">{{ saveMessage }}</p>
        <p v-if="dirty">有未保存修改。离开或浏览器刷新前会提醒；页面内刷新保留输入，请先保存或明确放弃。</p>
        <p v-if="retryPending">上次结果尚未核实，输入保留并暂时锁定；“核对上次保存结果”复用原请求，不重复写入。</p>
        <el-button v-if="dirty && !retryPending" :disabled="busy || saving" @click="discardAndReload">放弃未保存修改并重新读取</el-button>
        <ul v-if="issues.length" class="field-issues" role="alert"><li v-for="issue in issues" :key="`${issue.stepId}-${issue.field}-${issue.message}`" class="field-issue">{{ issue.message }}</li></ul>
      </div>
      <label>适用对象
        <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-object" v-model="objectId" :disabled="navigationLocked" @change="changeObject"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option :value="0" label="整个订单行" /><el-option v-for="obj in selected.objects" :key="obj.id" :value="obj.id" :label="`冻结设计对象${obj.id}（设计项${obj.design_item_id}）`" /></el-select>
      </label>
      <p>下方工序区域可独立滚动，保存按钮位于区域前方。按标准版本真实顺序展示 {{ selected.standardStepCount }} 步。执行但无定量数据仍经过，不能用零值代替未知；订单页面不能增删工序。用户明确依据与补拟测试假设分别保存。</p>
      <div class="execution-steps-scroll" aria-label="订单工序执行编辑区域" tabindex="0"><ol class="execution-step-list">
        <li class="execution-step" :data-step-id="row.stepId" v-for="row in rows" :key="row.stepId">
          <strong>{{ row.sequence }}．{{ row.operationName }}</strong>；工作中心：{{ row.workCenterName }}；前序：{{ row.predecessors.join('、') || '起点' }}
          <div class="decision">
            <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-decision" v-model="row.decision" :disabled="!action('save')?.executable || editingLocked"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option value="REQUIRED" label="执行（经过，定量另行核定）" /><el-option value="NOT_APPLICABLE" label="本单不执行（需明确依据）" /><el-option value="PENDING" label="待核定（依据尚不足）" /></el-select>
            <el-select size="default" popper-class="order-execution-select-options" class="order-select order-select-evidence" v-model="row.evidenceClass" :disabled="!action('save')?.executable || editingLocked"><template #label="{label}"><span class="order-select-label" :title="label">{{ label }}</span></template><el-option value="USER_CONFIRMED" label="用户／业务明确依据" /><el-option value="TEST_ASSUMPTION" label="补拟测试假设" /><el-option value="UNRESOLVED" label="依据待核定" /></el-select>
            <el-input v-model="row.basis" :disabled="!action('save')?.executable || editingLocked" type="textarea" :rows="2" placeholder="图纸或业务依据，不从材料空值推断" />
          </div>
          <span v-if="isRowDirty(row)" class="unsaved-badge">此步有未保存修改</span>
          <p>服务端已保存：{{ row.decisionLabel }}；{{ row.evidenceLabel }}；适用：{{ row.scopeLabel }}；办理人：{{ row.operatorLabel || '尚未办理' }}；审计：{{ row.auditId || '尚无' }}</p><p v-for="issue in issues.filter(item=>item.stepId===row.stepId)" :key="issue.field+issue.message" class="save-error">{{ issue.message }}</p>
        </li>
      </ol></div>
      <details class="workflow-actions"><summary>确认／安排自身修订（与保存草稿分开）</summary><p>保存允许待核定；确认才要求全部必要判断齐备。先保存工序修改，再办理确认。</p><el-button v-for="name in ['confirm','revise']" :key="name" :disabled="!action(name)?.executable || editingLocked || dirtyCount>0 || !reason.trim()" :title="dirtyCount ? '请先保存修改' : action(name)?.disabledReason" @click="writeWorkflow(name)">{{ action(name)?.displayName || '动作状态未取得' }}</el-button><p>{{ action('confirm')?.disabledReason }}</p></details>
      <details><summary>本安排办理记录（标准版本与订单安排分别留痕）</summary><p v-for="audit in selected.auditHistory" :key="audit.id">审计{{ audit.id }}：{{ audit.actor__username }} · {{ audit.reason }} · {{ audit.created_at }}</p></details>
    </article>
  </section>
</template>
<script setup>
import {computed,ref,watch,onMounted,onBeforeUnmount} from 'vue'
import {onBeforeRouteLeave,onBeforeRouteUpdate} from 'vue-router'
import {ElMessageBox} from 'element-plus'
import {pdeApi} from '@/api/pde'
import {getFoundationCanonicalModuleByEntity} from '@/meta/master-data/foundationEntryUnificationRegistry'
import {resolveCurrentIdentity} from '@/meta/runtime/pageTitleManager'
import {assertFoundationRequestIdentity} from '@/meta/runtime/foundationRoutingRead'
import {changedExecutionRows,executionFieldIssues,draftErrorMessage,createExecutionDraftSaver} from '@/meta/runtime/orderExecutionDraft'
const emit=defineEmits(['facts','state','draft-state'])
const u=r=>r?.data??r
const foundationRoute=getFoundationCanonicalModuleByEntity('routings').routePath
const arrangements=ref([]),choices=ref(null),selected=ref(null),selectedId=ref(null),objectId=ref(0),rows=ref([]),error=ref(''),busy=ref(false)
const bomId=ref(null),routeId=ref(null),preview=ref(null),selectReason=ref(''),reason=ref(''),resetExecution=ref(false)
const originalRows=ref([]),saveStatus=ref('idle'),saveMessage=ref(''),retryPending=ref(false),serverIssues=ref([]),saveReasonInput=ref(null)
let generation=0,loadGeneration=0,loadedObjectId=0
const action=name=>selected.value?.availableActions?.find(a=>a.action===name)
const key=()=>`order-execution-${crypto.randomUUID()}`
const changed=computed(()=>changedExecutionRows(rows.value,originalRows.value))
const dirtyCount=computed(()=>changed.value.length)
const dirty=computed(()=>dirtyCount.value>0 || Boolean(reason.value.trim()))
const saving=computed(()=>['saving','verifying'].includes(saveStatus.value))
const editingLocked=computed(()=>busy.value || saving.value || retryPending.value)
const navigationLocked=computed(()=>editingLocked.value || dirty.value)
const issues=computed(()=>[...new Map([...executionFieldIssues(rows.value,originalRows.value),...serverIssues.value].map(x=>[`${x.stepId}:${x.field}:${x.message}`,x])).values()])
const saveStatusLabel=computed(()=>({saving:'保存中，请等待…',verifying:'已提交，正在核对服务端结果…',success:dirty.value?'有未保存修改':'保存成功，已回读',unverified:'保存结果待核对',error:'保存未完成，输入保留'}[saveStatus.value] || (dirty.value?'有未保存修改':'当前没有未保存修改')))
const isRowDirty=row=>changed.value.some(item=>item.stepId===row.stepId)
function applyLoaded(data){
  const value=data.orderExecutionArrangements?.[0]
  if(!value)throw Error('服务端未返回所选安排，不使用缓存补齐。')
  assertFoundationRequestIdentity(resolveCurrentIdentity(),value.requestIdentity)
  selected.value=value;selectedId.value=value.id;bomId.value=value.bomVersionId;routeId.value=value.routingVersionId;rows.value=value.steps.map(row=>({...row}));originalRows.value=value.steps.map(row=>({...row}));loadedObjectId=objectId.value
  arrangements.value=arrangements.value.map(a=>a.id===value.id?value:a)
  emit('facts',data);emit('state','loaded')
}
async function readSelected(){
  const current=++generation;error.value='';emit('state','loading')
  try{const data=u(await pdeApi.orderRoutingExecution({arrangementId:selectedId.value,...(objectId.value?{baselineItemId:objectId.value}:{})}));if(current!==generation)return;applyLoaded(data)}
  catch(e){if(current===generation){selected.value=null;rows.value=[];originalRows.value=[];error.value=draftErrorMessage(e);emit('facts',null);emit('state','read_failed')}}
}
function changeArrangement(){if(dirty.value || retryPending.value){selectedId.value=selected.value?.id;error.value='请先保存或明确放弃未保存修改，再切换安排。';return}objectId.value=0;return readSelected()}
function changeObject(){if(dirty.value || retryPending.value){objectId.value=loadedObjectId;error.value='请先保存或明确放弃修改，再切换适用对象。';return}return readSelected()}
async function load(){
  if(dirty.value || retryPending.value){error.value='订单安排有未保存修改或未核实请求，未重新读取；输入仍保留，请先保存或明确放弃。';return false}
  const owner=++loadGeneration;const current=++generation;busy.value=true;error.value='';selected.value=null;rows.value=[];originalRows.value=[];choices.value=null;arrangements.value=[];preview.value=null;emit('facts',null);emit('state','loading')
  try{const [response,options]=await Promise.all([pdeApi.orderRoutingExecution(),pdeApi.orderRoutingExecution({action:'choices'})]);if(current!==generation)return
    const data=u(response),optionData=u(options);assertFoundationRequestIdentity(resolveCurrentIdentity(),optionData.requestIdentity)
    if(!Array.isArray(data.orderExecutionArrangements))throw Error('订单安排事实未取得')
    arrangements.value=data.orderExecutionArrangements;choices.value=optionData
    if(arrangements.value.length){selectedId.value=arrangements.value.some(a=>a.id===selectedId.value)?selectedId.value:arrangements.value[0].id;await readSelected()}else{emit('facts',data);emit('state','loaded')}
  }catch(e){if(current===generation){error.value=draftErrorMessage(e);emit('facts',null);emit('state','read_failed')}}finally{if(owner===loadGeneration)busy.value=false}
}
const saver=createExecutionDraftSaver({post:async payload=>u(await pdeApi.saveOrderRoutingExecution(payload)),read:async(id,object)=>{const envelope=u(await pdeApi.orderRoutingExecution({arrangementId:id,...(object?{baselineItemId:object}:{})}));return {envelope,arrangement:envelope.orderExecutionArrangements?.[0]}},makeKey:key,assertIdentity:actual=>assertFoundationRequestIdentity(resolveCurrentIdentity(),actual),onState:state=>{saveStatus.value=state.status;retryPending.value=state.pending;saveMessage.value=state.message||'';serverIssues.value=state.fieldErrors||[]}})
async function saveDraft(){
  if(!selected.value || !action('save')?.executable || busy.value || saving.value)return
  error.value=''
  const outcome=await saver.save({arrangement:selected.value,rows:rows.value,originalRows:originalRows.value,objectId:objectId.value||null,reason:reason.value})
  if(outcome.ok){applyLoaded(outcome.loaded.envelope);reason.value='';saveMessage.value=outcome.message}
  else if(!reason.value.trim() && !outcome.fieldErrors?.length)saveReasonInput.value?.focus()
}
async function discardAndReload(){
  if(retryPending.value){error.value='上次结果尚未核实，请先核对保存请求。';return}
  try{await ElMessageBox.confirm('放弃当前未保存输入并从服务端重新读取？此前已保存记录不变。','有未保存修改',{confirmButtonText:'放弃并重新读取',cancelButtonText:'保留输入',type:'warning'})}catch{return}
  rows.value=originalRows.value.map(row=>({...row}));reason.value='';serverIssues.value=[];saveMessage.value='';saveStatus.value='idle';await load()
}
async function previewStandard(){try{error.value='';preview.value=u(await pdeApi.orderRoutingExecution({action:'preview',bomVersionId:bomId.value,routingVersionId:routeId.value}))}catch(e){preview.value=null;error.value=draftErrorMessage(e)}}
async function selectStandard(){if(navigationLocked.value)return;busy.value=true;try{const existing=arrangements.value.find(a=>a.bomVersionId===bomId.value);const result=u(await pdeApi.saveOrderRoutingExecution({action:'select',bomVersionId:bomId.value,routingVersionId:routeId.value,referenceHash:preview.value.referenceHash,reason:selectReason.value,idempotencyKey:key(),expectedEditVersion:existing?.editVersion,resetExecution:resetExecution.value}));selectedId.value=result.id;objectId.value=0;preview.value=null;resetExecution.value=false;await load()}catch(e){error.value=draftErrorMessage(e)}finally{busy.value=false}}
async function writeWorkflow(name){if(editingLocked.value || dirtyCount.value)return;busy.value=true;try{await pdeApi.saveOrderRoutingExecution({action:name,arrangementId:selected.value.id,reason:reason.value,idempotencyKey:key(),expectedEditVersion:selected.value.editVersion});reason.value='';await load()}catch(e){error.value=draftErrorMessage(e)}finally{busy.value=false}}
function beforeUnload(event){if(dirty.value || retryPending.value){event.preventDefault();event.returnValue='';return ''}}
async function permitLeave(){if(!dirty.value && !retryPending.value)return true;try{await ElMessageBox.confirm('当前有未保存修改或未核实请求。离开会丢失本地输入，是否仍要离开？','尚未完成保存',{confirmButtonText:'仍然离开',cancelButtonText:'返回保存',type:'warning'});return true}catch{return false}}
onBeforeRouteLeave(permitLeave);onBeforeRouteUpdate(permitLeave)
onMounted(()=>window.addEventListener('beforeunload',beforeUnload))
onBeforeUnmount(()=>{generation++;loadGeneration++;window.removeEventListener('beforeunload',beforeUnload)})
watch([dirty,dirtyCount,saveStatus,retryPending],()=>emit('draft-state',{hasUnsavedChanges:dirty.value,changedStepCount:dirtyCount.value,saveStatus:saveStatus.value,unverifiedRequest:retryPending.value}),{immediate:true})
watch(()=>JSON.stringify(rows.value.map(row=>[row.stepId,row.decision,row.evidenceClass,row.basis])),()=>{if(!saving.value && !retryPending.value)serverIssues.value=[]})
watch(dirty,value=>{if(value && saveStatus.value==='success'){saveStatus.value='idle';saveMessage.value=''}})
defineExpose({load})
</script>
<style scoped>
.selection,.decision{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:14px 0}.order-execution-panel label{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.execution-save-toolbar{position:sticky;top:64px;z-index:12;border:1px solid #a7c5ed;border-radius:10px;background:#f8fbff;padding:14px;margin:16px 0;box-shadow:0 3px 12px #203b5c18}.save-primary-row{display:flex;align-items:center;flex-wrap:wrap;gap:14px}.save-reason{margin-top:12px}.save-reason :deep(.el-input){flex:1;min-width:240px}.execution-save-toolbar p{margin:8px 0}.execution-steps-scroll{max-height:65vh;overflow-y:auto;border:1px solid #dce4ed;border-radius:8px;padding:0 16px;overscroll-behavior:contain}.execution-step-list{margin:0;padding-left:24px}.execution-step{padding:16px 0;border-bottom:1px solid #dce4ed}.unsaved-badge{margin-left:12px;color:#8b4b00;font-weight:700}.save-error,.field-issue{color:#a52020}.save-success{color:#146c3b}.field-issues{max-height:144px;overflow-y:auto;margin:8px 0;padding-left:20px}.field-issue{padding:4px 0;line-height:1.5}.workflow-actions{margin:16px 0}
.order-execution-panel .order-select{flex:0 1 auto;min-width:0;max-width:100%;vertical-align:middle}.order-select-bom{width:17rem}.order-select-routing{width:23rem}.order-select-arrangement{width:28rem}.order-select-object{width:18rem}.order-select-decision{width:16rem}.order-select-evidence{width:12rem}
.order-execution-panel .selection{align-items:end;gap:12px}.order-execution-panel .selection>label{display:grid;gap:6px;min-width:0}.source-identity-note{font-size:13px;color:#52657d}.order-select-label{display:block;width:100%;line-height:24px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.order-execution-panel :deep(.order-select .el-select__wrapper){height:32px;min-height:32px;padding:4px 10px;box-sizing:border-box;align-items:center;line-height:24px}.order-execution-panel :deep(.order-select .el-select__selection){height:24px;min-width:0;flex-wrap:nowrap;align-items:center}.order-execution-panel :deep(.order-select .el-select__placeholder){line-height:24px;white-space:nowrap}.order-execution-panel :deep(.order-select .el-select__suffix){height:24px;display:flex;align-items:center}.order-execution-panel :deep(.order-select .el-select__caret){width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center}
:global(.order-execution-select-options .el-select-dropdown__list){max-width:min(34rem,calc(100vw - 32px))}:global(.order-execution-select-options .el-select-dropdown__item){min-height:32px;height:auto;box-sizing:border-box;line-height:20px;padding:6px 12px;display:flex;align-items:center;white-space:normal;overflow-wrap:anywhere;word-break:normal}:global(.order-execution-select-options .el-select-dropdown__item span){white-space:normal;line-height:20px}
@media(max-width:760px){.order-execution-panel .selection{display:grid;grid-template-columns:minmax(0,1fr)}.order-execution-panel .selection>label,.order-execution-panel .selection .order-select{width:100%}}
@media(max-width:720px){.execution-save-toolbar{top:8px}.save-primary-row .el-button{width:100%;margin:0}.order-execution-panel :deep(.el-select){max-width:100%}.execution-steps-scroll{max-height:60vh}}
</style>
