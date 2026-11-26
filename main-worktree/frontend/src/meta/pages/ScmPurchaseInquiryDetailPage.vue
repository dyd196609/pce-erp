<template>
  <main class="inquiry-page" data-page-code="purchase-inquiry-detail" data-business-object="PurchaseInquiry" data-runtime-version="V1.14.2.8.18.7">
    <header class="page-heading">
      <div><h1>{{ pageName.pageTitle }}</h1><p>PurchaseInquiry Detail · {{ inquiry?.inquiryNo || inquiryNo }}</p></div>
      <el-button @click="router.push('/scm/purchase-inquiry')">返回询价工作台</el-button>
    </header>
    <el-alert v-if="!inquiry" title="未找到询价运行上下文" type="error" :closable="false" show-icon />
    <template v-else>
      <section class="panel" data-acceptance-id="purchase-inquiry-detail-context">
        <h2>询价基本信息</h2>
        <el-descriptions :column="3" border>
          <el-descriptions-item label="询价编号">{{ inquiry.inquiryNo }}</el-descriptions-item>
          <el-descriptions-item label="来源采购申请">{{ inquiry.sourceRequestNo || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ inquiry.statusLabel || inquiry.statusCode }}</el-descriptions-item>
        </el-descriptions>
      </section>
      <section class="panel" data-acceptance-id="purchase-inquiry-next-actions">
        <h2>下一流程动作</h2>
        <p><strong>当前状态：</strong>{{ inquiry.runtimeState }}</p>
        <p>草稿允许：保存询价、准备供应商报价</p>
        <div class="actions">
          <el-button type="primary" data-process-action="EDIT_PURCHASE_INQUIRY" @click="runNext('EDIT_PURCHASE_INQUIRY')">编辑询价</el-button>
          <el-button data-process-action="PREPARE_SUPPLIER_QUOTE" @click="runNext('PREPARE_SUPPLIER_QUOTE')">准备供应商报价</el-button>
        </div>
        <p>本节点不发送供应商，不创建采购订单。</p>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { executePurchaseInquiryAction, loadPurchaseInquiryActionExecutionContext } from '@/meta/runtime/purchaseInquiryActionExecutionRuntime.js'
import { resolvePageNameConsumption } from '@/meta/governance/pageNameConsumer.js'

const route = useRoute()
const router = useRouter()
const pageName = resolvePageNameConsumption({ pageCode: 'purchase-inquiry-detail', route: route.path })
const inquiryNo = computed(() => String(route.params.inquiryNo || ''))
const context = computed(() => loadPurchaseInquiryActionExecutionContext(inquiryNo.value))
const inquiry = computed(() => context.value?.inquiry || null)
function runNext(actionCode) {
  const result = executePurchaseInquiryAction({ inquiry: inquiry.value, actionCode })
  if (!result.allowed) { ElMessage.error('当前询价不允许执行该动作'); return }
  router.push(result.route)
}
</script>

<style scoped>
.inquiry-page{display:grid;gap:16px;max-width:1200px;margin:0 auto}.page-heading{display:flex;align-items:center;justify-content:space-between}.page-heading h1,.panel h2{margin:0}.page-heading p,.panel p{color:#64748b}.panel{padding:20px;border:1px solid #dce4ed;border-radius:10px;background:#fff}.actions{display:flex;gap:12px;margin-top:16px}
</style>
