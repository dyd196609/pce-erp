import { evaluatePurchaseInquiryActionGuard } from '../domain/scm/purchaseInquiry/rules/purchaseInquiryActionGuardRules.js'
import { PURCHASE_INQUIRY_TASK_MODEL } from '../domain/scm/purchaseInquiry/runtime/purchaseInquiryTaskModel.js'
import { mapPurchaseInquiryServerFact } from '../schema/scm/purchaseInquiryRuntimeMapping.js'
import { mapSupplierInquiryTaskFact, mapSupplierQuotationFact } from '../schema/scm/supplierQuotationRuntimeMapping.js'
import { mapPriceReviewPreparationFact, mapQuotationComparisonFact } from '../schema/scm/priceReviewPreparationRuntimeMapping.js'
import { mapPriceApprovalEntryAssessmentFact } from '../schema/scm/priceApprovalEntryAssessmentRuntimeMapping.js'
import { mapPriceApprovalCreationAssessmentFact } from '../schema/scm/priceApprovalCreationAssessmentRuntimeMapping.js'
import { mapFormalPriceApprovalProjectionFact, mapPriceApprovalEvidencePackageFact } from '../schema/scm/formalPriceApprovalProjectionRuntimeMapping.js'
import { assessPurchaseInquiryActivation } from '../domain/scm/inquiryPreparation/purchaseInquiryActivationRule.js'
import { evaluatePurchaseInquiryActivationGuard } from '../domain/scm/inquiryPreparation/purchaseInquiryActivationGuard.js'
import { purchaseInquiryRuntimeStore } from './purchaseInquiryRuntimeStore.js'
import { buildMaterialSupplierCandidates } from '../process/scm/purchaseInquiry/materialSupplierCandidateContext.js'
import { resolvePurchaseInquiryBusinessState } from '../process/scm/purchaseInquiry/purchaseInquiryBusinessStateMapping.js'
import { normalizePurchaseInquirySupplierCandidate } from '../process/scm/purchaseInquiry/purchaseInquirySupplierCandidateContext.js'

export const PURCHASE_INQUIRY_RUNTIME_VERSION = 'V1.14.2.8.7.13.1'

const readSessionObjects = () => [...purchaseInquiryRuntimeStore.reload()]
const writeSessionObjects = objects => purchaseInquiryRuntimeStore.replace(objects)

