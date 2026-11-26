export const FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE_VERSION = 'V1.14.2.8.7.5'

const mode = (viewMode, userRole, displaySections, hiddenSections, validationScope) => Object.freeze({
  viewMode, userRole: Object.freeze(userRole), displaySections: Object.freeze(displaySections),
  hiddenSections: Object.freeze(hiddenSections), validationScope,
  permissionChanged: false, businessStateChanged: false, objectCreated: false, workflowStarted: false,
})

export const FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODES = Object.freeze([
  mode('business_view', ['purchase_buyer', 'purchase_manager', 'management_user'],
    ['inquiry_overview', 'quotation_situation', 'price_comparison', 'approval_preparation', 'next_business_hint'],
    ['runtime_name', 'domain_object_name', 'guard_name', 'acceptance_result', 'technical_status_code'], 'business_understanding'),
  mode('acceptance_view', ['developer', 'implementation', 'tester'],
    ['domain_status', 'runtime_status', 'guard_status', 'acceptance_result', 'data_protection_status', 'automatic_verification_status'],
    [], 'system_acceptance'),
])

export const FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE',
  version: FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE_VERSION,
  defaultViewMode: 'business_view',
  modes: FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODES,
  modeCount: 2,
  sharedBusinessModel: true,
  presentationSeparated: true,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalPageViewMode(model = FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE'
    && model.defaultViewMode === 'business_view' && model.modeCount === 2
    && model.modes.map((item) => item.viewMode).join('|') === 'business_view|acceptance_view'
    && model.modes.every((item) => item.permissionChanged === false && item.businessStateChanged === false
      && item.objectCreated === false && item.workflowStarted === false)
    && model.modes[0].displaySections.length === 5 && model.modes[0].hiddenSections.length === 5
    && model.modes[1].displaySections.length === 6
    && model.sharedBusinessModel === true && model.presentationSeparated === true
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
