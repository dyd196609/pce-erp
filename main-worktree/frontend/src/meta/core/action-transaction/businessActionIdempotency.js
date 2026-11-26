import { stableBusinessActionTransactionHash } from './businessActionTransactionIntegrity.js'

const text = (value) => String(value ?? '').trim()

export function buildBusinessActionIdempotencyKey({ actionCode, sourceKey, reviewId, reviewHash, transactionPolicyVersion } = {}) {
  return `BAI-${stableBusinessActionTransactionHash({ actionCode: text(actionCode), sourceKey: text(sourceKey), reviewId: text(reviewId), reviewHash: text(reviewHash), transactionPolicyVersion: text(transactionPolicyVersion) })}`
}

export function resolveBusinessActionIdempotency({ idempotencyKey, records = [] } = {}) {
  const record = records.find((item) => item.idempotencyKey === idempotencyKey) || null
  if (!record) return { status: 'not_found', record: null, canStart: true, mustRecover: false }
  if (record.status === 'committed') return { status: 'committed', record, canStart: false, mustRecover: false }
  if (record.status === 'commit_unknown') return { status: 'commit_unknown', record, canStart: false, mustRecover: true }
  if (record.status === 'in_progress') return { status: 'in_progress', record, canStart: false, mustRecover: false }
  return { status: record.status, record, canStart: record.status === 'failed_retryable', mustRecover: false }
}
