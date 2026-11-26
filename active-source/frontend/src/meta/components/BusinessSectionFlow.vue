<template>
  <section class="business-section-flow" aria-label="页面内部流程">
    <header>
      <p>页面内部流程</p>
      <h2>{{ title }}</h2>
    </header>
    <ol>
      <li
        v-for="section in sections"
        :key="section.sectionId"
        :class="{ technical: section.isTechnicalSection }"
      >
        <span>{{ section.sequence }}</span>
        <div>
          <strong>{{ section.sectionTitle }}</strong>
          <small>{{ section.sectionPurpose }}</small>
        </div>
      </li>
    </ol>
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: '从来源确认到下一步输出',
  },
  sections: {
    type: Array,
    default: () => [],
  },
})
</script>

<style scoped>
.business-section-flow {
  display: grid;
  gap: 12px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #ffffff;
}

.business-section-flow header p {
  margin: 0;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
}

.business-section-flow header h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 16px;
}

.business-section-flow ol {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.business-section-flow li {
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 10px;
  align-items: start;
  padding: 10px;
  border-radius: 8px;
  background: #f8fafc;
}

.business-section-flow li.technical {
  background: #f1f5f9;
}

.business-section-flow li > span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #2563eb;
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
}

.business-section-flow strong {
  display: block;
  color: #0f172a;
  font-size: 13px;
}

.business-section-flow small {
  display: block;
  margin-top: 3px;
  color: #64748b;
  line-height: 1.5;
}
</style>
