<template>
  <div class="meta-control-center">
    <header class="meta-control-center__header">
      <div>
        <p>V30 Autonomous Enterprise OS</p>
        <h2>Meta Runtime Control Center</h2>
      </div>
      <strong>{{ autonomousEnterprise.fullAutonomyMode }}</strong>
    </header>

    <section class="meta-control-center__grid">
      <article>
        <span>Autonomous Enterprise Dashboard</span>
        <strong>{{ autonomousEnterprise.metrics.enterpriseAutonomyIndex }}/100</strong>
        <p>{{ autonomousEnterprise.mode }}</p>
      </article>

      <article>
        <span>Continuous Runtime Monitor</span>
        <strong>{{ autonomousEnterprise.continuousRuntime }}</strong>
        <p>{{ autonomousEnterprise.execution.continuousRuntime.autoWorkflowProgression }}</p>
      </article>

      <article>
        <span>Self-Healing Status Panel</span>
        <strong>{{ autonomousEnterprise.selfHealing }}</strong>
        <p>{{ autonomousEnterprise.healing.consistency.state }}</p>
      </article>

      <article>
        <span>Financial Autopilot View</span>
        <strong>{{ autonomousEnterprise.execution.financialAutopilot.financialAutopilot }}</strong>
        <p>{{ autonomousEnterprise.execution.financialAutopilot.profitOptimization.status }}</p>
      </article>
    </section>

    <section class="meta-control-center__instances">
      <h3>Runtime Instances</h3>
      <div v-for="i in dashboard.instances" :key="i.id" class="meta-control-center__instance">
        <span>{{ i.id }}</span>
        <strong>{{ i.status }}</strong>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { getControlDashboard } from '@/platform/runtime/metaControlCenter'
import { onEvent } from '@/platform/core/metaEventBus'
import { runAutonomousEnterprise } from '@/meta/autonomy/autonomousEnterpriseCore'

const dashboard = ref(getControlDashboard())
const autonomousEnterprise = computed(() =>
  runAutonomousEnterprise({
    goal: 'unmanned_enterprise_operation',
  })
)

onEvent('BPM_CHANGE', (data) => {
  console.log('Workflow changed:', data)
})
</script>

<style scoped>
.meta-control-center {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 20px;
  background: #f5f7fb;
  min-height: 100%;
}

.meta-control-center__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 16px;
  background: #fff;
}

.meta-control-center__header p {
  margin: 0 0 4px;
  color: #667085;
  font-size: 12px;
}

.meta-control-center__header h2 {
  margin: 0;
  color: #172033;
  font-size: 22px;
}

.meta-control-center__header strong {
  color: #0f7b5f;
  font-size: 18px;
}

.meta-control-center__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.meta-control-center__grid article,
.meta-control-center__instances {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
}

.meta-control-center__grid span,
.meta-control-center__instance span {
  color: #667085;
  font-size: 12px;
}

.meta-control-center__grid strong {
  display: block;
  margin: 8px 0;
  color: #101828;
  font-size: 18px;
}

.meta-control-center__grid p {
  margin: 0;
  color: #475467;
  font-size: 13px;
}

.meta-control-center__instances h3 {
  margin: 0 0 12px;
  font-size: 16px;
}

.meta-control-center__instance {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid #eef2f6;
}

@media (max-width: 960px) {
  .meta-control-center__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .meta-control-center__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .meta-control-center__grid {
    grid-template-columns: 1fr;
  }
}
</style>
