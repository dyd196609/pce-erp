export const ENTERPRISE_ACCEPTANCE_TEMPLATE_RESOLVER_VERSION = 'V1.14.2.8.4.22'
export const SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE = 'SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE'
export const ENTERPRISE_PAGE_COMMON_TEMPLATE = 'ENTERPRISE_PAGE_COMMON_TEMPLATE'

const PAGE_TEMPLATE_MAP = Object.freeze({ SCM_PURCHASE_REQUEST: SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE })
const MODULE_TEMPLATE_MAP = Object.freeze({ SCM: SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE })

export function resolveEnterpriseAcceptanceTemplate(page = {}) {
  if (page.result !== 'PASS' || !page.pageCode) return Object.freeze({ result: 'UNKNOWN', templateCode: '', matchType: 'none', error: { code: 'PAGE_UNRESOLVED', message: page.error?.message || page.pageCode || '' } })
  if (PAGE_TEMPLATE_MAP[page.pageCode]) return Object.freeze({ result: 'PASS', templateCode: PAGE_TEMPLATE_MAP[page.pageCode], sourceTemplateCode: 'PCE-SCM-BUSINESS-PAGE-ACCEPTANCE-V1', matchType: 'pageCode' })
  if (MODULE_TEMPLATE_MAP[page.moduleCode]) return Object.freeze({ result: 'PASS', templateCode: MODULE_TEMPLATE_MAP[page.moduleCode], sourceTemplateCode: 'PCE-SCM-BUSINESS-PAGE-ACCEPTANCE-V1', matchType: 'moduleCode' })
  if (page.moduleCode) return Object.freeze({ result: 'PASS', templateCode: ENTERPRISE_PAGE_COMMON_TEMPLATE, sourceTemplateCode: 'PCE-ENTERPRISE-PAGE-ACCEPTANCE-MASTER-V1', matchType: 'common' })
  return Object.freeze({ result: 'UNKNOWN', templateCode: '', matchType: 'none', error: { code: 'TEMPLATE_NOT_RESOLVED', message: page.pageCode } })
}
