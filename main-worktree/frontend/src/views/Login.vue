<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>掌云智造</h2>
      <el-alert
        v-if="returnTarget"
        :title="`当前标签需要正常登录；登录成功后将返回：${returnTarget}`"
        type="warning"
        show-icon
        :closable="false"
        class="return-alert"
      />
      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" autocomplete="username" placeholder="用户名" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input v-model="form.password" type="password" show-password autocomplete="current-password" placeholder="密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" native-type="submit" :loading="loading">
            登录
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { authenticateEnterprise } from '../api/auth.js'
import { useUserStore } from '../stores/counter.js'
import { normalizeAccountShortcut, rememberAccountShortcut } from '../meta/runtime/accountShortcuts.js'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const form = reactive({ username: normalizeAccountShortcut({ username: route.query.username })?.username || '', password: '' })
const loading = ref(false)
const formRef = ref(null)
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const returnTarget = computed(() => {
  const requested = typeof route.query.redirect === 'string' ? route.query.redirect : ''
  return requested.startsWith('/') && !requested.startsWith('//') ? requested : ''
})

async function handleLogin() {
  if (loading.value) return
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    const authentication = await authenticateEnterprise(form)
    userStore.setToken(authentication.token)
    userStore.setUserInfo(authentication.user)
    try { rememberAccountShortcut({ username: authentication.user.username, label: authentication.user.real_name }) } catch { /* login works when local preference storage is disabled */ }
    form.password = ''
    ElMessage.success('登录成功')
    const requested = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const redirect = requested.startsWith('/') && !requested.startsWith('//') ? requested : '/'
    await router.push(redirect)
  } catch (error) {
    ElMessage.error(error?.response?.data?.error || error?.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - var(--pce-account-bookmark-height, 0px));
  background: #f0f2f5;
}

.login-card {
  width: 400px;
}

.return-alert {
  margin-bottom: 18px;
}
</style>
