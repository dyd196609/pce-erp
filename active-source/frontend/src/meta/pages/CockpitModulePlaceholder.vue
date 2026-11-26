<template>
  <main class="placeholder-page">
    <section class="placeholder-header">
      <p>{{ layer }}</p>
      <h1>{{ title }}</h1>
    </section>

    <section class="placeholder-grid">
      <article class="placeholder-panel">
        <span>Status</span>
        <strong>READY</strong>
      </article>
      <article class="placeholder-panel">
        <span>Tenant</span>
        <strong>company_a</strong>
      </article>
      <article class="placeholder-panel">
        <span>Owner</span>
        <strong>{{ owner }}</strong>
      </article>
    </section>
  </main>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: 'Module',
  },
  layer: {
    type: String,
    default: 'Cockpit Module',
  },
  owner: {
    type: String,
    default: 'ProfitOS',
  },
})
</script>

<style scoped>
.placeholder-page {
  min-height: 420px;
  padding: 24px;
  background: #f4f7fb;
}

.placeholder-header {
  margin-bottom: 18px;
}

.placeholder-header p {
  margin: 0 0 4px;
  color: #64748b;
}

.placeholder-header h1 {
  margin: 0;
  color: #1f2937;
}

.placeholder-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.placeholder-panel {
  padding: 18px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.placeholder-panel span {
  display: block;
  margin-bottom: 8px;
  color: #64748b;
}

.placeholder-panel strong {
  font-size: 24px;
  color: #111827;
}

@media (max-width: 800px) {
  .placeholder-grid {
    grid-template-columns: 1fr;
  }
}
</style>
