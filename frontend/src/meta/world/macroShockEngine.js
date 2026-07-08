import { simulateCountryEconomy } from './countryEconomicModel.js'

export function simulateCrisis(context = {}) {
  const severity = Number(context.shock?.severity ?? 0.2)

  return {
    type: context.shock?.type || 'INFLATION_SHOCK',
    severity,
    gdpImpact: Number((-severity * 2.4).toFixed(2)),
    demandImpact: Number((-severity * 1.6).toFixed(2)),
  }
}

export function simulateWarDisruptionInflationShock(context = {}) {
  const crisis = simulateCrisis(context)

  return {
    logisticsRisk: Number((crisis.severity * 0.8).toFixed(2)),
    inflationImpact: Number((crisis.severity * 0.12).toFixed(3)),
    supplyRisk: crisis.severity > 0.35 ? 'HIGH' : 'MEDIUM',
  }
}

export function modelEconomicRecovery(context = {}) {
  const crisis = simulateCrisis(context)
  const recoveryMonths = Math.round(6 + crisis.severity * 24)

  return {
    recoveryMonths,
    policy: crisis.severity > 0.35 ? 'STIMULUS_AND_SUPPLY_REROUTE' : 'TARGETED_SUPPORT',
  }
}

export function simulateMacroShock(context = {}) {
  const countries = context.countries?.length ? context.countries : [{ code: 'CN' }, { code: 'US' }, { code: 'DE' }]
  const crisis = simulateCrisis(context)

  return {
    mode: 'V26_MACRO_SHOCK',
    crisis,
    shockImpact: simulateWarDisruptionInflationShock(context),
    recovery: modelEconomicRecovery(context),
    countryImpact: countries.map((country) => simulateCountryEconomy({
      ...country,
      shock: true,
      demandPressure: crisis.severity,
    })),
  }
}
