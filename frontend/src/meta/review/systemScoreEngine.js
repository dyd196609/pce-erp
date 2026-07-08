import { buildEnterpriseReviewMatrix } from './enterpriseReviewMatrix.js'

function toScore(value) {
  return Math.round(Number(value || 0) * 100)
}

function average(values) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

export function calculateSystemScores(reviewStatus) {
  const matrix = buildEnterpriseReviewMatrix(reviewStatus)

  const systemHealthScore = toScore(average([
    reviewStatus.complianceRate,
    matrix.crossModuleConsistency,
    matrix.dataFlowIntegrity,
  ]))

  const executionIntegrityScore = toScore(average([
    matrix.executionTraceability,
    matrix.dataFlowIntegrity,
  ]))

  const businessAlignmentScore = toScore(average([
    reviewStatus.completionRate,
    matrix.scopeScores.find((item) => item.scope === 'ProfitOS')?.complianceRate || 0,
    matrix.scopeScores.find((item) => item.scope === 'BI')?.complianceRate || 0,
  ]))

  return {
    systemHealthScore,
    executionIntegrityScore,
    businessAlignmentScore,
    matrix,
  }
}

