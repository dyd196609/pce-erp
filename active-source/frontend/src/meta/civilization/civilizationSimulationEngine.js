import { simulateGlobalEconomy } from '../global/globalEconomicBrain.js'
import { simulateHumanBehavior } from './humanBehaviorEngine.js'
import { simulatePolicyImpact } from './governanceAIEngine.js'

function clampScore(value) {
  return Math.max(0, Math.min(100, Math.round(value)))
}

function resolveEconomy(state = {}) {
  return state.economy || state.globalEconomy || simulateGlobalEconomy(state)
}

export function simulateSociety(state = {}) {
  const economy = resolveEconomy(state)
  const macro = economy.macro || {}
  const market = economy.market || {}
  const enterprises = market.enterprises || []
  const inflationPenalty = Number(macro.inflationPressure || 0) * 35
  const growthBoost = Number(macro.gdpTrend || 0) * 4
  const stabilityIndex = clampScore(68 + growthBoost - inflationPenalty)
  const cityDevelopment = enterprises.map((enterprise) => ({
    country: enterprise.country,
    cityCluster: `${enterprise.country}_industrial_region`,
    developmentIndex: clampScore(55 + (enterprise.regionalDemand || 0) / 12 - (enterprise.region?.logisticsCost || 0) * 80),
  }))

  return {
    mode: 'SOCIETY_STRUCTURE_SIMULATION',
    stabilityIndex,
    cityDevelopment,
    industryDistribution: enterprises.map((enterprise) => ({
      country: enterprise.country,
      role: enterprise.role,
      concentration: enterprise.regionalDemand > enterprise.inventory ? 'HIGH_DEMAND' : 'BALANCED',
    })),
    educationStructure: {
      skilledLaborIndex: clampScore(62 + growthBoost),
      reskillingNeed: stabilityIndex < 75 ? 'ELEVATED' : 'NORMAL',
    },
    healthcareResources: {
      accessIndex: clampScore(70 - inflationPenalty / 2),
      pressure: inflationPenalty > 8 ? 'MEDIUM' : 'LOW',
    },
    employmentStructure: {
      employmentIndex: clampScore(66 + growthBoost - inflationPenalty / 2),
      dominantSector: enterprises[0]?.role || 'general',
    },
  }
}

export function simulatePopulationDynamics(state = {}) {
  const economy = resolveEconomy(state)
  const behavior = state.behavior || simulateHumanBehavior({ ...state, economy })
  const migration = behavior.laborMigration
  const migrationPressure = clampScore(Number(migration.flowIntensity || 0))
  const populationFlow = (economy.market?.enterprises || []).map((enterprise) => ({
    country: enterprise.country,
    inflow: enterprise.country === migration.to ? migrationPressure : Math.round(migrationPressure / 4),
    outflow: enterprise.country === migration.from ? migrationPressure : Math.round(migrationPressure / 5),
  }))

  return {
    mode: 'POPULATION_DYNAMICS',
    migrationPressure,
    populationFlow,
    laborAvailability: migrationPressure > 50 ? 'SHIFTING' : 'STABLE',
  }
}

export function simulateEconomyIntegration(state = {}) {
  const economy = resolveEconomy(state)
  const society = state.society || simulateSociety({ ...state, economy })
  const civilizationKpi = {
    civilizationHealthIndex: clampScore(
      society.stabilityIndex * 0.45 +
      (economy.market?.network?.globalOptimization?.networkEfficiency || 70) * 0.35 +
      (economy.market?.demandSupplyBalance || 0.8) * 20
    ),
    societyStability: society.stabilityIndex,
    economicResilience: clampScore(70 + (economy.macro?.gdpTrend || 0) * 3 - (economy.macro?.inflationPressure || 0) * 40),
  }

  return {
    mode: 'ECONOMY_SOCIETY_INTEGRATION',
    economy,
    civilizationKpi,
    unifiedCivilizationState: {
      economicMode: economy.mode,
      socialMode: society.mode,
      macroTrend: economy.macro?.gdpTrend,
      stabilityIndex: society.stabilityIndex,
    },
  }
}

export function simulateCivilization(state = {}) {
  const economyBase = resolveEconomy(state)
  const behavior = simulateHumanBehavior({ ...state, economy: economyBase })
  const society = simulateSociety({ ...state, economy: economyBase, behavior })
  const population = simulatePopulationDynamics({ ...state, economy: economyBase, behavior, society })
  const economy = simulateEconomyIntegration({ ...state, economy: economyBase, behavior, society, population })
  const governance = simulatePolicyImpact({ ...state, economy: economyBase, behavior, society, population })

  return {
    mode: 'V13.7_DIGITAL_CIVILIZATION_OS',
    society,
    population,
    economy,
    governance,
    behavior,
  }
}
