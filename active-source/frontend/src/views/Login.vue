<template>
  <main class="login-container" :data-ui-version="UI_BRAND.version">
    <section class="login-panel" aria-label="掌云智造账户登录">
      <section class="brand-panel" aria-label="掌云智造品牌介绍">
        <div class="brand-image-window"><img src="/brand/palmcloud-user02-original.png?v=20261116-02" alt="掌云智造 PalmCloud ERP · 掌上云端·系统互联·智能协同·全局在握" /></div>
        <p class="brand-description"><span>整木专用</span></p>
        <div class="capabilities"><article v-for="item in capabilities" :key="item.title"><component :is="item.icon" v-if="item.icon" aria-hidden="true" /><svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path :d="item.path" /></svg><div><h2>{{ item.title }}</h2><p>{{ item.detail }}</p></div></article></div>
      </section>
      <section class="login-form-panel">
        <p class="login-eyebrow">欢迎使用 PalmCloud ERP</p><h1>账户登录</h1>
        <p class="login-intro">多企业共用入口，登录后按授权进入企业工作范围。</p>
        <el-alert v-if="returnTarget" title="登录成功后返回原工作位置" type="info" show-icon :closable="false" class="return-alert" />
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleLogin">
          <details class="account-picker"><summary>选择账户（查看完整账号）<span v-if="selectedAccount"> · {{ selectedAccount.label }}</span></summary><div class="account-options"><p v-if="!accounts.length">尚无账户书签，请手工输入原账号。</p><button v-for="account in accounts" :key="account.username" type="button" @click="selectAccount(account)"><strong>{{ account.label }}</strong><span v-if="account.label !== account.username">{{ account.username }}</span></button></div></details>
          <el-form-item label="账号" prop="username">
            <el-input ref="usernameInputRef" v-model="form.username" name="username" aria-label="账号" autocomplete="username" placeholder="请输入原登录账号，不是姓名" autocapitalize="none" spellcheck="false" />
          </el-form-item>
          <p v-if="form.username" class="selected-account-value">登录账号：{{ form.username }}</p>
          <el-form-item label="密码" prop="password">
            <div class="password-control">
              <el-input ref="passwordInputRef" v-model="form.password" name="password" aria-label="密码" :type="passwordVisible ? 'text' : 'password'" autocomplete="current-password" placeholder="密码" />
              <button type="button" class="password-toggle" :aria-label="passwordVisible ? '隐藏密码' : '显示密码'" :aria-pressed="passwordVisible" @click="togglePassword">{{ passwordVisible ? '隐藏' : '显示' }}</button>
            </div>
          </el-form-item>
          <el-button class="login-submit" type="primary" native-type="submit" :loading="loading">登录</el-button>
        </el-form>
      </section>
      <footer class="login-environment">{{ UI_BRAND.environment }} · {{ UI_BRAND.version }} · 登录界面 L1.7</footer>
    </section>
  </main>
</template>
<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Box, CircleCheck } from '@element-plus/icons-vue'
import { authenticateEnterprise } from '../api/auth.js'
import { useUserStore } from '../stores/counter.js'
import { UI_BRAND } from '../meta/runtime/uiBranding.js'
import { normalizeAccountShortcut, rememberAccountShortcut, readAccountShortcuts } from '../meta/runtime/accountShortcuts.js'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const form = reactive({ username: normalizeAccountShortcut({ username: route.query.username })?.username || '', password: '' })
const accounts = ref(readAccountShortcuts())
const selectedUsername = ref('')
const selectedAccount = computed(() => accounts.value.find(row => row.username === selectedUsername.value))
function selectAccount(account) { selectedUsername.value = account.username; form.username = account.username; form.password = ''; document.activeElement?.closest('details')?.removeAttribute('open') }
const capabilities = [
 {title:'营销管理',detail:'客户管理·接单审批',path:'M5 3h14v18H5z M8 8h8 M8 12h8 M8 16h5'},
 {title:'工程管理',detail:'工序工艺·拆单核算·标准产能',path:'M3 5h18v14H3z M7 9h4v6H7z M14 9h4 M14 13h4'},
 {title:'物料供应',detail:'采购供应·库存管理',icon:Box},
 {title:'计划排产',detail:'资源统筹·计划排程',path:'M4 5h16v15H4z M8 3v4 M16 3v4 M4 10h16 M8 14h3 M13 17h3'},
 {title:'生产执行',detail:'派工报工·交接入库',path:'M3 21V9l6 3V6l6 4V3h6v18z M6 16h2 M11 16h2 M17 16h2'},
 {title:'品质管控',detail:'质量检验·品质追溯',icon:CircleCheck},
 {title:'进度管控',detail:'进度反馈·协同跟进',path:'M3 12h4l3-7 4 14 3-7h4'},
 {title:'异常处理',detail:'发现问题·跟踪处理',path:'M12 3 2 21h20L12 3z M12 9v5 M12 17v1'},
 {title:'绩效管理',detail:'业务数据·绩效考核',path:'M4 21V11h4v10 M10 21V7h4v14 M16 21V3h4v18'}
]
const loading = ref(false)
const formRef = ref(null)
const usernameInputRef = ref(null), passwordInputRef = ref(null), passwordVisible = ref(false)
function togglePassword() { passwordVisible.value = !passwordVisible.value; passwordInputRef.value?.focus() }
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const returnTarget = computed(() => {
  const requested = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  return requested.startsWith('/') && !requested.startsWith('//') && !/[\\\r\n]/.test(requested) ? requested : ''
})

