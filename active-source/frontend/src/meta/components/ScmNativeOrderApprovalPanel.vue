<template>
  <section class="native-order-approval" data-native-order-approval>
    <h3>采购订单提交、审核、复核与下达</h3>
    <p>价格依据有效不代表订单已批准。当前办理资格由原服务逐单核实；制单人与后续办理分离，复核人与下达人分离。</p>
    <el-button :loading="busy" @click="readCurrent">读取当前审批依据</el-button>
    <p v-if="busy" role="status">正在读取或确认原动作，不会自动重复提交。</p>
    <el-alert v-if="readError" type="error" :closable="false" :title="readError.message" />
    <el-alert v-if="actionError" type="error" :closable="false" :title="actionError.message" />
    <template v-if="context">
      <p data-order-approval-current>{{ context.orderNo }} · 当前状态：{{ shown(context.statusLabel) }}；决定版本 {{ context.decisionVersion }}；流程版本 {{ context.workflowVersion }}。</p>
      <p v-for="item in context.blockedReasons" :key="item.code" role="alert">{{ item.message }}</p>
      <p v-if="!actions.length">服务端未提供当前可办动作；可查看当前依据与历史。</p>
      <template v-else>
        <label>本次办理理由<el-input v-model="reason" aria-label="采购订单本次办理理由" maxlength="240" :disabled="Boolean(pending)||busy" /></label>
        <div class="order-actions"><el-button v-for="action in actions" :key="action.actionCode" type="primary"
          :data-order-approval-action="action.actionCode" :loading="busy" :disabled="Boolean(pending)||!reason.trim()"
          @click="execute(action.actionCode,reason)">{{ action.displayName }}</el-button></div>
      </template>
      <h4>当前决定</h4>
      <p v-if="!context.history.length">本版本尚无已登记决定。</p>
      <p v-else>{{ actionName(currentDecision.action) }}；办理人记录 {{ shown(currentDecision.actorId) }}／员工记录 {{ shown(currentDecision.actorEmployeeId) }}；时间 {{ shown(currentDecision.occurredAt) }}；理由 {{ shown(currentDecision.reason) }}。</p>
      <details><summary>原审批历史及来源、价格、流程版本追溯</summary>
        <article v-for="item in context.history" :key="item.auditId" data-order-approval-history>
          <p>{{ actionName(item.action) }} · 决定版本 {{ item.decisionVersion }} · 流程版本 {{ item.workflowVersion }}；办理人记录 {{ shown(item.actorId) }}／员工记录 {{ shown(item.actorEmployeeId) }}；{{ shown(item.occurredAt) }}；{{ shown(item.reason) }}。</p>
        </article><pre>{{ JSON.stringify(context,null,2) }}</pre>
      </details>
    </template>
    <section v-if="pending" role="status" data-order-approval-result>
      <h4>{{ receipt?.resultState==='COMMITTED'?'原动作已登记':'原动作结果尚未确认' }}</h4>
      <p>回执仅为当时结果，不代表当前仍可办理。保留原动作标识，只查询同一次动作，不自动重放。</p>
      <p>原订单记录 {{ pending.orderId }}；{{ actionName(pending.action) }}。</p>
      <el-button :loading="busy" @click="queryOriginal">查询原订单动作结果</el-button>
      <template v-if="receipt?.resultState==='COMMITTED'">
        <p>{{ shown(receipt.objectNo) }}；当时状态 {{ shown(receipt.statusLabel) }}；决定版本 {{ receipt.decisionVersion }}；流程版本 {{ receipt.workflowVersion }}；回执时间 {{ shown(receipt.receiptAsOf) }}。</p>
        <el-button @click="acknowledge">已查看回执，重新读取当前依据</el-button>
      </template>
      <details><summary>原动作标识与回执</summary><pre>{{ JSON.stringify({pending,receipt},null,2) }}</pre></details>
    </section>
    <details v-if="readError||actionError"><summary>读取及动作诊断</summary><pre>{{ JSON.stringify({readError,actionError},null,2) }}</pre></details>
  </section>
</template>
<script setup>
import { computed, ref, watch } from 'vue'
import { createNativeOrderApproval, ORDER_APPROVAL_ROUTES } from '../runtime/nativeOrderApproval.js'
const props=defineProps({orderId:{type:[String,Number],required:true}}), emit=defineEmits(['changed'])
const {context,readError,busy,actionError,pending,receipt,load,execute,queryOriginal,acknowledgeCommitted}=createNativeOrderApproval()
const reason=ref(''),shown=v=>v===null||v===undefined||v===''?'未提供':String(v)
const actions=computed(()=>context.value?.actionContracts.filter(a=>ORDER_APPROVAL_ROUTES[a.actionCode]&&context.value.availableActions.includes(a.actionCode))||[])
const currentDecision=computed(()=>context.value?.history.at(-1))
const actionName=code=>context.value?.actionContracts.find(a=>a.actionCode===code)?.displayName||({'procurement.purchase_order.submit':'提交采购订单','procurement.purchase_order.approve':'审核采购订单','procurement.purchase_order.review':'复核采购订单','procurement.purchase_order.release':'下达采购订单'})[code]||'未知动作（未识别）'
async function readCurrent(){await load(props.orderId)}
async function acknowledge(){await acknowledgeCommitted(props.orderId);if(context.value)emit('changed')}
watch(()=>props.orderId,()=>{reason.value='';void readCurrent()},{immediate:true})
</script>
<style scoped>
.native-order-approval{display:grid;gap:12px;min-width:0;margin:16px 0}.native-order-approval p{margin:0;line-height:1.65;overflow-wrap:anywhere}.native-order-approval label{display:grid;gap:8px}.order-actions{display:flex;gap:10px;flex-wrap:wrap}.native-order-approval pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.native-order-approval :deep(.el-button){white-space:normal;height:auto;min-height:44px;line-height:1.5;max-width:100%;margin-left:0}
</style>
