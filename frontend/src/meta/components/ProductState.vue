<template>
  <section class="product-state" :class="type">
    <template v-if="type === 'skeleton'">
      <div class="skeleton-line wide" />
      <div class="skeleton-line" />
      <div class="skeleton-grid">
        <span />
        <span />
        <span />
      </div>
    </template>

    <template v-else>
      <strong>{{ title }}</strong>
      <p>{{ message }}</p>
    </template>
  </section>
</template>

<script setup>
defineProps({
  type: {
    type: String,
    default: 'empty',
  },
  title: {
    type: String,
    default: 'No data',
  },
  message: {
    type: String,
    default: 'There is no information to show yet.',
  },
})
</script>

<style scoped>
.product-state {
  padding: 18px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.product-state strong {
  display: block;
  margin-bottom: 6px;
  color: #111827;
}

.product-state p {
  margin: 0;
  color: #64748b;
}

.product-state.error {
  border-color: #fecaca;
  background: #fff7f7;
}

.product-state.loading {
  border-color: #bfdbfe;
  background: #eff6ff;
}

.skeleton-line,
.skeleton-grid span {
  display: block;
  height: 12px;
  border-radius: 999px;
  background: linear-gradient(90deg, #e5edf6, #f8fafc, #e5edf6);
}

.skeleton-line {
  width: 64%;
  margin-bottom: 12px;
}

.skeleton-line.wide {
  width: 88%;
}

.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-top: 18px;
}

.skeleton-grid span {
  height: 58px;
  border-radius: 8px;
}
</style>
