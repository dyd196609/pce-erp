<template>
  <div class="control-tower">
    <h2>Meta ERP Control Tower (V3.8)</h2>

    <div class="grid">
      <section class="card health-card">
        <h3>System Health</h3>
        <div class="health">{{ intelligence?.health ?? 0 }}/100</div>
        <div class="summary">{{ intelligence?.insight?.summary || 'No trace data' }}</div>
      </section>

      <section class="card">
        <h3>Bottlenecks</h3>
        <div v-if="(intelligence?.bottlenecks || []).length === 0" class="empty">None</div>
        <div v-for="b in intelligence?.bottlenecks || []" :key="b.step" class="line">
          <span>{{ b.step }}</span>
          <strong>{{ Math.round(b.avgCost) }}ms</strong>
        </div>
      </section>

      <section class="card">
        <h3>Errors</h3>
        <div v-if="errors.length === 0" class="empty">None</div>
        <div v-for="(e, index) in errors" :key="`${e.event}-${index}`" class="line error">
          <span>{{ e.event }}</span>
          <strong>{{ e.count || 1 }}</strong>
        </div>
      </section>

      <section class="card">
        <h3>Optimization Actions</h3>
        <div v-if="(actions?.actions || []).length === 0" class="empty">None</div>
        <div v-for="(a, i) in actions?.actions || []" :key="i" class="action">
          <strong>{{ a.type }} / {{ a.severity }}</strong>
          <div v-for="s in a.suggestion" :key="s">- {{ s }}</div>
        </div>
      </section>
    </div>

    <section class="card timeline">
      <h3>Trace Timeline</h3>
      <div v-if="traces.length === 0" class="empty">No trace data</div>
      <div v-for="(t, index) in traces" :key="`${t.time}-${index}`" class="trace-row">
        <span class="event">{{ t.event }}</span>
        <span class="cost">{{ t.payload?.cost ?? 0 }}ms</span>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const traces = ref([])
const intelligence = ref(null)
const actions = ref(null)
let timer = null

const errors = computed(() => intelligence.value?.errors || [])

function refresh() {
  const traceApi = window.__TRACE__

  traces.value = traceApi?.get?.() || []
  intelligence.value = traceApi?.intelligence?.() || null
  actions.value = traceApi?.actions?.() || null
}

onMounted(() => {
  refresh()
  timer = window.setInterval(refresh, 1000)
})

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer)
  }
})
</script>

<style scoped>
.control-tower {
  min-height: 100vh;
  padding: 20px;
  background: #f5f7fb;
  color: #1f2937;
  font-family: Arial, sans-serif;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.card {
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid #dde3ee;
  border-radius: 8px;
  background: #ffffff;
}

.health {
  font-size: 32px;
  font-weight: 700;
}

.summary,
.empty {
  color: #64748b;
}

.line,
.trace-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  border-top: 1px solid #eef2f7;
}

.error {
  color: #b42318;
}

.action {
  padding: 8px 0;
  border-top: 1px solid #eef2f7;
}

.timeline {
  max-height: 46vh;
  overflow: auto;
}

.event {
  overflow-wrap: anywhere;
}

.cost {
  white-space: nowrap;
  font-weight: 700;
}
</style>
