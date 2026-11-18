export function validateProcessRegressionBaseline(baseline, checkpoints = []) {
  const checks = Object.freeze(baseline.steps.map((step, index) => {
    const checkpoint = checkpoints[index]
    const valid = checkpoint?.stepCode === step.stepCode
      && checkpoint?.objectType === step.objectType
      && checkpoint?.result === 'PASS'
      && (typeof step.validate !== 'function' || step.validate(checkpoint.object, checkpoints))
    return Object.freeze({ stepCode: step.stepCode, result: valid ? 'PASS' : 'FAIL', valid })
  }))
  const valid = checks.length === baseline.steps.length && checks.every(item => item.valid)
  return Object.freeze({ baselineCode: baseline.baselineCode, processRule: 'PROCESS-008',
    result: valid ? 'PASS' : 'FAIL', valid, checks })
}

