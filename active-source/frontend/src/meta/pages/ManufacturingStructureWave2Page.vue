<template>
  <main class="wave2-page" data-page-code="pce-foundation-wave2" data-fact-source="server">
    <header class="hero">
      <div>
        <p>FOUNDATION WAVE 2 · ENGINEERING ACCEPTANCE</p>
        <h1>制造结构、完整产品、BOM 与 Routing 基础</h1>
        <span>只读回读正式服务端事实；Excel、mock 与 localStorage 均不是本页事实来源。</span>
      </div>
      <button type="button" @click="load">刷新正式事实</button>
    </header>

    <section class="summary">
      <article><small>工程 Gate</small><strong>{{ facts.gate || '-' }}</strong></article>
      <article><small>工程状态</small><strong>{{ facts.engineeringStatus || '-' }}</strong></article>
      <article><small>Migration 就绪度</small><strong>{{ migration.readiness || '-' }}</strong></article>
      <article><small>Migration 执行授权</small><strong>{{ migration.authorization || '-' }}</strong></article>
      <article><small>正式 Migration</small><strong>{{ migration.applyStatus || '-' }}</strong></article>
      <article><small>Schema</small><strong>{{ migration.schemaAvailability || '-' }}</strong></article>
      <article><small>正式主数据写入</small><strong>{{ auth.formalMasterDataWrite || '-' }}</strong></article>
    </section>

    <section class="card">
      <div class="section-title"><h2>唯一正式模型</h2><span>{{ facts.factSource || '-' }}</span></div>
      <table>
        <thead><tr><th>领域</th><th>Canonical Model</th></tr></thead>
        <tbody><tr v-for="(value, key) in facts.canonicalModels || {}" :key="key"><td>{{ key }}</td><td>{{ value }}</td></tr></tbody>
      </table>
    </section>

    <section class="card">
      <div class="section-title"><h2>正式数据库保护</h2><span>未授权写入按钮保持禁用</span></div>
      <div class="counts"><article v-for="(value, key) in facts.recordCounts || {}" :key="key"><small>{{ key }}</small><strong>{{ value }}</strong></article></div>
      <p v-if="facts.missingWave2Tables?.length" class="notice">Wave 2 Migration 尚未应用到正式数据库：{{ facts.missingWave2Tables.join('、') }}</p>
    </section>

    <section class="card">
      <h2>工程能力</h2>
      <div class="capabilities"><span v-for="(value, key) in facts.capabilities || {}" :key="key" :class="value ? 'pass' : 'hold'">{{ key }} · {{ value ? 'GO' : 'HOLD' }}</span></div>
    </section>

    <section class="card">
      <h2>架构裁决</h2>
      <ol><li v-for="item in facts.architectureDecisions || []" :key="item">{{ item }}</li></ol>
    </section>

    <section class="card protected">
      <h2>受控执行边界</h2>
      <p>Production Migration、BOM、Routing、WorkCenter、Product Template 与 Configured Product 正式写入均未授权。</p>
      <button type="button" disabled>正式写入（未授权）</button>
    </section>
    <p v-if="error" class="error">{{ error }}</p>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { pdeApi } from '@/api/pde.js'

const facts = ref({})
const error = ref('')
const auth = computed(() => facts.value.authorization || {})
const migration = computed(() => facts.value.migrationState || {})

async function load() {
  error.value = ''
  try {
    const response = await pdeApi.wave2ManufacturingFoundation()
    if (response?.success === false) {
      throw new Error(response?.error?.message || 'Wave 2 服务端事实读取失败')
    }
    facts.value = response?.data?.data ?? response?.data ?? response ?? {}
  } catch (exception) {
    facts.value = {}
    error.value = exception?.response?.data?.message || exception?.message || 'Wave 2 服务端事实读取失败'
  }
}

onMounted(load)
</script>

<style scoped>
.wave2-page { display:grid; gap:18px; padding:24px; background:#f2f6fb; color:#172033; }
.hero,.card,.summary { background:#fff; border:1px solid #dbe4f0; border-radius:16px; padding:20px; }
.hero { display:flex; justify-content:space-between; align-items:center; gap:24px; background:linear-gradient(130deg,#18396f,#315ec4); color:#fff; }
.hero p { margin:0; opacity:.8; font-weight:700; letter-spacing:.04em; }
.hero h1 { margin:7px 0; }
button { border:1px solid #fff; border-radius:9px; padding:10px 16px; background:#fff; color:#204a9d; font-weight:700; cursor:pointer; }
button:disabled { border-color:#d0d7e2; background:#e7ebf1; color:#7b8493; cursor:not-allowed; }
.summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.summary article,.counts article { background:#f5f8fd; border-radius:10px; padding:14px; }
small,strong { display:block; }
strong { margin-top:7px; overflow-wrap:anywhere; }
.section-title { display:flex; justify-content:space-between; align-items:center; gap:18px; }
table { width:100%; border-collapse:collapse; }
th,td { padding:11px 12px; border-bottom:1px solid #e4eaf2; text-align:left; }
.counts { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:10px; }
.capabilities { display:flex; flex-wrap:wrap; gap:9px; }
.capabilities span { border-radius:999px; padding:7px 11px; font-size:13px; font-weight:700; }
.pass { background:#e8f7ef; color:#176b41; }.hold { background:#fff3dd; color:#885b0a; }
.notice { padding:12px; border-radius:9px; background:#fff5df; color:#7a5205; }
.protected { border-color:#e7bf78; }.error { color:#b42318; }
@media (max-width:900px) { .summary { grid-template-columns:1fr 1fr; }.hero { align-items:flex-start; flex-direction:column; } }
</style>
