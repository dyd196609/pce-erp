<template>
  <main class="batch-page" data-acceptance-id="production-batch-foundation-preview" data-read-only="true">
    <section class="hero"><div><p>GROUP 6 · PLANNING FOUNDATION</p><h1>Production Batch 与 GENERAL / KITTING 排程预览</h1><span>按生产批次调度，不按订单号直接调度；当前无保存、无迁移、无计划下达。</span></div><strong>PREVIEW ONLY</strong></section>
    <section v-if="loading" class="panel">正在加载确定性预览……</section><section v-else-if="error" class="panel error">{{ error }}</section>
    <template v-else>
      <section class="status"><article><span>FOUNDATION</span><strong>DEVELOPED</strong></article><article><span>PRODUCTION ENABLED</span><strong>FALSE</strong></article><article><span>BUSINESS WRITE</span><strong>{{ facts.productionBusinessWriteCount }}</strong></article><article><span>USER VALIDATED</span><strong>NO</strong></article></section>
      <section class="panel"><header><div><h2>正式分层与 Schema Contract</h2><p>SalesOrder 1:N ProductionBatch → ProductionBatchItem → Engineering/BOM/Routing → Operation Planning</p></div><span>{{ facts.schema.persistenceStatus }}</span></header>
        <div class="schema-grid"><article><h3>ProductionBatch</h3><code v-for="field in facts.schema.productionBatch" :key="field">{{ field }}</code></article><article><h3>ProductionBatchItem</h3><code v-for="field in facts.schema.productionBatchItem" :key="field">{{ field }}</code></article><article><h3>下游强制血缘</h3><code v-for="field in facts.schema.downstreamRequiredLineage" :key="field">{{ field }}</code></article></div>
        <ul><li v-for="rule in facts.schema.constraints" :key="rule">{{ rule }}</li></ul>
      </section>
      <section class="panel"><header><div><h2>批次数量分配预览</h2><p>订单行100 → B001=30、B002=30、B003=40。</p></div><strong>{{ facts.allocationPreview.valid ? 'VALID' : 'BLOCKED' }}</strong></header>
        <div class="table-wrap"><table><thead><tr><th>订单行</th><th>需求</th><th>已投产</th><th>剩余</th></tr></thead><tbody><tr v-for="row in facts.allocationPreview.items" :key="row.salesOrderItemId"><td>{{ row.salesOrderItemId }}</td><td>{{ row.demandQuantity }}</td><td>{{ row.allocatedQuantity }}</td><td>{{ row.remainingQuantity }}</td></tr></tbody></table></div>
      </section>
      <section class="mode-grid"><article class="panel"><h2>GENERAL · FLOW THROUGH</h2><p>每个成员自己的完成时间，成为自己的下一步最早开始。</p><member-table :preview="facts.generalPreview" /></article><article class="panel kitting"><h2>KITTING · BATCH GATE</h2><p>Required Members 全部完成后，MAX(own completion) 作为统一下游时间。</p><member-table :preview="facts.kittingPreview" /><div class="gate"><span>Slowest Member</span><strong>{{ facts.kittingPreview.slowestMember }}</strong><span>Gate Completion</span><strong>{{ facts.kittingPreview.batchKittingCompletionTime }}</strong></div></article></section>
      <section class="panel blocked"><header><div><h2>数据不足自动阻断</h2><p>缺真实成员、产能或工作日历时不生成貌似准确的齐套日期。</p></div><strong>{{ facts.blockedPreview.planningStatus }}</strong></header><ul><li v-for="item in facts.blockedPreview.missingRequiredData" :key="item">{{ item }}</li></ul><p>{{ facts.blockedPreview.blockReason }}</p></section>
      <section class="panel authority"><strong>配置权威：</strong>{{ facts.configurationAuthority }}<br><span>修改 Operation 默认或 RoutingStep 覆盖即可改变结果；算法不读取“组装/包装”等名称。</span></section>
      <router-link class="back" to="/foundation/manual-acceptance-center">返回 GROUP 1–6 人工验收中心</router-link>
    </template>
  </main>
</template>

<script setup>
import { defineComponent, h, onMounted, ref } from 'vue'
import { planningApi } from '@/api/planning.js'
const MemberTable = defineComponent({ props: { preview: Object }, setup(props) { return () => h('div', { class: 'table-wrap' }, [h('table', [h('thead', [h('tr', ['Member','Own completion','Downstream earliest start'].map(v => h('th', v)))]), h('tbody', (props.preview?.members || []).map(row => h('tr', [h('td', row.memberId), h('td', row.calculatedCompletionTime), h('td', row.nextEarliestStartTime)])))])]) } })
const facts = ref({ schema: { productionBatch: [], productionBatchItem: [], downstreamRequiredLineage: [], constraints: [] }, allocationPreview: { items: [] }, generalPreview: {}, kittingPreview: {}, blockedPreview: {} })
const loading = ref(true); const error = ref('')
async function load() { try { const response = await planningApi.productionBatchFoundationPreview(); facts.value = response?.data ?? response } catch (exception) { error.value = exception?.message || '排程预览读取失败' } finally { loading.value = false } }
onMounted(load)
</script>

<style scoped>
.batch-page{padding:24px;color:#17233a;box-sizing:border-box}.hero,.panel{border:1px solid #dbe3ef;border-radius:16px;background:#fff;padding:21px 23px;margin-bottom:18px}.hero{display:flex;justify-content:space-between;align-items:center;gap:20px;color:#fff;background:linear-gradient(135deg,#123767,#315bcf)}.hero h1,.hero p,.hero span,.panel h2,.panel p{margin:0}.hero h1{margin:5px 0 8px}.hero>strong{border:1px solid #aac4ff;border-radius:999px;padding:9px 13px}.status,.schema-grid,.mode-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}.status{margin-bottom:18px}.status article{display:grid;gap:6px;padding:16px;border-left:4px solid #315bcf;border-radius:11px;background:#fff}.status strong{font-size:20px}.panel header{display:flex;justify-content:space-between;gap:20px;align-items:center;margin-bottom:14px}.schema-grid article{display:flex;flex-direction:column;gap:7px;padding:14px;background:#f6f8fc;border-radius:10px}.schema-grid h3{margin:0 0 5px}.schema-grid code{padding:4px 7px;background:#e9eff9;border-radius:5px}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px;border-bottom:1px solid #e6ebf3;text-align:left;white-space:nowrap}th{background:#edf2f8}.kitting{border-color:#deb34d}.gate{display:grid;grid-template-columns:1fr 1.5fr;gap:7px;margin-top:14px;padding:13px;background:#fff4d7;border-radius:9px}.blocked{background:#fff1f0;border-color:#efb3ae}.authority{background:#eef4ff;line-height:1.8}.back{display:inline-block;padding:10px 15px;background:#315bcf;color:#fff;border-radius:9px;text-decoration:none;font-weight:700}.error{color:#a5221a}@media(max-width:760px){.batch-page{padding:12px}.hero,.panel header{align-items:flex-start;flex-direction:column}}
</style>
