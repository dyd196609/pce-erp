import { getReviewRuntimeSchema } from './reviewEngine.js'
import { buildEnterpriseReviewMatrix } from './enterpriseReviewMatrix.js'
import { calculateSystemScores } from './systemScoreEngine.js'

function rate(count, total) {
  return total === 0 ? 0 : count / total
}

function calculateModuleCompliance(moduleEntry, runtime) {
  const features = moduleEntry.features || []
  const required = features.filter((feature) => feature.required)
  const passed = required.filter((feature) => {
    const domainReady = runtime.exists[feature.domain] !== false
    return feature.state.passed && domainReady
  })

  return {
    module: moduleEntry.module,
    total: features.length,
    required: required.length,
    passed: passed.length,
    complianceRate: rate(passed.length, required.length || features.length),
    status: passed.length === required.length ? 'PASSED' : 'REVIEW_REQUIRED',
  }
}

export function evaluateFeatureCompliance(schema = getReviewRuntimeSchema()) {
  const features = schema.rules.map((rule) => {
    const domainReady = schema.runtime.exists[rule.domain] !== false

    return {
      id: rule.id,
      module: rule.module,
      domain: rule.domain,
      feature: rule.feature,
      required: rule.required,
      sourceStatus: rule.status,
      state: rule.state.state,
      label: rule.state.label,
      progress: rule.state.progress,
      completed: rule.state.completed,
      passed: rule.state.passed && domainReady,
      domainReady,
    }
  })

  const requiredFeatures = features.filter((feature) => feature.required)
  const passed = requiredFeatures.filter((feature) => feature.passed)
  const completed = features.filter((feature) => feature.completed)

  return {
    total: features.length,
    required: requiredFeatures.length,
    passed: passed.length,
    completed: completed.length,
    complianceRate: rate(passed.length, requiredFeatures.length),
    completionRate: rate(completed.length, features.length),
    features,
  }
}

export function compareSystemWithReviewTemplate(schema = getReviewRuntimeSchema()) {
  const modules = Object.values(schema.modules).map((moduleEntry) =>
    calculateModuleCompliance(moduleEntry, schema.runtime)
  )

  return {
    modules,
    missingDomains: schema.rules
      .filter((rule) => schema.runtime.exists[rule.domain] === false)
      .map((rule) => rule.domain),
  }
}

export function generateReviewStatus(workbook) {
  const schema = getReviewRuntimeSchema(workbook)
  const compliance = evaluateFeatureCompliance(schema)
  const comparison = compareSystemWithReviewTemplate(schema)
  const baseStatus = {
    mode: 'V12.4_ENTERPRISE_REVIEW_RUNTIME',
    sourceSheets: schema.sourceSheets,
    scopes: schema.scopes,
    complianceRate: compliance.complianceRate,
    completionRate: compliance.completionRate,
    featureStatus: compliance.features,
    moduleCompliance: comparison.modules,
    systemEvaluation: schema.evaluation,
    organization: {
      ...schema.runtime.organization,
      departments: schema.runtime.departments,
      roles: schema.runtime.roles,
      employees: schema.runtime.employees,
      materials: schema.runtime.materials,
    },
    missingDomains: comparison.missingDomains,
    summary: {
      totalFeatures: compliance.total,
      passedFeatures: compliance.passed,
      completedFeatures: compliance.completed,
      reviewStatus: comparison.missingDomains.length === 0 ? 'READY' : 'INCOMPLETE',
    },
  }

  return {
    ...baseStatus,
    enterpriseMatrix: buildEnterpriseReviewMatrix(baseStatus),
    systemScores: calculateSystemScores(baseStatus),
  }
}
