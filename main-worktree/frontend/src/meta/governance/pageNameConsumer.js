import { applyPageDocumentTitle } from '../runtime/pageTitleManager.js'
import { resolveBusinessName } from './businessNameRegistry.js'

export const PAGE_NAME_CONSUMER_VERSION = 'V1.14.2.8.18.10.3.6'
export const NAME_GOV_003 = Object.freeze({
  ruleCode: 'NAME-GOV-003',
  ruleName: '页面名称消费一致性规范',
})
export const NAME_GOV_004 = Object.freeze({
  ruleCode: 'NAME-GOV-004',
  ruleName: '页面壳层名称统一消费规范',
  nameSource: 'BusinessNameRegistry',
  fallbackAllowed: false,
})
export const NAME_GOV_005 = Object.freeze({
  ruleCode: 'NAME-GOV-005',
  ruleName: 'Router 业务名称源禁用规范',
  forbiddenSource: 'route.meta.title',
})
export const NAME_GOV_006 = Object.freeze({
  ruleCode: 'NAME-GOV-006',
  ruleName: '业务名称回退字段禁用规范',
  forbiddenSources: ['fallbackTitle', 'canonicalName', 'currentList.title', 'pageTitle'],
})

export function resolvePageNameConsumption(input = {}) {
  const query = typeof input === 'string'
    ? (input.startsWith('/') ? { route: input } : { pageCode: input })
    : input || {}
  const record = resolveBusinessName(query)
  if (!record) {
    return Object.freeze({
      result: 'FAIL',
      nameSource: 'BusinessNameRegistry',
      pageName: '页面名称未登记',
      pageTitle: '页面名称未登记',
      browserTitle: '页面名称未登记',
      displayName: '页面名称未登记',
      moduleCode: '',
      businessObject: '',
      route: String(query.route || ''),
    })
  }
  return Object.freeze({
    ...record,
    headerName: record.pageTitle,
    internalTitle: record.pageTitle,
    result: 'PASS',
    nameSource: 'BusinessNameRegistry',
  })
}

export function applyConsumedBrowserTitle(consumption, documentRef = globalThis.document) {
  if (!documentRef || consumption?.result !== 'PASS') return ''
  return applyPageDocumentTitle(consumption.route, documentRef, consumption.browserTitle)
}
