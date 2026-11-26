export const FORMAL_PRICE_APPROVAL_PROJECTION_RULE_ENGINE_VERSION = 'V1.14.2.8.6.5'

export const FORMAL_PRICE_APPROVAL_PROJECTION_RULES = Object.freeze([
  Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-001', name: '创建冻结证据检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-002', name: '报价证据链检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-003', name: '比较与核价准备证据检查' }),
  Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-004', name: '准入评估证据检查' }),
])

const present = (value) => value !== undefined && value !== null && String(value).trim() !== ''

export function evaluateFormalPriceApprovalProjection(input = {}) {
  const evidencePackage = input.evidencePackage || {}
  const creationAssessment = input.creationAssessment || {}
  const hasFacts = present(evidencePackage.evidencePackageNo) || present(creationAssessment.creationAssessmentStatus)
  if (!hasFacts) {
    return Object.freeze({
      result: 'NOT_CREATED', projectionStatus: 'not_created', packageStatus: 'not_created', rules: Object.freeze([]),
      missingEvidence: Object.freeze([]), projectionAvailable: false, decisionOnly: true,
      formalPriceApprovalObjectCreated: false, businessWriteCount: 0, productionDataWritten: false,
    })
  }
  const freezeBlocked = creationAssessment.creationAssessmentStatus === 'blocked'
  const freezeReady = creationAssessment.creationAssessmentStatus === 'ready'
  const packageBlocked = evidencePackage.packageStatus === 'blocked'
  const missingEvidence = Object.freeze([
    ...(!Array.isArray(evidencePackage.quotationEvidenceRefs) || evidencePackage.quotationEvidenceRefs.length === 0 ? ['quotationEvidenceRefs'] : []),
    ...(!present(evidencePackage.comparisonEvidenceRef) ? ['comparisonEvidenceRef'] : []),
    ...(!present(evidencePackage.preparationEvidenceRef) ? ['preparationEvidenceRef'] : []),
    ...(!present(evidencePackage.entryAssessmentEvidenceRef) ? ['entryAssessmentEvidenceRef'] : []),
    ...(!present(evidencePackage.creationFreezeEvidenceRef) ? ['creationFreezeEvidenceRef'] : []),
  ])
  const blocked = freezeBlocked || packageBlocked
  const complete = freezeReady && missingEvidence.length === 0 && evidencePackage.packageStatus === 'available'
  const projectionStatus = blocked ? 'blocked' : complete ? 'available' : 'incomplete'
  const rules = Object.freeze([
    Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-001', result: freezeBlocked ? 'BLOCKED' : freezeReady ? 'PASS' : 'FAIL' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-002', result: missingEvidence.includes('quotationEvidenceRefs') ? 'FAIL' : 'PASS' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-003', result: missingEvidence.some((item) => ['comparisonEvidenceRef', 'preparationEvidenceRef'].includes(item)) ? 'FAIL' : 'PASS' }),
    Object.freeze({ ruleCode: 'FORMAL-PRICE-PROJECTION-004', result: missingEvidence.some((item) => ['entryAssessmentEvidenceRef', 'creationFreezeEvidenceRef'].includes(item)) ? 'FAIL' : 'PASS' }),
  ])
  return Object.freeze({
    result: projectionStatus.toUpperCase(),
    projectionStatus,
    packageStatus: blocked ? 'blocked' : complete ? 'available' : 'incomplete',
    rules,
    missingEvidence,
    projectionAvailable: projectionStatus === 'available',
    decisionOnly: true,
    evidenceArchiveWritten: false,
    formalPriceApprovalObjectCreated: false,
    approvalWorkflowStarted: false,
    approvalTaskCreated: false,
    approvalSubmitted: false,
    priceApproved: false,
    purchaseOrderCreated: false,
    businessWriteCount: 0,
    productionDataWritten: false,
  })
}
