<template>
  <section class="page-step-navigation" aria-label="业务流程步骤导航">
    <router-link
      v-if="previousStep"
      class="step-nav-button"
      :to="previousStep.routePath"
    >
      上一步：{{ previousStep.stepName }}
    </router-link>
    <span v-else class="step-nav-button disabled">上一步：暂无</span>

    <router-link
      v-if="primarySourceStep"
      class="step-nav-button"
      :to="primarySourceStep.routePath"
    >
      查看来源：{{ primarySourceStep.stepName }}
    </router-link>
    <span v-else class="step-nav-button disabled">查看来源：当前为流程起点</span>

    <router-link
      v-if="defaultNextStep"
      class="step-nav-button primary"
      :to="defaultNextStep.routePath"
    >
      下一步：{{ defaultNextStep.stepName }}
    </router-link>
    <span v-else class="step-nav-button disabled">下一步：流程末端</span>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  context: {
    type: Object,
    default: null,
  },
})

const previousStep = computed(() => props.context?.previousStep || null)
const defaultNextStep = computed(() => props.context?.defaultNextStep || null)
const primarySourceStep = computed(() => props.context?.sourceSteps?.[0] || previousStep.value || null)
</script>

<style scoped>
.page-step-navigation {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 12px 0;
}

.step-nav-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: #ffffff;
  color: #1e293b;
  font-size: 13px;
  font-weight: 700;
  text-decoration: none;
}

.step-nav-button.primary {
  border-color: #2563eb;
  background: #2563eb;
  color: #ffffff;
}

.step-nav-button.disabled {
  color: #94a3b8;
  background: #f8fafc;
  cursor: not-allowed;
}
</style>
