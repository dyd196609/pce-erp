import { optimizeRevenue } from './autonomousRevenueEngine.js'
import { runAutonomousEcosystem } from '../ecosystem/autonomous/autonomousRuntime.js'

export function decidePricingChanges(context = {}) {
  const revenue = optimizeRevenue(context)

  return {
    action: revenue.revenueModel.multiplier > 1 ? 'ADJUST_PRICE' : 'KEEP_PRICE',
    model: revenue.revenueModel,
  }
}

export function decideModuleActivation(context = {}) {
  const ecosystem = runAutonomousEcosystem(context)
  const promoted = ecosystem.governance.evolution?.promoted || []

  return {
    action: promoted.length ? 'ACTIVATE_PROMOTED_MODULES' : 'KEEP_CURRENT_MODULES',
    modules: promoted.map((item) => item.pluginId),
  }
}

export function decideFeatureRestriction(context = {}) {
  const ecosystem = runAutonomousEcosystem(context)
  const threats = ecosystem.governance.security.threatCount

  return {
    action: threats > 0 ? 'RESTRICT_RISKY_FEATURES' : 'ALLOW_STANDARD_FEATURES',
    restricted: threats > 0,
    reason: threats > 0 ? 'ECOSYSTEM_SECURITY_THREAT' : 'NO_THREAT',
  }
}

export function decideEnterpriseUpgrades(context = {}) {
  const revenue = optimizeRevenue(context)

  return {
    action: revenue.upgradePaths.length ? 'SUGGEST_UPGRADE' : 'NO_UPGRADE_REQUIRED',
    upgradePaths: revenue.upgradePaths,
  }
}

export function runAutonomousBusinessDecision(context = {}) {
  return {
    mode: 'V23_AUTONOMOUS_BUSINESS_DECISION',
    pricing: decidePricingChanges(context),
    moduleActivation: decideModuleActivation(context),
    featureRestriction: decideFeatureRestriction(context),
    enterpriseUpgrade: decideEnterpriseUpgrades(context),
  }
}
