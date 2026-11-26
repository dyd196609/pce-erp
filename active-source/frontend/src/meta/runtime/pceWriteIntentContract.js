export const PCE_WRITE_INTENT_CONTRACT_VERSION =
  'PCE-WRITE-INTENT-CONTRACT-V1.0'

export const WriteIntentCategory = Object.freeze({
  PREVIEW_PREPARATION_WRITE: 'preview_preparation_write',
  SEND_TASK_PREPARATION_WRITE: 'send_task_preparation_write',
  BANK_SEND_EXECUTION_WRITE: 'bank_send_execution_write',
  BUSINESS_PROGRESS_WRITE: 'business_progress_write',
  AUDIT_WRITE: 'audit_write',
})

export const SEND_TASK_PREPARATION_FIELD = 'bankSendTasks'

export const BANK_SEND_EXECUTION_FIELDS = Object.freeze([
  'bankMessages',
  'paymentExecutions',
  'fundsDebits',
  'bankTransactions',
  'paymentVouchers',
  'ledgerEntries',
  'postings',
])

export const FORBIDDEN_BUSINESS_PROGRESS_FIELDS =
  BANK_SEND_EXECUTION_FIELDS

function assertCount(facts, field, context) {
  const value = facts?.[field]
  if (!Number.isInteger(value) || value < 0) {
    throw new Error(`${context}:${field} must be a non-negative integer`)
  }
}

export function assertWriteIntentFacts(facts, context = 'write-intent') {
  if (
    facts?.contractVersion !== PCE_WRITE_INTENT_CONTRACT_VERSION
    || !Array.isArray(facts?.categories)
    || !Object.values(WriteIntentCategory).every(category => (
      facts.categories.includes(category)
    ))
  ) {
    throw new Error(`${context}: write intent contract is incomplete`)
  }
  assertCount(facts, 'previewPreparationWriteCount', context)
  assertCount(facts, 'sendTaskPreparationWriteCount', context)
  assertCount(facts, 'bankSendExecutionWriteCount', context)
  assertCount(facts, 'auditWriteCount', context)
  assertCount(facts, 'forbiddenBusinessProgressWriteCount', context)
  assertCount(
    facts.businessProgressCounts,
    SEND_TASK_PREPARATION_FIELD,
    context,
  )
  for (const field of FORBIDDEN_BUSINESS_PROGRESS_FIELDS) {
    assertCount(facts.businessProgressCounts, field, context)
  }
  const actualForbiddenCount = FORBIDDEN_BUSINESS_PROGRESS_FIELDS
    .reduce(
      (total, field) => total + facts.businessProgressCounts[field],
      0,
    )
  if (
    actualForbiddenCount !== facts.forbiddenBusinessProgressWriteCount
    || actualForbiddenCount !== facts.bankSendExecutionWriteCount
    || facts.sendTaskPreparationWriteCount
      !== facts.businessProgressCounts[SEND_TASK_PREPARATION_FIELD]
    || facts.businessProgressWriteBlocked !== (actualForbiddenCount === 0)
    || facts.bankSendExecutionWriteBlocked !== (actualForbiddenCount === 0)
    || facts.sendTaskPreparationWriteAllowed !== true
    || facts.previewWriteAllowed !== true
    || facts.previewOnlyEnforced !== true
  ) {
    throw new Error(`${context}: write intent totals are inconsistent`)
  }
  return facts
}
