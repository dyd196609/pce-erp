<template>
  <section class="crm-process-page" data-page-code="crm-order-process" data-business-write-count="0">
    <header class="page-header">
      <div>
        <p class="eyebrow">PROCESS CENTER / CRM / ORDER OPERATION V1.0</p>
        <h1>订单业务流程</h1>
        <p>接单 → 订单评审 → 产品设计 → BOM → 工艺路线 → 工程资料 → 工程核算 → 制造输出 → MRP / 计划输入</p>
      </div>
      <button type="button" @click="router.push('/process-center')">返回流程中心</button>
    </header>

    <nav class="module-tabs" aria-label="业务流程模块">
      <button type="button" @click="router.push('/process-center?module=SCM')">SCM 供应链</button>
      <button type="button" class="active">CRM 营销</button>
      <button type="button" @click="router.push('/process-center?module=PDE')">PDE 产品工程</button>
      <button type="button" @click="router.push('/process-center?module=EMD')">EMD 主数据</button>
    </nav>

    <section class="process-card" data-acceptance-id="crm-order-operation-process">
      <header>
        <div><h2>CRM 订单业务流程 V1.0</h2><p>本轮只开放 STEP 1“接单”的真实业务样本只读预览。</p></div>
        <span>STEP 1 AWAITING</span>
      </header>
      <div class="node-track" data-acceptance-id="crm-order-node-track">
        <template v-for="(node, index) in crmOrderNodes" :key="node.nodeCode">
          <ProcessNodeNavigation
            :node="node"
            :selected="selectedNode?.nodeCode === node.nodeCode"
            @inspect="selectedNode = $event"
            @opened="handleOpened"
          />
          <b v-if="index < crmOrderNodes.length - 1" aria-hidden="true">→</b>
        </template>
      </div>
      <p class="guardrail">后续节点均等待 STEP 1 用户验收；计划输入未部署，生产业务写入 0。</p>
    </section>

    <aside v-if="selectedNode" class="inspector">
      <span>当前查看节点</span><strong>{{ selectedNode.nodeName }}</strong>
      <p>{{ selectedNode.statusDescription }}</p>
      <code>{{ selectedNode.pageUrl }}</code>
    </aside>
  </section>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ProcessNodeNavigation from '../components/ProcessNodeNavigation.vue'
import { CRM_ORDER_PROCESS_NODES } from '../runtime/crmOrderProcessRegistry.js'

const router = useRouter()
const crmOrderNodes = CRM_ORDER_PROCESS_NODES
const selectedNode = ref(crmOrderNodes[0])

function handleOpened(result) {
  if (!result.opened) selectedNode.value = result.node
}
</script>

<style scoped>
.crm-process-page{display:grid;gap:16px;padding:20px;background:#f4f7fb;color:#17233b}.page-header,.process-card,.inspector{border:1px solid #c7d7fe;border-radius:12px;background:#fff;padding:20px}.page-header,.process-card>header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}.page-header h1,.process-card h2{margin:4px 0 8px}.page-header p,.process-card p{margin:0;color:#64748b}.eyebrow{color:#1d4ed8!important;font-size:12px;font-weight:800}.module-tabs{display:flex;flex-wrap:wrap;gap:8px}.module-tabs button,.page-header button{padding:9px 13px;border:1px solid #bfdbfe;border-radius:8px;background:#fff;color:#1e3a8a}.module-tabs .active{background:#dbeafe;border-color:#2563eb;font-weight:800}.process-card>header span{padding:6px 10px;border-radius:999px;background:#fff7ed;color:#c2410c;font-size:12px;font-weight:800}.node-track{display:flex;align-items:center;gap:8px;margin-top:18px;padding-bottom:12px;overflow-x:auto}.node-track>b{color:#2563eb;font-size:20px}.guardrail{padding:12px;border:1px dashed #fdba74;border-radius:8px;background:#fff7ed!important;color:#9a3412!important}.inspector{display:grid;gap:6px}.inspector span{color:#64748b;font-size:12px}.inspector code{overflow-wrap:anywhere;color:#1d4ed8}@media(max-width:760px){.page-header,.process-card>header{display:grid}}
</style>
