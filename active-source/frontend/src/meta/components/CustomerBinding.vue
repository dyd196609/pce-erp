<template>
  <details class="evidence-disclosure" v-if="access !== false" @toggle="onToggle">
    <summary>客户账号绑定</summary>
    <p v-if="message" role="status">{{ message }}</p>
    <template v-if="data?.canProvision">
      <el-button size="large" native-type="button" :aria-expanded="showProvision" :disabled="busy" @click="showProvision = !showProvision">新增客户账号</el-button>
      <form v-if="showProvision" aria-label="开通独立客户账号" class="evidence-form evidence-subform" @submit.prevent="provision">
        <label class="evidence-field">登录账号
          <input v-model.trim="draft.username" required maxlength="50" pattern="[a-zA-Z0-9_.@\-]+" autocomplete="off" />
        </label>
        <label class="evidence-field">客户联系人姓名
          <input v-model.trim="draft.realName" required maxlength="50" autocomplete="off" />
        </label>
        <label class="evidence-field evidence-field--choice">客户档案
          <select v-model="draft.customerId" required>
            <option value="" disabled>请选择</option>
            <option v-for="row in data.customers" :key="row.id" :value="row.id">{{ row.name }}（{{ row.code }}）</option>
          </select>
        </label>
        <label class="evidence-field evidence-field--wide">客户身份核实依据
          <textarea v-model.trim="draft.reason" required maxlength="300" rows="2"></textarea>
        </label>
        <p class="evidence-form-note">开户后，由账户管理员在「组织结构 → 用户账户」设置初始密码。</p>
        <el-button size="large" native-type="submit" type="primary" :disabled="busy">开户并绑定</el-button>
      </form>
      <router-link v-if="newAccountCreated" to="/organization?tab=users">前往用户账户设置初始密码</router-link>
    </template>
    <p v-if="data && !data.accounts.length">当前没有可绑定的已有客户账号。</p>
    <form v-if="data" class="evidence-form evidence-subform" aria-label="绑定已有客户账号" @submit.prevent="save">
      <label class="evidence-field evidence-field--choice">已核实的客户账号
        <select v-model="accountId" required>
          <option value="" disabled>请选择</option>
          <option v-for="row in data.accounts" :key="row.id" :value="row.id">{{ row.name }}（{{ row.username }}）</option>
        </select>
      </label>
      <label class="evidence-field evidence-field--choice">客户档案
        <select v-model="customerId" required>
          <option value="" disabled>请选择</option>
          <option v-for="row in data.customers" :key="row.id" :value="row.id">{{ row.name }}（{{ row.code }}）</option>
        </select>
      </label>
      <label class="evidence-field evidence-field--wide">客户身份核实依据
          <textarea v-model.trim="reason" required maxlength="300" rows="2"></textarea>
        </label>
      <el-button size="large" native-type="submit" type="primary" :disabled="busy || !data.accounts.length">确认绑定</el-button>
    </form>
  </details>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { bindingUrl, evidenceRead, evidenceWrite } from '@/api/enterpriseEvidence'

const data = ref(null), access = ref(null), message = ref(''), busy = ref(false)
const accountId = ref(''), customerId = ref(''), reason = ref('')
const showProvision = ref(false), newAccountCreated = ref(false)
const draft = reactive({ username: '', realName: '', customerId: '', reason: '' })

async function load() {
  const result = await evidenceRead(bindingUrl)
  access.value = result.meta?.status !== 403
  data.value = result.success ? result.data : null
  if (!result.success && access.value) message.value = '客户账号或客户档案读取失败。'
}

function onToggle(event) { if (event.target.open) load() }

async function save() {
  if (busy.value) return
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

async function provision() {
  if (busy.value) return
  busy.value = true
  newAccountCreated.value = false
  try {
    const result = await evidenceWrite(bindingUrl, { action: 'provision', ...draft })
    if (!result.success) {
      message.value = result.error?.message || '客户开户失败。'
      return
    }
    message.value = `账号 ${result.data.username} 已绑定客户档案 ${result.data.customerCode}。${result.data.credentialStatusLabel}。`
    Object.assign(draft, { username: '', realName: '', customerId: '', reason: '' })
    showProvision.value = false
    newAccountCreated.value = true
    await load()
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