async function handleLogin() {
  if (loading.value) return
  // Browser autofill may update native controls before Vue receives an input event.
  const username = usernameInputRef.value?.input?.value, password = passwordInputRef.value?.input?.value
  if (typeof username === 'string') {
    // Never silently substitute a selected identity for an edited/autofilled value.
    if (selectedUsername.value && username !== selectedUsername.value) {
      selectedUsername.value = ''
      form.username = username
      ElMessage.error('账号输入已被修改或自动填充，请重新选择账户，或手工输入完整原登录账号后再登录。')
      return
    }
    form.username = username
  }
  if (accounts.value.some(row => row.identitySource === 'authenticated-profile' && row.label !== row.username && row.label === form.username)) {
    ElMessage.error('此处需要原登录账号，不能使用人员姓名。请在“选择账户”中选择对应原账号，或手工输入完整原账号。')
    return
  }
  if (typeof password === 'string') form.password = password
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const authentication = await authenticateEnterprise(form)
    userStore.setToken(authentication.token)
    userStore.setUserInfo(authentication.user)
    try { rememberAccountShortcut({ username: authentication.user.username, label: authentication.user.real_name, identitySource: 'authenticated-profile' }) } catch { /* login works when local preference storage is disabled */ }
    form.password = ''
    ElMessage.success('登录成功')
    const requested = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const redirect = requested.startsWith('/') && !requested.startsWith('//') && !/[\\\r\n]/.test(requested) ? requested : '/'
    await router.push(redirect)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>
<style scoped>
.login-container{box-sizing:border-box;min-height:calc(100dvh - var(--pce-account-bookmark-height,52px));display:grid;place-items:center;padding:28px;background:linear-gradient(135deg,#eef6ff,#f7fafc 55%,#edf4fa);color:#153b59}
.login-panel{box-sizing:border-box;width:min(1120px,100%);display:grid;grid-template-columns:minmax(0,1.15fr) minmax(400px,1fr);gap:42px;align-items:center;padding:40px;border:1px solid #dce7f0;border-radius:22px;background:#fff;box-shadow:0 18px 60px #173f6910}
.brand-panel{min-width:0}.brand-image-window{width:100%;aspect-ratio:2.5;overflow:hidden;background:#fff}.brand-image-window img{display:block;width:100%;height:100%;object-fit:cover;object-position:center}
.brand-description{display:flex;align-items:center;justify-content:center;gap:18px;margin:20px 0;text-align:center;font-size:1.375rem;font-weight:600;letter-spacing:.15em;line-height:1.5;color:#153b59}
.brand-description::before,.brand-description::after{content:"";flex:1 1 64px;min-width:0;max-width:76px;height:1px;background:linear-gradient(to right,transparent,#a9c3ef)}
.brand-description::after{background:linear-gradient(to left,transparent,#a9c3ef)}
.brand-description>span{position:relative;isolation:isolate;box-sizing:border-box;flex:0 0 auto;min-width:0;inline-size:min(12.5rem,64%);padding:9px 21px;border:0;background:none;box-shadow:none;overflow-wrap:anywhere;text-wrap:balance}
.brand-description>span::before{--brand-edge-feather:10pt;content:"";position:absolute;inset:1px 2px;z-index:-1;pointer-events:none;border-radius:12px;background:linear-gradient(90deg,#fff,transparent var(--brand-edge-feather),transparent calc(100% - var(--brand-edge-feather)),#fff),linear-gradient(180deg,#fff,transparent var(--brand-edge-feather),transparent calc(100% - var(--brand-edge-feather)),#fff),linear-gradient(180deg,#f2f6ff,#eaf2ff);filter:none}
.login-context{display:grid;gap:14px;font-size:13px;line-height:1.6;margin:24px 0 0}.login-context div{display:grid;grid-template-columns:72px minmax(0,1fr);gap:10px}.login-context dt{color:#64748b}.login-context dd{margin:0;overflow-wrap:anywhere}
.login-form-panel{min-width:0;padding:28px;background:#f7faff;border:1px solid #e2eaf4;border-radius:16px}.login-eyebrow{font-size:13px;color:#2575bf;margin:0 0 8px}.login-form-panel h1{font-size:28px;margin:0 0 12px}.login-intro{font-size:14px;line-height:1.6;color:#52677b;margin:0 0 24px}.return-alert{margin-bottom:18px}
.password-control{display:flex;align-items:stretch;gap:8px;width:100%;min-width:0}.password-control :deep(.el-input){min-width:0;flex:1}.password-toggle{flex:none;min-width:56px;min-height:48px;border:1px solid #b9cee3;border-radius:6px;background:#fff;color:#165c9b;font:inherit;cursor:pointer}.login-submit{width:100%;height:48px;font-size:16px;margin-top:6px}
.login-panel :deep(.el-input__wrapper){min-height:48px;box-sizing:border-box;padding:4px 12px}.login-panel :deep(.el-input__inner){font-size:16px;height:38px;line-height:38px}.login-panel :deep(.el-form-item__label){font-size:15px;color:#193e5e}.login-panel :deep(.el-form-item){margin-bottom:24px}.login-panel :focus-visible{outline:3px solid #2586e9;outline-offset:3px}
@media(max-width:1024px){.login-container{padding:20px}.login-panel{width:min(660px,100%);grid-template-columns:1fr;gap:24px;padding:28px}.brand-image-window{max-width:460px;margin:auto}.brand-description{font-size:1.25rem;margin:16px 0;gap:16px}.login-context{grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.login-context div:last-child{grid-column:1/-1}.login-form-panel{padding:24px}}
@media(max-width:520px){.login-container{padding:12px;align-items:start}.login-panel{padding:16px;gap:18px;border-radius:14px}.login-form-panel{padding:18px}.login-form-panel h1{font-size:24px}.login-context{grid-template-columns:1fr;font-size:12px}.login-context div:last-child{grid-column:auto}.login-context div{grid-template-columns:60px minmax(0,1fr)}.brand-description{font-size:1.125rem;gap:.75rem}.brand-description>span{inline-size:min(11rem,68%);padding:8px 17px}.login-intro{margin-bottom:18px}.login-panel :deep(.el-form-item){margin-bottom:22px}}
@media(max-height:600px){.login-container{align-items:start;padding-block:12px}.login-panel{padding-block:20px}.login-form-panel{padding-block:18px}}
</style>

<style scoped>
.business-promise{font-size:20px;line-height:1.6;margin:22px 0;color:#193e5e;font-weight:600}.capabilities{display:grid;grid-template-columns:1fr 1fr;gap:22px 16px}.capabilities article{display:flex;gap:10px;align-items:flex-start;min-width:0}.capabilities svg{width:25px;height:25px;flex:none;color:#3877b9}.capabilities h2{font-size:16px;margin:0 0 7px;color:#193e5e}.capabilities p{font-size:14px;margin:0;line-height:1.6;color:#62788c}.login-environment{grid-column:1/-1;font-size:12px;color:#687b8e;border-top:1px solid #e1eaf2;padding-top:14px;overflow-wrap:anywhere}.account-picker{margin-bottom:18px}.account-picker summary{cursor:pointer;min-height:44px;line-height:1.6;padding:8px 0;color:#165c9b;overflow-wrap:anywhere}.account-options{display:grid;gap:6px;max-height:240px;overflow:auto}.account-options button{display:grid;gap:4px;text-align:left;min-height:48px;padding:10px;background:#fff;border:1px solid #ccdae9;border-radius:6px;color:#193e5e;font:inherit;overflow-wrap:anywhere;white-space:normal;cursor:pointer}.account-options span{font-size:13px;color:#62788c}.account-options strong{font-weight:600}.login-panel{row-gap:24px}@media(max-width:520px){.login-form-panel{grid-row:1}.brand-panel{grid-row:2}.capabilities{gap:16px 10px}.business-promise{font-size:18px}.capabilities p{font-size:14px}}
</style>

<style scoped>.selected-account-value{overflow-wrap:anywhere;white-space:normal;font-size:13px;line-height:1.6;color:#52677b;margin:-12px 0 18px}</style>
<style scoped>
.account-picker{width:100%;min-width:0}.account-picker summary{box-sizing:border-box;border:1px solid #b9cee3;border-radius:7px;background:#fff;padding:12px;font-size:15px;font-weight:600;min-height:48px}.account-options{box-sizing:border-box;width:100%;max-height:280px;overflow-y:auto;overflow-x:hidden;margin-top:8px;padding:2px}.account-options button{width:100%;min-width:0;box-sizing:border-box;font-size:14px;line-height:1.65;word-break:break-word;overflow-wrap:anywhere;text-overflow:clip;white-space:normal}.account-options span{font-size:14px;overflow-wrap:anywhere}.account-options strong{font-size:14px;font-weight:500;overflow-wrap:anywhere}.account-options button:hover{background:#eaf3ff;border-color:#4787cb}@media(min-width:1100px){.login-panel{width:min(1200px,100%);grid-template-columns:minmax(0,1.15fr) minmax(480px,1fr);gap:36px}.login-form-panel{padding:24px}.account-options{min-width:0}}@media(max-width:520px){.account-options button,.account-options span,.account-options strong{font-size:14px}.account-picker summary{font-size:15px}}
</style>

<style scoped>
.capabilities{margin-top:22px;gap:22px 24px}.capabilities article:last-child{grid-column:1/-1;justify-content:center;text-align:center;align-items:center;padding-top:2px}.capabilities h2{font-size:16px}.capabilities p{font-size:14px;white-space:normal;overflow-wrap:anywhere}.brand-description{margin-bottom:18px}@media(max-width:520px){.capabilities{gap:20px 12px;margin-top:18px}.capabilities article{gap:8px}.capabilities svg{width:22px;height:22px}}
</style>
<style scoped>.capabilities article:last-child{text-align:left;align-items:flex-start}.capabilities article:last-child svg{margin-top:1px}</style>
<style scoped>.capabilities article:last-child{grid-column:1 / -1;justify-content:flex-start;text-align:left;align-items:flex-start}</style>
<style scoped>.brand-image-window{position:relative;aspect-ratio:1320/540;overflow:hidden}.brand-image-window img{position:absolute;display:block;width:116.363636%;height:auto;max-width:none;left:-8.333333%;top:-46.296296%;object-fit:initial;object-position:initial}</style>

<style scoped>
/* Local brand02 crop preserves original pixels and all four slogan clauses. */
.brand-image-window{width:88%;margin-inline:auto;aspect-ratio:1320/540}
.brand-image-window img{width:116.363636%;left:-8.333333%;top:-42.592593%;height:auto;max-width:none}
@media(min-width:1025px){
 .login-panel{align-items:start}
 .brand-panel{align-self:stretch;display:flex;flex-direction:column}
 .capabilities{margin-top:auto}
 .login-form-panel{align-self:stretch;margin-top:36px;margin-bottom:2px;display:flex;flex-direction:column}
 .login-form-panel :deep(.el-form){flex:1;display:flex;flex-direction:column}
 .login-submit{margin-top:auto}
}
@media(max-width:1024px){.login-form-panel{margin-block:0;align-self:auto}}
@media(max-width:760px){
 .login-intro,.capabilities p{font-size:13px}
 /* Inputs remain16px and controls retain their existing48px touch height. */
}
</style>
