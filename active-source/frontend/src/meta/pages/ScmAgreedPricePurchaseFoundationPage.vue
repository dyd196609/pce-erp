<template>
  <main class="agreed-request" data-page-code="agreed-price-purchase-foundation" data-purchase-mode="AGREED_PRICE"
    data-business-object="PurchaseRequest" data-material-source="MaterialMaster">
    <header class="page-heading"><div><h1>新建既定价格采购申请</h1>
      <p>先创建正式 PurchaseRequest（采购申请）。审批后使用现有有效供应商物料价格进入既定价格确认，不再进行询价、比价和核价。</p></div>
      <el-button @click="router.push('/scm/purchase-request')">返回采购申请</el-button></header>
    <el-alert title="采购申请明细只从 MaterialMaster（物料档案）选择；本阶段不绑定 SupplierMaterialPrice，也不生成采购订单。"
      type="info" :closable="false" show-icon />
    <section class="form-entry" data-acceptance-id="agreed-price-purchase-request-form">
      <h2>采购申请头与物料明细</h2>
      <p>填写申请人、申请部门、采购部门、使用部门、项目、成本中心、申请原因和交付要求，并维护多条物料、数量与需求日期。</p>
      <el-button type="primary" data-process-action="OPEN_AGREED_PRICE_PURCHASE_REQUEST_FORM" @click="openForm">填写既定价格采购申请</el-button>
    </section>
    <ScmPurchaseRequestOriginalBusinessRegion ref="businessRegionRef" create-title="新建既定价格采购申请"
      @refreshed="handleSaved" @authentication-required="handleAuthenticationRequired"
      @procurement-mode-routed="handleModeRouted" />
  </main>
</template>

<script setup>
import { nextTick,onMounted,provide,ref } from 'vue'
import { useRoute,useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import ScmPurchaseRequestOriginalBusinessRegion from '@/meta/components/ScmPurchaseRequestOriginalBusinessRegion.vue'
import { initPurchaseRequestProviders,purchaseRequestProviders,PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY } from '@/meta/scm/purchaseRequestProviderRuntimeRegistry.js'

const router=useRouter(),route=useRoute(),businessRegionRef=ref(null)
provide(PURCHASE_REQUEST_PROVIDER_RUNTIME_KEY,purchaseRequestProviders)
async function openForm(){await businessRegionRef.value?.openCreate('AGREED_PRICE')}
function handleSaved(saved){if(saved?.purchaseMode==='AGREED_PRICE')ElMessage.success(`${saved.requestNo} 已进入既定价格采购申请链路。`)}
function handleModeRouted(saved){if(saved?.purchaseMode==='AGREED_PRICE')router.push({path:'/scm/purchase-request',query:{created:saved.requestNo,purchaseMode:'AGREED_PRICE'}})}
function handleAuthenticationRequired(){router.push({path:'/login',query:{redirect:route.fullPath}})}
onMounted(async()=>{await initPurchaseRequestProviders();await nextTick();await openForm()})
</script>

<style scoped>
.agreed-request{display:grid;gap:18px;padding:20px}.page-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.page-heading h1,.form-entry h2{margin:0 0 8px}.page-heading p,.form-entry p{margin:0;color:#64748b}.form-entry{padding:20px;border:1px solid #dbe4ee;border-radius:12px;background:#fff}.form-entry p{margin-bottom:16px}
</style>
