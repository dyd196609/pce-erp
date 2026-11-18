export const FORMAL_PRICE_APPROVAL_COMMENT_VERSION = 'V1.14.2.8.6.23'

export const FORMAL_PRICE_APPROVAL_COMMENT_FIELDS = Object.freeze([
  'commentNo', 'nodeCode', 'commentType', 'authorRole', 'content', 'evidenceRefs', 'commentStatus',
])

export const FORMAL_PRICE_APPROVAL_COMMENT_MODEL = Object.freeze({
  modelCode: 'SCM_FORMAL_PRICE_APPROVAL_COMMENT',
  version: FORMAL_PRICE_APPROVAL_COMMENT_VERSION,
  fields: FORMAL_PRICE_APPROVAL_COMMENT_FIELDS,
  statuses: Object.freeze(['definition_only', 'draft_reference', 'review_reference', 'closed_reference']),
  currentStatus: 'definition_only',
  mode: 'definition_only',
  commentMeansApprovalResult: false,
  commentExecutionEnabled: false,
  commentInstanceCount: 0,
  persistenceConnected: false,
})

export function validateFormalPriceApprovalCommentModel(model = FORMAL_PRICE_APPROVAL_COMMENT_MODEL) {
  const valid = model.modelCode === 'SCM_FORMAL_PRICE_APPROVAL_COMMENT'
    && model.fields.join(',') === FORMAL_PRICE_APPROVAL_COMMENT_FIELDS.join(',')
    && model.statuses.includes(model.currentStatus)
    && model.currentStatus === 'definition_only'
    && model.mode === 'definition_only'
    && model.commentMeansApprovalResult === false
    && model.commentExecutionEnabled === false
    && model.commentInstanceCount === 0
    && model.persistenceConnected === false
  return Object.freeze({ result: valid ? 'PASS' : 'FAIL', valid })
}
