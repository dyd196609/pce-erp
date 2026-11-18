import verifiedBookmarkNames from './verifiedBookmarkNames.json'
import { openProcessNodeInNewTab } from '../process/processNodeNavigation.js'
import { TAB_AUTH_TOKEN_KEY, TAB_AUTH_IDENTITY_KEY, TAB_AUTH_EPOCH_KEY } from './tabAuthenticationContext.js'

export const ACCOUNT_SHORTCUT_PAGE = Object.freeze({
  route: '/account-shortcuts', title: '快捷登录账户', pageCode: 'account-shortcuts',
})
export const ACCOUNT_SHORTCUT_KEY = 'pce_account_shortcut_names_v1'
// Personal login bookmarks, never an account directory or authorization source.
const defaults = [
  { username: 'pce_emp_comp001_0002', label: 'pce_emp_comp001_0002' },
  { username: 'admin', label: 'admin' },
]
export function normalizeAccountShortcut(value) {
  const username = typeof value?.username === 'string' ? value.username.trim() : ''
  if (!/^[\p{L}\p{N}_.@-]{1,50}$/u.test(username)) return null
  return { username, label: verifiedBookmarkNames[username] || (value?.identitySource === 'authenticated-profile' ? (String(value?.label || username).trim().slice(0, 60) || username) : username), identitySource: value?.identitySource === 'authenticated-profile' ? 'authenticated-profile' : 'account-bookmark' }
}
export function readAccountShortcuts(storage = globalThis.localStorage) {
  let saved = []
  try { saved = JSON.parse(storage?.getItem(ACCOUNT_SHORTCUT_KEY) || '[]') } catch { /* use bookmarks */ }
  const rows = Array.isArray(saved) ? saved : []
  return [...new Map([...defaults, ...rows].map(normalizeAccountShortcut).filter(Boolean)
    .map(row => [row.username, row])).values()].slice(0, 30)
}
export function rememberAccountShortcut(value, storage = globalThis.localStorage) {
  const row = normalizeAccountShortcut(value)
  if (!row) throw new Error('请输入有效账号名（最多50个字符）。')
  const rows = readAccountShortcuts(storage).filter(item => item.username !== row.username)
  const next = [row, ...rows].slice(0, 30)
  // Explicit allowlist: no password, JWT, cookie, permissions, or company claim.
  storage?.setItem(ACCOUNT_SHORTCUT_KEY, JSON.stringify(next))
  return next
}
export function accountLoginLocation(username = '') {
  return { path: '/system-login', query: { username, redirect: '/process-center' } }
}
export function openUnauthenticatedAccountTab(location, router, browserWindow = globalThis.window) {
  const href = router.resolve(location).href
  const tab = browserWindow.open('about:blank', '_blank')
  if (!tab) return { opened: false, reason: '浏览器未能打开新页签，请允许当前站点弹出窗口。' }
  try {
    for (const key of [TAB_AUTH_TOKEN_KEY, TAB_AUTH_IDENTITY_KEY, TAB_AUTH_EPOCH_KEY]) tab.sessionStorage.removeItem(key)
    tab.opener = null
    tab.location.replace(href)
    return { opened: true }
  } catch {
    tab.close()
    return { opened: false, reason: '新页签隔离未完成，请重试。' }
  }
}
export async function openCurrentAccountTab(targetPath, router, browserWindow = globalThis.window) {
  const result = openProcessNodeInNewTab({ pageCode: ACCOUNT_SHORTCUT_PAGE.pageCode, pageUrl: targetPath, allowNewTab: true }, router, browserWindow)
  return result.handoffPromise ? await result.handoffPromise : result
}
