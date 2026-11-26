<template>
  <main class="comparison-page" data-acceptance-id="base-data-comparison-preview" data-read-only="true">
    <FoundationBreadcrumb group="第1组 客户、供应商与计量单位" :module="title" show-return />
    <section class="hero">
      <div>
        <p class="eyebrow">Enterprise Master Data · Batch 1</p>
        <h1>{{ title }}只读对照预览</h1>
        <p>真实来源 Excel → 当前正式数据 → 精确匹配 / 缺失 / 冲突。不会保存、导入或自动映射。</p>
      </div>
      <span class="readonly">READ ONLY · WRITE 0</span>
    </section>

    <nav class="tabs" aria-label="Batch 1 对照页">
      <router-link v-for="item in tabs" :key="item.entity" :to="`/foundation/base-data-comparison/${item.entity}`">
        {{ item.label }}
      </router-link>
    </nav>

    <section v-if="loading" class="panel">正在读取正式事实并执行精确对照……</section>
    <section v-else-if="error" class="panel error">{{ error }}</section>
    <template v-else>
      <section class="source panel">
        <div>
          <span>来源</span>
          <strong>{{ sourceLabel }}</strong>
        </div>
        <div><span>哈希</span><strong class="hash">{{ sourceHash }}</strong></div>
        <div><span>正式模型</span><strong>{{ formalModel }}</strong></div>
        <div><span>用户已验收</span><strong>{{ summary.userValidated ? '是' : '否' }}</strong></div>
      </section>

      <section class="summary">
        <article><span>来源记录</span><strong>{{ summary.sourceRecordCount }}</strong></article>
        <article><span>有效来源</span><strong>{{ summary.validSourceCount }}</strong></article>
        <article><span>正式记录</span><strong>{{ summary.formalRecordCount }}</strong></article>
        <article class="good"><span>精确匹配</span><strong>{{ summary.exactMatchCount }}</strong></article>
        <article class="warn"><span>未匹配来源</span><strong>{{ summary.unmatchedSourceCount }}</strong></article>
        <article class="warn"><span>不属于当前来源</span><strong>{{ summary.formalOutsideCurrentSourceCount }}</strong></article>
        <article class="danger"><span>冲突</span><strong>{{ summary.conflictCount }}</strong></article>
        <article class="danger"><span>正式同名组</span><strong>{{ summary.formalDuplicateGroupCount }}</strong></article>
        <article class="danger"><span>无效来源</span><strong>{{ summary.invalidSourceCount }}</strong></article>
        <article><span>测试/历史明确标记</span><strong>{{ summary.explicitTestHistoricalCount }}</strong></article>
        <article><span>就绪状态</span><strong>{{ summary.readiness }}</strong></article>
      </section>

      <section class="panel">
        <header>
          <div>
            <h2>来源逐条对照</h2>
            <p>仅精确匹配；不使用简称、模糊名称或推断映射。</p>
          </div>
          <span>{{ rows.length }} 条</span>
        </header>
        <div class="table-wrap">
          <table>
            <thead><tr>
              <th>来源行/序号</th><th>来源名称/计量单位</th><th v-if="isUom">业务语义与例子</th>
              <th>正式编码</th><th>正式名称</th><th>启用</th><th>匹配状态</th><th>拟处理</th><th>说明</th>
            </tr></thead>
            <tbody>
              <tr v-for="(row, index) in rows" :key="`${row.sourceRow || row.sourceValue}-${index}`">
                <td>{{ row.sourceRow ? `${row.sourceRow} / ${row.sequence || '-'}` : row.occurrences }}</td>
                <td><strong>{{ row.sourceName || row.sourceValue || '（空名称）' }}</strong></td>
                <td v-if="isUom" class="context">{{ uomContext(row) }}</td>
                <td>{{ row.formalMatch?.formalCode || row.candidateFormal?.formalCode || '-' }}</td>
                <td>{{ row.formalMatch?.formalName || row.candidateFormal?.formalName || '-' }}</td>
                <td>{{ row.formalMatch ? (row.formalMatch.enabled ? '启用' : '停用') : '-' }}</td>
                <td><span :class="statusClass(row.matchStatus)">{{ statusLabel(row.matchStatus) }}</span></td>
                <td>{{ actionLabel(row.proposedAction) }}</td>
                <td class="reason">{{ row.decisionReason }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <header>
          <div><h2>正式库中不属于当前整木来源的记录</h2><p>单独展示，不计作当前来源匹配；“测试/历史”只按明确标记识别，不擅自推断。</p></div>
          <span>{{ formalOnlyRows.length }} 条</span>
        </header>
        <div class="table-wrap formal-only">
          <table>
            <thead><tr><th>正式编码</th><th>正式名称</th><th>来源/性质</th><th>启用</th><th>测试/历史明确标记</th></tr></thead>
            <tbody><tr v-for="row in formalOnlyRows" :key="row.id">
              <td>{{ row.formalCode }}</td><td>{{ row.formalName }}</td><td>{{ row.dataOrigin }}</td>
              <td>{{ row.enabled ? '启用' : '停用' }}</td><td>{{ row.testHistorical ? '是' : '否/未明确' }}</td>
            </tr></tbody>
          </table>
        </div>
      </section>

      <section class="boundary panel">
        <strong>边界：SOURCE → CURRENT FORMAL DATA → DIFFERENCE → PREVIEW → USER VALIDATION</strong>
        <span>Production business master-data write = {{ facts.productionBusinessMasterDataWriteCount }}</span>
      </section>
    </template>
  </main>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import FoundationBreadcrumb from '@/meta/components/FoundationBreadcrumb.vue'

const props = defineProps({ entity: { type: String, required: true } })
const tabs = [
  { entity: 'customers', label: '客户 / 经销商' },
  { entity: 'suppliers', label: '供应商' },
  { entity: 'uoms', label: 'UOM' },
]
const facts = ref({})
const loading = ref(false)
const error = ref('')
const rows = computed(() => facts.value.rows || [])
const formalOnlyRows = computed(() => facts.value.formalOutsideCurrentSourceRows || [])
const summary = computed(() => facts.value.summary || {})
const isUom = computed(() => props.entity === 'uoms')
const title = computed(() => tabs.find(item => item.entity === props.entity)?.label || props.entity)
const formalModel = computed(() => ({ customers: 'sales.Customer', suppliers: 'procurement.Supplier', uoms: 'masterdata.UnitOfMeasure' }[props.entity]))
const sourceLabel = computed(() => {
  const source = facts.value.source || {}
  if (source.fileName) return `${source.fileName} / ${source.sheet}`
  return (source.sourceFiles || []).map(item => `${item.fileName} / ${item.sheet}`).join('；')
})
const sourceHash = computed(() => {
  const source = facts.value.source || {}
  if (source.sha256) return source.sha256
  return (source.sourceFiles || []).map(item => `${item.fileName}: ${item.sha256}`).join('；')
})

const statusLabels = {
  EXACT_MATCH: '精确匹配', NO_MATCH: '缺失', CONFLICT: '冲突',
  INCOMPLETE_SOURCE: '来源不完整', MANUAL_DECISION_REQUIRED: '待人工裁决',
  USER_DECISION_MAPPED: '用户裁决：映射', USER_DECISION_NOT_UOM: '用户裁决：非UOM',
}
const actionLabels = {
  REUSE_EXISTING: '拟复用', CREATE_OR_MANUAL_MATCH_REVIEW: '拟新增/人工匹配',
  MANUAL_MATCH_REQUIRED: '人工匹配', SOURCE_CORRECTION_REQUIRED: '修正来源',
  NO_AUTOMATIC_MAPPING: '不自动映射',
  CALCULATION_BASIS_AREA: 'calculation_basis=AREA',
}
const statusLabel = value => statusLabels[value] || value
const actionLabel = value => actionLabels[value] || value
const statusClass = value => value === 'EXACT_MATCH' ? 'pill good' : value === 'NO_MATCH' ? 'pill warn' : 'pill danger'
const uomContext = row => (row.examples || []).map(example => {
  const object = example.materialName || example.operationName || '-'
  const basis = example.quantityBasis ? `；核算口径=${example.quantityBasis}` : ''
  const category = example.materialCategory ? `；分类=${example.materialCategory}` : ''
  return `${example.sourceFile} 第${example.sourceRow}行：${object}${basis}${category}`
}).join(' ｜ ')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const response = await enterpriseMasterDataApi.baseDataComparison(props.entity)
    facts.value = response?.data ?? response
  } catch (exception) {
    error.value = exception?.message || '对照事实读取失败'
  } finally {
    loading.value = false
  }
}
watch(() => props.entity, load, { immediate: true })
</script>

