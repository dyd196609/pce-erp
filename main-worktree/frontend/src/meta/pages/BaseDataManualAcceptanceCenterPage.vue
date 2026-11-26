<template>
  <main class="acceptance-center" data-acceptance-id="base-data-manual-acceptance-center" data-read-only="true">
    <FoundationBreadcrumb />
    <section class="hero">
      <div><p>基础数据 · 第1–6组</p><h1>基础数据人工验收中心</h1><span>来源事实、正式数据、缺失、冲突与模拟状态一次展开；本页只作就绪看板，不保存、不导入。</span></div>
      <strong>只读 · 写入 0</strong>
    </section>

    <section v-if="loading" class="panel">正在读取正式数据现实……</section>
    <section v-else-if="error" class="panel error">{{ error }}</section>
    <template v-else>
      <section class="headline-grid">
        <article><span>基础数据系统状态</span><strong>{{ statusLabel(facts.baseDataSystem) }}</strong></article>
        <article class="danger"><span>基础数据现实状态</span><strong>{{ statusLabel(facts.baseDataReality) }}</strong></article>
        <article><span>正式业务写入</span><strong>{{ facts.productionBusinessMasterDataWriteCount }}</strong></article>
        <article class="danger"><span>用户已验收</span><strong>否</strong></article>
      </section>

      <section class="panel matrix">
        <header><div><h2>第1–6组状态矩阵</h2><p>已开发、数据存在、用户已验收三层分开判定。</p></div></header>
        <div class="table-wrap"><table><thead><tr><th>组别</th><th>范围</th><th>已开发</th><th>数据存在</th><th>用户已验收</th><th>就绪状态</th></tr></thead>
          <tbody><tr v-for="group in facts.groups" :key="group.group"><td><strong>{{ groupLabel(group) }}</strong></td><td>{{ group.name }}</td><td>{{ yesNo(group.developed) }}</td><td>{{ statusLabel(group.dataPresent) }}</td><td>{{ yesNo(group.userValidated) }}</td><td><span class="pill danger">{{ statusLabel(group.ready) }}</span></td></tr></tbody>
        </table></div>
      </section>

      <section v-for="group in facts.groups" :key="group.group" class="panel group-panel">
        <header><div><p>基础数据分组</p><h2>{{ groupLabel(group) }}</h2></div><strong>{{ statusLabel(group.ready) }}</strong></header>
        <div class="table-wrap"><table><thead><tr>
          <th>模块</th><th>来源</th><th>正式数据</th><th>缺失</th><th>冲突</th><th>模拟数据</th><th>已开发</th><th>数据存在</th><th>用户已验收</th><th>就绪状态</th><th>验收/维护入口</th>
        </tr></thead><tbody><tr v-for="item in group.modules" :key="item.code">
          <td><strong>{{ moduleLabel(item) }}</strong></td><td>{{ item.source }}<small>{{ countLabel(item.sourceRecordCount) }}</small></td><td>{{ item.formalData }}</td><td>{{ item.missing }}</td><td>{{ item.conflict }}</td><td>{{ item.simulatedCount }}</td><td>{{ yesNo(item.developed) }}</td><td>{{ statusLabel(item.dataPresent) }}</td><td>{{ yesNo(item.userValidated) }}</td><td><span class="pill danger">{{ statusLabel(item.ready) }}</span></td>
          <td><div v-if="moduleActions(group, item).length" class="module-actions"><router-link v-for="action in moduleActions(group, item)" :key="action.key" :class="{ prominent: action.prominent }" :to="action.route">{{ action.label }}</router-link></div><span v-else>尚无可用入口</span></td>
        </tr></tbody></table></div>
      </section>

      <section class="panel simulation">
        <header><div><h2>测试模拟辅助字段预览</h2><p>仅展示可模拟格式；不会覆盖来源真实值，也不会写入正式库。</p></div><strong>仅预览</strong></header>
        <div class="table-wrap"><table><thead><tr><th>对象</th><th>字段</th><th>拟值</th><th>Provenance</th></tr></thead><tbody><tr v-for="row in facts.simulatedDataPreview" :key="`${row.entity}-${row.field}`"><td>{{ row.entity }}</td><td>{{ row.field }}</td><td>{{ row.previewValue }}</td><td><span class="pill warn">{{ row.provenance }}</span></td></tr></tbody></table></div>
        <ul><li v-for="rule in facts.simulationRules" :key="rule">{{ rule }}</li></ul>
      </section>

      <section class="panel deployment">
        <header><div><h2>计划模块部署现实</h2><p>本轮不启用生产计划。</p></div><strong>未部署</strong></header>
        <div class="headline-grid inner"><article><span>productionEnabled</span><strong>{{ facts.planningDeployment.productionEnabled }}</strong></article><article><span>planning.0005 applied</span><strong>{{ facts.planningDeployment.migration0005Applied }}</strong></article><article><span>Demand</span><strong>{{ facts.planningDeployment.demandRecords }}</strong></article><article><span>MPS / MRP</span><strong>{{ facts.planningDeployment.mpsRecords }} / {{ facts.planningDeployment.mrpRecords }}</strong></article></div>
        <router-link class="primary-link" to="/planning/production-batch-foundation">进入 Production Batch / GENERAL / KITTING 预览</router-link>
      </section>
    </template>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { enterpriseMasterDataApi } from '@/api/enterpriseMasterData.js'
