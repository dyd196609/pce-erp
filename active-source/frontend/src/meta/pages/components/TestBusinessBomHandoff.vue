<template>
  <section class="card" data-acceptance-id="test-business-bom-handoff">
    <h2>测试业务核算 → BOM 草稿</h2>
    <el-alert title="测试业务仅允许草稿保存和来源查看；禁止正式评审、发布及制造。隔离补充映射不代表日常材料方案已获业务确认。" type="warning" :closable="false" />
    <p><el-button :loading="busy" @click="load">刷新测试承接</el-button></p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <p v-if="authenticationRequired"><router-link :to="loginLocation">前往登录</router-link></p>
    <template v-if="loaded">
      <p v-if="!records.length">当前公司没有已保存的测试业务核算。</p>
      <el-select v-if="records.length" v-model="selectedId" @change="selectSource" placeholder="请选择已保存的测试核算" aria-label="选择测试核算" style="width:min(680px,100%)">
        <el-option v-for="r in records" :key="r.id" :value="r.id" :label="`${r.orderNo}／${r.calculationNo}／${r.purposeLabel}`" />
      </el-select>
      <template v-if="current">
        <p>用途：{{ current.purposeLabel }}；{{ current.restrictionLabel }}</p>
        <p>来源 {{ current.sourceId }}／版本 {{ current.sourceVersion }} → 获准 R{{ current.revision }} → 基线 {{ current.baselineNo }} → {{ current.calculationNo }}</p>
        <el-alert v-if="!current.sourceValid" :title="current.error" type="error" :closable="false" />
        <template v-if="current.preview">
          <el-alert v-if="current.preview.firstRealBlocker" :title="current.preview.firstRealBlocker.statusLabel" :description="current.preview.firstRealBlocker.message" type="warning" :closable="false" />
          <p v-if="current.preview.currentVersionMaterialCompleteness?.missingComponentKeys?.length">缺项定位：{{ missingNames.join('、') }}；需明确材料、规格、基本单位、结构角色和用量映射，不从部件名称或工程面积自动推断。</p>
          <article v-for="(row,index) in current.preview.rows" :key="row.lineNo" class="material-detail">
            <h3>材料需求 {{ index+1 }}：{{ row.materialName }}</h3>
            <p>物料编号：{{ row.materialCode }}；结构：{{ componentNames(row) }}；规格：{{ row.orderSpecification.materialSpecification || '未维护' }}</p>
            <p>数量：{{ row.quantity }} {{ row.uomCode }}（订单总工程净量）；损耗：{{ row.scrapRate === null ? '未维护' : row.scrapRate }}</p>
            <p>来源材料需求：{{ row.sourceRequirementIds.join('、') }}；来源核算：{{ current.calculationNo }}；用途：测试业务</p>
          </article>
          <p v-if="!current.canMaintain">当前账号无BOM维护权限；可以查看来源和缺项，不能生成。</p>
          <el-button type="primary" :disabled="busy || !generateAction?.enabled" @click="generate">{{ generateAction?.displayName }}</el-button>
          <p v-if="current.preview.alreadyGenerated">已保存测试草稿；同一核算重复生成不会新增BOM。</p>
        </template>
        <article v-for="v in current.versions" :key="v.id" class="material-detail">
          <p>BOM版本 {{ v.name }}：{{ v.statusLabel }}／{{ v.purposeLabel }}；{{ v.originVersionId ? `派生自版本 ${v.originVersionId}` : '来源核算直接生成' }}</p>
          <el-button :disabled="busy || !copyAction(v)?.enabled" @click="derive(v)">{{ copyAction(v)?.displayName }}</el-button>
        </article>
      </template>
    </template>
    <p v-if="receipt" role="status">{{ receipt }}</p>
  </section>