<style scoped>
.comparison-page{padding:24px;color:#18243a;box-sizing:border-box}.hero,.panel{background:#fff;border:1px solid #dce4f0;border-radius:16px;padding:20px 22px;margin-bottom:18px}.hero{display:flex;justify-content:space-between;gap:20px;align-items:center;background:linear-gradient(135deg,#183d73,#315bcf);color:#fff}.hero h1,.hero p,.panel h2,.panel p{margin:0}.hero h1{margin:5px 0 8px}.eyebrow{font-size:12px;letter-spacing:.08em}.readonly{padding:9px 12px;border:1px solid #a9c2ff;border-radius:999px;white-space:nowrap}.tabs{display:flex;gap:10px;margin-bottom:18px}.tabs a{padding:10px 15px;border-radius:10px;background:#edf2ff;color:#244a9b;text-decoration:none}.tabs a.router-link-active{background:#315bcf;color:#fff}.source,.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.source div,.summary article{display:grid;gap:6px;padding:13px;border-radius:11px;background:#f6f8fc}.source span,.summary span{font-size:12px;color:#627089}.hash{font-size:10px;word-break:break-all}.summary{margin-bottom:18px}.summary article{border-left:4px solid #315bcf}.summary article.good{border-left-color:#178454}.summary article.warn{border-left-color:#d98b00}.summary article.danger{border-left-color:#c9362b}.summary strong{font-size:23px}.panel header{display:flex;justify-content:space-between;gap:18px;align-items:center;margin-bottom:13px}.table-wrap{overflow:auto;max-height:620px;border:1px solid #e1e7f0;border-radius:10px}.formal-only{max-height:420px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e8edf5;text-align:left;vertical-align:top}th{position:sticky;top:0;background:#edf2f8;z-index:1;white-space:nowrap}.reason,.context{min-width:260px;white-space:normal}.pill{display:inline-block;padding:3px 8px;border-radius:999px;white-space:nowrap}.pill.good{background:#e6f6ef;color:#126b45}.pill.warn{background:#fff3d6;color:#8b5a00}.pill.danger{background:#feeceb;color:#a6231b}.boundary{display:flex;justify-content:space-between;gap:16px;background:#fff8e7}.error{color:#a6231b}@media(max-width:760px){.comparison-page{padding:12px}.hero,.boundary,.panel header{align-items:flex-start;flex-direction:column}}
</style>
