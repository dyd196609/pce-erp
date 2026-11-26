export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_VERSION = 'V1.14.2.8.7.6.1'

const member = (memberCode, label, validationScope, assertions) => Object.freeze({
  memberCode, label, validationScope, assertions: Object.freeze(assertions),
  dataSource: 'synthetic_definition', environment: 'canary', productionConnected: false,
})

export const FORMAL_PRICE_APPROVAL_CANARY_COHORT_MEMBERS = Object.freeze([
  member('business_view_canary', '业务视图金丝雀', 'business_view', ['business_language', 'next_step_clarity', 'technical_content_hidden']),
  member('acceptance_view_canary', '验收视图金丝雀', 'acceptance_view', ['governance_complete', 'guard_visible', 'zero_write_visible']),
  member('isolation_guard_canary', '隔离保护金丝雀', 'protection_boundary', ['no_business_execution', 'no_workflow', 'no_persistence']),
])

export const FORMAL_PRICE_APPROVAL_CANARY_COHORT = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_COHORT',
  version: FORMAL_PRICE_APPROVAL_CANARY_COHORT_VERSION,
  cohortNo: 'FPA-CANARY-COHORT-DEFINITION-001',
  environment: 'canary',
  members: FORMAL_PRICE_APPROVAL_CANARY_COHORT_MEMBERS,
  memberCount: FORMAL_PRICE_APPROVAL_CANARY_COHORT_MEMBERS.length,
  executionMode: 'automatic_validation_only',
  productionConnected: false,
  isProduction: false,
  persisted: false,
  businessWriteCount: 0,
  productionDataWritten: false,
})

export function validateFormalPriceApprovalCanaryCohort(model = FORMAL_PRICE_APPROVAL_CANARY_COHORT) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_CANARY_COHORT'
    && model.environment === 'canary' && model.memberCount === 3 && model.members.length === 3
    && model.members.every(item => item.environment === 'canary' && item.dataSource === 'synthetic_definition'
      && item.productionConnected === false && item.assertions.length === 3)
    && model.executionMode === 'automatic_validation_only' && model.productionConnected === false
    && model.isProduction === false && model.persisted === false
    && model.businessWriteCount === 0 && model.productionDataWritten === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