export const PURCHASE_INQUIRY_RUNTIME = Object.freeze({
  runtimeCode: 'SCM_PURCHASE_INQUIRY_RUNTIME',
  version: PURCHASE_INQUIRY_RUNTIME_VERSION,
  pageRoutes: Object.freeze(['/scm/purchase-inquiry', '/scm/purchase-inquiry/create']),
  taskModelCode: PURCHASE_INQUIRY_TASK_MODEL.modelCode,
  batchPreparationRuleCode: 'SCM_PURCHASE_INQUIRY_BATCH_PREPARATION_RULE',
  batchPreparationAutomaticActivation: false,
  quotationRuntimeCode: 'SCM_PURCHASE_INQUIRY_QUOTATION_RUNTIME',
  priceReviewPreparationRuntimeCode: 'SCM_PURCHASE_INQUIRY_PRICE_REVIEW_PREPARATION_RUNTIME',
  priceApprovalEntryAssessmentRuntimeCode: 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_ENTRY_ASSESSMENT_RUNTIME',
  priceApprovalCreationAssessmentRuntimeCode: 'SCM_PURCHASE_INQUIRY_PRICE_APPROVAL_CREATION_FREEZE_RUNTIME',
  formalPriceApprovalProjectionRuntimeCode: 'SCM_PURCHASE_INQUIRY_FORMAL_PRICE_APPROVAL_PROJECTION_RUNTIME',
  formalPriceApprovalObjectModelCode: 'SCM_FORMAL_PRICE_APPROVAL_OBJECT',
  formalPriceApprovalObjectInstanceCount: 0,
  formalPriceApprovalRuntimeCode: 'SCM_FORMAL_PRICE_APPROVAL_RUNTIME',
  formalPriceApprovalCreationSimulationCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SIMULATION',
  formalPriceApprovalCreationSimulationBusinessObject: false,
  formalPriceApprovalCreationSimulationWriteCount: 0,
  createFormalPriceApprovalCommandCode: 'SCM_CREATE_FORMAL_PRICE_APPROVAL_COMMAND',
  createFormalPriceApprovalCommandTriggerMode: 'manual_only',
  createFormalPriceApprovalCommandDispatcherConnected: false,
  createFormalPriceApprovalCommandInstanceCount: 0,
  formalPriceApprovalCreationAuthorizationCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUTHORIZATION',
  formalPriceApprovalCreationAuthorizationExecutionPermission: false,
  formalPriceApprovalCreationAuditCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_AUDIT_TRAIL',
  formalPriceApprovalCreationAuditPersistenceMode: 'none',
  formalPriceApprovalFinalReleaseAssessmentCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_ASSESSMENT',
  formalPriceApprovalFinalReleaseIsExecution: false,
  formalPriceApprovalFinalReleaseGateCommandExecutor: false,
  formalPriceApprovalFinalReleaseAssessmentInstanceCount: 0,
  formalPriceApprovalCreationSandboxCode: 'SCM_FORMAL_PRICE_APPROVAL_CREATION_SANDBOX',
  formalPriceApprovalCreationSandboxEnvironment: 'sandbox',
  formalPriceApprovalCreationSandboxProductionEndpointConnected: false,
  formalPriceApprovalHumanConfirmationCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_CONFIRMATION',
  formalPriceApprovalHumanConfirmationExecutionPermission: false,
  formalPriceApprovalFinalReleaseAgreementCode: 'SCM_FORMAL_PRICE_APPROVAL_FINAL_RELEASE_AGREEMENT',
  formalPriceApprovalFinalReleaseAgreementExecutionPermission: false,
  formalPriceApprovalFinalReleaseAgreementInstanceCount: 0,
  formalPriceApprovalExecutionBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_BOUNDARY',
  formalPriceApprovalExecutionContextCode: 'SCM_FORMAL_PRICE_APPROVAL_EXECUTION_CONTEXT',
  formalPriceApprovalExecutionBoundaryExecutorConnected: false,
  formalPriceApprovalProductionExecution: false,
  formalPriceApprovalEndToEndSafetyDrillCode: 'SCM_FORMAL_PRICE_APPROVAL_END_TO_END_SAFETY_DRILL',
  formalPriceApprovalEndToEndSafetyDrillStageCount: 15,
  formalPriceApprovalEndToEndSafetyDrillExecutionMode: 'isolated_read_only',
  formalPriceApprovalEndToEndSafetyDrillProductionExecution: false,
  formalPriceApprovalPostCreationStateTakeoverCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_STATE_TAKEOVER',
  formalPriceApprovalPostCreationAutomaticTakeover: false,
  formalPriceApprovalPostCreationStateMutationAllowed: false,
  formalPriceApprovalPostCreationWorkflowEngineConnected: false,
  formalPriceApprovalPostCreationLifecycleStateMachineCode: 'SCM_FORMAL_PRICE_APPROVAL_POST_CREATION_LIFECYCLE_STATE_MACHINE',
  formalPriceApprovalPostCreationLifecycleTransitionCount: 4,
  formalPriceApprovalPostCreationLifecycleEnabledTransitionCount: 0,
  formalPriceApprovalPostCreationLifecyclePersistenceConnected: false,
  formalPriceApprovalWorkflowHandoffCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_HANDOFF',
  formalPriceApprovalWorkflowOwnershipCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_OWNERSHIP',
  formalPriceApprovalWorkflowHandoffMode: 'boundary_design_only',
  formalPriceApprovalWorkflowHandoffWorkflowConnected: false,
  formalPriceApprovalWorkflowHandoffInstanceCount: 0,
  formalPriceApprovalWorkflowHandoffApprovalTaskCount: 0,
  formalPriceApprovalWorkflowStartAssessmentCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_START_ASSESSMENT',
  formalPriceApprovalWorkflowInstanceBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_INSTANCE_BOUNDARY',
  formalPriceApprovalWorkflowStartAssessmentMode: 'assessment_only',
  formalPriceApprovalWorkflowStarted: false,
  formalPriceApprovalWorkflowRunning: false,
  formalPriceApprovalWorkflowInstanceCount: 0,
  formalPriceApprovalWorkflowApprovalTaskCount: 0,
  formalPriceApprovalInstanceLifecycleCode: 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_LIFECYCLE',
  formalPriceApprovalTaskLifecycleCode: 'SCM_FORMAL_PRICE_APPROVAL_TASK_LIFECYCLE',
  formalPriceApprovalInstanceTaskBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_INSTANCE_TASK_BOUNDARY',
  formalPriceApprovalInstanceTaskBoundaryMode: 'definition_only',
  formalPriceApprovalInstanceLifecycleEnabledTransitionCount: 0,
  formalPriceApprovalTaskLifecycleEnabledTransitionCount: 0,
  formalPriceApprovalApprovalInstanceCount: 0,
  formalPriceApprovalApprovalTaskCount: 0,
  formalPriceApprovalApprovalResultCount: 0,
  formalPriceApprovalWorkflowRuntimeStateCode: 'SCM_FORMAL_PRICE_APPROVAL_WORKFLOW_RUNTIME_STATE',
  formalPriceApprovalResultBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_RESULT_BOUNDARY',
  formalPriceApprovalWorkflowRuntimeCurrentState: 'definition_only',
  formalPriceApprovalWorkflowRuntimeEnabledTransitionCount: 0,
  formalPriceApprovalWorkflowRuntimeInstanceCount: 0,
  formalPriceApprovalWorkflowRuntimeStarted: false,
  formalPriceApprovalWorkflowRuntimeRunning: false,
  formalPriceApprovalWorkflowRuntimeCompleted: false,
  formalPriceApprovalResultCount: 0,
  formalPriceApprovalNodeDefinitionCode: 'SCM_FORMAL_PRICE_APPROVAL_NODE_DEFINITION',
  formalPriceApprovalDecisionRuleCode: 'SCM_FORMAL_PRICE_APPROVAL_DECISION_RULE',
  formalPriceApprovalNodeDecisionBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_NODE_DECISION_BOUNDARY',
  formalPriceApprovalNodeDefinitionCount: 3,
  formalPriceApprovalNodeRuntimeCount: 0,
  formalPriceApprovalNodeTaskCount: 0,
  formalPriceApprovalNodeDecisionResultCount: 0,
  formalPriceApprovalNodeDecisionBusinessEffectApplied: false,
  formalPriceApprovalCommentModelCode: 'SCM_FORMAL_PRICE_APPROVAL_COMMENT',
  formalPriceApprovalEvidenceFeedbackModelCode: 'SCM_FORMAL_PRICE_APPROVAL_EVIDENCE_FEEDBACK',
  formalPriceApprovalFeedbackBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_FEEDBACK_BOUNDARY',
  formalPriceApprovalCommentInstanceCount: 0,
  formalPriceApprovalEvidenceFeedbackInstanceCount: 0,
  formalPriceApprovalFeedbackTaskExecution: false,
  formalPriceApprovalFeedbackResultCount: 0,
  formalPriceApprovalFeedbackBusinessChangeApplied: false,
  formalPriceApprovalAuditTrailCode: 'SCM_FORMAL_PRICE_APPROVAL_AUDIT_TRAIL',
  formalPriceApprovalEvidenceArchiveBoundaryCode: 'SCM_FORMAL_PRICE_APPROVAL_EVIDENCE_ARCHIVE_BOUNDARY',
  formalPriceApprovalAuditDefinitionCount: 6,
  formalPriceApprovalArchiveBoundaryCount: 1,
  formalPriceApprovalAuditPersistedRecordCount: 0,
  formalPriceApprovalAuditPersisted: false,
  formalPriceApprovalEvidenceArchivePersisted: false,
  formalPriceApprovalAuditApprovalExecution: false,
  formalPriceApprovalAuditBusinessEffectApplied: false,
  formalPriceApprovalGovernanceSummaryCode: 'SCM_FORMAL_PRICE_APPROVAL_GOVERNANCE_SUMMARY',
  formalPriceApprovalGovernanceStageMatrixCode: 'SCM_FORMAL_PRICE_APPROVAL_GOVERNANCE_STAGE_MATRIX',
  formalPriceApprovalOperationReadinessCode: 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_READINESS',
  formalPriceApprovalGovernanceStageCount: 12,
  formalPriceApprovalGovernancePassedStageCount: 12,
  formalPriceApprovalGovernanceExecutionEnabledStageCount: 0,
  formalPriceApprovalOperationReadinessStatus: 'validation_ready',
  formalPriceApprovalOperationEnabled: false,
  formalPriceApprovalAutoRunEnabled: false,
  formalPriceApprovalOperationValidationScenarioCode: 'SCM_FORMAL_PRICE_APPROVAL_OPERATION_VALIDATION_SCENARIO',
  formalPriceApprovalBusinessViewCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW',
  formalPriceApprovalOperationValidationStatus: 'validation_ready',
  formalPriceApprovalOperationValidationScenarioCount: 4,
  formalPriceApprovalBusinessViewSectionCount: 4,
  formalPriceApprovalProductionOperationEnabled: false,
  formalPriceApprovalBusinessExecutionEnabled: false,
  formalPriceApprovalBusinessViewOptimizationCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_VIEW_OPTIMIZATION',
  formalPriceApprovalUserAcceptancePreparationCode: 'SCM_FORMAL_PRICE_APPROVAL_USER_ACCEPTANCE_PREPARATION',
  formalPriceApprovalBusinessViewOptimizationStatus: 'user_acceptance_ready',
  formalPriceApprovalUserAcceptancePreparationStatus: 'ready_for_user_acceptance',
  formalPriceApprovalOptimizedViewItemCount: 4,
  formalPriceApprovalUserAcceptanceChecklistCount: 5,
  formalPriceApprovalUserAcceptancePassedChecklistCount: 5,
  formalPriceApprovalOperationApprovalGranted: false,
  formalPriceApprovalBusinessNavigationCode: 'SCM_FORMAL_PRICE_APPROVAL_BUSINESS_NAVIGATION',
  formalPriceApprovalRoleNavigationViewCode: 'SCM_FORMAL_PRICE_APPROVAL_ROLE_NAVIGATION_VIEW',
  formalPriceApprovalBusinessNavigationStatus: 'ready_for_user_path_validation',
  formalPriceApprovalNavigationStepCount: 5,
  formalPriceApprovalRoleNavigationViewCount: 3,
  formalPriceApprovalNavigationRouteActionEnabled: false,
  formalPriceApprovalNavigationWorkflowRuntimeConnected: false,
  formalPriceApprovalNavigationAutoActionEnabled: false,
  formalPriceApprovalScenarioModelCode: 'SCM_FORMAL_PRICE_APPROVAL_SCENARIO',
  formalPriceApprovalScenarioStatus: 'ready_for_user_acceptance',
  formalPriceApprovalScenarioCount: 3,
  formalPriceApprovalNormalScenarioCount: 1,
  formalPriceApprovalSpecialScenarioCount: 1,
  formalPriceApprovalExceptionScenarioCount: 1,
  formalPriceApprovalScenarioProductionDataUsed: false,
  formalPriceApprovalScenarioAutoDecisionPerformed: false,
  formalPriceApprovalViewModeCode: 'SCM_FORMAL_PRICE_APPROVAL_VIEW_MODE',
  formalPriceApprovalViewSwitcherCode: 'SCM_FORMAL_PRICE_APPROVAL_VIEW_SWITCHER',
  formalPriceApprovalDefaultViewMode: 'business_view',
  formalPriceApprovalViewModeCount: 2,
  formalPriceApprovalViewSwitchMode: 'presentation_only',
  formalPriceApprovalViewSwitchBusinessActionTriggered: false,
  formalPriceApprovalHiddenGovernanceModelDeleted: false,
  formalPriceApprovalPageViewGovernanceStandardCode: 'PCE_ERP_PAGE_VIEW_GOVERNANCE_STANDARD',
  formalPriceApprovalPageViewModeCode: 'SCM_FORMAL_PRICE_APPROVAL_PAGE_VIEW_MODE',
  formalPriceApprovalUserAcceptanceFeedbackMode: 'session_only',
  formalPriceApprovalUserAcceptanceChecklistCount: 7,
  formalPriceApprovalUserAcceptancePassedChecklistCount: 7,
  formalPriceApprovalViewSwitchExecuted: true,
  formalPriceApprovalUserFeedbackPersisted: false,
  formalPriceApprovalUserFeedbackBusinessStateChanged: false,
  formalPriceApprovalCanaryAcceptanceCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE',
  formalPriceApprovalCanaryEnvironment: 'canary',
  formalPriceApprovalCanaryProductionConnected: false,
  formalPriceApprovalHumanRoleAcceptanceCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ROLE_ACCEPTANCE',
  formalPriceApprovalHumanRoleCount: 3,
  formalPriceApprovalHumanAcceptanceExecutionMode: 'session_validation_only',
  formalPriceApprovalHumanAcceptanceIsBusinessExecution: false,
  formalPriceApprovalFeedbackLoopCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_ACCEPTANCE_FEEDBACK_LOOP',
  formalPriceApprovalFeedbackLoopStorageMode: 'memory_session_only',
  formalPriceApprovalFeedbackLoopStateCount: 5,
  formalPriceApprovalFeedbackLoopPersisted: false,
  formalPriceApprovalFeedbackLoopIsErpData: false,
  formalPriceApprovalCanaryCohortCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_COHORT',
  formalPriceApprovalCanaryCohortMemberCount: 3,
  formalPriceApprovalCanaryCohortExecutionMode: 'automatic_validation_only',
  formalPriceApprovalCanaryAutomaticAcceptanceCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_AUTOMATIC_ACCEPTANCE',
  formalPriceApprovalCanaryAutomaticAcceptanceTriggerMode: 'manual_validation_trigger',
  formalPriceApprovalCanaryAutomaticAcceptanceIsBusinessExecution: false,
  formalPriceApprovalCanaryResultSummaryCode: 'SCM_FORMAL_PRICE_APPROVAL_CANARY_ACCEPTANCE_RESULT_SUMMARY',
  formalPriceApprovalCanaryResultSummaryStorageMode: 'memory_session_only',
  formalPriceApprovalCanaryResultPersisted: false,
  formalPriceApprovalCanaryResultIsApprovalResult: false,
  formalPriceApprovalRecentCanaryExecutionState: 'completed',
  formalPriceApprovalRecentCanaryTotalCount: 3,
  formalPriceApprovalRecentCanaryPassCount: 3,
  formalPriceApprovalRecentCanaryFailCount: 0,
  formalPriceApprovalRecentCanaryOverallResult: 'PASS',
  formalPriceApprovalHumanBusinessAcceptanceExecutionCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_BUSINESS_ACCEPTANCE_EXECUTION',
  formalPriceApprovalHumanBusinessAcceptanceRoleCount: 3,
  formalPriceApprovalHumanBusinessAcceptanceChecklistCount: 7,
  formalPriceApprovalHumanBusinessAcceptanceIsBusinessExecution: false,
  formalPriceApprovalHumanFeedbackCollectionCode: 'SCM_FORMAL_PRICE_APPROVAL_HUMAN_FEEDBACK_COLLECTION',
  formalPriceApprovalHumanFeedbackStorageMode: 'memory_session_only',
  formalPriceApprovalHumanFeedbackPersisted: false,
  formalPriceApprovalHumanFeedbackIsErpData: false,
  purchaseRequestInquiryMappingCode: 'SCM_PURCHASE_REQUEST_INQUIRY_MAPPING_VALIDATION',
  purchaseRequestInquiryMappingMode: 'simulation_validation_only',
  purchaseRequestInquiryMappingFieldCount: 8,
  purchaseRequestInquiryMappingRequiredFieldCount: 7,
  purchaseRequestInquiryMappingScenarioCount: 3,
  purchaseRequestInquiryMappingCreatesInquiry: false,
  purchaseRequestInquiryMappingSendsSupplier: false,
  purchaseRequestInquiryMappingCreatesQuotationTask: false,
  purchaseRequestInquiryMappingPersistsProjection: false,
  purchaseRequestInquirySourceTraceCreatesTransaction: false,
  inquiryCreationSimulationCode: 'SCM_INQUIRY_CREATION_SIMULATION',
  inquiryCreationSimulationMode: 'simulation_only',
  inquiryCreationSimulationPrerequisiteCheckCount: 4,
  inquiryCreationSimulationStatus: 'simulated_ready',
  inquiryCreationSimulationCreatesInquiry: false,
  supplierInquiryPreparationCode: 'SCM_SUPPLIER_INQUIRY_PREPARATION',
  supplierInquiryPreparationCandidateCount: 2,
  supplierInquiryPreparationStatus: 'prepared',
  supplierCandidateCreatesInquiryTask: false,
  supplierInquiryPreparationSendsSupplier: false,
  supplierInquiryPreparationCreatesQuotationTask: false,
  supplierInquiryPreparationPersisted: false,
  inquiryPreparationObjectCode: 'SCM_INQUIRY_PREPARATION_OBJECT',
  inquiryPreparationCreationMode: 'manual_session_runtime',
  inquiryPreparationStatus: 'prepared',
  inquiryPreparationCreatesFormalInquiry: false,
  inquiryPreparationCreatesQuotation: false,
  inquiryPreparationSendsSupplier: false,
  inquiryPreparationDatabaseWritten: false,
  inquiryPreparationProviderCode: 'SCM_INQUIRY_PREPARATION_PROVIDER',
  inquiryPreparationProviderFactOwner: 'inquiry-preparation',
  inquiryPreparationActivationRuleCode: 'SCM_PURCHASE_INQUIRY_ACTIVATION_RULE',
  inquiryPreparationActivationManualOnly: true,
  inquiryPreparationActivationTargetStatus: 'draft',
  factSource: 'server',
  createMode: 'memory_only',
  durableBusinessWriteCount: 0,
  databaseState: 'UNCHANGED',
  productionDataWritten: false,
})