import FoundationBreadcrumb from '@/meta/components/FoundationBreadcrumb.vue'
import { stateManager } from '@/meta/runtime/stateManager.js'
import { getFoundationGroupLabel, getFoundationModuleActions, getFoundationModuleLabel } from '@/meta/master-data/foundationNavigationRegistry.js'
const facts = ref({ groups: [], planningDeployment: {}, simulatedDataPreview: [], simulationRules: [] })
const loading = ref(true)
const error = ref('')
const yesNo = value => value ? '是' : '否'
const statusLabels = { YES: '是', NO: '否', READY: '已就绪', NOT_READY: '未就绪', PARTIAL: '部分具备', PRESENT: '已具备', MISSING: '缺失', VALIDATED: '已验收', NOT_VALIDATED: '未验收', DEVELOPED: '已开发', NOT_DEVELOPED: '未开发', UNKNOWN: '未知', NOT_DEPLOYED: '未部署' }
const statusLabel = value => statusLabels[String(value)] || String(value ?? '-')
const countLabel = value => value === null || value === undefined ? '来源数量：未知' : `来源数量：${value}`
const groupLabel = group => getFoundationGroupLabel(group.group)
const moduleLabel = item => getFoundationModuleLabel(item.code, item.module)
const moduleActions = (group, item) => getFoundationModuleActions(group.group, item, stateManager.snapshot().role)
async function load() {
  try { const response = await enterpriseMasterDataApi.baseDataReadiness(); facts.value = response?.data ?? response }
  catch (exception) { error.value = exception?.message || '基础数据现实读取失败' }
  finally { loading.value = false }
}
onMounted(load)
</script>

<style scoped>
.acceptance-center{padding:24px;color:#17233a;box-sizing:border-box}.hero,.panel{border:1px solid #dbe3ef;border-radius:16px;background:#fff;padding:21px 23px;margin-bottom:18px}.hero{display:flex;justify-content:space-between;align-items:center;gap:20px;color:#fff;background:linear-gradient(135deg,#143969,#315bcf)}.hero h1,.hero p,.hero span,.panel h2,.panel p{margin:0}.hero h1{margin:5px 0 8px}.hero>strong{border:1px solid #aac4ff;border-radius:999px;padding:9px 13px;white-space:nowrap}.headline-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:13px;margin-bottom:18px}.headline-grid article{display:grid;gap:7px;padding:16px;border:1px solid #dfe7f2;border-left:4px solid #315bcf;border-radius:12px;background:#fff}.headline-grid article.danger{border-left-color:#c9352b}.headline-grid strong{font-size:20px}.panel header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:13px}.group-panel header>div>p{font-size:12px;color:#61708a}.table-wrap{overflow:auto;border:1px solid #e0e7f1;border-radius:10px}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:10px;border-bottom:1px solid #e8edf5;text-align:left;vertical-align:top;min-width:105px}th{position:sticky;top:0;background:#edf2f8;z-index:1;white-space:nowrap}td:nth-child(2),td:nth-child(4),td:nth-child(5){min-width:220px}td small{display:block;margin-top:5px;color:#687790}.pill{display:inline-block;padding:3px 8px;border-radius:999px;white-space:nowrap}.pill.danger{background:#feeceb;color:#a5221a}.pill.warn{background:#fff2d5;color:#865700}a{color:#2457ba;font-weight:700}.simulation{background:#fffaf0}.simulation ul{line-height:1.8}.inner{margin:14px 0}.primary-link{display:inline-block;padding:10px 15px;border-radius:9px;background:#315bcf;color:#fff;text-decoration:none}.error{color:#a5221a}@media(max-width:760px){.acceptance-center{padding:12px}.hero,.panel header{align-items:flex-start;flex-direction:column}}
.module-actions{display:flex;flex-wrap:wrap;gap:7px;min-width:170px}.module-actions a{display:inline-block;padding:6px 9px;border:1px solid #b9c8e3;border-radius:8px;background:#f7f9fd;text-decoration:none;white-space:nowrap}.module-actions a.prominent{border-color:#17676c;background:#17676c;color:#fff;box-shadow:0 3px 10px rgba(23,103,108,.22)}
</style>
