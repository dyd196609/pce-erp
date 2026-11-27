<template>
  <section aria-label="运营风险待办">
    <h2>运营风险待办</h2>
    <div class="evidence-toolbar">
      <el-button size="large" v-for="entry in kinds" :key="entry.id" :aria-pressed="kind === entry.id" :type="kind === entry.id ? 'primary' : 'default'"
        native-type="button" @click="switchKind(entry.id)">{{ entry.name }}</el-button>
      <el-button size="large" native-type="button" :disabled="waiting || saving" @click="load">刷新风险待办</el-button>
    </div>
    <p v-if="waiting" role="status">正在读取正式风险依据。</p>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="data">
      <p v-if="!data.items.length">当前页没有具备正式依据的风险记录。</p>
      <details v-for="item in data.items" :key="item.id" class="case">
        <summary>
          {{ item.source.no }} · {{ item.source.findingLabel }} · {{ item.statusLabel }}
        </summary>
        <p>责任岗位 {{ item.source.department }} · 原单 {{ item.source.orderNo }}</p>
        <p v-if="item.source.workOrderNo">工单 {{ item.source.workOrderNo }} · 工序 {{ item.source.operation }}</p>
        <p v-else>采购行 {{ item.source.lineId }} · 收货 {{ item.source.receiptNo }} · 物料 {{ item.source.material }}</p>
        <p v-if="item.sourceCurrent">原单当前状态 {{ item.source.statusLabel }}。{{ item.source.cause }}</p>
        <p v-else>当前依据待核，以下为受理时保存的正式证据。</p>
        <p v-if="item.source.scheduleDelay">
          {{ item.source.scheduleDelay.statusLabel }} · {{ item.source.scheduleDelay.reason }}
          冻结计划 {{ item.source.scheduleDelay.plannedAt }} · 正式开工 {{ item.source.scheduleDelay.actualAt }}
          · 开工记录 {{ item.source.scheduleDelay.startRecordId }}
        </p>
        <ul v-if="item.source.predecessors?.length">
          <li v-for="prior in item.source.predecessors" :key="prior.operationId">{{ prior.name }} · {{ prior.reason }}</li>
        </ul>
        <p v-if="item.source.quantity">
          检验 {{ item.source.quantity }} {{ item.source.unit }} · 合格 {{ item.source.qualified }} {{ item.source.unit }}
          · 不合格 {{ item.source.rejected }} {{ item.source.unit }}
        </p>
        <RouterLink :to="item.source.link">查看原始记录</RouterLink>
        <details class="evidence-disclosure" v-if="item.risk">
          <summary>查看办理历史</summary>
          <p>处理人 {{ item.risk.handler }}</p>
          <ol>
            <li v-for="entry in item.risk.history" :key="entry.at">
              {{ new Date(entry.at).toLocaleString('zh-CN') }} · {{ entry.actor }} · {{ entry.after.status || '已受理' }}
              · {{ entry.reason }} <span v-if="entry.after.evidence">· {{ entry.after.evidence }}</span>
            </li>
          </ol>
        </details>
        <div class="evidence-toolbar">
          <el-button size="large" v-for="action in item.action ? [item.action] : item.risk?.actions || []" :key="action.code"
            native-type="button" :disabled="saving" @click="select(item, action)">{{ action.label }}</el-button>
        </div>
        <form class="evidence-form evidence-subform" aria-label="运营风险办理" v-if="selected?.id === item.id" @submit.prevent="submit(item)">
          <label class="evidence-field evidence-field--choice" v-if="selected.action.type === 'receive'">指定处理人
            <select v-model="handlerId" required>
              <option value="" disabled>请选择</option>
              <option v-for="person in item.handlers" :key="person.id" :value="person.id">{{ person.name }}</option>
            </select>
          </label>
          <label class="evidence-field evidence-field--wide">办理说明
          <textarea v-model.trim="reason" required maxlength="300" rows="2"></textarea>
        </label>
          <label class="evidence-field evidence-field--full" v-if="selected.action.type !== 'receive'">原单据及处置／复核证据
            <textarea v-model.trim="evidence" required maxlength="1800" rows="3"></textarea>
          </label>
          <div class="evidence-toolbar evidence-form-actions">
            <el-button size="large" native-type="submit" type="primary" :disabled="saving">提交</el-button>
            <el-button size="large" native-type="button" :disabled="saving" @click="selected = null">取消</el-button>
          </div>
        </form>
      </details>
      <div class="evidence-toolbar evidence-pagination" role="group" aria-label="风险来源分页">
        <el-button size="large" native-type="button" :disabled="page === 1 || saving" @click="changePage(page - 1)">上一页</el-button>
        <span>来源第 {{ page }} 页</span>
        <el-button size="large" native-type="button" :disabled="!data.hasNext || saving" @click="changePage(page + 1)">下一页</el-button>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { evidenceRead, evidenceWrite } from '@/api/enterpriseEvidence'

const kinds = [{ id: 'mes', name: 'MES 进度风险' }, { id: 'qms', name: 'QMS 品质风险' }]
const route = useRoute(), router = useRouter()
const kind = computed(() => route.query.operationalRisk === 'qms' ? 'qms' : 'mes')
const page = ref(1), data = ref(null), message = ref('')
const waiting = ref(false), saving = ref(false), selected = ref(null)
const handlerId = ref(''), reason = ref(''), evidence = ref('')
let sequence = 0

function endpoint() { return '/api/analytics/operational-risks/' + kind.value + '/' }

async function load() {
  const read = ++sequence
  waiting.value = true
  message.value = ''
  data.value = null
  selected.value = null
  const result = await evidenceRead(endpoint(), { page: page.value })
  if (read !== sequence) return
  waiting.value = false
  if (!result.success) {
    message.value = result.error?.message || '正式风险依据读取失败，结果待核。'
    return
  }
  data.value = result.data
}

function switchKind(value) {
  if (saving.value || value === kind.value) return
  router.replace({ query: { ...route.query, operationalRisk: value } })
}

function changePage(value) { page.value = value; return load() }

function select(item, action) {
  selected.value = { id: item.id, action }
  handlerId.value = ''
  reason.value = ''
  evidence.value = ''
}

async function submit(item) {
  if (saving.value) return
  const action = selected.value.action.type
  saving.value = true
  try {
    const result = action === 'receive'
      ? await evidenceWrite(endpoint(), { sourceId: item.id, handlerId: handlerId.value, reason: reason.value })
      : await evidenceWrite(endpoint() + item.risk.id + '/' + action + '/',
        { expectedVersion: item.risk.version, reason: reason.value, evidence: evidence.value })
    if (result.success) await load()
    else message.value = result.error?.message || '风险办理未完成。'
  } finally { saving.value = false }
}

watch(kind, () => { page.value = 1; return load() }, { immediate: true })
</script>

<style scoped>
.case { padding: 12px; border-top: 1px solid #d6e0ee; }
</style>
