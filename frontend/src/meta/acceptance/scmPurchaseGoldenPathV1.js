import { createProcessRegressionBaseline, validateProcessRegressionBaseline } from '../process/runtime/processRegressionBaseline/index.js'
import { transitionPurchaseRequestState, validatePurchaseRequestStateContract } from '../process/scm/purchaseRequest/state/purchaseRequestStateContract.js'
import { validatePurchaseRequestInquiryPreparationHandoff } from '../process/scm/purchaseRequest/purchaseRequestInquiryPreparationHandoffContract.js'
import { executeScmPurchaseProcessGovernanceWalkthrough } from './scmPurchaseProcessGovernanceV11428181.js'
import { purchaseInquiryLifecycleProvider, PURCHASE_INQUIRY_ENTRY_CODES } from '../providers/purchaseInquiryLifecycleProvider.js'
import { inquiryPreparationProvider } from '../providers/inquiryPreparationProvider.js'
import { createInquiryPreparation } from '../runtime/inquiryPreparationRuntime.js'

export const SCM_PURCHASE_GOLDEN_PATH_V1 = createProcessRegressionBaseline({
  baselineCode: 'SCM_PURCHASE_GOLDEN_PATH_V1', version: 'V1.14.2.8.18.2',
  steps: [
    ['PURCHASE_REQUEST', 'PurchaseRequest'], ['APPROVAL', 'PurchaseRequest'],
    ['INQUIRY_PREPARATION', 'InquiryPreparation'], ['PURCHASE_INQUIRY', 'PurchaseInquiry'],
    ['SUPPLIER_QUOTE', 'SupplierQuote[]'], ['QUOTE_COMPARISON', 'QuoteComparison'],
    ['SUPPLIER_RECOMMENDATION', 'SupplierRecommendationDecision'],
    ['PURCHASE_ORDER_CREATION_GATE', 'PurchaseOrderCreationGateDecision'],
    ['PURCHASE_ORDER_TRANSACTION', 'PurchaseOrderTransaction'],
    ['PURCHASE_ORDER_ISSUE_PREPARATION', 'PurchaseOrderIssuePreparation'],
    ['PURCHASE_ORDER_ISSUE_BOUNDARY', 'PurchaseOrderIssueDecision'],
    ['PURCHASE_ORDER_ISSUE_EXECUTION_AUTHORIZATION', 'PurchaseOrderIssueAuthorization'],
  ].map(([stepCode, objectType]) => ({ stepCode, objectType })),
})

function createdRequest() {
  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return Object.freeze({ objectType: 'PurchaseRequest', requestNo: `PR-GOLDEN-${suffix}`,
    requestDate: '2026-08-04', requester: 'golden-buyer', department: '需求部门', purchaseDepartment: '采购部',
    statusCode: 'draft', approvalStatus: 'draft', businessLifecycleState: 'created',
    inquiryEligibility: Object.freeze({ eligible: true }),
    items: Object.freeze([
      Object.freeze({ materialCode: 'MAT-GOLDEN-01', materialName: '黄金路径物料', unit: 'EA', quantity: 3,
        requiredDate: '2026-09-01', suggestedSupplierId: 'SUP-GOLDEN-01', suggestedSupplierName: '黄金供应商一' }),
      Object.freeze({ materialCode: 'MAT-GOLDEN-02', materialName: '黄金路径辅料', unit: 'EA', quantity: 2,
        requiredDate: '2026-09-02', suggestedSupplierId: 'SUP-GOLDEN-02', suggestedSupplierName: '黄金供应商二' }),
    ]) })
}

const checkpoint = (stepCode, objectType, object) => Object.freeze({ stepCode, objectType, object, result: 'PASS' })

