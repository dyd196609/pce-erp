<template>
  <el-button class="account-bookmark" :loading="opening" aria-label="账户书签" title="打开快捷登录账户（新页签）" @click="openShortcuts">
    <span class="bookmark-star" aria-hidden="true">★</span>账户书签
  </el-button>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getTabAuthToken } from '../runtime/tabAuthenticationContext.js'
import { ACCOUNT_SHORTCUT_PAGE, openCurrentAccountTab, openUnauthenticatedAccountTab } from '../runtime/accountShortcuts.js'
const router = useRouter()
const opening = ref(false)
async function openShortcuts() {
  if (opening.value) return
  opening.value = true
  try {
    const result = getTabAuthToken()
      ? await openCurrentAccountTab(ACCOUNT_SHORTCUT_PAGE.route, router)
      : openUnauthenticatedAccountTab(ACCOUNT_SHORTCUT_PAGE.route, router)
    if (!result.opened) ElMessage.error(result.reason || '快捷登录页签打开失败，请重试。')
  } finally { opening.value = false }
}
</script>

<style scoped>
.account-bookmark {
  flex-shrink: 0;
  height: 38px;
  padding: 0 16px;
  border: 1px solid #1e4d86;
  border-radius: 7px;
  background: #173e70;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
}
.account-bookmark:hover, .account-bookmark:focus-visible { background: #245b9d; color: #fff; border-color: #173e70; }
.account-bookmark:focus-visible { outline: 3px solid #d89200; outline-offset: 2px; }
.bookmark-star { color: #ffd36b; margin-right: 7px; font-size: 18px; }
</style>
