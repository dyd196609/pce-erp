<template>
  <section
    class="pce-enterprise-list-canary-card"
    data-acceptance-id="enterprise-list-canary-mode"
    data-list-data-mode="canary_acceptance"
    aria-label="金丝雀验收模式"
  >
    <h3>金丝雀验收模式</h3>
    <div class="canary-mode-grid">
      <span>数据模式：<strong data-acceptance-id="canary-list-data-mode">{{ facts.dataMode }}</strong></span>
      <span>批次：<strong data-acceptance-id="canary-list-batch-id">{{ facts.canaryBatchId }}</strong></span>
      <span>场景：<strong data-acceptance-id="canary-list-scenario-code">{{ facts.scenarioCode }}</strong></span>
      <span>清理策略：<strong data-acceptance-id="canary-list-cleanup-policy">{{ facts.cleanupPolicy }}</strong></span>
      <span>对象编号：<strong data-acceptance-id="canary-list-object-no">{{ facts.canaryContext?.current?.objectNo }}</strong></span>
      <span>当前节点：<strong data-acceptance-id="canary-list-current-node">{{ facts.canaryContext?.current?.moduleName }}</strong></span>
      <span>下一节点：<strong data-acceptance-id="canary-list-next-node">{{ facts.canaryContext?.next?.moduleName || '流程终点' }}</strong></span>
      <span>当前数据源：<strong data-acceptance-id="canary-list-data-source">canary_acceptance</strong></span>
      <span>正式业务数据读取：<strong data-acceptance-id="canary-list-business-read">否</strong></span>
      <span>金丝雀对象数量：<strong data-acceptance-id="canary-list-object-count">{{ facts.canaryObjectCount || facts.recordCount || 0 }}</strong></span>
    </div>
    <p>当前列表由只读金丝雀数据 Provider 提供，不读取或修改普通 PurchaseRequest 业务数据。</p>
  </section>
</template>

<script setup>
defineProps({
  facts: { type: Object, required: true },
})
</script>

<style scoped>
.pce-enterprise-list-canary-card {
  display: grid;
  gap: 10px;
  margin: 12px 0 14px;
  padding: 14px;
  border: 1px solid #60a5fa;
  border-radius: 10px;
  background: #eff6ff;
}
.pce-enterprise-list-canary-card h3,
.pce-enterprise-list-canary-card p { margin: 0; }
.canary-mode-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 8px;
}
.canary-mode-grid span {
  padding: 9px 10px;
  border-radius: 7px;
  background: #fff;
  color: #475569;
}
.canary-mode-grid strong { color: #0f172a; }
</style>
