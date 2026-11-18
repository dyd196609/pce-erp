export const PRICE_REVIEW_PREPARATION_MODEL_VERSION = 'V1.14.2.8.6.2'

export const PRICE_REVIEW_PREPARATION_STATES = Object.freeze([
  'not_created',
  'prepared',
  'pending_review',
  'blocked',
])

const field = (name, type) => Object.freeze({ name, type, required: true, factAuthority: 'server' })

export const PRICE_REVIEW_PREPARATION = Object.freeze({
  objectCode: 'SCM_PRICE_REVIEW_PREPARATION',
  objectName: '核价准备对象',
  businessObject: 'PriceReviewPreparation',
  version: PRICE_REVIEW_PREPARATION_MODEL_VERSION,
  fields: Object.freeze([
    field('preparationNo', 'string'),
    field('inquiryNo', 'string'),
    field('comparisonNo', 'string'),
    field('sourceQuotationCount', 'number'),
    field('reviewStatus', 'status'),
    field('blockedReasons', 'array'),
  ]),
  states: PRICE_REVIEW_PREPARATION_STATES,
  formalPriceApprovalObject: false,
  persistenceMode: 'read_only_projection',
  automaticCreation: false,
  autoPriceApproval: false,
  createsPurchaseOrder: false,
  productionDataWritten: false,
})

export function validatePriceReviewPreparation(model = PRICE_REVIEW_PREPARATION) {
  const expected = ['preparationNo', 'inquiryNo', 'comparisonNo', 'sourceQuotationCount', 'reviewStatus', 'blockedReasons']
  const fields = new Set(model.fields?.map((item) => item.name))
  const valid = expected.every((name) => fields.has(name))
    && model.states.join(',') === 'not_created,prepared,pending_review,blocked'
    && model.formalPriceApprovalObject === false
    && model.persistenceMode === 'read_only_projection'
    && model.automaticCreation === false
    && model.autoPriceApproval === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
