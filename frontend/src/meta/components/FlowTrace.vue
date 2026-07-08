<template>
  <div class="flow-trace">
    <h3>流程回溯</h3>

    <div class="trace-list">
      <div v-for="(item, index) in trace" :key="index" class="trace-item">
        <div class="line">
          <b>{{ item.from }}</b>
          →
          <b>{{ item.to }}</b>
        </div>

        <div class="meta">
          <span>👤 {{ item.user }}</span>
          <span>🧑‍💼 {{ item.role }}</span>
          <span>⏱ {{ formatTime(item.time) }}</span>
        </div>

        <div class="duration" v-if="item.duration">耗时：{{ item.duration / 1000 }} 秒</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { buildFlowTrace } from '@/meta/runtime/flowReplayEngine'

const props = defineProps({
  orderId: String,
})

const trace = computed(() => {
  return buildFlowTrace(props.orderId || '')
})

function formatTime(t) {
  return new Date(t).toLocaleString()
}
</script>

<style>
.flow-trace {
  padding: 20px;
}

.trace-item {
  border-left: 3px solid #409eff;
  padding: 10px;
  margin-bottom: 10px;
  background: #f5f5f5;
}

.line {
  font-size: 14px;
}

.meta {
  font-size: 12px;
  color: #666;
  margin-top: 5px;
  display: flex;
  gap: 10px;
}

.duration {
  font-size: 12px;
  color: red;
}
</style>
