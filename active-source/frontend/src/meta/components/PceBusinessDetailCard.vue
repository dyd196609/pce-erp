<template>
  <article
    class="business-detail-card"
    data-acceptance-id="pce-business-detail-card"
    data-detail-view-mode="business_card"
  >
    <section v-if="detail.fields?.length" data-acceptance-id="master-data-business-fields">
      <h3>{{ detail.sectionTitle || '业务信息' }}</h3>
      <dl class="detail-grid">
        <div v-for="field in detail.fields" :key="field.label">
          <dt>{{ field.label }}</dt>
          <dd>{{ field.value ?? '-' }}</dd>
        </div>
      </dl>
    </section>

    <template v-else>
    <section>
      <h3>基础信息</h3>
      <dl class="detail-grid">
        <div><dt>编号</dt><dd>{{ detail.basicInformation?.number || '-' }}</dd></div>
        <div><dt>供应商</dt><dd>{{ detail.basicInformation?.supplier || '-' }}</dd></div>
        <div><dt>期间</dt><dd>{{ detail.basicInformation?.period || '-' }}</dd></div>
        <div><dt>来源单据</dt><dd>{{ detail.basicInformation?.sourceDocument || '-' }}</dd></div>
      </dl>
    </section>

    <section>
      <h3>金额信息</h3>
      <dl class="detail-grid">
        <div><dt>确认金额</dt><dd>{{ money(detail.amountInformation?.confirmedAmount) }}</dd></div>
        <div><dt>扣减金额</dt><dd>{{ money(detail.amountInformation?.deductionAmount) }}</dd></div>
        <div><dt>最终金额</dt><dd>{{ money(detail.amountInformation?.finalAmount) }}</dd></div>
      </dl>
    </section>

    <section data-acceptance-id="business-source-chain">
      <h3>业务来源链</h3>
      <div class="source-chain">
        <template v-for="(item, index) in detail.businessSourceChain || []" :key="item.label">
          <div class="source-node">
            <strong>{{ item.label }}</strong>
            <span>{{ item.count }} 项</span>
            <small>{{ references(item.references) }}</small>
          </div>
          <b v-if="index < (detail.businessSourceChain || []).length - 1">↓</b>
        </template>
      </div>
    </section>

    <section>
      <h3>当前状态</h3>
      <span class="status-pill">{{ detail.currentStatus || '-' }}</span>
    </section>

    <section data-acceptance-id="business-state-history">
      <h3>状态历史</h3>
      <ol v-if="detail.stateHistory?.length" class="timeline">
        <li v-for="item in detail.stateHistory" :key="`${item.version}-${item.timestamp}`">
          <div>
            <strong>{{ item.beforeStatus }} → {{ item.afterStatus }}</strong>
            <span>{{ displayTime(item.timestamp) }}</span>
          </div>
          <p>{{ item.operator }} · {{ item.reason }}</p>
        </li>
      </ol>
      <p v-else class="empty">暂无状态变化记录</p>
    </section>

    <section data-acceptance-id="business-operation-records">
      <h3>操作记录</h3>
      <ol v-if="detail.operationRecords?.length" class="timeline">
        <li v-for="item in detail.operationRecords" :key="item.actionNo">
          <div>
            <strong>{{ item.operator }} · {{ item.actionLabel }}</strong>
            <span>{{ displayTime(item.timestamp) }}</span>
          </div>
          <p>{{ item.roleLabel }} · {{ item.beforeStatus }} → {{ item.afterStatus }}</p>
        </li>
      </ol>
      <p v-else class="empty">暂无业务操作记录</p>
    </section>
    </template>
  </article>
</template>

<script setup>
defineProps({
  detail: {
    type: Object,
    required: true,
  },
})

function money(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  return Number.isFinite(number)
    ? number.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : String(value)
}

function references(values) {
  return Array.isArray(values) && values.length ? values.join('、') : '无来源记录'
}

function displayTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.business-detail-card { display:grid; gap:18px; color:#1f2937; }
.business-detail-card section { padding:16px; border:1px solid #dbe4ee; border-radius:12px; background:#fff; }
h3 { margin:0 0 12px; color:#16243a; }
.detail-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:0; }
.detail-grid div { padding:11px 12px; border-radius:8px; background:#f6f8fb; }
dt { color:#64748b; font-size:13px; }
dd { margin:5px 0 0; font-weight:700; overflow-wrap:anywhere; }
.source-chain { display:grid; justify-items:stretch; gap:7px; }
.source-chain > b { justify-self:center; color:#64748b; }
.source-node { display:grid; grid-template-columns:140px 70px 1fr; gap:12px; padding:10px 12px; border-radius:9px; background:#eff6ff; }
.source-node span,.source-node small { color:#475569; overflow-wrap:anywhere; }
.status-pill { display:inline-flex; padding:7px 13px; border-radius:999px; background:#e0f2fe; color:#075985; font-weight:700; }
.timeline { display:grid; gap:10px; margin:0; padding:0 0 0 18px; }
.timeline li { padding:0 0 10px 8px; border-bottom:1px solid #e5e7eb; }
.timeline li div { display:flex; justify-content:space-between; gap:12px; }
.timeline span,.timeline p,.empty { color:#64748b; }
.timeline p { margin:6px 0 0; }
@media (max-width:700px) {
  .detail-grid { grid-template-columns:1fr; }
  .source-node { grid-template-columns:1fr; }
  .timeline li div { display:grid; }
}
</style>
