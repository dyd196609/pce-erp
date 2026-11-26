import { issueTabAuthenticationHandoff } from '../../api/auth.js'
import {
  TAB_AUTH_EPOCH_KEY,
  TAB_AUTH_IDENTITY_KEY,
  TAB_AUTH_TOKEN_KEY,
} from '../runtime/tabAuthenticationContext.js'

export const PROCESS_NODE_NAVIGATION_VERSION = 'V1.14.2.8.4.19'

export function isProcessNodeNavigable(node = {}) {
  return Boolean(node.pageCode && node.pageUrl && node.allowNewTab === true)
}

export function buildProcessNodeTabUrl(node = {}, locationLike = globalThis.location) {
  if (!isProcessNodeNavigable(node)) return ''
  const origin = String(locationLike?.origin || '').replace(/\/$/, '')
  const pathname = String(locationLike?.pathname || '/')
  const pageUrl = String(node.pageUrl).startsWith('/') ? node.pageUrl : `/${node.pageUrl}`
  return `${origin}${pathname}#${pageUrl}`
}

export async function openProcessNodeInCurrentPage(node = {}, router) {
  if (!node.pageCode || !node.pageUrl || typeof router?.push !== 'function') {
    return { opened: false, pageUrl: String(node.pageUrl || ''), reason: 'PROCESS_NODE_NOT_NAVIGABLE' }
  }
  await router.push(node.pageUrl)
  return {
    opened: true,
    pageUrl: node.pageUrl,
    pageCode: node.pageCode,
    target: '_self',
  }
}

export function openProcessNodeInNewTab(node = {}, routerOrWindow, explicitWindow) {
  const router = typeof routerOrWindow?.resolve === 'function' ? routerOrWindow : null
  const browserWindow = router
    ? (explicitWindow || globalThis.window)
    : (routerOrWindow?.open ? routerOrWindow : (explicitWindow || globalThis.window))
  const baseUrl = buildProcessNodeTabUrl(node, browserWindow?.location)
  if (!baseUrl || typeof browserWindow?.open !== 'function') {
    return { opened: false, url: baseUrl, reason: 'PROCESS_NODE_NOT_NAVIGABLE' }
  }
  // Preserve the established pure-navigation contract for non-UI callers.
  // The real process-center UI always provides the router and therefore uses
  // the server-authorized one-time handoff below.
  if (!router) {
    browserWindow.open(baseUrl, '_blank')
    return { opened: true, url: baseUrl, target: '_blank', processCenterPreserved: true }
  }
  const tab = browserWindow.open('about:blank', '_blank')
  if (!tab) return { opened: false, url: baseUrl, reason: 'NEW_TAB_BLOCKED' }
  try {
    // about:blank initially inherits this origin. Remove any browser-cloned
    // sessionStorage before severing the opener relationship.
    tab.sessionStorage?.removeItem(TAB_AUTH_TOKEN_KEY)
    tab.sessionStorage?.removeItem(TAB_AUTH_IDENTITY_KEY)
    tab.sessionStorage?.removeItem(TAB_AUTH_EPOCH_KEY)
  } catch { /* receiving tab still validates the one-time exchange */ }
  tab.opener = null
  const handoffPromise = (async () => {
    try {
    const targetPath = router?.resolve ? router.resolve(node.pageUrl).fullPath : node.pageUrl
    const handoff = await issueTabAuthenticationHandoff(targetPath)
    const separator = String(targetPath).includes('?') ? '&' : '?'
    const origin = String(browserWindow.location?.origin || '').replace(/\/$/, '')
    const pathname = String(browserWindow.location?.pathname || '/')
    const url = `${origin}${pathname}#${targetPath}${separator}authHandoff=${encodeURIComponent(handoff.handoffCode)}`
    tab.location.replace(url)
      return {
      opened: true, url, target: '_blank', processCenterPreserved: true,
      authenticationHandoff: 'SHORT_LIVED_SINGLE_USE',
      }
    } catch (error) {
      tab.close()
      return { opened: false, url: baseUrl, reason: error?.message || 'AUTHENTICATION_HANDOFF_FAILED' }
    }
  })()
  return {
    opened: true, url: baseUrl, target: '_blank', processCenterPreserved: true,
    authenticationHandoff: 'PENDING_SHORT_LIVED_SINGLE_USE', handoffPromise,
  }
}
