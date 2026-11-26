import { analyzePatch } from './tracePatchEngine.js'

function calcRisk(patch) {
  let risk = 0

  if (patch.type === 'ARCH_REFACTOR') risk += 3
  if (patch.type === 'SCHEMA_PATCH') risk += 2
  if (patch.type === 'CODE_OPTIMIZATION') risk += 1

  if (patch.target?.includes('api')) risk += 2
  if (patch.target?.includes('schema')) risk += 2

  if (risk <= 2) return 'LOW'
  if (risk <= 4) return 'MEDIUM'
  if (risk <= 6) return 'HIGH'
  return 'CRITICAL'
}

function attachRisk(patches) {
  return patches.map((patch) => ({
    ...patch,
    risk: calcRisk(patch),
  }))
}

export function analyzeRisk() {
  const patchData = analyzePatch()
  const risked = attachRisk(patchData.patches)

  return {
    patches: risked,
    summary: {
      low: risked.filter((patch) => patch.risk === 'LOW').length,
      medium: risked.filter((patch) => patch.risk === 'MEDIUM').length,
      high: risked.filter((patch) => patch.risk === 'HIGH').length,
      critical: risked.filter((patch) => patch.risk === 'CRITICAL').length,
    },
  }
}
