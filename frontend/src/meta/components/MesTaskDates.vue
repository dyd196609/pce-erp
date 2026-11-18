<template>
  <section class="task-dates" aria-label="任务日期事实" data-task-date-facts="D2-R1" :data-dates-current="current">
    <h3>任务日期</h3>
    <p v-if="!current" role="note">上次只读日期；当前读取未核实，不能据此操作。</p>
    <template v-if="display.valid">
      <p class="date-meaning">计划取本任务冻结来源；实际开工与记录时间分别查看<span v-if="display.timezone">。业务时区：{{ display.timezone }}</span>。</p>
      <dl><div v-for="row in display.rows" :key="row.key"><dt>{{ row.label }}</dt><dd :data-date-kind="row.key">{{ row.value }}</dd></div></dl>
      <p v-if="showReview">独审生效时间仅表示审核结果生效，不等同生产现场实际完成时间。</p>
    </template>
    <p v-else role="note">当前任务尚未取得匹配的日期事实；计划和实际日期均未核实。</p>
  </section>
</template>
<script setup>
import { computed } from 'vue'
import { taskDateDisplay } from '@/meta/runtime/mesTaskDates.js'
const props = defineProps({ facts: { type: Object, default: null }, taskId: { type: [Number, String], default: null }, current: Boolean, showReview: Boolean })
const display = computed(() => taskDateDisplay(props.facts, props.taskId, { showReview: props.showReview }))
</script>
<style scoped>
.task-dates{margin:20px 0;padding:16px;border:1px solid #dbe5f2;border-radius:10px;background:#f8fbff;color:#263e59;min-width:0}
h3{margin:0 0 12px;font-size:1.05rem}p{margin:8px 0;line-height:1.6;overflow-wrap:anywhere}.date-meaning{color:#60768e}
dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:16px 0}dl>div{min-width:0}dt{color:#60768e;margin-bottom:6px}dd{margin:0;line-height:1.6;overflow-wrap:anywhere}
@media(max-width:600px){dl{grid-template-columns:minmax(0,1fr)}.task-dates{padding:14px}}
</style>
