import { ApiContract } from './apiContract.js'
import { getAllSchemas } from './schemaRegistry.js'

export function suggestRepair() {
  const schemas = getAllSchemas()
  const suggestions = []

  schemas.forEach((schema) => {
    const module = schema.api?.module

    if (!module) {
      suggestions.push({
        type: 'MISSING_MODULE',
        fix: 'Add api.module to schema',
      })
      return
    }

    const contract = ApiContract[module]

    if (!contract) {
      suggestions.push({
        type: 'MISSING_CONTRACT',
        module,
        fix: `Add contract for ${module}`,
      })
      return
    }

    if (!contract.list) {
      suggestions.push({
        type: 'MISSING_LIST_API',
        module,
        fix: `Add list endpoint for ${module}`,
      })
    }

    if (!contract.detail) {
      suggestions.push({
        type: 'MISSING_DETAIL_API',
        module,
        fix: `Add detail endpoint for ${module}`,
      })
    }
  })

  return suggestions
}
