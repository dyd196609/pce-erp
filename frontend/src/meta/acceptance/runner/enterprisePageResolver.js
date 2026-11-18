import { resolveScmPageIdentity } from '../../schema/scm/scmPageIdentityRegistry.js'
import { resolveScmStandardPageContract } from '../../schema/scm/scmStandardPageContract.js'
import { findPageAcceptanceContract } from '../../runtime/pcePageAcceptanceRegistry.js'

export const ENTERPRISE_PAGE_RESOLVER_VERSION = 'V1.14.2.8.4.22'

const COMPONENT_BY_ROUTE = Object.freeze({
  '/scm/purchase-request': 'ScmPurchaseRequestPage',
})

export function normalizeEnterprisePageUrl(pageUrl = '') {
  const value = String(pageUrl || '').trim()
  if (!value) return { pagePath: '', query: Object.freeze({}) }
  let routeValue = value
  try {
    const parsed = new URL(value, 'http://localhost')
    routeValue = parsed.hash?.startsWith('#/') ? parsed.hash.slice(1) : `${parsed.pathname}${parsed.search}`
  } catch { routeValue = value }
  const [pagePath, queryString = ''] = routeValue.replace(/^#/, '').split('?')
  const query = Object.fromEntries(new URLSearchParams(queryString).entries())
  return Object.freeze({ pagePath: pagePath || '/', query: Object.freeze(query) })
}

const canonicalPageCode = (moduleCode, pageCode) => `${moduleCode}_${String(pageCode).replace(/[^a-zA-Z0-9]+/g, '_').toUpperCase()}`

export function resolveEnterprisePage({ pageUrl, moduleCode = '' } = {}) {
  const normalized = normalizeEnterprisePageUrl(pageUrl)
  const scmIdentity = resolveScmPageIdentity(normalized.pagePath)
  const scmContract = resolveScmStandardPageContract(normalized.pagePath)
  if (scmIdentity && scmContract) {
    if (moduleCode && moduleCode !== scmIdentity.moduleCode) return Object.freeze({ result: 'UNKNOWN', error: { code: 'MODULE_MISMATCH', message: `${moduleCode} != ${scmIdentity.moduleCode}` }, pageUrl: normalized.pagePath, query: normalized.query })
    return Object.freeze({
      result: 'PASS',
      pageCode: canonicalPageCode(scmIdentity.moduleCode, scmIdentity.pageCode),
      runtimePageCode: scmIdentity.pageCode,
      pageName: scmIdentity.pageName,
      pageUrl: scmContract.route,
      moduleCode: scmIdentity.moduleCode,
      routeName: `${scmIdentity.moduleCode.toLowerCase()}-${scmIdentity.pageCode}`,
      component: COMPONENT_BY_ROUTE[scmContract.route] || scmContract.pageCode,
      businessObject: scmContract.businessObject,
      pageVersion: scmContract.version,
      pageType: scmIdentity.pageType,
      query: normalized.query,
    })
  }
  const generic = findPageAcceptanceContract(normalized.pagePath)
  if (generic) return Object.freeze({
    result: 'PASS', pageCode: canonicalPageCode(generic.moduleCode, generic.pageCode), runtimePageCode: generic.pageCode,
    pageName: generic.canonicalName, pageUrl: generic.route, moduleCode: generic.moduleCode, routeName: generic.routeName,
    component: generic.component, businessObject: generic.businessObject || generic.pageCode, pageVersion: generic.businessVersion,
    pageType: generic.pageType, query: normalized.query,
  })
  return Object.freeze({ result: 'UNKNOWN', error: { code: 'PAGE_NOT_REGISTERED', message: normalized.pagePath }, pageUrl: normalized.pagePath, query: normalized.query })
}
