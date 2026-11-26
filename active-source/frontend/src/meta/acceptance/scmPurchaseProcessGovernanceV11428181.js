import { createProcessHandoffAuditContract, auditProcessHandoffChain } from '../process/runtime/processHandoffAudit/index.js'
import { validatePageFactSourceGovernance, validateMultiEntryProviderConsistency } from '../process/runtime/pageFactSourceGovernance.js'
import { purchaseInquiryLifecycleProvider, PURCHASE_INQUIRY_ENTRY_CODES } from '../providers/purchaseInquiryLifecycleProvider.js'
import { createInquiryPreparation } from '../runtime/inquiryPreparationRuntime.js'
import { activatePurchaseInquiryFromPreparation } from '../runtime/purchaseInquiryRuntime.js'
import { createSupplierQuoteContext, markSupplierQuoteWaiting, receiveSupplierQuote, saveSupplierQuote } from '../runtime/supplierQuoteRuntime.js'
import { createQuoteComparisonContext, generateQuoteComparisonFact, saveQuoteComparison, markQuoteComparisonRecommendationReady } from '../runtime/quoteComparisonRuntime.js'
import { createSupplierRecommendationContext, generateSupplierRecommendationDecision, saveSupplierRecommendationDecision, markSupplierRecommendationApprovalReady } from '../runtime/supplierRecommendationRuntime.js'
import { createPurchaseOrderCreationGateContext, evaluatePurchaseOrderGateDecision, savePurchaseOrderGateDecision } from '../runtime/purchaseOrderCreationGateRuntime.js'
import { createPurchaseOrderTransactionContext, createPurchaseOrderTransaction } from '../runtime/purchaseOrderTransactionRuntime.js'
import { createPurchaseOrderIssuePreparationContext, checkPurchaseOrderIssuePreparation, savePurchaseOrderIssuePreparation } from '../runtime/purchaseOrderIssuePreparationRuntime.js'
import { createPurchaseOrderIssueBoundaryContext, evaluatePurchaseOrderIssueBoundary, savePurchaseOrderIssueDecision } from '../runtime/purchaseOrderIssueBoundaryRuntime.js'
import { createPurchaseOrderIssueExecutionContext, checkPurchaseOrderIssueExecution, savePurchaseOrderIssueExecutionPreparation } from '../runtime/purchaseOrderIssueExecutionRuntime.js'
import { PURCHASE_REQUEST_INQUIRY_HANDOFF_CONTRACT, validatePurchaseRequestInquiryHandoff } from '../process/scm/purchaseRequest/purchaseRequestInquiryHandoffContract.js'
import { PURCHASE_INQUIRY_PREPARATION_HANDOFF_CONTRACT, validatePurchaseInquiryPreparationHandoff } from '../process/scm/purchaseInquiry/purchaseInquiryPreparationHandoffContract.js'
import { PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF_CONTRACT, validatePurchaseInquirySupplierQuoteHandoff } from '../process/scm/supplierQuote/purchaseInquirySupplierQuoteHandoffContract.js'
import { SUPPLIER_QUOTE_COMPARISON_HANDOFF_CONTRACT, validateSupplierQuoteComparisonHandoff } from '../process/scm/quoteComparison/supplierQuoteComparisonHandoffContract.js'
import { QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_CONTRACT, validateQuoteComparisonRecommendationHandoff } from '../process/scm/supplierRecommendation/quoteComparisonRecommendationHandoffContract.js'
import { SUPPLIER_RECOMMENDATION_PURCHASE_ORDER_GATE_HANDOFF_CONTRACT, validateSupplierRecommendationPurchaseOrderGateHandoff } from '../process/scm/purchaseOrderCreationGate/supplierRecommendationPurchaseOrderGateHandoffContract.js'
import { PURCHASE_ORDER_GATE_TRANSACTION_HANDOFF_CONTRACT, validatePurchaseOrderGateTransactionHandoff } from '../process/scm/purchaseOrderTransaction/purchaseOrderGateTransactionHandoffContract.js'
import { PURCHASE_ORDER_TRANSACTION_ISSUE_PREPARATION_HANDOFF_CONTRACT, validatePurchaseOrderTransactionIssuePreparationHandoff } from '../process/scm/purchaseOrderIssuePreparation/purchaseOrderTransactionIssuePreparationHandoffContract.js'
import { ISSUE_PREPARATION_BOUNDARY_HANDOFF_CONTRACT, validateIssuePreparationBoundaryHandoff } from '../process/scm/purchaseOrderIssueBoundary/purchaseOrderIssuePreparationBoundaryHandoffContract.js'
import { ISSUE_BOUNDARY_EXECUTION_HANDOFF_CONTRACT, validateIssueBoundaryExecutionHandoff } from '../process/scm/purchaseOrderIssueExecution/purchaseOrderIssueBoundaryExecutionHandoffContract.js'
import { PURCHASE_REQUEST_ACTION_CONTRACTS, resolvePurchaseRequestGovernedActionContract } from '../process/scm/purchaseRequest/purchaseRequestActionContracts.js'
import { PURCHASE_INQUIRY_ACTION_CONTRACTS } from '../process/scm/purchaseInquiry/purchaseInquiryActionContracts.js'
import { validatePurchaseRequestStateSeparation } from '../process/scm/purchaseRequest/purchaseRequestStateTransitionContract.js'

