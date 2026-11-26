import fs from 'node:fs'
import path from 'node:path'

const root = path.join(process.cwd(), 'test-results/bank-send-production-release-v67')
const isolationUrl = 'http://127.0.0.1:8000/api/finance/bank-send-dual-isolation-checks/'
const reviewUrl = 'http://127.0.0.1:8000/api/finance/bank-send-production-release-reviews/'
const [isolationResponse, reviewResponse] = await Promise.all([
  fetch(isolationUrl),
  fetch(reviewUrl),
])
if (!isolationResponse.ok || !reviewResponse.ok) {
  throw new Error(`V67 API unavailable: ${isolationResponse.status}/${reviewResponse.status}`)
}
const isolationPayload = await isolationResponse.json()
const reviewPayload = await reviewResponse.json()
const isolation = isolationPayload.data
const review = reviewPayload.data
const check = isolation.results[0]
const reviewRow = review.results[0]
const stats = JSON.parse(
  fs.readFileSync(path.join(root, 'playwright-report.json'), 'utf8'),
).stats ?? {}
const isolationSurfaces = [
  isolation.recordCount,
  isolation.isolationFacts.recordCount,
  isolation.diagnosticFacts.recordCount,
  isolation.strictFacts.recordCount,
  isolation.acceptanceFacts.recordCount,
]
const reviewSurfaces = [
  review.recordCount,
  review.reviewFacts.recordCount,
  review.diagnosticFacts.recordCount,
  review.strictFacts.recordCount,
  review.acceptanceFacts.recordCount,
]
const rules = {
  'RELEASE-001': check?.productionInterfaceDisabled === true,
  'RELEASE-002': check?.productionCredentialAbsent === true,
  'RELEASE-003': check?.sendPermissionDisabled === true,
  'RELEASE-004': check?.paymentPermissionDisabled === true,
  'RELEASE-005': check?.result === 'passed'
    && check.environmentCheck && check.credentialCheck
    && check.permissionCheck && check.interfaceCheck,
  'RELEASE-006': reviewRow?.decisions?.length >= 2
    && new Set(reviewRow.decisions.map(row => row.operator)).size
      === reviewRow.decisions.length
    && new Set(reviewRow.decisions.map(row => row.role)).size
      === reviewRow.decisions.length,
  'RELEASE-007': reviewRow?.status === 'locked'
    && reviewRow.productionReviewMeansSent === false
    && reviewRow.bankSent === false,
  'RELEASE-008': review.bankSendObjectCount === 0
    && review.bankMessageSendWriteCount === 0,
  'RELEASE-009': review.paymentExecutionCount === 0
    && review.paymentExecutionWriteCount === 0,
  'RELEASE-CHECKS-001-010': Array.from(
    { length: 10 }, (_, i) => `RELEASE-${String(i + 1).padStart(3, '0')}`,
  ).every(rule => reviewRow?.checks?.[rule] === true),
  'STATE-001': reviewRow?.stateMachineConsistent === true
    && reviewRow.statusTransitionCount === 3,
  'FACT-ISOLATION-001': new Set(isolationSurfaces).size === 1,
  'FACT-REVIEW-001': new Set(reviewSurfaces).size === 1,
  'ACCEPTANCE-001': isolation.acceptanceFacts.acceptanceStatus === 'PASS'
    && isolation.acceptanceFacts.unknownReason === ''
    && review.acceptanceFacts.acceptanceStatus === 'PASS'
    && review.acceptanceFacts.unknownReason === '',
  'SECURITY-001': review.financialImpactWriteCount === 0
    && review.businessProgressWriteCount === 0,
  'PLAYWRIGHT-001': Number(stats.unexpected ?? 0) === 0
    && Number(stats.expected ?? 0) >= 8,
}
const checks = Object.entries(rules).map(([rule, passed]) => ({
  rule,
  passed: Boolean(passed),
}))
const report = {
  result: checks.every(row => row.passed) ? 'passed' : 'failed',
  version: reviewPayload.version,
  rules: checks,
  summary: {
    passed: checks.filter(row => row.passed).length,
    failed: checks.filter(row => !row.passed).length,
  },
  dualIsolation: {
    checkCount: isolation.checkCount,
    passedCount: isolation.passedCount,
    environment: check.environmentCheck,
    credential: check.credentialCheck,
    permission: check.permissionCheck,
    interface: check.interfaceCheck,
  },
  manualReleaseReview: {
    reviewCount: review.reviewCount,
    status: reviewRow.status,
    statusChain: 'draft -> reviewing -> review_passed -> locked',
    decisions: reviewRow.decisions,
    productionReviewMeansSent: false,
  },
  fiveSurfaceFacts: {
    dualIsolation: {
      api: isolationSurfaces[0],
      page: isolationSurfaces[1],
      diagnostic: isolationSurfaces[2],
      strictFacts: isolationSurfaces[3],
      acceptanceFacts: isolationSurfaces[4],
    },
    releaseReview: {
      api: reviewSurfaces[0],
      page: reviewSurfaces[1],
      diagnostic: reviewSurfaces[2],
      strictFacts: reviewSurfaces[3],
      acceptanceFacts: reviewSurfaces[4],
    },
  },
  protection: {
    dualIsolationWriteCount: review.dualIsolationWriteCount,
    releaseReviewWriteCount: review.releaseReviewWriteCount,
    bankMessageSendWriteCount: review.bankMessageSendWriteCount,
    paymentExecutionWriteCount: review.paymentExecutionWriteCount,
    financialImpactWriteCount: review.financialImpactWriteCount,
    businessProgressWriteCount: review.businessProgressWriteCount,
    productionUserDataWritten: false,
  },
  playwright: {
    expected: Number(stats.expected ?? 0),
    unexpected: Number(stats.unexpected ?? 0),
  },
}
fs.writeFileSync(
  path.join(root, 'v67_acceptance_report.json'),
  `${JSON.stringify(report, null, 2)}\n`,
)
console.log(JSON.stringify(report, null, 2))
if (report.result !== 'passed') process.exitCode = 1
