<template>
  <main class="legacy-diagnostic" data-page-code="foundation-legacy-data-diagnostic" data-page-type="DIAGNOSTIC_PAGE" data-formality="NON-FORMAL" data-maintenance-capability="READ_ONLY" data-server-write-count="0" data-localstorage-write-count="0">
    <section class="warning">
      <div><p>LEGACY / NON-FORMAL / READ-ONLY</p><h1>遗留本地数据检查器</h1><span>此页面只检查并导出历史浏览器数据，不承担正式业务事实、CRUD 或迁移。</span></div>
      <router-link to="/foundation">返回企业基础资料</router-link>
    </section>
    <section class="protection">
      <strong>保护规则</strong>
      <span>不删除、不清空、不覆盖、不自动迁移、不写入 Server。</span>
      <button type="button" @click="inspect">重新只读检查</button>
    </section>
    <section class="matrix">
      <table>
        <thead><tr><th>Legacy Key</th><th>存在</th><th>可解析</th><th>记录数量</th><th>分类</th><th>正式性</th><th>只读动作</th></tr></thead>
        <tbody>
          <tr v-for="item in results" :key="item.key"><td>{{ item.key }}</td><td>{{ item.exists ? '是' : '否' }}</td><td>{{ item.parseable ? '是' : item.exists ? '否' : 'N/A' }}</td><td>{{ item.recordCount ?? '未知' }}</td><td>{{ item.classification }}</td><td>NON-FORMAL</td><td><button type="button" :disabled="!item.exists" @click="exportLegacy(item.key)">导出原始 JSON</button></td></tr>
        </tbody>
      </table>
    </section>
    <section class="boundaries"><h2>禁止能力</h2><p>新增=0　编辑=0　保存=0　删除=0　启停=0　正式导入=0　正式编码=0　Server合并=0</p><p>无法自动确认的数据保持 UNKNOWN；USER_LOCAL_ONLY、CONFLICTING、UNKNOWN 均需另立正式迁移任务并由用户确认。</p></section>
  </main>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { inspectLegacyFoundationStorage } from '@/meta/runtime/legacyFoundationDiagnostic.js'
const results = ref([])
function inspect() {
  results.value = inspectLegacyFoundationStorage(window.localStorage)
}
function exportLegacy(key) {
  const raw = window.localStorage.getItem(key)
  if (raw === null) return
  const blob = new Blob([raw], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${key}-NON-FORMAL-READ-ONLY-export.json`
  anchor.click()
  URL.revokeObjectURL(url)
}
onMounted(inspect)
</script>

<style scoped>
.legacy-diagnostic{width:100%;max-width:100%;min-width:0;padding:24px;overflow-x:hidden;box-sizing:border-box;color:#17233a}.warning,.protection,.matrix,.boundaries{border:1px solid #e5c07b;border-radius:14px;background:#fffaf0;padding:20px 22px;margin-bottom:16px}.warning,.protection{display:flex;justify-content:space-between;align-items:center;gap:20px}.warning p,.warning h1,.warning span{margin:0}.warning p{color:#9a5b00;font-weight:800;letter-spacing:.05em}.warning h1{margin:5px 0 8px}.warning a,.protection button,.matrix button{border:1px solid #9a5b00;border-radius:8px;padding:8px 12px;background:#fff;color:#7a4800;text-decoration:none;font-weight:700}.matrix{overflow-x:auto}.matrix table{width:100%;min-width:980px;border-collapse:collapse}.matrix th,.matrix td{padding:11px;border-bottom:1px solid #ead9b7;text-align:left}.boundaries h2,.boundaries p{margin:0}.boundaries p{margin-top:8px;line-height:1.6}@media(max-width:760px){.legacy-diagnostic{padding:14px}.warning,.protection{align-items:flex-start;flex-direction:column}}
</style>
