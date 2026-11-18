<template>
  <section class="page-operation-guide" aria-label="页面操作指引">
    <div class="guide-heading">
      <p class="guide-eyebrow">页面操作指引</p>
      <h2>{{ context?.currentStep?.pageTitle || context?.currentStep?.stepName || '当前业务页面' }}</h2>
      <span>{{ context?.currentStep?.businessPurpose || purpose || '按业务流程完成当前页面操作。' }}</span>
    </div>

    <div class="guide-grid">
      <article>
        <span>进入本页前</span>
        <strong>{{ prerequisiteText }}</strong>
      </article>
      <article>
        <span>本页要完成</span>
        <strong>{{ context?.currentStep?.operatorHint || purpose || '检查来源、执行当前环节允许的页面操作。' }}</strong>
      </article>
      <article>
        <span>本页输出</span>
        <strong>{{ outputText }}</strong>
      </article>
      <article>
        <span>保护边界</span>
        <strong>{{ boundaryText }}</strong>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  context: {
    type: Object,
    default: null,
  },
  purpose: {
    type: String,
    default: '',
  },
  outputs: {
    type: Array,
    default: () => [],
  },
})

const prerequisiteText = computed(() => {
  const prerequisites = props.context?.currentStep?.prerequisites || []
  return prerequisites.length ? prerequisites.join('；') : '来源单据可追溯，当前页面只处理本环节允许的操作。'
})

const outputText = computed(() => {
  const outputs = props.outputs.length ? props.outputs : props.context?.currentStep?.outputs || []
  return outputs.length ? outputs.join('；') : '生成或更新本环节页面对象，不反向修改来源业务单据。'
})

const boundaryText = computed(() => {
  const boundaries = props.context?.currentStep?.protectionBoundaries || []
  return boundaries.length ? boundaries.join('；') : '不写总账、不核销、不生成银行流水、不越级修改上下游业务状态。'
})
</script>

<style scoped>
.page-operation-guide {
  display: grid;
  gap: 14px;
  padding: 18px;
  border: 1px solid #dbe5f4;
  border-radius: 8px;
  background: #f8fbff;
}

.guide-heading {
  display: grid;
  gap: 4px;
}

.guide-heading h2 {
  margin: 0;
  color: #1d4ed8;
  font-size: 18px;
}

.guide-heading span {
  color: #475569;
  line-height: 1.7;
}

.guide-eyebrow {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.guide-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
}

.guide-grid article {
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.guide-grid span {
  color: #64748b;
  font-size: 12px;
}

.guide-grid strong {
  color: #0f172a;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.6;
}
</style>