export function buildPurchaseInquiryRuntimeView(facts = {}) {
  const combinedObjects = [...(facts.objects || [])]
  const knownInquiryNos = new Set(combinedObjects.map(item => item.inquiryNo || item.businessNo))
  listPurchaseInquiryRuntimeObjects().forEach(item => { if (!knownInquiryNos.has(item.inquiryNo)) combinedObjects.push(item) })
  const inquiries = Object.freeze(combinedObjects.map(item => {
    const mapped = mapPurchaseInquiryServerFact(item)
    return Object.freeze({ ...mapped, ...resolvePurchaseInquiryBusinessState(mapped) })
  }))
  const supplierInquiryTasks = Object.freeze((facts.supplierInquiryTasks || []).map(mapSupplierInquiryTaskFact))
  const supplierQuotations = Object.freeze((facts.supplierQuotations || []).map(mapSupplierQuotationFact))
  const quotationComparisons = Object.freeze((facts.quotationComparisons || []).map(mapQuotationComparisonFact))
  const priceReviewPreparations = Object.freeze((facts.priceReviewPreparations || []).map(mapPriceReviewPreparationFact))
  const priceApprovalEntryAssessments = Object.freeze((facts.priceApprovalEntryAssessments || []).map(mapPriceApprovalEntryAssessmentFact))
  const priceApprovalCreationAssessments = Object.freeze((facts.priceApprovalCreationAssessments || []).map(mapPriceApprovalCreationAssessmentFact))
  const formalPriceApprovalProjections = Object.freeze((facts.formalPriceApprovalProjections || []).map(mapFormalPriceApprovalProjectionFact))
  const priceApprovalEvidencePackages = Object.freeze((facts.priceApprovalEvidencePackages || []).map(mapPriceApprovalEvidencePackageFact))
  const statusStatistics = inquiries.reduce((summary, inquiry) => {
    const label = inquiry.statusLabel || '未提供状态'
    summary[label] = (summary[label] || 0) + 1
    return summary
  }, {})
  return Object.freeze({
    summary: Object.freeze({
      inquiryCount: inquiries.length,
      supplierCount: inquiries.reduce((total, item) => total + Number(item.supplierCount || 0), 0),
      lineCount: inquiries.reduce((total, item) => total + Number(item.lineCount || 0), 0),
    }),
    statusStatistics: Object.freeze(statusStatistics),
    inquiries,
    quotationRuntime: Object.freeze({
      supplierInquiryTasks,
      supplierQuotations,
      quotationComparisons,
      priceReviewPreparations,
      priceApprovalEntryAssessments,
      priceApprovalCreationAssessments,
      formalPriceApprovalProjections,
      priceApprovalEvidencePackages,
      automaticQuotationCreation: false,
      autoSupplierSelection: false,
      autoPriceApproval: false,
      formalPriceApprovalObjectCreated: false,
      approvalWorkflowStarted: false,
      approvalTaskCreated: false,
      autoPurchaseOrderCreation: false,
      readOnly: true,
    }),
    strictFacts: Object.freeze({ ...facts, objects: Object.freeze(combinedObjects), recordCount: combinedObjects.length,
      factSource: combinedObjects.length === (facts.objects || []).length ? (facts.factSource || 'server') : 'server+session_runtime' }),
  })
}

