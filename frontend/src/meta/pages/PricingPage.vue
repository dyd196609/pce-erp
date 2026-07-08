<template>
  <main class="pricing-page">
    <header class="pricing-header">
      <p>Commercial Entry</p>
      <h1>Choose a ProfitOS plan</h1>
      <span>Plans are safe to test in demo mode and can be upgraded without changing cockpit configuration.</span>
    </header>

    <section class="pricing-grid">
      <article v-for="plan in plans" :key="plan.key" class="plan-card">
        <h2>{{ plan.name }}</h2>
        <strong>${{ plan.price }}</strong>
        <p>{{ plan.description }}</p>
        <ul>
          <li v-for="feature in plan.features" :key="feature">{{ feature }}</li>
        </ul>
        <el-button type="primary" plain @click="selectPlan(plan)">
          Select {{ plan.name }}
        </el-button>
      </article>
    </section>

    <ProductState
      class="state"
      type="empty"
      title="Upgrade flow ready"
      message="Plan selection updates the active tenant session and returns to the cockpit."
    />
  </main>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import ProductState from '../components/ProductState.vue'
import { createProfitSession, getCommercialPlans, getProfitSession } from '../demo/demoMode.js'
import { stateManager } from '../runtime/stateManager.js'
import { trackSubscriptionUpgrade } from '../growth/revenueEngine.js'

const router = useRouter()
const plans = getCommercialPlans()

function selectPlan(plan) {
  const session = getProfitSession()
  const previousPlan = stateManager.getPlan()
  stateManager.setPlan(plan.key)
  stateManager.setSession({
    lastPlanChange: Date.now(),
  })

  createProfitSession({
    ...session,
    plan: plan.key,
  })
  trackSubscriptionUpgrade({
    tenantId: stateManager.getTenant().id,
    fromPlan: previousPlan,
    toPlan: plan.key,
  })

  ElMessage.success(`${plan.name} plan selected`)
  router.push('/dashboard')
}
</script>

<style scoped>
.pricing-page {
  min-height: 100vh;
  padding: 28px;
  background: #eef3f8;
}

.pricing-header {
  margin-bottom: 18px;
}

.pricing-header p,
.pricing-header h1,
.pricing-header span {
  margin: 0;
}

.pricing-header p {
  color: #2563eb;
  font-weight: 700;
}

.pricing-header h1 {
  margin: 8px 0;
  color: #111827;
}

.pricing-header span {
  color: #64748b;
}

.pricing-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.plan-card {
  padding: 20px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.plan-card h2,
.plan-card p {
  margin: 0;
}

.plan-card strong {
  display: block;
  margin: 14px 0 8px;
  font-size: 32px;
}

.plan-card p {
  color: #64748b;
  min-height: 48px;
}

.plan-card ul {
  min-height: 100px;
  padding-left: 18px;
}

.plan-card li {
  margin-bottom: 8px;
}

.state {
  margin-top: 16px;
}

@media (max-width: 900px) {
  .pricing-grid {
    grid-template-columns: 1fr;
  }
}
</style>
