import { getReviewScopes } from './reviewScopeMapper.js'

function average(values) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

function scopeCompliance(reviewStatus, scope) {
  const relatedFeatures = reviewStatus.featureStatus.filter((feature) =>
    scope.domains.includes(feature.domain)
  )

  const passed = relatedFeatures.filter((feature) => feature.passed)

  return {
    scope: scope.key,
    label: scope.label,
    total: relatedFeatures.length,
    passed: passed.length,
    complianceRate: relatedFeatures.length ? passed.length / relatedFeatures.length : 0,
  }
}

export function buildEnterpriseReviewMatrix(reviewStatus) {
  const scopeScores = getReviewScopes().map((scope) => scopeCompliance(reviewStatus, scope))
  const moduleCompliance = reviewStatus.moduleCompliance || []
  const crossModuleConsistency = average(scopeScores.map((item) => item.complianceRate))

  const dataFlowIntegrity = average([
    scopeScores.find((item) => item.scope === 'ERP')?.complianceRate || 0,
    scopeScores.find((item) => item.scope === 'SCM')?.complianceRate || 0,
    scopeScores.find((item) => item.scope === 'WMS')?.complianceRate || 0,
    scopeScores.find((item) => item.scope === 'BI')?.complianceRate || 0,
  ])

  const executionTraceability = average([
    scopeScores.find((item) => item.scope === 'MES')?.complianceRate || 0,
    scopeScores.find((item) => item.scope === 'SCM')?.complianceRate || 0,
    scopeScores.find((item) => item.scope === 'ProfitOS')?.complianceRate || 0,
  ])

  return {
    moduleCompliance,
    scopeScores,
    crossModuleConsistency,
    dataFlowIntegrity,
    executionTraceability,
  }
}

