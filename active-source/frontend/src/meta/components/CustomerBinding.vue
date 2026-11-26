<template>
  <details v-if="access !== false" @toggle="onToggle">
    <summary>客户账号绑定</summary>
    <p v-if="message" role="status">{{ message }}</p>
    <form v-if="data" @submit.prevent="save">
      <label>已核实的客户账号
        <select v-model="accountId" required>
          <option value="" disabled>请选择</option>
          <option v-for="row in data.accounts" :key="row.id" :value="row.id">{{ row.name }}（{{ row.username }}）</option>
        </select>
      </label>
      <label>客户档案
        <select v-model="customerId" required>
          <option value="" disabled>请选择</option>
          <option v-for="row in data.customers" :key="row.id" :value="row.id">{{ row.name }}（{{ row.code }}）</option>
        </select>
      </label>
      <label>客户身份核实依据 <input v-model.trim="reason" required maxlength="300"></label>
      <button type="submit" :disabled="busy">确认绑定</button>
    </form>
  </details>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { bindingUrl, evidenceRead, evidenceWrite } from '@/api/enterpriseEvidence'

const data = ref(null), access = ref(null), message = ref(''), busy = ref(false)
const accountId = ref(''), customerId = ref(''), reason = ref('')

async function load() {
  const result = await evidenceRead(bindingUrl)
  access.value = result.meta?.status !== 403
  data.value = result.success ? result.data : null
  if (!result.success && access.value) message.value = '客户账号或客户档案读取失败。'
}

function onToggle(event) { if (event.target.open) load() }

async function save() {
  busy.value = true
  const result = await evidenceWrite(bindingUrl, { accountId: accountId.value, customerId: customerId.value, reason: reason.value })
  busy.value = false
  if (!result.success) {
    message.value = result.error?.message || '客户账号绑定失败。'
    return
  }
  message.value = '客户账号已绑定。'
  accountId.value = ''
  customerId.value = ''
  reason.value = ''
  await load()
}

onMounted(load)
</script>