export const SCM_PURCHASE_PROCESS_GOVERNANCE_VERSION = 'V1.14.2.8.18.1'

const passes = value => value?.result === 'PASS' || value?.valid === true
const transition = (from, to) => Object.freeze({ from, to })

function fixtureRequest() {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return Object.freeze({
    objectType: 'PurchaseRequest', requestNo: `PR-GOV-${suffix}`, requestDate: '2026-08-04',
    requester: 'governance-buyer', department: '需求部门', purchaseDepartment: '采购部',
    statusCode: 'approved', approvalStatus: 'completed', inquiryEligibility: Object.freeze({ eligible: true }),
    items: Object.freeze([
      Object.freeze({ lineNo: 1, materialCode: 'MAT-GOV-01', materialName: '治理物料', unit: 'EA', quantity: 6,
        requiredDate: '2026-09-01', suggestedSupplierId: 'SUP-GOV-01', suggestedSupplierName: '治理供应商一' }),
      Object.freeze({ lineNo: 2, materialCode: 'MAT-GOV-02', materialName: '治理辅料', unit: 'EA', quantity: 2,
        requiredDate: '2026-09-02', suggestedSupplierId: 'SUP-GOV-02', suggestedSupplierName: '治理供应商二' }),
    ]),
  })
}

function handoffAudit(handoffContract, requiredFields, sourceObject, context, targetObject, mappedFacts, validator, from, to) {
  const contract = createProcessHandoffAuditContract({
    auditCode: `AUDIT_${handoffContract.handoffCode}`,
    sourceNode: handoffContract.fromNode,
    targetNode: handoffContract.toNode,
    handoffContract,
    requiredFields,
    validateContext: () => passes(validator(sourceObject, context)),
  })
  return Object.freeze({ contract, artifacts: Object.freeze({ sourceObject, context, targetObject,
    mappedFacts, stateTransition: transition(from, to) }) })
}