</template>
<script setup>
import {ref,computed,onMounted} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {pdeApi} from '@/api/pde'
import {testBomFailure} from '@/meta/runtime/testBomFailure'
import {resolvePceBusinessActions} from '@/meta/runtime/pceBusinessActionRegistry'
const emit=defineEmits(['saved','facts'])
const route=useRoute(),router=useRouter(),records=ref([]),selectedId=ref(null),busy=ref(false),loaded=ref(false),error=ref(''),receipt=ref('')
const authenticationRequired=ref(false)
const loginLocation='/login'
function rejectFailure(response,fallback){if(!response.success)throw Object.assign(new Error(testBomFailure(response,fallback).message),{authenticationRequired:testBomFailure(response,fallback).authenticationRequired})}
function showFailure(e,fallback){const failure=e.authenticationRequired ? {message:e.message,authenticationRequired:true} : testBomFailure(e,fallback);error.value=failure.message;authenticationRequired.value=failure.authenticationRequired;if(failure.authenticationRequired){loaded.value=false;records.value=[];selectedId.value=null;receipt.value='';emit('facts',null)}}
const current=computed(()=>records.value.find(r=>r.id===selectedId.value))
function actionFor(id,state){const r=resolvePceBusinessActions({currentModule:'bom-management',currentStatus:state,permissions:current.value?.actionPermissions||[],eligibility:current.value?.preview?.canGenerate});return [...r.availableActions,...r.unavailableActions].find(a=>a.actionId===id)}
const generateAction=computed(()=>actionFor('generate-test-business-bom',current.value?.actionState))
function copyAction(v){return actionFor('derive-test-business-bom',v.actionState)}
const missingNames=computed(()=>current.value?.components.filter(c=>current.value.preview.currentVersionMaterialCompleteness.missingComponentKeys.includes(c.key)).map(c=>c.name)||[])
function selectSource(id){const r=records.value.find(x=>x.id===id);if(r)return router.replace({query:{...route.query,orderId:String(r.salesOrderId),sourceCalculationId:String(r.id)}})}
function componentNames(row){return current.value.components.filter(c=>row.orderSpecification.structureRole?.toLowerCase()===c.key.toLowerCase()).map(c=>c.name).join('、')||'详见来源需求'}
async function load(){busy.value=true;error.value='';try{const response=await pdeApi.testBusinessBomHandoff();rejectFailure(response,'测试承接读取失败，请重试。');authenticationRequired.value=false;emit('facts',response.data);records.value=response.data.records;loaded.value=true;selectedId.value=records.value.find(r=>String(r.id)===String(route.query.sourceCalculationId)&&(!route.query.orderId||String(r.salesOrderId)===String(route.query.orderId)))?.id??null}catch(e){showFailure(e,'测试承接读取失败，请重试。');loaded.value=false;emit('facts',null)}finally{busy.value=false}}
async function generate(){busy.value=true;error.value='';try{const r=await pdeApi.generateOrderBom(current.value.id,{previewHash:current.value.preview.previewHash,reason:'隔离页面：生成测试业务BOM草稿，不发布不制造'});rejectFailure(r,'测试BOM生成失败，请重试。');receipt.value='测试BOM草稿已保存。';await load();emit('saved')}catch(e){showFailure(e,'测试BOM保存失败，请重试。')}finally{busy.value=false}}
async function derive(v){busy.value=true;error.value='';try{const r=await pdeApi.deriveTestBom({versionId:v.id,key:`copy-${v.id}-${Date.now()}`,reason:'隔离页面：复制测试草稿，保留测试用途及来源沿革'});rejectFailure(r,'测试BOM复制失败，请重试。');receipt.value='测试派生版本已保存。';await load();emit('saved')}catch(e){showFailure(e,'测试BOM复制失败，请重试。')}finally{busy.value=false}}
defineExpose({load})
onMounted(load)
</script>
<style scoped>.material-detail{border:1px solid #dcdfe6;border-radius:6px;margin:12px 0;padding:12px}.material-detail h3{margin:0 0 8px}.material-detail p{margin:6px 0}</style>
