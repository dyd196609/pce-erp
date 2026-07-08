export const PAGE_STATE = {
  NORMAL: 'NORMAL',
  MONITOR: 'MONITOR',
  RESTRICTED: 'RESTRICTED',
  BLOCKED: 'BLOCKED',
}

export const PageExecutionContractV1 = {
  version: '1.0',
  pageType: 'list',
  schema: null,
  execution: {
    allowEdit: true,
    allowDelete: true,
    allowNavigation: true,
  },
  reviewHook: {
    beforeRender: 'reviewControlEngine.runReviewControlLoop',
    beforeAction: 'reviewControlEngine.enforceUIControl',
    afterAction: 'reviewControlEngine.runReviewControlLoop',
  },
  controlMode: PAGE_STATE.NORMAL,
  optimization: {
    autoReorderColumns: false,
    autoReduceLoad: false,
    autoRouteOptimization: false,
  },
}

export function createPageExecutionContract(schema = null, overrides = {}) {
  return {
    ...PageExecutionContractV1,
    ...overrides,
    schema,
    execution: {
      ...PageExecutionContractV1.execution,
      ...(overrides.execution || {}),
    },
    reviewHook: {
      ...PageExecutionContractV1.reviewHook,
      ...(overrides.reviewHook || {}),
    },
    optimization: {
      ...PageExecutionContractV1.optimization,
      ...(overrides.optimization || {}),
    },
  }
}