export function createPurchaseInquiryRuntimeObject(input = {}) {
  const guard = evaluatePurchaseInquiryActionGuard({ status: 'draft', action: 'edit' })
  if (guard.decision !== 'allow') throw new Error('询价草稿创建守卫未通过')
  if (!input.inquiryTitle || !input.inquiryDate || !input.buyerName) throw new Error('基本信息不完整')
  if (!Array.isArray(input.suppliers) || input.suppliers.length === 0) throw new Error('请至少选择一个供应商')
  if (!Array.isArray(input.lines) || input.lines.length === 0) throw new Error('请至少维护一行询价明细')
  const runtimeObject = Object.freeze({
    ...input,
    id: `PI-RUNTIME-${Date.now()}`,
    inquiryNo: `PI-DRAFT-${String(readSessionObjects().length + 1).padStart(4, '0')}`,
    statusCode: 'draft',
    statusLabel: '草稿',
    runtimeState: 'inquiry_draft',
    persistenceMode: 'memory_only',
    createdPurchaseOrder: false,
    sentToSupplier: false,
    paymentCreated: false,
    inventoryActionCreated: false,
    productionDataWritten: false,
  })
  writeSessionObjects([...readSessionObjects(), runtimeObject])
  return runtimeObject
}

export function listPurchaseInquiryRuntimeObjects() {
  return Object.freeze(readSessionObjects().map(item => Object.freeze(item)))
}

