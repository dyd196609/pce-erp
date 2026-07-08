<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="copy">
        <p>Commercial SaaS Entry</p>
        <h1>ProfitOS</h1>
        <span>Multi-tenant profit operating system for enterprise teams.</span>
      </div>

      <el-form class="login-form" label-position="top">
        <el-form-item label="Tenant">
          <el-select v-model="form.tenantId" class="full">
            <el-option label="Demo Company" value="demo_company" />
            <el-option label="Company A" value="company_a" />
            <el-option label="Company B" value="company_b" />
          </el-select>
        </el-form-item>

        <el-form-item label="Role">
          <el-select v-model="form.role" class="full">
            <el-option label="Manager" value="manager" />
            <el-option label="Admin" value="admin" />
            <el-option label="Viewer" value="viewer" />
          </el-select>
        </el-form-item>

        <el-form-item label="Plan">
          <el-select v-model="form.plan" class="full">
            <el-option label="Basic" value="basic" />
            <el-option label="Pro" value="pro" />
            <el-option label="Enterprise" value="enterprise" />
          </el-select>
        </el-form-item>

        <el-checkbox v-model="form.demoMode">Demo mode</el-checkbox>

        <div class="actions">
          <el-button type="primary" size="large" @click="enterSystem">
            Enter ProfitOS
          </el-button>
          <el-button size="large" @click="goPricing">
            View Pricing
          </el-button>
        </div>
      </el-form>
    </section>
  </main>
</template>

<script setup>
import { reactive } from 'vue'
import { useRouter } from 'vue-router'
import { createProfitSession, hasCompletedOnboarding } from '../demo/demoMode.js'
import { stateManager } from '../runtime/stateManager.js'
import { recordActivation, activationSteps } from '../growth/activationEngine.js'

const router = useRouter()
const form = reactive({
  tenantId: 'demo_company',
  role: 'manager',
  plan: 'pro',
  demoMode: true,
})

function enterSystem() {
  stateManager.setTenant({
    id: form.tenantId,
    name: form.tenantId === 'demo_company' ? 'Demo Company' : form.tenantId,
    dataScope: form.demoMode ? 'demo' : form.tenantId,
  })
  stateManager.setRole(form.role)
  stateManager.setPlan(form.plan)
  stateManager.setSession({
    authenticated: true,
    demoMode: form.demoMode,
  })

  createProfitSession({
    tenantId: form.tenantId,
    tenantName: form.tenantId === 'demo_company' ? 'Demo Company' : form.tenantId,
    role: form.role,
    plan: form.plan,
    demoMode: form.demoMode,
  })
  recordActivation({
    tenantId: form.tenantId,
    step: activationSteps.FIRST_LOGIN,
    module: 'dashboard',
  })

  router.push(hasCompletedOnboarding() ? '/dashboard' : '/onboarding')
}

function goPricing() {
  router.push('/pricing')
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #eef3f8;
}

.login-panel {
  width: min(920px, 100%);
  display: grid;
  grid-template-columns: 1fr 420px;
  gap: 24px;
  padding: 28px;
  background: #fff;
  border: 1px solid #dce5f2;
  border-radius: 8px;
}

.copy {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.copy p,
.copy h1,
.copy span {
  margin: 0;
}

.copy p {
  color: #2563eb;
  font-weight: 700;
}

.copy h1 {
  margin: 8px 0;
  font-size: 42px;
  color: #111827;
}

.copy span {
  color: #64748b;
  font-size: 16px;
}

.login-form {
  padding: 20px;
  background: #f8fafc;
  border: 1px solid #e5edf6;
  border-radius: 8px;
}

.full {
  width: 100%;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

@media (max-width: 820px) {
  .login-panel {
    grid-template-columns: 1fr;
  }
}
</style>
