const defaultCountries = {
  CN: { population: 1410, productivity: 1.12, pricePressure: 0.04, employmentBase: 0.96, industryIndex: 1.18 },
  US: { population: 335, productivity: 1.28, pricePressure: 0.03, employmentBase: 0.95, industryIndex: 1.08 },
  DE: { population: 84, productivity: 1.2, pricePressure: 0.025, employmentBase: 0.94, industryIndex: 1.12 },
  VN: { population: 100, productivity: 0.82, pricePressure: 0.05, employmentBase: 0.93, industryIndex: 0.92 },
}

function normalizeCountry(country = {}) {
  const code = country.code || country.country || 'CN'
  const base = defaultCountries[code] || defaultCountries.CN

  return {
    code,
    ...base,
    ...country,
  }
}

export function calculateGDP(country = {}) {
  const c = normalizeCountry(country)
  return Math.round(c.population * c.productivity * 120)
}

export function simulateInflation(country = {}) {
  const c = normalizeCountry(country)
  return Number((c.pricePressure + Math.max(0, c.demandPressure || 0) * 0.01).toFixed(3))
}

export function simulateEmployment(country = {}) {
  const c = normalizeCountry(country)
  const shockPenalty = c.shock ? 0.04 : 0
  return Number(Math.max(0.75, c.employmentBase - shockPenalty).toFixed(3))
}

export function simulateIndustry(country = {}) {
  const c = normalizeCountry(country)
  return Math.round(c.industryIndex * c.productivity * 100)
}

export function simulateCountryEconomy(country = {}) {
  const normalized = normalizeCountry(country)

  return {
    mode: 'V26_COUNTRY_ECONOMIC_MODEL',
    country: normalized.code,
    gdp: calculateGDP(normalized),
    inflation: simulateInflation(normalized),
    employment: simulateEmployment(normalized),
    industrialOutput: simulateIndustry(normalized),
  }
}