export function ensurePurchaseInquiryRuntimeDraft(inquiry = {}) {
  if (!inquiry.inquiryNo || inquiry.statusCode !== 'draft') throw new Error('PURCHASE_INQUIRY_DRAFT_CONTEXT_REQUIRED')
  const existing = readSessionObjects().find(item => item.inquiryNo === inquiry.inquiryNo)
  if (existing) return Object.freeze(existing)
  const runtimeObject = Object.freeze({ ...inquiry, id: inquiry.id || `PI-CONTEXT-${inquiry.inquiryNo}`,
    statusCode: 'draft', statusLabel: inquiry.statusLabel || '草稿', runtimeState: 'inquiry_draft',
    persistenceMode: 'session_runtime', sentToSupplier: false, supplierQuoteCreated: false,
    createdPurchaseOrder: false, financeObjectCreated: false, paymentCreated: false,
    inventoryActionCreated: false, productionDataWritten: false })
  writeSessionObjects([...readSessionObjects(), runtimeObject])
  return runtimeObject
}

export function updatePurchaseInquiryRuntimeState(inquiryNo = '', runtimeState = '') {
  const objects = readSessionObjects()
  const index = objects.findIndex(item => item.inquiryNo === inquiryNo)
  if (index < 0) throw new Error('PURCHASE_INQUIRY_RUNTIME_OBJECT_NOT_FOUND')
  if (!['inquiry_draft', 'quote_preparation_ready'].includes(runtimeState)) throw new Error('PURCHASE_INQUIRY_RUNTIME_STATE_INVALID')
  const state = resolvePurchaseInquiryBusinessState({ ...objects[index], statusCode: 'draft', runtimeState })
  const updated = Object.freeze({ ...objects[index], statusCode: 'draft', statusLabel: state.businessStatusLabel,
    businessStatusCode: state.businessStatusCode, businessStatusLabel: state.businessStatusLabel,
    runtimeState, processStatusCode: state.processStatusCode, processStatusLabel: state.processStatusLabel,
    quotePreparationReady: runtimeState === 'quote_preparation_ready', supplierQuoteCreated: false,
    sentToSupplier: false, createdPurchaseOrder: false, productionDataWritten: false })
  objects.splice(index, 1, updated)
  writeSessionObjects(objects)
  return updated
}

