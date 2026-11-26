<template>
  <main class="purchase-approval-page" data-page-code="purchase-approval" data-page-name="采购审批"
    data-module-code="SCM" data-business-object="PurchaseRequestApproval">
    <header><div><p>SCM · 采购申请</p><h1>{{ businessName.pageTitle }}</h1>
      <span>本页执行审批实例与审批任务；审批规则请在系统配置页面维护。</span></div>
      <router-link to="/admin/approval-flow-config">查看审批规则配置</router-link></header>
    <section class="panel" data-acceptance-region="approval-runtime-binding">
      <h2>当前审批策略</h2>
      <div class="facts"><span>业务对象<strong>{{ policy.contract.businessObject }}</strong></span>
        <span>审批关卡<strong>{{ policy.gateCount }} 关</strong></span>
        <span>策略编号<strong>{{ policy.policyCode }}</strong></span>
        <span>下一节点<strong>询价准备</strong></span></div>
      <el-table :data="policy.gates" border empty-text="暂无审批关卡">
        <el-table-column prop="level" label="关卡" width="90" />
        <el-table-column prop="name" label="审批任务" />
        <el-table-column prop="approverRole" label="审批角色" />
        <el-table-column prop="passState" label="通过后状态" />
      </el-table>
    </section>
    <section class="panel" data-acceptance-region="approval-instance-execution"><h2>审批实例执行</h2>
      <el-empty v-if="!binding" description="请从已提交采购申请进入审批；配置页不执行审批任务。" />
      <template v-else><div class="facts"><span>采购申请<strong>{{ binding.instance.businessObjectId }}</strong></span>
        <span>当前关卡<strong>{{ binding.instance.currentGate }} / {{ binding.policy.gateCount }}</strong></span>
        <span>审批状态<strong>{{ statusLabel }}</strong></span><span>当前任务<strong>{{ currentTask?.approverRole||'已完成' }}</strong></span></div>
        <el-button type="primary" data-process-action="APPROVE_CURRENT_TASK" :disabled="Boolean(binding.result)" @click="approveCurrentTask">审批通过</el-button>
      </template></section>
  </main>
</template>
<script setup>
import { resolveBusinessName } from '@/meta/governance/businessNameRegistry.js'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { purchaseRequestApi } from '@/api/purchaseRequest.js'
import { createApprovalPolicy, ensureBoundApprovalRuntime, executeBoundApprovalTask,
  saveBoundApprovalRuntime, writeBoundApprovalResult } from '@/meta/workflow/approvalRuntimeBinding.js'
const businessName=resolveBusinessName('purchase-approval')
const policy=createApprovalPolicy('purchaseRequest')
const route=useRoute()
const businessObjectId=String(route.query.businessObjectId||'')
const binding=ref(businessObjectId?ensureBoundApprovalRuntime({moduleName:'purchaseRequest',businessObjectId,
  submittedBy:String(route.query.submittedBy||'purchase-request-page')}):null)
const currentTask=computed(()=>binding.value?.tasks.find(task=>task.status==='pending')||null)
const statusLabel=computed(()=>binding.value?.result?'审批已完成':binding.value?.instance.status==='in_progress'?'审批进行中':'待审批')
async function approveCurrentTask(){
  const next=executeBoundApprovalTask(binding.value,{actorId:'current-user',actorRole:currentTask.value?.approverRole||''})
  if(next.result&&route.query.objectId){const response=await purchaseRequestApi.approve(route.query.objectId);if(!response?.success)return ElMessage.error(response?.error?.message||'业务状态回写失败')}
  binding.value=next.result?writeBoundApprovalResult(next,{requestNo:businessObjectId,approvalStatus:'submitted',businessLifecycleState:'submitted'}):next
  saveBoundApprovalRuntime(binding.value);ElMessage.success(next.result?'审批完成，业务状态已回写':'当前关卡已通过，进入下一关')
}
</script>
<style scoped>.purchase-approval-page{display:grid;gap:18px;padding:20px}.purchase-approval-page header{display:flex;align-items:center;justify-content:space-between;gap:16px}.purchase-approval-page h1{margin:4px 0}.purchase-approval-page p,.purchase-approval-page span{color:#64748b}.panel{padding:18px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.facts{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px}.facts span{display:grid;gap:6px}.facts strong{color:#172033}@media(max-width:800px){.purchase-approval-page header{align-items:flex-start;flex-direction:column}.facts{grid-template-columns:1fr}}</style>
