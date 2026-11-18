import { resolvePageNameConsumption } from './pageNameConsumer.js'

export const PAGE_NAME_CONSUMPTION_GOVERNANCE_VERSION = 'V1.14.2.8.18.10.3.6'

export const PAGE_NAME_CONSUMPTION_PROFILES = Object.freeze([
  ['purchase-request','/scm/purchase-request','src/meta/pages/ScmPurchaseRequestPage.vue','SCM'],
  ['inquiry-preparation','/scm/inquiry-preparations','src/meta/pages/ScmInquiryPreparationPage.vue','SCM'],
  ['purchase-inquiry','/scm/purchase-inquiry','src/meta/pages/ScmPurchaseInquiryNodePage.vue','SCM'],
  ['supplier-quote-workbench','/scm/supplier-quotes','src/meta/pages/ScmSupplierQuoteWorkbenchPage.vue','SCM'],
  ['quote-comparison-workbench','/scm/quote-comparisons','src/meta/pages/ScmQuoteComparisonWorkbenchPage.vue','SCM'],
  ['inventory-balances','/wms/inventory-balances','src/meta/pages/WmsPage.vue','WMS'],
  ['incoming-inspection','/qms/incoming-inspections','src/meta/pages/QmsPage.vue','QMS'],
  ['purchase-approval','/scm/purchase-approvals','src/meta/pages/PurchaseApprovalExecutionPage.vue','SCM'],
  ['payable-prepare','/finance/payable-prepares','src/meta/pages/PayablePreparePage.vue','FIN'],
].map(([pageCode, route, componentFile, moduleCode]) => Object.freeze({
  pageCode,
  route,
  componentFile,
  moduleCode,
  headerConsumer: 'BusinessNameRegistry',
  browserTitleConsumer: 'BusinessNameRegistry',
  internalTitleConsumer: 'BusinessNameRegistry',
})))

export function createPageNameConsumerReport() {
  return PAGE_NAME_CONSUMPTION_PROFILES.map(profile => {
    const name = resolvePageNameConsumption({ pageCode: profile.pageCode, route: profile.route })
    const aligned = name.result === 'PASS'
      && name.pageTitle === name.headerName
      && name.headerName === name.browserTitle
      && name.browserTitle === name.internalTitle
    return Object.freeze({
      page: name.pageName,
      pageCode: profile.pageCode,
      route: profile.route,
      componentFile: profile.componentFile,
      registryName: name.pageName,
      headerName: name.headerName,
      browserTitle: name.browserTitle,
      internalTitle: name.internalTitle,
      businessObject: name.businessObject,
      moduleCode: name.moduleCode,
      nameSource: name.nameSource,
      result: aligned ? 'PASS' : 'FAIL',
    })
  })
}

export function validatePageNameConsumptionGovernance() {
  const rows = createPageNameConsumerReport()
  const failures = rows.filter(row => row.result !== 'PASS')
  return Object.freeze({
    ruleCode: 'NAME-GOV-003',
    result: failures.length ? 'FAIL' : 'PASS',
    pageCount: rows.length,
    rows,
    failures,
  })
}