export function findPurchaseInquiryByPreparation(inquiryPreparationNo = '') {
  return listPurchaseInquiryRuntimeObjects().find(item => item.sourcePreparationNo === String(inquiryPreparationNo || '')) || null
}

export function beginPurchaseInquiryDraftEdit(inquiry = {}) {
  if (!inquiry.inquiryNo || inquiry.statusCode !== 'draft') throw new Error('仅草稿询价允许编辑')
  return Object.freeze({
    inquiryNo: inquiry.inquiryNo,
    inquiryTitle: inquiry.inquiryTitle || '',
    inquiryDate: inquiry.inquiryDate || '',
    buyerName: inquiry.buyerName || '',
    currency: inquiry.currency || 'CNY',
    runtimeState: 'inquiry_editing',
    sourcePreparationNo: inquiry.sourcePreparationNo || '',
    sourceRequestNo: inquiry.sourceRequestNo || '',
  })
}

export function savePurchaseInquiryDraft(draft = {}) {
  const objects = readSessionObjects()
  const index = objects.findIndex(item => item.inquiryNo === draft.inquiryNo)
  if (index < 0) throw new Error('询价草稿不存在')
  if (objects[index].statusCode !== 'draft' || draft.runtimeState !== 'inquiry_editing') throw new Error('询价草稿状态不允许保存')
  if (!String(draft.inquiryTitle || '').trim() || !String(draft.inquiryDate || '').trim() || !String(draft.buyerName || '').trim()) {
    throw new Error('询价主题、日期和采购员不能为空')
  }
  const draftLines = draft.materialLines || draft.lines || objects[index].lines || []
  const legacyCandidatesChanged = Boolean(draft.initialSupplierCandidateSnapshot)
    && JSON.stringify(draft.supplierCandidates || []) !== draft.initialSupplierCandidateSnapshot
  const materialCandidatesUnchanged = Boolean(draft.initialSupplierCandidateSnapshot)
    && draftLines.every(item => JSON.stringify(item.supplierCandidates || []) === draft.initialSupplierCandidateSnapshot)
  const savedLines = draftLines.map(item => {
    const candidates = legacyCandidatesChanged && materialCandidatesUnchanged
      ? (draft.supplierCandidates || []) : (item.supplierCandidates || [])
    return Object.freeze({ ...item, supplierCandidates: Object.freeze([...candidates]) })
  })
  const materialSupplierCandidates = buildMaterialSupplierCandidates(savedLines,
    draft.supplierCandidates || draft.suppliers || objects[index].suppliers || [])
  const supplierMap = new Map(savedLines.flatMap(line => line.supplierCandidates || [])
    .map(normalizePurchaseInquirySupplierCandidate)
    .map(candidate => [candidate.supplierCode, candidate]))
  const savedRuntimeState = draft.sourceRuntimeState === 'quote_preparation_ready'
    ? 'quote_preparation_ready' : 'inquiry_draft'
  const savedState = resolvePurchaseInquiryBusinessState({ ...objects[index], statusCode: 'draft',
    runtimeState: savedRuntimeState })
  const saved = Object.freeze({
    ...objects[index],
    inquiryTitle: String(draft.inquiryTitle).trim(),
    inquiryDate: String(draft.inquiryDate).trim(),
    buyerName: String(draft.buyerName).trim(),
    currency: draft.currency || objects[index].currency || 'CNY',
    lines: Object.freeze(savedLines), materialSupplierCandidates,
    suppliers: Object.freeze([...supplierMap.values()]),
    supplierCount: supplierMap.size, lineCount: savedLines.length,
    runtimeState: savedRuntimeState, processStatusCode: savedState.processStatusCode,
    processStatusLabel: savedState.processStatusLabel,
    lastSavedAt: new Date().toISOString(),
    sentToSupplier: false,
    supplierQuoteCreated: false,
    createdPurchaseOrder: false,
    financeObjectCreated: false,
    paymentCreated: false,
    productionDataWritten: false,
  })
  objects.splice(index, 1, saved)
  writeSessionObjects(objects)
  return Object.freeze({
    result: 'PASS',
    saved: true,
    object: saved,
    businessWriteCount: 1,
    persistenceMode: 'session_runtime',
    productionDataWritten: false,
  })
}

