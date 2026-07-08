<template>
  <main class="onboarding-page">
    <section class="hero">
      <p>First-time setup</p>
      <h1>Explore ProfitOS safely with demo data</h1>
      <span>Review the operating model, sample order, and customer profit preview before entering the cockpit.</span>
    </section>

    <section class="onboarding-grid">
      <article class="panel">
        <h2>System guide</h2>
        <ol>
          <li>ProfitOS makes profit decisions.</li>
          <li>PalmCloud executes ERP, MES, SCM, and WMS workflows.</li>
          <li>The cockpit keeps health, billing, trace, and tenant context visible.</li>
        </ol>
      </article>

      <article class="panel">
        <h2>Sample order</h2>
        <div class="row">
          <span>Revenue</span>
          <b>{{ formatCurrency(order.revenue) }}</b>
        </div>
        <div class="row">
          <span>Total Cost</span>
          <b>{{ formatCurrency(order.materialCost + order.laborCost + order.overhead) }}</b>
        </div>
      </article>

      <ProductState
        type="skeleton"
        title="Loading preview"
        message="Preparing sample data"
      />
    </section>

    <section class="customer-preview">
      <h2>Customer profit preview</h2>
      <div v-for="customer in customers" :key="customer.name" class="customer-row">
        <span>{{ customer.name }}</span>
        <b>{{ formatCurrency(customer.profit) }}</b>
      </div>
    </section>

    <div class="actions">
      <el-button type="primary" size="large" @click="enterCockpit">
        Enter Cockpit
      </el-button>
      <el-button size="large" @click="viewPricing">
        Compare Plans
      </el-button>
    </div>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import ProductState from '../components/ProductState.vue'
import { completeOnboarding, getDemoCustomers, getDemoOrder } from '../demo/demoMode.js'
import { stateManager } from '../runtime/stateManager.js'

const router = useRouter()
const order = getDemoOrder()
const customers = getDemoCustomers()
const currentStep = ref(stateManager.getSession().onboardingStep || 0)

function formatCurrency(value) {
  return `$${Number(value || 0).toLocaleString()}`
}

function enterCockpit() {
  stateManager.completeOnboarding()
  completeOnboarding()
  router.push('/dashboard')
}

function viewPricing() {
  stateManager.setOnboardingStep(2)
  router.push('/pricing')
}

onMounted(() => {
  const nextStep = Math.max(currentStep.value, 1)
  currentStep.value = nextStep
  stateManager.setOnboardingStep(nextStep)
})
</script>

<style scoped>
.onboarding-page {
  min-height: 100vh;
  padding: 28px;
  background: #eef3f8;
}

.hero,
.panel,
.customer-preview {
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.hero {
  padding: 26px;
  margin-bottom: 16px;
}

.hero p,
.hero h1,
.hero span {
  margin: 0;
}

.hero p {
  color: #2563eb;
  font-weight: 700;
}

.hero h1 {
  margin: 8px 0;
  color: #111827;
}

.hero span,
.row span,
.customer-row span {
  color: #64748b;
}

.onboarding-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.panel,
.customer-preview {
  padding: 18px;
}

.panel h2,
.customer-preview h2 {
  margin: 0 0 14px;
}

.panel ol {
  margin: 0;
  padding-left: 18px;
}

.panel li {
  margin-bottom: 10px;
}

.row,
.customer-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #edf2f7;
}

.customer-preview {
  margin-top: 14px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

@media (max-width: 900px) {
  .onboarding-grid {
    grid-template-columns: 1fr;
  }
}
</style>
