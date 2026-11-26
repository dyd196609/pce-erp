<template>
  <section class="card" data-fact-source="server">
    <h2>历史测试路线绑定与固定版本（只读沿革）</h2>
    <p><strong>历史正式承接（当前公司）：{{ formalHandoffCount ?? '未取得' }} 项</strong>。此数来自普通列表的正式物料清单承接事实，不包含下方测试绑定。</p>
    <template v-if="loaded && summary">
      <p v-for="scope in summary.orderGroups" :key="scope.orderId"><strong>订单 {{ scope.orderNo }}：本单测试绑定共 {{ scope.testBindingCount }} 项，其中历史方案 {{ scope.historicalPlanCount }} 项</strong>。两页展示同一批绑定，不重复计数。</p>
      <p>{{ summary.countMeaningLabel }}{{ summary.restrictionLabel }}</p>
    </template>
    <p>只读查看测试用途路线引用；工艺假设不代表日常方案已确认。历史正式承接与测试绑定是不同口径，不能相加解释为正式制造资格。</p>
    <p>补拟必经：本测试方案要求经过，依据为补拟假设。本单不执行：未满足已声明的执行条件。待核定：尚无足够依据决定是否执行。必经但无定量数据仍要经过，不等于不执行，也不表示数量为零。</p>
    <p>订单工程实例是订单行对应的工程对象；物料清单记录材料与结构需求；路线版本固定整条工序顺序，路线步骤引用工序主数据。制造构成、包装、安装及工艺耗材属于不同需求类型，不能用工程作业量替代材料耗用。测试业务只供验证，不取得正式制造资格。</p>
    <p>下方普通列表保留既有通用及正式路线定义；本区域旧绑定均作为历史保留。当前订单执行选择请查看上方独立安排；标准结构补正只在企业基础资料办理。各历史版本数量仍从其真实步骤读取。</p>
    <p v-if="loading" role="status">正在独立读取测试路线绑定…</p>
    <p v-else-if="error" role="alert">测试绑定读取失败：{{ error }}。本部分事实及数量未取得，不代表没有绑定。</p>
    <p v-else-if="loaded && !bindings.length">已成功读取，尚未保存测试工程路线引用。</p>
    <p v-if="partialFailure" role="alert">部分测试绑定校验失败；不能将局部读取成功视为整页通过。</p>
    <article v-for="binding in bindings" :key="binding.id">
      <h3>物料清单（BOM）版本记录编号 {{ binding.bomVersionId }} · {{ binding.purposeLabel }}</h3>
      <p>{{ binding.statusLabel }}</p>
      <p v-if="binding.historicalPlan" role="note"><strong>历史方案，仅保留沿革：</strong>{{ binding.legacyContractLabel }}。其原执行判断只证明当时保存内容，不代表当前订单不执行；当前判断见上方独立订单安排，历史未被覆盖。</p>
      <p v-else>当前补正方案；路线用途：{{ binding.routeVersionPurposeLabel }}。<template v-if="binding.originRoutingVersionId">承接原路线版本记录编号 {{ binding.originRoutingVersionId }}，原发布版本保持。</template></p>
      <dl v-if="binding.displayIdentity" class="binding-identity">
        <dt>所属订单</dt><dd>{{ binding.displayIdentity.orderNo }}</dd>
        <dt>物料清单版本</dt><dd>{{ binding.displayIdentity.bomVersionName }}（版本记录编号 {{ binding.displayIdentity.bomVersionId }}，原版本标识保留）</dd>
        <dt>路线编码及名称</dt><dd>{{ binding.displayIdentity.routingCode }} · {{ binding.displayIdentity.routingName }}</dd>
        <dt>固定路线版本名称</dt><dd>{{ binding.displayIdentity.routingVersionName }}（{{ binding.versionNameExplanation }}）</dd>
        <dt>固定路线修订</dt><dd>{{ binding.displayIdentity.routingVersionRevision }}</dd>
        <dt>固定路线版本记录编号</dt><dd><strong>{{ binding.displayIdentity.routingVersionRecordId }}</strong></dd>
      </dl>
      <details v-if="binding.steps">
      <summary>查看完整 {{ binding.stepsCount }} 步工序顺序、条件及工作中心（含必经依据／补拟／待核定说明）</summary>
      <ol>
        <li v-for="step in binding.steps" :key="step.stepId">
          <strong>{{ step.stage }} · {{ step.sequence }} {{ step.operationName }}</strong>
          <p>{{ step.decisionLabel }}；{{ step.evidenceLabel }}：{{ step.basis }}</p>
          <p>{{ step.quantityLabel }}；本页不生成工程作业量或涂料耗用。</p>
          <p>工作中心：{{ step.workCenterName }}（{{ step.resourceBasis }}）；前序：{{ step.predecessors.join('、') || '起点' }}</p>
        </li>
      </ol>
      </details>
    </article>
  </section>
</template>
<script setup>
import {ref,onBeforeUnmount} from 'vue'
import {pdeApi} from '@/api/pde'
import {readPceFactLoadEnvelope} from '@/meta/runtime/pceFactLoadContract'
defineProps({formalHandoffCount:{type:Number,default:null}})
const emit=defineEmits(['facts','state'])
const bindings=ref([]),loading=ref(false),loaded=ref(false),error=ref(''),partialFailure=ref(false)
const summary=ref(null)
let generation=0
async function load(){
  const current=++generation
  loading.value=true;loaded.value=false;error.value='';bindings.value=[];summary.value=null;partialFailure.value=false
  emit('facts',null);emit('state','loading')
  try{
    const response=await pdeApi.testEngineeringRoutingBindings()
    const {data}=readPceFactLoadEnvelope(response,'/api/pde/routings/test-engineering-binding/','pde-routings')
    if(current!==generation)return
    if(!Array.isArray(data.testEngineeringRouting))throw new Error('绑定接口未返回有效事实')
    bindings.value=data.testEngineeringRouting
    summary.value=data.testEngineeringRoutingSummary
    partialFailure.value=bindings.value.some(row=>row.factLoadStatus==='read_failed')
    loaded.value=true;emit('facts',data);emit('state',partialFailure.value?'read_failed':'loaded')
  }catch(failure){
    if(current!==generation)return
    error.value=failure?.factLoadFacts?.errorMessage||failure?.response?.data?.errorMessage||failure?.message||'服务端读取未完成'
    emit('state','read_failed')
  }finally{if(current===generation)loading.value=false}
}
defineExpose({load})
onBeforeUnmount(()=>{generation+=1})
</script>
<style scoped>
.binding-identity{display:grid;grid-template-columns:minmax(10em,auto) 1fr;gap:8px 16px;padding:14px;border:1px solid #dce4ed;border-radius:8px}
.binding-identity dt{font-weight:600}.binding-identity dd{margin:0;overflow-wrap:anywhere}
</style>
