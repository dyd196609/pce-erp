export const FORMAL_PRICE_APPROVAL_VIEW_SWITCHER_VERSION = 'V1.14.2.8.7.4'

export const FORMAL_PRICE_APPROVAL_VIEW_SWITCHER = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_VIEW_SWITCHER',
  version: FORMAL_PRICE_APPROVAL_VIEW_SWITCHER_VERSION,
  switchMode: 'presentation_only',
  allowedModes: Object.freeze(['business_view', 'acceptance_view']),
  persisted: false,
  routeChanged: false,
  businessActionTriggered: false,
  workflowTriggered: false,
  governanceModelDeleted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalViewSwitcher(model = FORMAL_PRICE_APPROVAL_VIEW_SWITCHER) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_VIEW_SWITCHER'
    && model.switchMode === 'presentation_only'
    && model.allowedModes.join('|') === 'business_view|acceptance_view'
    && model.persisted === false && model.routeChanged === false && model.businessActionTriggered === false
    && model.workflowTriggered === false && model.governanceModelDeleted === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
