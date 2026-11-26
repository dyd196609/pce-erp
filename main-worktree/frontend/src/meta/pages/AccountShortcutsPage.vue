<template>
  <PceFormPageShell>
    <section class="shortcut-page" data-page-code="account-shortcuts" data-contract="PCE-WEB-ACCEPTANCE-V1.1">
      <header>
        <p class="eyebrow">PCE · 账户入口</p>
        <h1>{{ ACCOUNT_SHORTCUT_PAGE.title }}</h1>
        <p>需要办理业务时选择账户，业务页面将在新页签打开。误关本页后，点击任意 PCE 页面左上角的“★ 账户书签”即可找回。</p>
        <nav aria-label="快捷账户页面动作">
          <el-button :loading="loading" @click="refresh">刷新</el-button>
          <el-button @click="copyDiagnostics">复制诊断数据</el-button>
          <el-button :loading="opening" @click="openWorkspace">返回业务流程中心</el-button>
        </nav>
      </header>

      <section class="current-account" aria-label="当前页签账户">
        <h2>当前页签账户</h2>
        <p v-if="loading" role="status">正在核对登录状态…</p>
        <template v-else-if="profile">
          <strong>{{ profile.identity.realName || profile.identity.username }}</strong>
          <p>{{ profile.identity.username }} · {{ profile.organization.name }}</p>
          <el-button type="primary" :loading="opening" @click="openWorkspace">以当前账户打开业务流程中心</el-button>
        </template>
        <p v-else role="status">{{ notice || '本页签尚未登录，请选择下方账户。' }}</p>
      </section>

      <section aria-label="常用账户快捷入口">
        <h2>常用账户</h2>
        <p>这里只记住账号名称。账户身份与可用权限在登录时核验。</p>
        <div class="account-grid">
          <article v-for="account in accounts" :key="account.username" class="account-card">
            <strong>{{ account.label }}</strong>
            <p>{{ account.username }}</p>
            <el-button v-if="profile?.identity.username === account.username" type="primary" plain :loading="opening" @click="openWorkspace">以此账户打开</el-button>
            <el-button v-else :aria-label="`登录 ${account.label}`" @click="openLogin(account)">登录此账户</el-button>
          </article>
        </div>
      </section>

      <section class="add-account" aria-label="添加账户快捷入口">
        <h2>添加常用账户</h2>
        <form @submit.prevent="addAccount">
          <label>账号名<input v-model="newAccount.username" maxlength="50" autocomplete="off" placeholder="输入登录账号" required /></label>
          <label>显示名称<input v-model="newAccount.label" maxlength="60" autocomplete="off" placeholder="例如：张宏达" /></label>
          <el-button native-type="submit">添加快捷入口</el-button>
        </form>
        <p>此操作仅保存本机快捷入口，不创建账户。密码在正常登录页输入，本页不保存密码。</p>
      </section>
    </section>
  </PceFormPageShell>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import PceFormPageShell from '../components/PceFormPageShell.vue'
import { accessControlApi } from '../../api/accessControl.js'
import { getTabAuthToken } from '../runtime/tabAuthenticationContext.js'
import { ACCOUNT_SHORTCUT_PAGE, accountLoginLocation, openCurrentAccountTab, openUnauthenticatedAccountTab, readAccountShortcuts, rememberAccountShortcut } from '../runtime/accountShortcuts.js'