export function createScmPurchaseRequestHandoffAcceptanceData() {
  const created = Object.freeze({ objectType: 'PurchaseRequest', objectId: 'PR_TEST_HANDOFF_001',
    requestNo: 'PR_TEST_HANDOFF_001', requestDate: '2026-08-04', requester: 'handoff-acceptance-user',
    department: '验收需求部门', purchaseDepartment: '验收采购部', statusCode: 'draft',
    approvalStatus: 'draft', businessLifecycleState: 'created', inquiryEligibility: Object.freeze({ eligible: true }),
    items: Object.freeze([Object.freeze({ materialCode: 'MAT_HANDOFF_001', materialName: '交接验收物料',
      specification: 'SPEC-HANDOFF-001', unit: 'EA', quantity: 5, requiredDate: '2026-09-01',
      suggestedSupplierId: 'SUP_HANDOFF_001', suggestedSupplierName: '交接候选供应商' })]) })
  const submitted = transitionPurchaseRequestState(created, 'SUBMIT_APPROVAL')
  const approved = transitionPurchaseRequestState(submitted, 'APPROVE')
  const creation = createInquiryPreparation(approved)
  const providerFacts = inquiryPreparationProvider.load({ sourceRequestNo: approved.requestNo })
  const valid = creation.result === 'PASS'
    && providerFacts.selected?.sourceRequestNo === 'PR_TEST_HANDOFF_001'
    && providerFacts.selected?.objectType === 'InquiryPreparationContext'
    && providerFacts.selected?.preparationStatus === 'ready_for_inquiry'
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, created, submitted, approved,
    inquiryPreparation: creation.object, providerFacts,
    navigation: Object.freeze({ route: '/scm/purchase-inquiry',
      query: Object.freeze({ inquiryPreparationNo: creation.object?.inquiryPreparationNo,
        sourceRequestNo: creation.object?.sourceRequestNo }) }),
    boundaries: Object.freeze({ purchaseInquiryCreated: false, quotationTaskCreated: false,
      supplierSent: false, quoteCreated: false, purchaseOrderCreated: false, productionDataWritten: false }) })
}

export function executeScmPurchaseGoldenPathV1() {
  const created = createdRequest()
  const submitted = transitionPurchaseRequestState(created, 'SUBMIT_APPROVAL')
  const approved = transitionPurchaseRequestState(submitted, 'APPROVE')
  const chain = executeScmPurchaseProcessGovernanceWalkthrough(approved)
  const preparationState = transitionPurchaseRequestState(approved, 'CREATE_INQUIRY_PREPARATION')
  const inquiryState = transitionPurchaseRequestState(preparationState, 'START_PURCHASE_INQUIRY')
  const handoff = validatePurchaseRequestInquiryPreparationHandoff(approved, chain.preparation)
  const checkpoints = Object.freeze([
    checkpoint('PURCHASE_REQUEST', 'PurchaseRequest', created),
    checkpoint('APPROVAL', 'PurchaseRequest', approved),
    checkpoint('INQUIRY_PREPARATION', 'InquiryPreparation', chain.preparation),
    checkpoint('PURCHASE_INQUIRY', 'PurchaseInquiry', chain.inquiry),
    checkpoint('SUPPLIER_QUOTE', 'SupplierQuote[]', chain.completedQuotes),
    checkpoint('QUOTE_COMPARISON', 'QuoteComparison', chain.comparison),
    checkpoint('SUPPLIER_RECOMMENDATION', 'SupplierRecommendationDecision', chain.recommendation),
    checkpoint('PURCHASE_ORDER_CREATION_GATE', 'PurchaseOrderCreationGateDecision', chain.gateDecision),
    checkpoint('PURCHASE_ORDER_TRANSACTION', 'PurchaseOrderTransaction', chain.transaction),
    checkpoint('PURCHASE_ORDER_ISSUE_PREPARATION', 'PurchaseOrderIssuePreparation', chain.issuePreparation),
    checkpoint('PURCHASE_ORDER_ISSUE_BOUNDARY', 'PurchaseOrderIssueDecision', chain.issueDecision),
    checkpoint('PURCHASE_ORDER_ISSUE_EXECUTION_AUTHORIZATION', 'PurchaseOrderIssueAuthorization', chain.authorization),
  ])
  const process008 = validateProcessRegressionBaseline(SCM_PURCHASE_GOLDEN_PATH_V1, checkpoints)
  const firstLoad = purchaseInquiryLifecycleProvider.loadForEntry(PURCHASE_INQUIRY_ENTRY_CODES.purchaseRequest,
    { query: { inquiryPreparationNo: chain.preparation.inquiryPreparationNo } })
  const refreshLoad = purchaseInquiryLifecycleProvider.loadForEntry(PURCHASE_INQUIRY_ENTRY_CODES.directUrl,
    { query: { inquiryPreparationNo: chain.preparation.inquiryPreparationNo } })
  const providerConsistent = firstLoad.factSnapshotId === refreshLoad.factSnapshotId
    && firstLoad.preparations.length === refreshLoad.preparations.length
  const valid = process008.valid && handoff.valid && providerConsistent
    && validatePurchaseRequestStateContract().valid
    && submitted.approvalStatus === 'submitted' && approved.approvalStatus === 'approved'
    && preparationState.businessLifecycleState === 'inquiry_preparation_created'
    && inquiryState.businessLifecycleState === 'inquiry_started'
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid, created, submitted, approved,
    preparationState, inquiryState, chain, handoff, checkpoints, process008, firstLoad, refreshLoad, providerConsistent })
}
