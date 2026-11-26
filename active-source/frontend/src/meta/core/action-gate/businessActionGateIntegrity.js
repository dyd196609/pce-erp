export const cloneBusinessActionGateValue = (value) => JSON.parse(JSON.stringify(value ?? null))

function canonicalize(value) {
  if (Array.isArray(value)) return value.map(canonicalize)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, canonicalize(value[key])]))
  }
  return value
}

export function stableBusinessActionTextHash(value) {
  const input = String(value ?? '')
  let hash = 2166136261
  for (const char of input) {
    hash ^= char.charCodeAt(0)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, '0').toUpperCase()
}

export function stableBusinessActionGateHash(value) {
  return stableBusinessActionTextHash(JSON.stringify(canonicalize(value)))
}

export function validateBusinessActionReviewIntegrity(review = {}) {
  const { reviewHash, resultSource, integrityValid, integrityErrorCode, artifactClassification, ...payload } = review
  const expectedReviewHash = stableBusinessActionGateHash(payload)
  const valid = Boolean(reviewHash) && reviewHash === expectedReviewHash
  return { integrityValid: valid, expectedReviewHash, actualReviewHash: reviewHash || '', errorCode: valid ? '' : 'BUSINESS_ACTION_REVIEW_INTEGRITY_FAILED' }
}

export function restoreBusinessActionReview(review = {}) {
  const integrity = validateBusinessActionReviewIntegrity(review)
  if (!integrity.integrityValid) return { restored: false, review: null, ...integrity }
  return { restored: true, review: { ...cloneBusinessActionGateValue(review), resultSource: 'existing_review_result', integrityValid: true }, ...integrity }
}
