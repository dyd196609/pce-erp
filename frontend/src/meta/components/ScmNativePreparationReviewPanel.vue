<template>
  <section v-if="recordId || pending || context" class="native-review" data-native-preparation-review>
    <h3>准确版本的核价准备审核</h3>
    <p>读取资格与审核资格分别核实。通过仅为本准备准确版本的核价结论，不代表价格已确认、采购订单已批准或可以付款。</p>
    <el-button v-if="recordId" :loading="busy" @click="readCurrent">读取当前审核依据</el-button>
    <p v-if="busy" role="status">正在核实原服务结果；不会自动重复提交。</p>
    <el-alert v-if="readError" :title="readError.message" type="error" :closable="false" />
    <el-alert v-if="actionError" :title="actionError.message" type="error" :closable="false" />
    <section v-if="context" data-native-review-context>
      <p>{{ context.approvalPrepareNo }}；比较版本 {{ context.sourceComparisonVersion }}；{{ shown(context.statusLabel) }}。</p>
      <p>当前结论：{{ shown(context.currentResultLabel) }}；决定版本 {{ context.decisionVersion }}；工作流版本 {{ context.workflowVersion }}。</p>
      <p>当前结论与历史决定分开显示；重新核价期间原决定保留，不作为当前结论。</p>
      <p v-for="item in context.blockedReasons" :key="item.code" role="alert">{{ item.message }}</p>
      <p v-if="!context.availableActions.length">服务端未提供当前可办审核动作；仅可查看原依据。</p>
      <template v-if="actions.length">
        <label>本次办理理由<el-input v-model="reason" aria-label="本次办理理由" maxlength="240" :disabled="Boolean(pending)" /></label>
        <template v-if="context.availableActions.includes('SUBMIT_REVIEW')">
          <label>本次核价结论<select v-model="result" aria-label="本次核价结论" :disabled="Boolean(pending)"><option value="">请选择结论</option><option v-for="item in PREPARATION_REVIEW_RESULTS" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
          <label>审核意见<el-input v-model="opinion" aria-label="审核意见" type="textarea" maxlength="1000" :disabled="Boolean(pending)" /></label>
          <label v-if="result==='pass'">核价意见对象（人工明确原候选）<select v-model="supplier" aria-label="核价意见对象" :disabled="Boolean(pending)"><option value="">请选择原候选，不自动选供</option><option v-for="item in candidates" :key="item.supplierCode" :value="item.supplierCode">{{ shown(item.supplierName || item.supplierCode) }}</option></select></label>
        </template>
        <el-button v-for="action in actions" :key="action.actionCode" :data-process-action="action.actionCode" type="primary" :loading="busy"
          :disabled="Boolean(pending)||!reason.trim()||(action.actionCode==='SUBMIT_REVIEW'&&(!result||!opinion.trim()||(result==='pass'&&!supplier)))"
          @click="execute(action.actionCode,{reason,reviewResult:result,opinion,selectedSupplierCode:supplier})">{{ action.actionName }}</el-button>
      </template>
      <h4>原服务审核历史</h4>
      <p v-if="!context.history.length">服务端尚无本版本审核历史。</p>
      <article v-for="item in context.history" :key="item.auditId" data-native-review-history>
        <p>{{ PREPARATION_REVIEW_ACTIONS[item.action]?.actionName || '未知动作（未识别）' }} · {{ shown(item.resultLabel) }} · 比较版本 {{ item.comparisonVersion }} · 决定版本 {{ item.decisionVersion }}</p>
        <p>办理人记录 {{ shown(item.actorId) }}；时间 {{ shown(item.occurredAt) }}；理由 {{ shown(item.reason) }}；意见 {{ shown(item.opinion) }}。</p>
      </article>
      <details><summary>审核来源、版本与完整历史追溯</summary><pre>{{ JSON.stringify(context,null,2) }}</pre></details>
    </section>
    <section v-if="pending" data-native-review-result role="status">
      <h4>{{ receipt?.resultState==='COMMITTED'?'原审核动作已提交':'原审核动作结果尚未确认' }}</h4>
      <p>保留原动作标识，只查询同一次动作；不自动重放。回执为当时结果，不授予当前办理资格。</p>
      <el-button :loading="busy" @click="queryOriginal">查询原审核动作结果</el-button>
      <template v-if="receipt?.resultState==='COMMITTED'">
        <p>{{ receipt.approvalPrepareNo }} · 比较版本 {{ receipt.sourceComparisonVersion }} · 当时状态 {{ shown(receipt.statusLabel) }} · 当时结论 {{ shown(receipt.reviewResultLabel) }} · 回执时间 {{ shown(receipt.receiptAsOf) }}。</p>
        <el-button @click="acknowledge">已查看回执，读取当前审核依据</el-button>
      </template>
      <details><summary>原审核动作与历史回执</summary><pre>{{ JSON.stringify({pending,receipt},null,2) }}</pre></details>
    </section>
    <details v-if="readError||actionError||rejected"><summary>审核读取与动作诊断</summary><pre>{{ JSON.stringify({readError,actionError,rejected},null,2) }}</pre></details>
  </section>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { createNativePreparationReview } from '../runtime/nativePreparationReview.js'
import { PREPARATION_REVIEW_ACTIONS, PREPARATION_REVIEW_RESULTS } from '../process/scm/nativePreparationReviewActions.js'
const props=defineProps({preparation:{type:Object,default:()=>({})}}),emit=defineEmits(['current-facts'])
const recordId=computed(()=>props.preparation.preparationId ?? props.preparation.id)
const candidates=computed(()=>props.preparation.supplierCandidates || [])
const {context,readError,busy,actionError,pending,receipt,rejected,load,execute,queryOriginal,acknowledgeCommitted}=createNativePreparationReview()
const reason=ref(''),result=ref(''),opinion=ref(''),supplier=ref('')
const shown=v=>v===null||v===undefined||v===''?'未提供':String(v)
const actions=computed(()=>Object.values(PREPARATION_REVIEW_ACTIONS).filter(action=>action.allowed(context.value)))
async function readCurrent(){if(!recordId.value)return;await load(recordId.value);if(context.value)emit('current-facts',context.value)}
async function acknowledge(){await acknowledgeCommitted();if(context.value)emit('current-facts',context.value)}
watch(recordId,()=>{reason.value='';result.value='';opinion.value='';supplier.value='';context.value=null;void readCurrent()})
onMounted(()=>void readCurrent())
</script>
<style scoped>
.native-review{display:grid;gap:12px;min-width:0}.native-review p{line-height:1.65;overflow-wrap:anywhere}.native-review label{display:grid;gap:8px}.native-review select{min-height:44px;width:100%;max-width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:5px;background:white}.native-review pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.native-review article{border-bottom:1px solid #dbe4ee}.native-review :deep(.el-button){white-space:normal;height:auto;min-height:44px;line-height:1.5;max-width:100%}
</style>
