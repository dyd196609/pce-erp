import { generateEnterprise } from './enterpriseGenerator'
import { createEnterpriseInstance } from '../runtime/multiEnterpriseRuntime'

/**
 * ============================
 * AI Enterprise Cloner
 * ============================
 */

export const cloneEnterprise = async (industry) => {
  const result = await generateEnterprise(industry)

  const instanceId = createEnterpriseInstance(result)

  return {
    instanceId,
    result,
  }
}
