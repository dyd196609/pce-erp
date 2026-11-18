<template>
  <div ref="appElement" class="pce-app" :style="{ '--pce-account-bookmark-height': `${accountBookmarkHeight}px`, '--pce-system-bar-height': `${systemBarHeight}px` }">
    <nav ref="accountBookmarkBar" class="account-bookmark-bar" aria-label="固定账户书签">
      <AccountShortcutsEntry />
      <span class="account-full-label" aria-live="polite">{{ accountLabel }}</span>
      <details class="account-compact-identity">
        <summary>{{ accountShortLabel }} · 账号</summary>
        <div role="status">{{ accountLabel }}</div>
      </details>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { applyPageDocumentTitle, resolveCurrentIdentity } from './meta/runtime/pageTitleManager.js'
import AccountShortcutsEntry from './meta/components/AccountShortcutsEntry.vue'

const route = useRoute()
const accountLabel = ref('正在确认账户')
const accountShortLabel = ref('正在确认账户')
let accountTimer

function syncAccount() {
  const identity = resolveCurrentIdentity()
  accountShortLabel.value = identity?.realName || identity?.username || '未登录'
  const label = identity
    ? `当前账户 ${identity.realName ? `${identity.realName}（${identity.username}）` : identity.username}`
    : '未登录'
  if (accountLabel.value === label) return
  accountLabel.value = label
  applyPageDocumentTitle(route)
}

const accountBookmarkBar = ref(null)
const appElement = ref(null)
const accountBookmarkHeight = ref(52)
const systemBarHeight = ref(72)
let bookmarkResizeObserver
let shellMutationObserver
let observedSystemBar

onMounted(() => {
  syncAccount()
  window.addEventListener('pce:authentication-changed', syncAccount)
  window.addEventListener('storage', syncAccount)
  window.addEventListener('focus', syncAccount)
  accountTimer = window.setInterval(syncAccount, 1000)
  const syncBookmarkHeight = () => {
    accountBookmarkHeight.value = Math.ceil(accountBookmarkBar.value.getBoundingClientRect().height)
    systemBarHeight.value = Math.ceil(observedSystemBar?.getBoundingClientRect().height || 0)
  }
  bookmarkResizeObserver = new ResizeObserver(syncBookmarkHeight)
  bookmarkResizeObserver.observe(accountBookmarkBar.value)
  const observeSystemBar = () => {
    const systemBar = appElement.value.querySelector('.system-bar')
    if (systemBar === observedSystemBar) return
    if (observedSystemBar) bookmarkResizeObserver.unobserve(observedSystemBar)
    observedSystemBar = systemBar
    if (observedSystemBar) bookmarkResizeObserver.observe(observedSystemBar)
    syncBookmarkHeight()
  }
  shellMutationObserver = new MutationObserver(observeSystemBar)
  shellMutationObserver.observe(appElement.value, { childList: true, subtree: true })
  observeSystemBar()
  syncBookmarkHeight()
})

onBeforeUnmount(() => {
  window.clearInterval(accountTimer)
  window.removeEventListener('pce:authentication-changed', syncAccount)
  window.removeEventListener('storage', syncAccount)
  window.removeEventListener('focus', syncAccount)
  bookmarkResizeObserver?.disconnect()
  shellMutationObserver?.disconnect()
})
</script>

<style scoped>
.pce-app {
  --pce-account-bookmark-height: 52px;
  padding-top: var(--pce-account-bookmark-height);
}
.account-bookmark-bar {
  position: fixed;
  inset: 0 0 auto;
  z-index: 1000;
  box-sizing: border-box;
  min-height: 52px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 14px;
  padding: 6px 12px;
  background: #eff6ff;
  border-bottom: 1px solid #93b4dc;
  box-shadow: 0 2px 6px #172d4614;
}
.account-bookmark-bar > span { min-width: 0; color: #334d70; font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.account-compact-identity { display: none; }
@media (max-width: 900px) {
  .account-bookmark-bar { min-height: 52px; gap: 8px; padding: 4px 8px; flex-wrap: nowrap; }
  .account-bookmark-bar > .account-full-label { display: none; }
  .account-bookmark-bar :deep(.account-bookmark) { min-height: 44px; height: auto; padding-inline: 10px; font-size: .8125rem; }
  .account-compact-identity { display: block; min-width: 0; margin-left: auto; color: #334d70; font-size: .8125rem; }
  .account-compact-identity summary { min-height: 44px; display: flex; align-items: center; cursor: pointer; overflow-wrap: anywhere; }
  .account-compact-identity summary::after { content: ' ▾'; margin-left: 5px; }
  .account-compact-identity > div { position: absolute; inset: 100% 8px auto; padding: 12px; border: 1px solid #b9cee3; border-radius: 8px; background: #fff; box-shadow: 0 6px 18px #173f6922; overflow-wrap: anywhere; }
}
@media (max-width: 440px) {
  .account-bookmark-bar { gap: 8px; padding-inline: 8px; }
  .account-bookmark-bar > span { max-width: 140px; font-size: 12px; }
}
@media print {
  .account-bookmark-bar { display: none; }
  .pce-app { padding-top: 0; }
}
</style>
