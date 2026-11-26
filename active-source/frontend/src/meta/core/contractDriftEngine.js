import { ApiContract } from './apiContract.js'
import { getAllSchemas } from './schemaRegistry.js'

export function calculateDriftScore() {
  let total = 0
  let issues = 0

  const schemas = getAllSchemas()

  schemas.forEach((schema) => {
    const module = schema.api?.module
    total += 1

    const contract = ApiContract[module]

    if (!contract) {
      issues += 1
      return
    }

    if (!contract.list || !contract.detail) {
      issues += 1
    }
  })

  return {
    driftScore: total === 0 ? 0 : issues / total,
    totalModules: total,
    issueModules: issues,
  }
}
