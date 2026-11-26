export const PCE_PAGE_VIEW_GOVERNANCE_STANDARD_VERSION = 'PCE-ERP-PAGE-VIEW-GOVERNANCE-V1.0'

export const PCE_PAGE_VIEW_MODES = Object.freeze(['business_view', 'acceptance_view'])

export const PCE_PAGE_VIEW_GOVERNANCE_STANDARD = Object.freeze({
  standardCode: 'PCE_ERP_PAGE_VIEW_GOVERNANCE_STANDARD',
  version: PCE_PAGE_VIEW_GOVERNANCE_STANDARD_VERSION,
  modes: PCE_PAGE_VIEW_MODES,
  defaultRules: Object.freeze({ normalUser: 'business_view', developmentAcceptance: 'acceptance_view' }),
  businessView: Object.freeze({
    audiences: Object.freeze(['business_user', 'business_manager', 'management_user']),
    purpose: 'complete_business_work',
    requiredSections: Object.freeze(['currentBusinessStage', 'businessStatus', 'keyEvidence', 'judgementResult', 'nextBusinessHint']),
    hiddenTechnicalContent: Object.freeze(['runtimeName', 'domainObjectName', 'guardName', 'acceptanceResult', 'technicalStatusCode']),
  }),
  acceptanceView: Object.freeze({
    audiences: Object.freeze(['developer', 'implementation', 'tester']),
    purpose: 'complete_system_acceptance',
    requiredSections: Object.freeze(['domainStatus', 'runtimeStatus', 'guardStatus', 'acceptanceResult', 'dataProtectionStatus', 'automaticVerificationStatus']),
  }),
  sharedBusinessModel: true,
  presentationSeparated: true,
  viewSwitchChangesPermission: false,
  viewSwitchChangesBusinessState: false,
  viewSwitchCreatesObject: false,
  viewSwitchStartsWorkflow: false,
  viewSwitchWritesDatabase: false,
})

export function validatePcePageViewGovernanceStandard(standard = PCE_PAGE_VIEW_GOVERNANCE_STANDARD) {
  const valid = standard.standardCode === 'PCE_ERP_PAGE_VIEW_GOVERNANCE_STANDARD'
    && standard.modes.join('|') === 'business_view|acceptance_view'
    && standard.defaultRules.normalUser === 'business_view' && standard.defaultRules.developmentAcceptance === 'acceptance_view'
    && standard.businessView.requiredSections.length === 5 && standard.businessView.hiddenTechnicalContent.length === 5
    && standard.acceptanceView.requiredSections.length === 6
    && standard.sharedBusinessModel === true && standard.presentationSeparated === true
    && standard.viewSwitchChangesPermission === false && standard.viewSwitchChangesBusinessState === false
    && standard.viewSwitchCreatesObject === false && standard.viewSwitchStartsWorkflow === false
    && standard.viewSwitchWritesDatabase === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
