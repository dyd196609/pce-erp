import { validateSupplierRecommendationNodeContractV1142811 } from './supplierRecommendationNodeContractV1142811.js'
import { validateSupplierRecommendationDomainV1142811 } from './supplierRecommendationDomainModelV1142811.js'
import { SUPPLIER_RECOMMENDATION_STATES_V1142811,
  SUPPLIER_RECOMMENDATION_BOUNDARY_V1142811 } from './supplierRecommendationStateContractV1142811.js'
import { SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS_V1142811,
  SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS_V1142811 } from './supplierRecommendationActionContractsV1142811.js'
import { validateQuoteComparisonRecommendationHandoffV1142811 } from './quoteComparisonSupplierRecommendationHandoffV1142811.js'
import { validateSupplierRecommendationProviderContractV1142811 } from './supplierRecommendationProviderContractV1142811.js'
import { validateSupplierRecommendationPageContractV1142811 } from './supplierRecommendationPageContractV1142811.js'
import { createSupplierRecommendationProviderV1142811 } from '../../../providers/supplierRecommendationProviderV1142811.js'
import { executeConfirmRecommendationDecision, executeCreateRecommendationDecisionContext,
  executePreparePurchaseOrderGateHandoff, executePrepareRecommendationDecision,
  executeStartManualReview, executeStartRecommendationEvaluation } from '../../../runtime/supplierRecommendationActionRuntimeV1142811.js'

export const SUPPLIER_RECOMMENDATION_ACCEPTANCE_VERSION_V1142811 = 'V1.14.2.8.18.11'
export const SUPPLIER_RECOMMENDATION_PROCESS006_PATH_V1142811 = Object.freeze([
  'QUOTE_COMPARISON_RESULT', 'CREATE_RECOMMENDATION_CONTEXT', 'START_EVALUATION',
  'PREPARE_DECISION', 'MANUAL_REVIEW', 'CONFIRM_RECOMMENDATION', 'PREPARE_GATE_HANDOFF',
])

export function runSupplierRecommendationBusinessWalkthroughV1142811({ preparation, supplierProvider,
  store, sourceStore, manualSelections, recommendationReason, confirmedBy }) {
  const steps = []
  const record = (stepCode, result, facts = {}) => steps.push(Object.freeze({ sequence: steps.length + 1,
    stepCode, result, facts: Object.freeze({ ...facts }) }))
  record('QUOTE_COMPARISON_RESULT', preparation?.preparationStatus === 'comparison_ready' ? 'PASS' : 'FAIL',
    { recommendationPreparationNo: preparation?.recommendationPreparationNo })
  const created = executeCreateRecommendationDecisionContext(preparation, store, supplierProvider)
  record('CREATE_RECOMMENDATION_CONTEXT', created.result, { decisionContextNo: created.context?.decisionContextNo })
  if (created.result !== 'PASS') return Object.freeze({ result: 'FAIL', steps: Object.freeze(steps) })
  const evaluating = executeStartRecommendationEvaluation(created.context, store)
  record('START_EVALUATION', evaluating.result, { status: evaluating.context?.recommendationStatus })
  const prepared = evaluating.result === 'PASS' ? executePrepareRecommendationDecision(evaluating.context, store) : evaluating
  record('PREPARE_DECISION', prepared.result, { status: prepared.context?.recommendationStatus })
  const reviewing = prepared.result === 'PASS' ? executeStartManualReview(prepared.context, store) : prepared
  record('MANUAL_REVIEW', reviewing.result, { status: reviewing.context?.recommendationStatus,
    approvalContextNo: reviewing.approvalContext?.approvalContextNo })
  const confirmed = reviewing.result === 'PASS' ? executeConfirmRecommendationDecision(reviewing.context,
    reviewing.approvalContext, { selections: manualSelections, reason: recommendationReason, confirmedBy }, store) : reviewing
  record('CONFIRM_RECOMMENDATION', confirmed.result, { status: confirmed.decision?.recommendationStatus,
    manualConfirmationStatus: confirmed.decision?.manualConfirmationStatus })
  const handed = confirmed.result === 'PASS'
    ? executePreparePurchaseOrderGateHandoff(confirmed.decision, store) : confirmed
  record('PREPARE_GATE_HANDOFF', handed.result, { status: handed.decision?.recommendationStatus,
    purchaseOrderCreated: handed.purchaseOrderCreated })
  const providerFacts = createSupplierRecommendationProviderV1142811({ sourceStore, store }).load()
  return Object.freeze({ result: handed.result, steps: Object.freeze(steps), preparation,
    context: providerFacts.contexts.find(item => item.decisionContextNo === created.context.decisionContextNo),
    approvalContext: confirmed.approvalContext, decision: handed.decision, handoff: handed.handoff,
    providerFacts, ...SUPPLIER_RECOMMENDATION_BOUNDARY_V1142811 })
}

export function validateSupplierRecommendationAcceptanceV1142811({ walkthrough, preparation,
  supplierProvider, store, sourceStore }) {
  const node = validateSupplierRecommendationNodeContractV1142811()
  const domain = validateSupplierRecommendationDomainV1142811(walkthrough.context, walkthrough.decision)
  const state = SUPPLIER_RECOMMENDATION_STATES_V1142811.join('>')
    === 'created>evaluating>decision_prepared>manual_review>confirmed>handoff_ready'
    && walkthrough.decision?.recommendationStatus === 'handoff_ready'
  const action = SUPPLIER_RECOMMENDATION_ACTION_CONTRACTS_V1142811.length === 6
    && ['AUTO_RECOMMEND_SUPPLIER', 'AI_DECIDE_SUPPLIER', 'CREATE_PURCHASE_ORDER']
      .every(item => SUPPLIER_RECOMMENDATION_FORBIDDEN_ACTIONS_V1142811.includes(item))
  const handoff = validateQuoteComparisonRecommendationHandoffV1142811(preparation, walkthrough.context).valid
    && walkthrough.handoff?.targetObjectType === 'PurchaseOrderCreationGateContext'
    && walkthrough.handoff?.purchaseOrderGateCreated === false
  const providerFacts = createSupplierRecommendationProviderV1142811({ sourceStore, store }).load()
  const provider = validateSupplierRecommendationProviderContractV1142811().valid
    && providerFacts.factSource === 'SupplierRecommendationRuntimeStore'
    && providerFacts.upstreamFactSource === 'QuoteComparisonRuntimeStore'
  const page = validateSupplierRecommendationPageContractV1142811()
  const boundaries = Object.values(SUPPLIER_RECOMMENDATION_BOUNDARY_V1142811).every(value => value === false)
    && walkthrough.purchaseOrderCreated === false && walkthrough.handoff?.purchaseOrderCreated === false
  const process006A = node.valid && domain.valid && state && action && page.valid
  const process006B = handoff && provider
  const process006C = providerFacts.records.every(item => item.preparation.objectType
    === 'SupplierRecommendationDecisionPreparationContext')
  const process006D = walkthrough.result === 'PASS'
    && walkthrough.steps.map(item => item.stepCode).join('>')
      === SUPPLIER_RECOMMENDATION_PROCESS006_PATH_V1142811.join('>')
  const process008 = boundaries && walkthrough.decision?.decisionMode === 'manual_only'
  const valid = process006A && process006B && process006C && process006D && process008
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', node, domain, state, action, handoff,
    provider, page, process006A, process006B, process006C, process006D, process008, boundaries })
}
