import { evaluateEcosystemHealth } from './healthEngine.js'
import { evaluatePluginQuality } from './qualityEngine.js'
import { evaluateSecurity } from './securityEngine.js'
import { evaluateRevenueFairness } from './revenueFairnessEngine.js'
import { evolveEcosystem } from './evolutionEngine.js'
import { getPluginRegistry } from '../pluginSDK.js'
import { evaluatePlugin } from './pluginQualityEngine.js'
import { maintainSystemBalance } from './stabilityEngine.js'
import { runSecurityGovernance } from './securityGovernanceEngine.js'
import { governRevenueFairness } from './revenueFairnessController.js'
import { runEvolutionPolicyAI } from './evolutionPolicyAI.js'

export function runEcosystemGovernance(context = {}) {
  const health = evaluateEcosystemHealth(context)
  const quality = evaluatePluginQuality()
  const security = evaluateSecurity()
  const revenueFairness = evaluateRevenueFairness()
  const evolution = evolveEcosystem()
  const plugins = getPluginRegistry()
  const pluginQuality = plugins.map(evaluatePlugin)
  const stabilityGovernance = maintainSystemBalance()
  const securityGovernance = runSecurityGovernance(plugins)
  const revenueGovernance = governRevenueFairness()
  const evolutionPolicy = runEvolutionPolicyAI()

  return {
    mode: 'V21_ECOSYSTEM_GOVERNANCE',
    governanceMode: 'ACTIVE',
    ecosystemQualityControl: 'ENABLED',
    stabilityGovernance: 'ACTIVE',
    revenueGovernance: 'ACTIVE',
    ecosystemHealthMonitoring: 'ACTIVE',
    pluginScoring: 'ENABLED',
    revenueFairness: 'ACTIVE',
    health,
    quality,
    security,
    revenueFairness,
    evolution,
    pluginQuality,
    stabilityGovernance,
    securityGovernance,
    revenueGovernance,
    evolutionPolicy,
    decision: security.threatCount > 0
      ? 'ISOLATE_RISK'
      : quality.averageScore < 60
      ? 'QUALITY_REVIEW'
      : 'ECOSYSTEM_HEALTHY',
  }
}
