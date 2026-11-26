<template>
  <section aria-label="已保存测试核算">
    <h3>已保存测试核算</h3>
    <p>与上方只读预览分开。保存时服务端重新校验并计算；保存的测试记录不得用于生产、BOM或制造。</p>
    <el-button :disabled="busy" @click="load">读取已保存测试核算</el-button>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loaded && !records.length">所选基线尚无已保存测试核算。</p>
    <article v-for="record in records" :key="record.id">
      <h4>{{ record.calculationNo }} · {{ record.statusLabel }}</h4>
      <p>{{ record.baselineNo }} ／ R{{ record.designRevision }} · 测试业务用途，不用于生产</p>
      <p>保存人：{{ record.savedBy.name }}；保存时间：{{ record.savedAt }}；{{ record.validityLabel }}</p>
      <p>{{ record.validityReason }}</p><p>保存原因：{{ record.reason }}</p>
      <p>规则版本：{{ record.ruleSnapshot.adapterVersion }}</p>
      <p>冻结汇总：{{ record.snapshot.summary.quantity }}块；工程净面积{{ record.snapshot.summary.S }}m²；见光面积{{ record.snapshot.summary.Q }}m²；封边净长{{ record.snapshot.summary.R }}m</p>
      <details><summary>查看已保存12项结果及规则依据</summary><table><thead><tr><th>部件</th><th>结果</th><th>数值</th><th>单位</th><th>表达式</th></tr></thead><tbody><tr v-for="row in record.snapshot.rows" :key="row.id"><td>{{ row.componentName }}</td><td>{{ row.project }}</td><td>{{ row.value }}</td><td>{{ row.unit }}</td><td>{{ row.expression }}</td></tr></tbody></table></details>
    </article>
    <template v-if="canSave">
      <el-input v-model="reason" placeholder="本次测试核算保存原因（必填，240字以内）" :maxlength="240" />
      <el-button :disabled="busy || !reason.trim()" @click="save">受控保存测试核算</el-button>
      <p>此动作使用核算执行权限并新增测试记录；已有验收记录无需重复保存。</p>
    </template>
  </section>
</template>
<script setup>
import {ref,watch,onMounted} from 'vue'
import {pdeApi} from '@/api/pde.js'
const props=defineProps({baselineId:[Number,String]})
const busy=ref(false),error=ref(''),records=ref([]),canSave=ref(false),loaded=ref(false),reason=ref('')
let sequence=0,key='',requestBody=''
const unpack=r=>r?.data??r
watch(()=>props.baselineId,()=>{sequence++;records.value=[];error.value='';canSave.value=false;loaded.value=false;reason.value='';key='';requestBody='';load()})
async function load(){const seq=++sequence,id=props.baselineId;busy.value=true;error.value='';try{const r=unpack(await pdeApi.testCalculationRecords({baselineId:id}));if(seq===sequence){records.value=r.records;canSave.value=r.canSave;loaded.value=true}}catch(e){if(seq===sequence)error.value=e?.response?.data?.message||e.message}finally{if(seq===sequence)busy.value=false}}
async function save(){const seq=sequence,id=props.baselineId;busy.value=true;error.value='';try{
  const context=unpack(await pdeApi.testCalculationPreview({mode:'context',baselineId:id})).context
  if(seq!==sequence)return
  const body={context,reason:reason.value.trim()},serialized=JSON.stringify(body)
  if(serialized!==requestBody){key=crypto.randomUUID();requestBody=serialized}
  await pdeApi.saveTestCalculation(body,key)
  if(seq===sequence){reason.value='';await load()}
}catch(e){if(seq===sequence)error.value=e?.response?.data?.message||e.message}finally{if(seq===sequence)busy.value=false}}
onMounted(load)
</script>
