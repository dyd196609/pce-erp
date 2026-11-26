<template>
  <main class="foundation-portal" data-page-code="enterprise-foundation-operator-portal" data-page-type="OPERATOR_PAGE" data-fact-source="server" data-legacy-formal-store-dependency="0" data-business-localstorage-write="0">
    <section class="hero">
      <div><p class="eyebrow">Enterprise Foundation Operator Portal</p><h1>企业基础资料</h1><p>统一进入各领域已有的服务端正式维护能力；门户不拥有第二套 Model、Store 或写服务。</p></div>
      <button type="button" :disabled="loading" @click="loadStatistics">{{ loading ? '正在刷新' : '刷新服务端统计' }}</button>
    </section>

    <section class="facts" data-acceptance-id="FOUNDATION_SERVER_FACT_SUMMARY">
      <header><div><h2>服务端正式事实</h2><p>统计只来自 MasterDataStatisticsRuntime；legacy localStorage 不参与加载、补值或覆盖。</p></div><strong :class="{ failed: loadStatus === 'read_failed' }">{{ loadStatusLabel }}</strong></header>
      <div class="fact-grid">
        <article v-for="item in summaryCards" :key="item.field"><span>{{ item.title }}</span><strong>{{ item.value }}</strong><small>{{ item.source }}</small></article>
      </div>
      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
    </section>

    <section class="validation-entry" data-acceptance-id="FOUNDATION_WAVE1_PREVIEW_ENTRY">
      <div>
        <p class="eyebrow">Validation Page · VALIDATION ACTION</p>
        <h2>制造基础数据导入预览</h2>
        <p>选择已批准的05半成品板材、10采购物料或01工序来源，查看候选、单位和异常；预览不会写入正式主数据。</p>
      </div>
      <router-link to="/foundation/import-preview">进入只读导入预览</router-link>
    </section>

    <section class="validation-entry acceptance" data-acceptance-id="BASE_DATA_MANUAL_ACCEPTANCE_ENTRY">
      <div>
        <p class="eyebrow">GROUP 1–6 · MANUAL VALIDATION</p>
        <h2>基础数据人工验收中心</h2>
        <p>查看来源、正式数据、缺失、冲突、模拟与三层状态；进入制造维护和 Production Batch 排程预览。</p>
      </div>
      <router-link to="/foundation/manual-acceptance-center">开始逐模块人工验收</router-link>
    </section>

    <nav class="foundation-group-nav" aria-label="企业基础资料页内分组">
      <strong>页内分组</strong>
      <button v-for="group in foundationEntryGroups" :key="group.key" type="button" @click="scrollToGroup(group.key)">{{ group.label }}</button>
    </nav>

    <section v-for="group in foundationEntryGroups" :id="`foundation-group-${group.key}`" :key="group.key" class="entry-group" :data-foundation-group="group.key">
      <header><h2>{{ group.label }}</h2><p>{{ group.description }}</p></header>
      <div class="entry-grid">
        <router-link
          v-for="item in group.entries"
          :key="item.objectCode"
          :to="item.routeName ? { name: item.routeName } : item.route"
          :data-navigation-key="item.navigationKey"
          :data-page-key="item.pageKey"
          :data-target-route="item.route"
          :class="{ 'acceptance-ready-entry': item.acceptanceAvailable }"
        ><strong>{{ item.displayName }}</strong><b v-if="item.acceptanceAvailable">本模块含来源人工验收</b><span>{{ item.description }}</span><small>{{ item.route }}</small></router-link>
      </div>
    </section>

    <section class="diagnostics" data-acceptance-id="FOUNDATION_DIAGNOSTIC_ENTRIES">
      <div><p class="eyebrow">Diagnostic / Gate</p><h2>诊断与历史数据保护</h2><p>诊断入口不是 Operator CRUD，不生成经营正式事实。</p></div>
      <nav><router-link to="/pde/a1-foundation">生产基础完整性检查</router-link><router-link to="/foundation/legacy-diagnostic">遗留本地数据只读检查</router-link></nav>
    </section>
  </main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { foundationEntryGroups } from '@/meta/master-data/foundationEntryUnificationRegistry.js'
import { loadMasterDataStatisticsRuntime } from '@/meta/providers/masterDataStatisticsRuntimeProvider.js'

