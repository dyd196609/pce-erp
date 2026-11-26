import { listMarketplaceModules } from '../marketplaceEngine.js'
import { evaluatePluginQuality } from './qualityEngine.js'

export function evolveEcosystem() {
  const quality = evaluatePluginQuality()
  const marketplace = listMarketplaceModules()
  const promoted = quality.ranking.filter((plugin) => plugin.score >= 85)
  const deprecated = quality.ranking.filter((plugin) => plugin.score < 50)

  return {
    mode: 'V21_ECOSYSTEM_EVOLUTION',
    promoted,
    deprecated,
    actions: [
      ...promoted.map((plugin) => ({
        type: 'PROMOTE_PLUGIN',
        pluginId: plugin.pluginId,
        reason: 'HIGH_QUALITY_SCORE',
      })),
      ...deprecated.map((plugin) => ({
        type: 'DEPRECATE_PLUGIN',
        pluginId: plugin.pluginId,
        reason: 'LOW_QUALITY_SCORE',
      })),
    ],
    marketplaceSize: marketplace.length,
  }
}