export function activatePurchaseInquiryFromPreparation(preparation = {}) {
  const existing = findPurchaseInquiryByPreparation(preparation.inquiryPreparationNo)
  const assessment = assessPurchaseInquiryActivation(preparation, existing)
  const guard = evaluatePurchaseInquiryActivationGuard('activatePurchaseInquiry')
  if (assessment.decision === 'return_existing') return Object.freeze({ result: 'PASS', created: false, idempotent: true,
    object: existing, assessment, guard, businessWriteCount: 0 })
  if (!assessment.eligible || !guard.allowed) return Object.freeze({ result: 'FAIL', created: false, idempotent: false,
    object: null, assessment, guard, businessWriteCount: 0 })
  const inquiryNo = `PI-${String(preparation.sourceRequestNo).replace(/^PR/, '')}`
  const runtimeObject = Object.freeze({ id: `PI-ACTIVATION-${preparation.inquiryPreparationNo}`, inquiryNo,
    inquiryTitle: `采购申请 ${preparation.sourceRequestNo} 询价`, inquiryDate: new Date().toISOString().slice(0, 10),
    sourcePreparationNo: preparation.inquiryPreparationNo, sourceRequestNo: preparation.sourceRequestNo,
    buyerName: preparation.requester || '', supplierCount: preparation.supplierCandidateCount ?? preparation.supplierCandidates?.length ?? 0,
    lineCount: preparation.materialLineCount ?? preparation.inquiryLines?.length ?? 0, currency: 'CNY',
    suppliers: Object.freeze([...(preparation.supplierCandidates || [])]), lines: Object.freeze([...(preparation.inquiryLines || [])]),
    statusCode: 'draft', statusLabel: '草稿', runtimeState: 'inquiry_draft', persistenceMode: 'session_runtime', activationMode: 'manual_only',
    quotationCount: 0, supplierQuoteCreated: false, sentToSupplier: false, quoteComparisonCreated: false,
    priceApprovalCreated: false, createdPurchaseOrder: false, financeObjectCreated: false, inventoryActionCreated: false,
    productionDataWritten: false })
  writeSessionObjects([...readSessionObjects(), runtimeObject])
  return Object.freeze({ result: 'PASS', created: true, idempotent: false, object: runtimeObject,
    assessment, guard, businessWriteCount: 1 })
}

export function evaluatePurchaseInquiryRuntimeGuard(action) {
  if (PURCHASE_INQUIRY_TASK_MODEL.forbiddenActions.includes(action)) {
    return Object.freeze({ result: 'PASS', decision: 'deny', reason: 'runtime_boundary_forbidden' })
  }
  return Object.freeze({ result: action === 'createInquiryObject' ? 'PASS' : 'FAIL', decision: action === 'createInquiryObject' ? 'allow' : 'deny' })
}