export function executeScmPurchaseProcessGovernanceWalkthrough(requestInput = null) {
  const request = requestInput || fixtureRequest()
  const preparationResult = createInquiryPreparation(request)
  if (!passes(preparationResult)) throw new Error('GOVERNANCE_INQUIRY_PREPARATION_FAILED')
  const preparation = preparationResult.object
  const inquiryResult = activatePurchaseInquiryFromPreparation(preparation)
  if (!passes(inquiryResult)) throw new Error('GOVERNANCE_PURCHASE_INQUIRY_FAILED')
  const inquiry = inquiryResult.object

  const quoteContext = markSupplierQuoteWaiting(createSupplierQuoteContext({ ...inquiry, responseDeadline: '2026-08-31' }))
  const completedQuotes = quoteContext.supplierCandidates.map((supplier, index) => saveSupplierQuote(receiveSupplierQuote(quoteContext, {
    supplierId: supplier.supplierId, quoteNo: `SQ-GOV-${index + 1}-${request.requestNo}`,
    quoteDate: '2026-08-04', validUntil: '2026-09-30', currency: 'CNY',
    lines: inquiry.lines.map((line, lineIndex) => ({ ...line, unitPrice: 10 + index + lineIndex,
      deliveryDate: line.requiredDate || '2026-09-01' })),
  })).object)
  const comparisonContext = createQuoteComparisonContext(completedQuotes)
  const comparison = markQuoteComparisonRecommendationReady(saveQuoteComparison(generateQuoteComparisonFact(comparisonContext)).object)
  const recommendationContext = createSupplierRecommendationContext(comparison)
  const recommendation = markSupplierRecommendationApprovalReady(
    saveSupplierRecommendationDecision(generateSupplierRecommendationDecision(recommendationContext)).object,
  )
  const gateContext = createPurchaseOrderCreationGateContext(recommendation)
  const gateDecision = savePurchaseOrderGateDecision(evaluatePurchaseOrderGateDecision(gateContext)).object
  const transactionContext = createPurchaseOrderTransactionContext(gateDecision)
  const transaction = createPurchaseOrderTransaction(transactionContext)
  const issuePreparationContext = createPurchaseOrderIssuePreparationContext(transaction)
  const issuePreparation = savePurchaseOrderIssuePreparation(checkPurchaseOrderIssuePreparation(issuePreparationContext)).object
  const issueBoundaryContext = createPurchaseOrderIssueBoundaryContext(issuePreparation)
  const issueDecision = savePurchaseOrderIssueDecision(evaluatePurchaseOrderIssueBoundary(issueBoundaryContext)).object
  const issueExecutionContext = createPurchaseOrderIssueExecutionContext(issueDecision)
  const authorization = savePurchaseOrderIssueExecutionPreparation(checkPurchaseOrderIssueExecution(issueExecutionContext)).object

  const handoffs = auditProcessHandoffChain([
    handoffAudit(PURCHASE_REQUEST_INQUIRY_HANDOFF_CONTRACT,
      ['requestNo', 'department', 'purchaseDepartment', 'materialLines', 'quantity', 'deliveryDate'], request, preparation, preparation,
      { requestNo: request.requestNo, department: request.department, purchaseDepartment: request.purchaseDepartment,
        materialLines: request.items, quantity: request.items.reduce((sum, item) => sum + item.quantity, 0), deliveryDate: request.items[0].requiredDate },
      (_source, target) => validatePurchaseRequestInquiryHandoff(target), 'approved', 'inquiry_preparation_created'),
    handoffAudit(PURCHASE_INQUIRY_PREPARATION_HANDOFF_CONTRACT,
      ['preparationNo', 'sourceRequestNo', 'materialLines', 'supplierCandidates'], preparation, inquiry, inquiry,
      { preparationNo: preparation.inquiryPreparationNo, sourceRequestNo: preparation.sourceRequestNo,
        materialLines: preparation.inquiryLines, supplierCandidates: preparation.supplierCandidates },
      validatePurchaseInquiryPreparationHandoff, 'preparation_ready', 'inquiry_draft'),
    handoffAudit(PURCHASE_INQUIRY_SUPPLIER_QUOTE_HANDOFF_CONTRACT,
      ['inquiryNo', 'supplierContext', 'quotationScope'], inquiry, quoteContext, quoteContext,
      { inquiryNo: inquiry.inquiryNo, supplierContext: quoteContext.supplierCandidates,
        quotationScope: { materials: quoteContext.materials, deadline: quoteContext.deadline } },
      validatePurchaseInquirySupplierQuoteHandoff, 'inquiry_draft', 'quote_context_created'),
    handoffAudit(SUPPLIER_QUOTE_COMPARISON_HANDOFF_CONTRACT,
      ['supplierQuoteList', 'price', 'deliveryDate', 'validity'], completedQuotes, comparisonContext, comparisonContext,
      { supplierQuoteList: completedQuotes, price: completedQuotes[0].lines[0].unitPrice,
        deliveryDate: completedQuotes[0].lines[0].deliveryDate, validity: completedQuotes[0].validUntil },
      validateSupplierQuoteComparisonHandoff, 'quotation_completed', 'comparison_context_created'),
    handoffAudit(QUOTE_COMPARISON_RECOMMENDATION_HANDOFF_CONTRACT,
      ['comparisonEvidence', 'recommendationEvidence'], comparison, recommendationContext, recommendationContext,
      { comparisonEvidence: comparison.facts, recommendationEvidence: recommendationContext.riskEvidence },
      validateQuoteComparisonRecommendationHandoff, 'recommendation_ready', 'recommendation_context_created'),
    handoffAudit(SUPPLIER_RECOMMENDATION_PURCHASE_ORDER_GATE_HANDOFF_CONTRACT,
      ['supplier', 'reason', 'evidence', 'costReference'], recommendation, gateContext, gateContext,
      { supplier: gateContext.recommendedSupplier, reason: recommendation.decisionBasis,
        evidence: gateContext.recommendationEvidence, costReference: gateContext.costReference },
      validateSupplierRecommendationPurchaseOrderGateHandoff, 'approval_ready', 'gate_context_created'),
    handoffAudit(PURCHASE_ORDER_GATE_TRANSACTION_HANDOFF_CONTRACT,
      ['orderLines', 'amountReference', 'sourceTrace'], gateDecision, transactionContext, transactionContext,
      { orderLines: transactionContext.purchaseDetails, amountReference: transactionContext.amountReference,
        sourceTrace: transactionContext.sourceChain }, validatePurchaseOrderGateTransactionHandoff, 'eligible', 'transaction_context_created'),
    handoffAudit(PURCHASE_ORDER_TRANSACTION_ISSUE_PREPARATION_HANDOFF_CONTRACT,
      ['supplier', 'deliveryRequirement'], transaction, issuePreparationContext, issuePreparationContext,
      { supplier: issuePreparationContext.supplier, deliveryRequirement: issuePreparationContext.deliveryRequirements },
      validatePurchaseOrderTransactionIssuePreparationHandoff, 'draft', 'issue_context_created'),
    handoffAudit(ISSUE_PREPARATION_BOUNDARY_HANDOFF_CONTRACT,
      ['preparationResult', 'evidence'], issuePreparation, issueBoundaryContext, issueBoundaryContext,
      { preparationResult: issueBoundaryContext.preparationResult, evidence: issueBoundaryContext.evidence },
      validateIssuePreparationBoundaryHandoff, 'ready_for_issue', 'issue_boundary_context_created'),
    handoffAudit(ISSUE_BOUNDARY_EXECUTION_HANDOFF_CONTRACT,
      ['authorizationEvidence'], issueDecision, issueExecutionContext, issueExecutionContext,
      { authorizationEvidence: issueExecutionContext.authorizationEvidence },
      validateIssueBoundaryExecutionHandoff, issueDecision.status, 'execution_context_created'),
  ])

  return Object.freeze({ request, preparation, inquiry, completedQuotes, comparison, recommendation,
    gateDecision, transaction, issuePreparation, issueDecision, issueExecutionContext, authorization, handoffs })
}

