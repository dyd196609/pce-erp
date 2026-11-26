import { resolveBusinessName } from '../governance/businessNameRegistry.js'
import { resolvePlatformPageIdentity } from '../governance/platformPageIdentityRegistry.js'
import {
  TAB_AUTH_IDENTITY_KEY,
  getTabAuthToken,
  readTabIdentity,
  rememberTabIdentity,
} from './tabAuthenticationContext.js'

export const PCE_ERP_DEFAULT_DOCUMENT_TITLE = '掌云智造 · PalmCloud ERP'
export const PCE_CURRENT_IDENTITY_STORAGE_KEY = TAB_AUTH_IDENTITY_KEY

function normalizeRoutePath(routeOrPath) {
  const raw = typeof routeOrPath === 'string'
    ? routeOrPath
    : routeOrPath?.path || routeOrPath?.fullPath || ''
  const path = String(raw || '').split('?')[0].split('#')[0]
  return path || '/'
}

function routeQueryMode(routeOrPath) {
  if (typeof routeOrPath === 'object' && routeOrPath?.query?.mode) return String(routeOrPath.query.mode)
  const raw = typeof routeOrPath === 'string' ? routeOrPath : routeOrPath?.fullPath || ''
  const query = String(raw).split('?')[1]?.split('#')[0] || ''
  return new URLSearchParams(query).get('mode') || ''
}

export function resolvePageBusinessTitle(routeOrPath) {
  const path = normalizeRoutePath(routeOrPath)
  const businessName = resolveBusinessName({ route: path })
  if (path === '/sales/orders' && routeQueryMode(routeOrPath) === 'development-contract') return {
    pageTitle: '开发合同与报价', browserTitle: '开发合同与报价', moduleName: businessName?.moduleCode || 'SALES',
    processName: businessName?.processName || '销售订单', stepId: businessName?.nodeCode,
    routePath: path, businessObject: businessName?.businessObject,
    nameSource: 'BusinessNameRegistry + governed sales order subview',
  }
  if (businessName) return {
    pageTitle: businessName.pageTitle, browserTitle: businessName.browserTitle, moduleName: businessName.moduleCode,
    processName: businessName.processName, stepId: businessName.nodeCode,
    routePath: businessName.route, businessObject: businessName.businessObject,
    nameSource: 'BusinessNameRegistry',
  }
  const platformPage = resolvePlatformPageIdentity(path)
  if (platformPage) return {
    pageTitle: platformPage.displayName,
    browserTitle: platformPage.displayName,
    moduleName: platformPage.moduleName,
    processName: platformPage.moduleName,
    routePath: platformPage.route,
    nameSource: 'PlatformPageIdentityRegistry',
  }
  return {
    pageTitle: '页面名称未登记',
    moduleName: 'PCE-ERP',
    processName: '页面名称治理',
    routePath: path,
    canonicalNameMissing: true,
  }
}

export function buildPageDocumentTitle(routeOrPath) {
  const resolved = resolvePageBusinessTitle(routeOrPath)
  if (!resolved?.pageTitle) return PCE_ERP_DEFAULT_DOCUMENT_TITLE
  return resolved.browserTitle || resolved.pageTitle
}

function tokenUsername(storage) {
  try {
    const token = getTabAuthToken(storage)
    const encoded = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const payload = JSON.parse(globalThis.atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '=')))
    if (!payload?.username || (payload.exp && Number(payload.exp) * 1000 <= Date.now())) return ''
    return String(payload.username)
  } catch { return '' }
}

export function rememberCurrentIdentity(user, storage = globalThis.sessionStorage) {
  const identity = user ? {
    userId: user.id ?? user.userId ?? user.identity?.userId ?? null,
    username: String(user.username ?? user.identity?.username ?? ''),
    realName: String(user.real_name ?? user.realName ?? user.identity?.realName ?? ''),
    companyId: user.company_id ?? user.companyId ?? user.organization?.id ?? null,
  } : null
  if (!storage || !identity?.username) return null
  return rememberTabIdentity(identity, storage)
}

export function clearCurrentIdentity(storage = globalThis.sessionStorage) {
  try { storage?.removeItem(PCE_CURRENT_IDENTITY_STORAGE_KEY) } catch { /* best effort */ }
}

export function resolveCurrentIdentity(storage = globalThis.sessionStorage) {
  const username = tokenUsername(storage)
  if (!username) return null
  try {
    const remembered = readTabIdentity(storage)
    if (remembered?.username === username) return remembered
  } catch { /* fall through to the signed JWT username */ }
  return { userId: null, username, realName: '', companyId: null }
}

const dynamicTitles = new Map()

export function setDynamicPageTitle(route, owner, title) {
  dynamicTitles.set(normalizeRoutePath(route), { owner, title })
  return applyPageDocumentTitle(route)
}

export function clearDynamicPageTitle(route, owner) {
  const path = normalizeRoutePath(route)
  if (dynamicTitles.get(path)?.owner === owner) dynamicTitles.delete(path)
}

export function buildIdentityAwareDocumentTitle(routeOrPath, storage = globalThis.sessionStorage, canonicalTitle) {
  const pageTitle = dynamicTitles.get(normalizeRoutePath(routeOrPath))?.title || canonicalTitle || buildPageDocumentTitle(routeOrPath)
  const identity = resolveCurrentIdentity(storage)
  if (!identity) return `未登录｜${pageTitle}`
  const actor = identity.realName || identity.username
  return `${actor}｜${pageTitle}`
}

export function applyPageDocumentTitle(routeOrPath, documentRef = globalThis.document, canonicalTitle) {
  if (!documentRef) return ''
  const title = buildIdentityAwareDocumentTitle(routeOrPath, globalThis.sessionStorage, canonicalTitle)
  documentRef.title = title
  return title
}
