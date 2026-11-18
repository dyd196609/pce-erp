<template>
  <section data-standard-route-owner="enterprise-foundation">
    <h3>标准路线结构与版本维护</h3>
    <p>本模块是标准路线新建、工序结构／顺序编辑及版本增加的唯一维护归属。订单是否执行某道已有工序，请到订单工序执行安排办理，不在这里生成版本。</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <el-button :loading="busy" @click="load">刷新标准版本</el-button>
    <el-select v-model="versionId" @change="choose" placeholder="选择准确标准版本" style="width:30em"><el-option v-for="v in versions" :key="v.id" :value="v.id" :label="`${v.name}（修订${v.revision}，记录${v.id}，${v.statusLabel}，${v.usageLabel}）`" /></el-select>
    <template v-if="!versions.length && canMaintain"><el-input v-model="reason" placeholder="首版标准草稿依据" /><el-button :disabled="!reason.trim() || busy" @click="initialVersion">通过正常服务建立首个标准草稿版本</el-button></template>
    <template v-if="selected">
      <p>标准路线版本记录{{ selected.id }}，前驱记录{{ selected.originVersionId || '首版' }}；{{ selected.editDisabledReason || '当前草稿可正常维护' }}。不编辑已发布版本或历史引用。</p>
      <label>后继版本用途依据
        <el-select v-model="testBom" clearable placeholder="通用后继；测试用途须选可信物料清单来源" style="width:35em"><el-option v-for="bom in boms" :key="bom.id" :value="bom.id" :label="`测试物料清单${bom.bom_version}（记录${bom.id}）`" /></el-select>
      </label>
      <el-input v-model="reason" type="textarea" placeholder="本次标准结构维护或新增版本依据，订单执行选择不属于结构变更" />
      <el-button v-if="canMaintain" :disabled="!selected.canCreateSuccessor || busy || !reason.trim()" :title="selected.successorDisabledReason" @click="successor">通过正常服务新增标准路线后继版本</el-button>
      <template v-if="selected.canEdit && canMaintain">
        <p>上移／下移改变标准顺序；前序按步骤身份保留，移位后须核对交接依赖，不自动抹去条件分支。</p>
        <ol>
          <li v-for="(row,index) in rows" :key="row.key">
            {{ index+1 }}．<el-select v-model="row.operationId" style="width:19em"><el-option v-for="op in operations" :key="op.id" :value="op.id" :label="`${op.name}（${op.code}）`" /></el-select>
            <el-button :disabled="index===0" @click="move(index,-1)">上移</el-button><el-button :disabled="index===rows.length-1" @click="move(index,1)">下移</el-button>
            <el-button @click="rows.splice(index,1)">从本草稿结构移除</el-button>
            <label>前序工序<el-select v-model="row.predecessorKeys" multiple style="width:30em"><el-option v-for="parent in rows.slice(0,index)" :key="parent.key" :value="parent.key" :label="`${rows.indexOf(parent)+1}．${operations.find(op=>op.id===parent.operationId)?.name || '工序'}`" /></el-select></label>
          </li>
        </ol>
        <el-button @click="rows.push({key:cryptoKey(),id:null,operationId:null,predecessorKeys:rows.length?[rows[rows.length-1].key]:[]})">添加既有工序主数据引用</el-button>
        <el-button :disabled="busy || !reason.trim() || rows.some(r=>!r.operationId)" @click="save">保存本标准草稿结构／顺序</el-button>
      </template>
      <ol v-else><li v-for="step in selected.steps" :key="step.id">{{ step.sequence }}．{{ step.operationName }}；前序{{ step.predecessors.join('、') || '起点' }}</li></ol>
    </template>
  </section>
</template>
<script setup>
import {ref,computed,watch,onBeforeUnmount} from 'vue'
import {pdeApi} from '@/api/pde'
import {resolveCurrentIdentity} from '@/meta/runtime/pageTitleManager'
import {assertFoundationRequestIdentity} from '@/meta/runtime/foundationRoutingRead'
const props=defineProps({routingId:{type:Number,required:true},canMaintain:{type:Boolean,default:false}})
const versions=ref([]),versionId=ref(null),rows=ref([]),operations=ref([]),boms=ref([]),reason=ref(''),testBom=ref(null),error=ref(''),busy=ref(false)
const selected=computed(()=>versions.value.find(v=>v.id===versionId.value))
const u=r=>r?.data??r,cryptoKey=()=>crypto.randomUUID()
function choose(){const v=selected.value;if(!v)return;const keys=Object.fromEntries(v.steps.map(s=>[s.sequence,String(s.id)]));rows.value=v.steps.map(s=>({key:String(s.id),id:s.id,operationId:s.operationId,workCenterId:s.workCenterId,predecessorKeys:s.predecessors.map(n=>keys[n])}))}
let generation=0
async function load(){const current=++generation;busy.value=true;error.value='';versions.value=[];rows.value=[];operations.value=[];boms.value=[];try{
  const data=u(await pdeApi.foundationRoutingVersions(props.routingId));if(current!==generation)return;assertFoundationRequestIdentity(resolveCurrentIdentity(),data.requestIdentity)
  versions.value=data.versions;operations.value=data.operations;boms.value=data.testBomVersions
  if(!versions.value.some(v=>v.id===versionId.value))versionId.value=versions.value[0]?.id;choose()
}catch(e){if(current===generation)error.value=e?.response?.data?.message||e.message||'标准路线未读取完成'}finally{if(current===generation)busy.value=false}}
async function successor(){busy.value=true;error.value='';try{const result=u(await pdeApi.foundationRoutingAction(selected.value.id,'successor',{reason:reason.value,idempotencyKey:cryptoKey(),...(testBom.value?{testBomVersionId:testBom.value}:{})}));versionId.value=result.result.routingVersionId;reason.value='';await load()}catch(e){error.value=e?.response?.data?.message||e.message}finally{busy.value=false}}
async function save(){busy.value=true;error.value='';try{await pdeApi.foundationRoutingAction(selected.value.id,'save-structure',{rows:rows.value,expectedHash:selected.value.editHash,reason:reason.value,idempotencyKey:cryptoKey()});reason.value='';await load()}catch(e){error.value=e?.response?.data?.message||e.message}finally{busy.value=false}}
async function initialVersion(){busy.value=true;error.value='';try{await pdeApi.foundationRoutingInitial(props.routingId,{reason:reason.value,idempotencyKey:cryptoKey()});reason.value='';await load()}catch(e){error.value=e?.response?.data?.message||e.message}finally{busy.value=false}}
watch(()=>props.routingId,()=>{versionId.value=null;load()},{immediate:true})
onBeforeUnmount(()=>generation++)
</script>
<style scoped>li{padding:12px;border-bottom:1px solid #dce4ed}label{display:flex;gap:8px;align-items:center;margin:8px 0}</style>