export function validateScmPurchaseProcessGovernance() {
  const walkthrough = executeScmPurchaseProcessGovernanceWalkthrough()
  const entries = Object.values(PURCHASE_INQUIRY_ENTRY_CODES).map(entryCode =>
    purchaseInquiryLifecycleProvider.loadForEntry(entryCode))
  const page = validatePageFactSourceGovernance({ pageCode: 'purchase-inquiry',
    providerCode: 'SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER', runtimeContext: true, businessObject: true,
    directUrlComposition: false, directLocalStateComposition: false,
    directTemporaryArrayComposition: false, directPageCacheComposition: false })
  const multiEntry = validateMultiEntryProviderConsistency(entries)
  const requiredActions = ['SUBMIT_APPROVAL', 'APPROVE', 'CREATE_INQUIRY_PREPARATION']
    .map(resolvePurchaseRequestGovernedActionContract)
  const actionContracts = [...PURCHASE_REQUEST_ACTION_CONTRACTS, ...PURCHASE_INQUIRY_ACTION_CONTRACTS]
  const actionValid = requiredActions.every(Boolean)
    && ['START_PURCHASE_INQUIRY', 'EDIT_PURCHASE_INQUIRY', 'SAVE_PURCHASE_INQUIRY']
      .every(code => actionContracts.some(contract => contract.actionCode === code && contract.buttonCode))
  const state = validatePurchaseRequestStateSeparation()
  const isolated = [walkthrough.authorization.supplierApiCalled, walkthrough.authorization.purchaseOrderIssued,
    walkthrough.authorization.goodsReceived, walkthrough.authorization.inventoryPosted,
    walkthrough.authorization.invoiceCreated, walkthrough.authorization.paymentCreated,
    walkthrough.authorization.productionDataWritten].every(value => value === false)
  const process006D = walkthrough.handoffs.valid && walkthrough.authorization.objectType === 'PurchaseOrderIssueAuthorization' && isolated
  return Object.freeze({
    pageRuntime: page, actionContract: Object.freeze({ result: actionValid ? 'PASS' : 'FAIL', valid: actionValid }),
    stateContract: state, handoff: walkthrough.handoffs,
    provider: Object.freeze({ result: entries.every(item => item.providerCode === 'SCM_PURCHASE_INQUIRY_LIFECYCLE_PROVIDER') ? 'PASS' : 'FAIL' }),
    multiEntry,
    process006A: Object.freeze({ result: page.valid && actionValid && state.valid ? 'PASS' : 'FAIL' }),
    process006B: Object.freeze({ result: walkthrough.handoffs.valid ? 'PASS' : 'FAIL' }),
    process006C: Object.freeze({ result: multiEntry.valid ? 'PASS' : 'FAIL' }),
    process006D: Object.freeze({ result: process006D ? 'PASS' : 'FAIL' }),
    walkthrough,
  })
}
