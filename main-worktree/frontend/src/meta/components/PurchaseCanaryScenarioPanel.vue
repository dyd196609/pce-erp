<template>
  <section
    v-if="context"
    class="purchase-canary-panel"
    data-acceptance-id="purchase-canary-scenario-panel"
    data-current-state-source="server"
  >
    <div class="purchase-canary-heading">
      <div>
        <p>持久演示读模型 · 服务端权威</p>
        <h2>金丝雀验收场景</h2>
      </div>
      <label>
        场景选择
        <select
          :value="context.scenario.code"
          data-acceptance-id="purchase-canary-scenario-selector"
          @change="changeScenario"
        >
          <option v-for="item in context.scenarios" :key="item.code" :value="item.code">
            {{ item.code }} · {{ item.name }}
          </option>
        </select>
      </label>
    </div>
    <div class="purchase-canary-grid">
      <article><span>批次</span><strong>{{ context.batchId }}</strong></article>
      <article><span>场景代码</span><strong>{{ context.scenario.code }}</strong></article>
      <article><span>场景名称</span><strong>{{ context.scenario.name }}</strong></article>
      <article><span>用途</span><strong>{{ context.purpose }}</strong></article>
      <article data-acceptance-id="canary-data-type"><span>数据类型</span><strong>{{ context.dataType }}</strong></article>
      <article data-acceptance-id="canary-retention-policy"><span>保留策略</span><strong>{{ context.retentionPolicy?.cleanupPolicy }}</strong></article>
      <article><span>上一模块</span><strong>{{ context.previous?.moduleName || '流程起点' }}</strong></article>
      <article><span>当前模块</span><strong>{{ context.current.moduleName }}</strong></article>
      <article><span>下一模块</span><strong>{{ context.next?.moduleName || '本轮终点' }}</strong></article>
      <article><span>当前对象编号</span><strong>{{ context.current.objectNo }}</strong></article>
      <article><span>当前状态</span><strong>{{ context.current.status }}</strong></article>
      <article><span>下一步允许</span><strong>{{ context.current.nextStepAllowed ? '是' : '否' }}</strong></article>
      <article class="purchase-canary-wide"><span>阻断原因</span><strong>{{ context.current.blockReason || '无' }}</strong></article>
    </div>
    <div class="purchase-canary-actions">
      <button v-if="context.previous" type="button" @click="navigate(context.previous)">查看上一模块</button>
      <button type="button" @click="router.push(canaryRoute('/process-center'))">返回业务流程中心</button>
      <button v-if="context.next" type="button" :disabled="!context.current.nextStepAllowed" @click="navigate(context.next)">
        查看下一模块
      </button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { loadEnterpriseListCanaryFacts } from '@/meta/runtime/enterpriseListCanaryDataProvider.js'

const props = defineProps({
  moduleCode: { type: String, required: true },
})

const route = useRoute()
const router = useRouter()
const context = ref(null)

function queryFor(scenarioCode = route.query.scenarioCode || 'HAPPY_PATH') {
  return {
    batchId: route.query.canaryBatchId || 'PURCHASE-FLOW-DEMO-V1',
    scenarioCode,
    moduleCode: props.moduleCode,
  }
}

function canaryRoute(path, scenarioCode = context.value?.scenario?.code || 'HAPPY_PATH') {
  return {
    path,
    query: {
      ...route.query,
      canaryBatchId: context.value?.batchId || 'PURCHASE-FLOW-DEMO-V1',
      scenarioCode,
      sourceObjectNo: context.value?.current?.objectNo || '',
    },
  }
}

async function load() {
  const plainApDraftDemo = props.moduleCode === 'account-payable-draft'
  if (!route.query.canaryBatchId && !plainApDraftDemo) {
    context.value = null
    return
  }
  try {
    const query = queryFor()
    const facts = await loadEnterpriseListCanaryFacts(props.moduleCode, {
      canaryBatchId: query.batchId,
      scenarioCode: query.scenarioCode,
    })
    context.value = facts?.canaryContext || null
  } catch {
    context.value = null
  }
}

function changeScenario(event) {
  const scenarioCode = event.target.value
  router.replace(canaryRoute(route.path, scenarioCode)).then(load)
}

function navigate(target) {
  router.push(canaryRoute(target.routePath))
}

watch(() => [route.query.canaryBatchId, route.query.scenarioCode, props.moduleCode], load)
onMounted(load)
</script>

<style scoped>
.purchase-canary-panel {
  margin: 16px 0;
  padding: 18px;
  border: 1px solid #6f9bd1;
  border-radius: 12px;
  background: linear-gradient(135deg, #f4f9ff, #edf6f1);
}
.purchase-canary-heading, .purchase-canary-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.purchase-canary-heading p { margin: 0; color: #496782; }
.purchase-canary-heading h2 { margin: 3px 0 12px; }
.purchase-canary-heading label { display: grid; gap: 4px; }
.purchase-canary-heading select { min-width: 260px; padding: 7px; }
.purchase-canary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
}
.purchase-canary-grid article {
  display: grid;
  gap: 3px;
  padding: 9px;
  border-radius: 8px;
  background: rgba(255,255,255,.8);
}
.purchase-canary-grid span { color: #637386; font-size: 12px; }
.purchase-canary-wide { grid-column: span 2; }
.purchase-canary-actions { justify-content: flex-start; margin-top: 12px; }
.purchase-canary-actions button { padding: 7px 12px; }
</style>
