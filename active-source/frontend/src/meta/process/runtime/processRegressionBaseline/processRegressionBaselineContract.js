export function createProcessRegressionBaseline(definition = {}) {
  if (!definition.baselineCode) throw new Error('PROCESS_REGRESSION_BASELINE_CODE_REQUIRED')
  if (!Array.isArray(definition.steps) || !definition.steps.length) throw new Error('PROCESS_REGRESSION_BASELINE_STEPS_REQUIRED')
  return Object.freeze({ baselineCode: definition.baselineCode, version: definition.version,
    processRule: 'PROCESS-008', immutable: true,
    steps: Object.freeze(definition.steps.map(step => Object.freeze({ ...step }))) })
}