const statistics = ref(null)
const loading = ref(false)
const loadStatus = ref('loading')
const errorMessage = ref('')
const loadStatusLabel = computed(() => ({ loading: '加载中', loaded: 'SERVER / LOADED', read_failed: 'SERVER / READ_FAILED' }[loadStatus.value] || '未知'))
const summaryCards = computed(() => {
  const runtime = statistics.value
  const item = (field, title) => ({ field, title, value: runtime ? runtime[field] : '—', source: runtime?.countSources?.[field] || '等待服务端事实' })
  return [item('materialCount', '物料档案'), item('supplierCount', '供应商档案'), item('supplierMaterialRelationCount', '物料供应商关系'), item('supplierPriceCount', '供应商有效价格')]
})
async function loadStatistics() {
  loading.value = true
  errorMessage.value = ''
  try {
    statistics.value = await loadMasterDataStatisticsRuntime({ force: true })
    loadStatus.value = 'loaded'
  } catch (error) {
    statistics.value = null
    loadStatus.value = 'read_failed'
    errorMessage.value = error?.message || '企业基础资料服务端统计读取失败。'
  } finally { loading.value = false }
}
function scrollToGroup(groupKey) {
  document.getElementById(`foundation-group-${groupKey}`)?.scrollIntoView({ behavior: 'auto', block: 'start' })
}
onMounted(loadStatistics)
</script>

<style scoped>
.foundation-portal{width:100%;max-width:100%;min-width:0;padding:24px;overflow-x:hidden;color:#17233a;box-sizing:border-box}.hero,.facts,.validation-entry,.entry-group,.diagnostics{border:1px solid #d9e2f2;border-radius:16px;background:#fff;padding:22px 24px;margin-bottom:18px}.hero,.facts>header,.validation-entry,.diagnostics{display:flex;align-items:center;justify-content:space-between;gap:24px}.hero{background:linear-gradient(135deg,#173f79,#3157d5);color:#fff}.hero h1,.hero p,.validation-entry h2,.validation-entry p,.entry-group h2,.entry-group p,.facts h2,.facts p,.diagnostics h2,.diagnostics p{margin:0}.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;opacity:.78}.hero h1{margin:5px 0 8px;font-size:30px}.hero button{border:0;border-radius:10px;padding:11px 18px;color:#173f79;font-weight:700;cursor:pointer}.validation-entry{background:#fff8e7}.validation-entry h2{margin:5px 0 8px}.validation-entry>a{flex:0 0 auto;border-radius:10px;padding:11px 16px;background:#3157d5;color:#fff;text-decoration:none;font-weight:700}.fact-grid,.entry-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin-top:18px}.fact-grid article,.entry-grid a{min-width:0;border:1px solid #e2e9f5;border-radius:12px;padding:16px;background:#f8faff}.fact-grid article{display:grid;gap:5px}.fact-grid article strong{font-size:24px}.fact-grid small,.entry-grid small{color:#607089}.entry-group header p{margin-top:6px;color:#607089}.entry-grid a{display:grid;gap:7px;color:#17233a;text-decoration:none}.entry-grid a:hover{border-color:#3157d5;box-shadow:0 5px 16px rgba(49,87,213,.1)}.entry-grid a span{color:#46566f;line-height:1.55}.diagnostics nav{display:flex;gap:12px;flex-wrap:wrap}.diagnostics a{border:1px solid #3157d5;border-radius:9px;padding:9px 13px;color:#3157d5;text-decoration:none;font-weight:700}.failed,.error{color:#b42318}@media(max-width:760px){.foundation-portal{padding:14px}.hero,.facts>header,.validation-entry,.diagnostics{align-items:flex-start;flex-direction:column}}
.validation-entry.acceptance{background:#eef4ff}
.entry-grid a.acceptance-ready-entry{border-color:#17676c;background:#eef9f7}.entry-grid a.acceptance-ready-entry>b{width:max-content;border-radius:999px;padding:3px 8px;background:#17676c;color:#fff;font-size:11px}
.foundation-group-nav{position:sticky;top:0;z-index:3;display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:18px;padding:11px 14px;border:1px solid #d9e2f2;border-radius:12px;background:rgba(255,255,255,.96);box-shadow:0 4px 14px rgba(23,35,58,.07)}.foundation-group-nav strong{margin-right:4px}.foundation-group-nav button{border:1px solid #b9c8e3;border-radius:8px;padding:7px 11px;background:#f7f9fd;color:#2457ba;font-weight:700;cursor:pointer}.foundation-group-nav button:hover{border-color:#3157d5;background:#eef4ff}
</style>
