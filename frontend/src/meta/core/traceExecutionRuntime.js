import { analyzePatch } from './tracePatchEngine.js'

function simulateApply(patch) {
  return {
    target: patch.target,
    status: 'SIMULATED',
    result: 'NOT_EXECUTED',
    risk: patch.type,
  }
}

function validate(patchResults) {
  const errors = []

  for (const result of patchResults) {
    if (!result.target) {
      errors.push('missing target')
    }
  }

  return {
    valid: errors.length === 0,
    errors,
  }
}

function buildRollbackPlan(patchResults) {
  return patchResults.map((result) => ({
    target: result.target,
    status: 'ROLLBACK_SIMULATED',
    action: 'No runtime change was applied; rollback is a no-op.',
  }))
}

function buildSelfHealingLoop(patchData, results, validation) {
  return {
    diagnosis: patchData.patches.length > 0 ? 'PATCHES_AVAILABLE' : 'NO_PATCH_REQUIRED',
    simulated: results.length,
    validation,
    nextStep: validation.valid
      ? 'Human review required before any real patch execution.'
      : 'Fix validation errors and re-run dry-run simulation.',
  }
}

export function runExecutionSimulation() {
  const patchData = analyzePatch()
  const results = patchData.patches.map(simulateApply)
  const validation = validate(results)

  return {
    health: patchData.health,
    mode: 'DRY_RUN_ONLY',
    results,
    validation,
    rollback: buildRollbackPlan(results),
    selfHealingLoop: buildSelfHealingLoop(patchData, results, validation),
  }
}