const router = useRouter()
const accounts = ref(readAccountShortcuts())
const newAccount = reactive({ username: '', label: '' })
const profile = ref(null), loading = ref(false), opening = ref(false), notice = ref('')
let readSequence = 0
async function refresh() {
  const sequence = ++readSequence
  accounts.value = readAccountShortcuts()
  profile.value = null
  notice.value = ''
  loading.value = false
  if (!getTabAuthToken()) return
  loading.value = true
  try {
    const response = await accessControlApi.profile()
    if (sequence !== readSequence) return
    if (!response.success || !response.data?.authenticated || !response.data?.identity?.username) throw new Error('登录状态未能核对，请重新登录或刷新重试。')
    profile.value = response.data
    // Profile is server-verified; local bookmarks remain names only.
    try { accounts.value = rememberAccountShortcut({ username: profile.value.identity.username, label: profile.value.identity.realName }) } catch { /* storage may be disabled */ }
  } catch (error) {
    if (sequence === readSequence) notice.value = error.message || '登录状态读取失败，请刷新重试。'
  } finally { if (sequence === readSequence) loading.value = false }
}
function openLogin(account = {}) {
  const result = openUnauthenticatedAccountTab(accountLoginLocation(account.username || ''), router)
  if (!result.opened) ElMessage.error(result.reason)
}
async function openWorkspace() {
  if (opening.value || loading.value) return
  if (!profile.value || !getTabAuthToken()) { openLogin(); return }
  opening.value = true
  try {
    const result = await openCurrentAccountTab('/process-center', router)
    if (!result.opened) { profile.value = null; notice.value = '当前登录无法继续使用，请选择账户正常登录。'; ElMessage.error('新页签打开失败，请刷新登录状态后重试。') }
  } finally { opening.value = false }
}
function addAccount() {
  try {
    accounts.value = rememberAccountShortcut(newAccount)
    newAccount.username = ''; newAccount.label = ''
    ElMessage.success('账户快捷入口已添加')
  } catch (error) { ElMessage.error(error.message || '快捷入口保存失败') }
}
async function copyDiagnostics() {
  try {
    await navigator.clipboard.writeText(JSON.stringify({ pageCode: ACCOUNT_SHORTCUT_PAGE.pageCode, route: ACCOUNT_SHORTCUT_PAGE.route, accountShortcutCount: accounts.value.length, profileLoaded: Boolean(profile.value), loading: loading.value, scope: 'navigation-and-authentication-only' }, null, 2))
    ElMessage.success('诊断数据已复制')
  } catch { ElMessage.error('复制失败，请检查浏览器剪贴板权限。') }
}
function syncBookmarks(event) { if (!event.key || event.key === 'pce_account_shortcut_names_v1') accounts.value = readAccountShortcuts() }
onMounted(() => { refresh(); window.addEventListener('pce:authentication-changed', refresh); window.addEventListener('storage', syncBookmarks) })
onBeforeUnmount(() => { readSequence += 1; window.removeEventListener('pce:authentication-changed', refresh); window.removeEventListener('storage', syncBookmarks) })
</script>

<style scoped>
.shortcut-page { max-width: 980px; margin: 0 auto; padding: 32px 20px; color: #172d46; display: grid; gap: 24px; overflow-wrap: anywhere; }
h1 { margin: 6px 0 12px; font-size: 30px; } h2 { margin: 0 0 12px; font-size: 19px; }
p { color: #52647a; line-height: 1.6; } .eyebrow { color: #2563eb; font-size: 13px; font-weight: 700; }
nav { display: flex; flex-wrap: wrap; gap: 8px; }
.current-account, .add-account { border: 1px solid #d7e2ee; border-radius: 12px; padding: 22px; background: #f5f9ff; }
.current-account strong { font-size: 22px; }
.account-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 250px), 1fr)); gap: 14px; }
.account-card { border: 1px solid #d4dfeb; border-radius: 10px; padding: 22px; background: white; }
.account-card strong { font-size: 18px; } .account-card p { font-size: 14px; min-height: 23px; }
form { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; }
label { display: grid; gap: 7px; flex: 1 1 200px; min-width: 0; font-size: 14px; }
input { box-sizing: border-box; width: 100%; border: 1px solid #bac9da; border-radius: 5px; padding: 9px 12px; font: inherit; }
input:focus { outline: 2px solid #2563eb; outline-offset: 1px; }
nav :deep(.el-button) { margin-left: 0; }
</style>
