import { PURCHASE_INQUIRY_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryAcceptanceProfile.js'
import { PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryRuntimeAcceptanceProfile.js'
import { SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE } from '../scm/supplierQuotationRuntimeAcceptanceProfile.js'
import { PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE } from '../scm/priceReviewPreparationAcceptanceProfile.js'
import { PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE } from '../scm/priceApprovalEntryAssessmentAcceptanceProfile.js'
import { PRICE_APPROVAL_CREATION_FREEZE_ACCEPTANCE_PROFILE } from '../scm/priceApprovalCreationFreezeAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalProjectionAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalObjectAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalRuntimeAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalCreationSimulationAcceptanceProfile.js'
import { CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE } from '../scm/createFormalPriceApprovalCommandAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalCreationAuthorizationAuditAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalFinalReleaseAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalSandboxAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalReleaseAgreementAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalExecutionBoundaryAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalEndToEndSafetyDrillAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalPostCreationStateTakeoverAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalPostCreationLifecycleAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalWorkflowHandoffAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalWorkflowStartAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalInstanceLifecycleAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalWorkflowRuntimeAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalNodeDecisionAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalFeedbackAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalAuditArchiveAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalGovernanceSummaryAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalOperationValidationAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalBusinessViewUserAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalNavigationAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalScenarioAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalViewSeparationAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalUserAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalHumanAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalCanaryCohortAcceptanceProfile.js'
import { FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE } from '../scm/formalPriceApprovalHumanBusinessAcceptanceProfile.js'
import { PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE } from '../scm/purchaseRequestInquiryMappingAcceptanceProfile.js'
import { INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE } from '../scm/inquiryCreationSimulationSupplierPreparationAcceptanceProfile.js'
import { PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE } from '../scm/purchaseRequestSubmitSelectionFixAcceptanceProfile.js'
import { PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE } from '../scm/purchaseRequestBusinessActionClosureAcceptanceProfile.js'
import { PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_ACCEPTANCE_PROFILE } from '../scm/purchaseRequestInquiryPreparationCreationAcceptanceProfile.js'
import { PURCHASE_INQUIRY_PREPARATION_PROVIDER_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryPreparationProviderAcceptanceProfile.js'
import { PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryActivationAcceptanceProfile.js'
import { PURCHASE_INQUIRY_ENTRY_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryEntryAcceptanceProfile.js'
import { PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryLifecycleWorkbenchAcceptanceProfile.js'
import { PURCHASE_INQUIRY_LIFECYCLE_REGRESSION_ACCEPTANCE_PROFILE } from '../scm/purchaseInquiryLifecycleRegressionAcceptanceProfile.js'
import { PURCHASE_INQUIRY_BUSINESS_RULES } from '../../domain/scm/purchaseInquiry/rules/purchaseInquiryBusinessRules.js'
import { PURCHASE_INQUIRY_STATE_TRANSITION_RULES } from '../../domain/scm/purchaseInquiry/rules/purchaseInquiryStateTransitionRules.js'
import { PURCHASE_INQUIRY_ACTION_GUARD_RULES } from '../../domain/scm/purchaseInquiry/rules/purchaseInquiryActionGuardRules.js'
import { PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE_CODE } from '../../domain/scm/purchaseInquiry/purchaseInquiryFinancialBoundary.js'
import {
  SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE,
  SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE,
} from '../scm/supplierQuoteComparisonAcceptanceProfiles.js'
import { SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE } from '../scm/supplierRecommendationDecisionAcceptanceProfiles.js'
import { SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE } from '../scm/purchaseOrderCreationGateAcceptanceProfiles.js'
import { SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE } from '../scm/purchaseOrderDomainAcceptanceProfiles.js'
import { SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE } from '../scm/purchaseOrderTransactionBoundaryAcceptanceProfiles.js'
import { SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE } from '../scm/purchaseOrderApprovalInterfaceAcceptanceProfiles.js'
import { SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE } from '../scm/purchaseOrderTransactionAcceptanceProfiles.js'
import { SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE } from '../scm/purchaseOrderIssueBoundaryAcceptanceProfiles.js'
import { SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE } from '../scm/scmPurchaseLifecycleFreezeAcceptanceProfiles.js'

export const ENTERPRISE_ACCEPTANCE_REGISTRY_VERSION = 'V1.14.2.8.4.24'

const freezeList = values => Object.freeze([...values])

export const SCM_PURCHASE_INQUIRY_RULE_PROFILE = Object.freeze({
  profileCode: 'SCM_PURCHASE_INQUIRY_RULE_PROFILE',
  version: 'V1.14.2.8.5.2',
  moduleCode: 'SCM',
  objectCode: 'SCM_PURCHASE_INQUIRY',
  stateRules: PURCHASE_INQUIRY_STATE_TRANSITION_RULES,
  businessRules: PURCHASE_INQUIRY_BUSINESS_RULES,
  actionGuards: PURCHASE_INQUIRY_ACTION_GUARD_RULES,
  financeGuards: freezeList([PURCHASE_INQUIRY_FINANCIAL_BOUNDARY_RULE_CODE]),
  activationMode: 'read_only',
  mode: 'read_only',
  businessWriteCount: 0,
  productionUserDataWritten: false,
})

const SCM_REGISTRATION = Object.freeze({
  moduleCode: 'SCM',
  moduleName: '供应链管理',
  readOnlyActivation: true,
  objects: freezeList([
    'SCM_PURCHASE_REQUEST',
    'SCM_PURCHASE_INQUIRY',
    'SCM_PURCHASE_ORDER',
  ]),
  objectRegistrations: freezeList([
    PURCHASE_INQUIRY_ACCEPTANCE_PROFILE,
    PURCHASE_INQUIRY_RUNTIME_ACCEPTANCE_PROFILE,
    SUPPLIER_QUOTATION_RUNTIME_ACCEPTANCE_PROFILE,
    PRICE_REVIEW_PREPARATION_ACCEPTANCE_PROFILE,
    PRICE_APPROVAL_ENTRY_ASSESSMENT_ACCEPTANCE_PROFILE,
    PRICE_APPROVAL_CREATION_FREEZE_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_PROJECTION_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_OBJECT_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_RUNTIME_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_CREATION_SIMULATION_ACCEPTANCE_PROFILE,
    CREATE_FORMAL_PRICE_APPROVAL_COMMAND_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION_AUDIT_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_SANDBOX_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_RELEASE_AGREEMENT_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_WORKFLOW_START_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_NODE_DECISION_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_FEEDBACK_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_AUDIT_ARCHIVE_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_USER_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_NAVIGATION_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_SCENARIO_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_VIEW_SEPARATION_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_CANARY_COHORT_ACCEPTANCE_PROFILE,
    FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_PROFILE,
    PURCHASE_REQUEST_INQUIRY_MAPPING_ACCEPTANCE_PROFILE,
    INQUIRY_CREATION_SIMULATION_SUPPLIER_PREPARATION_ACCEPTANCE_PROFILE,
    PURCHASE_REQUEST_SUBMIT_SELECTION_FIX_ACCEPTANCE_PROFILE,
    PURCHASE_REQUEST_BUSINESS_ACTION_CLOSURE_ACCEPTANCE_PROFILE,
    PURCHASE_REQUEST_INQUIRY_PREPARATION_CREATION_ACCEPTANCE_PROFILE,
    PURCHASE_INQUIRY_PREPARATION_PROVIDER_ACCEPTANCE_PROFILE,
    PURCHASE_INQUIRY_ACTIVATION_ACCEPTANCE_PROFILE,
    PURCHASE_INQUIRY_ENTRY_ACCEPTANCE_PROFILE,
    PURCHASE_INQUIRY_LIFECYCLE_WORKBENCH_ACCEPTANCE_PROFILE,
    PURCHASE_INQUIRY_LIFECYCLE_REGRESSION_ACCEPTANCE_PROFILE,
    SCM_SUPPLIER_QUOTE_ACCEPTANCE_PROFILE,
    SCM_QUOTE_COMPARISON_ACCEPTANCE_PROFILE,
    SCM_SUPPLIER_RECOMMENDATION_DECISION_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_ORDER_CREATION_GATE_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_ORDER_DOMAIN_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_ORDER_TRANSACTION_BOUNDARY_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_ORDER_APPROVAL_INTERFACE_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_ORDER_TRANSACTION_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_ORDER_ISSUE_BOUNDARY_ACCEPTANCE_PROFILE,
    SCM_PURCHASE_LIFECYCLE_MODEL_FREEZE_ACCEPTANCE_PROFILE,
  ]),
  ruleProfiles: freezeList([SCM_PURCHASE_INQUIRY_RULE_PROFILE]),
  pages: freezeList([
    Object.freeze({
      pageCode: 'SCM_PURCHASE_REQUEST',
      pageUrl: '/scm/purchase-request',
      businessObject: 'PurchaseRequest',
    }),
    Object.freeze({
      pageCode: 'SCM_PURCHASE_INQUIRY',
      pageUrl: '/scm/purchase-inquiry',
      businessObject: 'PurchaseInquiry',
    }),
    Object.freeze({
      pageCode: 'SCM_PURCHASE_INQUIRY_CREATE',
      pageUrl: '/scm/purchase-inquiry/create',
      businessObject: 'PurchaseInquiry',
    }),
  ]),
  templates: freezeList(['SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2']),
  templateStack: freezeList([
    'ENTERPRISE_PAGE_MASTER_TEMPLATE',
    'ENTERPRISE_PAGE_COMMON_CHECKLIST',
    'SCM_BUSINESS_PAGE_ACCEPTANCE_TEMPLATE_V2',
  ]),
  evidenceCollectors: freezeList([
    'ROUTE_EVIDENCE_COLLECTOR',
    'PAGE_IDENTITY_COLLECTOR',
    'SERVER_FACTS_COLLECTOR',
    'API_EVIDENCE_COLLECTOR',
    'LIST_CONTRACT_COLLECTOR',
    'NAVIGATION_COLLECTOR',
    'ACTION_EVIDENCE_COLLECTOR',
    'DATABASE_PROTECTION_COLLECTOR',
    'PERFORMANCE_COLLECTOR',
    'BROWSER_EVIDENCE_COLLECTOR',
  ]),
  collectorAliases: Object.freeze({
    SCM_TRACE_COLLECTOR: 'SERVER_FACTS_COLLECTOR',
    SCM_ACTION_COLLECTOR: 'ACTION_EVIDENCE_COLLECTOR',
  }),
  rules: freezeList([
    'SCM_OBJECT_RULE',
    'SCM_STATUS_RULE',
    'SCM_TRACE_RULE',
    'SCM_ACTION_RULE',
    'SCM_FINANCIAL_BOUNDARY_RULE',
    'SCM_CANARY_ISOLATION_RULE',
    'SCM_DATA_PROTECTION_RULE',
    'SCM_RELATIONSHIP_DIRECTION_RULE',
  ]),
  runner: Object.freeze({
    runnerCode: 'ENTERPRISE_PAGE_ACCEPTANCE_RUNNER',
    executionMode: 'read_only',
    pageUrl: '/scm/purchase-request',
  }),
  archive: Object.freeze({
    archiveCode: 'ENTERPRISE_PAGE_ACCEPTANCE_ARCHIVE',
    writer: 'enterprisePageAcceptanceRunnerArchiveWriter',
    root: 'test-results/page-acceptance',
    immutable: true,
  }),
})

export const ENTERPRISE_ACCEPTANCE_REGISTRY = Object.freeze({
  registryVersion: 'V1',
  version: ENTERPRISE_ACCEPTANCE_REGISTRY_VERSION,
  activationMode: 'read_only',
  modules: Object.freeze([SCM_REGISTRATION]),
})

export function listEnterpriseAcceptanceModuleRegistrations() {
  return ENTERPRISE_ACCEPTANCE_REGISTRY.modules
}

export function getEnterpriseAcceptanceModuleRegistration(moduleCode = '') {
  return ENTERPRISE_ACCEPTANCE_REGISTRY.modules.find(item => item.moduleCode === String(moduleCode).trim().toUpperCase()) || null
}

export function validateEnterpriseAcceptanceRegistration(registration) {
  if (!registration) return Object.freeze({ valid: false, result: 'FAIL', missing: Object.freeze(['module']) })
  const missing = []
  if (!registration.moduleCode) missing.push('moduleCode')
  if (!registration.moduleName) missing.push('moduleName')
  if (!registration.readOnlyActivation) missing.push('readOnlyActivation')
  if (!registration.objects?.length) missing.push('objects')
  if (!registration.objectRegistrations?.length) missing.push('objectRegistrations')
  if (!registration.ruleProfiles?.length) missing.push('ruleProfiles')
  if (!registration.templates?.length) missing.push('templates')
  if (!registration.templateStack?.length) missing.push('templateStack')
  if (!registration.evidenceCollectors?.length) missing.push('evidenceCollectors')
  if (!registration.rules?.length) missing.push('rules')
  if (!registration.runner?.runnerCode || registration.runner.executionMode !== 'read_only') missing.push('runner')
  if (!registration.archive?.archiveCode || !registration.archive?.writer || !registration.archive?.root || registration.archive.immutable !== true) missing.push('archive')
  return Object.freeze({ valid: missing.length === 0, result: missing.length === 0 ? 'PASS' : 'FAIL', missing: Object.freeze(missing) })
}
