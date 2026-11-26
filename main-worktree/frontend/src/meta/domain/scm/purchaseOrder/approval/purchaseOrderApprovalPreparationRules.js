import { PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL } from './purchaseOrderApprovalPreparationDomainModel.js'

export const PURCHASE_ORDER_APPROVAL_PREPARATION_RULES_VERSION = 'V1.14.2.8.5.8'
export const PURCHASE_ORDER_APPROVAL_PREPARATION_RULE_SET_CODE = 'SCM_PURCHASE_ORDER_APPROVAL_PREPARATION_RULES'

export const PURCHASE_ORDER_APPROVAL_PREPARATION_REQUIRED_FIELDS = Object.freeze(
  PURCHASE_ORDER_APPROVAL_PREPARATION_DOMAIN_MODEL.fields.map(item => item.name),
)

const isPresent = value => value !== undefined && value !== null && value !== ''

export function evaluatePurchaseOrderApprovalPreparation(input = {}) {
  const missingFields = Object.freeze(PURCHASE_ORDER_APPROVAL_PREPARATION_REQUIRED_FIELDS.filter(name => {
    const value = input[name]
    return name === 'evidenceReferences' ? !Array.isArray(value) || value.length === 0 : !isPresent(value)
  }))
  const ready = missingFields.length === 0
  return Object.freeze({
    preparationStatus: ready ? 'ready' : 'blocked',
    approvalPreparationReady: ready,
    missingFields,
    purchaseOrderDomainId: input.purchaseOrderDomainId || null,
    creationRequestId: input.creationRequestId || null,
    transactionBoundaryId: input.transactionBoundaryId || null,
    supplierReference: input.supplierReference || null,
    amountReference: input.amountReference || null,
    deliveryRequirement: input.deliveryRequirement || null,
    evidenceReferences: Object.freeze(Array.isArray(input.evidenceReferences) ? [...input.evidenceReferences] : []),
    riskSummary: input.riskSummary ?? null,
    createdAutomatically: false,
    submitsApproval: false,
    createsWorkflowInstance: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
