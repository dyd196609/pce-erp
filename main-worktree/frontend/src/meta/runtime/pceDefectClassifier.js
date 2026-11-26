import { pceBasicOperationDefectTaxonomy } from './pceBasicOperationDefectTaxonomy.js'

export const PCE_DEFECT_CLASSIFIER_VERSION = 'V1.14.2.8.3.1'

export function classifyPceVerificationFailure(input = {}) {
  const searchable = [
    input.testId,
    input.pageRoute,
    input.pageArea,
    input.componentName,
    input.userAction,
    input.expectedResult,
    input.actualResult,
    input.domInfo,
    input.styleInfo,
    input.failureReport,
  ].map((item) => String(item || '').toLowerCase()).join(' ')

  for (const rule of pceBasicOperationDefectTaxonomy) {
    if (rule.keywords.some((keyword) => searchable.includes(String(keyword).toLowerCase()))) {
      return {
        category: rule.category,
        subcategory: rule.subcategory,
        matchedBy: 'deterministic_keyword',
        matchedKeywords: rule.keywords.filter((keyword) => searchable.includes(String(keyword).toLowerCase())),
        manualClassificationRequired: false,
      }
    }
  }

  return {
    category: 'manual_classification_required',
    subcategory: 'manual_classification_required',
    matchedBy: 'none',
    matchedKeywords: [],
    manualClassificationRequired: true,
  }
}

export function classifyPceVerificationFailures(failures = []) {
  return failures.map((failure) => ({
    ...failure,
    classification: classifyPceVerificationFailure(failure),
  }))
}
