<template>
  <section class="business-process-context-bar">
    <article>
      <span>所属模块</span>
      <strong>{{ context.step.moduleName }}</strong>
    </article>
    <article>
      <span>业务流程</span>
      <strong>{{ context.step.processName }}</strong>
    </article>
    <article>
      <span>当前步骤</span>
      <strong>{{ context.step.stepName }}</strong>
      <small>第 {{ context.step.stepSequence }} 步</small>
    </article>
    <article>
      <span>来源步骤</span>
      <strong>{{ sourceNames }}</strong>
    </article>
    <article>
      <span>下一步骤</span>
      <strong>{{ nextNames }}</strong>
    </article>
    <article>
      <span>当前流程状态</span>
      <strong>{{ flowStatus }}</strong>
    </article>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  context: { type: Object, required: true },
  flowStatus: { type: String, default: '只读导航已接入' },
})

const sourceNames = computed(() => {
  const names = props.context.sourceSteps?.map((item) => item.stepName).filter(Boolean) || []
  return names.length ? names.join(' / ') : '无来源步骤'
})

const nextNames = computed(() => {
  const names = props.context.nextSteps?.map((item) => item.stepName).filter(Boolean) || []
  return names.length ? names.join(' / ') : '流程终点'
})
</script>

<style scoped>
.business-process-context-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
  padding: 14px;
  border: 1px solid #d8e0ea;
  border-radius: 8px;
  background: #f8fafc;
}

.business-process-context-bar article {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.business-process-context-bar span,
.business-process-context-bar small {
  color: #64748b;
  font-size: 12px;
}

.business-process-context-bar strong {
  color: #0f172a;
}
</style>
