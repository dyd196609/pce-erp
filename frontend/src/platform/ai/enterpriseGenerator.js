import { buildBlueprint } from './enterpriseBlueprint'
import { generateERP } from './aiErpGenerator'

/**
 * ============================
 * AI Enterprise Generator
 * ============================
 */

export const generateEnterprise = async (industry) => {
  const blueprint = buildBlueprint(industry)

  const enterprise = await generateERP(industry)

  return {
    blueprint,
    enterprise,
  }
}
