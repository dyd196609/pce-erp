<template>
  <div class="timeline">
    <h3>审批轨迹</h3>

    <el-timeline>
      <el-timeline-item v-for="log in logs" :key="log.id" :timestamp="log.time" placement="top">
        <p>
          <b>{{ log.action }}</b>
          （{{ log.from }} → {{ log.to }}）
        </p>

        <p>用户：{{ log.user }} ｜ 角色：{{ log.role }}</p>
      </el-timeline-item>
    </el-timeline>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { getAuditLogsByOrder } from '@/meta/runtime/auditEngine'

const props = defineProps({
  orderId: String,
})

const logs = computed(() => {
  return getAuditLogsByOrder(props.orderId || '')
})
</script>

<style scoped>
.timeline {
  padding: 20px;
}
</style>
